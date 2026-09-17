from __future__ import annotations

import asyncio
from pathlib import Path
from types import SimpleNamespace

import app.service as service_module
from app.models import Candidate
from app.providers import (
    BrandableHit,
    ControlledBrandableProvider,
    GBIFProvider,
    SemanticHit,
    TaxonHit,
)
from app.service_v18 import SearchV2Service


ROOT = Path(__file__).resolve().parents[1]


def test_search_v2_is_active_service():
    assert service_module.NameLabService is SearchV2Service


def test_gbif_deep_source_extracts_real_species_epithets_without_network(monkeypatch):
    provider = GBIFProvider(timeout=0.1)

    async def fake_resolve(_client, _taxon_name):
        return 123

    async def fake_get(_client, _path, params):
        assert params["rank"] == "SPECIES"
        return {
            "count": 4,
            "results": [
                {"key": 1, "specificEpithet": "aurora", "canonicalName": "Avis aurora"},
                {"key": 2, "specificEpithet": "lucida", "canonicalName": "Avis lucida"},
                {"key": 3, "specificEpithet": "aurora", "canonicalName": "Alia aurora"},
                {"key": 4, "specificEpithet": "blue-wing", "canonicalName": "Alia blue-wing"},
            ],
        }

    monkeypatch.setattr(provider, "resolve_taxon", fake_resolve)
    monkeypatch.setattr(provider, "_get", fake_get)
    hits = asyncio.run(provider.species_epithets_for_niche("Trochilidae", "hummingbirds", 20))

    assert [h.name for h in hits] == ["aurora", "lucida"]
    assert all(h.source == "gbif:epithet" for h in hits)


def test_deep_mode_uses_extra_taxonomy_and_semantic_english(monkeypatch):
    service = SearchV2Service.__new__(SearchV2Service)
    service.catalog = SimpleNamespace(get=lambda key: SimpleNamespace(key=key) if key == "birds" else None)
    calls = {"epithet": 0, "semantic": 0}

    async def fake_base(_keys, _per_niche, _languages):
        return [TaxonHit(name="Loxops", niche="birds", source="gbif:genus")], []

    async def fake_epithets(_keys, per_niche):
        calls["epithet"] = per_niche
        return [TaxonHit(name="Aurora", niche="birds", source="gbif:epithet")], []

    async def fake_semantic(_keys, per_niche):
        calls["semantic"] = per_niche
        return [SemanticHit(name="glimmer", niche="English · birds", meaning="related to birds")], []

    monkeypatch.setattr(service, "discover", fake_base)
    monkeypatch.setattr(service, "_discover_species_epithets", fake_epithets)
    monkeypatch.setattr(service, "_discover_semantic_english", fake_semantic)

    hits, warnings, source_counts = asyncio.run(
        service.discover_v2(["birds"], 220, ["en"], "deep")
    )

    assert warnings == []
    assert {h.name.lower() for h in hits} == {"loxops", "aurora", "glimmer"}
    assert calls["epithet"] >= 100
    assert calls["semantic"] >= 30
    assert source_counts["gbif:epithet"] == 1
    assert source_counts["semantic:en"] == 1


def test_fast_mode_does_not_spend_extra_source_budget(monkeypatch):
    service = SearchV2Service.__new__(SearchV2Service)
    service.catalog = SimpleNamespace(get=lambda key: SimpleNamespace(key=key))
    calls = []

    async def fake_base(_keys, _per_niche, _languages):
        return [TaxonHit(name="Loxops", niche="birds", source="gbif:genus")], []

    async def fake_epithets(_keys, per_niche):
        calls.append(("epithet", per_niche))
        return [], []

    async def fake_semantic(_keys, per_niche):
        calls.append(("semantic", per_niche))
        return [], []

    monkeypatch.setattr(service, "discover", fake_base)
    monkeypatch.setattr(service, "_discover_species_epithets", fake_epithets)
    monkeypatch.setattr(service, "_discover_semantic_english", fake_semantic)

    asyncio.run(service.discover_v2(["birds"], 60, ["en"], "fast"))
    assert calls == [("epithet", 0), ("semantic", 0)]


def test_domain_check_order_keeps_top_names_and_adds_source_diversity():
    candidates = []
    for i in range(45):
        source = "gbif:genus" if i < 35 else "semantic:en"
        niche = "birds" if i % 2 == 0 else "insects"
        candidates.append(Candidate(
            name=f"Name{i}", domain=f"name{i}.com", niche=niche, source=source, score=100 - i
        ))
    ordered = SearchV2Service._check_order(candidates)
    assert ordered[0].name == "Name0"
    assert len(ordered) == len(candidates)
    assert len({c.name for c in ordered}) == len(candidates)


def test_controlled_brandable_provider_is_deterministic_one_edit_and_genus_only():
    provider = ControlledBrandableProvider()
    hits = [
        TaxonHit(name="Loxops", niche="hummingbirds", source="gbif:genus"),
        TaxonHit(name="Aurora", niche="hummingbirds", source="gbif:epithet"),
        SemanticHit(name="lumen", niche="English · birds", source="semantic:en"),
    ]
    first = provider.expand(hits, 6, 6, limit=120)
    second = provider.expand(hits, 6, 6, limit=120)

    assert first
    assert [h.name for h in first] == [h.name for h in second]
    assert all(len(h.name) == 6 for h in first)
    assert all(h.source == "brandable:near-root" for h in first)
    assert all(h.key == "loxops" for h in first)
    assert all("1 edit" in h.meaning for h in first)
    assert all(provider._within_one_edit("loxops", h.name) for h in first)
    assert not any(h.key in {"aurora", "lumen"} for h in first)


def test_deep_search_pivots_to_near_root_genus_after_zero_real_availability(monkeypatch):
    service = SearchV2Service.__new__(SearchV2Service)
    service.brandable = ControlledBrandableProvider()
    service.profile = SimpleNamespace()

    monkeypatch.setattr(service, "_refresh_profile", lambda: None)
    monkeypatch.setattr(service, "_known_names", lambda: set())

    discovered = [TaxonHit(name="Loxops", niche="hummingbirds", source="gbif:genus")]

    async def fake_discover_v2(*_args, **_kwargs):
        return discovered, [], {"gbif:genus": 1}

    async def fake_score(items, **_kwargs):
        if items and isinstance(items[0], BrandableHit):
            return [Candidate(
                name="Loxopa", domain="loxopa.com", niche="hummingbirds",
                source="brandable:near-root", score=80,
            )], 0
        return [Candidate(
            name="Loxops", domain="loxops.com", niche="hummingbirds",
            source="gbif:genus", score=90,
        )], 0

    async def fake_check(ordered, **_kwargs):
        if ordered and ordered[0].source.startswith("brandable:"):
            ordered[0].domain_status = "available"
            return list(ordered), list(ordered), []
        for item in ordered:
            item.domain_status = "taken"
        return list(ordered), [], []

    async def fake_screen(items, _brand_checks):
        return items

    monkeypatch.setattr(service, "discover_v2", fake_discover_v2)
    monkeypatch.setattr(service, "_score_discovered", fake_score)
    monkeypatch.setattr(service, "_check_live", fake_check)
    monkeypatch.setattr(service, "_screen_available", fake_screen)
    monkeypatch.setattr(service, "_with_links", lambda c: c.to_dict())

    result = asyncio.run(service.run_search(
        ["birds"], min_len=6, max_len=6, domain_checks=80,
        brand_checks=10, min_score=50, language_keys=["en"], search_mode="deep",
    ))

    assert result["stats"]["real_available_before_brandable"] == 0
    assert result["stats"]["brandable_pool"] > 0
    assert result["stats"]["brandable_checked"] == 1
    assert result["stats"]["brandable_available"] == 1
    assert result["candidates"][0]["domain"] == "loxopa.com"


def test_search_v2_keeps_live_available_only_invariant():
    text = (ROOT / "app" / "service_v18.py").read_text(encoding="utf-8")
    assert 'c.domain_status == "available"' in text
    assert "primary_cap = 640" in text
    assert "brandable_check_cap = 560" in text
    assert "target_available = 40" in text
    assert "score < min_score" in text
    assert 'mode != "fast"' in text


def test_frontend_sends_actual_search_mode():
    text = (ROOT / "app" / "static" / "core-v15b1.js").read_text(encoding="utf-8")
    assert "search_mode:mode" in text
    assert "Głęboki: najpierw realne źródła" in text
    assert "fallback:" in text
