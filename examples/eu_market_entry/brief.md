# Should Lumen Analytics enter the EU?

Lumen Analytics is a mid-market B2B SaaS company that sells per-seat analytics software. The leadership team must decide whether to enter the European Union within the next 18 months. The five candidate countries are Germany, France, Netherlands, Spain and Poland.

## The decision

Produce a decision dossier that answers:

1. Should Lumen enter the EU within 18 months (enter or hold)?
2. In which order should the five candidate countries be entered, and why?
3. At what per-seat monthly price?
4. What is the 3-year P&L, and what are the main risks?

## Evidence

All evidence is in a read-only data room mounted at `/data/`. Read its `README.md` first; it lists every file. Use only what is in the data room. Do not use outside knowledge for facts or figures.

## Citation rule

Every factual claim must cite its source file in square brackets, with the path relative to the data-room root. Examples: `[README.md]`, `[crm_pipeline.csv]`, `[crm_pipeline.csv:rows 1-40]`, `[cost_structure.csv]`. Do not write `/data/...` paths; they are rejected. Cite relative to the data-room root only.

## How to work with the evidence

Work like an auditor:

- Compare files against each other.
- Recompute totals from their line items.
- Check qualitative claims against measured data.
- Compare competitor prices with the company's own.
- Check regulatory timelines for every country.
- Break measured data down by each dimension it records, and look for groups that behave differently from the rest.

Report any discrepancy, contradiction or risk you find in the evidence, with the files involved and the figures that differ.

## Final output format

Keep the final dossier under 700 words (the DOSSIER_SUMMARY block does not count).

The final dossier must end with the line `DOSSIER_SUMMARY` followed by a fenced json block with exactly these keys and no others:

DOSSIER_SUMMARY
```json
{
  "recommendation": "<enter or hold>",
  "country_order": ["<country 1>", "<country 2>", "<country 3>", "<country 4>", "<country 5>"],
  "blocker_country": "<country>",
  "anomaly_segment": "<segment>",
  "undercutting_competitor": "<competitor>",
  "arith_mismatch_eur": "<number>"
}
```

Field rules: `recommendation` is "enter" or "hold"; `country_order` lists the five candidate countries, best first; `blocker_country`, `anomaly_segment` and `undercutting_competitor` are names taken from the evidence; `arith_mismatch_eur` is a number in EUR. Replace every placeholder with your own finding.
