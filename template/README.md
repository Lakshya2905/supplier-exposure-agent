# template

Empty files with the correct headers. Copy this folder, fill it in, and score it.

**The headers are generated from `src/contract.py` and a test asserts they still
match it.** They cannot drift from the contract the validator enforces, which is
the usual way a template folder becomes wrong: somebody edits the schema and the
example stays as it was.

Six files are required and three are optional. Delete an optional file you have
nothing for; do not ship it empty, because an empty order book and no order book
are different facts and this system treats them differently.

| file | required |
|---|---|
| `bom.csv` | yes |
| `part_master.csv` | yes |
| `suppliers.csv` | yes |
| `lead_times.csv` | yes |
| `demand_plan.csv` | yes |
| `sources.csv` | yes |
| `recovery_inputs.csv` | no |
| `commitments.csv` | no |
| `sub_tier_sources.csv` | no |

`docs/DATA_DICTIONARY.md` says what every column holds, what its unit is, and
what a blank means. Two things are worth reading before you start:

- **A blank is not a zero.** In `on_hand_units` a blank means nobody has counted
  and a `0` means somebody counted and found none. Those are different findings
  and the whole tool is built to keep them apart. Do not fill blanks with zeros
  to make the file look tidy.
- **Units are part of the contract.** `quoted_lead_time_days` is days. If your
  system holds weeks, convert the values; renaming the header would score every
  lead time at a seventh of its length and nothing would say so.
