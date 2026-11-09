"""Generate the payment-level decline benchmark from the knowledge base (version 2).
Usage: python gen_benchmark.py <schema.sql> <seed.sql> <out_dir>
Adds over version 1: merchant-written problem reports (no codes), 30-day retry counts,
processor-code inputs, and more advice-code overrides. Roughly half the cases are hard."""
import sys, json, random, csv
import duckdb

SCHEMA, SEED, OUT = sys.argv[1], sys.argv[2], sys.argv[3]
rng = random.Random(20261103)
VISA_REATTEMPT_LIMIT = 15  # Visa: at most 15 reattempts in 30 days for retryable declines (verify against Visa's published rules)

db = duckdb.connect(); db.execute(open(SCHEMA).read()); db.execute(open(SEED).read())
cols = [d[0] for d in db.execute('select * from decline_code limit 0').description]
codes = {r[0]: dict(zip(cols, r)) for r in db.execute('select * from decline_code').fetchall()}
rcols = [d[0] for d in db.execute('select * from decision_rule limit 0').description]
rules = [dict(zip(rcols, r)) for r in db.execute('select * from decision_rule').fetchall()]
pmap = db.execute('select processor_code, processor_label, code_id from processor_code_map').fetchall()

def cnp(c): return not c['merchant_explanation'].startswith('Card-present')
resp_codes = [c for c in codes.values() if c['code_system'] == 'iso_response' and cnp(c)]

MERCHANTS = [('Gym and fitness membership', 25, 120), ('Video streaming subscription', 8, 25), ('Software subscription (SaaS)', 15, 300),
             ('Utility bill payment', 40, 250), ('Online retail', 20, 400), ('Meal-kit subscription', 50, 110),
             ('Wine club subscription', 45, 180), ('Lawn care service', 60, 200), ('Medical supplies (recurring)', 30, 150),
             ('Online marketplace', 10, 600)]
RECURRING_TYPES = ['Recurring renewal', 'First recurring payment', 'Installment (merchant-initiated)']
ONE_TIME = 'One-time charge on a stored card'
QUESTIONS = {
 True: ["The merchant says this customer's renewal failed. Why did it fail, and what should the merchant do next?",
        'A subscription payment was declined. What went wrong and should the merchant retry?',
        'The customer is asking why their membership payment did not go through. What happened and what is the next step?'],
 False: ["A charge on the customer's saved card was declined. Why, and what should the merchant do?",
         'The merchant wants to know why this stored-card payment failed and whether to try again.',
         "Support ticket: payment declined on a returning customer's saved card. Diagnose it and recommend the next step."],
}
# What a merchant or account manager would actually write: symptoms, never codes. Some are deliberately misleading.
REPORTS = {
 'insufficient_funds': ['The customer insists they have money in the account and that the card works elsewhere.',
                        'Payment failed near the end of the month. The customer has paid on time before.',
                        'Declined on the renewal date; the customer says they will look into it.'],
 'expired_card': ['The card was saved a few years ago and the renewal suddenly started failing this month.',
                  'This customer has been billed fine for a long time and nothing changed on our side.',
                  'Customer says they recently received a new card in the mail but did not update anything.'],
 'invalid_account': ['The customer typed the card in themselves at signup.', 'First charge on a newly saved card failed.',
                     'Customer swears the card is valid.'],
 'lost_stolen': ['The card was working last month and the customer has not said anything.',
                 'Customer is surprised and says nothing is wrong with their card.'],
 'fraud_suspected': ['A larger than usual order from a returning customer was declined.',
                     "The customer says their bank didn't contact them about anything."],
 'issuer_generic': ['Declined with no clear reason. The customer says their bank sees no problem.',
                    "We don't understand why this keeps failing; everything looks normal.",
                    'Customer called the bank, and the bank said to just try again.'],
 'authentication_required': ['European customer; the payment was declined during checkout.',
                             'The first payment for a new customer in Europe failed.'],
 'limit_exceeded': ['The customer tried a bigger purchase than usual.', 'Customer has made several purchases today.'],
 'restricted_card': ['The customer is paying with a card issued abroad.', 'The customer is using a corporate card.',
                     'Customer says this card is a gift or prepaid card.'],
 'invalid_data': ['This started after we updated our checkout integration.', 'Only some payments fail; others go through fine.'],
 'issuer_unavailable': ['The payment failed overnight. The customer never had problems before.',
                        'Several payments failed in a short window last night.'],
 'merchant_config': ["Several different customers' cards are failing at this merchant since this morning.",
                     'The merchant recently changed their business setup with us.'],
 'recurring_cancelled': ["The customer's membership payment failed and they haven't contacted us.",
                         'The customer may have asked their bank to stop the payments; we are not sure.'],
}
COMMON = {'05': 6, '51': 6, '54': 4, '14': 2, '91': 2, '59': 2, '41': 1.5, '43': 1.5, '61': 1.5, '100': 5, '116': 3, '101': 3}
NET_SHARE = {'visa': 0.50, 'mastercard': 0.30, 'amex': 0.12, 'discover': 0.08}
_tot = {}
for x in resp_codes: _tot[x['network']] = _tot.get(x['network'], 0) + COMMON.get(x['code'], 1.0)
def weight(c): return NET_SHARE[c['network']] * COMMON.get(c['code'], 1.0) / _tot[c['network']]

RETRY = {'do_not_retry': 'no', 'stop_recurring': 'no', 'request_new_payment': 'no', 'contact_issuer': 'no',
         'retry_later': 'yes', 'retry_with_authentication': 'yes', 'update_credential': 'conditional',
         'fix_request_data': 'conditional', 'check_merchant_setup': 'no', 'escalate_to_engineer': 'no'}

def answer(s):
    resp = codes[s['response_code_id']]
    adv = codes.get(s['advice_code_id']) if s['advice_code_id'] else None
    cat, action, esc = resp['category'], resp['primary_action'], resp['escalate_to_human']
    retry, guidance, rule_used = resp['retryable'], resp['retry_guidance'] or '', 'response code'
    best = None
    for r in rules:
        if r['response_code_id'] not in (None, resp['code_id']): continue
        if r['advice_code_id'] is not None and r['advice_code_id'] != s['advice_code_id']: continue
        if r['response_code_id'] is None and r['advice_code_id'] is None: continue
        if r['is_recurring'] is not None and r['is_recurring'] != s['recurring']: continue
        if best is None or r['priority'] > best['priority']: best = r
    if best:
        action, rule_used = best['resulting_action'], best['rule_id']; retry = RETRY[action]
        if adv and best['advice_code_id'] == adv['code_id'] and adv['category'] in ('recurring_cancelled', 'expired_card', 'restricted_card'):
            cat = adv['category']
        if adv and adv['retry_guidance']: guidance = adv['retry_guidance']
    elif adv:
        action, retry, rule_used = adv['primary_action'], RETRY[adv['primary_action']], 'advice code'
        guidance = adv['retry_guidance'] or guidance
    if resp['code_id'] == 'mastercard:iso_response:65' and s['card_region'] != 'Europe':
        cat, action, retry, guidance, rule_used = 'limit_exceeded', 'retry_later', 'yes', 'Retry after the limit resets.', 'region rule (MC 65 outside Europe)'
    # Visa reattempt limit overrides any retry advice
    if s['network'] == 'visa' and s['retries_last_30_days'] >= VISA_REATTEMPT_LIMIT and action in ('retry_later', 'contact_issuer') and retry != 'no':
        action, retry, guidance = 'do_not_retry', 'no', 'Visa reattempt limit reached for this card in 30 days.'
        rule_used += ' + Visa reattempt limit'
    if adv: esc = esc or adv['escalate_to_human']
    if s.get('repeat_failure') and cat in ('invalid_data', 'merchant_config', 'issuer_unavailable'):
        esc, rule_used = True, rule_used + ' + repeated failure'
    if s['code_source'] == 'processor': rule_used = 'processor code mapped to network meaning; ' + rule_used
    return dict(answer_category=cat, answer_action=action, answer_retry=retry, answer_escalate='Yes' if esc else 'No',
                answer_retry_guidance=guidance, answer_rule=rule_used,
                answer_explanation=resp['merchant_explanation'] + (f" Advice code: {adv['merchant_explanation']}" if adv else ''),
                answer_cardholder_message=resp['cardholder_message'])

def base(resp, recurring=None, region='United States', card_type=None):
    m, lo, hi = rng.choice(MERCHANTS)
    if recurring is None: recurring = rng.random() < 0.65
    attempt = rng.choice([1, 1, 1, 2, 2, 3])
    prev = 'None (first attempt)' if attempt == 1 else rng.choice(['Declined with same code', 'Declined with same code', 'Approved last cycle'])
    return dict(network=resp['network'], response_code_id=resp['code_id'], response_code=resp['code'], code_source='network',
                advice_code_id=None, advice_code='', recurring=recurring,
                transaction_type=rng.choice(RECURRING_TYPES) if recurring else ONE_TIME, merchant_type=m,
                amount=f'{rng.uniform(lo, hi):.2f}', currency='EUR' if region == 'Europe' else 'USD',
                card_type=card_type or rng.choice(['Credit', 'Credit', 'Debit']), card_region=region,
                attempt_number=attempt, previous_attempt=prev, retries_last_30_days=rng.randint(0, attempt + 2),
                repeat_failure=False, difficulty='standard', hard_case_type='', report_override='')

def pick(net, code, system='iso_response'): return codes[f'{net}:{system}:{code}']
def setadv(s, cid, label): s['advice_code_id'] = cid; s['advice_code'] = label

scen = []
def hard(s, kind): s['difficulty'] = 'hard'; s['hard_case_type'] = kind; scen.append(s)
SKIP = {'visa:iso_response:R0', 'visa:iso_response:R1', 'visa:iso_response:R3', 'mastercard:iso_response:65', 'mastercard:iso_response:79'}

# ---- standard cases (200) ----
while sum(1 for s in scen if s['difficulty'] == 'standard') < 200:
    resp = rng.choices(resp_codes, weights=[weight(c) for c in resp_codes])[0]
    if resp['code_id'] in SKIP: continue
    scen.append(base(resp, region='Europe' if resp['category'] == 'authentication_required' else 'United States'))

# ---- hard cases from version 1 ----
for _ in range(12):
    s = base(pick('mastercard', rng.choice(['51', '05', '61']))); setadv(s, 'mastercard:merchant_advice:03', 'MAC 03')
    if s['attempt_number'] == 1: s['attempt_number'], s['previous_attempt'] = 2, 'Declined with same code'
    hard(s, 'Advice code forbids retry')
for _ in range(10):
    n = rng.randint(24, 30); s = base(pick('mastercard', rng.choice(['05', '51']))); setadv(s, f'mastercard:merchant_advice:{n}', f'MAC {n}')
    hard(s, 'Advice code sets retry wait')
for _ in range(8):
    s = base(pick('visa', rng.choice(['05', '51']))); setadv(s, 'visa:merchant_advice:1', 'Visa category 1'); hard(s, 'Visa category forbids retry')
for _ in range(4):
    s = base(pick('visa', '05')); setadv(s, 'visa:merchant_advice:2', 'Visa category 2'); hard(s, 'Visa category allows later retry')
for code in ['R0', 'R1', 'R3', 'R1', 'R3', 'R0']:
    hard(base(pick('visa', code), recurring=True), 'Recurring authorization revoked')
for _ in range(6):
    s = base(pick('mastercard', '05'), recurring=True); setadv(s, 'mastercard:merchant_advice:21', 'MAC 21'); hard(s, 'Cardholder cancelled recurring payments')
for _ in range(8):
    s = base(pick('mastercard', '79'), recurring=True); setadv(s, 'mastercard:merchant_advice:01', 'MAC 01'); hard(s, 'Stale credential with update available')
for _ in range(4): hard(base(pick('amex', '187'), recurring=True), 'Card replaced by issuer')
for region in ['Europe'] * 3 + ['United States'] * 3:
    hard(base(pick('mastercard', '65'), region=region), 'Code meaning depends on region')
for mac in ['40', '41', '40', '41']:
    s = base(pick('mastercard', '05'), recurring=True, card_type='Prepaid' if mac == '40' else 'Virtual')
    setadv(s, f'mastercard:merchant_advice:{mac}', f'MAC {mac}'); hard(s, 'Card type cannot support recurring')
for net, code in [('visa', '30'), ('mastercard', '30'), ('amex', '181'), ('discover', '30'), ('visa', '96'), ('discover', '94')]:
    s = base(pick(net, code)); s['repeat_failure'] = True; s['attempt_number'], s['previous_attempt'] = 3, 'Declined with same code'
    s['report_override'] = 'This has failed three times in a row with the same result.'
    hard(s, 'Repeated system or format failure needs escalation')
for _ in range(3):
    s = base(pick('mastercard', '05')); setadv(s, 'mastercard:merchant_advice:04', 'MAC 04'); hard(s, 'Token setup problem')
for _ in range(2):
    s = base(pick('mastercard', '05')); setadv(s, 'mastercard:merchant_advice:99', 'MAC 99'); hard(s, 'Sources disagree on advice code')

# ---- new hard cases ----
# 1. Visa reattempt limit: a retryable decline that has already been retried too often
for _ in range(40):
    s = base(pick('visa', rng.choice(['05', '51', '51', '61', '65', '91', '96', '19'])), recurring=rng.random() < 0.8)
    s['retries_last_30_days'] = rng.randint(VISA_REATTEMPT_LIMIT, 24)
    s['attempt_number'], s['previous_attempt'] = s['retries_last_30_days'] + 1, 'Declined with same code'
    s['report_override'] = "We have retried this payment every day for weeks and it keeps failing."
    hard(s, 'Retry limit reached')
# 2. Processor codes: the record shows First Data's code, not the network code
for _ in range(45):
    pc, plabel, cid = rng.choice(pmap)
    net = rng.choice(['visa', 'visa', 'mastercard'])
    tgt = cid if net == 'visa' else cid.replace('visa:', 'mastercard:')
    # Mastercard 65, 70 and 82 mean something different from Visa, so those processor codes stay on Visa
    if tgt not in codes or tgt.split(':')[-1] in ('65', '70', '82'): tgt, net = cid, 'visa'
    region = 'Europe' if codes[tgt]['category'] == 'authentication_required' else 'United States'
    recurring = True if codes[tgt]['category'] == 'recurring_cancelled' else None
    s = base(codes[tgt], recurring=recurring, region=region)
    s['response_code'], s['code_source'] = pc, 'processor'
    hard(s, 'Processor code needs translation')
# 3. More advice-code overrides on Mastercard policy, fraud and generic declines
for rc, mac, kind in [('82', '03', 'Advice code forbids retry'), ('83', '03', 'Advice code forbids retry'),
                      ('82', '02', 'Advice code allows later retry'), ('05', '02', 'Advice code allows later retry'),
                      ('83', '24', 'Advice code sets retry wait'), ('05', '01', 'Stale credential with update available'),
                      ('51', '01', 'Stale credential with update available')]:
    for _ in range(4):
        s = base(pick('mastercard', rc), recurring=True if mac == '01' else None)
        setadv(s, f'mastercard:merchant_advice:{mac}', f'MAC {mac}'); hard(s, kind)
for adv_n, kind in [('3', 'Visa category requires data fix')]:
    for _ in range(6):
        s = base(pick('visa', rng.choice(['05', '14', 'N7']))); setadv(s, f'visa:merchant_advice:{adv_n}', f'Visa category {adv_n}'); hard(s, kind)

rng.shuffle(scen)
for i, s in enumerate(scen, 1):
    s['scenario_id'] = f'DB-{i:03d}'
    s['question'] = rng.choice(QUESTIONS[s['recurring']])
    s.update(answer(s))
    s['merchant_report'] = s['report_override'] or rng.choice(REPORTS[s['answer_category']])

hard_ids = [s['scenario_id'] for s in scen if s['difficulty'] == 'hard']
std_ids = [s['scenario_id'] for s in scen if s['difficulty'] == 'standard']
rng.shuffle(hard_ids); rng.shuffle(std_ids)
timed = hard_ids[:13] + std_ids[:12]
label = hard_ids[13:51] + std_ids[12:49]
rng.shuffle(timed); rng.shuffle(label)
for s in scen:
    s['varun_set'] = 'timed' if s['scenario_id'] in timed else ('labeling' if s['scenario_id'] in label else '')

fields = ['scenario_id', 'varun_set', 'difficulty', 'hard_case_type', 'question', 'merchant_report', 'network', 'code_source',
          'response_code', 'advice_code', 'transaction_type', 'merchant_type', 'amount', 'currency', 'card_type', 'card_region',
          'attempt_number', 'previous_attempt', 'retries_last_30_days',
          'answer_category', 'answer_action', 'answer_retry', 'answer_escalate', 'answer_retry_guidance', 'answer_rule',
          'answer_explanation', 'answer_cardholder_message', 'response_code_id', 'advice_code_id']
with open(f'{OUT}/benchmark_scenarios_answer_key.csv', 'w', newline='') as f:
    w = csv.DictWriter(f, fieldnames=fields, extrasaction='ignore'); w.writeheader(); w.writerows(scen)
json.dump({'timed': timed, 'labeling': label}, open(f'{OUT}/varun_sets.json', 'w'))
json.dump(scen, open(f'{OUT}/_scenarios.json', 'w'), default=str)
print(len(scen), 'scenarios;', len(hard_ids), 'hard;', 'timed', len(timed), 'labeling', len(label))
