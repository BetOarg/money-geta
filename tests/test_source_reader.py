import json
import socket
import pytest
from scripts.providers import source_reader as reader


def test_url_validation_blocks_local_hosts_credentials_and_secrets():
    urls = ["file:///etc/passwd", "http://localhost/a", "http://127.0.0.1/",
            "https://user:pass@example.com/", "https://example.com/?access_token=x",
            "https://printer.local/"]
    for url in urls:
        with pytest.raises(reader.SourceReadError):
            reader._clean_url(url)


def test_dns_blocks_mixed_public_and_private_addresses(monkeypatch):
    monkeypatch.setattr(reader.socket, "getaddrinfo", lambda *a, **k: [
        (socket.AF_INET, socket.SOCK_STREAM, 6, "", ("8.8.8.8", 443)),
        (socket.AF_INET, socket.SOCK_STREAM, 6, "", ("10.0.0.2", 443)),
    ])
    with pytest.raises(reader.SourceReadError, match="non-public"):
        reader._public_ips("example.com", 443)


def test_html_extracts_visible_text_and_hash(monkeypatch):
    body = b"<title>Primary source</title><meta name='description' content='Context'><h1>Fact</h1><script>secret()</script><p>Visible text</p>"
    monkeypatch.setattr(reader, "_fetch_once", lambda url, timeout: (
        200, {"content-type": "text/html; charset=utf-8"}, body, "https://example.com/a"))
    doc = reader.read_source("https://example.com/a")
    assert doc.title == "Primary source"
    assert doc.description == "Context"
    assert "Visible text" in doc.text and "secret()" not in doc.text
    assert len(doc.content_sha256) == 64


def test_redirect_downgrade_and_redirect_limit_blocked(monkeypatch):
    monkeypatch.setattr(reader, "_fetch_once", lambda url, timeout: (
        302, {"location": "http://example.com/plain"}, b"", url))
    with pytest.raises(reader.SourceReadError, match="HTTPS-to-HTTP"):
        reader.read_source("https://example.com/secure")
    monkeypatch.setattr(reader, "_fetch_once", lambda url, timeout: (
        302, {"location": "/again"}, b"", url))
    with pytest.raises(reader.SourceReadError, match="five redirects"):
        reader.read_source("https://example.com/start")


def test_content_type_and_body_limit(monkeypatch):
    monkeypatch.setattr(reader, "_fetch_once", lambda url, timeout: (
        200, {"content-type": "video/mp4"}, b"x", url))
    with pytest.raises(reader.SourceReadError, match="Unsupported"):
        reader.read_source("https://example.com/video")
    monkeypatch.setattr(reader, "_fetch_once", lambda url, timeout: (
        200, {"content-type": "text/plain"}, b"x" * (reader.MAX_BODY_BYTES + 1), url))
    with pytest.raises(reader.SourceReadError, match="2 MiB"):
        reader.read_source("https://example.com/large")


def test_ledger_append_deduplicates_and_refuses_corruption(tmp_path, monkeypatch):
    root = tmp_path / "projects"
    campaign = root / "p" / "campaigns" / "c"
    campaign.mkdir(parents=True)
    (root / "p" / "project.json").write_text("{}", encoding="utf-8")
    (campaign / "campaign.json").write_text("{}", encoding="utf-8")
    monkeypatch.setattr(reader, "get_project", lambda *a, **k: {})
    monkeypatch.setattr(reader, "get_campaign", lambda *a, **k: {})
    doc = reader.SourceDocument(1, "e1", "https://example.com", "https://example.com", 200,
                                "text/plain", "Title", "", "text", "hash", 4, 0, "now")
    ledger = reader.record_source_document("p", "c", doc, root=root)
    reader.record_source_document("p", "c", doc, root=root)
    assert len(ledger.read_text(encoding="utf-8").splitlines()) == 1
    ledger.write_text("{broken\n", encoding="utf-8")
    with pytest.raises(reader.SourceReadError, match="malformed"):
        reader.record_source_document("p", "c", doc, root=root)
