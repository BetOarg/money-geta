from scripts import read_source


def test_cli_requires_explicit_network_opt_in(capsys):
    assert read_source.main(["--project", "p", "--campaign", "c", "--url", "https://example.com"]) == 2
    assert "BLOCKED" in capsys.readouterr().out


def test_cli_records_source_and_disclaims_verification(monkeypatch, capsys, tmp_path):
    from scripts.providers.source_reader import SourceDocument
    doc = SourceDocument(1, "evidence", "https://example.com", "https://example.com", 200,
                         "text/plain", "Example", "", "source text", "hash", 11, 0, "now")
    monkeypatch.setattr(read_source, "read_source", lambda *a, **k: doc)
    monkeypatch.setattr(read_source, "record_source_document", lambda *a, **k: tmp_path / "source_ledger.jsonl")
    result = read_source.main(["--project", "p", "--campaign", "c", "--url", "https://example.com", "--allow-network"])
    output = capsys.readouterr().out
    assert result == 0
    assert "EVIDENCE: evidence" in output
    assert "LEDGER:" in output
    assert "does not verify factual claims" in output
