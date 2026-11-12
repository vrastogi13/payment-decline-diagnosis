"""Generate the merchant-level test: 90 days of synthetic stored-card transactions for 30 merchants,
with planted decline patterns and an answer key ranking them by impact.
Usage: python gen_merchants.py <out_dir>
Outputs: merchant_profiles.csv, merchant_transactions.csv, merchant_answer_key.csv"""
import sys, csv, random
from datetime import datetime, timedelta

OUT = sys.argv[1]
rng = random.Random(20261104)
START = datetime(2026, 7, 1)
DAYS = 90

RISK = {'retrying_hard_declines', 'excessive_soft_retries', 'revoked_still_billed'}
VISA_LIMIT = 20  # Visa: at most 20 authorization attempts per card in 30 days (decline categories 2-4)
# Pattern library. impact = declined amount the merchant could recover by fixing it.
PATTERNS = {
 'expired_card_spike':     ('expired_card', 'update_credential', 'Many stored cards have expired; enable an account updater or network tokens.'),
 'issuer_outage':          ('issuer_unavailable', 'retry_later', 'One issuer was unavailable for several hours; retry the affected payments.'),
 'retrying_hard_declines': ('lost_stolen', 'do_not_retry', 'The merchant keeps retrying declines that will never approve, risking network fees.'),
 'excessive_soft_retries': ('issuer_generic', 'do_not_retry', 'Soft declines are retried beyond the Visa limit of 20 attempts per card in 30 days.'),
 'prepaid_on_subscription':('restricted_card', 'request_new_payment', 'Prepaid or single-use cards are used for subscriptions and fail on renewal.'),
 'missing_3ds_europe':     ('authentication_required', 'retry_with_authentication', 'European payments need 3-D Secure, which the merchant is not sending.'),
 'integration_regression': ('invalid_data', 'fix_request_data', 'Format errors started after a change to the merchant integration.'),
 'merchant_setup_error':   ('merchant_config', 'check_merchant_setup', 'Declines for invalid merchant started on a specific date across many cards.'),
 'revoked_still_billed':   ('recurring_cancelled', 'stop_recurring', 'Customers who revoked recurring payments are still being billed.'),
}
MERCHANT_TYPES = [('Gym and fitness membership', 40, 90, 0.95), ('Video streaming subscription', 9, 20, 1.0),
                  ('Software subscription (SaaS)', 20, 250, 0.9), ('Utility bill payment', 50, 220, 0.9),
                  ('Online retail', 25, 300, 0.25), ('Meal-kit subscription', 55, 110, 0.85), ('Wine club subscription', 50, 160, 0.9),
                  ('Online marketplace', 15, 500, 0.2)]
ISSUERS = [f'Issuer {c}' for c in 'ABCDEFGHJK']
BASE_DECLINES = [('visa', '51', 30), ('visa', '05', 25), ('visa', '54', 8), ('visa', '14', 3), ('visa', '91', 2), ('visa', '59', 2),
                 ('mastercard', '51', 18), ('mastercard', '05', 15), ('mastercard', '54', 5), ('amex', '100', 8), ('amex', '116', 5),
                 ('discover', '05', 3)]
NET = ['visa'] * 50 + ['mastercard'] * 30 + ['amex'] * 12 + ['discover'] * 8

rows, profiles, key = [], [], []
tid = 0
def txn(m, day, card, amount, approved, net, code='', advice='', attempt=1, retry_of='', hour=None, region=None, ctype=None, recurring=True):
    global tid; tid += 1
    ts = START + timedelta(days=day, hours=hour if hour is not None else rng.randint(0, 23), minutes=rng.randint(0, 59))
    rows.append(dict(txn_id=f'T{tid:07d}', merchant_id=m['merchant_id'], timestamp=ts.isoformat(timespec='minutes'),
                     card_id=card['card_id'], issuer=card['issuer'], network=net, card_type=ctype or card['card_type'],
                     card_region=region or card['region'], transaction_type='Recurring' if recurring else 'One-time',
                     amount=f'{amount:.2f}', status='approved' if approved else 'declined', response_code=code if not approved else '00',
                     advice_code=advice, attempt_number=attempt, retry_of=retry_of))
    return f'T{tid:07d}'

for i in range(1, 31):
    mtype, lo, hi, rec_share = rng.choice(MERCHANT_TYPES)
    m = dict(merchant_id=f'M{i:03d}', merchant_type=mtype, region='Europe' if i % 4 == 0 else 'United States')
    n_cards = rng.randint(250, 600)
    cards = [dict(card_id=f'{m["merchant_id"]}-C{j:04d}', issuer=rng.choice(ISSUERS), card_type=rng.choice(['Credit', 'Credit', 'Debit']),
                  region=m['region'], net=rng.choice(NET), price=round(rng.uniform(lo, hi), 2)) for j in range(n_cards)]
    # Choose patterns: 4 clean merchants test false alarms; others get 1 to 3 patterns
    if i in (5, 12, 19, 26): chosen = []
    else:
        pool = [p for p in PATTERNS if p != 'missing_3ds_europe'] + (['missing_3ds_europe'] * 3 if m['region'] == 'Europe' else [])
        chosen = rng.sample(sorted(set(pool)), rng.choice([1, 2, 2, 3]))
        if m['region'] == 'Europe' and 'missing_3ds_europe' not in chosen: chosen[0] = 'missing_3ds_europe'
    impacts = {p: 0.0 for p in chosen}; counts = {p: 0 for p in chosen}; compliant = set()
    # Background traffic: each card billed monthly (recurring) or occasionally (one-time)
    for c in cards:
        recurring = rng.random() < rec_share
        days = [d for d in range(rng.randint(0, 29), DAYS, 30)] if recurring else sorted(rng.sample(range(DAYS), rng.randint(1, 3)))
        for d in days:
            if rng.random() < 0.06:
                net, code, _ = rng.choices(BASE_DECLINES, weights=[w for *_, w in BASE_DECLINES])[0]
                txn(m, d, c, c['price'], False, net, code, recurring=recurring)
            else:
                txn(m, d, c, c['price'], True, c['net'], recurring=recurring)
    # Planted patterns
    for p in chosen:
        k = max(15, int(n_cards * rng.uniform(0.05, 0.15)))
        affected = rng.sample(cards, k)
        if p == 'expired_card_spike':
            for c in affected:
                d = rng.randint(30, DAYS - 1)
                if c['net'] == 'mastercard': txn(m, d, c, c['price'], False, 'mastercard', '79', 'MAC 01')
                else: txn(m, d, c, c['price'], False, c['net'] if c['net'] != 'amex' else 'amex', '54' if c['net'] != 'amex' else '101')
                impacts[p] += c['price']; counts[p] += 1
        elif p == 'issuer_outage':
            iss, day, hour = rng.choice(ISSUERS), rng.randint(10, DAYS - 5), rng.randint(0, 18)
            for c in affected:
                c2 = dict(c, issuer=iss)
                txn(m, day, c2, c['price'], False, 'visa' if c['net'] == 'visa' else 'mastercard', '91', hour=hour + rng.randint(0, 5))
                impacts[p] += c['price']; counts[p] += 1
        elif p == 'retrying_hard_declines':
            for c in affected[:max(8, k // 2)]:
                d = rng.randint(5, DAYS - 10); code = rng.choice(['41', '43', '59'])
                first = txn(m, d, c, c['price'], False, 'visa' if c['net'] != 'mastercard' else 'mastercard', code)
                for a in range(2, rng.randint(4, 9)):
                    txn(m, min(DAYS - 1, d + a - 1), c, c['price'], False, 'visa' if c['net'] != 'mastercard' else 'mastercard', code, attempt=a, retry_of=first)
                    counts[p] += 1
                impacts[p] += c['price'] * 0.2  # mostly fee risk, little recoverable revenue
        elif p == 'excessive_soft_retries':
            over = 0
            for c in affected[:max(8, k // 2)]:
                d = rng.randint(0, 40)
                first = txn(m, d, c, c['price'], False, 'visa', rng.choice(['05', '51']))
                n_attempts = rng.randint(17, 26) - 1   # total attempts on this card, first one included
                for a in range(2, n_attempts + 1):
                    txn(m, min(DAYS - 1, d + a), c, c['price'], False, 'visa', '05', attempt=a, retry_of=first)
                    if n_attempts > VISA_LIMIT: counts[p] += 1
                if n_attempts > VISA_LIMIT: over += 1
                impacts[p] += c['price'] * 0.3
            if over == 0: compliant.add(p)   # every chain stayed within the Visa limit, so there is nothing to report
        elif p == 'prepaid_on_subscription':
            for c in affected:
                d = rng.randint(30, DAYS - 1); mac = rng.choice(['MAC 40', 'MAC 41'])
                txn(m, d, c, c['price'], False, 'mastercard', '05', mac, ctype='Prepaid' if mac == 'MAC 40' else 'Virtual')
                impacts[p] += c['price']; counts[p] += 1
        elif p == 'missing_3ds_europe':
            for c in affected:
                d = rng.randint(0, DAYS - 1)
                if c['net'] == 'mastercard': txn(m, d, c, c['price'], False, 'mastercard', '65', region='Europe', recurring=False)
                else: txn(m, d, c, c['price'], False, 'visa', '1A', region='Europe', recurring=False)
                impacts[p] += c['price']; counts[p] += 1
        elif p == 'integration_regression':
            start = rng.randint(40, 75)
            for c in affected:
                d = rng.randint(start, DAYS - 1); net = c['net'] if c['net'] in ('visa', 'mastercard', 'discover') else 'visa'
                txn(m, d, c, c['price'], False, net, '30'); impacts[p] += c['price']; counts[p] += 1
            m['integration_change_day'] = start
        elif p == 'merchant_setup_error':
            start = rng.randint(50, 80)
            for c in affected:
                d = rng.randint(start, DAYS - 1)
                txn(m, d, c, c['price'], False, c['net'] if c['net'] != 'amex' else 'visa', rng.choice(['03', '58']))
                impacts[p] += c['price']; counts[p] += 1
        elif p == 'revoked_still_billed':
            for c in affected[:max(6, k // 2)]:
                d = rng.randint(0, 40); code = rng.choice(['R1', 'R3'])
                for a, dd in enumerate(range(d, DAYS, 30), 1):
                    txn(m, dd, c, c['price'], False, 'visa', code, attempt=a); counts[p] += 1
                impacts[p] += c['price'] * 0.1  # cannot be recovered; the issue is billing customers who cancelled
    chosen = [q for q in chosen if q not in compliant]
    profiles.append(dict(merchant_id=m['merchant_id'], merchant_type=mtype, region=m['region'], stored_cards=n_cards,
                         planted_patterns=len(chosen)))
    # Revenue patterns are ranked by recoverable amount. Risk patterns (fees, billing customers who cancelled) are flagged, not ranked.
    revenue = sorted([q for q in chosen if q not in RISK], key=lambda q: (-impacts[q], q))
    for q in revenue + sorted(q for q in chosen if q in RISK):
        cat, act, desc = PATTERNS[q]
        key.append(dict(merchant_id=m['merchant_id'], impact_type='risk' if q in RISK else 'revenue',
                        revenue_rank=revenue.index(q) + 1 if q in revenue else '', pattern=q, category=cat, action=act,
                        affected_declines=counts[q], recoverable_amount=f'{impacts[q]:.2f}' if q not in RISK else '0.00', description=desc))
    if not chosen:
        key.append(dict(merchant_id=m['merchant_id'], impact_type='none', revenue_rank='', pattern='none', category='', action='',
                        affected_declines=0, recoverable_amount='0.00', description='Background declines only; nothing to fix.'))

rows.sort(key=lambda r: (r['merchant_id'], r['timestamp']))
for name, data in [('merchant_transactions', rows), ('merchant_profiles', profiles), ('merchant_answer_key', key)]:
    with open(f'{OUT}/{name}.csv', 'w', newline='') as f:
        w = csv.DictWriter(f, fieldnames=list(data[0])); w.writeheader(); w.writerows(data)
print(len(rows), 'transactions;', sum(1 for r in rows if r['status'] == 'declined'), 'declined;', len(profiles), 'merchants;',
      sum(1 for k in key if k['pattern'] != 'none'), 'planted patterns')
