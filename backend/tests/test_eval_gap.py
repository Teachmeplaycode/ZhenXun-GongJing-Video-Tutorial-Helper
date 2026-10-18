"""scripts/eval_gap.py 的缺口清单（Issue #7）。"""
import json
from pathlib import Path

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
