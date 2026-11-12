# Benchmark results

Scenarios: 398. Accuracy shown with 95% bootstrap confidence intervals.

| Variant | Category acc. | Action acc. | Both correct | Category macro-F1 | Action macro-F1 | Escalation precision | Escalation recall | Hallucination flags | Median latency (ms) | Total cost ($) | Missing |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| A | 83.4% (79.9% to 86.9%) | 65.6% (60.8% to 69.8%) | 65.6% (60.8% to 69.8%) | 0.866 | 0.662 | 56.8% | 90.9% | 0.0% | 1 | 0.00 | 0 |
| B | 39.7% (35.4% to 44.5%) | 28.9% (24.4% to 33.4%) | 15.8% (12.3% to 19.6%) | 0.301 | 0.163 | 11.1% | 1.8% | 0.0% | 5512 | 0.00 | 0 |
| C | 35.7% (31.4% to 40.2%) | 23.9% (19.6% to 28.1%) | 12.3% (9.3% to 15.6%) | 0.203 | 0.089 | 66.7% | 3.6% | 0.0% | 8104 | 0.00 | 0 |
| D | 86.4% (82.9% to 89.7%) | 72.9% (68.3% to 77.1%) | 70.9% (66.1% to 75.1%) | 0.823 | 0.680 | 88.0% | 80.0% | 0.0% | 5142 | 0.00 | 0 |

## Action accuracy by difficulty

| Variant | Standard | Hard |
| --- | --- | --- |
| A | 100.0% | 30.8% |
| B | 24.0% | 33.8% |
| C | 22.5% | 25.3% |
| D | 79.5% | 66.2% |

## Action accuracy on hard-case types

| Hard-case type | n | A | B | C | D |
| --- | --- | --- | --- | --- | --- |
| Advice code allows later retry | 8 | 0.0% | 100.0% | 75.0% | 62.5% |
| Advice code forbids retry | 20 | 20.0% | 5.0% | 0.0% | 55.0% |
| Advice code sets retry wait | 14 | 28.6% | 85.7% | 78.6% | 71.4% |
| Card replaced by issuer | 4 | 100.0% | 25.0% | 0.0% | 100.0% |
| Card type cannot support recurring | 4 | 0.0% | 0.0% | 0.0% | 50.0% |
| Cardholder cancelled recurring payments | 6 | 0.0% | 50.0% | 50.0% | 100.0% |
| Code meaning depends on region | 6 | 50.0% | 16.7% | 50.0% | 50.0% |
| Near retry limit, retry still allowed | 20 | 100.0% | 90.0% | 35.0% | 90.0% |
| Processor code needs translation | 45 | 0.0% | 22.2% | 24.4% | 86.7% |
| Recurring authorization revoked | 6 | 100.0% | 33.3% | 33.3% | 66.7% |
| Repeated system or format failure needs escalation | 6 | 100.0% | 16.7% | 0.0% | 66.7% |
| Retry limit reached | 20 | 15.0% | 0.0% | 0.0% | 5.0% |
| Sources disagree on advice code | 2 | 0.0% | 0.0% | 0.0% | 100.0% |
| Stale credential with update available | 16 | 50.0% | 37.5% | 18.8% | 50.0% |
| Token setup problem | 3 | 0.0% | 0.0% | 0.0% | 33.3% |
| Visa category allows later retry | 4 | 0.0% | 100.0% | 100.0% | 100.0% |
| Visa category forbids retry | 8 | 0.0% | 0.0% | 0.0% | 75.0% |
| Visa category requires data fix | 6 | 50.0% | 0.0% | 0.0% | 50.0% |

## Pairwise significance (exact McNemar test on action correctness)

| Comparison | Only second correct | Only first correct | p-value |
| --- | --- | --- | --- |
| A vs B | 38 | 184 | 0.0000 |
| A vs C | 37 | 203 | 0.0000 |
| A vs D | 79 | 50 | 0.0134 |
| B vs C | 11 | 31 | 0.0029 |
| B vs D | 192 | 17 | 0.0000 |
| C vs D | 211 | 16 | 0.0000 |

Hallucination flags are automated: a code is flagged when the explanation cites one that is neither in the scenario nor in the knowledge base for that network. Review a sample by hand before reporting the rate.
