# Benchmark results

Scenarios: 398. Accuracy shown with 95% bootstrap confidence intervals.

| Variant | Category acc. | Action acc. | Both correct | Category macro-F1 | Action macro-F1 | Escalation precision | Escalation recall | Hallucination flags | Median latency (ms) | Total cost ($) | Missing |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| D | 86.4% (82.9% to 89.7%) | 72.9% (68.3% to 77.1%) | 70.9% (66.1% to 75.1%) | 0.823 | 0.680 | 88.0% | 80.0% | 0.0% | 5142 | 0.00 | 0 |
| D+check | 86.4% (82.9% to 89.7%) | 71.9% (67.3% to 76.4%) | 70.4% (65.6% to 74.9%) | 0.823 | 0.681 | 74.6% | 80.0% | 0.0% | 5142 | 0.00 | 0 |

## Action accuracy by difficulty

| Variant | Standard | Hard |
| --- | --- | --- |
| D | 79.5% | 66.2% |
| D+check | 78.5% | 65.2% |

## Action accuracy on hard-case types

| Hard-case type | n | D | D+check |
| --- | --- | --- | --- |
| Advice code allows later retry | 8 | 62.5% | 62.5% |
| Advice code forbids retry | 20 | 55.0% | 45.0% |
| Advice code sets retry wait | 14 | 71.4% | 71.4% |
| Card replaced by issuer | 4 | 100.0% | 100.0% |
| Card type cannot support recurring | 4 | 50.0% | 50.0% |
| Cardholder cancelled recurring payments | 6 | 100.0% | 100.0% |
| Code meaning depends on region | 6 | 50.0% | 50.0% |
| Near retry limit, retry still allowed | 20 | 90.0% | 90.0% |
| Processor code needs translation | 45 | 86.7% | 86.7% |
| Recurring authorization revoked | 6 | 66.7% | 66.7% |
| Repeated system or format failure needs escalation | 6 | 66.7% | 66.7% |
| Retry limit reached | 20 | 5.0% | 5.0% |
| Sources disagree on advice code | 2 | 100.0% | 100.0% |
| Stale credential with update available | 16 | 50.0% | 50.0% |
| Token setup problem | 3 | 33.3% | 33.3% |
| Visa category allows later retry | 4 | 100.0% | 100.0% |
| Visa category forbids retry | 8 | 75.0% | 75.0% |
| Visa category requires data fix | 6 | 50.0% | 50.0% |

## Pairwise significance (exact McNemar test on action correctness)

| Comparison | Only second correct | Only first correct | p-value |
| --- | --- | --- | --- |
| D vs D+check | 0 | 4 | 0.1250 |

Hallucination flags are automated: a code is flagged when the explanation cites one that is neither in the scenario nor in the knowledge base for that network. Review a sample by hand before reporting the rate.
