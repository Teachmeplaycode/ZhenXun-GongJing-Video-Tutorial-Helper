"""Public institution evidence lookup. Search hits never establish registration or licensing.

ANTIFRAUD_INSTITUTION_SOURCES may point to a local JSON {exact_name: [public_url, ...]}.
This is useful for official registries that search engines cannot index. Pages are always
fetched through the existing SSRF/redirect-safe web.fetch; no browser credentials are used.
"""
from __future__ import annotations

import asyncio
import json
import re
from pathlib import Path
from urllib.parse import urlsplit

from modules.agent import web
from modules.settings import settings

SUFFIX = r'(?:股份有限公司|有限责任公司|有限公司|证券公司|保险公司|基金管理公司|投资公司|银行|基金会|医院|研究院|研究所|大学|集团)'
NAME = re.compile(rf'[\u4e00-\u9fffA-Za-z·]{{2,36}}{SUFFIX}')
INTRO = re.compile(r'^(?:(?:视频中|我们|他们|我是|来自|欢迎来到|声称|所谓|这家|一家|机构名称|公司名称|机构|公司|名称|由|在|向|与|是|的|本视频推荐|推荐|请核查|核查|介绍|据称))+')
# Narration boundaries are separated before matching, so prose cannot become part of
# the legal name. Keep standalone names (including location prefixes) unchanged.
CLAUSE_BREAK = re.compile(
    r'(?:这是|那是|这就是|那就是|(?:介绍|推荐|提到|核查|声称|宣称)的是|'
    r'(?:产品|项目|服务)(?:由|来自)|(?:我们|他们)(?:与|由|在|来自|推荐)|'
    r'(?:声称|宣称|据称)?来自|欢迎来到|所属(?:机构|公司)是|机构名称|公司名称)\s*[:：]?\s*'
)
REGISTRY_HOSTS = ('gsxt.gov.cn',)
REGISTRY_LABEL = re.compile(r'(?:企业名称|机构名称|单位名称)\s*[:：]\s*([^\n，。；;]{2,60})')
CODE = re.compile(r'(?:统一社会信用代码|注册号)\s*[:：]\s*([0-9A-Z]{18}|[0-9]{15})(?![A-Za-z0-9])')
STATE = re.compile(r'登记状态\s*[:：]\s*(存续|在业|开业|正常|注销|吊销)')


def official(url: str) -> bool:
    host = (urlsplit(url).hostname or '').lower().rstrip('.')
    return urlsplit(url).scheme in {'http', 'https'} and (host == 'gov.cn' or host.endswith('.gov.cn'))


def registry_record(url: str, text: str, name: str) -> dict | None:
    """Only an exact structured registry record, never a general notice or search snippet."""
    host = (urlsplit(url).hostname or '').lower().rstrip('.')
    if not any(host == h or host.endswith('.' + h) for h in REGISTRY_HOSTS):
        return None
    names = [m.group(1).strip() for m in REGISTRY_LABEL.finditer(text)]
    code, state = CODE.search(text), STATE.search(text)
    # Reject search result lists with several records: fields might belong to another entity.
    if names != [name] or not code or not state:
        return None
    return {'name': name, 'registration_code': code.group(1), 'registration_state': state.group(1)}


def extract(segments) -> list[dict]:
    found = {}
    for source, start, end, text in segments:
        for match in NAME.finditer(CLAUSE_BREAK.sub(" ", text)):
            name = INTRO.sub('', match.group(0)).strip()
            if len(name) < 4:
                continue
            item = {'name': name, 'timestamp': {'start': start, 'end': end},
                    'evidence': {'source': source}, 'original_text': text[:1500]}
            if name not in found or start < found[name]['timestamp']['start']:
                found[name] = item
    return sorted(found.values(), key=lambda item: item['timestamp']['start'])


def _int(config, name, default, maximum):
    try:
        return max(1, min(maximum, int(config.get(name, default))))
    except (TypeError, ValueError):
        return default


def configured_sources(config) -> dict:
    filename = config.get('ANTIFRAUD_INSTITUTION_SOURCES', '').strip()
    if not filename:
        return {}
    path = Path(filename).expanduser()
    if path.stat().st_size > 1 << 20:
        raise ValueError('机构来源配置超过大小上限')
    value = json.loads(path.read_text(encoding='utf-8'))
    if not isinstance(value, dict) or any(not isinstance(k, str) or not isinstance(v, list)
            or any(not isinstance(url, str) for url in v) for k, v in value.items()):
        raise ValueError('机构来源配置须为机构全称到URL列表的对象')
    return value


async def check(segments, *, config=None, searcher=None, fetcher=None) -> dict:
    config = settings() if config is None else config
    names = extract(segments)
    cap = _int(config, 'ANTIFRAUD_MAX_INSTITUTIONS', 3, 5)
    chosen = names[:cap]
    result = {'status': 'done', 'items': [], 'omitted': max(0, len(names) - cap),
              'message': '公开网页证据只能辅助核查；登记记录不证明视频主体身份、经营资质或产品安全。'}
    if not chosen:
        result['status'] = 'not_applicable'
        result['message'] = '未提取到可核查的机构全称；不据此推断不存在机构或资质问题。'
        return result
    if config.get('LLM_WEB', 'on').lower() in {'off', '0', 'false'}:
        result['status'] = 'partial'
        result['items'] = [dict(item, status='unverified', reason='联网已关闭，机构未核实。', sources=[]) for item in chosen]
        return result
    try:
        known = configured_sources(config)
    except (OSError, ValueError):
        known = {}
        result['configuration_error'] = '机构来源文件不可用；尝试公开检索，不视为已核实。'
    searcher, fetcher = searcher or web.search, fetcher or web.fetch
    timeout = _int(config, 'ANTIFRAUD_INSTITUTION_TIMEOUT', 20, 60)
    semaphore = asyncio.Semaphore(2)

    async def lookup(item):
        answer = dict(item, status='unverified', reason='未找到足以确认登记的公开证据；不代表机构不存在。', sources=[])
        async def run():
            urls = list(known.get(item['name'], []))[:2]
            if not urls:
                hits = await searcher(f'"{item["name"]}" 登记 注册 资质 site:gov.cn', limit=5)
                urls = [hit.url for hit in hits]
            # Prefer official evidence, but keep third-party material visibly unverified.
            urls = sorted(dict.fromkeys(urls), key=lambda url: not official(url))[:2]
            errors = 0
            for url in urls:
                try:
                    page = await fetcher(url)
                except Exception:
                    errors += 1
                    continue
                if item['name'] not in page.text:
                    continue
                position = page.text.index(item['name'])
                snippet = page.text[max(0, position - 180):position + 700]
                record = registry_record(page.url, page.text, item['name'])
                source = {'title': page.title, 'url': page.url, 'snippet': snippet,
                          'official': official(page.url), 'kind': 'registry' if record else 'reference'}
                answer['sources'].append(source)
                if record:
                    answer.update(status='record_found', record=record,
                        reason='官方登记页包含与机构全称精确匹配的登记记录。记录状态见来源；尚未确认视频主体与该机构的关联或经营资质。')
                    return
            if answer['sources']:
                has_official = any(source['official'] for source in answer['sources'])
                answer['status'] = 'official_reference' if has_official else 'unverified'
                answer['reason'] = ('官方公开页面提及该机构，但没有足以确认当前登记/资质的结构化记录。' if has_official
                                    else '仅取得第三方提及，不能确认机构登记或经营资质。')
            elif errors:
                answer.update(status='error', reason='公开页面读取失败，机构未核实；未取得证据不代表机构不存在。')
        async with semaphore:
            try:
                await asyncio.wait_for(run(), timeout)
            except Exception:
                answer.update(status='error', reason='机构公开证据检索失败或超时，机构未核实。')
        return answer

    result['items'] = await asyncio.gather(*(lookup(item) for item in chosen))
    if result['omitted'] or any(item['status'] != 'record_found' for item in result['items']):
        result['status'] = 'partial'
    return result
