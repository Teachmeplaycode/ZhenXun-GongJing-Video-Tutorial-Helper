"""话术规则库：从 rules.json 加载规则，对一段文字逐条匹配，返回命中的规则与证据片段。

规则库是纯数据（rules.json），可由人工扩充而无需改代码。匹配用正则（re.search, IGNORECASE），
对每段带时间点的文字（转写 Segment 或画面 Caption）独立匹配，命中即记录规则、片段与时间点。
"""
from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from pathlib import Path

RULES_FILE = Path(__file__).parent / "rules.json"


@dataclass
class Rule:
    id: str
    category: str
    name: str
    patterns: list[re.Pattern]
    weight: int
    description: str

    @classmethod
    def from_dict(cls, data: dict) -> "Rule":
        compiled = [re.compile(p, re.IGNORECASE) for p in data.get("patterns", [])]
        return cls(
            id=data["id"],
            category=data.get("category", ""),
            name=data.get("name", data["id"]),
            patterns=compiled,
            weight=int(data.get("weight", 1)),
            description=data.get("description", ""),
        )

    def match(self, text: str) -> list[str]:
        """Return the distinct text snippets of this rule matched in `text` (empty if none)."""
        hits: list[str] = []
        seen: set[str] = set()
        for pat in self.patterns:
            for m in pat.finditer(text):
                snippet = m.group(0)
                if snippet not in seen:
                    seen.add(snippet)
                    hits.append(snippet)
        return hits


@dataclass
class RuleHit:
    """One rule matched in one timed text segment — the atomic unit of evidence."""
    rule_id: str
    category: str
    name: str
    weight: int
    snippet: str           # the matched phrase
    text: str              # the full segment text that contained it
    start: float           # segment start time (seconds)
    end: float             # segment end time (seconds)
    source: str            # "transcript" | "screentext"
    description: str = ""    # rule description for human review

    def as_dict(self) -> dict:
        return {
            "rule_id": self.rule_id,
            "category": self.category,
            "name": self.name,
            "weight": self.weight,
            "snippet": self.snippet,
            "description": self.description,
            "text": self.text,
            "start": round(self.start, 2),
            "end": round(self.end, 2),
            "source": self.source,
        }


@dataclass
class RuleLibrary:
    rules: list[Rule]
    scoring: dict = field(default_factory=dict)
    version: int = 1

    @classmethod
    def load(cls, path: Path | str = RULES_FILE) -> "RuleLibrary":
        data = json.loads(Path(path).read_text(encoding="utf-8"))
        rules = [Rule.from_dict(r) for r in data.get("rules", [])]
        return cls(rules=rules, scoring=data.get("scoring", {}), version=int(data.get("version", 1)))

    def scan_text(self, text: str, start: float, end: float, source: str) -> list[RuleHit]:
        """Match every rule against one timed text segment; return all hits (possibly empty)."""
        if not text or not text.strip():
            return []
        hits: list[RuleHit] = []
        for rule in self.rules:
            for snippet in rule.match(text):
                hits.append(RuleHit(
                    rule_id=rule.id, category=rule.category, name=rule.name,
                    weight=rule.weight, snippet=snippet, text=text,
                    start=start, end=end, source=source, description=rule.description,
                ))
        return hits

    def scan_segments(self, segments: list[tuple[float, float, str]], source: str) -> list[RuleHit]:
        """Scan many timed segments at once. `segments` is (start, end, text) triples."""
        hits: list[RuleHit] = []
        for start, end, text in segments:
            hits.extend(self.scan_text(text, start, end, source))
        return hits

    def categories_hit(self, hits: list[RuleHit]) -> list[str]:
        """Distinct categories in the order they were first hit."""
        seen: set[str] = set()
        out: list[str] = []
        for h in hits:
            if h.category not in seen:
                seen.add(h.category)
                out.append(h.category)
        return out
