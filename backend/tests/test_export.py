import io
import zipfile
from pathlib import Path
import pytest

from modules.export import build_markdown, build_print_html, build_zip, collect_image_refs, select_messages
from modules.export.markdown import collect_sources, linkify_stamps

JOB = "s1"


def video(**kw):
    base = dict(
        platform="bilibili", video_id="BV1", canonical_url="https://www.bilibili.com/video/BV1",
        title="柚子与药物", duration=120, part=1, parts=[{"index": 1, "title": "P1", "duration": 120}],
        cover="", author="测试作者", description="一段关于柚子和药物的视频", playable_duration=None, notes=[],
    )
    base.update(kw)
    return base


def slots(n=4, duration=120):
    return [{"index": i, "time": round((i + 0.5) / n * duration, 3), "status": "ok", "reason": ""} for i in range(n)]


def replay_events():
    return [
        {"type": "tool_call.started", "call_id": "r1", "tool_name": "frames.replay", "t": 0},
        {"type": "tool_call.output", "call_id": "r1", "stdout": "复看", "exit_code": 0, "t": 0.4,
         "data": {"start": 60, "end": 61, "fps": 3, "times": [60, 60.33, 60.67, 61],
                  "frames": [f"/api/link-jobs/{JOB}/replay/0006000-0006100-030/{n}.jpg" for n in ("00", "01", "02", "03")]}},
        {"type": "tool_call.completed", "call_id": "r1", "result_count": 4, "t": 0.4},
    ]


def web_answer_events():
    results = [
        {"title": "Grapefruit and Drugs", "url": "https://www.fda.gov/grapefruit", "host": "www.fda.gov", "verdict": "reliable"},
        {"title": "震惊！相克", "url": "https://toutiao.example.com/a", "host": "toutiao.example.com", "verdict": "unreliable"},
    ]
    return [
        {"type": "tool_call.started", "call_id": "s1", "tool_name": "web.search", "t": 0.1},
        {"type": "tool_call.output", "call_id": "s1", "stdout": "2 条", "exit_code": 0, "t": 0.5,
         "data": {"query": "grapefruit", "results": results}},
        {"type": "tool_call.completed", "call_id": "s1", "result_count": 2, "t": 0.5},
        {"type": "assistant.message.delta", "delta": "会影响。在 [00:30] 提到 CYP3A4，见 https://www.fda.gov/grapefruit", "t": 1.0},
        {"type": "run.completed", "steps": 1, "elapsed_ms": 1000, "summary": "", "t": 1.1},
    ]


def make_messages():
    return [
        {"id": 1, "role": "user", "content": "柚子会影响药物吗？", "status": "done", "frames": [0, 1]},
        {"id": 2, "role": "assistant", "content": "会影响。在 [00:30] 提到 CYP3A4，见 https://www.fda.gov/grapefruit",
         "status": "done", "events": web_answer_events()},
    ]


def test_markdown_has_video_header_and_qa(tmp_path):
    md, refs = build_markdown(video(), "讲了什么", make_messages(), slots(), JOB, tmp_path / "jobs")
    assert "# 柚子与药物" in md
    assert "测试作者" in md and "bilibili" in md
    assert "https://www.bilibili.com/video/BV1" in md
    assert "## 问答" in md
    assert "柚子会影响药物吗？" in md
    assert "CYP3A4" in md


def test_markdown_keeps_time_stamps(tmp_path):
    md, _ = build_markdown(video(), "", make_messages(), slots(), JOB, tmp_path / "jobs")
    # the [00:30] stamp is kept (as a link on Bilibili, but the text remains)
    assert "00:30" in md


def test_bilibili_time_links(tmp_path):
    md, _ = build_markdown(video(), "", make_messages(), slots(), JOB, tmp_path / "jobs")
    assert "t=30" in md  # the stamp links to the video at 30 s
    assert "https://www.bilibili.com/video/BV1?t=30" in md


def test_non_bilibili_keeps_plain_stamp(tmp_path):
    msgs = make_messages()
    md, _ = build_markdown(video(platform="youtube", canonical_url="https://youtu.be/x"), "", msgs, slots(), JOB, tmp_path / "jobs")
    assert "[00:30]" in md  # no link on other platforms
    assert "t=30" not in md


def test_collect_image_refs_keyframes_and_replay(tmp_path):
    jobs = tmp_path / "jobs"
    (jobs / JOB).mkdir(parents=True)
    (jobs / JOB / "000.jpg").write_bytes(b"jpg")
    (jobs / JOB / "001.jpg").write_bytes(b"jpg")
    (jobs / JOB / "replay" / "0006000-0006100-030").mkdir(parents=True)
    (jobs / JOB / "replay" / "0006000-0006100-030" / "00.jpg").write_bytes(b"jpg")
    msgs = [
        {"id": 1, "role": "user", "content": "问", "status": "done", "frames": [0, 1]},
        {"id": 2, "role": "assistant", "content": "答", "status": "done", "events": replay_events()},
    ]
    refs = collect_image_refs(msgs, slots(), jobs, JOB)
    apis = [r.api_path for r in refs]
    assert f"/api/link-jobs/{JOB}/frames/0.jpg" in apis
    assert f"/api/link-jobs/{JOB}/frames/1.jpg" in apis
    assert f"/api/link-jobs/{JOB}/replay/0006000-0006100-030/00.jpg" in apis
    assert all(r.zip_name.startswith(("frame_", "replay_")) for r in refs)


def test_collect_image_refs_extra_and_motion(tmp_path):
    jobs = tmp_path / "jobs"
    (jobs / JOB / "extra").mkdir(parents=True)
    (jobs / JOB / "extra" / "00001250.jpg").write_bytes(b"jpg")
    (jobs / JOB / "motion" / "0006000-0006100" / "out").mkdir(parents=True)
    (jobs / JOB / "motion" / "0006000-0006100" / "out" / "heat.jpg").write_bytes(b"jpg")
    events = [
        {"type": "tool_call.started", "call_id": "v", "tool_name": "frames.view", "t": 0},
        {"type": "tool_call.output", "call_id": "v", "stdout": "", "exit_code": 0, "t": 0.3,
         "data": {"start": 10, "end": 20, "secs": [12.5], "frames": [f"/api/link-jobs/{JOB}/extra/00001250.jpg"]}},
        {"type": "tool_call.completed", "call_id": "v", "result_count": 1, "t": 0.3},
        {"type": "tool_call.started", "call_id": "m", "tool_name": "frames.motion", "t": 0.4},
        {"type": "tool_call.output", "call_id": "m", "stdout": "", "exit_code": 0, "t": 0.8,
         "data": {"start": 60, "end": 61, "images": [f"/api/link-jobs/{JOB}/motion/0006000-0006100/heat.jpg"]}},
        {"type": "tool_call.completed", "call_id": "m", "result_count": 1, "t": 0.8},
    ]
    refs = collect_image_refs([{"id": 1, "role": "assistant", "content": "", "events": events}], slots(), jobs, JOB)
    apis = [r.api_path for r in refs]
    assert f"/api/link-jobs/{JOB}/extra/00001250.jpg" in apis
    assert f"/api/link-jobs/{JOB}/motion/0006000-0006100/heat.jpg" in apis
    assert any(r.zip_name.startswith("extra_") for r in refs)
    assert any(r.zip_name.startswith("motion_") for r in refs)


def test_select_messages():
    msgs = [{"id": 1, "role": "user"}, {"id": 2, "role": "assistant"}, {"id": 3, "role": "user"}]
    assert select_messages(msgs, None) == msgs
    assert select_messages(msgs, set()) == []
    assert [m["id"] for m in select_messages(msgs, {1, 2})] == [1, 2]


def test_build_zip_includes_markdown_and_images(tmp_path):
    jobs = tmp_path / "jobs"
    (jobs / JOB).mkdir(parents=True)
    (jobs / JOB / "000.jpg").write_bytes(b"jpeg-bytes")
    msgs = [
        {"id": 1, "role": "user", "content": "问", "status": "done", "frames": [0]},
        {"id": 2, "role": "assistant", "content": "答", "status": "done", "events": []},
    ]
    md, refs = build_markdown(video(), "", msgs, slots(), JOB, jobs)
    data = build_zip(md, refs)
    with zipfile.ZipFile(io.BytesIO(data)) as zf:
        names = zf.namelist()
        assert "笔记.md" in names
        assert any(n.startswith("images/frame_") and n.endswith(".jpg") for n in names)
        assert b"jpeg-byte" in zf.read(next(n for n in names if n.startswith("images/frame_")))
        assert "柚子与药物" in zf.read("笔记.md").decode("utf-8")


def test_build_zip_skips_missing_images(tmp_path):
    jobs = tmp_path / "jobs"
    (jobs / JOB).mkdir(parents=True)  # no frame files written
    msgs = [{"id": 1, "role": "user", "content": "问", "status": "done", "frames": [0]}]
    md, refs = build_markdown(video(), "", msgs, slots(), JOB, jobs)
    with zipfile.ZipFile(io.BytesIO(build_zip(md, refs))) as zf:
        assert zf.namelist() == ["笔记.md"]  # the md only; the missing image is left out


def test_build_print_html_has_cjk_and_images(tmp_path):
    jobs = tmp_path / "jobs"
    msgs = [
        {"id": 1, "role": "user", "content": "柚子会影响药物吗？", "status": "done", "frames": [0]},
        {"id": 2, "role": "assistant", "content": "在 [00:30] 提到 CYP3A4", "status": "done", "events": replay_events()},
    ]
    page = build_print_html(video(), "讲了什么", msgs, slots(), JOB, "http://localhost:8000")
    assert "<!DOCTYPE html>" in page and 'lang="zh-CN"' in page
    assert "柚子与药物" in page and "柚子会影响药物吗？" in page
    assert "CYP3A4" in page  # CJK + ascii preserved, no mojibake
    assert "page-break" in page  # print paging CSS
    assert "http://localhost:8000/api/link-jobs/s1/replay/0006000-0006100-030/00.jpg" in page
    assert "http://localhost:8000/api/link-jobs/s1/frames/0.jpg" in page


def test_build_print_html_empty_selection(tmp_path):
    msgs = make_messages()
    page = build_print_html(video(), "", msgs, slots(), JOB, "http://x", selected_ids={999})
    assert "没有选中" in page


def test_collect_sources_web_and_papers():
    events = [
        {"type": "tool_call.output", "call_id": "s", "data": {"results": [
            {"title": "FDA", "url": "https://fda.gov", "verdict": "reliable"},
            {"title": "农场", "url": "https://farm.cn", "verdict": "irrelevant"}]}},
        {"type": "tool_call.output", "call_id": "p", "data": {"papers": [
            {"title": "论文A", "url": "https://arxiv.org/1", "year": 2024, "venue": "Nature"}]}},
    ]
    sources = collect_sources(events, "参见 https://fda.gov 和 https://arxiv.org/1")
    urls = {s["url"] for s in sources}
    assert "https://fda.gov" in urls and "https://arxiv.org/1" in urls
    assert "https://farm.cn" not in urls  # irrelevant dropped
    paper = next(s for s in sources if s["url"] == "https://arxiv.org/1")
    assert paper["kind"] == "论文" and "2024" in paper["meta"]


def test_manual_replay_in_markdown(tmp_path):
    jobs = tmp_path / "jobs"
    (jobs / JOB / "replay" / "0006000-0006100-030").mkdir(parents=True)
    (jobs / JOB / "replay" / "0006000-0006100-030" / "00.jpg").write_bytes(b"jpg")
    msgs = [{"id": 5, "role": "assistant", "content": "", "status": "done", "manual": "replay", "events": replay_events()}]
    md, refs = build_markdown(video(), "", msgs, slots(), JOB, jobs)
    assert "## 手动慢放" in md
    assert "01:00–01:01" in md
    assert any("replay_" in r.zip_name for r in refs)


def test_linkify_stamps_preserves_non_stamps():
    out = linkify_stamps("见 [00:30] 和 [01:55]", "https://www.bilibili.com/video/BV1", "bilibili")
    assert "t=30" in out and "t=115" in out
    plain = linkify_stamps("没有时间点", "https://www.bilibili.com/video/BV1", "bilibili")
    assert plain == "没有时间点"


def test_question_and_answer_each_appear_once_with_correct_roles(tmp_path):
    messages = [{"id": 1, "role": "user", "content": "unique question"},
                {"id": 2, "role": "assistant", "content": "unique answer"}]
    md, _ = build_markdown(video(), "", messages, [], JOB, tmp_path)
    page = build_print_html(video(), "", messages, [], JOB, "http://localhost")
    for rendered in (md, page):
        assert rendered.count("unique question") == 1
        assert rendered.count("unique answer") == 1
    assert "### 1. 问" in md and "### 1. 答" in md
    assert "<h3>1. 问</h3>" in page and "<h3>1. 答</h3>" in page


@pytest.mark.parametrize("path", [
    "/api/link-jobs/s1/replay/../outside.jpg", "/api/link-jobs/s1/replay/../00.jpg",
    "/api/link-jobs/s1/replay/0006000-0006100-030/../../secret.jpg",
    "/api/link-jobs/s1/replay/%2e%2e/00.jpg", "/api/link-jobs/s1/frames/-1.jpg",
    "/api/link-jobs/s1/extra/not-a-frame.jpg", "/api/link-jobs/s1/motion/0006000-0006100/other.jpg",
    "/api/link-jobs/other/frames/0.jpg", "x/api/link-jobs/s1/frames/0.jpg",
])
def test_export_image_paths_follow_real_route_grammar(tmp_path, path):
    from modules.export.markdown import api_to_disk
    assert api_to_disk(path, tmp_path, JOB) is None


def test_export_rejects_symlink_escapes_for_keyframes_and_replay(tmp_path):
    from modules.export.markdown import api_to_disk
    jobs = tmp_path / "jobs"
    root = jobs / JOB
    root.mkdir(parents=True)
    secret = tmp_path / "secret.jpg"
    secret.write_bytes(b"private")
    (root / "000.jpg").symlink_to(secret)
    assert api_to_disk(f"/api/link-jobs/{JOB}/frames/0.jpg", jobs, JOB) is None
    md, refs = build_markdown(video(), "", make_messages(), [], JOB, jobs)
    assert b"private" not in build_zip(md, refs)
    outside = tmp_path / "outside"
    outside.mkdir()
    (root / "replay").symlink_to(outside, target_is_directory=True)
    assert api_to_disk(f"/api/link-jobs/{JOB}/replay/0006000-0006100-030/00.jpg", jobs, JOB) is None


@pytest.mark.parametrize("url", ["javascript:alert(1)", "data:text/html,<script>x</script>", "file:///etc/passwd", "//example.org/x", "https://example.org/\nattack"])
def test_unsafe_source_and_video_links_are_not_exported_as_links(tmp_path, url):
    messages = [{"role": "assistant", "content": "see [00:30]", "events": [
        {"type": "tool_call.output", "data": {"url": url, "title": "bad", "results": [{"url": url}], "papers": [{"url": url}]}}
    ]}]
    assert collect_sources(messages[0]["events"]) == []
    page = build_print_html(video(canonical_url=url), "", messages, [], JOB, "http://localhost")
    assert "href=" not in page
    md, _ = build_markdown(video(canonical_url=url), "", messages, [], JOB, tmp_path)
    assert "t=30" not in md


def test_printed_timestamp_is_real_html_link_and_prose_is_escaped():
    page = build_print_html(video(canonical_url="https://www.bilibili.com/video/BV1?foo=1#part"), "", [
        {"role": "assistant", "content": '<script>bad()</script> [00:30]'}], [], JOB, "http://localhost")
    assert '<a href="https://www.bilibili.com/video/BV1?foo=1&amp;t=30#part">[00:30]</a>' in page
    assert "&lt;script&gt;" in page and "<script>" not in page


@pytest.mark.parametrize('protected', [
    '[00:30](https://example.com)', '`[00:30]`', '``[00:30]``',
    '```text\n[00:30]\n```', '~~~\n[00:30]\n~~~',
    '![00:30](https://example.com/p.png)', '[00:30][reference]',
    r'\[00:30]', '[00:30]\n\n[00:30]: https://example.com',
])
def test_timestamp_linkification_preserves_markdown_constructs(protected):
    output = linkify_stamps(protected + '\n普通时间 [00:45]', video()['canonical_url'], 'bilibili')
    assert output.startswith(protected)
    assert 't=30' not in output
    assert 't=45' in output


def test_export_sources_follow_only_answer_citations(tmp_path):
    events = web_answer_events()
    assert collect_sources(events, '没有引用来源') == []
    sources = collect_sources(events, '来源 https://www.fda.gov/grapefruit')
    assert [source['url'] for source in sources] == ['https://www.fda.gov/grapefruit']
    message = {'id': 1, 'role': 'assistant', 'content': '没有引用来源', 'events': events}
    markdown, _ = build_markdown(video(), '', [message], slots(), JOB, tmp_path)
    printed = build_print_html(video(), '', [message], slots(), JOB, 'http://localhost:5194')
    assert '**来源：**' not in markdown
    assert '<h4>来源</h4>' not in printed


def test_missing_attached_frames_never_produce_broken_zip_references(tmp_path):
    jobs = tmp_path / 'jobs'
    (jobs / JOB).mkdir(parents=True)
    (jobs / JOB / '001.jpg').write_bytes(b'present image')
    messages = [{'id': 1, 'role': 'user', 'content': '看这两帧', 'frames': [0, 1]}]
    markdown, refs = build_markdown(video(), '', messages, slots(), JOB, jobs)
    assert 'images/frame_000.jpg' not in markdown
    assert 'images/frame_001.jpg' in markdown
    with zipfile.ZipFile(io.BytesIO(build_zip(markdown, refs))) as bundle:
        assert 'images/frame_000.jpg' not in bundle.namelist()
        assert 'images/frame_001.jpg' in bundle.namelist()
    assert len(collect_image_refs(messages, slots(), jobs, JOB)) == 1
