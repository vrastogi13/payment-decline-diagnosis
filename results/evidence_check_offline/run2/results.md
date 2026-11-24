# Benchmark results

Scenarios: 398. Accuracy shown with 95% bootstrap confidence intervals.

| Variant | Category acc. | Action acc. | Both correct | Category macro-F1 | Action macro-F1 | Escalation precision | Escalation recall | Hallucination flags | Median latency (ms) | Total cost ($) | Missing |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| D | 85.9% (82.4% to 89.2%) | 72.6% (68.1% to 76.9%) | 70.4% (65.6% to 74.6%) | 0.821 | 0.683 | 86.0% | 78.2% | 0.0% | 4701 | 0.00 | 0 |
| D+check | 85.9% (82.4% to 89.2%) | 71.9% (67.3% to 76.4%) | 69.8% (65.3% to 74.4%) | 0.821 | 0.699 | 71.7% | 78.2% | 0.0% | 4701 | 0.00 | 0 |

## Action accuracy by difficulty

| Variant | Standard | Hard |
| --- | --- | --- |
| D | 79.0% | 66.2% |
| D+check | 78.5% | 65.2% |

## Action accuracy on hard-case types

| Hard-case type | n | D | D+check |
| --- | --- | --- | --- |
| Advice code allows later retry | 8 | 62.5% | 62.5% |
| Advice code forbids retry | 20 | 60.0% | 50.0% |
| Advice code sets retry wait | 14 | 71.4% | 71.4% |
| Card replaced by issuer | 4 | 100.0% | 100.0% |
| Card type cannot support recurring | 4 | 50.0% | 50.0% |
| Cardholder cancelled recurring payments | 6 | 100.0% | 100.0% |
| Code meaning depends on region | 6 | 50.0% | 50.0% |
| Near retry limit, retry still allowed | 20 | 85.0% | 85.0% |
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
| D vs D+check | 1 | 4 | 0.3750 |

Hallucination flags are automated: a code is flagged when the explanation cites one that is neither in the scenario nor in the knowledge base for that network. Review a sample by hand before reporting the rate.
