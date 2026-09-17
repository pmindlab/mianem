# Current Task

TASK_ID: mianem-v1-7-4-state-recovery-and-search-depth-2026-09-17

Status: implementation on feature branch; CI + Human Owner Windows QA pending.

## Trigger
Human Owner reported two real-product problems in the Windows portable build:

1. previously saved shortlist / radar / reject records were no longer visible after moving from the source/development build to portable state under `%LOCALAPPDATA%\\PMindLab\\Mianem`;
2. normal naming search could sometimes return very few or zero records, even though the product should continue searching rather than stop after one shallow discovery/domain-check pass.

A competitor benchmark (Namelix, Atom, NameSnack, Looka) also confirmed the mature pattern: create a broad candidate pool, rank it, learn from saved preferences, and progressively check availability rather than treating one small batch as the complete search universe.

## v1.7.4 remediation

### Portable state recovery
- Preserve portable mutable state under `%LOCALAPPDATA%\\PMindLab\\Mianem`.
- Never bundle the Human Owner's local SQLite state.
- If the current portable DB already has candidates, do not import or overwrite anything.
- If exactly one obvious legacy `data\\namelab.db` is found next to the launch location, import it automatically.
- Otherwise, when the new portable DB is empty, explicitly offer the user a file picker for the old `namelab.db` rather than silently presenting an empty history.
- Validate that the selected SQLite DB contains the Mianem `candidates` table and at least one candidate.
- Preserve an existing empty target as `namelab.before-import*.db` before replacement.
- Copy through a temporary file and validate it before atomic replacement.

### Adaptive search depth
- Keep the existing real-word / taxonomy preference and existing scoring threshold.
- If the initial scored pool is thin, repeat discovery against the same trusted sources with a larger source limit (up to a bounded maximum).
- Do not lower `min_score` merely to fill the screen.
- Check live `.com` availability progressively in additional ranked batches when the first batch produces too few available names.
- Bound the additional domain work; no unbounded scanning.
- Only `domain_status == available` may enter returned results.
- Existing brand screening remains after live availability filtering.

## QA gates
- `pytest -q` green.
- Existing Windows portable tests green.
- New portable-state tests prove non-empty target protection, backup of an empty target, and automatic import of one obvious legacy DB.
- New search-depth tests prove v1.7.4 is the active service and that progressive checks never promote non-available domains.
- PyInstaller single-file Windows build green.
- Packaged `--smoke-test` and `--server-smoke-test` green.
- Human Owner validates on Windows that old saved names can be recovered and that a search which previously returned too few names now continues deeper.

## Product invariants
No aftermarket, auction, broker, redemption, pending-delete or merely expiring domain may be presented as available. Recommendation quality remains independent from `.com` availability. Brand screening remains research triage, not legal trademark clearance.
