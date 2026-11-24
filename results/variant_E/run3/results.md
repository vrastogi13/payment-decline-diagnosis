# Benchmark results

Scenarios: 398. Accuracy shown with 95% bootstrap confidence intervals.

| Variant | Category acc. | Action acc. | Both correct | Category macro-F1 | Action macro-F1 | Escalation precision | Escalation recall | Hallucination flags | Median latency (ms) | Total cost ($) | Missing |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| A | 83.4% (79.9% to 86.9%) | 65.6% (60.8% to 69.8%) | 65.6% (60.8% to 69.8%) | 0.866 | 0.662 | 56.8% | 90.9% | 0.0% | 1 | 0.00 | 0 |
| D | 86.4% (82.9% to 89.7%) | 72.9% (68.3% to 77.1%) | 70.9% (66.1% to 75.1%) | 0.823 | 0.680 | 88.0% | 80.0% | 0.0% | 5142 | 0.00 | 0 |
| E_model | 86.2% (82.7% to 89.4%) | 77.4% (72.9% to 81.2%) | 73.4% (68.8% to 77.4%) | 0.833 | 0.715 | 85.2% | 83.6% | 0.0% | 11056 | 0.00 | 0 |
| E | 86.2% (82.7% to 89.4%) | 73.9% (69.3% to 78.1%) | 71.4% (66.8% to 75.6%) | 0.833 | 0.637 | 63.0% | 83.6% | 0.0% | 11056 | 0.00 | 0 |

## Action accuracy by difficulty

| Variant | Standard | Hard |
| --- | --- | --- |
| A | 100.0% | 30.8% |
| D | 79.5% | 66.2% |
| E_model | 83.0% | 71.7% |
| E | 78.5% | 69.2% |

## Action accuracy on hard-case types

| Hard-case type | n | A | D | E_model | E |
| --- | --- | --- | --- | --- | --- |
| Advice code allows later retry | 8 | 0.0% | 62.5% | 62.5% | 62.5% |
| Advice code forbids retry | 20 | 20.0% | 55.0% | 70.0% | 70.0% |
| Advice code sets retry wait | 14 | 28.6% | 71.4% | 71.4% | 71.4% |
| Card replaced by issuer | 4 | 100.0% | 100.0% | 100.0% | 100.0% |
| Card type cannot support recurring | 4 | 0.0% | 50.0% | 50.0% | 50.0% |
| Cardholder cancelled recurring payments | 6 | 0.0% | 100.0% | 100.0% | 66.7% |
| Code meaning depends on region | 6 | 50.0% | 50.0% | 50.0% | 50.0% |
| Near retry limit, retry still allowed | 20 | 100.0% | 90.0% | 100.0% | 100.0% |
| Processor code needs translation | 45 | 0.0% | 86.7% | 91.1% | 88.9% |
| Recurring authorization revoked | 6 | 100.0% | 66.7% | 66.7% | 66.7% |
| Repeated system or format failure needs escalation | 6 | 100.0% | 66.7% | 66.7% | 66.7% |
| Retry limit reached | 20 | 15.0% | 5.0% | 10.0% | 5.0% |
| Sources disagree on advice code | 2 | 0.0% | 100.0% | 100.0% | 100.0% |
| Stale credential with update available | 16 | 50.0% | 50.0% | 50.0% | 50.0% |
| Token setup problem | 3 | 0.0% | 33.3% | 66.7% | 33.3% |
| Visa category allows later retry | 4 | 0.0% | 100.0% | 100.0% | 100.0% |
| Visa category forbids retry | 8 | 0.0% | 75.0% | 100.0% | 100.0% |
| Visa category requires data fix | 6 | 50.0% | 50.0% | 50.0% | 50.0% |

## Pairwise significance (exact McNemar test on action correctness)

| Comparison | Only second correct | Only first correct | p-value |
| --- | --- | --- | --- |
| A vs D | 79 | 50 | 0.0134 |
| A vs E_model | 87 | 40 | 0.0000 |
| A vs E | 82 | 49 | 0.0050 |
| D vs E_model | 18 | 0 | 0.0000 |
| D vs E | 16 | 12 | 0.5716 |
| E_model vs E | 0 | 14 | 0.0001 |

Hallucination flags are automated: a code is flagged when the explanation cites one that is neither in the scenario nor in the knowledge base for that network. Review a sample by hand before reporting the rate.
