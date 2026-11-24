# Variant E: variant D plus the evidence check

Runs: raw/E_run1-3.jsonl (payment test, run 2026-11-23 on the repaired scenarios file) and raw/E_merchants_run1-3.csv
(merchant test, run 2026-11-22). Each payment output keeps the model's own answer (`model_output`) beside the checked answer
(`output`). "E_model" below scores the model's answer before the check; "E" scores the checked answer, where an answer that
fails the check becomes an escalation. Per-run scores are in run1 to run3.

Release v1.0 of this repository shipped a copy of benchmark_scenarios_answer_key.csv in which a spreadsheet save had
dropped the leading zeros of 81 response codes (05 became 5) and trailing zeros in the amount column. Release v1.1
restores the file. Variants A to D were run on the intact file before that save, and variant E was run on the
restored file; the scorer reads both forms identically, so no published score changes.

## Payment test, 398 scenarios, mean of three runs

| | A | D | E_model | E |
| --- | --- | --- | --- | --- |
| Category accuracy | 83.4% | 86.3% | 86.0% | 86.0% |
| Action accuracy | 65.6% | 72.8% | 77.4% | 74.0% |
| Action, standard cases | 100.0% | 79.3% | 82.7% | 78.5% |
| Action, hard cases | 30.8% | 66.2% | 72.1% | 69.4% |
| Escalation precision | 56.8% | 88.0% | 85.2% | 63.4% |
| Escalation recall | 90.9% | 80.0% | 83.6% | 83.6% |
| Answers released without escalation | 310 | 348 | 344 | 325 |
| Released answers with a wrong next step | 26.5% | 26.8% | 21.8% | 21.0% |

* Asking for an Evidence line changed the action in about 23 scenarios per run; in each run 18 or 19 became correct and none
  became wrong (exact McNemar, E_model vs D, p < 0.001 in every run).
* The check failed 21 answers per run on average (25, 17, 21). Their actions were right 64.5% of the time and their
  categories 58.0%, against 78.1% action accuracy for answers that passed. Escalating them cut wrong released answers
  slightly (21.8% to 21.0%) but cost 3.4 points of action accuracy and 22 points of escalation precision. E vs D is not
  significant (wins/losses per run 16/15, 18/9, 16/12; p = 1.00, 0.12, 0.57).
* Most common failure reasons: citing a field the record does not have (often the documentation under another name),
  citing Mastercard advice code 03 on a record with no advice code, not citing the response code, citing the wrong code.
* Retry limit reached (20 scenarios): D 5%, E_model 10%, E 5%. The evidence check does not fix the reattempt-limit failure.
* Median input tokens 2,070 per diagnosis (D: about 1,930); median latency 6.5 s.

## Merchant test, 30 merchants, mean of three runs

| | A | D | E |
| --- | --- | --- | --- |
| Pattern precision | 82.1% | 43.3% | 49.7% |
| Pattern recall | 62.7% | 63.4% | 55.6% |
| Pattern F1 | 71.1% | 51.5% | 52.4% |
| False alarms on clean merchants | 75.0% | 75.0% | 75.0% |
| Action accuracy on found patterns | 100.0% | 75.2% | 80.3% |

Dropped findings and reasons: raw/E_merchants_run*_flagged.csv.
