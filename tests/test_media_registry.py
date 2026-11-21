import json
from pathlib import Path

import pytest

from scripts.campaign_registry import create_campaign
from scripts.project_registry import create_project
from scripts.providers.openverse import _normalize, save_image_candidates
from scripts.media_registry import MediaReviewError, review_media_candidate, check_media_candidate, media_review_status


def _fixture(tmp_path):
    root = tmp_path / "projects"
    create_project("Media review", "viral", root=root)
    create_campaign("media-review", "Campaign", "YouTube Shorts", root=root)
    item = {
        "title": "Photo", "url": "https://cdn.example.org/photo.jpg",
        "foreign_landing_url": "https://example.org/photo", "creator": "Creator",
        "creator_url": "https://example.org/creator", "license": "by",
        "license_version": "4.0", "license_url": "https://creativecommons.org/licenses/by/4.0/",
        "source": "Example", "category": "photograph",
        "thumbnail": "https://cdn.example.org/thumb.jpg", "width": 1280, "height": 720,
        "attribution": "Photo by Creator",
    }
    candidate = _normalize("photo", [item])[0]
    save_image_candidates("media-review", "campaign", [candidate], root=root)
    return root, candidate


def test_media_review_requires_explicit_source_and_rights_evidence(tmp_path):
    root, candidate = _fixture(tmp_path)
    with pytest.raises(MediaReviewError, match="explicit source-page review"):
        review_media_candidate("media-review", "campaign", candidate.candidate_id,
            decision="approved", reviewer="Operator", rights_evidence="terms checked",
            reviewed_license="CC BY 4.0", source_reviewed=False, root=root)
    assert check_media_candidate("media-review", "campaign", candidate.candidate_id, root=root)[0] is False


def test_approved_review_is_bound_to_candidate_metadata_hash(tmp_path):
    root, candidate = _fixture(tmp_path)
    event = review_media_candidate("media-review", "campaign", candidate.candidate_id,
        decision="approved", reviewer="Operator", rights_evidence="Original source license page reviewed.",
        reviewed_license="CC BY 4.0, attribution required", attribution="Creator; link to source",
        source_reviewed=True, root=root)
    assert event["decision"] == "approved"
    assert check_media_candidate("media-review", "campaign", candidate.candidate_id, root=root) == (True, [])
    assert media_review_status("media-review", "campaign", candidate.candidate_id, root=root) == "reviewed_approved"
    ledger = root / "media-review" / "campaigns" / "campaign" / "media_candidates.jsonl"
    data = json.loads(ledger.read_text(encoding="utf-8"))
    data["attribution"] = "changed attribution"
    ledger.write_text(json.dumps(data) + "\n", encoding="utf-8")
    passed, problems = check_media_candidate("media-review", "campaign", candidate.candidate_id, root=root)
    assert passed is False
    assert "stale" in problems[0]
    assert media_review_status("media-review", "campaign", candidate.candidate_id, root=root) == "review_stale"


def test_latest_rejection_revokes_approved_candidate(tmp_path):
    root, candidate = _fixture(tmp_path)
    review_media_candidate("media-review", "campaign", candidate.candidate_id,
        decision="approved", reviewer="Operator", rights_evidence="Source license verified.",
        reviewed_license="CC BY 4.0", source_reviewed=True, root=root)
    review_media_candidate("media-review", "campaign", candidate.candidate_id,
        decision="rejected", reviewer="Operator", notes="Source page unavailable.", root=root)
    passed, problems = check_media_candidate("media-review", "campaign", candidate.candidate_id, root=root)
    assert passed is False
    assert "rejected" in problems[0]


def test_new_license_metadata_version_invalidates_old_review(tmp_path):
    root, candidate = _fixture(tmp_path)
    review_media_candidate("media-review", "campaign", candidate.candidate_id,
        decision="approved", reviewer="Operator", rights_evidence="Original license page reviewed.",
        reviewed_license="CC BY 4.0", source_reviewed=True, root=root)
    updated_item = {
        "title": "Photo", "url": "https://cdn.example.org/photo.jpg",
        "foreign_landing_url": "https://example.org/photo", "creator": "Creator",
        "creator_url": "https://example.org/creator", "license": "by-sa",
        "license_version": "4.0", "license_url": "https://creativecommons.org/licenses/by-sa/4.0/",
        "source": "Example", "category": "photograph",
        "thumbnail": "https://cdn.example.org/thumb.jpg", "width": 1280, "height": 720,
        "attribution": "Photo by Creator",
    }
    refreshed = _normalize("new query", [updated_item])[0]
    assert refreshed.candidate_id == candidate.candidate_id
    saved = save_image_candidates("media-review", "campaign", [refreshed], root=root)
    assert saved["added"] == 1
    passed, problems = check_media_candidate("media-review", "campaign", candidate.candidate_id, root=root)
    assert passed is False
    assert "stale" in problems[0]
