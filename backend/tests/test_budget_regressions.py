import asyncio
import types

import pytest

from modules.agent.budget import AnswerBudget, prices, side_tokens
from modules.agent.run import run_agent
from test_budget import make_job, client_for, collect, sse_body


def test_unknown_intent_usage_cannot_look_free(monkeypatch):
    monkeypatch.setenv("LLM_PRICE_IN_M", "2")
    monkeypatch.setenv("LLM_PRICE_OUT_M", "8")
    b = AnswerBudget()
    b.add_side({"prompt_tokens": None, "completion_tokens": None}, 5)
    b.llm_finished(100, 10)
    assert b.cost()["computable"] is False


def test_nonfinite_prices_and_invalid_usage_are_unknown(monkeypatch):
    monkeypatch.setenv("LLM_PRICE_IN_M", "inf")
    monkeypatch.setenv("LLM_PRICE_OUT_M", "NaN")
    assert prices() == (None, None)
    assert side_tokens({"prompt": True, "completion": -1}) == (None, None)


def test_nested_skill_model_calls_are_in_terminal_usage(tmp_path, monkeypatch):
    import httpx
    from modules.agent import skills
    from modules.llm import Usage
    async def fake_skill(name, job, llm, **kwargs):
        async def nested():
            u = Usage()
            return "".join([d async for d in llm.stream([], u)])
        await asyncio.gather(nested(), nested())
        yield ("result", "verified", "verified", 1, {}, False)
    monkeypatch.setattr(skills, "run", fake_skill)
    def handler(request):
        return httpx.Response(200, text=sse_body(
            {"choices": [{"delta": {"content": "answer"}, "finish_reason": "stop"}]},
            {"choices": [], "usage": {"prompt_tokens": 100, "completion_tokens": 10}}))
    events = collect(run_agent(make_job(tmp_path, ["ok"]), client_for(handler), "科普核查"))
    assert events[-1]["usage"]["prompt"] == 300
    assert events[-1]["budget"]["llm_calls"] == 3


def test_partial_usage_keeps_known_lower_bounds(monkeypatch):
    from modules.agent.budget import MeteredClient
    from modules.llm import Usage
    class Partial:
        async def stream(self, messages, usage, **kwargs):
            usage.prompt_tokens, usage.completion_tokens = 19, None
            yield 'partial'
    async def go():
        b = AnswerBudget()
        u = Usage()
        assert [x async for x in MeteredClient(Partial(), b).stream([], u)] == ['partial']
        return b
    b = asyncio.run(go())
    assert b.usage() == {'prompt': 19, 'completion': None, 'known_prompt': 19, 'known_completion': 0, 'complete': False}
    assert not b.cost()['computable']


def test_model_failure_and_cancel_retain_partial_usage():
    from modules.agent.budget import MeteredClient
    from modules.llm import Usage, LLMError
    class Broken:
        async def stream(self, messages, usage, **kwargs):
            usage.prompt_tokens = 13
            yield 'partial'
            raise LLMError('network', 'broken')
    async def fail():
        b = AnswerBudget()
        with pytest.raises(LLMError):
            async for _ in MeteredClient(Broken(), b).stream([], Usage()):
                pass
        assert b.prompt_tokens == 13 and b.llm_failures == 1
        assert b.usage()['prompt'] is None and not b.tokens_known
        return b
    asyncio.run(fail())
    class Waiting:
        async def stream(self, messages, usage, **kwargs):
            usage.prompt_tokens = 7
            await asyncio.sleep(60)
            yield 'never'
    async def cancel():
        b = AnswerBudget()
        async def consume():
            async for _ in MeteredClient(Waiting(), b).stream([], Usage()):
                pass
        task = asyncio.create_task(consume())
        await asyncio.sleep(.01)
        task.cancel()
        with pytest.raises(asyncio.CancelledError):
            await task
        assert b.llm_calls == 1 and b.llm_failures == 1 and b.prompt_tokens == 7
        assert b.calls[0]['status'] == 'cancelled' and not b.tokens_known
    asyncio.run(cancel())


def test_shared_client_is_metered_independently_for_parallel_answers():
    from modules.agent.budget import MeteredClient
    from modules.llm import Usage
    class Shared:
        async def stream(self, messages, usage, **kwargs):
            await asyncio.sleep(.005)
            usage.prompt_tokens, usage.completion_tokens = messages[0], 2
            yield 'ok'
    async def go():
        raw = Shared()
        a, b = AnswerBudget(), AnswerBudget()
        async def consume(budget, n):
            return [d async for d in MeteredClient(raw, budget).stream([n], Usage())]
        await asyncio.gather(consume(a, 10), consume(b, 20))
        assert a.prompt_tokens == 10 and b.prompt_tokens == 20
        assert a.llm_calls == b.llm_calls == 1
    asyncio.run(go())


def test_remaining_seconds_interrupt_model_and_preserve_terminal(tmp_path, monkeypatch):
    import time
    monkeypatch.setenv('LLM_BUDGET_MAX_SECONDS', '.03')
    class Slow:
        config = types.SimpleNamespace(model='slow')
        async def stream(self, messages, usage, **kwargs):
            usage.prompt_tokens = 17
            await asyncio.sleep(60)
            yield 'never'
    start = time.perf_counter()
    done = collect(run_agent(make_job(tmp_path, ['ok']), Slow(), '讲了什么'))[-1]
    assert time.perf_counter() - start < .5
    assert done['type'] == 'run.error' and done['code'] == 'budget'
    assert done['budget']['limit_hits'] == ['seconds']
    assert done['usage']['known_prompt'] == 17 and not done['usage']['complete']


def test_skill_obeys_call_limit_before_nested_requests(tmp_path, monkeypatch):
    import httpx
    from modules.agent import skills
    monkeypatch.setenv('LLM_BUDGET_MAX_TOOL_CALLS', '0')
    async def forbidden(*args, **kwargs):
        raise AssertionError('skill must not start')
        yield
    monkeypatch.setattr(skills, 'run', forbidden)
    handler = lambda r: httpx.Response(200, text=sse_body(
        {'choices': [{'delta': {'content': 'existing facts'}, 'finish_reason': 'stop'}]},
        {'choices': [], 'usage': {'prompt_tokens': 100, 'completion_tokens': 10}}))
    events = collect(run_agent(make_job(tmp_path, ['ok']), client_for(handler), '科普核查'))
    done = events[-1]
    assert done['type'] == 'run.completed' and done['budget']['tool_calls'] == 0
    assert done['budget']['blocked_calls'] == 1
    assert any(e.get('exit_code') == 3 for e in events)


def test_initial_frames_and_request_reservations_cannot_exceed_cap():
    from modules.agent.budget import limits
    b = AnswerBudget(caps={**limits({}), 'frames': 5})
    assert b.select_frames(3) == 3
    denied, args = b.prepare_tool('view_frames', {'count': 6})
    assert denied is None and args['count'] == 2
    denied, _ = b.prepare_tool('view_frames', {'count': 1})
    assert denied == 'frames' and b.frames_reserved == 5
    c = AnswerBudget(caps={**limits({}), 'frames': 15})
    assert c.prepare_tool('replay', {})[0] == 'frames'
    assert c.tool_calls == 0  # no decoding can start with insufficient quota


def test_tool_reservation_is_atomic_for_parallel_attempts():
    from modules.agent.budget import limits
    b = AnswerBudget(caps={**limits({}), 'external': 1})
    assert b.prepare_tool('web_search', {})[0] is None
    assert b.prepare_tool('fetch_page', {})[0] == 'external'
    assert b.external_calls == b.tool_calls == b.blocked_calls == 1


def test_unknown_token_reports_are_not_zero_in_eval(capsys):
    from scripts.eval import summary, print_report
    rows = [dict(id='a', passed=True, seconds=1, prompt_tokens=2000, completion_tokens=100,
                 cost_cny=None, fails=[], judge=None),
            dict(id='b', passed=True, seconds=1, prompt_tokens=None, completion_tokens=None,
                 cost_cny=None, fails=[], judge=None)]
    s = summary(rows)
    assert s['avg_prompt_k'] == 2 and s['prompt_priced'] == '1/2'
    assert s['avg_completion_k'] == .1 and s['completion_priced'] == '1/2'
    print_report(rows, None)
    out = capsys.readouterr().out
    assert '未知' in out and '1/2 题已知' in out


def test_budget_error_is_persisted_in_answer_log(tmp_path, monkeypatch):
    import json
    from fastapi.testclient import TestClient
    from test_budget import load_app
    monkeypatch.setenv('LLM_BUDGET_MAX_SECONDS', '0')
    app = load_app(tmp_path, monkeypatch)
    job = make_job(tmp_path / 'jobs' / 'j1', ['ok'])
    app.jobs['j1'] = job
    app.store.create(job, 'test')
    monkeypatch.setattr(app, 'get_llm', lambda: types.SimpleNamespace(config=types.SimpleNamespace(model='unused')))
    with TestClient(app.app) as c:
        response = c.post('/api/agent/runs', json={'video_id': 'j1', 'question': 'hello', 'history': False, 'web': False, 'papers': False})
    assert '"code": "budget"' in response.text
    records = [json.loads(line) for path in (tmp_path / 'logs').glob('*.jsonl') for line in path.read_text().splitlines()]
    final = next(r for r in records if r['event'] == 'answer')
    assert final['status'] == 'error' and final['budget_limit_hits'] == ['seconds']
    assert final['tool_calls'] == 0
    assert final['cost_cny'] is None and final['known_prompt_tokens'] == 0


def test_stopping_api_stream_persists_live_budget(tmp_path, monkeypatch):
    import json
    from test_budget import load_app
    app = load_app(tmp_path, monkeypatch)
    job = make_job(tmp_path / 'jobs' / 'j1', ['ok'])
    app.jobs['j1'] = job
    app.store.create(job, 'test')
    closed = []
    class Partial:
        config = types.SimpleNamespace(model='partial')
        async def stream(self, messages, usage, **kwargs):
            try:
                usage.prompt_tokens = 23
                yield 'a' * 80
                await asyncio.sleep(60)
            finally:
                closed.append(True)
    monkeypatch.setattr(app, 'get_llm', lambda: Partial())
    captured = []
    monkeypatch.setattr(app.log, 'event', lambda event, **fields: captured.append({'event': event, **fields}))
    async def go():
        response = await app.agent_run(app.AgentRequest(video_id='j1', question='hello', history=False, web=False, papers=False))
        async for chunk in response.body_iterator:
            if 'assistant.message.delta' in chunk:
                break
        await response.body_iterator.aclose()
        assert closed == [True]  # request-owned model stream closes before the API returns
    asyncio.run(go())
    final = next(r for r in captured if r['event'] == 'answer')
    assert final['status'] == 'stopped' and final['known_prompt_tokens'] == 23
    assert final['usage_complete'] is False and final['prompt_tokens'] is None
    assert final['tool_calls'] == 0
    assistant = app.store.messages(job.id)[-1]
    stopped = assistant['events'][-1]
    assert stopped['code'] == 'stopped' and stopped['budget']['llm_calls'] == 1
    assert stopped['usage']['known_prompt'] == 23 and not stopped['cost']['computable']


def test_zoom_frames_enter_context_once_and_obey_remaining_quota(tmp_path, monkeypatch):
    import httpx
    from modules.agent.tools import AgentTools, ToolResult
    job = make_job(tmp_path, ['ok', 'ok'])
    n_requested = []
    async def view(self, name, args):
        n_requested.append(args['count'])
        return ToolResult('zoom', 'zoom', 1, [('zoom', job.frame_path(0))])
    monkeypatch.setattr(AgentTools, 'run', view)
    monkeypatch.setenv('LLM_BUDGET_MAX_FRAMES', '3')
    bodies = []
    def handler(request):
        import json
        bodies.append(json.loads(request.content))
        return httpx.Response(200, text=sse_body(
            {'choices': [{'delta': {'content': 'answer'}, 'finish_reason': 'stop'}]},
            {'choices': [], 'usage': {'prompt_tokens': 100, 'completion_tokens': 10}}))
    done = collect(run_agent(job, client_for(handler), '00:10到00:15画面'))[-1]
    blocks = bodies[0]['messages'][1]['content']
    assert sum(b.get('type') == 'image_url' for b in blocks) == 3
    assert n_requested == [1]  # two initial frames left only one zoom slot
    assert done['budget']['frames_reserved'] == 3 and done['budget']['frames_read'] == 3


def test_remaining_seconds_interrupt_skill_await(tmp_path, monkeypatch):
    import httpx
    import time
    from modules.agent import skills
    monkeypatch.setenv('LLM_BUDGET_MAX_SECONDS', '.03')
    async def slow(*args, **kwargs):
        await asyncio.sleep(60)
        yield ('result', 'never', '', 0, {}, False)
    monkeypatch.setattr(skills, 'run', slow)
    handler = lambda r: (_ for _ in ()).throw(AssertionError('main model must not be called'))
    began = time.perf_counter()
    done = collect(run_agent(make_job(tmp_path, ['ok']), client_for(handler), '科普核查'))[-1]
    assert time.perf_counter() - began < .5
    assert done['code'] == 'budget' and done['budget']['tool_calls'] == 1


def test_run_error_keeps_model_counts(tmp_path, monkeypatch):
    import httpx
    monkeypatch.setenv('LLM_PRICE_IN_M', '2')
    monkeypatch.setenv('LLM_PRICE_OUT_M', '8')
    done = collect(run_agent(make_job(tmp_path, ['ok']), client_for(lambda r: httpx.Response(503)), 'hello'))[-1]
    assert done['type'] == 'run.error'
    assert done['budget']['llm_calls'] == done['budget']['llm_failures'] == 1
    assert done['usage']['prompt'] is None and not done['cost']['computable']


def test_finite_prices_that_overflow_still_cannot_produce_infinite_cost(monkeypatch):
    monkeypatch.setenv('LLM_PRICE_IN_M', '1e308')
    monkeypatch.setenv('LLM_PRICE_OUT_M', '1e308')
    b = AnswerBudget()
    b.llm_finished(1000, 1000)
    assert b.cost()['cny'] is None and not b.cost()['computable']


def test_exhausted_tokens_do_not_start_unmetered_intent_fallback(tmp_path, monkeypatch):
    monkeypatch.setenv('LLM_BUDGET_MAX_TOKENS', '0')
    entered = []
    async def classify(question, decider=None):
        entered.append(True)
        from modules.agent.intent import by_keywords
        return by_keywords(question)
    monkeypatch.setattr('modules.agent.run.intent.classify', classify)
    raw = types.SimpleNamespace(config=types.SimpleNamespace(model='unused'))
    done = collect(run_agent(make_job(tmp_path, ['ok']), raw, 'hello'))[-1]
    assert entered == []
    assert done['code'] == 'budget' and done['budget']['limit_hits'] == ['tokens']


def test_optional_intent_client_is_metered_once(tmp_path, monkeypatch):
    import httpx
    from modules.llm import Usage
    from modules.agent import intent
    injected = []
    async def classify(question, decider=None, *, client=None):
        injected.append(client)
        u = Usage()
        _ = [d async for d in client.stream([], u)]
        route = intent.by_keywords(question)
        route.usage = {'prompt_tokens': u.prompt_tokens, 'completion_tokens': u.completion_tokens}
        return route
    monkeypatch.setattr('modules.agent.run.intent.classify', classify)
    handler = lambda r: httpx.Response(200, text=sse_body(
        {'choices': [{'delta': {'content': 'answer'}, 'finish_reason': 'stop'}]},
        {'choices': [], 'usage': {'prompt_tokens': 50, 'completion_tokens': 5}}))
    done = collect(run_agent(make_job(tmp_path, ['ok']), client_for(handler), 'hello'))[-1]
    from modules.agent.budget import MeteredClient
    assert isinstance(injected[0], MeteredClient)
    assert done['budget']['llm_calls'] == 2 and done['usage']['prompt'] == 100
    assert done['usage']['completion'] == 10  # metadata must not add the routed stream twice


def test_optional_intent_client_preserves_partial_on_answer_deadline(tmp_path, monkeypatch):
    from modules.llm import Usage
    async def classify(question, decider=None, *, client=None):
        _ = [d async for d in client.stream([], Usage())]
        raise AssertionError('deadline must interrupt')
    monkeypatch.setattr('modules.agent.run.intent.classify', classify)
    monkeypatch.setenv('LLM_BUDGET_MAX_SECONDS', '.03')
    class Slow:
        config = types.SimpleNamespace(model='slow')
        async def stream(self, messages, usage, **kwargs):
            usage.prompt_tokens = 31
            await asyncio.sleep(60)
            yield 'never'
    done = collect(run_agent(make_job(tmp_path, ['ok']), Slow(), 'hello'))[-1]
    assert done['code'] == 'budget' and done['usage']['known_prompt'] == 31
    assert done['budget']['llm_calls'] == 1 and not done['usage']['complete']


def test_parallel_output_allowances_are_reserved_before_requests():
    from modules.agent.budget import MeteredClient, limits
    from modules.llm import Usage
    requested = []
    class Concurrent:
        async def stream(self, messages, usage, max_tokens=2048, **kwargs):
            requested.append(max_tokens)
            await asyncio.sleep(.01)
            usage.prompt_tokens, usage.completion_tokens = 0, max_tokens
            yield 'done'
    async def go():
        b = AnswerBudget(caps={**limits({}), 'tokens': 100})
        proxy = MeteredClient(Concurrent(), b)
        async def one():
            return [d async for d in proxy.stream([], Usage(), max_tokens=70)]
        await asyncio.gather(one(), one())
        assert requested == [70, 30]
        assert b.completion_tokens == 100 and b.output_reserved == 0
    asyncio.run(go())


def test_unknown_output_allowance_is_not_available_for_reuse():
    from modules.agent.budget import MeteredClient, limits, BudgetExceeded
    from modules.llm import Usage
    class Unknown:
        async def stream(self, messages, usage, **kwargs):
            yield 'no usage'
    async def go():
        b = AnswerBudget(caps={**limits({}), 'tokens': 100})
        proxy = MeteredClient(Unknown(), b)
        _ = [d async for d in proxy.stream([], Usage(), max_tokens=100)]
        assert b.unreported_token_reserve == 100 and not b.tokens_known
        with pytest.raises(BudgetExceeded) as denied:
            _ = [d async for d in proxy.stream([], Usage())]
        assert "保守预留" in denied.value.message  # unknown usage must not be called a measured total
    asyncio.run(go())


def test_exhausted_continuation_emits_budget_error(tmp_path, monkeypatch):
    import httpx
    calls = []
    monkeypatch.setenv('LLM_BUDGET_MAX_TOKENS', '100')
    def handler(r):
        calls.append(True)
        return httpx.Response(200, text=sse_body(
            {'choices': [{'delta': {'content': 'partial answer'}, 'finish_reason': 'length'}]},
            {'choices': [], 'usage': {'prompt_tokens': 90, 'completion_tokens': 10}}))
    done = collect(run_agent(make_job(tmp_path, ['ok']), client_for(handler), 'hello'))[-1]
    assert calls == [True]
    assert done['type'] == 'run.error' and done['code'] == 'budget'
    assert done['budget']['limit_hits'] == ['tokens']


@pytest.mark.parametrize('mode', ['timeout', 'cancel'])
def test_route_task_cancel_is_settled_before_its_proxy_finishes(tmp_path, monkeypatch, mode):
    from modules.llm import Usage
    from modules.agent import intent
    started = asyncio.Event()
    class Slow:
        config = types.SimpleNamespace(model='slow')
        async def stream(self, messages, usage, **kwargs):
            usage.prompt_tokens = 31
            started.set()
            await asyncio.sleep(60)
            yield 'never'
    async def classify(question, decider=None, *, client=None):
        u = Usage()
        async def ask():
            _ = [d async for d in client.stream([], u, max_tokens=8)]
        task = asyncio.create_task(ask())
        try:
            await started.wait()
            if mode == 'cancel':
                await asyncio.sleep(60)
            route = intent.by_keywords(question)
            route.usage = {'prompt_tokens': u.prompt_tokens, 'completion_tokens': u.completion_tokens}
            return route
        finally:
            task.cancel()  # deliberate A behavior: do not await potentially slow cleanup
    monkeypatch.setattr('modules.agent.run.intent.classify', classify)
    async def go():
        b = AnswerBudget()
        async def consume():
            return [e async for e in run_agent(make_job(tmp_path, ['ok']), Slow(), 'hello', budget=b)]
        task = asyncio.create_task(consume())
        await started.wait()
        if mode == 'cancel':
            task.cancel()
            with pytest.raises(asyncio.CancelledError):
                await task
        else:
            # Classifier returns with its cancelled proxy still active; next model
            # call would hang, so intercept just the terminal ledger via a small cap.
            b.caps['tokens'] = 31
            events = await task
            assert events[-1]['usage']['known_prompt'] == 31
        assert b.llm_calls == 1 and b.prompt_tokens == 31 and not b.tokens_known
    asyncio.run(go())


def test_settle_does_not_cancel_an_already_cleaning_route_again():
    from modules.agent.budget import MeteredClient
    from modules.llm import Usage
    entered, cleaning = asyncio.Event(), asyncio.Event()
    cancellations = []
    class Cleanly:
        async def stream(self, messages, usage, **kwargs):
            try:
                entered.set()
                await asyncio.sleep(60)
                yield 'never'
            finally:
                cleaning.set()
                try:
                    await asyncio.sleep(.01)
                except asyncio.CancelledError:
                    cancellations.append('cleanup cancelled twice')
                    raise
    async def go():
        b = AnswerBudget()
        async def consume():
            _ = [d async for d in MeteredClient(Cleanly(), b).stream([], Usage())]
        task = asyncio.create_task(consume())
        await entered.wait()
        task.cancel()  # same first cancellation that A issues before returning
        await cleaning.wait()
        b.settle_calls(list(b.active))
        with pytest.raises(asyncio.CancelledError):
            await task
        assert cancellations == [] and b.llm_calls == 1
    asyncio.run(go())
