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


def test_gui_can_re_register_edited_script_versions():
    import scripts.money_geta_gui as gui
    assert hasattr(gui.MoneyGetaApp, "reregister_script_ui")
    assert "script_reregister_btn" in gui.MoneyGetaApp._build_script.__code__.co_names


def test_gui_exposes_openverse_image_search_workflow():
    import scripts.money_geta_gui as gui
    assert hasattr(gui.MoneyGetaApp, "image_search_ui")
    assert hasattr(gui.MoneyGetaApp, "show_image_candidate")
    assert hasattr(gui.MoneyGetaApp, "open_image_source")
    assert "image_results_list" in gui.MoneyGetaApp._build_image_search.__code__.co_names


def test_gui_exposes_image_candidate_rights_review_controls():
    import scripts.money_geta_gui as gui
    assert hasattr(gui.MoneyGetaApp, "review_media_ui")
    assert "media_approve_btn" in gui.MoneyGetaApp._build_image_search.__code__.co_names
    assert "media_rights_evidence_var" in gui.MoneyGetaApp._build_image_search.__code__.co_names


def test_gui_download_action_requires_reviewed_candidate_state():
    import scripts.money_geta_gui as gui
    assert hasattr(gui.MoneyGetaApp, "download_image_candidate_ui")
    assert "image_download_btn" in gui.MoneyGetaApp._build_image_search.__code__.co_names
    assert "reviewed_approved" in gui.MoneyGetaApp.show_image_candidate.__code__.co_consts
    assert "media_download_done" in gui.MoneyGetaApp._poll_events.__code__.co_consts


def test_gui_image_download_requires_confirmation_and_network_opt_in():
    import scripts.money_geta_gui as gui
    import inspect
    source = inspect.getsource(gui.MoneyGetaApp.download_image_candidate_ui)
    assert "askyesno" in source
    assert "allow_network=True" in source
    assert "confirm_download=True" in source


def test_desktop_local_media_library_tab_has_search_and_integrity_controls():
    import inspect
    from scripts.money_geta_gui import MoneyGetaApp
    build_source = inspect.getsource(MoneyGetaApp._build_media_library)
    load_source = inspect.getsource(MoneyGetaApp.media_library_load_ui)
    verify_source = inspect.getsource(MoneyGetaApp.media_library_verify_ui)
    poll_source = inspect.getsource(MoneyGetaApp._poll_events)
    assert "Biblioteca local" in inspect.getsource(MoneyGetaApp.__init__)
    assert "search_media_assets" in load_source and "list_media_assets" in load_source
    assert "verify_media_library" in verify_source
    assert "media_library_verify_done" in poll_source and "media_library_done" in poll_source
    assert "media_library_items" in build_source and "usable_for_selection" in poll_source


def test_gui_exposes_scene_visual_plan_review_workflow():
    import inspect
    from scripts.money_geta_gui import MoneyGetaApp
    build = inspect.getsource(MoneyGetaApp._build_scene_visual_plan)
    refresh = inspect.getsource(MoneyGetaApp.scene_plan_refresh_scripts_ui)
    generate = inspect.getsource(MoneyGetaApp.scene_plan_build_ui)
    assign = inspect.getsource(MoneyGetaApp.scene_plan_assign_asset_ui)
    save = inspect.getsource(MoneyGetaApp.scene_plan_save_ui)
    poll = inspect.getsource(MoneyGetaApp._poll_events)
    assert "Plan visual" in inspect.getsource(MoneyGetaApp.__init__)
    assert "scene_plan_refresh_scripts_ui" in build
    assert "check_script" in refresh
    assert "build_scene_asset_plan" in generate
    assert "selected_candidate_id" in assign
    assert "save_scene_visual_plan" in save
    assert "scene_plan_done" in poll and "scene_plan_error" in poll
    from scripts.scene_visual_plan_store import save_scene_visual_plan
    assert "render_authorized" in inspect.getsource(save_scene_visual_plan)

def test_gui_scene_visual_plan_displays_local_thumbnail_preview():
    import inspect
    from scripts.money_geta_gui import MoneyGetaApp
    build = inspect.getsource(MoneyGetaApp._build_scene_visual_plan)
    preview = inspect.getsource(MoneyGetaApp._scene_plan_preview_asset)
    assert "scene_plan_preview_label" in build
    assert "ImageTk" in preview and "thumbnail" in preview
    assert "local_path" in preview and "Path" in preview
    assert "https://" not in preview
