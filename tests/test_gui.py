import json

from scripts.money_geta_gui import candidate_rows, save_settings


def test_candidate_rows_reads_candidate_metadata(tmp_path):
    job = tmp_path / "job"
    job.mkdir()
    (job / "candidates.json").write_text(json.dumps({
        "candidates": [{"n": 2, "start": 12.5, "end": 29.0, "title": "Chase scene", "score": 0.91}]
    }), encoding="utf-8")
    assert candidate_rows(job) == [{"n": 2, "start": 12.5, "end": 29.0, "title": "Chase scene", "score": 0.91}]


def test_candidate_rows_rejects_missing_required_number(tmp_path):
    job = tmp_path / "job"
    job.mkdir()
    (job / "candidates.json").write_text('{"candidates":[{"start":1,"end":2}]}', encoding="utf-8")
    try:
        candidate_rows(job)
    except KeyError:
        pass
    else:
        raise AssertionError("missing candidate number must not be silently accepted")


def test_settings_round_trip(tmp_path, monkeypatch):
    import scripts.money_geta_gui as gui
    settings_file = tmp_path / "settings.json"
    monkeypatch.setattr(gui, "SETTINGS_FILE", settings_file)
    monkeypatch.setattr(gui, "APP_DIR", tmp_path)
    data = {"mpt_dir": "C:/MPT", "gtavi_dir": "C:/GTAVI", "jobs_dir": "C:/Jobs"}
    save_settings(data)
    assert json.loads(settings_file.read_text(encoding="utf-8")) == data


def test_gui_exposes_research_and_script_workflows():
    import scripts.money_geta_gui as gui
    assert hasattr(gui.MoneyGetaApp, "_build_research")
    assert hasattr(gui.MoneyGetaApp, "run_campaign_research_ui")
    assert hasattr(gui.MoneyGetaApp, "_build_script")
    assert hasattr(gui.MoneyGetaApp, "generate_script_ui")
    assert hasattr(gui.MoneyGetaApp, "open_script_draft")


def test_gui_script_review_controls_are_hash_bound():
    import scripts.money_geta_gui as gui
    assert hasattr(gui.MoneyGetaApp, "review_script_ui")
    assert "script_review_id_var" in gui.MoneyGetaApp._build_script.__code__.co_names
    assert "script_review_sha_var" in gui.MoneyGetaApp._build_script.__code__.co_names
