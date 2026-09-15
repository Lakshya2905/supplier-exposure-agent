# sample

A worked example, small enough to read in full and labelled so every row is
here for a reason. **Synthetic**: no real part numbers, no real supplier names.

Score it with `POST /api/score` against this directory, or point the backend at
it. Seven parts, two finished goods, and all three optional files filled in — so
this is also the only dataset in the repository where `resource_days`,
`committed_at_risk` and sub-tier correlation actually produce figures.

## What each part demonstrates

| part | shows |
|---|---|
| `SAMPLE-P-01` | **One supplier who owns the tooling.** Moving means cutting new tooling, not raising a purchase order. Its resourcing chain is timed except for tooling, so the total is a **lower bound** and the sentence names tooling as the untimed step. |
| `SAMPLE-P-02` | **A hidden single source.** Two qualified suppliers on paper, one that can actually quote. It also feeds both finished goods while only one is in the order book, so promised orders are a **lower bound**. |
| `SAMPLE-P-03` | **Nobody to call.** The supplier list was checked and is empty. That is a finding, not a gap in the spreadsheet, and the tool says so in those words. |
| `SAMPLE-P-04` | **Made in-house.** There is no purchase lead time to wait out, so that measure is *not applicable* rather than unknown — a distinction that keeps it out of the work queue for ever. |
| `SAMPLE-P-05` | **A blank on-hand record.** Cover reads "not enough data to say", never zero. Its resourcing chain is fully timed *and* carries a cycle count, so it is the one settled chain here and reports both "if it passes first time" and "if it takes two attempts". |
| `SAMPLE-P-06` | **A recorded zero.** Stock was counted and there is none. Compare it with `SAMPLE-P-05`: same screen, opposite findings, and collapsing them is the failure this whole tool is built around. |
| `SAMPLE-P-07` | **One supplier, spelled two ways.** `Calder Corporation` in `suppliers.csv` and `Calder Corp` in `lead_times.csv`. The tool reconciles them and shows in the evidence panel that it did, rather than quietly counting two suppliers or quietly counting one. |

## What the whole set demonstrates

**Correlation that only a sub-tier field can see.** `SAMPLE-P-01` and
`SAMPLE-P-05` share a supplier and a region, so supplier grouping and region
grouping both find them. `SAMPLE-P-06` is a different company in a different
region — and all three suppliers buy from `Ferrite Mill`. Only the tier grouping
sees that, and it is the reason the sub-tier column exists.

`Vantage Works` has a blank sub-tier source: they have not said. It groups with
nothing, because two suppliers who have both declined to say are not thereby
buying from the same place.

**Criticality tiers.** A, B and C are on the part master, and `SAMPLE-P-04` has
none — which reads as *unclassified* and stays in scope. Scope the run to `A`
and the tool assesses two parts and says out loud that it did not examine the
other five.

**An order book that covers part of the plan.** `SAMPLE-FG-01` has committed
orders and `SAMPLE-FG-02` does not, so some parts report a figure, some report a
lower bound, and some abstain. Three different answers from one file, and none
of them is zero.
