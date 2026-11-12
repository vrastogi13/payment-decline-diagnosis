# Results averaged over runs

Runs: run1, run2, run3. Each cell: mean (min to max).

## Payment-level test

| Variant | Category acc. | Action acc. | Both correct | Escalation precision | Escalation recall | Hallucination flags | Median latency (ms) | Cost per run ($) |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| A | 83.4% (83.4% to 83.4%) | 65.6% (65.6% to 65.6%) | 65.6% (65.6% to 65.6%) | 56.8% (56.8% to 56.8%) | 90.9% (90.9% to 90.9%) | 0.0% (0.0% to 0.0%) | 1.00 (1.00 to 1.00) | 0.00 (0.00 to 0.00) |
| B | 39.6% (39.2% to 39.9%) | 29.0% (28.9% to 29.1%) | 15.8% (15.6% to 16.1%) | 17.0% (11.1% to 20.0%) | 3.0% (1.8% to 3.6%) | 0.0% (0.0% to 0.0%) | 3,270.67 (1,534.00 to 5,512.50) | 0.00 (0.00 to 0.00) |
| C | 35.8% (35.7% to 35.9%) | 24.1% (23.9% to 24.6%) | 12.6% (12.3% to 12.8%) | 66.7% (66.7% to 66.7%) | 3.6% (3.6% to 3.6%) | 0.0% (0.0% to 0.0%) | 5,273.83 (3,792.00 to 8,104.00) | 0.00 (0.00 to 0.00) |
| D | 86.3% (85.9% to 86.4%) | 72.8% (72.6% to 72.9%) | 70.7% (70.4% to 70.9%) | 88.0% (86.0% to 90.0%) | 80.0% (78.2% to 81.8%) | 0.0% (0.0% to 0.0%) | 7,917.83 (4,701.00 to 13,911.00) | 0.00 (0.00 to 0.00) |

## Merchant-level test

| Variant | Pattern precision | Pattern recall | Pattern F1 | False alarms (clean) | Action accuracy | Top revenue issue |
| --- | --- | --- | --- | --- | --- | --- |
| A | 82.1% (82.1% to 82.1%) | 62.7% (62.7% to 62.7%) | 71.1% (71.1% to 71.1%) | 75.0% (75.0% to 75.0%) | 100.0% (100.0% to 100.0%) | 65.2% (65.2% to 65.2%) |
| B | n/a | 0.0% (0.0% to 0.0%) | n/a | 0.0% (0.0% to 0.0%) | n/a | 0.0% (0.0% to 0.0%) |
| C | 18.8% (16.4% to 20.4%) | 20.3% (19.6% to 21.6%) | 19.5% (17.9% to 20.6%) | 100.0% (100.0% to 100.0%) | 71.2% (63.6% to 80.0%) | 13.0% (13.0% to 13.0%) |
| D | 43.3% (39.5% to 45.5%) | 63.4% (58.8% to 68.6%) | 51.5% (47.2% to 54.7%) | 75.0% (75.0% to 75.0%) | 75.2% (73.3% to 77.1%) | 36.2% (30.4% to 47.8%) |

## Run-to-run consistency (payment test)

| Variant | Scenarios with the same action in every run |
| --- | --- |
| A | 100.0% |
| B | 99.0% |
| C | 97.7% |
| D | 98.7% |
