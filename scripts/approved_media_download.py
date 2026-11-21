"""Safe, explicit local downloads of operator-approved Openverse image candidates."""
from __future__ import annotations
import hashlib, http.client, ipaddress, json, os, re, socket, ssl, tempfile
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urlsplit, parse_qsl, urljoin
from scripts.media_registry import _campaign_file, _read_candidates, check_media_candidate, _candidate_hash
from scripts.artifact_registry import _reject_symlink_components

MAX_BYTES=20*1024*1024
MAX_REDIRECTS=3
TIMEOUT=15
ALLOWED_TYPES={"image/jpeg","image/png","image/webp","image/gif","image/bmp"}
SENSITIVE_QUERY_KEYS={"token","access_token","auth","key","api_key","signature","sig"}

class MediaDownloadError(ValueError):
    """Candidate download is not safe or cannot be verified."""

def _resolve_public(host, port=443, resolver=socket.getaddrinfo):
    try: records=resolver(host,port,type=socket.SOCK_STREAM)
    except OSError as exc: raise MediaDownloadError(f"DNS resolution failed: {host}") from exc
    addresses=sorted({r[4][0] for r in records})
    if not addresses: raise MediaDownloadError("Host has no address records.")
    for raw in addresses:
        try: ip=ipaddress.ip_address(raw.split("%",1)[0])
        except ValueError: raise MediaDownloadError("DNS returned an invalid address.") from None
        if not ip.is_global: raise MediaDownloadError("Private, reserved or non-global network destinations are blocked.")
    return addresses

def _validate_url(url, resolver=socket.getaddrinfo):
    if not isinstance(url,str) or len(url)>4096: raise MediaDownloadError("Image URL is invalid or too long.")
    try: parsed=urlsplit(url); port=parsed.port
    except ValueError: raise MediaDownloadError("Malformed image URL.") from None
    if parsed.scheme.lower()!="https" or not parsed.hostname or parsed.username or parsed.password:
        raise MediaDownloadError("Only credential-free HTTPS URLs are permitted.")
    if port not in (None,443): raise MediaDownloadError("Nonstandard HTTPS ports are blocked.")
    if any(k.lower() in SENSITIVE_QUERY_KEYS for k,_ in parse_qsl(parsed.query,keep_blank_values=True)):
        raise MediaDownloadError("URL contains a sensitive query parameter; refusing to persist it.")
    _resolve_public(parsed.hostname,port or 443,resolver=resolver)
    return url

class _PinnedHTTPSConnection(http.client.HTTPSConnection):
    def __init__(self, host, pinned_ip, timeout, context):
        super().__init__(host, timeout=timeout, context=context)
        self.pinned_ip=pinned_ip
    def connect(self):
        raw=socket.create_connection((self.pinned_ip,self.port),timeout=self.timeout)
        self.sock=self._context.wrap_socket(raw,server_hostname=self.host)

class _ResponseAdapter:
    def __init__(self,connection,response): self.connection=connection; self.response=response; self.headers=response.headers
    def read(self,size=-1): return self.response.read(size)
    def close(self):
        try: self.response.close()
        finally: self.connection.close()

def _open_checked(url,*,resolver=socket.getaddrinfo,timeout=TIMEOUT):
    current=url
    for redirect_count in range(MAX_REDIRECTS+1):
        _validate_url(current,resolver=resolver)
        parsed=urlsplit(current)
        ips=_resolve_public(parsed.hostname,parsed.port or 443,resolver=resolver)
        context=ssl.create_default_context()
        path=parsed.path or "/"
        if parsed.query: path+="?"+parsed.query
        last_error=None
        response=None
        connection=None
        for ip in ips:
            connection=_PinnedHTTPSConnection(parsed.hostname,ip,timeout,context)
            try:
                connection.request("GET",path,headers={"User-Agent":"Money-Geta/0.1","Accept":"image/*"})
                response=connection.getresponse()
                break
            except OSError as exc:
                connection.close()
                last_error=exc
        if response is None:
            raise MediaDownloadError("Could not connect to any validated public address.") from last_error
        if response.status in {301,302,303,307,308}:
            location=response.getheader("Location")
            response.close(); connection.close()
            if not location: raise MediaDownloadError("Redirect response has no Location header.")
            if redirect_count>=MAX_REDIRECTS: raise MediaDownloadError("Too many redirects.")
            current=urljoin(current,location)
            _validate_url(current,resolver=resolver)
            continue
        if response.status<200 or response.status>=300:
            response.close(); connection.close()
            raise MediaDownloadError(f"Image server returned HTTP {response.status}.")
        return _ResponseAdapter(connection,response)
    raise MediaDownloadError("Too many redirects.")

def _image_signature(data):
    checks=[(b"\xff\xd8\xff","image/jpeg",".jpg"),(b"\x89PNG\r\n\x1a\n","image/png",".png"),
      (b"GIF87a","image/gif",".gif"),(b"GIF89a","image/gif",".gif"),(b"BM","image/bmp",".bmp")]
    for magic,typ,ext in checks:
        if data.startswith(magic): return typ,ext
    if len(data)>=12 and data[:4]==b"RIFF" and data[8:12]==b"WEBP": return "image/webp",".webp"
    raise MediaDownloadError("Downloaded content does not match a supported image signature.")

def _safe_campaign_assets(campaign_file):
    root=campaign_file.parent.resolve(); folder=campaign_file.parent/"media_assets"
    _reject_symlink_components(folder); folder.mkdir(parents=True,exist_ok=True)
    resolved=folder.resolve(strict=True)
    if not resolved.is_relative_to(root) or not resolved.is_dir(): raise MediaDownloadError("Asset directory escaped campaign.")
    return resolved

def download_approved_candidate(project_id,campaign_id,candidate_id,*,allow_network=False,confirm_download=False,root=None,resolver=socket.getaddrinfo,opener=_open_checked):
    if not allow_network or not confirm_download: raise MediaDownloadError("BLOCKED: both explicit network opt-in and download confirmation are required.")
    if not re.fullmatch(r"[A-Za-z0-9_-]{1,128}",candidate_id or ""): raise MediaDownloadError("Candidate ID contains unsafe filename characters.")
    campaign_file=_campaign_file(project_id,campaign_id,root)
    candidate=_read_candidates(campaign_file).get(candidate_id)
    if candidate is None: raise MediaDownloadError("Candidate not found in campaign.")
    passed,problems=check_media_candidate(project_id,campaign_id,candidate_id,root=root)
    if not passed: raise MediaDownloadError("Rights review is not current and approved: "+"; ".join(problems))
    url=_validate_url(candidate.get("image_url"),resolver=resolver)
    assets=_safe_campaign_assets(campaign_file); ledger=campaign_file.parent/"media_download_ledger.jsonl"
    _reject_symlink_components(ledger)
    current_hash=_candidate_hash(candidate)
    if ledger.exists():
        if not ledger.is_file(): raise MediaDownloadError("Download ledger is not a regular file.")
        try: previous=[json.loads(line) for line in ledger.read_text(encoding="utf-8").splitlines() if line.strip()]
        except (OSError,UnicodeError,json.JSONDecodeError): raise MediaDownloadError("Download ledger is unreadable or malformed.") from None
        for row in reversed(previous):
            if row.get("candidate_id")==candidate_id and row.get("candidate_sha256")==current_hash:
                local=campaign_file.parent/row.get("local_path","")
                _reject_symlink_components(local)
                if not local.is_file() or not local.resolve().is_relative_to(assets):
                    raise MediaDownloadError("Previously downloaded asset is missing or outside the asset directory.")
                if hashlib.sha256(local.read_bytes()).hexdigest()!=row.get("sha256"):
                    raise MediaDownloadError("Previously downloaded asset failed integrity verification.")
                return row
    response=opener(url,resolver=resolver,timeout=TIMEOUT); tmp=None
    try:
        ctype=response.headers.get("Content-Type","").split(";",1)[0].strip().lower()
        if ctype not in ALLOWED_TYPES: raise MediaDownloadError(f"Unexpected content type: {ctype or 'missing'}.")
        clen=response.headers.get("Content-Length")
        if clen:
            try:
                declared_size = int(clen)
            except ValueError:
                raise MediaDownloadError("Invalid Content-Length header.") from None
            if declared_size > MAX_BYTES:
                raise MediaDownloadError("Image exceeds 20 MB limit.")
        digest=hashlib.sha256(); total=0
        with tempfile.NamedTemporaryFile(prefix=".asset-",suffix=".part",dir=assets,delete=False) as f:
            tmp=Path(f.name)
            while True:
                block=response.read(65536)
                if not block: break
                total+=len(block)
                if total>MAX_BYTES: raise MediaDownloadError("Image exceeds 20 MB limit.")
                digest.update(block); f.write(block)
            f.flush(); os.fsync(f.fileno())
            data=tmp.read_bytes()
        actual,ext=_image_signature(data)
        if actual!=ctype: raise MediaDownloadError("Content-Type does not match image signature.")
        final=assets/(candidate_id+ext); _reject_symlink_components(final)
        if final.exists():
            if hashlib.sha256(final.read_bytes()).hexdigest()!=digest.hexdigest(): raise MediaDownloadError("Refusing to overwrite existing file with different bytes.")
            tmp.unlink(); tmp=None
        else: tmp.replace(final); tmp=None
        record={"schema_version":1,"event_type":"approved_media_download","candidate_id":candidate_id,
          "candidate_sha256":current_hash,"source_url":url,"source_page_url":candidate.get("source_page_url"),
          "license":candidate.get("license"),"license_url":candidate.get("license_url"),"creator":candidate.get("creator"),
          "attribution":candidate.get("attribution"),"local_path":str(final.relative_to(campaign_file.parent)),
          "sha256":digest.hexdigest(),"size_bytes":total,"downloaded_at":datetime.now(timezone.utc).isoformat()}
        with ledger.open("a",encoding="utf-8",newline="\n") as f:
            f.write(json.dumps(record,ensure_ascii=False,sort_keys=True)+"\n"); f.flush(); os.fsync(f.fileno())
        return record
    finally:
        try: response.close()
        except Exception: pass
        if tmp is not None: tmp.unlink(missing_ok=True)
