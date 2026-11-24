# Merchant-level results

Merchants: 30; planted patterns: 51.

| Variant | Pattern precision | Pattern recall | Pattern F1 | False alarms on clean merchants | Action accuracy (found patterns) | Top revenue issue correct | Revenue ordering accuracy |
| --- | --- | --- | --- | --- | --- | --- | --- |
| A | 82.1% | 62.7% | 71.1% | 75.0% | 100.0% | 65.2% | 66.7% |
| D | 39.5% | 58.8% | 47.2% | 75.0% | 73.3% | 30.4% | 0.0% |
| D+check | 51.8% | 56.9% | 54.2% | 75.0% | 72.4% | 34.8% | 0.0% |

Revenue patterns are ranked by recoverable amount. Risk patterns (retrying hard declines, excessive soft retries, billing customers who revoked recurring payments) count toward detection and action accuracy but are not ranked.
