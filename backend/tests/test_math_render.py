import re

import pytest

from modules.math_render import finish_page, formula_source, math_spans, render_markdown
from modules.notes.export import to_preview_html
from modules.export import build_print_html
from modules.export.markdown import linkify_stamps


@pytest.mark.parametrize('source,tex,display', [
    (r"条件 $f'(\xi)=0$。", r"f'(\xi)=0", False),
    (r'数值 $2x+1$。', '2x+1', False),
    (r'\(a<\xi<b\)', r'a<\xi<b', False),
    ('$$\n\\frac{1}{x^2+1}\n$$', '\n\\frac{1}{x^2+1}\n', True),
    (r'\[\lim_{n\to\infty}a_n=1\]', r'\lim_{n\to\infty}a_n=1', True),
])
def test_math_recognizes_explicit_delimiters(source, tex, display):
    spans = list(math_spans(source))
    assert len(spans) == 1
    assert spans[0][2:] == (tex, display)
    rendered = render_markdown(source)
    assert 'data-tex=' in rendered
    assert f'data-display="{str(display).lower()}"' in rendered


@pytest.mark.parametrize('source', [
    '金额 $20 和 $30；价格 $5.00 and $10.00', r'转义 \$x\$ 与未完成 $x^2',
    '`$x^2$`', '```latex\n$$x^2$$\n```', '~~~latex\n$$x^2$$\n~~~',
    '    $$x^2$$', '[链接](https://example.com/$x$)', 'https://example.com/$x$',
])
def test_code_prices_links_and_incomplete_math_stay_literal(source):
    assert list(math_spans(source)) == []
    assert 'data-tex=' not in render_markdown(source)


def test_price_does_not_swallow_a_later_formula():
    assert [span[2] for span in math_spans('价格 $20 和 $30，公式 $x^2$')] == ['x^2']


def test_math_is_opaque_to_timestamp_export_and_markup_is_escaped():
    source = r'比例 $[00:30]$；回看 [00:30]'
    linked = linkify_stamps(source, 'https://www.bilibili.com/video/BV1', 'bilibili')
    assert '$[00:30]$' in linked and linked.count('t=30') == 1
    rendered = render_markdown('$x</span><img src=x onerror=alert(1)>$')
    assert '<img src=x' not in rendered
    assert '&lt;img' in rendered


def test_preview_is_self_contained_and_accepts_legacy_wrapped_formulas():
    note = {'title': '中值定理', 'summary': r'满足 $a<\xi<b$', 'sections': [{
        'id': 's1', 'title': '拉格朗日', 'points': [r'得到 \(f\prime(\xi)=0\)'],
        'formulas': [r'$$\frac{1}{x^2+1}$$', r'\[\lim_{n\to\infty}a_n=1\]'],
        'examples': [r'例题：$x_1<\xi<x_2$'], 'figures': [],
    }]}
    page = to_preview_html(note, None, lambda _: None)
    assert len(re.findall(r'data-tex=', page)) == 5
    assert 'data:font/woff2;base64,' in page
    assert 'window.__mathReady' in page and 'katex.render' in page
    assert 'fonts/KaTeX_' not in page and 'cdn.jsdelivr' not in page
    assert not re.search(r'<(?:script|link)[^>]+(?:src|href)=', page)
    assert formula_source(r'$$\frac{1}{x}$$') == r'\frac{1}{x}'
    assert finish_page('<body>普通文字</body>') == '<body>普通文字</body>'


def test_qa_print_uses_the_same_offline_math_and_preserves_time_links():
    video = {'title': '高数', 'canonical_url': 'https://www.bilibili.com/video/BV1', 'platform': 'bilibili'}
    page = build_print_html(video, '', [
        {'id': 1, 'role': 'user', 'content': '讲讲极限'},
        {'id': 2, 'role': 'assistant', 'content': r'由 $f\prime(\xi)=0$ 得到结果，见 [00:30]'},
    ], [], 'math-job', 'http://localhost')
    assert 'data-tex=' in page and 'katex.render' in page
    assert 't=30' in page
