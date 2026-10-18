"""引流信息提取：从转写和画面文字里抓微信号、手机号、网址；二维码在 qrcode.py 单独解码。

每个提取器返回纯字符串列表；extract_from_segment 包装成带时间点和来源的 DrainageSignal，
供风险评分和报告使用。提取器针对中文诈骗话术的常见写法做了边界处理，尽量降低误报。
"""
from __future__ import annotations

import re
from dataclasses import dataclass

# 微信号：字母开头，6-20 位字母/数字/下划线（微信官方规则）。前缀引导，避免把任意英文词误判。
WECHAT_PREFIX = re.compile(
    r"(?:加(?:我)?(?:微信|v|x|vx|VX|Vx)|微?信(?:号)?|VX|vx|Vx|v/x|x/v|威信|薇信)"
    r"\s*[:：是]?\s*([A-Za-z][A-Za-z0-9_]{5,19})(?![A-Za-z0-9_])",
    re.IGNORECASE,
)
# "微信号:abc123" 里冒号后可能跟空格；也匹配 "加v abc1234"
WECHAT_LOOSE = re.compile(
    r"(?:加\s*v\s*|加\s*x\s*|v\s*[:：]\s*|x\s*[:：]\s*)([A-Za-z][A-Za-z0-9_]{5,19})(?![A-Za-z0-9_])",
    re.IGNORECASE,
)

# 手机号：1 + [3-9] + 9 位数字，允许中间有空格/横线（转写常见），再用边界避免匹配更长数字串。
PHONE = re.compile(r"(?<!\d)1[3-9]\d[\s-]?\d{4}[\s-]?\d{4}(?!\d)")
# 400 / 固话也常见于引流，但风险低于手机号，单独标记
PHONE_400 = re.compile(r"(?<!\d)400[\s-]?\d{3}[\s-]?\d{4}(?!\d)")

# 网址：完整 http(s) 链接
URL = re.compile(r"https?://[A-Za-z0-9.\-]+(/[^\s，。、；）)]*)?")
# 短链/裸域名（t.cn、bit.ly、dwz.cn、url.cn 等已知短链服务）
SHORT_DOMAINS = r"(?:t\.cn|bit\.ly|dwz\.cn|url\.cn|tinyurl\.com|suo\.im|qr\.topscan\.com)"
SHORT_URL = re.compile(rf"{SHORT_DOMAINS}/[A-Za-z0-9]+")
# 中文"网址/链接"前缀后跟的域名
URL_PREFIX = re.compile(r"(?:网址|链接|地址|点?击|访问)\s*[:：]?\s*([A-Za-z0-9.\-]+\.[A-Za-z]{2,}(/[^\s，。、；）)]*)?)")

# 清洗手机号里的空格和横线
def _clean_phone(s: str) -> str:
    return re.sub(r"[\s-]", "", s)


@dataclass
class DrainageSignal:
    kind: str           # "wechat_id" | "phone" | "phone_400" | "url" | "short_url"
    value: str          # cleaned value
    raw: str            # as it appeared in text
    start: float        # segment start (seconds)
    end: float          # segment end (seconds)
    source: str         # "transcript" | "screentext" | "qrcode"
    context: str        # the segment text, for human review

    def as_dict(self) -> dict:
        return {
            "kind": self.kind,
            "value": self.value,
            "raw": self.raw,
            "start": round(self.start, 2),
            "end": round(self.end, 2),
            "source": self.source,
            "context": self.context,
        }


def extract_wechat_ids(text: str) -> list[str]:
    """WeChat IDs introduced by a prefix like '加微信 abc123' or 'VX: xyz789'.

    Returns deduplicated IDs in order of first appearance. A bare English word with no
    prefix is NOT matched — that would misread ordinary words as WeChat IDs.
    """
    found: list[str] = []
    seen: set[str] = set()
    for pat in (WECHAT_PREFIX, WECHAT_LOOSE):
        for m in pat.finditer(text):
            wid = m.group(1)
            if wid not in seen:
                seen.add(wid)
                found.append(wid)
    return found


def extract_phones(text: str) -> list[tuple[str, str]]:
    """Mobile numbers (1[3-9]xxxxxxxxx) and 400 numbers. Returns (kind, cleaned) pairs."""
    out: list[tuple[str, str]] = []
    seen: set[tuple[str, str]] = set()
    for m in PHONE.finditer(text):
        cleaned = _clean_phone(m.group(0))
        key = ("phone", cleaned)
        if key not in seen:
            seen.add(key)
            out.append(key)
    for m in PHONE_400.finditer(text):
        cleaned = _clean_phone(m.group(0))
        key = ("phone_400", cleaned)
        if key not in seen:
            seen.add(key)
            out.append(key)
    return out


def extract_urls(text: str) -> list[tuple[str, str]]:
    """Full http(s) URLs and short-link domains. Returns (kind, url) pairs."""
    out: list[tuple[str, str]] = []
    seen: set[str] = set()
    full_urls = list(URL.finditer(text))
    for m in full_urls:
        u = m.group(0).rstrip(".,;:)")
        if u not in seen:
            seen.add(u)
            out.append(("url", u))
    for m in SHORT_URL.finditer(text):
        if any(full.start() <= m.start() and m.end() <= full.end() for full in full_urls):
            continue
        u = m.group(0)
        if u not in seen:
            seen.add(u)
            out.append(("short_url", u))
    for m in URL_PREFIX.finditer(text):
        u = m.group(1).rstrip(".,;:)")
        if u not in seen:
            seen.add(u)
            out.append(("url", u))
    return out


def extract_from_segment(text: str, start: float, end: float, source: str) -> list[DrainageSignal]:
    """All drainage signals in one timed text segment."""
    if not text or not text.strip():
        return []
    signals: list[DrainageSignal] = []
    for wid in extract_wechat_ids(text):
        signals.append(DrainageSignal("wechat_id", wid, wid, start, end, source, text))
    for kind, value in extract_phones(text):
        signals.append(DrainageSignal(kind, value, value, start, end, source, text))
    for kind, value in extract_urls(text):
        signals.append(DrainageSignal(kind, value, value, start, end, source, text))
    return signals


def extract_from_segments(segments: list[tuple[float, float, str]], source: str) -> list[DrainageSignal]:
    """Drainage signals across many timed segments."""
    out: list[DrainageSignal] = []
    for start, end, text in segments:
        out.extend(extract_from_segment(text, start, end, source))
    return out


def dedupe(signals: list[DrainageSignal]) -> list[DrainageSignal]:
    """Drop later signals with the same (kind, value), keeping the earliest time point."""
    seen: set[tuple[str, str]] = set()
    out: list[DrainageSignal] = []
    for s in sorted(signals, key=lambda item: item.start):
        key = (s.kind, s.value)
        if key not in seen:
            seen.add(key)
            out.append(s)
    return out
