# Project 2 milestone gates

Use this checklist as evidence-based progress tracking. A file existing in Git does not, by itself, mean the milestone has passed.

- [ ] **M1 — Environment and reproducible data:** Create a fresh Python environment, install from `requirements.txt`, run the generator twice with the same seed and `--as-of` date, compare output files, and explain what each of the three tables represents.
- [ ] **M2 — PostgreSQL and loading:** Start the isolated Project 2 database, load all three CSVs, verify exact row counts, and confirm zero orphan session/order relationships.
- [ ] **M3 — Staging and quality:** Apply the staging views, inspect sample rows, and explain each coalesce, cast, JSON property extraction, and derived field.
- [ ] **M4 — Verified purchase reconciliation:** Confirm one row per distinct successful receipt-backed order; verify that pending and failed orders do not contribute revenue; inspect payment event/order mismatches.
- [ ] **M5 — Metric SQL and campaign mart:** Check denominators, compare all-channel totals with source queries, validate AOV as verified revenue divided by verified orders, and explain how the SQL avoids join fan-out.
- [ ] **M6 — Pandas analysis:** Run the independent analysis, confirm SQL-vs-Pandas reconciliation passes, and interpret acquisition, funnel, failure and daily revenue patterns without treating simulation assumptions as real benchmarks.
- [ ] **M7 — Dashboard:** Start Streamlit from a clean environment, verify all three tabs, exercise the source/date filters, and trace each displayed KPI to its SQL definition.
- [ ] **M8 — Testing and portfolio:** Run pytest locally, confirm GitHub Actions passes, complete README and metric/data dictionary, inspect the repository for secrets and generated identifiers, and explain the main design trade-offs.

Record date, commit SHA, test output, confidence (0–3), and remaining gaps whenever a gate is passed.
