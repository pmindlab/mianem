from __future__ import annotations

import asyncio
import math
import random
import re
from dataclasses import dataclass
from typing import Any
import httpx


@dataclass
class TaxonHit:
    name: str
    niche: str
    key: str | None = None
    source: str = "gbif"


class GBIFProvider:
    BASE = "https://api.gbif.org/v1"

    def __init__(self, timeout: float = 8.0):
        self.timeout = timeout

    async def _get(self, client: httpx.AsyncClient, path: str, params: dict[str, Any]) -> dict:
        r = await client.get(f"{self.BASE}{path}", params=params)
        r.raise_for_status()
        return r.json()

    async def match_taxon(self, taxon_name: str) -> dict:
        headers = {"User-Agent": "Mianem/1.8 taxonomy research"}
        async with httpx.AsyncClient(timeout=self.timeout, headers=headers, follow_redirects=True) as client:
            data = await self._get(client, "/species/match", {"name": taxon_name})
        key = data.get("usageKey") or data.get("nubKey") or data.get("key")
        return {
            "key": int(key) if key else None,
            "scientific_name": data.get("scientificName") or data.get("canonicalName") or taxon_name,
            "canonical_name": data.get("canonicalName") or taxon_name,
            "rank": data.get("rank"),
            "status": data.get("status"),
            "match_type": data.get("matchType"),
            "confidence": data.get("confidence"),
        }

    async def resolve_taxon(self, client: httpx.AsyncClient, taxon_name: str) -> int | None:
        data = await self._get(client, "/species/match", {"name": taxon_name})
        for key_name in ("usageKey", "nubKey", "key"):
            val = data.get(key_name)
            if val:
                try:
                    return int(val)
                except Exception:
                    pass
        return None

    @staticmethod
    def _page_offsets(count: int, page_size: int, pages: int, seed: str) -> list[int]:
        """Deterministically sample the whole result set, not only alphabetic head pages."""
        if count <= page_size or pages <= 1:
            return [0]
        max_offset = max(0, count - page_size)
        wanted = min(pages, max(1, math.ceil(count / page_size)))
        offsets = {0}
        if wanted > 1:
            # Even coverage is the baseline; deterministic jitter avoids repeatedly landing
            # on the same taxonomic boundaries for different page sizes.
            rng = random.Random(seed)
            for i in range(1, wanted):
                fraction = i / max(1, wanted - 1)
                base = int(round(max_offset * fraction))
                jitter = rng.randint(-page_size // 5, page_size // 5) if page_size >= 10 else 0
                offsets.add(max(0, min(max_offset, base + jitter)))
        return sorted(offsets)

    async def genera_for_niche(self, taxon_name: str, label: str, limit: int = 120) -> list[TaxonHit]:
        headers = {"User-Agent": "Mianem/1.8 taxonomy research"}
        async with httpx.AsyncClient(timeout=self.timeout, headers=headers, follow_redirects=True) as client:
            key = await self.resolve_taxon(client, taxon_name)
            if not key:
                return []

            first = await self._get(client, "/species/search", {
                "highertaxon_key": key,
                "rank": "GENUS",
                "status": "ACCEPTED",
                "limit": min(100, max(20, limit)),
                "offset": 0,
            })
            results = list(first.get("results", []))
            count = int(first.get("count", len(results)) or len(results))

            page_size = min(100, max(20, limit))
            pages_needed = max(1, min(6, math.ceil(max(1, limit) / page_size)))
            offsets = [o for o in self._page_offsets(count, page_size, pages_needed, f"genus:{taxon_name}:{limit}") if o]
            if offsets:
                tasks = [
                    self._get(client, "/species/search", {
                        "highertaxon_key": key,
                        "rank": "GENUS",
                        "status": "ACCEPTED",
                        "limit": page_size,
                        "offset": off,
                    }) for off in offsets
                ]
                pages = await asyncio.gather(*tasks, return_exceptions=True)
                for page in pages:
                    if isinstance(page, dict):
                        results.extend(page.get("results", []))

        seen: set[str] = set()
        hits: list[TaxonHit] = []
        for item in results:
            raw = item.get("canonicalName") or item.get("scientificName") or ""
            genus = str(item.get("genericName") or (raw.split()[0] if raw else "")).strip()
            if not genus or genus.lower() in seen:
                continue
            seen.add(genus.lower())
            hits.append(TaxonHit(name=genus, niche=label, key=str(item.get("key") or "") or None, source="gbif:genus"))
            if len(hits) >= limit:
                break
        return hits

    async def species_epithets_for_niche(self, taxon_name: str, label: str, limit: int = 500) -> list[TaxonHit]:
        """Return real specific epithets from accepted species across the selected taxon.

        These are not synthetic blends: every candidate is an attested component of an
        accepted scientific species name. Pages are sampled across the full GBIF result
        set so deep search does not repeatedly inspect only the first alphabetic slice.
        """
        if limit <= 0:
            return []
        headers = {"User-Agent": "Mianem/1.8 taxonomy research"}
        page_size = 100
        async with httpx.AsyncClient(timeout=self.timeout, headers=headers, follow_redirects=True) as client:
            key = await self.resolve_taxon(client, taxon_name)
            if not key:
                return []
            first = await self._get(client, "/species/search", {
                "highertaxon_key": key,
                "rank": "SPECIES",
                "status": "ACCEPTED",
                "limit": page_size,
                "offset": 0,
            })
            count = int(first.get("count", len(first.get("results", []))) or 0)
            results = list(first.get("results", []))
            pages = max(1, min(10, math.ceil(max(1, limit) / page_size)))
            offsets = [o for o in self._page_offsets(count, page_size, pages, f"species:{taxon_name}:{limit}") if o]
            if offsets:
                tasks = [
                    self._get(client, "/species/search", {
                        "highertaxon_key": key,
                        "rank": "SPECIES",
                        "status": "ACCEPTED",
                        "limit": page_size,
                        "offset": off,
                    }) for off in offsets
                ]
                fetched = await asyncio.gather(*tasks, return_exceptions=True)
                for page in fetched:
                    if isinstance(page, dict):
                        results.extend(page.get("results", []))

        seen: set[str] = set()
        hits: list[TaxonHit] = []
        for item in results:
            epithet = str(item.get("specificEpithet") or "").strip().lower()
            if not epithet:
                canonical = str(item.get("canonicalName") or "").strip()
                parts = canonical.split()
                epithet = parts[1].lower() if len(parts) >= 2 else ""
            # Keep only single Latin-alphabet tokens here. The normal candidate gate
            # applies length/negative-meaning rules later.
            if not re.fullmatch(r"[a-z]+", epithet) or epithet in seen:
                continue
            seen.add(epithet)
            hits.append(TaxonHit(
                name=epithet,
                niche=label,
                key=str(item.get("key") or "") or None,
                source="gbif:epithet",
            ))
            if len(hits) >= limit:
                break
        return hits
