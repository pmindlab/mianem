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

### 4. Availability-aware rooted brandable fallback
When Balanced/Deep has insufficient live `.com` yield after attested-source checking:

- do **not** merely scan more of the same real-word/taxa universe;
- build a deterministic bounded pool from the real discovered roots;
- preserve at least a 3-letter source stem;
- use only controlled neutral endings or bounded two-root fusion;
- reject bad vowel ratios, heavy consonant clusters and repeated-character junk before normal scoring;
- run the exact same Mianem quality + shortlist/radar preference scorer;
- do not lower `min_score`;
- Deep may spend up to 560 additional live checks on these high-ranked constructed forms, stopping as soon as the target yield is reached;
- every constructed result carries an explicit `brandable:*` source and explanation of its source root(s).

This is not a random syllable generator. Attested words remain the preferred first stage; constructed forms are a registration-yield fallback only after live saturation is observed.

## QA gates
- `pytest -q` green.
- Frontend JavaScript syntax gate green.
- Search v2 is the active service while `DeepNameLabService` remains its safety baseline.
- Regression proves species epithet extraction uses real single-token epithets and deduplicates them.
- Regression proves Deep mode spends extra taxonomy/semantic budget and Fast mode does not.
- Regression proves controlled brandable generation is deterministic and respects exact requested length.
- Regression proves a zero-available real-source run pivots to the rooted brandable phase in Deep mode.
- Regression proves UI sends `search_mode` to the backend and exposes fallback stats.
- Regression proves returned search still filters strictly on `domain_status == available`.
- Windows portable build and packaged smoke tests green before giving the Human Owner a replacement test ZIP.
- Human Owner repeats the same exact-length-6 Deep query and evaluates availability yield plus actual naming quality.

## Product invariants
No aftermarket, auction, broker, redemption, pending-delete or merely expiring domain may be presented as available. Recommendation quality remains independent from `.com` availability. Brand screening remains research triage, not legal trademark clearance. Prefer real words / real taxa / attested lexical material first; constructed forms are clearly labeled and used only as an availability fallback.
