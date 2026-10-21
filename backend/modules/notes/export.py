"""A note as Markdown with its pictures, zipped: from the editor's board when it was arranged, else as written.

Board blocks are read in reading order (top to bottom, then left to right), so moving a picture in the
editor moves it in the export too. Pictures are copied from the job folder into images/.
"""
from __future__ import annotations

import io
import re
import zipfile
from collections.abc import Callable
from pathlib import Path

from .task import clock

# Picture addresses the note uses → (folder under the job, file name)
SRC_RE = re.compile(r"/api/link-jobs/[\w-]+/(extra/\d{8}\.jpg|frames/\d+\.jpg|replay/[\d-]+/\d{2}\.jpg)$")


def _section_md(b: dict) -> list[str]:
    head = f"## {b.get('title') or '小节'}"
    if isinstance(b.get("start"), (int, float)) and isinstance(b.get("end"), (int, float)):
        head += f"（{clock(b['start'])}–{clock(b['end'])}）"
    out = [head, ""]
    out += [f"- {p}" for p in b.get("points") or []]
    if b.get("formulas"):
        out += ["", "**公式**", ""] + [f"$$\n{f}\n$$" for f in b["formulas"]]
    if b.get("examples"):
        out += ["", "**例题**", ""] + [f"{i + 1}. {e}" for i, e in enumerate(b["examples"])]
    return out + [""]


def _mindmap_md(node: dict, depth: int = 0) -> list[str]:
    if not isinstance(node, dict) or not node.get("label"):
        return []
    lines = [f"{'  ' * depth}- {node['label']}"]
    for child in node.get("children") or []:
        lines += _mindmap_md(child, depth + 1)
    return lines


def _figure_md(b: dict, name: str) -> list[str]:
    caption = b.get("caption") or "画面"
    when = f" · {clock(b['time'])}" if isinstance(b.get("time"), (int, float)) else ""
    return [f"![{caption}](images/{name})", f"*{caption}{when}*", ""]


def note_blocks(note: dict) -> list[dict]:
    """The note in its written order, as board-like blocks (no positions)."""
    blocks = [{"type": "title", "text": note.get("title"), "summary": note.get("summary")}]
    for s in note.get("sections") or []:
        blocks.append({"type": "section", **{k: s.get(k) for k in ("title", "start", "end", "points", "formulas", "examples")}})
        blocks += [{"type": "figure", **f} for f in s.get("figures") or []]
    if note.get("mindmap"):
        blocks.append({"type": "mindmap", "tree": note["mindmap"]})
    return blocks


def reading_order(blocks: list[dict]) -> list[dict]:
    """Top to bottom; blocks whose tops are within 40 px count as one row, read left to right."""
    rows: list[list[dict]] = []
    for b in sorted(blocks, key=lambda b: (float(b.get("y", 0)), float(b.get("x", 0)))):
        if rows and abs(float(b.get("y", 0)) - float(rows[-1][0].get("y", 0))) < 40:
            rows[-1].append(b)
        else:
            rows.append([b])
    return [b for row in rows for b in sorted(row, key=lambda b: float(b.get("x", 0)))]


def to_markdown(note: dict, board: dict | None, picture: Callable[[str], Path | None]) -> tuple[str, dict[str, Path], str]:
    """(markdown, {image name: file} referenced as images/<name>, title)."""
    blocks = reading_order(board["blocks"]) if board and board.get("blocks") else note_blocks(note)
    lines: list[str] = []
    files: dict[str, Path] = {}
    for b in blocks:
        kind = b.get("type")
        if kind == "title":
            lines += [f"# {b.get('text') or note.get('title') or '视频笔记'}", ""]
            if b.get("summary"):
                lines += [f"> {b['summary']}", ""]
        elif kind == "section":
            lines += _section_md(b)
        elif kind == "figure":
            src = str(b.get("src") or "")
            path = picture(src) if SRC_RE.search(src) else None
            if path is None:
                continue
            name = f"{len(files) + 1:02d}-{path.parent.name}-{path.name}" if path.parent.name != "frames" else f"{len(files) + 1:02d}-frame-{path.name}"
            files[name] = path
            lines += _figure_md(b, name)
        elif kind == "mindmap":
            lines += ["## 思维导图", ""] + _mindmap_md(b.get("tree") or {}) + [""]
        elif kind == "text" and str(b.get("text") or "").strip():
            lines += [str(b["text"]).strip(), ""]
    video = note.get("video") or {}
    if video.get("title"):
        lines += ["---", f"来源视频：{video['title']}", ""]
    return "\n".join(lines).rstrip() + "\n", files, note.get("title") or "视频笔记"


def to_zip(note: dict, board: dict | None, picture: Callable[[str], Path | None]) -> tuple[bytes, str]:
    """(zip bytes, title). `picture(src)` gives the file behind a picture address, or None."""
    markdown, files, title = to_markdown(note, board, picture)
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as z:
        z.writestr("笔记.md", markdown)
        for name, path in files.items():
            z.write(path, f"images/{name}")
    return buf.getvalue(), title


PREVIEW_STYLE = """
body { margin: 0; padding: 28px 32px 48px; background: #fff; color: #1a1a1a; font: 15px/1.8 -apple-system, "PingFang SC", "Microsoft YaHei", sans-serif; }
main { max-width: 760px; margin: 0 auto; }
h1 { font-size: 26px; line-height: 1.3; margin: 0 0 12px; } h2 { font-size: 19px; margin: 28px 0 8px; } h3 { font-size: 16px; }
blockquote { margin: 0 0 16px; padding: 8px 14px; border-left: 3px solid #c8f04a; background: #f7f6f2; color: #555; }
img { display: block; max-width: 100%; border-radius: 6px; margin: 8px 0 2px; }
img + em, p > em:only-child { color: #777; font-size: 13px; }
code { background: #f2f1ed; padding: 1px 4px; border-radius: 3px; font-size: 13px; }
hr { border: 0; border-top: 1px solid #e3e1db; margin: 28px 0 12px; }
li { margin: 2px 0; }
@media (max-width: 600px) { body { padding: 18px 16px 32px; } }
"""


def to_preview_html(note: dict, board: dict | None, picture: Callable[[str], Path | None]) -> str:
    """The note as the exported Markdown would read, as one self-contained page (pictures inlined)."""
    import base64
    import html as html_lib

    from markdown_it import MarkdownIt

    markdown, files, title = to_markdown(note, board, picture)
    for name, path in files.items():
        data = base64.b64encode(path.read_bytes()).decode()
        markdown = markdown.replace(f"(images/{name})", f"(data:image/jpeg;base64,{data})")
    body = MarkdownIt("commonmark", {"html": False}).enable("table").render(markdown)
    return (f"<!doctype html><html lang=\"zh-CN\"><head><meta charset=\"utf-8\"><meta name=\"viewport\" content=\"width=device-width, initial-scale=1\">"
            f"<title>{html_lib.escape(title)}</title><style>{PREVIEW_STYLE}</style></head><body><main>{body}</main></body></html>")


class ImageError(RuntimeError):
    pass


IMAGE_WIDTH = 720       # CSS px: a phone screen's reading width
IMAGE_SCALE = 1.5       # device pixels per CSS px
MAX_IMAGE_PX = 16000    # Chromium can't capture a taller page in one go: shrink the scale to fit


async def to_long_image(page: str) -> bytes:
    """The preview page as one long PNG, through the shared headless Chromium."""
    from modules.agent import browser

    if not browser.installed():
        raise ImageError("生成长图需要浏览器：在 backend 里运行 uv run playwright install --only-shell chromium")
    try:
        chromium = await browser.browser()
        context = await chromium.new_context(viewport={"width": IMAGE_WIDTH, "height": 900}, device_scale_factor=IMAGE_SCALE)
    except Exception as exc:  # noqa: BLE001 — most often the browser was never downloaded
        raise ImageError("浏览器启动失败，暂时不能生成长图") from exc
    try:
        tab = await context.new_page()
        await tab.set_content(page, wait_until="load")
        height = await tab.evaluate("document.documentElement.scrollHeight")
        if height * IMAGE_SCALE > MAX_IMAGE_PX:
            await context.close()
            context = await chromium.new_context(viewport={"width": IMAGE_WIDTH, "height": 900},
                                                 device_scale_factor=max(0.5, MAX_IMAGE_PX / height))
            tab = await context.new_page()
            await tab.set_content(page, wait_until="load")
        return await tab.screenshot(full_page=True, type="png")
    finally:
        await context.close()
