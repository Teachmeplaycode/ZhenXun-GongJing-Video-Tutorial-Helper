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


@pytest.mark.parametrize("field", ["question", "rubric"])
@pytest.mark.parametrize("value", [None, "", "  ", 1, [], {}])
def test_question_and_rubric_require_nonblank_text(field, value):
    case = {"id": "c1", "video": "v", "question": "q", "rubric": "confirmed answer", "qtype": "summary"}
    case[field] = value
    spec = {"videos": {"v": {"url": "x", "note": "n", "category": "vlog"}}, "cases": [case]}
    assert any(field in error for error in validate(spec))


@pytest.mark.parametrize("key", ["tools_any", "tools_all", "tools_none"])
@pytest.mark.parametrize("value", [[[]], [{}], [1], [None]])
def test_tool_checks_reject_non_string_entries(key, value):
    case = {"id": "c1", "video": "v", "question": "q", "rubric": "answer", "qtype": "summary", "checks": {key: value}}
    spec = {"videos": {"v": {"url": "x", "note": "n", "category": "vlog"}}, "cases": [case]}
    assert any(key in error for error in validate(spec))


@pytest.mark.parametrize("value", ["forbidden", [[]], [{}], [1], [None], ["valid", 1]])
def test_contains_none_rejects_non_string_entries_on_load(tmp_path, value):
    import json

    case = {"id": "c1", "video": "v", "question": "q", "rubric": "answer", "qtype": "summary",
            "checks": {"contains_none": value}}
    spec = {"videos": {"v": {"url": "x", "note": "n", "category": "vlog"}}, "cases": [case]}
    path = tmp_path / "cases.json"
    path.write_text(json.dumps(spec))
    with pytest.raises(ValueError, match="contains_none 应为字符串数组"):
        load(path)


@pytest.mark.parametrize("forbidden", [[], ["李宗盛", "forbidden"]])
def test_contains_none_strings_can_be_loaded_and_evaluated(tmp_path, forbidden):
    import json
    from scripts.eval import check

    case = {"id": "c1", "video": "v", "question": "q", "rubric": "answer", "qtype": "summary",
            "checks": {"contains_none": forbidden}}
    spec = {"videos": {"v": {"url": "x", "note": "n", "category": "vlog"}}, "cases": [case]}
    path = tmp_path / "cases.json"
    path.write_text(json.dumps(spec))
    loaded = load(path)
    assert check(loaded["cases"][0], {"status": "done", "answer": "safe", "tools": []}) == []


@pytest.mark.parametrize("field", ["url", "note"])
@pytest.mark.parametrize("value", [None, "", " \t\n", True, 123, ["text"], {"value": "text"}])
def test_video_metadata_requires_nonblank_text(field, value):
    video = {"url": "https://example.com/video", "note": "human confirmed", "category": "vlog"}
    video[field] = value
    assert any(f"videos.v 的 {field} 应为非空字符串" in error
               for error in validate({"videos": {"v": video}, "cases": []}))


@pytest.mark.parametrize("checks,error", [
    ({"contains_any": [[]]}, "contains_any[0]"),
    ({"contains_any": [[""]]}, "contains_any[0]"),
    ({"contains_any": [[" \t\n"]]}, "contains_any[0]"),
    ({"contains_any": [["valid", ""]]}, "contains_any[0]"),
    ({"contains_any": [["valid"], []]}, "contains_any[1]"),
    ({"contains_none": [""]}, "contains_none"),
    ({"contains_none": [" \t\n"]}, "contains_none"),
    ({"contains_none": ["valid", ""]}, "contains_none"),
])
def test_empty_content_checks_are_rejected(checks, error):
    case = {"id": "c1", "video": "v", "question": "q", "rubric": "answer", "qtype": "summary",
            "checks": checks}
    spec = {"videos": {"v": {"url": "x", "note": "n", "category": "vlog"}}, "cases": [case]}
    assert any(error in message for message in validate(spec))


@pytest.mark.parametrize("checks", [{"contains_any": [], "contains_none": []},
                                   {"contains_any": [[" 正确 ", "correct"], ["答案"]],
                                    "contains_none": [" 错误 "]}])
def test_optional_empty_lists_and_nonblank_checks_can_be_evaluated(checks):
    from scripts.eval import check

    case = {"id": "c1", "video": "v", "question": "q", "rubric": "answer", "qtype": "summary",
            "checks": checks}
    spec = {"videos": {"v": {"url": "https://example.com/video", "note": "n", "category": "vlog"}},
            "cases": [case]}
    assert validate(spec) == []
    assert check(case, {"status": "done", "answer": "正确答案", "tools": []}) == []


@pytest.mark.parametrize("key", ["tools_any", "tools_all", "tools_none"])
@pytest.mark.parametrize("value", ["", " ", "\t\n"])
def test_tool_checks_reject_blank_names(key, value):
    from evals.schema import _validate_checks
    assert _validate_checks("case", {key: [value]})


@pytest.mark.parametrize("key", ["contains_non", "tools_an", "time_stamps", "custom"])
def test_unknown_check_keys_are_rejected(key):
    from evals.schema import _validate_checks
    errors = _validate_checks("case", {key: []})
    assert any(key in error and "不支持" in error for error in errors)


@pytest.mark.parametrize("key", ["", " ", "\t", 1, None])
def test_video_keys_are_nonblank_referenceable_strings(key):
    spec = {"videos": {key: {"url": "https://example.com/v", "note": "ok", "category": next(iter(CATEGORIES))}}, "cases": []}
    assert any("编号" in e for e in validate(spec))


@pytest.mark.parametrize("frames", ["9", [{}], [True], [1.5], [-1], None, {"index": 9}])
def test_optional_frame_scopes_reject_malformed_indices(frames):
    spec = load(CASES)
    spec["cases"][0]["frames"] = frames
    assert any("frames" in e for e in validate(spec))


@pytest.mark.parametrize("frames", [[], [0], [1, 2, 3]])
def test_optional_frame_scopes_allow_integer_indices(frames):
    spec = load(CASES)
    spec["cases"][0]["frames"] = frames
    assert validate(spec) == []


@pytest.mark.parametrize("flag", ["web", "papers"])
@pytest.mark.parametrize("value", [None, [], {}, 0, 1, "false"])
def test_execution_permissions_require_real_booleans(flag, value):
    spec = load(CASES)
    spec["cases"][0][flag] = value
    assert any(f"{flag} 应为布尔值" in error for error in validate(spec))


@pytest.mark.parametrize("field", ["webb", "paper", "frame", "frame_indices", "scope", "history", "custom"])
def test_unknown_case_fields_cannot_silently_change_permissions_or_scope(field):
    spec = load(CASES)
    spec["cases"][0][field] = False
    assert any(f"case 不支持字段 {field}" in error for error in validate(spec))


@pytest.mark.parametrize("first,alias", [
    ("https://example.com/watch?v=A", "https://example.com/watch?v=A"),
    ("https://example.com/watch?v=A", " HTTPS://EXAMPLE.COM:443/watch?v=A "),
    ("http://example.com/watch?v=A", "http://EXAMPLE.COM:80/watch?v=A"),
    ("https://example.com", "https://example.com/"),
    ("https://www.bilibili.com/video/BV1pEa66NEGA/?p=2", "https://www.bilibili.com/video/BV1pEa66NEGA?p=2"),
])
def test_video_url_aliases_cannot_inflate_multiple_categories(first, alias):
    spec = {"videos": {"first": {"url": first, "note": "confirmed", "category": "lecture"},
                       "alias": {"url": alias, "note": "same source", "category": "sports"}}, "cases": []}
    errors = validate(spec)
    assert any("videos.alias" in error and "videos.first" in error and "重复" in error for error in errors)


@pytest.mark.parametrize("first,second", [
    ("https://www.youtube.com/watch?v=A", "https://www.youtube.com/watch?v=B"),
    ("https://www.bilibili.com/video/BV1pEa66NEGA?p=1", "https://www.bilibili.com/video/BV1pEa66NEGA?p=2"),
    ("https://example.com/#/video/A", "https://example.com/#/video/B"),
    ("https://example.com/video/A", "https://example.com/video/a"),
    ("https://example.com/watch?v=A&signature=x", "https://example.com/watch?v=A&signature=y"),
    ("https://example.com:8443/watch?v=A", "https://example.com/watch?v=A"),
])
def test_distinct_video_identifiers_parts_hash_routes_and_ports_remain_valid(first, second):
    spec = {"videos": {"first": {"url": first, "note": "confirmed", "category": "lecture"},
                       "second": {"url": second, "note": "confirmed", "category": "sports"}}, "cases": []}
    assert validate(spec) == []
