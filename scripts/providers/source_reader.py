"""Bounded, SSRF-resistant reader for public HTML/text research sources."""
from __future__ import annotations

import hashlib
import http.client
import ipaddress
import json
import re
import socket
import ssl
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from email.message import Message
from html.parser import HTMLParser
from pathlib import Path
from urllib.parse import parse_qsl, urljoin, urlsplit, urlunsplit

from scripts.campaign_registry import get_campaign
from scripts.project_registry import default_projects_root, get_project, safe_slug


class SourceReadError(RuntimeError):
    """A source could not be fetched or safely interpreted."""


MAX_BODY_BYTES = 2 * 1024 * 1024
MAX_TEXT_CHARS = 20_000
MAX_REDIRECTS = 5
SECRET_QUERY = re.compile(r"(?:token|api[_-]?key|access[_-]?token|auth|signature|secret|password|passwd|credential)", re.I)


@dataclass(frozen=True)
class SourceDocument:
    schema_version: int
    evidence_id: str
    requested_url: str
    final_url: str
    status_code: int
    content_type: str
    title: str
    description: str
    text: str
    content_sha256: str
    byte_count: int
    redirect_count: int
    retrieved_at: str

    def to_dict(self) -> dict:
        return asdict(self)


class _VisibleHTML(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.title_parts, self.text_parts = [], []
        self.description = ""
        self.in_title = False
        self.hidden = 0

    def handle_starttag(self, tag, attrs):
        tag = tag.lower()
        values = {k.lower(): v or "" for k, v in attrs}
        if tag in {"script", "style", "noscript", "svg", "template"}:
            self.hidden += 1
        elif tag == "title":
            self.in_title = True
        elif tag == "meta" and values.get("name", "").lower() in {"description", "og:description"}:
            self.description = values.get("content", "")[:1000]
        elif tag in {"p", "div", "br", "li", "h1", "h2", "h3", "section", "article"}:
            self.text_parts.append("\n")

    def handle_endtag(self, tag):
        tag = tag.lower()
        if tag in {"script", "style", "noscript", "svg", "template"} and self.hidden:
            self.hidden -= 1
        elif tag == "title":
            self.in_title = False
        elif tag in {"p", "div", "li", "h1", "h2", "h3", "section", "article"}:
            self.text_parts.append("\n")

    def handle_data(self, data):
        if self.in_title:
            self.title_parts.append(data)
        if not self.hidden:
            value = " ".join(data.split())
            if value:
                self.text_parts.append(value)

    def result(self):
        title = " ".join(" ".join(self.title_parts).split())[:500]
        text = re.sub(r"\n{3,}", "\n\n", "\n".join(self.text_parts))
        return title, self.description.strip(), text.strip()[:MAX_TEXT_CHARS]


def _clean_url(value: str):
    if not isinstance(value, str) or len(value) > 4096:
        raise SourceReadError("URL must be a string no longer than 4096 characters.")
    try:
        parsed = urlsplit(value.strip())
        port = parsed.port
    except ValueError:
        raise SourceReadError("URL is malformed.") from None
    scheme = parsed.scheme.lower()
    if scheme not in {"http", "https"} or not parsed.hostname:
        raise SourceReadError("Only absolute HTTP or HTTPS URLs are supported.")
    if parsed.username or parsed.password:
        raise SourceReadError("URLs containing embedded credentials are blocked.")
    if any(SECRET_QUERY.search(key) for key, _ in parse_qsl(parsed.query, keep_blank_values=True)):
        raise SourceReadError("Credential-like URL query parameters are blocked.")
    host = parsed.hostname.encode("idna").decode("ascii").lower().rstrip(".")
    if host in {"localhost", "localhost.localdomain"} or host.endswith(".local"):
        raise SourceReadError("Local hostnames are blocked.")
    try:
        literal = ipaddress.ip_address(host)
    except ValueError:
        literal = None
    if literal is not None and not literal.is_global:
        raise SourceReadError("Non-public IP addresses are blocked.")
    port = port or (443 if scheme == "https" else 80)
    if port != (443 if scheme == "https" else 80):
        raise SourceReadError("Only default HTTP/HTTPS ports are supported.")
    clean = urlunsplit((scheme, host, parsed.path or "/", parsed.query, ""))
    return clean, urlsplit(clean), port, host


def _public_ips(host: str, port: int) -> list[str]:
    try:
        answers = socket.getaddrinfo(host, port, type=socket.SOCK_STREAM)
    except OSError:
        raise SourceReadError("Source hostname could not be resolved.") from None
    ips = sorted({item[4][0] for item in answers})
    if not ips:
        raise SourceReadError("Source hostname returned no addresses.")
    for raw in ips:
        try:
            address = ipaddress.ip_address(raw.split("%", 1)[0])
        except ValueError:
            raise SourceReadError("Source hostname returned an invalid address.") from None
        if not address.is_global:
            raise SourceReadError("Source resolves to a non-public IP; request blocked.")
    return ips


class _PinnedHTTP(http.client.HTTPConnection):
    def __init__(self, host, port, ip, timeout):
        super().__init__(host, port, timeout=timeout)
        self.ip = ip

    def connect(self):
        self.sock = socket.create_connection((self.ip, self.port), self.timeout)


class _PinnedHTTPS(http.client.HTTPSConnection):
    def __init__(self, host, port, ip, timeout):
        super().__init__(host, port, timeout=timeout, context=ssl.create_default_context())
        self.ip = ip

    def connect(self):
        raw = socket.create_connection((self.ip, self.port), self.timeout)
        try:
            self.sock = self._context.wrap_socket(raw, server_hostname=self.host)
        except Exception:
            raw.close()
            raise


def _fetch_once(url: str, timeout: float):
    clean, parsed, port, host = _clean_url(url)
    ip = _public_ips(host, port)[0]
    path = parsed.path or "/"
    if parsed.query:
        path += "?" + parsed.query
    cls = _PinnedHTTPS if parsed.scheme == "https" else _PinnedHTTP
    conn = cls(host, port, ip, timeout)
    try:
        conn.request("GET", path, headers={
            "User-Agent": "Money-Geta-ResearchReader/1.0",
            "Accept": "text/html,application/xhtml+xml,text/plain;q=0.9",
            "Accept-Encoding": "identity",
            "Connection": "close",
        })
        response = conn.getresponse()
        headers = {k.lower(): v for k, v in response.getheaders()}
        try:
            if int(headers.get("content-length", "0")) > MAX_BODY_BYTES:
                raise SourceReadError("Source response exceeds the 2 MiB limit.")
        except ValueError:
            raise SourceReadError("Invalid Content-Length header.") from None
        body = response.read(MAX_BODY_BYTES + 1)
        if len(body) > MAX_BODY_BYTES:
            raise SourceReadError("Source response exceeds the 2 MiB limit.")
        return response.status, headers, body, clean
    except SourceReadError:
        raise
    except (OSError, http.client.HTTPException, ssl.SSLError):
        raise SourceReadError("Source request failed, timed out, or failed TLS validation.") from None
    finally:
        conn.close()


def read_source(url: str, *, timeout_seconds: float = 15.0) -> SourceDocument:
    if timeout_seconds <= 0 or timeout_seconds > 30:
        raise SourceReadError("Timeout must be between 0 and 30 seconds.")
    requested, _, _, _ = _clean_url(url)
    current, redirects = requested, 0
    while True:
        status, headers, body, final_url = _fetch_once(current, timeout_seconds)
        if len(body) > MAX_BODY_BYTES:
            raise SourceReadError("Source response exceeds the 2 MiB limit.")
        if status in {301, 302, 303, 307, 308}:
            location = headers.get("location")
            if not location or redirects >= MAX_REDIRECTS:
                raise SourceReadError("Missing redirect target or more than five redirects.")
            target = urljoin(final_url, location)
            if final_url.startswith("https://") and target.lower().startswith("http://"):
                raise SourceReadError("HTTPS-to-HTTP redirects are blocked.")
            current, _, _, _ = _clean_url(target)
            redirects += 1
            continue
        if status < 200 or status >= 300:
            raise SourceReadError(f"Source returned HTTP {status}.")
        mime = headers.get("content-type", "").split(";", 1)[0].strip().lower()
        if mime not in {"text/html", "application/xhtml+xml", "text/plain"}:
            raise SourceReadError(f"Unsupported source content type: {mime or 'missing'}.")
        msg = Message()
        msg["content-type"] = headers.get("content-type", "")
        charset = msg.get_content_charset() or "utf-8"
        try:
            decoded = body.decode(charset, errors="replace")
        except LookupError:
            decoded = body.decode("utf-8", errors="replace")
        if mime == "text/plain":
            title, description, text = "", "", decoded.strip()[:MAX_TEXT_CHARS]
        else:
            parser = _VisibleHTML()
            try:
                parser.feed(decoded)
                parser.close()
                title, description, text = parser.result()
            except Exception:
                raise SourceReadError("Source HTML could not be parsed.") from None
        if not text:
            raise SourceReadError("Source contained no extractable text.")
        digest = hashlib.sha256(body).hexdigest()
        retrieved = datetime.now(timezone.utc).isoformat()
        evidence_id = hashlib.sha256((final_url + "\n" + digest).encode()).hexdigest()
        return SourceDocument(1, evidence_id, requested, final_url, status, mime, title,
                              description, text, digest, len(body), redirects, retrieved)


def record_source_document(project_id: str, campaign_id: str, document: SourceDocument,
                           *, root: Path | None = None) -> Path:
    if safe_slug(project_id) != project_id or safe_slug(campaign_id) != campaign_id:
        raise SourceReadError("Project and campaign IDs must be normalized slugs.")
    projects_root = (root or default_projects_root()).expanduser().resolve()
    get_project(project_id, projects_root)
    get_campaign(project_id, campaign_id, projects_root)
    folder = (projects_root / project_id / "campaigns" / campaign_id).resolve()
    if not folder.is_relative_to(projects_root) or not folder.is_dir():
        raise SourceReadError("Campaign directory is invalid or outside projects root.")
    ledger = folder / "source_ledger.jsonl"
    if ledger.is_symlink():
        raise SourceReadError("Source ledger symlinks are blocked.")
    if ledger.exists():
        if not ledger.is_file():
            raise SourceReadError("Source ledger is not a regular file.")
        try:
            for line in ledger.read_text(encoding="utf-8").splitlines():
                if json.loads(line).get("evidence_id") == document.evidence_id:
                    return ledger
        except (OSError, UnicodeError, json.JSONDecodeError, AttributeError):
            raise SourceReadError("Existing source ledger is malformed; refusing to append.") from None
    try:
        with ledger.open("a", encoding="utf-8", newline="\n") as handle:
            handle.write(json.dumps(document.to_dict(), ensure_ascii=False, sort_keys=True) + "\n")
            handle.flush()
            import os
            os.fsync(handle.fileno())
    except OSError:
        raise SourceReadError("Could not persist source evidence.") from None
    return ledger
