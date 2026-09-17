# Current Task

TASK_ID: mianem-search-v2-multisource-depth-2026-09-17

Status: implementation on stacked feature branch; CI and Human Owner result-quality QA pending.

## Context / base
This task is stacked on the v1.7.4 state-recovery branch from PR #21. The Human Owner explicitly asked to prioritize materially more effective naming search; the stale version label visible in the browser is deferred and is not the focus of this task.

## Trigger
The current search can still produce very few or zero useful records because the source universe is narrow:

- taxonomy discovery primarily searches GENUS records,
- bundled language lists are intentionally small,
- availability checking can only work with names that discovery has already surfaced.

A competitor benchmark (Atom, Namelix, NameSnack, Looka) reinforced the useful architecture pattern: build a broad multi-source candidate universe first, rank it, use saved preferences, then progressively check live availability. Mianem adopts that search architecture without copying competitor UI/content and without switching to random word blends.

## Search v2 scope

### 1. Multi-source discovery
- Preserve existing curated genera, seeds and bundled language words.
- Add accepted GBIF species epithets as a second real taxonomic source.
- Sample species pages across the full GBIF result set rather than only the first alphabetic slice.
- When English is explicitly selected, add an optional runtime semantic real-word source related to the selected naming areas.
- Remote semantic failure is non-fatal; taxonomy and bundled data remain sufficient to run the app.
- Deduplicate names before scoring.

### 2. Mode-specific depth
- Fast: existing shallow source budget; no extra species/semantic spend.
- Detailed/Balanced: bounded species expansion plus a smaller semantic-English budget.
- Deep: materially larger species and semantic source budgets distributed across all selected areas.
- The UI sends the actual selected mode to the backend instead of expressing depth only through numeric limits.

### 3. Ranking + availability
- Keep the existing `min_score`; do not lower quality merely to populate the screen.
- Keep the learned preference profile from shortlist/radar/reject decisions.
- Keep the highest-ranked names first, then diversify domain-check order across source families and niches so one source cannot monopolize the finite live-check budget.
- Progressive live `.com` checking budgets: Fast up to 120, Balanced up to 320, Deep up to 640 candidates when necessary.
- Deep target is up to 40 actually available results when the source pool and RDAP yield permit it.
- Stop early if repeated RDAP batches are mostly unknown/rate-limited rather than hammering the service.

## QA gates
- `pytest -q` green.
- Frontend JavaScript syntax gate green.
- Search v2 is the active service while `DeepNameLabService` remains its safety baseline.
- Regression proves species epithet extraction uses real single-token epithets and deduplicates them.
- Regression proves Deep mode spends extra taxonomy/semantic budget and Fast mode does not.
- Regression proves UI sends `search_mode` to the backend.
- Regression proves returned search still filters strictly on `domain_status == available`.
- Windows portable build and packaged smoke tests green before giving the Human Owner a test ZIP.
- Human Owner compares Deep search on a previously weak query and evaluates both quantity and actual naming quality.

## Product invariants
No aftermarket, auction, broker, redemption, pending-delete or merely expiring domain may be presented as available. Recommendation quality remains independent from `.com` availability. Brand screening remains research triage, not legal trademark clearance. Prefer real words / real taxa / attested lexical material over synthetic startup-style blends.
