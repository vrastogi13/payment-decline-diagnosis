# Merchant-level results

Merchants: 30; planted patterns: 51.

| Variant | Pattern precision | Pattern recall | Pattern F1 | False alarms on clean merchants | Action accuracy (found patterns) | Top revenue issue correct | Revenue ordering accuracy |
| --- | --- | --- | --- | --- | --- | --- | --- |
| A | 82.1% | 62.7% | 71.1% | 75.0% | 100.0% | 65.2% | 66.7% |
| B | n/a | 0.0% | n/a | 0.0% | n/a | 0.0% | n/a |
| C | 19.6% | 21.6% | 20.6% | 100.0% | 63.6% | 13.0% | n/a |
| D | 41.1% | 58.8% | 48.4% | 75.0% | 86.7% | 39.1% | 100.0% |

Revenue patterns are ranked by recoverable amount. Risk patterns (retrying hard declines, excessive soft retries, billing customers who revoked recurring payments) count toward detection and action accuracy but are not ranked.
