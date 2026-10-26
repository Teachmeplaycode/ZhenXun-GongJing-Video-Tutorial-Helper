"""Selected composer tasks are metadata, never text the user is made to appear to have typed."""
import asyncio

import pytest
from fastapi.testclient import TestClient

from modules.export import build_markdown, build_print_html
from modules.store import SessionStore
from tests.test_screentext import make_job


@pytest.fixture
def api(tmp_path, monkeypatch):
    import app
    store = SessionStore(tmp_path / 'sessions.sqlite3')
    job = make_job(tmp_path / 'jobs' / 'command-job')
    job.id = 'command-job'
    store.create(job, 'test')
    seen, charged = [], []
    async def run(job, client, question, **options):
        seen.append({'question': question, **options})
        yield {'type': 'assistant.message.delta', 'delta': '回答正文'}
        yield {'type': 'run.completed', 'steps': 1, 'elapsed_ms': 1, 'model': 'test', 'usage': {}}
    async def evidence(events, job, question):
        async for event in events:
            yield event
    monkeypatch.setattr(app, 'store', store)
    monkeypatch.setattr(app, 'DATA_DIR', tmp_path / 'jobs')
    monkeypatch.setattr(app, 'find_job', lambda _: job)
    monkeypatch.setattr(app, 'mine', lambda _: True)
    monkeypatch.setattr(app, 'get_llm', lambda: object())
    monkeypatch.setattr(app, 'get_decider', lambda: None)
    monkeypatch.setattr(app, 'run_agent', run)
    monkeypatch.setattr(app, 'with_evidence', evidence)
    monkeypatch.setattr(app.member_service, 'charge', charged.append)
    client = TestClient(app.app)
    yield client, store, job, seen, charged
    client.close()
    store.close()


def test_command_executes_canonical_instruction_but_saves_only_user_text(api):
    client, store, job, seen, charged = api
    response = client.post('/api/agent/runs', json={'video_id': job.id, 'command': '核实',
        'question': '只核实罗尔定理的证明', 'web': False, 'papers': True})
    assert response.status_code == 200
    assert '查资料' in seen[0]['question'] and '只核实罗尔定理的证明' in seen[0]['question']
    assert seen[0]['command'] == '核实'
    question = store.messages(job.id)[0]
    assert question['content'] == '只核实罗尔定理的证明'
    assert question['command'] == '核实' and question['web'] is False and question['papers'] is True
    assert charged == ['questions']
    assert store.history(job.id)[0]['content'] == seen[0]['question']


def test_a_task_without_user_supplement_is_valid_and_stays_distinct_in_history(api):
    client, store, job, seen, _ = api
    assert client.post('/api/agent/runs', json={'video_id': job.id, 'command': '总结', 'question': ''}).status_code == 200
    assert seen[0]['question'].startswith('总结这个视频')
    saved = store.messages(job.id)[0]
    assert saved['content'] == '' and saved['command'] == '总结'
    assert store.history(job.id)[0]['content'] == seen[0]['question']


@pytest.mark.parametrize('command', ['unknown', '', 'skill.factcheck', 12])
def test_unknown_command_is_rejected_before_charging_or_writing(api, command):
    client, store, job, seen, charged = api
    assert client.post('/api/agent/runs', json={'video_id': job.id, 'command': command, 'question': '用户文字'}).status_code == 422
    assert not seen and not charged and not store.messages(job.id)


def test_legacy_question_is_unchanged_and_does_not_pass_a_new_keyword(api):
    client, store, job, seen, _ = api
    assert client.post('/api/agent/runs', json={'video_id': job.id, 'question': '自己输入的普通问题'}).status_code == 200
    assert seen[0]['question'] == '自己输入的普通问题' and 'command' not in seen[0]
    assert store.messages(job.id)[0]['content'] == '自己输入的普通问题'


@pytest.mark.parametrize('command, question', [('细看', '看01:00 到 01:05的动作'), ('慢放', '12秒到13秒'), ('慢放', '01:00 到 01:05')])
def test_user_time_does_not_keep_a_conflicting_default(command, question):
    from modules.agent.commands import compose_question
    effective = compose_question(command, question)
    assert question in effective
    assert '00:00' not in effective and '00:02' not in effective and '00:30' not in effective


def test_default_time_and_summary_plan_are_preserved():
    from modules.agent.commands import compose_question
    from modules.agent.response_plan import is_summary
    assert '00:00 到 00:30' in compose_question('细看', '')
    assert '00:00 到 00:02' in compose_question('慢放', '')
    assert is_summary(compose_question('总结', '关注几个核心概念'))
    assert compose_question(None, '  原样文字  ') == '  原样文字  '


def test_exports_label_the_task_without_inserting_template_as_user_text(api, tmp_path):
    client, store, job, _, _ = api
    client.post('/api/agent/runs', json={'video_id': job.id, 'command': '核实', 'question': '我的补充'})
    client.post('/api/agent/runs', json={'video_id': job.id, 'command': '总结', 'question': ''})
    messages = store.messages(job.id)
    md, _ = build_markdown(job.video.public(), '', messages, [], job.id, tmp_path)
    html = build_print_html(job.video.public(), '', messages, [], job.id, 'https://example.test')
    for content in (md, html):
        assert '任务：' in content and '/核实' in content and '/总结' in content and '我的补充' in content
        assert '核实视频里的主要说法是否正确' not in content


def test_gif_studio_preserves_command_metadata_without_a_template(api):
    client, store, job, _, _ = api
    response = client.post(f'/api/link-jobs/{job.id}/studio', json={'text': '', 'command': 'GIF', 'start': 1, 'end': 3})
    assert response.status_code == 200
    card = store.messages(job.id)[0]
    assert card['manual'] == 'clip' and card['request'] == '' and card['command'] == 'GIF'


@pytest.mark.parametrize('command,tool', [('科普核查','skill.factcheck'), ('反诈识别','skill.antifraud')])
def test_explicit_skill_selection_is_not_taken_over_by_summary_words(tmp_path, monkeypatch, command, tool):
    from modules.agent.commands import compose_question
    from modules.agent import run
    from modules.agent.tools import ToolResult
    from tests.test_tools import make_job as tool_job
    monkeypatch.setenv('INTENT_LLM_FALLBACK', 'off')
    monkeypatch.setattr(run.experience, 'kinds', lambda: [])
    async def classifier(*args, **kwargs):
        raise AssertionError('explicit skill selection should not be reclassified')
    async def stream(self, name, params):
        yield ToolResult('已完成核查', '核查完毕', data={'skill': tool.split('.')[-1]}, count=1)
    monkeypatch.setattr(run.intent, 'classify', classifier)
    monkeypatch.setattr(run.AgentTools, 'stream', stream)
    class Client:
        config = type('Config', (), {'model': 'test'})()
        async def stream(self, messages, usage, **kwargs):
            usage.prompt_tokens, usage.completion_tokens, usage.finish_reason = 100, 10, 'stop'
            yield '核查结论。'
    async def go():
        return [event async for event in run.run_agent(tool_job(tmp_path), Client(), compose_question(command, '总结结论'), command=command)]
    events = asyncio.run(go())
    assert any(event.get('tool_name') == tool for event in events)


def test_selected_generic_verification_requires_research_without_running_health_skill(tmp_path, monkeypatch):
    from modules.agent.commands import compose_question
    from modules.agent import run
    from modules.agent.tools import ToolResult
    from modules.llm import ToolCall
    from tests.test_tools import make_job as tool_job
    monkeypatch.setenv('LLM_WEB', 'on')
    monkeypatch.setattr(run.experience, 'kinds', lambda: [])
    async def no_classifier(*args, **kwargs):
        raise AssertionError('selected verification must not be reclassified or have research voted away')
    monkeypatch.setattr(run.intent, 'classify', no_classifier)
    monkeypatch.setattr(run, 'research_wanted', no_classifier)
    async def stream(self, name, params):
        assert name == 'web_search'
        yield ToolResult('已核实数学定理', '有来源', count=1)
    monkeypatch.setattr(run.AgentTools, 'stream', stream)
    class Client:
        config = type('Config', (), {'model': 'test'})()
        calls = 0
        async def stream(self, messages, usage, **kwargs):
            self.calls += 1
            usage.prompt_tokens, usage.completion_tokens, usage.finish_reason = 100, 10, 'stop'
            if self.calls == 1:
                yield '未经核实不应直接发出的断言'
            elif self.calls == 2:
                usage.tool_calls = [ToolCall('lookup', 'web_search', {'query': '罗尔定理'})]
                usage.finish_reason = 'tool_calls'
                return
            else:
                yield '已查资料后的回答'
    async def go():
        return [e async for e in run.run_agent(tool_job(tmp_path), Client(), compose_question('核实', '罗尔定理'), command='核实')]
    events = asyncio.run(go())
    assert any(e.get('tool_name') == 'web.search' for e in events)
    assert not any(str(e.get('tool_name', '')).startswith('skill.') for e in events)
    assert ''.join(e['delta'] for e in events if e['type'] == 'assistant.message.delta') == '已查资料后的回答'


def test_look_closer_uses_the_users_seconds_for_automatic_frame_reading():
    from modules.agent.commands import compose_question
    from modules.agent.run import asked_ranges
    assert asked_ranges(compose_question('细看', '12秒到13秒的动作')) == [('00:12', '00:13')]


@pytest.mark.parametrize('command, supplement', [('时间线', '骗局出现的时间点'), ('论文', '总结这个主题的研究')])
def test_other_selected_tasks_do_not_become_unrequested_whole_video_skills(tmp_path, monkeypatch, command, supplement):
    from modules.agent import run
    from modules.agent.commands import compose_question
    from tests.test_tools import make_job as tool_job
    monkeypatch.setenv('LLM_TOOLS', 'off')
    monkeypatch.setattr(run.experience, 'kinds', lambda: [])
    async def no_classifier(*args, **kwargs):
        raise AssertionError('selected task should define the route')
    monkeypatch.setattr(run.intent, 'classify', no_classifier)
    class Client:
        config = type('Config', (), {'model': 'test'})()
        async def stream(self, messages, usage, **kwargs):
            usage.prompt_tokens, usage.completion_tokens, usage.finish_reason = 100, 10, 'stop'
            yield '回答正文'
    async def go():
        return [e async for e in run.run_agent(tool_job(tmp_path), Client(), compose_question(command, supplement), command=command)]
    events = asyncio.run(go())
    route = next(e for e in events if e['type'] == 'tool_call.output' and e['call_id'] == 'route')
    assert route['data']['kind'] == 'content'
    assert not any(str(e.get('tool_name', '')).startswith('skill.') for e in events)


def test_session_list_can_name_a_task_without_claiming_the_template_is_user_text(api):
    client, store, job, _, _ = api
    client.post('/api/agent/runs', json={'video_id': job.id, 'command': '总结', 'question': ''})
    assert store.messages(job.id)[0]['content'] == ''
    assert store.list()[0]['last_question'] == '/总结'


@pytest.mark.parametrize('seconds, clock', [('3600', '1:00:00'), ('7200', '2:00:00')])
def test_seconds_normalization_keeps_long_course_times(seconds, clock):
    from modules.agent.commands import compose_question
    from modules.agent.run import asked_ranges
    effective = compose_question('细看', f'{seconds}秒到{int(seconds)+5}秒')
    assert asked_ranges(effective)[0][0] == clock


def test_single_seconds_point_is_ready_for_automatic_frame_reading():
    from modules.agent.commands import compose_question
    from modules.agent.run import asked_ranges
    ranges = asked_ranges(compose_question('细看', '看100秒的按钮'))
    assert [(float(a), float(b)) for a, b in ranges] == [(90, 110)]
    # A compound Chinese time is left intact rather than turning its seconds suffix into a new point.
    assert not asked_ranges(compose_question('细看', '看1分40秒的按钮'))


def test_process_task_adapts_to_a_pv_without_classifying_it_as_software(tmp_path, monkeypatch):
    from modules.agent import run
    from modules.agent.commands import compose_question
    from tests.test_tools import make_job as tool_job
    monkeypatch.setenv('LLM_TOOLS', 'off')
    monkeypatch.setattr(run.experience, 'kinds', lambda: [])
    async def no_classifier(*args, **kwargs):
        raise AssertionError('explicit process task must not add a classification call')
    monkeypatch.setattr(run.intent, 'classify', no_classifier)
    seen = []
    class Client:
        config = type('Config', (), {'model': 'test'})()
        async def stream(self, messages, usage, **kwargs):
            seen.append(messages)
            usage.prompt_tokens, usage.completion_tokens, usage.finish_reason = 100, 10, 'stop'
            yield '开场远景建立空间，随后切到人物近景。'
    job = tool_job(tmp_path)
    job.video.title = '游戏 PV'
    async def go():
        return [e async for e in run.run_agent(job, Client(), compose_question('卡点', '关注开场分镜'), command='卡点')]
    events = asyncio.run(go())
    assert len(seen) == 1 and events[-1]['type'] == 'run.completed'
    guide = seen[0][-1]['content']
    assert '影视、PV' in guide and '景别、构图、运镜' in guide
    effective = compose_question('卡点', '关注开场分镜')
    assert '影视讲镜头' in effective and '点了哪个按钮' not in effective
