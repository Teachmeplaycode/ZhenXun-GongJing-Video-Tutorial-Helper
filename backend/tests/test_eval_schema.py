"""evals/schema.py 的格式校验（Issue #7）。"""
from pathlib import Path

import pytest

from evals.schema import CATEGORIES, QTYPES, validate, load

CASES = Path(__file__).resolve().parent.parent / "evals" / "cases.json"


def test_categories_and_qtypes_match_issue():
    assert len(CATEGORIES) == 6
    assert len(QTYPES) == 5
    assert "ad_shopping" in CATEGORIES
    assert set(QTYPES) == {"locate", "visual_detail", "action_count", "summary", "verify"}


def test_current_cases_json_is_valid():
    errors = validate(__import__("json").loads(CASES.read_text()))
    assert errors == []


def test_current_cases_json_loads():
    spec = load(CASES)
    assert len(spec["videos"]) == 11
    assert len(spec["cases"]) == 47


def test_missing_category_is_reported():
    spec = {"videos": {"v": {"url": "x", "note": "n"}}, "cases": []}
    assert any("videos.v 缺少 category" in e for e in validate(spec))


def test_bad_category_is_reported():
    spec = {"videos": {"v": {"url": "x", "note": "n", "category": "bogus"}}, "cases": []}
    assert any("category=bogus" in e for e in validate(spec))


def test_dangling_video_reference():
    spec = {"videos": {}, "cases": [{"id": "c1", "video": "ghost", "question": "q", "qtype": "summary"}]}
    assert any("引用了不存在的视频 ghost" in e for e in validate(spec))


def test_missing_qtype_is_reported():
    spec = {"videos": {"v": {"url": "x", "note": "n", "category": "vlog"}},
            "cases": [{"id": "c1", "video": "v", "question": "q"}]}
    assert any("c1 缺少 qtype" in e for e in validate(spec))


def test_duplicate_ids():
    spec = {"videos": {"v": {"url": "x", "note": "n", "category": "vlog"}},
            "cases": [{"id": "c1", "video": "v", "question": "q", "qtype": "summary"},
                      {"id": "c1", "video": "v", "question": "q", "qtype": "summary"}]}
    assert any("id 重复：c1" in e for e in validate(spec))


def test_bad_contains_any_shape():
    spec = {"videos": {"v": {"url": "x", "note": "n", "category": "vlog"}},
            "cases": [{"id": "c1", "video": "v", "question": "q", "qtype": "summary",
                       "checks": {"contains_any": ["not-a-list-of-strings"]}}]}
    assert any("contains_any[0]" in e for e in validate(spec))


def test_load_raises_on_invalid():
    import tempfile
    with tempfile.NamedTemporaryFile("w", suffix=".json", delete=False) as f:
        f.write('{"videos": {"v": {"url": "x", "note": "n"}}, "cases": []}')
        path = Path(f.name)
    try:
        try:
            load(path)
            assert False, "没抛异常"
        except ValueError as e:
            assert "校验失败" in str(e)
    finally:
        path.unlink()


@pytest.mark.parametrize("field,value", [
    ("id", []), ("id", {}), ("id", 1),
    ("video", []), ("video", {}), ("video", 1),
    ("qtype", []), ("qtype", {}),
    ("checks", None), ("checks", 1), ("checks", []),
])
def test_malformed_case_fields_return_validation_errors(field, value):
    case = {"id": "c1", "video": "v", "question": "q", "qtype": "summary"}
    case[field] = value
    spec = {"videos": {"v": {"url": "x", "note": "n", "category": "vlog"}},
            "cases": [case]}
    assert validate(spec)


@pytest.mark.parametrize("category", [[], {}, 1])
def test_malformed_categories_return_validation_errors(category):
    spec = {"videos": {"v": {"url": "x", "note": "n", "category": category}}, "cases": []}
    assert validate(spec)
