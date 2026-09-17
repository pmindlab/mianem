from __future__ import annotations

import re
from dataclasses import dataclass


@dataclass
class BrandableHit:
    name: str
    niche: str
    key: str | None = None
    source: str = "brandable:rooted"
    meaning: str = ""


class ControlledBrandableProvider:
    """Deterministic brandable expansion from attested source words.

    This is deliberately not a random syllable generator. Every candidate preserves a
    visible 3+ letter stem from one or two real discovery hits, then uses a compact set
    of neutral endings or a bounded stem fusion. The normal Mianem phonetic/quality
    scorer still decides whether the resulting form is worth checking.
    """

    ENDINGS = (
        "a", "e", "i", "o", "ia", "io", "is", "on", "or", "en", "el", "an",
        "ar", "er", "al", "um", "ix", "ox", "ra", "la", "na", "va",
    )
    STRIP_SUFFIXES = (
        "aceae", "idae", "inae", "opsis", "ella", "ellus", "ensis", "iana",
        "icus", "icum", "ica", "ium", "ius", "eus", "eum", "ea", "ae",
        "us", "um", "is",
    )
    VOWELS = set("aeiou")

    @classmethod
    def _stem(cls, raw: str) -> str:
        word = re.sub(r"[^a-z]", "", raw.lower())
        if len(word) < 3:
            return ""
        stem = word
        for suffix in cls.STRIP_SUFFIXES:
            if stem.endswith(suffix) and len(stem) - len(suffix) >= 3:
                stem = stem[:-len(suffix)]
                break
        return stem

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
    def _join(left: str, right: str) -> str:
        # Avoid an ugly doubled boundary when the two preserved parts touch.
        if left and right and left[-1] == right[0]:
            return left + right[1:]
        return left + right

    def expand(self, hits: list, min_len: int, max_len: int, limit: int = 2400) -> list[BrandableHit]:
        if limit <= 0:
            return []

        roots: list[tuple[str, str, str]] = []
        seen_roots: set[str] = set()
        for hit in hits:
            raw = str(getattr(hit, "name", "") or "").strip().lower()
            root = self._stem(raw)
            if len(root) < 3 or root in seen_roots:
                continue
            seen_roots.add(root)
            niche = str(getattr(hit, "niche", "") or "source")
            roots.append((root, raw, niche))
            if len(roots) >= 360:
                break

        out: dict[str, BrandableHit] = {}

        def add(word: str, niche: str, key: str, meaning: str, source: str) -> None:
            if len(out) >= limit:
                return
            word = word.lower()
            if word in seen_roots:
                return
            if not self._looks_brandable(word, min_len, max_len):
                return
            out.setdefault(word, BrandableHit(
                name=word,
                niche=niche,
                key=key,
                source=source,
                meaning=meaning,
            ))

        # Family 1: preserve a real stem and fit a neutral ending to the requested length.
        for root, raw, niche in roots:
            for target in range(min_len, max_len + 1):
                for ending in self.ENDINGS:
                    keep = target - len(ending)
                    if keep < 3 or keep > len(root):
                        continue
                    stem = root[:keep]
                    candidate = self._join(stem, ending)
                    add(
                        candidate,
                        niche,
                        raw,
                        f"constructed from real root {raw}",
                        "brandable:rooted",
                    )
                    if len(out) >= limit:
                        return list(out.values())

        # Family 2: bounded fusion of two attested roots. Each side contributes >=3 chars.
        # Pair only nearby source roots to keep work deterministic and bounded.
        for index, (left_root, left_raw, left_niche) in enumerate(roots):
            for right_root, right_raw, right_niche in roots[index + 1:index + 9]:
                for target in range(max(min_len, 6), max_len + 1):
                    for left_size in range(3, target - 2):
                        right_size = target - left_size
                        if left_size > len(left_root) or right_size > len(right_root):
                            continue
                        left = left_root[:left_size]
                        right = right_root[-right_size:]
                        candidate = self._join(left, right)
                        niche = left_niche if left_niche == right_niche else f"{left_niche} + {right_niche}"
                        add(
                            candidate,
                            niche,
                            f"{left_raw}+{right_raw}",
                            f"fusion of real roots {left_raw} + {right_raw}",
                            "brandable:fusion",
                        )
                        if len(out) >= limit:
                            return list(out.values())

        return list(out.values())
