from __future__ import annotations

import asyncio
import re
from dataclasses import dataclass

import httpx


@dataclass
class SemanticHit:
    name: str
    niche: str
    key: str | None = None
    source: str = "semantic:en"
    meaning: str = ""


class SemanticWordProvider:
    """Runtime semantic expansion for real English words.

    This provider is deliberately optional: search keeps working from bundled data and
    taxonomy when the remote semantic service is unavailable. Returned multi-word,
    punctuated and synthetic-looking tokens are discarded before scoring.
    """

    BASE = "https://api.datamuse.com/words"

    def __init__(self, timeout: float = 8.0, concurrency: int = 4):
        self.timeout = timeout
        self.semaphore = asyncio.Semaphore(max(1, concurrency))

    @staticmethod
    def _topic_text(label: str, description: str = "") -> str:
        label = re.sub(r"[^A-Za-z ]+", " ", label).strip().lower()
        description = re.sub(r"[^A-Za-z ]+", " ", description).strip().lower()
        # The label is the strongest signal. A short description adds context without
        # turning the request into a long natural-language prompt.
        words = (label + " " + description).split()
        stop = {"and", "or", "the", "of", "with", "small", "large", "true", "family", "genera"}
        compact = [w for w in words if w not in stop]
        return " ".join(compact[:8]) or label

    async def related_words(self, label: str, description: str = "", limit: int = 120) -> list[SemanticHit]:
        if limit <= 0:
            return []
        topic = self._topic_text(label, description)
        params = {"ml": topic, "max": min(200, max(20, limit))}
        headers = {"User-Agent": "Mianem/1.8 semantic naming research"}
        async with self.semaphore:
            async with httpx.AsyncClient(timeout=self.timeout, headers=headers, follow_redirects=True) as client:
                response = await client.get(self.BASE, params=params)
                response.raise_for_status()
                payload = response.json()

        hits: list[SemanticHit] = []
        seen: set[str] = set()
        for item in payload if isinstance(payload, list) else []:
            word = str(item.get("word") or "").strip().lower()
            # Mianem's primary search is intentionally one-token and ASCII for .com.
            if not re.fullmatch(r"[a-z]+", word) or word in seen:
                continue
            seen.add(word)
            hits.append(SemanticHit(
                name=word,
                niche=f"English · {label}",
                key=topic,
                source="semantic:en",
                meaning=f"related to {label}",
            ))
            if len(hits) >= limit:
                break
        return hits
