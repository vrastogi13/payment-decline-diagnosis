# Merchant-level results

Merchants: 30; planted patterns: 51.

| Variant | Pattern precision | Pattern recall | Pattern F1 | False alarms on clean merchants | Action accuracy (found patterns) | Top revenue issue correct | Revenue ordering accuracy |
| --- | --- | --- | --- | --- | --- | --- | --- |
| A | 82.1% | 62.7% | 71.1% | 75.0% | 100.0% | 65.2% | 66.7% |
| D | 45.5% | 68.6% | 54.7% | 75.0% | 77.1% | 47.8% | 100.0% |
| D+check | 52.4% | 64.7% | 57.9% | 75.0% | 75.8% | 43.5% | 100.0% |

Revenue patterns are ranked by recoverable amount. Risk patterns (retrying hard declines, excessive soft retries, billing customers who revoked recurring payments) count toward detection and action accuracy but are not ranked.
