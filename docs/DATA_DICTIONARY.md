# Data dictionary

What stages 2 onward should read before touching a CSV. Column names are also
available as constants in `src/synthetic/model.py`; import those rather than
typing string literals, so a rename is one edit and a typo is an ImportError
instead of a silently empty join.

## Null semantics, the part most likely to bite

| encoding | meaning |
|---|---|
| empty cell | **no record exists**. The honest answer downstream is "cannot tell". |
| `0` | somebody counted and recorded zero. A real measurement. |

These are different facts and must stay different. One `fillna(0)` collapses
"nobody knows" into "we have none", and the data set deliberately contains both
so that collapse fails a test rather than shipping.

`supplier_region` never contains the token `NA`. pandas reads a bare `NA` as
NaN by default, which would silently delete a region from concentration
analysis.

## bom.csv

| column | type | notes |
|---|---|---|
| `parent_part` | str | never a leaf |
| `child_part` | str | every value also appears in `part_master.csv` |
| `qty_per_parent` | int | per one unit of the parent, always >= 1 |

Edges only. **Depth is not precomputed here.** Deriving it is stage 2's job,
and shipping it in the input would let stage 2 grade itself.

The BOM is acyclic by construction. A part may appear under more than one
parent, and at more than one depth: depth is a property of the path, not of the
part.

## part_master.csv

| column | type | notes |
|---|---|---|
| `part_number` | str | prefixed `SEA-P-` or `SEA-FG-` |
| `description` | str | synthetic |
| `source_type` | str | `make` or `buy`. **Required, never blank.** |
| `sourcing_list_status` | str | `verified`, `unverified`, or blank |
| `on_hand_units` | int or blank | blank = no record, `0` = counted and empty |
| `tooling_owner` | str | `company`, `supplier`, or blank (portability unknown) |
| `annual_spend_usd` | int | **display only. Never scored, ranked or weighted.** |

`source_type` is what separates two cases that otherwise look identical: a part
with no supplier rows is either made in-house (a known fact) or a bought part
whose suppliers nobody recorded (an unknown).

`sourcing_list_status` gates the verdict only. It never enters scoring.

## suppliers.csv

| column | type | notes |
|---|---|---|
| `part_number` | str | |
| `supplier_name` | str | **may be a variant spelling** |
| `supplier_region` | str | one of four; never `NA` |
| `qualification_date` | str | ISO date |

One row per part-supplier pair. A part with no rows here has no recorded
suppliers, which means different things depending on `source_type` and
`sourcing_list_status`.

## lead_times.csv

| column | type | notes |
|---|---|---|
| `part_number` | str | |
| `supplier_name` | str | **may be spelled differently from suppliers.csv** |
| `quoted_lead_time_days` | int | 3 to 300 |
| `lead_time_p95_days` | int | 95th percentile observed, always >= quoted |

Not every part-supplier pair has a row. A pair present in `suppliers.csv` and
absent here is a supplier that cannot be quoted, which is what makes a hidden
single source hidden.

`lead_time_p95_days` is named for what it is rather than a vague "variance", so
stage 4 does not have to guess whether it is a standard deviation or a bound.

## demand_plan.csv

| column | type | notes |
|---|---|---|
| `finished_good_part` | str | prefixed `SEA-FG-` |
| `annual_units` | int | spread, not flat |

**One finished good is deliberately absent from this file.** That produces two
different situations, and they are not the same answer:

- a part fed by recorded finished goods **and** the absent one has *partially
  known* usage. Compute cover on known demand only and flag it an **upper
  bound**: unrecorded demand can only reduce cover, never increase it.
- a part fed **only** by the absent finished good is a full "cannot tell".

## sources.csv

The extract manifest: one row per input file, and the only file that describes
the others.

| column | type | notes |
|---|---|---|
| `source_file` | str | one of the five files above. Never `sources.csv` itself |
| `system_of_record` | str | which system the extract came out of |
| `retrieved_at` | str | ISO 8601 with offset. When that file was pulled |

**`system_of_record`, not `source_type`.** `source_type` is already a
`part_master.csv` column meaning make or buy, and an evidence panel showing
"source type: buy" beside "source type: ERP part master" would put two
unrelated facts under one word.

`retrieved_at` comes from `extract_anchor` and `extract_lag_hours` in
`src/synthetic/config.py`, never from a clock: `evals/` is frozen under a
manifest of hashes, and a wall-clock stamp would produce a different byte on
every build.

**The lags are staggered on purpose.** Five files pulled at one instant would
make `as of` a constant, and a constant printed on every evidence record is
decoration. The spread is what makes "the supplier list is a fortnight older
than the plan" a thing a reviewer can see.

Row locators are *not* in this file. A supplier or lead time record carries the
1-based data row it was read from, attached during the read, because a part has
many rows under a name that repeats and recovering the row afterwards would be
a lookup that can return the wrong one.

## truth/answer_key.json

Not an input. The generator's own record of what it decided, for grading later
stages. Gitignored along with `data/`.

It records **decisions and raw assignments only**: which records were omitted,
which supplier string maps to which supplier, which finished good was dropped
from the demand plan, and the per-part verdict.

It deliberately does **not** record anything requiring a traversal or a
threshold. No exploded quantities, no blast radius, no "is long lead". If the
answer key walked the BOM, a bug in that walk and a bug in stage 2's walk could
agree with each other and the test would pass.
