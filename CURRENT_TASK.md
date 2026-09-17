# Current Task

TASK_ID: mianem-search-v2-multisource-depth-2026-09-17

Status: implementation on stacked feature branch; CI and Human Owner result-quality QA pending.

## Context / base
This task is stacked on the v1.7.4 state-recovery branch from PR #21. The Human Owner explicitly asked to prioritize materially more effective naming search; the stale version label visible in the browser is deferred and is not the focus of this task.

## Trigger
The current search can still produce very few or zero useful records because the source universe is narrow and short real-word `.com` space is highly saturated:

- taxonomy discovery originally searched primarily GENUS records,
- bundled language lists are intentionally small,
- availability checking can only work with names that discovery has already surfaced,
- Human Owner's real Deep QA on 17.09.2026 with exact length 6 produced: **12,300 discovered → 490 selected → 490 checked → 0 available `.com`**.

That QA result is a hard product finding: deeper discovery of only attested words/taxa can increase volume without increasing registration yield.

A competitor benchmark (Atom, Namelix, NameSnack, Looka) reinforced the useful architecture pattern: build a broad multi-source candidate universe first, rank it, use saved preferences, then progressively check live availability. Mianem adopts that architecture without copying competitor UI/content.

## Search v2 scope

### 1. Multi-source discovery
- Preserve existing curated genera, seeds and bundled language words.
- Add accepted GBIF species epithets as a second real taxonomic source.
- Sample species pages across the full GBIF result set rather than only the first alphabetic slice.
- When English is explicitly selected, add an optional runtime semantic real-word source related to the selected naming areas.
- Remote semantic failure is non-fatal; taxonomy and bundled data remain sufficient to run the app.
- Deduplicate names before scoring.

### 2. Mode-specific depth
- Fast: existing shallow source budget; no extra species/semantic spend and no constructed-name fallback.
- Detailed/Balanced: bounded species expansion plus a smaller semantic-English budget.
- Deep: materially larger species and semantic source budgets distributed across all selected areas.
- The UI sends the actual selected mode to the backend instead of expressing depth only through numeric limits.

### 3. Ranking + availability
- Keep the existing `min_score`; do not lower quality merely to populate the screen.
- Keep the learned preference profile from shortlist/radar/reject decisions.
- Keep the highest-ranked names first, then diversify domain-check order across source families and niches so one source cannot monopolize the finite live-check budget.
- Primary live `.com` budgets: Fast up to 120, Balanced up to 320, Deep up to 640 candidates when necessary.
- Deep target is up to 40 actually available results when the source pool and RDAP yield permit it.
- Use smaller live-check chunks (max 80) so the search can pivot sooner and respect RDAP back-pressure.
- Stop early if repeated RDAP batches are mostly unknown/rate-limited rather than hammering the service.

### 4. Availability-aware near-root fallback
Human QA of the first rooted fallback showed another hard product finding: forms such as `Aglaor`, `Lafrix`, `Aglum`, `Urosix`, `Boisox` and `Doriax` were too abstract and no longer felt meaningfully connected to the selected bird groups.

Therefore Balanced/Deep fallback is now deliberately conservative:

- attested real names remain the preferred first phase;
- fallback source material is restricted to real **GBIF genus / curated seed** hits from the selected taxonomic areas;
- species epithets and generic semantic-English words may enrich real-name discovery but may **not** seed a synthetic fallback form;
- no two-root fusion;
- no arbitrary startup endings such as `-ix` / `-ox`;
- no truncation to a generic 3-letter stem;
- a generated form must differ from the source genus by **at most one character edit**;
- allowed transformations are only: one-character extension, final-character substitution, or final-character shortening;
- normal pronunciation / vowel-ratio / consonant-cluster checks still apply;
- normal Mianem quality + shortlist/radar preference scoring still applies;
- `min_score` is never lowered;
- provenance is explicit on the result (`<selected niche> · from <real genus>` and `brandable:near-root`);
- if this stricter fallback produces fewer results, that is preferable to filling the screen with abstract pseudo-names.

## QA gates
- `pytest -q` green.
- Frontend JavaScript syntax gate green.
- Search v2 is the active service while `DeepNameLabService` remains its safety baseline.
- Regression proves species epithet extraction uses real single-token epithets and deduplicates them.
- Regression proves Deep mode spends extra taxonomy/semantic budget and Fast mode does not.
- Regression proves near-root fallback is deterministic, genus-only, exact-length aware and max-one-edit from source.
- Regression proves a zero-available real-source run may pivot to the near-root genus phase in Deep mode.
- Regression proves UI sends `search_mode` to the backend and exposes fallback stats.
- Regression proves returned search still filters strictly on `domain_status == available`.
- Windows portable build and packaged smoke tests green before giving the Human Owner a replacement test ZIP.
- Human Owner repeats the same exact-length-6 Deep query and evaluates availability yield plus whether every derived result still has an obvious relationship to its source genus.

## Product invariants
No aftermarket, auction, broker, redemption, pending-delete or merely expiring domain may be presented as available. Recommendation quality remains independent from `.com` availability. Brand screening remains research triage, not legal trademark clearance. Prefer real words / real taxa / attested lexical material first; derived forms must stay visibly anchored to a real selected-area genus.
