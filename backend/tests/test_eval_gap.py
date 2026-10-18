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
    spec = {"videos": {f"v{i}": {"category": c} for i, c in enumerate(list(__import__("evals.schema", fromlist=["CATEGORIES"]).CATEGORIES) * 6)},
            "cases": [{"id": f"c{i}", "video": "v0", "qtype": "summary"} for i in range(150)]}
    g = gap_report(spec)
    assert g["meets_target"] is True



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
