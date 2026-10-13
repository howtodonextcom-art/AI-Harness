# ADR-0013: Pattern search leakage rule and design

Status: accepted (2026-10-08)

**Rule.** A candidate window ending at `e` may be matched to a query window `[q-W+1, q]` only if its
outcome window `[e+1, e+H]` ends before the query window starts: `e <= q - W - H`. `H` is the largest
horizon the outcome engine will use, fixed in `SearchConfig.horizon` (default 60) so a later change of
horizon cannot silently re-admit overlapping candidates.

**Why this strict form.** The weaker rule `e + H <= q` (outcome already known at query time) is
sufficient to avoid look-ahead but lets a candidate's outcome run through the query window, so the
matched "analogue" and the query share bars. That inflates apparent predictability whenever the
market trends through the overlap. The strict rule costs `W + H` bars of recent history per query.

**Other decisions.**
* The search slices values to `q + 1` rows first (defence in depth: current methods only read
  admissible rows, but a future method with global statistics must not be able to see the future).
* Representation is per-bar and ATR-normalised, with no global scaling (a global z-score would leak).
* Selected neighbours are at least `W` bars apart; ties favour the earlier window.
* Queries or candidates with missing values are never compared; a query with missing values raises.
* DTW and the distance-profile functions are implemented in NumPy; STUMPY/tslearn are not dependencies
  (numba support does not cover the whole Python matrix; see `docs/research/pattern-similarity.md`).

**Equivalent mutant noted.** Removing the `q + 1` slice does not change today's results (all methods
read only admissible rows); the slice is kept as a guard and is documented here rather than tested.
