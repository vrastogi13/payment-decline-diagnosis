# Merchant-level results

Merchants: 30; planted patterns: 51.

| Variant | Pattern precision | Pattern recall | Pattern F1 | False alarms on clean merchants | Action accuracy (found patterns) | Top revenue issue correct | Revenue ordering accuracy |
| --- | --- | --- | --- | --- | --- | --- | --- |
| A | 82.1% | 62.7% | 71.1% | 75.0% | 100.0% | 65.2% | 66.7% |
| B | n/a | 0.0% | n/a | 0.0% | n/a | 0.0% | n/a |
| C | 16.4% | 19.6% | 17.9% | 100.0% | 70.0% | 13.0% | n/a |
| D | 42.9% | 58.8% | 49.6% | 75.0% | 83.3% | 56.5% | 100.0% |

Revenue patterns are ranked by recoverable amount. Risk patterns (retrying hard declines, excessive soft retries, billing customers who revoked recurring payments) count toward detection and action accuracy but are not ranked.
