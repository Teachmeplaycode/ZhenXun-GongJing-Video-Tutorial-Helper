"""No external queries: fixture pages distinguish registration records from mentions and failures."""
import asyncio
from types import SimpleNamespace

from modules.antifraud import institutions as inst
from modules.agent.web import Page

NAME = '示例科技有限公司'
SEGMENTS = [('transcript', 12, 18, f'机构名称：{NAME}，宣称正规。')]
RECORD = f'企业名称：{NAME}\n统一社会信用代码：91110000123456789X\n登记状态：存续\n'


def run(**kwargs):
    return asyncio.run(inst.check(SEGMENTS, **kwargs))


async def results(query, limit):
    assert NAME in query
    return [SimpleNamespace(url='https://www.gsxt.gov.cn/record')]


async def record(url):
    return Page(url, '企业登记记录', RECORD)


def test_extract_name_keeps_video_evidence_and_earliest_time():
    found = inst.extract([('screentext', 30, 35, f'欢迎来到{NAME}'), *SEGMENTS])
    assert [item['name'] for item in found] == [NAME]
    assert found[0]['timestamp']['start'] == 12


def test_actual_official_record_requires_exact_name_and_structured_fields():
    answer = run(config={}, searcher=results, fetcher=record)
    assert answer['items'][0]['status'] == 'record_found'
    assert answer['items'][0]['record']['registration_state'] == '存续'
    assert answer['items'][0]['sources'][0]['url'] == 'https://www.gsxt.gov.cn/record'
    assert '视频主体' in answer['items'][0]['reason']


def test_official_mention_is_not_registration_or_qualification():
    async def mention(url):
        return Page('https://www.csrc.gov.cn/notice', '风险提示', f'{NAME}出现在通告中。')
    answer = run(config={}, searcher=results, fetcher=mention)
    assert answer['status'] == 'partial'
    assert answer['items'][0]['status'] == 'official_reference'
    assert 'record' not in answer['items'][0]


def test_search_snippet_is_never_enough_without_page_body_evidence():
    async def unrelated(url):
        return Page(url, NAME, '访问验证。页面没有企业名称。')
    answer = run(config={}, searcher=results, fetcher=unrelated)
    assert answer['items'][0]['status'] == 'unverified'
    assert not answer['items'][0]['sources']


def test_no_results_does_not_claim_nonexistence():
    async def empty(*args, **kwargs):
        return []
    answer = run(config={}, searcher=empty, fetcher=record)
    assert answer['items'][0]['status'] == 'unverified'
    assert '不代表机构不存在' in answer['items'][0]['reason']


def test_search_and_fetch_errors_preserve_honest_unverified_state():
    async def fail(*args, **kwargs):
        raise RuntimeError('provider unavailable')
    a = run(config={}, searcher=fail, fetcher=record)
    b = run(config={}, searcher=results, fetcher=fail)
    assert a['items'][0]['status'] == b['items'][0]['status'] == 'error'
    assert '未核实' in a['items'][0]['reason']


def test_web_off_does_not_call_network_or_leak_entity_names():
    async def forbidden(*args, **kwargs):
        raise AssertionError('must not call network')
    answer = run(config={'LLM_WEB': 'off'}, searcher=forbidden, fetcher=forbidden)
    assert answer['items'][0]['status'] == 'unverified'
    assert '联网已关闭' in answer['items'][0]['reason']


def test_configured_registry_url_is_fetched_with_existing_safe_fetcher(tmp_path):
    import json
    path = tmp_path / 'sources.json'
    path.write_text(json.dumps({NAME: ['https://www.gsxt.gov.cn/direct']}))
    async def forbidden(*args, **kwargs):
        raise AssertionError('explicit sources should avoid search')
    answer = run(config={'ANTIFRAUD_INSTITUTION_SOURCES': str(path)}, searcher=forbidden, fetcher=record)
    assert answer['items'][0]['status'] == 'record_found'
    assert answer['items'][0]['sources'][0]['url'].endswith('/direct')


def test_official_lookalike_and_unrelated_record_cannot_verify_registration():
    assert not inst.official('https://www.gsxt.gov.cn.evil.example/record')
    assert not inst.registry_record('https://www.gsxt.gov.cn.evil.example/record', RECORD, NAME)
    assert not inst.registry_record('https://www.gsxt.gov.cn/record', RECORD, '另一科技有限公司')
    assert not inst.registry_record('https://www.gsxt.gov.cn/record', RECORD + '企业名称：另一科技有限公司\n', NAME)


def test_non_official_source_remains_unverified_even_with_registration_text():
    async def third_party(url):
        return Page('https://directory.example/record', '目录', RECORD)
    answer = run(config={}, searcher=results, fetcher=third_party)
    assert answer['items'][0]['status'] == 'unverified'
    assert not answer['items'][0]['sources'][0]['official']


def test_config_errors_and_lookup_cap_are_explicit(tmp_path):
    answer = run(config={'ANTIFRAUD_INSTITUTION_SOURCES': str(tmp_path / 'missing')}, searcher=results, fetcher=record)
    assert answer['configuration_error']
    segments = SEGMENTS + [('screentext', 22, 24, '另一科技有限公司')]
    answer = asyncio.run(inst.check(segments, config={'ANTIFRAUD_MAX_INSTITUTIONS': '1'}, searcher=results, fetcher=record))
    assert answer['omitted'] == 1 and answer['status'] == 'partial'


def test_narrative_boundaries_do_not_become_part_of_legal_name():
    for text in (f'这是{NAME}推出的产品', f'今天介绍的是{NAME}', f'该产品由{NAME}推出',
                 f'我们与{NAME}合作', f'声称来自{NAME}', NAME):
        assert [item['name'] for item in inst.extract([('transcript', 1, 2, text)])] == [NAME]
    assert inst.extract([('transcript', 1, 2, '这是北京示例科技有限公司推出的产品')])[0]['name'] == '北京示例科技有限公司'


def test_narration_uses_exact_configured_name_instead_of_inventing_institution(tmp_path):
    import json
    path = tmp_path / 'sources.json'
    path.write_text(json.dumps({NAME: ['https://www.gsxt.gov.cn/direct']}))
    async def no_search(*args, **kwargs):
        raise AssertionError('configured exact legal name must be used')
    result = asyncio.run(inst.check([('transcript', 4, 6, f'这是{NAME}推出的产品')],
        config={'ANTIFRAUD_INSTITUTION_SOURCES': str(path)}, searcher=no_search, fetcher=record))
    assert result['items'][0]['status'] == 'record_found'
    assert result['items'][0]['name'] == NAME
