"""Turn a saved session into a Markdown note and the list of images it references.

The note keeps the answer's ``[mm:ss]`` time points; on Bilibili they become links with a ``?t=``
jump parameter. Images (keyframes, slow-motion replays, closer-look frames, motion heat/trail)
are collected as API paths, mapped to their files on disk, and bundled into the export zip so
the Markdown renders in Typora / GitHub with pictures intact.
"""
from __future__ import annotations

import re
import urllib.parse
from dataclasses import dataclass
from pathlib import Path

from markdown_it import MarkdownIt

# A time stamp in an answer, e.g. [00:30] or 01:55 — kept as [mm:ss] in the note.
STAMP_RE = re.compile(r"(?<![\d:])\[(\d+:\d{2}(?::\d{2})?)\](?![\d:])")
URL_RE = re.compile(r"https?://[^\s<>（）[\]，。；、\"“”]+")


def clock(seconds: float) -> str:
    t = max(0, int(round(seconds)))
    return f"{t // 60:02d}:{t % 60:02d}"


def stamp_to_seconds(stamp: str) -> float:
    parts = stamp.split(":")
    n = 0.0
    for p in parts:
        n = n * 60 + float(p)
    return n


def time_link(canonical_url: str, platform: str, seconds: float) -> str | None:
    """A jump link for a time point, where the platform supports one (Bilibili ``?t=``)."""
    if not safe_http_url(canonical_url) or platform != "bilibili":
        return None
    parsed = urllib.parse.urlsplit(canonical_url)
    query = urllib.parse.parse_qsl(parsed.query, keep_blank_values=True)
    query = [(key, value) for key, value in query if key != "t"] + [("t", str(int(round(seconds))))]
    return urllib.parse.urlunsplit(parsed._replace(query=urllib.parse.urlencode(query)))


def safe_http_url(value) -> bool:
    if not isinstance(value, str) or any(c.isspace() or c in "\\\x00" for c in value):
        return False
    try:
        parsed = urllib.parse.urlsplit(value)
        return parsed.scheme.lower() in ("http", "https") and bool(parsed.hostname)
    except ValueError:
        return False


def markdown_link(label: str, url: str) -> str:
    label = re.sub(r"([\\\[\]<>])", r"\\\1", label)
    url = urllib.parse.quote(url, safe=":/?#@!$&'*+,;=%-._~")
    return f"[{label}]({url})"


MARKDOWN_PROTECTED = re.compile(
    r"(?P<tick>`+).*?(?P=tick)"
    r"|!?\[[^\n]*?\]\((?:\\.|[^()\n]|\([^()\n]*\))*\)"
    r"|!?\[[^\n]*?\]\[[^\n]*?\]"
    r"|^ {0,3}\[[^]\n]+\]:[^\n]*$", re.MULTILINE | re.DOTALL)


def _block_code_ranges(text: str) -> list[tuple[int, int]]:
    """Track quote/list indentation so literal code survives timestamp linkification."""
    def consume(content, expected):
        kept = []
        for kind, width in expected:
            if kind == "quote":
                prefix = re.match(r" {0,3}>[ \t]?", content)
                if not prefix:
                    break
                content = content[prefix.end():]
            else:
                expanded = content.expandtabs(4)
                if expanded.startswith(" " * width):
                    content = expanded[width:]
                elif content.strip():
                    break
            kept.append((kind, width))
        return content, kept

    ranges, offset, fence, active = [], 0, None, []
    for line in text.splitlines(keepends=True):
        if fence:
            # Code cannot introduce new containers: only consume those that opened it.
            content, kept = consume(line, fence[2])
            if len(kept) == len(fence[2]):
                ranges.append((offset, offset + len(line)))
                active = kept
                if re.fullmatch(r" {0,3}" + re.escape(fence[0]) + "{" + str(fence[1]) + r",}[ \t\r\n]*", content):
                    fence = None
                offset += len(line)
                continue
            fence = None
        content, containers = consume(line, active)
        while True:
            quote = re.match(r" {0,3}>[ \t]?", content)
            if quote:
                containers.append(("quote", 0))
                content = content[quote.end():]
                continue
            expanded = content.expandtabs(4)
            item = re.match(r" {0,3}(?:[-+*]|\d{1,9}[.)])( +)", expanded)
            if not item:
                break
            # CommonMark list padding is 1–4 columns; 5+ means one column
            # of padding followed by indented code. Save the whole content width.
            padding = len(item[1]) if len(item[1]) <= 4 else 1
            width = item.start(1) + padding
            containers.append(("list", width))
            content = expanded[width:]
        active = containers
        if content.expandtabs(4).startswith("    "):
            ranges.append((offset, offset + len(line)))
        else:
            opening = re.match(r" {0,3}(`{3,}|~{3,})([^\r\n]*)", content)
            if opening and not (opening[1][0] == "`" and "`" in opening[2]):
                fence = (opening[1][0], len(opening[1]), containers)
                ranges.append((offset, offset + len(line)))
        offset += len(line)
    return ranges


def linkify_stamps(text: str, canonical_url: str, platform: str) -> str:
    """Keep ``[mm:ss]`` visible; on Bilibili make it a link to that moment."""
    if not safe_http_url(canonical_url) or platform != "bilibili":
        return text

    def repl(m: re.Match) -> str:
        url = time_link(canonical_url, platform, stamp_to_seconds(m.group(1)))
        return markdown_link(f"[{m.group(1)}]", url)

    protected = [(m.start(), m.end()) for m in MARKDOWN_PROTECTED.finditer(text)] + _block_code_ranges(text)
    reference_labels = set(re.findall(r"^ {0,3}\[([^]\n]+)\]:", text, re.MULTILINE))

    def unprotected(match):
        if match.start() and text[match.start() - 1] == "\\":
            return match.group(0)
        if match.group(1) in reference_labels or any(a <= match.start() < b for a, b in protected):
            return match.group(0)
        return repl(match)

    return STAMP_RE.sub(unprotected, text)


@dataclass
class ImageRef:
    api_path: str        # /api/link-jobs/{id}/frames/5.jpg  (as it appears in the session)
    disk_path: str       # absolute path to the file on disk, or "" if missing
    zip_name: str        # images/frame_005.jpg — the name inside the export zip
    label: str           # 关键帧 00:07 / 慢放 01:00.00 / 补看 00:12 / 运动热力图


def _safe_name(*parts: str) -> str:
    return "_".join(re.sub(r"[^0-9A-Za-z._-]", "", p) for p in parts if p)


def image_relative_path(api_path: str, job_id: str) -> Path | None:
    """Match exactly the image route keys and filenames the backend serves."""
    if not isinstance(api_path, str) or not api_path.startswith("/") or not re.fullmatch(r"[A-Za-z0-9_-]+", job_id):
        return None
    parts = api_path.split("/")[1:]
    if len(parts) < 5 or parts[0] != "api" or parts[1] != "link-jobs" or parts[2] != job_id:
        return None
    kind = parts[3]
    if kind == "frames" and len(parts) == 5 and re.fullmatch(r"[0-9]+\.jpg", parts[4]):
        try:
            index = int(parts[4][:-4])
        except ValueError:
            return None
        return Path(f"{index:03d}.jpg")
    if kind == "replay" and len(parts) == 6 and re.fullmatch(r"[0-9]{7}-[0-9]{7}-[0-9]{3}", parts[4]) and re.fullmatch(r"[0-9]{2}\.jpg", parts[5]):
        return Path("replay", parts[4], parts[5])
    if kind == "extra" and len(parts) == 5 and re.fullmatch(r"[0-9]{8}\.jpg", parts[4]):
        return Path("extra", parts[4])
    if kind == "motion" and len(parts) == 6 and re.fullmatch(r"[0-9]{7}-[0-9]{7}", parts[4]) and parts[5] in ("heat.jpg", "trail.jpg"):
        return Path("motion", parts[4], "out", parts[5])
    return None


def api_to_disk(api_path: str, data_dir, job_id: str):
    """Map a valid image route to a file contained in this job, including symlink resolution."""
    relative = image_relative_path(api_path, job_id)
    if relative is None:
        return None
    try:
        base = Path(data_dir).resolve()
        root = base / job_id
        if root.resolve() != root:
            return None
        path = (root / relative).resolve()
        return path if path.is_relative_to(root) else None
    except (OSError, RuntimeError, ValueError):
        return None


def _zip_name_for(api_path: str) -> str:
    parts = api_path.strip("/").split("/")
    kind = parts[3] if len(parts) > 3 else "img"
    if kind == "frames":
        try:
            index = int(parts[4][:-4])
        except (ValueError, IndexError):
            return _safe_name("frame", api_path) + ".jpg"
        return f"frame_{index:03d}.jpg"
    if kind == "replay":
        return f"replay_{_safe_name(parts[4], parts[5])}"
    if kind == "extra":
        return f"extra_{parts[4]}"
    if kind == "motion":
        return f"motion_{_safe_name(parts[4], parts[5])}"
    return _safe_name(api_path) + ".jpg"


def keyframe_ref(index: int, time: float, data_dir, job_id: str) -> ImageRef:
    api = f"/api/link-jobs/{job_id}/frames/{index}.jpg"
    disk = api_to_disk(api, data_dir, job_id)
    return ImageRef(api, str(disk) if disk and disk.is_file() else "", _zip_name_for(api), f"关键帧 {clock(time)}")


def _image_refs_from_events(events: list[dict], data_dir, job_id: str) -> list[ImageRef]:
    """Slow-motion replays, closer-look frames and motion images an answer used, in order."""
    out: list[ImageRef] = []
    seen: set[str] = set()
    for ev in events or []:
        if ev.get("type") != "tool_call.output":
            continue
        data = ev.get("data") or {}
        tool = _tool_name_for(events, ev.get("call_id"))
        paths = list(data.get("frames") or []) + list(data.get("images") or [])
        for p in paths:
            if not isinstance(p, str) or not p.startswith("/api/") or p in seen:
                continue
            disk = api_to_disk(p, data_dir, job_id)
            if disk is None or not disk.is_file():
                continue
            seen.add(p)
            out.append(ImageRef(p, str(disk), _zip_name_for(p), _label_for(tool, data)))
    return out


def _tool_name_for(events: list[dict], call_id: str) -> str:
    for ev in events:
        if ev.get("type") == "tool_call.started" and ev.get("call_id") == call_id:
            return ev.get("tool_name", "")
    return ""


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


def _inline_delimiters_before(before: str) -> list[str]:
    """Open wrappers inside one parser-identified Markdown inline block."""
    line = before
    opened, code = [], None
    for token in re.finditer(r"(?<!\\)(`+|\*{1,3}|_{1,3}|~~)", line):
        marker = token[0]
        left = line[token.start() - 1:token.start()] if token.start() else ""
        right = line[token.end():token.end() + 1]
        if marker.startswith("`"):
            code = None if code == marker else marker if code is None else code
        elif code is None:
            if marker in opened and left and not left.isspace():
                opened.remove(marker)
            elif (not right or not right.isspace()) and not (marker.startswith("_") and left.isalnum()):
                opened.append(marker)
    return [code] if code else opened


def _cited_urls(text: str, known: dict[str, dict]):
    # Use CommonMark block maps: inline wrappers may cross soft line breaks, but
    # cannot cross headings, list items, quotes, HTML/code blocks or paragraphs.
    offsets = [0] + [newline.end() for newline in re.finditer(r"\r\n?|\n", text)]
    if offsets[-1] < len(text):
        offsets.append(len(text))
    inline_blocks = [(offsets[token.map[0]], offsets[token.map[1]])
                     for token in MarkdownIt("commonmark").parse(text)
                     if token.type == "inline" and token.map]
    for match in URL_RE.finditer(text):
        raw = match.group(0)
        before = text[:match.start()]
        if before.endswith("<"):
            # Explicit autolink boundaries preserve even unbalanced URI sub-delimiters.
            yield raw
            continue
        if re.search(r"\]\([ \t]*$", before):
            depth, end = 1, 0
            for end, char in enumerate(raw):
                if char == "(":
                    depth += 1
                elif char == ")":
                    depth -= 1
                    if depth == 0:
                        break
            else:
                end = len(raw)
            yield raw[:end]
            continue
        block_start = next((start for start, end in inline_blocks if start <= match.start() < end), None)
        delimiters = _inline_delimiters_before(text[block_start:match.start()]) if block_start is not None else []
        if delimiters:
            # Tool metadata disambiguates literal URI punctuation from wrapper closers.
            exact = next((url for url in sorted(known, key=len, reverse=True)
                          if raw.startswith(url) and any(raw[len(url):].startswith(d) for d in delimiters)), None)
            if exact:
                yield exact
                continue
            ends = []
            for delimiter in delimiters:
                candidates = []
                for closing in re.finditer(re.escape(delimiter), raw):
                    end = closing.start()
                    left, right = raw[end - 1:end], raw[closing.end():closing.end() + 1]
                    if delimiter.startswith("_") and left.isalnum() and right.isalnum():
                        continue
                    if delimiter.startswith("`") and (left == "`" or right == "`"):
                        continue
                    candidates.append(end)
                if candidates:
                    ends.append(candidates[-1] if delimiter.startswith("_") else candidates[0])
            if ends:
                yield raw[:min(ends)]
                continue
        # Prefer an exact cited tool URL when the remaining text is only punctuation.
        exact = next((url for url in sorted(known, key=len, reverse=True)
                      if raw.startswith(url) and not raw[len(url):].strip(".,;:!)")), None)
        if exact:
            yield exact
            continue
        url = raw.rstrip(".,;:")
        while url.endswith(")") and url.count(")") > url.count("("):
            url = url[:-1].rstrip(".,;:")
        yield url


def collect_sources(events: list[dict], text: str = "") -> list[dict]:
    """Source links an answer cites: web results, fetched pages and papers, matched to its text."""
    known: dict[str, dict] = {}
    for ev in events or []:
        if ev.get("type") != "tool_call.output":
            continue
        data = ev.get("data") or {}
        for r in data.get("results") or []:
            if r.get("verdict") == "irrelevant" or not safe_http_url(r.get("url")):
                continue
            known[r["url"]] = {"title": r.get("title") or "", "url": r["url"], "kind": "网页"}
        if safe_http_url(data.get("url")) and not data.get("blocked"):
            known[data["url"]] = {"title": data.get("title") or "", "url": data["url"], "kind": "网页"}
        for p in data.get("papers") or []:
            if safe_http_url(p.get("url")):
                meta = " · ".join(str(x) for x in (p.get("year"), p.get("venue")) if x)
                known[p["url"]] = {"title": p.get("title") or "", "url": p["url"], "kind": "论文", "meta": meta}
    cited, seen = [], set()
    for url in _cited_urls(text, known):
        if url in seen or not safe_http_url(url):
            continue
        seen.add(url)
        source = known.get(url)
        if source is None:
            source = next((item for item in known.values() if url.startswith(item['url']) or item['url'].startswith(url)), None)
        cited.append({**source, 'url': url} if source else {'url': url, 'title': urllib.parse.urlsplit(url).hostname, 'kind': '链接'})
    return cited


def select_messages(messages: list[dict], selected_ids: set[int] | None) -> list[dict]:
    """None means all; an explicit empty set means no messages. Order is preserved."""
    if selected_ids is None:
        return list(messages)
    return [m for m in messages if m.get("id") in selected_ids]


def _video_header(video: dict, task: str) -> str:
    lines = [f"# {video.get('title') or video.get('video_id') or '视频笔记'}", ""]
    meta = []
    if video.get("author"):
        meta.append(f"**作者**：{video['author']}")
    if video.get("platform"):
        meta.append(f"**平台**：{video['platform']}")
    if video.get("duration"):
        meta.append(f"**时长**：{clock(video['duration'])}")
    if meta:
        lines.append(" · ".join(meta))
        lines.append("")
    if safe_http_url(video.get("canonical_url")):
        lines.append(f"**链接**：{video['canonical_url']}")
        lines.append("")
    desc = (video.get("description") or "").strip()
    if desc:
        lines.append(desc)
        lines.append("")
    if task:
        lines.append(f"> 任务：{task}")
        lines.append("")
    lines.append("---")
    lines.append("")
    return "\n".join(lines)


def _answer_block(message: dict, video: dict, index: int, slots: list[dict], data_dir, job_id: str) -> tuple[str, list[ImageRef]]:
    """One Q&A turn as Markdown, plus the images it references."""
    canonical_url = video.get("canonical_url") or ""
    platform = video.get("platform") or ""
    events = message.get("events") or []
    text = message.get("content") or ""
    label = "问" if message.get("role") == "user" else "答"
    out: list[str] = [f"### {index}. {label}", "", linkify_stamps(text, canonical_url, platform), ""]

    # Keyframes the user attached to the question are on the user message; the answer follows.
    frames = message.get("frames") or []
    keyframes: list[ImageRef] = []
    if frames:
        out.append("**附件关键帧：**")
        out.append("")
        for i in frames:
            if type(i) is int and i >= 0:
                slot = next((s for s in (slots or []) if s.get("index") == i), None)
                t = slot.get("time", 0.0) if slot else 0.0
                ref = keyframe_ref(i, t, data_dir, job_id)
                if not ref.disk_path:
                    continue
                keyframes.append(ref)
                out.append(f"![{ref.label}](images/{ref.zip_name})")
        out.append("")

    event_images = _image_refs_from_events(events, data_dir, job_id)
    imgs = keyframes + event_images
    if event_images:
        out.append("**引用画面：**")
        out.append("")
        for ref in event_images:
            out.append(f"![{ref.label}](images/{ref.zip_name})")
        out.append("")

    sources = collect_sources(events, text)
    if sources:
        out.append("**来源：**")
        out.append("")
        for i, s in enumerate(sources, 1):
            meta = f" · {s['meta']}" if s.get("meta") else ""
            out.append(f"{i}. {markdown_link(s['title'] or s['url'], s['url'])}（{s['kind']}{meta}）")
        out.append("")
    return "\n".join(out), imgs


def _manual_replay_block(message: dict, data_dir, job_id: str) -> tuple[str, list[ImageRef]]:
    events = message.get("events") or []
    data = {}
    for ev in events:
        if ev.get("type") == "tool_call.output" and isinstance(ev.get("data"), dict):
            data = ev["data"]
            break
    start, end = data.get("start"), data.get("end")
    fps = data.get("fps")
    head = f"- **手动慢放 [{clock(start)}–{clock(end)}]**"
    if fps:
        head += f" · 每秒 {fps:g} 帧"
    imgs = _image_refs_from_events(events, data_dir, job_id)
    lines = [head]
    for ref in imgs:
        lines.append(f"  ![{ref.label}](images/{ref.zip_name})")
    return "\n".join(lines), imgs


def collect_image_refs(messages: list[dict], slots: list[dict], data_dir, job_id: str) -> list[ImageRef]:
    """Every image the selected messages reference, deduplicated, in order."""
    out: list[ImageRef] = []
    seen: set[str] = set()

    def add(ref: ImageRef) -> None:
        if ref.disk_path and ref.api_path not in seen:
            seen.add(ref.api_path)
            out.append(ref)

    for m in messages:
        if m.get("role") == "user":
            for i in m.get("frames") or []:
                if type(i) is int and i >= 0:
                    slot = next((s for s in slots if s.get("index") == i), None)
                    t = slot.get("time", 0.0) if slot else 0.0
                    add(keyframe_ref(i, t, data_dir, job_id))
        for ref in _image_refs_from_events(m.get("events") or [], data_dir, job_id):
            add(ref)
    return out


def build_markdown(video: dict, task: str, messages: list[dict], slots: list[dict],
                   job_id: str, data_dir, selected_ids: set[int] | None = None) -> tuple[str, list[ImageRef]]:
    """Render the session as Markdown and return (text, image_refs).

    ``messages`` are the store's rows (id, role, content, status, events/frames/manual).
    ``selected_ids`` limits the export to those message ids (None = all, empty = none).
    """
    chosen = select_messages(messages, selected_ids)
    parts = [_video_header(video, task)]
    refs: list[ImageRef] = []
    seen: set[str] = set()

    def take(imgs: list[ImageRef]) -> None:
        for r in imgs:
            if r.api_path not in seen:
                seen.add(r.api_path)
                refs.append(r)

    qa, manuals = [], []
    for m in chosen:
        if m.get("manual") == "replay":
            manuals.append(m)
        else:
            qa.append(m)

    if qa:
        parts.append("## 问答")
        parts.append("")
        index = 0
        for m in qa:
            if m.get("role") == "user":
                index += 1
                block, imgs = _answer_block(m, video, index, slots, data_dir, job_id)
                parts.append(block)
                take(imgs)
            elif m.get("role") == "assistant":
                # An answer without a preceding question in the selection: emit it on its own.
                if index == 0:
                    index += 1
                block, imgs = _answer_block(m, video, index, slots, data_dir, job_id)
                parts.append(block)
                take(imgs)

    if manuals:
        parts.append("## 手动慢放")
        parts.append("")
        for m in manuals:
            block, imgs = _manual_replay_block(m, data_dir, job_id)
            parts.append(block)
            take(imgs)

    if not qa and not manuals:
        parts.append("_（没有选中要导出的问答）_")
        parts.append("")

    return "\n".join(parts).rstrip() + "\n", refs
