from __future__ import annotations

import re
from dataclasses import dataclass


@dataclass
class BrandableHit:
    name: str
    niche: str
    key: str | None = None
    source: str = "brandable:near-root"
    meaning: str = ""


class ControlledBrandableProvider:
    """Very conservative fallback from attested taxonomic genera.

    Search should prefer real names. If the real-name phase yields too few available
    `.com` domains, this provider may create a *near-root* variant — never a random
    syllable blend. A candidate must come from an actual genus/seed hit and differ from
    that source by at most one character edit. This keeps provenance recognisable.
    """

    VOWELS = set("aeiou")
    SOURCE_ALLOW = ("gbif:genus", "seed")
    ADD_AFTER_VOWEL = ("n", "r", "l", "s")
    ADD_AFTER_CONSONANT = ("a", "e", "i", "o")
    FINAL_REPLACEMENTS = ("a", "e", "i", "o")

    @classmethod
    def _max_cluster(cls, word: str) -> int:
        best = cur = 0
        for ch in word:
            if ch not in cls.VOWELS:
                cur += 1
                best = max(best, cur)
            else:
                cur = 0
        return best

    @classmethod
    def _looks_brandable(cls, word: str, min_len: int, max_len: int) -> bool:
        if not re.fullmatch(r"[a-z]+", word):
            return False
        if not (min_len <= len(word) <= max_len):
            return False
        if len(set(word)) < 3:
            return False
        vowels = sum(ch in cls.VOWELS for ch in word)
        ratio = vowels / len(word)
        if ratio < 0.24 or ratio > 0.68:
            return False
        if cls._max_cluster(word) > 2:
            return False
        if re.search(r"(.)\1\1", word):
            return False
        return True

    @staticmethod
    def _within_one_edit(source: str, candidate: str) -> bool:
        if source == candidate:
            return False
        if abs(len(source) - len(candidate)) > 1:
            return False
        if len(source) == len(candidate):
            return sum(a != b for a, b in zip(source, candidate)) == 1

        short, long = (source, candidate) if len(source) < len(candidate) else (candidate, source)
        i = j = edits = 0
        while i < len(short) and j < len(long):
            if short[i] == long[j]:
                i += 1
                j += 1
            else:
                edits += 1
                j += 1
                if edits > 1:
                    return False
        return True

    @classmethod
    def _source_allowed(cls, hit) -> bool:
        source = str(getattr(hit, "source", "") or "")
        return source == "seed" or source.startswith("gbif:genus")

    def expand(self, hits: list, min_len: int, max_len: int, limit: int = 2400) -> list[BrandableHit]:
        if limit <= 0:
            return []

        roots: list[tuple[str, str]] = []
        seen_roots: set[str] = set()
        for hit in hits:
            if not self._source_allowed(hit):
                continue
            raw = re.sub(r"[^a-z]", "", str(getattr(hit, "name", "") or "").strip().lower())
            if len(raw) < 4 or raw in seen_roots:
                continue
            seen_roots.add(raw)
            niche = str(getattr(hit, "niche", "") or "source")
            roots.append((raw, niche))
            if len(roots) >= 600:
                break

        out: dict[str, BrandableHit] = {}

        def add(candidate: str, raw: str, niche: str, operation: str) -> None:
            if len(out) >= limit:
                return
            candidate = candidate.lower()
            if candidate in seen_roots or not self._within_one_edit(raw, candidate):
                return
            if not self._looks_brandable(candidate, min_len, max_len):
                return
            out.setdefault(candidate, BrandableHit(
                name=candidate,
                niche=f"{niche} · from {raw.capitalize()}",
                key=raw,
                source="brandable:near-root",
                meaning=f"near-root variant of real genus {raw} · {operation} · 1 edit",
            ))

        for raw, niche in roots:
            for target in range(min_len, max_len + 1):
                delta = target - len(raw)

                # Exactly one appended character. No stem truncation, no arbitrary suffixes.
                if delta == 1:
                    additions = self.ADD_AFTER_VOWEL if raw[-1] in self.VOWELS else self.ADD_AFTER_CONSONANT
                    for ch in additions:
                        add(raw + ch, raw, niche, "single-character extension")

                # Exactly one final-character substitution. The full preceding genus stays intact.
                elif delta == 0 and len(raw) >= 5:
                    for ch in self.FINAL_REPLACEMENTS:
                        if ch != raw[-1]:
                            add(raw[:-1] + ch, raw, niche, "final-character substitution")

                # Remove only the final character; never carve a 3-letter stem out of a genus.
                elif delta == -1 and len(raw) >= 6:
                    add(raw[:-1], raw, niche, "single-character shortening")

                # More than one edit would make the provenance too abstract, so do nothing.
                if len(out) >= limit:
                    return list(out.values())

        return list(out.values())
