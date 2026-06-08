"""Use Claude API to summarize updates and classify by visa category."""
import logging
import os
from dataclasses import dataclass, field

import anthropic

logger = logging.getLogger(__name__)

VISA_CATEGORIES = [
    "F1 Students",
    "STEM OPT",
    "EB2 NIW",
    "O1 Visa",
    "Nigerian Nationals",
]

SYSTEM_PROMPT = """\
You are an expert US immigration analyst. Given a government update, you:
1. Write a 2–4 sentence plain-English summary (no jargon).
2. Rate impact (High / Medium / Low / None) for each visa category.
3. Output ONLY valid JSON — no markdown fences, no extra text.

Output schema:
{
  "summary": "...",
  "impact": {
    "F1 Students": "High|Medium|Low|None",
    "STEM OPT": "High|Medium|Low|None",
    "EB2 NIW": "High|Medium|Low|None",
    "O1 Visa": "High|Medium|Low|None",
    "Nigerian Nationals": "High|Medium|Low|None"
  },
  "action_required": true|false,
  "keywords": ["keyword1", "keyword2"]
}
"""


@dataclass
class ClassifiedItem:
    source: str
    url: str
    title: str
    summary: str
    impact: dict[str, str] = field(default_factory=dict)
    action_required: bool = False
    keywords: list[str] = field(default_factory=list)

    @property
    def max_impact(self) -> str:
        order = {"High": 3, "Medium": 2, "Low": 1, "None": 0}
        return max(self.impact.values(), key=lambda v: order.get(v, 0), default="None")

    @property
    def affected_categories(self) -> list[str]:
        return [k for k, v in self.impact.items() if v in ("High", "Medium")]


def classify_item(client: anthropic.Anthropic, source: str, url: str, title: str, content: str) -> ClassifiedItem | None:
    prompt = f"Source: {source}\nTitle: {title}\nURL: {url}\n\nContent:\n{content[:3000]}"
    try:
        msg = client.messages.create(
            model="claude-opus-4-8",
            max_tokens=600,
            system=SYSTEM_PROMPT,
            messages=[{"role": "user", "content": prompt}],
        )
        import json
        data = json.loads(msg.content[0].text)
        return ClassifiedItem(
            source=source,
            url=url,
            title=title,
            summary=data.get("summary", ""),
            impact=data.get("impact", {}),
            action_required=data.get("action_required", False),
            keywords=data.get("keywords", []),
        )
    except Exception as exc:
        logger.error("Classification failed for '%s': %s", title, exc)
        return None


def classify_all(items: list[dict]) -> list[ClassifiedItem]:
    api_key = os.environ.get("ANTHROPIC_API_KEY")
    if not api_key:
        raise RuntimeError("ANTHROPIC_API_KEY not set")
    client = anthropic.Anthropic(api_key=api_key)

    classified: list[ClassifiedItem] = []
    for item in items:
        result = classify_item(
            client,
            source=item["source"],
            url=item["url"],
            title=item["title"],
            content=item["content"],
        )
        if result:
            classified.append(result)
    return classified
