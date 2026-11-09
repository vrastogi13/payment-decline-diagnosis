# Benchmark results

Scenarios: 398. Accuracy shown with 95% bootstrap confidence intervals.

| Variant | Category acc. | Action acc. | Both correct | Category macro-F1 | Action macro-F1 | Escalation precision | Escalation recall | Hallucination flags | Median latency (ms) | Total cost ($) | Missing |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| A | 83.4% (79.9% to 86.9%) | 60.8% (56.0% to 65.3%) | 60.8% (56.0% to 65.3%) | 0.866 | 0.639 | 56.8% | 90.9% | 0.0% | 1 | 0.00 | 0 |
| B | 39.2% (34.7% to 44.0%) | 24.6% (20.6% to 28.9%) | 14.8% (11.6% to 18.3%) | 0.296 | 0.163 | 20.0% | 3.6% | 0.0% | 1534 | 0.00 | 0 |
| C | 35.9% (31.7% to 40.5%) | 22.9% (18.8% to 27.1%) | 12.1% (8.8% to 15.3%) | 0.205 | 0.094 | 66.7% | 3.6% | 0.0% | 3926 | 0.00 | 0 |
| D | 86.2% (82.7% to 89.4%) | 68.3% (63.6% to 72.9%) | 66.3% (61.6% to 71.1%) | 0.823 | 0.665 | 86.3% | 80.0% | 0.0% | 6283 | 0.00 | 0 |

## Action accuracy by difficulty

| Variant | Standard | Hard |
| --- | --- | --- |
| A | 100.0% | 21.2% |
| B | 24.5% | 24.7% |
| C | 23.0% | 22.7% |
| D | 79.0% | 57.6% |

## Action accuracy on hard-case types

| Hard-case type | n | A | B | C | D |
| --- | --- | --- | --- | --- | --- |
| Advice code allows later retry | 8 | 0.0% | 100.0% | 75.0% | 62.5% |
| Advice code forbids retry | 20 | 20.0% | 5.0% | 0.0% | 60.0% |
| Advice code sets retry wait | 14 | 28.6% | 85.7% | 78.6% | 71.4% |
| Card replaced by issuer | 4 | 100.0% | 25.0% | 0.0% | 100.0% |
| Card type cannot support recurring | 4 | 0.0% | 0.0% | 0.0% | 50.0% |
| Cardholder cancelled recurring payments | 6 | 0.0% | 50.0% | 50.0% | 100.0% |
| Code meaning depends on region | 6 | 50.0% | 16.7% | 50.0% | 50.0% |
| Processor code needs translation | 45 | 0.0% | 22.2% | 28.9% | 86.7% |
| Recurring authorization revoked | 6 | 100.0% | 33.3% | 33.3% | 66.7% |
| Repeated system or format failure needs escalation | 6 | 100.0% | 16.7% | 0.0% | 66.7% |
| Retry limit reached | 40 | 10.0% | 0.0% | 0.0% | 2.5% |
| Sources disagree on advice code | 2 | 0.0% | 0.0% | 0.0% | 100.0% |
| Stale credential with update available | 16 | 50.0% | 37.5% | 18.8% | 50.0% |
| Token setup problem | 3 | 0.0% | 0.0% | 0.0% | 33.3% |
| Visa category allows later retry | 4 | 0.0% | 100.0% | 100.0% | 100.0% |
| Visa category forbids retry | 8 | 0.0% | 0.0% | 0.0% | 75.0% |
| Visa category requires data fix | 6 | 50.0% | 0.0% | 0.0% | 50.0% |

## Pairwise significance (exact McNemar test on action correctness)

| Comparison | Only second correct | Only first correct | p-value |
| --- | --- | --- | --- |
| A vs B | 38 | 182 | 0.0000 |
| A vs C | 39 | 190 | 0.0000 |
| A vs D | 80 | 50 | 0.0107 |
| B vs C | 13 | 20 | 0.2962 |
| B vs D | 190 | 16 | 0.0000 |
| C vs D | 198 | 17 | 0.0000 |

Hallucination flags are automated: a code is flagged when the explanation cites one that is neither in the scenario nor in the knowledge base for that network. Review a sample by hand before reporting the rate.
