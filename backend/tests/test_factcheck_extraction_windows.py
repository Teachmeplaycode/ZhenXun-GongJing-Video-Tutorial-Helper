"""Statement-level anchoring, bounded extraction and complete-channel regressions."""
import asyncio
import json
import re
from types import SimpleNamespace

import pytest

from modules.factcheck import extract, report, verify
from modules.factcheck.run import run_factcheck


def output(quote, source="transcript", index=0):
    return {"claim": "模型虚构的标准化说法", "original_text": quote, "source": source,
            "segment_index": index, "start": 0, "end": 999}


def channel(status, segments):
    return SimpleNamespace(status=status, as_dict=lambda: {"segments": segments})


def test_distinct_statements_in_one_segment_receive_distinct_queries_and_verdicts():
    statements = ["苹果含维生素 C", "苹果能治癌"]
    segment = {"start": 12.5, "end": 18, "text": "苹果含维生素 C，但是有人说苹果能治癌。"}
    job = SimpleNamespace(id="multi", transcript=channel("done", [segment]), screentext=channel("empty", []),
                          video=SimpleNamespace(public=lambda: {}))
    searched = []

    async def ask(messages, max_tokens):
        if messages[0]["content"] == extract.SYSTEM:
            return json.dumps([output(text) for text in statements] + [output("苹果不含维生素 C")])
        if messages[0]["content"] == verify.SCREEN_SYSTEM:
            return '{"safe":true}'
        proposition = json.loads(messages[1]["content"])["claim"]
        assert proposition in statements
        return json.dumps({"verdict": "correct" if proposition == statements[0] else "wrong",
                           "risk": "low", "reason": "statement-specific evidence", "source_ids": ["s1"]})

    async def search(query, limit):
        searched.append(query)
        return [report.build_source("study", "https://pubmed.ncbi.nlm.nih.gov/1", "evidence")]

    async def consume():
        return [event async for event in run_factcheck(job, None, ask=ask, search=search)]

    result = asyncio.run(consume())[-1]["report"]
    assert searched == statements
    assert [claim["claim"] for claim in result["claims"]] == statements
    assert [claim["verdict"] for claim in result["claims"]] == ["correct", "wrong"]
    assert [claim["risk"] for claim in result["claims"]] == ["low", "high"]
    assert result["summary"]["correct"] == result["summary"]["wrong"] == 1
    assert [claim["original_text"] for claim in result["claims"]] == statements
    assert all(claim["evidence"] == {"source": "transcript", "segment_index": 0} for claim in result["claims"])
    assert all(claim["timestamp"]["start"] == 12.5 and claim["timestamp"]["end"] == 18 for claim in result["claims"])


@pytest.mark.parametrize("pending_channel", ["transcript", "screentext"])
@pytest.mark.parametrize("status", ["pending", "running"])
@pytest.mark.parametrize("partial", [False, True])
def test_any_unfinished_channel_prevents_extraction_and_completion(pending_channel, status, partial):
    segments = [{"start": 1, "end": 2, "text": "苹果含维生素C"}]
    job = SimpleNamespace(id="partial", transcript=channel("done", segments), screentext=channel("done", segments),
                          video=SimpleNamespace(public=lambda: {}))
    setattr(job, pending_channel, channel(status, segments if partial else []))

    async def unexpected(*args):
        pytest.fail("Incomplete channels must be rejected before any model or search call")

    async def consume():
        return [event async for event in run_factcheck(job, None, ask=unexpected, search=unexpected)]

    result = asyncio.run(consume())
    assert [event["type"] for event in result] == ["factcheck.started", "factcheck.error"]
    assert result[-1]["code"] == "content_not_ready" and result[-1]["retryable"] is True


def test_all_bounded_batches_include_both_channel_tails_and_global_indexes(monkeypatch):
    monkeypatch.setenv("LLM_MAX_TRANSCRIPT_CHARS", "1100")
    monkeypatch.setenv("LLM_MAX_SCREEN_CHARS", "1000")
    transcript = [{"start": i * 3, "end": i * 3 + 2, "text": f"语音说法{i}。" + "甲" * 700} for i in range(6)]
    screen = [{"start": i * 4, "end": i * 4 + 3, "text": f"画面说法{i}。" + "乙" * 600} for i in range(4)]
    calls, contexts = [], []

    async def ask(messages, max_tokens):
        user = messages[1]["content"]
        calls.append(user)
        found = []
        for heading, source, prefix, budget in [("语音转写", "transcript", "语音说法", 1100),
                                                ("画面文字", "screentext", "画面说法", 1000)]:
            match = re.search(rf"【{heading}】\n(.*?)(?=\n\n【|\n\n示例输出：)", user, re.S)
            if not match:
                continue
            text = match.group(1)
            assert len(text) <= budget
            for line in text.splitlines():
                index = int(re.match(r"\[(\d+) ", line)[1])
                assert f"{prefix}{index}。" in line
                contexts.append((source, index))
                found.append(output(f"{prefix}{index}", source, index))
        return json.dumps(found)

    claims = asyncio.run(extract.extract_claims(ask, transcript, screen))
    assert len(calls) == 6
    assert set(contexts) == {("transcript", i) for i in range(6)} | {("screentext", i) for i in range(4)}
    assert len(claims) == 10
    assert ("transcript", 5) in {(c["source"], c["segment_index"]) for c in claims}
    assert ("screentext", 3) in {(c["source"], c["segment_index"]) for c in claims}
    for c in claims:
        segment = (transcript if c["source"] == "transcript" else screen)[c["segment_index"]]
        assert c["original_text"] in segment["text"]
        assert (c["start"], c["end"]) == (segment["start"], segment["end"])


def test_oversized_single_segment_keeps_tail_and_deduplicates_overlap(monkeypatch):
    monkeypatch.setenv("LLM_MAX_TRANSCRIPT_CHARS", "1000")
    text = "首部说法。" + "甲" * 900 + "重叠说法" + "乙" * 1800 + "尾部说法。"
    transcript = [{"start": 0, "end": 1, "text": ""}, {"start": 1, "end": 2, "text": ""},
                  {"start": 50, "end": 80, "text": text}]
    requested_quotes, calls = [], []

    async def ask(messages, max_tokens):
        body = messages[1]["content"].split("【语音转写】\n")[1].split("\n\n示例输出：")[0]
        assert len(body) <= 1000
        assert body.startswith("[02 50.0-80.0]")
        calls.append(body)
        quotes = [quote for quote in ("首部说法", "重叠说法", "尾部说法") if quote in body]
        requested_quotes.extend(quotes)
        return json.dumps([output(quote, index=2) for quote in quotes])

    claims = asyncio.run(extract.extract_claims(ask, transcript, []))
    assert len(calls) > 1 and requested_quotes.count("重叠说法") > 1
    assert [c["claim"] for c in claims] == ["首部说法", "重叠说法", "尾部说法"]
    assert all(c["segment_index"] == 2 and (c["start"], c["end"]) == (50, 80) for c in claims)


def test_a_valid_quote_from_a_different_window_cannot_be_cited(monkeypatch):
    monkeypatch.setenv("LLM_MAX_TRANSCRIPT_CHARS", "1000")
    transcript = [{"start": 1, "end": 2, "text": "首段原文" + "甲" * 700},
                  {"start": 5, "end": 6, "text": "尾段原文" + "乙" * 700}]
    calls = []

    async def ask(messages, max_tokens):
        calls.append(messages)
        return json.dumps([output("尾段原文", index=1)]) if len(calls) == 1 else "[]"

    assert asyncio.run(extract.extract_claims(ask, transcript, [])) == []
    assert len(calls) == 2


def test_whole_quote_is_validated_before_display_truncation():
    real = "甲" * 400
    transcript = [{"start": 1, "end": 2, "text": real}]

    async def ask(*args):
        return json.dumps([output(real + "视频没有的内容"), output(real)])

    claims = asyncio.run(extract.extract_claims(ask, transcript, []))
    assert len(claims) == 1
    assert claims[0]["claim"] == claims[0]["original_text"] == real


def test_a_reply_cut_off_at_the_output_limit_keeps_its_complete_claims():
    cut = '[{"claim": "a", "original_text": "甲"}, {"claim": "b", "original_text": "乙"}, {"claim": "c", "orig'
    assert [i["claim"] for i in extract._parse(cut)] == ["a", "b"]
    assert extract._parse("没有说法") == [] and extract._parse("[") == []


def test_a_quote_may_run_across_short_speech_segments_and_differ_in_punctuation():
    transcript = [{"start": 70, "end": 72, "text": "结果微生物的含量"}, {"start": 72, "end": 75, "text": "加热和没加热的,相差很大"},
                  {"start": 75, "end": 80, "text": "下一句"}]

    async def ask(*args):
        return json.dumps([output("结果微生物的含量，加热和没加热的相差很大。", index=0),
                           output("加热和没加热的相差很大", index=0),        # begins in a later segment than it cites
                           output("结果微生物的含量加热和没加热的相差不大", index=0)])  # not what was said

    claims = asyncio.run(extract.extract_claims(ask, transcript, []))
    assert len(claims) == 1
    assert claims[0]["claim"] == "结果微生物的含量加热和没加热的,相差很大"  # the video's own text
    assert (claims[0]["start"], claims[0]["end"]) == (70, 75)
