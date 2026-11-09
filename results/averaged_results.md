# Results averaged over runs

Runs: run1, run2, run3. Each cell: mean (min to max).

## Payment-level test

| Variant | Category acc. | Action acc. | Both correct | Escalation precision | Escalation recall | Hallucination flags | Median latency (ms) | Cost per run ($) |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| A | 83.4% (83.4% to 83.4%) | 60.8% (60.8% to 60.8%) | 60.8% (60.8% to 60.8%) | 56.8% (56.8% to 56.8%) | 90.9% (90.9% to 90.9%) | 0.0% (0.0% to 0.0%) | 1.00 (1.00 to 1.00) | 0.00 (0.00 to 0.00) |
| B | 39.6% (39.2% to 39.9%) | 24.5% (24.4% to 24.6%) | 15.1% (14.8% to 15.3%) | 17.0% (11.1% to 20.0%) | 3.0% (1.8% to 3.6%) | 0.0% (0.0% to 0.0%) | 3,270.67 (1,534.00 to 5,512.50) | 0.00 (0.00 to 0.00) |
| C | 35.8% (35.7% to 35.9%) | 22.4% (22.1% to 22.9%) | 11.8% (11.6% to 12.1%) | 66.7% (66.7% to 66.7%) | 3.6% (3.6% to 3.6%) | 0.0% (0.0% to 0.0%) | 5,273.83 (3,792.00 to 8,104.00) | 0.00 (0.00 to 0.00) |
| D | 86.2% (86.2% to 86.2%) | 68.3% (68.1% to 68.6%) | 66.2% (66.1% to 66.3%) | 86.8% (86.3% to 88.0%) | 80.0% (80.0% to 80.0%) | 0.0% (0.0% to 0.0%) | 5,710.17 (3,713.50 to 7,134.00) | 0.00 (0.00 to 0.00) |

## Merchant-level test

| Variant | Pattern precision | Pattern recall | Pattern F1 | False alarms (clean) | Action accuracy | Top revenue issue |
| --- | --- | --- | --- | --- | --- | --- |
| A | 82.1% (82.1% to 82.1%) | 62.7% (62.7% to 62.7%) | 71.1% (71.1% to 71.1%) | 75.0% (75.0% to 75.0%) | 100.0% (100.0% to 100.0%) | 65.2% (65.2% to 65.2%) |
| B | n/a | 0.0% (0.0% to 0.0%) | n/a | 0.0% (0.0% to 0.0%) | n/a | 0.0% (0.0% to 0.0%) |
| C | 18.8% (16.4% to 20.4%) | 20.3% (19.6% to 21.6%) | 19.5% (17.9% to 20.6%) | 100.0% (100.0% to 100.0%) | 71.2% (63.6% to 80.0%) | 13.0% (13.0% to 13.0%) |
| D | 41.8% (41.1% to 42.9%) | 59.5% (58.8% to 60.8%) | 49.1% (48.4% to 49.6%) | 75.0% (75.0% to 75.0%) | 82.5% (77.4% to 86.7%) | 47.8% (39.1% to 56.5%) |

## Run-to-run consistency (payment test)

| Variant | Scenarios with the same action in every run |
| --- | --- |
| A | 100.0% |
| B | 99.0% |
| C | 97.7% |
| D | 99.2% |
