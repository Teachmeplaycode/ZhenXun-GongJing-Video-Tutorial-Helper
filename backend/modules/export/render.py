"""Pack a Markdown note into a zip, and render a print-styled HTML page for PDF export.

The zip holds ``笔记.md`` plus an ``images/`` folder so pictures render in Typora / GitHub.
The HTML page uses the browser's own CJK fonts (no mojibake) and CSS ``page-break`` for paging;
the user opens it and prints to PDF, which avoids a heavy PDF dependency on the backend.
"""
from __future__ import annotations

import io
import html
import zipfile
from pathlib import Path

from .markdown import ImageRef, STAMP_RE, clock, collect_image_refs, collect_sources, image_relative_path, safe_http_url, select_messages, stamp_to_seconds, time_link


def build_zip(markdown_text: str, image_refs: list[ImageRef]) -> bytes:
    """A zip with 笔记.md and images/ — only files that exist on disk are included."""
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as zf:
        zf.writestr("笔记.md", markdown_text)
        for ref in image_refs:
            p = Path(ref.disk_path)
            if p.is_file():
                zf.write(p, f"images/{ref.zip_name}")
    return buf.getvalue()


def _esc(text: str) -> str:
    return html.escape(text or "")


def _event_image_paths(events: list[dict], job_id: str) -> list[tuple[str, str]]:
    """(api_path, label) for the replays / closer looks / motion images an answer used."""
    out: list[tuple[str, str]] = []
    seen: set[str] = set()
    started: dict[str, str] = {}
    for ev in events or []:
        if ev.get("type") == "tool_call.started":
            started[ev.get("call_id")] = ev.get("tool_name", "")
    for ev in events or []:
        if ev.get("type") != "tool_call.output":
            continue
        data = ev.get("data") or {}
        tool = started.get(ev.get("call_id"), "")
        paths = list(data.get("frames") or []) + list(data.get("images") or [])
        for p in paths:
            if image_relative_path(p, job_id) is None or p in seen:
                continue
            seen.add(p)
            out.append((p, _label_for(tool, data)))
    return out


def _label_for(tool: str, data: dict) -> str:
    if tool == "frames.replay":
        t = data.get("start")
        return f"慢放 {clock(t)}" if isinstance(t, (int, float)) else "慢放"
    if tool == "frames.view":
        times = data.get("secs") or data.get("times") or []
        return f"补看 {clock(times[0])}" if times and isinstance(times[0], (int, float)) else "补看"
    if tool == "frames.motion":
        return "运动测量图"
    return "画面"


def _img_tag(api_path: str, label: str, base_url: str) -> str:
    url = f"{base_url}{api_path}"
    return f'<figure class="shot"><img src="{_esc(url)}" alt="{_esc(label)}"><figcaption>{_esc(label)}</figcaption></figure>'


def _text_html(text: str, canonical_url: str, platform: str) -> str:
    """Escape all prose, then create real links only for recognized timestamps."""
    chunks, cursor = [], 0
    for match in STAMP_RE.finditer(text):
        chunks.append(_esc(text[cursor:match.start()]))
        label = _esc(match.group(0))
        href = time_link(canonical_url, platform, stamp_to_seconds(match.group(1)))
        chunks.append(f'<a href="{_esc(href)}">{label}</a>' if href else label)
        cursor = match.end()
    chunks.append(_esc(text[cursor:]))
    return "".join(chunks)


def _answer_html(message: dict, video: dict, index: int, job_id: str, base_url: str,
                 available_images: set[str]) -> str:
    canonical_url = video.get("canonical_url") or ""
    platform = video.get("platform") or ""
    events = message.get("events") or []
    text = message.get("content") or ""
    out = ['<section class="qa">']
    label = "问" if message.get("role") == "user" else "答"
    out.append(f"<h3>{index}. {label}</h3>")
    out.append(f'<div class="answer">{_text_html(text, canonical_url, platform)}</div>')

    frames = [i for i in message.get("frames") or []
              if type(i) is int and i >= 0 and f"/api/link-jobs/{job_id}/frames/{i}.jpg" in available_images]
    if frames:
        out.append('<div class="shots"><h4>附件关键帧</h4>')
        for i in frames:
            if type(i) is int and i >= 0:
                api = f"/api/link-jobs/{job_id}/frames/{i}.jpg"
                out.append(f'<figure class="shot"><img src="{_esc(base_url + api)}" alt="关键帧 {i}"></figure>')
        out.append("</div>")

    imgs = [(api, label) for api, label in _event_image_paths(events, job_id) if api in available_images]
    if imgs:
        out.append('<div class="shots"><h4>引用画面</h4>')
        for api, label in imgs:
            out.append(_img_tag(api, label, base_url))
        out.append("</div>")

    sources = collect_sources(events, text)
    if sources:
        out.append('<div class="sources"><h4>来源</h4><ol>')
        for s in sources:
            meta = f" · {_esc(s['meta'])}" if s.get("meta") else ""
            out.append(f'<li><a href="{_esc(s["url"])}">{_esc(s["title"] or s["url"])}</a>（{_esc(s["kind"])}{meta}）</li>')
        out.append("</ol></div>")
    out.append("</section>")
    return "\n".join(out)


def build_print_html(video: dict, task: str, messages: list[dict], slots: list[dict],
                     job_id: str, base_url: str, selected_ids: set[int] | None = None, *, data_dir=None) -> str:
    """A self-contained, print-styled HTML page for the browser's Print → PDF."""
    chosen = select_messages(messages, selected_ids)
    available_images = set()
    ok_frames = {f"/api/link-jobs/{job_id}/frames/{slot['index']}.jpg"
                 for slot in slots if type(slot.get("index")) is int and slot.get("status") == "ok"}
    if data_dir is not None:
        for ref in collect_image_refs(chosen, slots, data_dir, job_id):
            relative = image_relative_path(ref.api_path, job_id)
            if len(relative.parts) > 1 or ref.api_path in ok_frames:
                available_images.add(ref.api_path)
    title = video.get("title") or video.get("video_id") or "视频笔记"
    meta_bits = []
    if video.get("author"):
        meta_bits.append(f"<span>作者：{_esc(video['author'])}</span>")
    if video.get("platform"):
        meta_bits.append(f"<span>平台：{_esc(video['platform'])}</span>")
    if video.get("duration"):
        meta_bits.append(f"<span>时长：{clock(video['duration'])}</span>")
    meta_line = " · ".join(meta_bits)
    desc = _esc((video.get("description") or "").strip())
    link = video.get("canonical_url") or ""

    qa, manuals = [], []
    for m in chosen:
        (manuals if m.get("manual") == "replay" else qa).append(m)

    body: list[str] = [f"<h1>{_esc(title)}</h1>"]
    if meta_line:
        body.append(f'<p class="meta">{meta_line}</p>')
    if safe_http_url(link):
        body.append(f'<p class="link">链接：<a href="{_esc(link)}">{_esc(link)}</a></p>')
    if desc:
        body.append(f'<p class="desc">{desc}</p>')
    if task:
        body.append(f'<p class="task">任务：{_esc(task)}</p>')

    if qa:
        body.append("<h2>问答</h2>")
        index = 0
        for m in qa:
            if m.get("role") == "user":
                index += 1
            elif index == 0:
                index = 1
            body.append(_answer_html(m, video, index, job_id, base_url, available_images))

    if manuals:
        body.append("<h2>手动慢放</h2>")
        for m in manuals:
            events = m.get("events") or []
            data = next((e.get("data") or {} for e in events if e.get("type") == "tool_call.output"), {})
            start, end, fps = data.get("start"), data.get("end"), data.get("fps")
            head = f"手动慢放 [{clock(start)}–{clock(end)}]"
            if fps:
                head += f" · 每秒 {fps:g} 帧"
            body.append('<section class="qa manual">')
            body.append(f"<h3>{_esc(head)}</h3>")
            imgs = [(api, label) for api, label in _event_image_paths(events, job_id) if api in available_images]
            if imgs:
                body.append('<div class="shots">')
                for api, label in imgs:
                    body.append(_img_tag(api, label, base_url))
                body.append("</div>")
            body.append("</section>")

    if not qa and not manuals:
        body.append("<p>（没有选中要导出的问答）</p>")

    css = """
    * { box-sizing: border-box; }
    body { font-family: -apple-system, "PingFang SC", "Microsoft YaHei", "Noto Sans CJK SC", "Source Han Sans SC", sans-serif;
           max-width: 820px; margin: 0 auto; padding: 24px; color: #1a1a1a; line-height: 1.7; }
    h1 { font-size: 1.6em; margin: 0 0 .3em; }
    h2 { font-size: 1.25em; margin: 1.6em 0 .5em; border-bottom: 2px solid #ddd; padding-bottom: .2em; }
    h3 { font-size: 1.05em; margin: 1.2em 0 .4em; page-break-after: avoid; }
    h4 { font-size: .95em; margin: .8em 0 .3em; color: #555; }
    .meta, .link, .desc, .task { color: #555; font-size: .9em; margin: .2em 0; }
    .answer { white-space: pre-wrap; margin: .4em 0; }
    .shots { display: flex; flex-wrap: wrap; gap: 10px; margin: .5em 0; }
    .shots h4 { flex-basis: 100%; }
    figure.shot { margin: 0; page-break-inside: avoid; }
    figure.shot img { max-width: 230px; max-height: 180px; object-fit: contain; border: 1px solid #eee; }
    figcaption { font-size: .8em; color: #777; text-align: center; }
    .sources ol { padding-left: 1.4em; }
    .sources li { margin: .2em 0; }
    a { color: #1a6; text-decoration: none; word-break: break-all; }
    section.qa { page-break-inside: auto; orphans: 3; widows: 3; }
    h2 { page-break-after: avoid; }
    img { page-break-inside: avoid; }
    @page { size: A4; margin: 1.8cm; }
    @media print { body { max-width: none; padding: 0; } }
    """
    return (
        "<!DOCTYPE html>\n"
        '<html lang="zh-CN"><head><meta charset="utf-8">'
        f"<title>{_esc(title)} · 笔记</title>"
        f"<style>{css}</style></head><body>\n"
        + "\n".join(body)
        + "\n</body></html>"
    )
