# Evidence check applied offline to variant D's published outputs

Variant D's outputs (raw/D_run*.jsonl, raw/D_merchants_run*_raw.jsonl) were checked with `evidence_check.py` without calling the
model again. Checked outputs: raw/Dcheck_run*.jsonl and raw/Dcheck_merchants_run*.csv; every failed answer or dropped finding,
with its reasons, is in the matching *_flagged.csv. Scores per run are in run1 to run3 (variant "D+check").

Reproduce:
    for r in 1 2 3; do
      python evidence_check.py offline-payments  --raw raw/D_run$r.jsonl --out raw/Dcheck_run$r.jsonl
      python evidence_check.py offline-merchants --raw raw/D_merchants_run${r}_raw.jsonl --out raw/Dcheck_merchants_run$r.csv
      python score_decline_benchmark.py parse --raw raw/Dcheck_run$r.jsonl --out Dcheck_run$r.csv
      python score_decline_benchmark.py score --key benchmark_scenarios_answer_key.csv --schema decline_kb_schema.sql \
        --seed decline_kb_seed.sql --pred D=D_run$r.csv --pred D+check=Dcheck_run$r.csv --out results/evidence_check_offline/run$r
      python score_decline_benchmark.py score-merchants --key merchant_answer_key.csv --pred A=A_merchants.csv \
        --pred D=raw/D_merchants_run$r.csv --pred D+check=raw/Dcheck_merchants_run$r.csv --out results/evidence_check_offline/run$r
    done

## Results, mean of three runs

Payment test (398 scenarios)

| | D | D + evidence check |
| --- | --- | --- |
| Answers failing the check (escalated) | n/a | 10.7 (2.7%) |
| Action accuracy | 72.8% | 71.9% |
| Category accuracy | 86.3% | 86.3% |
| Escalation precision | 88.0% | 73.3% |
| Escalation recall | 80.0% | 80.0% |
| Answers released without escalation | 348 | 338 |
| Released answers with a wrong next step | 26.8% | 25.9% |

D's answers that failed the check had the right category in 31% of cases and the right next step in 41%, against 74% for the
answers that passed. Typical reasons: naming Discover code 63 for a record that says 61, describing a prepaid card when the
record says credit, treating code 65 on a US card as a European authentication request, naming the wrong network.

Merchant test (30 merchants, 51 planted patterns)

| | Group-by baseline (A) | D | D + evidence check |
| --- | --- | --- | --- |
| Pattern precision | 82.1% | 43.3% | 52.0% |
| Pattern recall | 62.7% | 63.4% | 59.5% |
| Pattern F1 | 71.1% | 51.5% | 55.4% |
| False alarms on clean merchants | 75.0% | 75.0% | 75.0% |
| Action accuracy on found patterns | 100.0% | 75.2% | 74.7% |

The check dropped 17 to 25 findings per run, mostly issuer outages argued from generic code 05, retry patterns argued from
codes of the wrong kind, and findings whose evidence denied the pattern ("no cards declined more than once").

## Caveats

* The offline check is an approximation. D did not save its tool results, so the documents it saw are approximated by the
  knowledge-base documents that name the record's codes, and its merchant tool results by every aggregate the tool can return
  for that merchant. Both are mostly supersets, which makes the offline check lenient.
* The check was written with D's outputs in view, and three rules were adjusted after looking at them: leading zeros in codes,
  durations in days not counted as retries, and "not permitted to terminal" codes accepted as merchant setup evidence. Variant E,
  a fresh run with the check in the loop and the rules frozen as they are now, is the clean test.
