from __future__ import annotations

from .models import Candidate
from .providers import LanguageHit
from .scoring import score_name, valid_candidate
from .service import NameLabService


class DeepNameLabService(NameLabService):
    """v1.7.4 adaptive search depth without weakening quality or availability rules."""

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
            if isinstance(hit, LanguageHit):
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
                source=hit.source,
                taxon_key=hit.key,
                score=score,
                components=components,
                reasons=reasons,
                acquisition_mode="available_now",
            ))
        scored.sort(key=lambda c: c.score, reverse=True)
        return scored, known_skipped

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
    ) -> dict:
        self._refresh_profile()
        language_keys = language_keys or []
        known_names = self._known_names()

        discovered, warnings = await self.discover(selected_keys, per_niche, language_keys)
        scored, known_skipped = await self._score_discovered(
            discovered,
            min_len=min_len,
            max_len=max_len,
            min_score=min_score,
            known_names=known_names,
        )

        initial_discovered = len(discovered)
        initial_scored = len(scored)
        deepened = False

        # If the initial source pool is thin, broaden the same trusted sources before
        # weakening any quality threshold. This mirrors the large-pool-first approach
        # used by mature naming tools while preserving Mianem's real-word/taxa bias.
        desired_scored_pool = max(80, max(1, domain_checks) * 2)
        if len(scored) < desired_scored_pool:
            deep_limit = min(400, max(per_niche * 3, 240))
            if deep_limit > per_niche:
                deeper, deeper_warnings = await self.discover(selected_keys, deep_limit, language_keys)
                warnings.extend(w for w in deeper_warnings if w not in warnings)
                merged = {h.name.lower(): h for h in discovered}
                for hit in deeper:
                    merged.setdefault(hit.name.lower(), hit)
                discovered = list(merged.values())
                scored, known_skipped = await self._score_discovered(
                    discovered,
                    min_len=min_len,
                    max_len=max_len,
                    min_score=min_score,
                    known_names=known_names,
                )
                deepened = len(discovered) > initial_discovered

        # Progressive live .com checking: do not stop after one shallow batch if it
        # yields only a handful of available names. Never changes the availability rule.
        batch_size = max(1, domain_checks)
        max_checks = min(len(scored), max(batch_size, min(240, batch_size * 4)))
        target_available = min(24, max(8, brand_checks * 2))
        checked: list[Candidate] = []
        available: list[Candidate] = []
        cursor = 0

        while cursor < max_checks and (cursor == 0 or len(available) < target_available):
            batch = scored[cursor:min(cursor + batch_size, max_checks)]
            if not batch:
                break
            domain_results = await self.domain.check_many([c.domain for c in batch])
            for c in batch:
                dr = domain_results.get(c.domain.lower())
                c.domain_status = dr.status if dr else "unknown"
            checked.extend(batch)
            available.extend(c for c in batch if c.domain_status == "available")
            cursor += len(batch)

        available = await self._screen_available(available, brand_checks)
        return {
            "candidates": [self._with_links(c) for c in available],
            "stats": {
                "discovered": len(discovered),
                "initial_discovered": initial_discovered,
                "after_brand_filter": len(scored),
                "initial_scored": initial_scored,
                "domain_checked": len(checked),
                "available": len(available),
                "brand_checked": min(len(available), max(0, brand_checks)),
                "known_skipped": known_skipped,
                "deepened": deepened,
            },
            "warnings": warnings,
            "search_note": (
                "Mianem automatycznie pogłębia zaufane źródła i kolejne partie live .com, "
                "gdy pierwsza próba daje zbyt mało dobrych wyników. Progi jakości nie są obniżane."
            ),
            "availability_note": (
                "Tylko .com dostępne teraz. Domeny z aktywnym rekordem RDAP "
                "(aukcja, broker, wygasająca/pending-delete, aftermarket) są odrzucane."
            ),
        }
