"""Explicit TeX in Markdown, rendered with self-contained KaTeX assets for offline exports."""
from __future__ import annotations

import base64
import html
import re
import uuid
from functools import lru_cache
from pathlib import Path

VENDOR = Path(__file__).with_name('vendor')


def formula_source(value: str) -> str:
    text = str(value or '').strip()
    for opening, closing in (('$$', '$$'), ('\\[', '\\]'), ('\\(', '\\)'), ('$', '$')):
        if text.startswith(opening) and text.endswith(closing):
            return text[len(opening):-len(closing)].strip()
    return text


def _escaped(text: str, pos: int) -> bool:
    count = 0
    while pos > 0 and text[pos - 1] == '\\':
        pos -= 1
        count += 1
    return count % 2 == 1


def math_spans(text: str):
    """Yield (start, end, tex, display), respecting code, links, currency and incomplete input."""
    # The export module already tracks Markdown code indentation, fences and links. Import lazily
    # to avoid an import cycle: export.render also uses this renderer for print/PDF pages.
    from modules.export.markdown import MARKDOWN_PROTECTED, _block_code_ranges

    protected = sorted([*_block_code_ranges(text), *(m.span() for m in MARKDOWN_PROTECTED.finditer(text)),
                        *(m.span() for m in re.finditer(r'https?://[^\s<>]+', text))])
    p = 0
    i = 0
    while i < len(text):
        while p < len(protected) and protected[p][1] <= i:
            p += 1
        if p < len(protected) and protected[p][0] <= i < protected[p][1]:
            i = protected[p][1]
            continue
        if text.startswith('\\\\', i):
            i += 2
            continue
        if _escaped(text, i):
            i += 1
            continue
        opening = next((mark for mark in ('$$', '\\[', '\\(', '$') if text.startswith(mark, i)), None)
        if not opening:
            i += 1
            continue
        closing = {'\\[': '\\]', '\\(': '\\)'}.get(opening, opening)
        start = i + len(opening)
        if opening == '$' and (start >= len(text) or text[start].isspace()):
            i += 1
            continue
        end = text.find(closing, start)
        while end >= 0 and _escaped(text, end):
            end = text.find(closing, end + len(closing))
        if end < 0 or end == start or (opening == '$' and ('\n' in text[start:end] or
            text[end - 1] == '$' or text[end:end + 2] == '$$' or text[end - 1].isspace() or
            (end + 1 < len(text) and text[end + 1].isdigit()))):
            i += len(opening)
            continue
        yield i, end + len(closing), text[start:end], opening in ('$$', '\\[')
        i = end + len(closing)


def protect_math(text: str) -> tuple[str, dict[str, str]]:
    prefix = 'ZXMATH' + uuid.uuid4().hex.upper()
    out, replacements, cursor = [], {}, 0
    for number, (start, end, tex, display) in enumerate(math_spans(text)):
        key = prefix + str(number) + 'END'
        klass = 'math-tex math-tex--display' if display else 'math-tex'
        replacements[key] = f'<span class="{klass}" data-tex="{html.escape(tex, quote=True)}" data-display="{str(display).lower()}">{html.escape(tex)}</span>'
        out += [text[cursor:start], key]
        cursor = end
    out.append(text[cursor:])
    return ''.join(out), replacements


def restore_math(rendered: str, replacements: dict[str, str]) -> str:
    for key, value in replacements.items():
        rendered = rendered.replace(key, value)
    return rendered


def render_markdown(text: str) -> str:
    from markdown_it import MarkdownIt

    protected, replacements = protect_math(text)
    rendered = MarkdownIt('commonmark', {'html': False}).enable('table').render(protected)
    return restore_math(rendered, replacements)


@lru_cache(maxsize=1)
def math_assets() -> str:
    """Bundle the pinned KaTeX runtime, CSS and fonts, without network requests or CDN reliance."""
    css = (VENDOR / 'katex.min.css').read_text()
    # WOFF2 is supported by every browser we target; only embed that format once per font face.
    def font(match):
        path = VENDOR / 'fonts' / match.group(1)
        data = base64.b64encode(path.read_bytes()).decode()
        return 'src:url(data:font/woff2;base64,' + data + ') format("woff2")'
    css = re.sub(r'src:url\(fonts/([^()]+\.woff2)\).*?(?=;|})', font, css)
    script = (VENDOR / 'katex.min.js').read_text().replace('</script', '<\\/script')
    render = '''window.__mathReady = false;
for (const node of document.querySelectorAll('.math-tex[data-tex]')) {
  katex.render(node.dataset.tex, node, {displayMode: node.dataset.display === 'true',
    throwOnError: false, output: 'htmlAndMathml', trust: false, strict: 'ignore', maxExpand: 1000, maxSize: 20});
}
Promise.resolve(document.fonts && document.fonts.ready).then(() => { window.__mathReady = true; });'''
    return (f'<style>{css}\n.math-tex--display{{display:block;max-width:100%;overflow-x:auto;overflow-y:hidden;margin:12px 0;padding:4px 0}}'
            '.math-tex--display .katex-display{margin:4px 0;text-align:left}.math-tex--display .katex-display>.katex{text-align:left}'
            '.math-tex .katex{font-size:1.08em}.math-tex .katex-error{white-space:pre-wrap;overflow-wrap:anywhere}'
            f'</style><script>{script}</script><script>{render}</script>')


def finish_page(page: str) -> str:
    return page.replace('</body>', math_assets() + '</body>') if 'class="math-tex' in page else page
