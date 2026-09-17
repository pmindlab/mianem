from __future__ import annotations

import asyncio
from collections import Counter, defaultdict, deque

from .models import Candidate
from .providers import LanguageHit, SemanticHit, SemanticWordProvider
from .scoring import score_name, valid_candidate
from .service_v174 import DeepNameLabService


class SearchV2Service(DeepNameLabService):
    """Multi-source naming search inspired by mature large-pool naming workflows.

    Search v2 keeps Mianem's core invariants: real/attested words are preferred, quality
    thresholds are not lowered just to fill the screen, and only a live-available .com
    may be returned as an available result.
    """

    def __init__(self):
        super().__init__()
        self.semantic = SemanticWordProvider(self.gbif.timeout, concurrency=4)

    @staticmethod
    def _mode(value: str | None) -> str:
        return value if value in {"fast", "balanced", "deep"} else "balanced"

    async def _score_discovered(
        self,
        discovered,
        *,
        min_len: int,
        max_len: int,
        min_score: float,
        known_names: set[str],
    ) -> tuple[list[Candidate], int]:
        scored: list[Candidate] = []
        known_skipped = 0
        for hit in discovered:
            name = hit.name.strip().lower()
            if name in known_names:
                known_skipped += 1
                continue
            if not valid_candidate(name, min_len, max_len):
                continue
            score, components, reasons = score_name(name, hit.niche, self.profile)

            source = str(getattr(hit, "source", "") or "")
            if source == "gbif:genus":
                reasons.insert(0, "real taxonomic genus")
            elif source == "gbif:epithet":
                reasons.insert(0, "real species epithet")
            elif source.startswith("semantic:"):
                meaning = str(getattr(hit, "meaning", "") or "").strip()
                reasons.insert(0, f"real semantic word · {meaning}" if meaning else "real semantic word")
            elif isinstance(hit, LanguageHit):
                detail = f"real word · {hit.niche}"
                if hit.meaning:
                    detail += f" · {hit.meaning}"
                reasons.insert(0, detail)
                if hit.key:
                    reasons.insert(1, f"original spelling: {hit.key}")

            if score < min_score:
                continue
            scored.append(Candidate(
                name=name.capitalize(),
                domain=f"{name}.com",
                niche=hit.niche,
                source=source or "discovery",
                taxon_key=getattr(hit, "key", None),
                score=score,
                components=components,
                reasons=reasons,
                acquisition_mode="available_now",
            ))
        scored.sort(key=lambda c: c.score, reverse=True)
        return scored, known_skipped

    async def _discover_species_epithets(self, selected_keys: list[str], per_niche: int) -> tuple[list, list[str]]:
        defs = [self.catalog.get(key) for key in selected_keys]
        defs = [n for n in defs if n is not None]
        if not defs or per_niche <= 0:
            return [], []

        semaphore = asyncio.Semaphore(4)

        async def one(niche):
            async with semaphore:
                try:
                    return await self.gbif.species_epithets_for_niche(niche.taxon, niche.label, per_niche), None
                except Exception as exc:
                    return [], f"GBIF species {niche.key}: {type(exc).__name__}"

        rows = await asyncio.gather(*(one(n) for n in defs))
        hits: list = []
        warnings: list[str] = []
        for batch, warning in rows:
            hits.extend(batch)
            if warning:
                warnings.append(warning)
        return hits, warnings

    async def _discover_semantic_english(self, selected_keys: list[str], per_niche: int) -> tuple[list[SemanticHit], list[str]]:
        defs = [self.catalog.get(key) for key in selected_keys]
        defs = [n for n in defs if n is not None]
        if not defs or per_niche <= 0:
            return [], []

        async def one(niche):
            try:
                return await self.semantic.related_words(niche.label, niche.description, per_niche), None
            except Exception as exc:
                return [], f"Semantic EN {niche.key}: {type(exc).__name__}"

        rows = await asyncio.gather(*(one(n) for n in defs))
        hits: list[SemanticHit] = []
        warnings: list[str] = []
        for batch, warning in rows:
            hits.extend(batch)
            if warning:
                warnings.append(warning)
        return hits, warnings

    async def discover_v2(
        self,
        selected_keys: list[str],
        per_niche: int,
        language_keys: list[str],
        search_mode: str,
    ) -> tuple[list, list[str], dict[str, int]]:
        mode = self._mode(search_mode)
        base_hits, warnings = await self.discover(selected_keys, per_niche, language_keys)
        hits = list(base_hits)

        # Bound extra work globally, so selecting many areas cannot explode into tens of
        # thousands of remote requests. Deep mode spends its budget across all areas.
        niche_count = max(1, len([k for k in selected_keys if self.catalog.get(k)]))
        if mode == "fast":
            epithet_each = 0
            semantic_each = 0
        elif mode == "balanced":
            epithet_each = min(180, max(60, 1200 // niche_count))
            semantic_each = min(50, max(20, 400 // niche_count)) if "en" in language_keys else 0
        else:
            epithet_each = min(420, max(100, 2600 // niche_count))
            semantic_each = min(100, max(30, 800 // niche_count)) if "en" in language_keys else 0

        extra_taxa, taxa_warnings = await self._discover_species_epithets(selected_keys, epithet_each)
        hits.extend(extra_taxa)
        warnings.extend(taxa_warnings)

        semantic_hits, semantic_warnings = await self._discover_semantic_english(selected_keys, semantic_each)
        hits.extend(semantic_hits)
        warnings.extend(semantic_warnings)

        # Preserve the highest-authority source when the same token appears more than once:
        # bundled/curated and genus hits arrive before species epithets and remote semantics.
        dedup: dict[str, object] = {}
        for hit in hits:
            dedup.setdefault(hit.name.lower(), hit)
        hits = list(dedup.values())
        source_counts = dict(Counter(str(getattr(h, "source", "discovery") or "discovery") for h in hits))
        return hits, warnings, source_counts

    @staticmethod
    def _check_order(scored: list[Candidate]) -> list[Candidate]:
        """Keep the very best names first, then diversify across source + niche buckets."""
        if len(scored) <= 30:
            return list(scored)
        head_count = min(80, max(30, len(scored) // 5))
        head = list(scored[:head_count])
        rest = scored[head_count:]
        buckets: dict[tuple[str, str], deque[Candidate]] = defaultdict(deque)
        for candidate in rest:
            source_family = candidate.source.split(":", 1)[0]
            buckets[(source_family, candidate.niche)].append(candidate)

        ordered = list(head)
        while buckets:
            active = sorted(
                buckets,
                key=lambda key: buckets[key][0].score if buckets[key] else -1,
                reverse=True,
            )
            for key in active:
                bucket = buckets.get(key)
                if not bucket:
                    buckets.pop(key, None)
                    continue
                ordered.append(bucket.popleft())
                if not bucket:
                    buckets.pop(key, None)
        return ordered

    async def run_search(
        self,
        selected_keys: list[str],
        min_len: int = 5,
        max_len: int = 9,
        per_niche: int = 120,
        domain_checks: int = 50,
        brand_checks: int = 12,
        min_score: float = 55.0,
        language_keys: list[str] | None = None,
        search_mode: str = "balanced",
    ) -> dict:
        self._refresh_profile()
        language_keys = language_keys or []
        mode = self._mode(search_mode)
        known_names = self._known_names()

        discovered, warnings, source_counts = await self.discover_v2(
            selected_keys, per_niche, language_keys, mode
        )
        scored, known_skipped = await self._score_discovered(
            discovered,
            min_len=min_len,
            max_len=max_len,
            min_score=min_score,
            known_names=known_names,
        )
        check_order = self._check_order(scored)

        batch_size = max(1, domain_checks)
        if mode == "fast":
            cap = 120
            target_available = 12
        elif mode == "balanced":
            cap = 320
            target_available = 24
        else:
            cap = 640
            target_available = 40
        max_checks = min(len(check_order), max(batch_size, cap))

        checked: list[Candidate] = []
        available: list[Candidate] = []
        cursor = 0
        rate_limited_batches = 0
        while cursor < max_checks and (cursor == 0 or len(available) < target_available):
            batch = check_order[cursor:min(cursor + batch_size, max_checks)]
            if not batch:
                break
            domain_results = await self.domain.check_many([c.domain for c in batch])
            unknown = 0
            for candidate in batch:
                result = domain_results.get(candidate.domain.lower())
                candidate.domain_status = result.status if result else "unknown"
                if candidate.domain_status == "unknown":
                    unknown += 1
            checked.extend(batch)
            available.extend(c for c in batch if c.domain_status == "available")
            cursor += len(batch)

            if unknown > len(batch) / 2:
                rate_limited_batches += 1
                if rate_limited_batches >= 2:
                    warnings.append("Live .com returned too many unknown results; deep checking stopped to avoid hammering RDAP.")
                    break
            else:
                rate_limited_batches = 0

        available = await self._screen_available(available, brand_checks)
        return {
            "candidates": [self._with_links(c) for c in available],
            "stats": {
                "discovered": len(discovered),
                "after_brand_filter": len(scored),
                "domain_checked": len(checked),
                "available": len(available),
                "brand_checked": min(len(available), max(0, brand_checks)),
                "known_skipped": known_skipped,
                "search_mode": mode,
                "source_counts": source_counts,
            },
            "warnings": list(dict.fromkeys(warnings)),
            "search_note": (
                "Search v2 builds a larger multi-source pool first (genera, real species epithets, "
                "bundled language words and optional semantic English), ranks it, then checks live .com "
                "progressively until the requested result yield is reached or the safe check budget is exhausted."
            ),
            "availability_note": (
                "Tylko .com dostępne teraz. Domeny z aktywnym rekordem RDAP "
                "(aukcja, broker, wygasająca/pending-delete, aftermarket) są odrzucane."
            ),
        }
