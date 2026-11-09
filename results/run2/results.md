# Benchmark results

Scenarios: 398. Accuracy shown with 95% bootstrap confidence intervals.

| Variant | Category acc. | Action acc. | Both correct | Category macro-F1 | Action macro-F1 | Escalation precision | Escalation recall | Hallucination flags | Median latency (ms) | Total cost ($) | Missing |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| A | 83.4% (79.9% to 86.9%) | 60.8% (56.0% to 65.3%) | 60.8% (56.0% to 65.3%) | 0.866 | 0.639 | 56.8% | 90.9% | 0.0% | 1 | 0.00 | 0 |
| B | 39.9% (35.7% to 44.7%) | 24.4% (20.4% to 28.9%) | 15.3% (12.1% to 19.1%) | 0.302 | 0.155 | 20.0% | 3.6% | 0.0% | 2766 | 0.00 | 0 |
| C | 35.7% (31.4% to 40.2%) | 22.1% (18.1% to 26.1%) | 11.8% (8.5% to 15.1%) | 0.203 | 0.089 | 66.7% | 3.6% | 0.0% | 3792 | 0.00 | 0 |
| D | 86.2% (82.7% to 89.4%) | 68.6% (63.8% to 73.1%) | 66.3% (61.6% to 71.1%) | 0.823 | 0.667 | 88.0% | 80.0% | 0.0% | 7134 | 0.00 | 0 |

## Action accuracy by difficulty

| Variant | Standard | Hard |
| --- | --- | --- |
| A | 100.0% | 21.2% |
| B | 24.0% | 24.7% |
| C | 22.5% | 21.7% |
| D | 79.5% | 57.6% |

## Action accuracy on hard-case types

| Hard-case type | n | A | B | C | D |
| --- | --- | --- | --- | --- | --- |
| Advice code allows later retry | 8 | 0.0% | 100.0% | 62.5% | 62.5% |
| Advice code forbids retry | 20 | 20.0% | 5.0% | 0.0% | 60.0% |
| Advice code sets retry wait | 14 | 28.6% | 85.7% | 78.6% | 71.4% |
| Card replaced by issuer | 4 | 100.0% | 25.0% | 0.0% | 100.0% |
| Card type cannot support recurring | 4 | 0.0% | 0.0% | 0.0% | 50.0% |
| Cardholder cancelled recurring payments | 6 | 0.0% | 50.0% | 50.0% | 100.0% |
| Code meaning depends on region | 6 | 50.0% | 16.7% | 50.0% | 50.0% |
| Processor code needs translation | 45 | 0.0% | 22.2% | 26.7% | 86.7% |
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
| A vs B | 38 | 183 | 0.0000 |
| A vs C | 37 | 191 | 0.0000 |
| A vs D | 80 | 49 | 0.0080 |
| B vs C | 12 | 21 | 0.1628 |
| B vs D | 192 | 16 | 0.0000 |
| C vs D | 200 | 15 | 0.0000 |

Hallucination flags are automated: a code is flagged when the explanation cites one that is neither in the scenario nor in the knowledge base for that network. Review a sample by hand before reporting the rate.
