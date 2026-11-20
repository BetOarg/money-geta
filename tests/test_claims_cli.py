from scripts import claims_cli


def test_claim_cli_requires_subcommand():
    import pytest
    with pytest.raises(SystemExit):
        claims_cli.main([])


def test_claim_cli_add_dispatches_and_outputs_json(monkeypatch, capsys):
    monkeypatch.setattr(claims_cli, "create_claim", lambda *a, **k: {
        "claim_id": "c1", "status": "unverified"
    })
    result = claims_cli.main([
        "add", "--project", "p", "--campaign", "c",
        "--claim", "A statement", "--evidence", "e1"
    ])
    assert result == 0
    assert '"claim_id": "c1"' in capsys.readouterr().out
