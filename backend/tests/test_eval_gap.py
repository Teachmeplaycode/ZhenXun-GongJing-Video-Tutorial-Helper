"""scripts/eval_gap.py 的缺口清单（Issue #7）。"""
import json
from pathlib import Path
import pytest

from scripts.eval_gap import gap_report, TENTATIVE_VIDEOS, TENTATIVE_QTYPES

CASES = Path(__file__).resolve().parent.parent / "evals" / "cases.json"


def test_current_gap_is_honest():
    spec = json.loads(CASES.read_text())
    g = gap_report(spec)
    assert g["videos"] == 11
    assert g["cases"] == 47
    assert g["videos_short"] == 19
    assert g["cases_short"] == 103
    assert g["meets_target"] is False


def test_all_categories_below_target():
    spec = json.loads(CASES.read_text())
    g = gap_report(spec)
    assert len(g["categories_below_target"]) == 6


def test_ad_shopping_is_empty():
    spec = json.loads(CASES.read_text())
    g = gap_report(spec)
    assert g["videos_per_category"]["ad_shopping"] == 0
    assert g["cases_per_category"]["ad_shopping"] == 0


def test_qtype_counts_sum_to_cases():
    spec = json.loads(CASES.read_text())
    g = gap_report(spec)
    assert sum(g["cases_per_qtype"].values()) == g["cases"]


def test_tentative_lists_are_documented():
    assert len(TENTATIVE_VIDEOS) == 4
    assert len(TENTATIVE_QTYPES) == 6
    for v, why in TENTATIVE_VIDEOS.items():
        assert "勉强" in why
    for c, why in TENTATIVE_QTYPES.items():
        assert "勉强" in why


def test_meets_target_when_full():
    spec = full_valid_spec()
    g = gap_report(spec)
    assert g["meets_target"] is True
    assert g["videos"] == 30 and g["cases"] == 150
    assert all(count == 5 for count in g["videos_per_category"].values())



def test_gap_cli_rejects_invalid_dataset_before_printing(tmp_path, monkeypatch, capsys):
    import pytest
    from scripts import eval_gap
    spec = json.loads(CASES.read_text())
    spec["cases"][0]["qtype"] = "unknown"
    path = tmp_path / "invalid.json"
    path.write_text(json.dumps(spec))
    monkeypatch.setattr(eval_gap, "CASES", path)
    monkeypatch.setattr("sys.argv", ["eval_gap.py", "--json"])
    with pytest.raises(ValueError, match="qtype"):
        eval_gap.main()
    assert not capsys.readouterr().out


def full_valid_spec():
    from evals.schema import CATEGORIES
    categories = list(CATEGORIES)
    return {"videos": {f"v{i}": {"url": f"https://example.com/watch?v={i}", "note": "test fixture",
                                 "category": categories[i // 5]} for i in range(30)},
            "cases": [{"id": f"c{i}", "video": f"v{i % 30}", "question": "question", "rubric": "confirmed test answer",
                       "qtype": "summary"} for i in range(150)]}


@pytest.mark.parametrize("json_mode", [False, True])
def test_gap_cli_cannot_claim_target_from_a_duplicate_url_in_another_category(tmp_path, monkeypatch, capsys, json_mode):
    from scripts import eval_gap
    spec = full_valid_spec()
    # Nominally 30 rows and 5 per category, but this replaces one sports/tutorial source with an alias.
    spec["videos"]["v5"]["url"] = " HTTPS://EXAMPLE.COM:443/watch?v=0 "
    path = tmp_path / "duplicates.json"
    path.write_text(json.dumps(spec))
    monkeypatch.setattr(eval_gap, "CASES", path)
    monkeypatch.setattr("sys.argv", ["eval_gap.py"] + (["--json"] if json_mode else []))
    with pytest.raises(ValueError, match="重复"):
        eval_gap.main()
    assert capsys.readouterr().out == ""


def test_gap_cli_counts_distinct_query_video_ids_without_merging_them(tmp_path, monkeypatch, capsys):
    from scripts import eval_gap
    path = tmp_path / "distinct.json"
    path.write_text(json.dumps(full_valid_spec()))
    monkeypatch.setattr(eval_gap, "CASES", path)
    monkeypatch.setattr("sys.argv", ["eval_gap.py", "--json"])
    eval_gap.main()
    report = json.loads(capsys.readouterr().out)
    assert report["videos"] == 30 and report["meets_target"] is True
    assert all(count == 5 for count in report["videos_per_category"].values())


@pytest.mark.parametrize("has_cases", [False, True])
def test_unreferenced_inventory_does_not_count_towards_video_or_category_coverage(has_cases):
    from evals.schema import CATEGORIES
    spec = full_valid_spec()
    if has_cases:
        for case in spec["cases"]:
            case["video"] = "v0"
    else:
        spec["cases"] = []
    report = gap_report(spec)
    active = 1 if has_cases else 0
    assert report["registered_videos"] == 30
    assert report["videos"] == active and report["videos_short"] == 30 - active
    assert len(report["unreferenced_videos"]) == 30 - active
    assert sum(report["videos_per_category"].values()) == active
    assert report["videos_per_category"][next(iter(CATEGORIES))] == active
    assert report["categories_below_target"] == list(CATEGORIES)
    assert report["meets_target"] is False


def test_last_video_must_have_a_case_before_video_and_category_targets_are_met():
    spec = full_valid_spec()
    for case in spec["cases"]:
        if case["video"] == "v29":
            case["video"] = "v0"
    report = gap_report(spec)
    assert report["videos"] == 29 and report["videos_short"] == 1
    assert report["videos_per_category"]["ad_shopping"] == 4
    assert report["categories_below_target"] == ["ad_shopping"]
    assert report["unreferenced_videos"] == ["v29"]
    assert report["meets_target"] is False
    spec["cases"][-1]["video"] = "v29"
    covered = gap_report(spec)
    assert covered["videos"] == 30 and covered["cases"] == 150
    assert covered["unreferenced_videos"] == []
    assert covered["videos_per_category"]["ad_shopping"] == 5
    assert covered["meets_target"] is True


def test_thirty_exercised_videos_still_require_five_in_each_category():
    spec = full_valid_spec()
    spec["videos"]["v29"]["category"] = "lecture"
    report = gap_report(spec)
    assert report["videos"] == 30 and report["videos_short"] == 0
    assert report["videos_per_category"]["ad_shopping"] == 4
    assert report["categories_below_target"] == ["ad_shopping"]
    assert report["meets_target"] is False


@pytest.mark.parametrize("json_mode", [False, True])
def test_gap_cli_reports_unreferenced_inventory_without_claiming_coverage(tmp_path, monkeypatch, capsys, json_mode):
    from scripts import eval_gap
    spec = full_valid_spec()
    for case in spec["cases"]:
        case["video"] = "v0"
    path = tmp_path / "inventory.json"
    path.write_text(json.dumps(spec))
    monkeypatch.setattr(eval_gap, "CASES", path)
    monkeypatch.setattr("sys.argv", ["eval_gap.py"] + (["--json"] if json_mode else []))
    eval_gap.main()
    text = capsys.readouterr().out
    if json_mode:
        report = json.loads(text)
        assert report["videos"] == 1 and report["registered_videos"] == 30
        assert report["cases"] == 150 and report["meets_target"] is False
        assert sum(report["videos_per_category"].values()) == 1
    else:
        assert "视频（已关联题目）：1/30（还差 29）" in text
        assert "29 个未关联题目，不计入覆盖率" in text
        assert "是否达标：否" in text
