import hashlib, json
import pytest
from scripts import approved_media_download as d

class Response:
    def __init__(self,data,ctype="image/png"):
        self.data=data; self.offset=0; self.headers={"Content-Type":ctype,"Content-Length":str(len(data))}; self.closed=False
    def read(self,size=-1):
        if self.offset>=len(self.data): return b""
        size=len(self.data) if size<0 else size
        block=self.data[self.offset:self.offset+size]; self.offset+=len(block); return block
    def close(self): self.closed=True

def resolver(host,port,**kwargs): return [(None,None,None,None,("8.8.8.8",port))]

def setup(tmp_path,monkeypatch,approved=True):
    cf=tmp_path/"p"/"campaigns"/"c"/"campaign.json"; cf.parent.mkdir(parents=True); cf.write_text("{}")
    cand={"candidate_id":"cand_1","image_url":"https://cdn.example/image.png","source_page_url":"https://source.example/item","license":"by","license_url":"https://license.example","creator":"Artist","attribution":"Artist"}
    monkeypatch.setattr(d,"_campaign_file",lambda *a,**k:cf)
    monkeypatch.setattr(d,"_read_candidates",lambda *a,**k:{cand["candidate_id"]:cand})
    monkeypatch.setattr(d,"check_media_candidate",lambda *a,**k:(approved,[] if approved else ["pending"]))
    monkeypatch.setattr(d,"_candidate_hash",lambda _: "a"*64)
    return cf,cand

def test_requires_explicit_double_opt_in(tmp_path,monkeypatch):
    setup(tmp_path,monkeypatch)
    with pytest.raises(d.MediaDownloadError,match="both explicit"):
        d.download_approved_candidate("p","c","cand_1")

def test_download_and_provenance_manifest(tmp_path,monkeypatch):
    cf,c=setup(tmp_path,monkeypatch); png=b"\x89PNG\r\n\x1a\n"+b"test-image-bytes"; r=Response(png)
    rec=d.download_approved_candidate("p","c","cand_1",allow_network=True,confirm_download=True,resolver=resolver,opener=lambda *a,**k:r)
    local=cf.parent/rec["local_path"]
    assert local.read_bytes()==png and rec["sha256"]==hashlib.sha256(png).hexdigest()
    assert json.loads((cf.parent/"media_download_ledger.jsonl").read_text().splitlines()[0])["candidate_id"]=="cand_1"
    assert r.closed

def test_unapproved_rights_blocks_network(tmp_path,monkeypatch):
    setup(tmp_path,monkeypatch,False)
    with pytest.raises(d.MediaDownloadError,match="Rights review"):
        d.download_approved_candidate("p","c","cand_1",allow_network=True,confirm_download=True,resolver=resolver,opener=lambda *a,**k:pytest.fail("unexpected network"))

def test_private_dns_blocked():
    private=lambda *a,**k:[(None,None,None,None,("127.0.0.1",443))]
    with pytest.raises(d.MediaDownloadError,match="non-global"): d._validate_url("https://example.com/img",resolver=private)

def test_https_only_and_sensitive_query():
    with pytest.raises(d.MediaDownloadError,match="HTTPS"): d._validate_url("http://example.com/img",resolver=resolver)
    with pytest.raises(d.MediaDownloadError,match="sensitive"): d._validate_url("https://example.com/img?token=abc",resolver=resolver)

def test_bad_signature_rejected_and_temp_removed(tmp_path,monkeypatch):
    cf,_=setup(tmp_path,monkeypatch); r=Response(b"not-an-image")
    with pytest.raises(d.MediaDownloadError,match="signature"):
        d.download_approved_candidate("p","c","cand_1",allow_network=True,confirm_download=True,resolver=resolver,opener=lambda *a,**k:r)
    assert not list((cf.parent/"media_assets").glob("*.part"))

def test_oversize_content_rejected(tmp_path,monkeypatch):
    cf,_=setup(tmp_path,monkeypatch); r=Response(b"\x89PNG\r\n\x1a\n"+b"x"*(d.MAX_BYTES+1))
    with pytest.raises(d.MediaDownloadError,match="20 MB"):
        d.download_approved_candidate("p","c","cand_1",allow_network=True,confirm_download=True,resolver=resolver,opener=lambda *a,**k:r)
    assert not list((cf.parent/"media_assets").glob("*.part"))

def test_unsafe_filename_id_rejected(tmp_path,monkeypatch):
    setup(tmp_path,monkeypatch)
    with pytest.raises(d.MediaDownloadError,match="filename"):
        d.download_approved_candidate("p","c","../escape",allow_network=True,confirm_download=True,resolver=resolver)

def test_repeat_download_returns_verified_existing_record(tmp_path,monkeypatch):
    cf,c=setup(tmp_path,monkeypatch); png=b"\x89PNG\r\n\x1a\n"+b"stable-image"; calls=[]
    def opener(*args,**kwargs): calls.append(1); return Response(png)
    first=d.download_approved_candidate("p","c","cand_1",allow_network=True,confirm_download=True,resolver=resolver,opener=opener)
    second=d.download_approved_candidate("p","c","cand_1",allow_network=True,confirm_download=True,resolver=resolver,opener=opener)
    assert first["sha256"]==second["sha256"]
    assert len(calls)==1


def test_https_connection_pins_to_validated_ip(monkeypatch):
    observed = {}
    class FakeTlsContext:
        verify_mode = __import__("ssl").CERT_REQUIRED
        check_hostname = True
        def wrap_socket(self, sock, server_hostname):
            observed["server_hostname"] = server_hostname
            return "tls-wrapped-socket"
    def fake_connect(address, timeout):
        observed["address"] = address
        observed["timeout"] = timeout
        return "raw-socket"
    monkeypatch.setattr(d.socket, "create_connection", fake_connect)
    connection = d._PinnedHTTPSConnection("assets.example.org", "8.8.8.8", 5, FakeTlsContext())
    connection.connect()
    assert observed == {"address": ("8.8.8.8", 443), "timeout": 5, "server_hostname": "assets.example.org"}
    assert connection.sock == "tls-wrapped-socket"


def test_public_dns_returns_validated_ip_list():
    records=[(None,None,None,None,("8.8.8.8",443)),(None,None,None,None,("1.1.1.1",443))]
    assert d._resolve_public("example.org",resolver=lambda *a,**k:records)==["1.1.1.1","8.8.8.8"]
