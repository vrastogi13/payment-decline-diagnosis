"""Build retrieval documents (variant D) and fine-tuning data (variant E) from the SAME knowledge base,
so the two variants learn identical facts. No benchmark scenario is used, to avoid test leakage.

Usage: python build_training_data.py <schema.sql> <seed.sql> <out_dir>
Outputs: kb_documents.jsonl        one retrieval document per code, rule, processor mapping and guidance note
         finetune_train.jsonl      chat-format examples (system / user / assistant)
         finetune_val.jsonl        10% held out for validation loss
         system_prompt.txt         the shared system prompt and output format for all model variants
"""
import sys, json, random
import duckdb

SCHEMA, SEED, OUT = sys.argv[1:4]
rng = random.Random(42)
db = duckdb.connect(); db.execute(open(SCHEMA).read()); db.execute(open(SEED).read())
def table(q):
    cur = db.execute(q); cols = [d[0] for d in cur.description]
    return [dict(zip(cols, r)) for r in cur.fetchall()]
codes = table('select * from decline_code')
by_id = {c['code_id']: c for c in codes}
rules = table('select * from decision_rule')
pmap = table('select * from processor_code_map')
ev = table('select e.code_id, s.publisher from code_evidence e join kb_source s using (source_id)')
pubs = {}
for e in ev: pubs.setdefault(e['code_id'], set()).add(e['publisher'])

NET = {'visa': 'Visa', 'mastercard': 'Mastercard', 'amex': 'American Express', 'discover': 'Discover', 'any': 'Any network'}
SYS = {'iso_response': 'response code', 'merchant_advice': 'merchant advice code', 'network_decision': 'network decision code'}
def lab(k): return (k or '').replace('_', ' ')
def name(c):
    if c['code_system'] == 'merchant_advice' and c['network'] == 'visa': return f"Visa decline category {c['code']}"
    return f"{NET[c['network']]} {SYS[c['code_system']]} {c['code']}"

SYSTEM_PROMPT = """You are a payments support assistant that diagnoses declined card payments for merchants and support teams.
Use the payment record from your tools when it is available. Never reveal the specific decline reason in text meant for the cardholder.
Answer in exactly this format:
Category: <one of: insufficient funds, expired card, invalid account, lost stolen, fraud suspected, issuer generic, authentication required, limit exceeded, restricted card, invalid data, issuer unavailable, merchant config, recurring cancelled>
Next step: <one of: retry later, retry with authentication, update credential, request new payment, contact issuer, do not retry, stop recurring, fix request data, check merchant setup, escalate to engineer>
Retry allowed: <yes | no | only after a change>
Escalate: <yes | no>
Explanation: <two to four sentences for the merchant>
Cardholder message: <one sentence that is safe to show the cardholder>"""

def answer_block(cat, action, retry, esc, expl, msg):
    r = {'yes': 'yes', 'no': 'no', 'conditional': 'only after a change'}.get(retry, retry)
    return (f"Category: {lab(cat)}\nNext step: {lab(action)}\nRetry allowed: {r}\nEscalate: {'yes' if esc else 'no'}\n"
            f"Explanation: {expl}\nCardholder message: {msg}")

# ---------------- retrieval documents ----------------
docs = []
for c in codes:
    retry = {'yes': 'Retry is allowed.', 'no': 'Do not retry.', 'conditional': 'Retry only after something changes.'}[c['retryable']]
    text = (f"{name(c)}: {c['short_name']}. {c['meaning']} Category: {lab(c['category'])}. This is a {c['decline_type']} decline. "
            f"{retry} {c['retry_guidance'] or ''} Recommended next step: {lab(c['primary_action'])}"
            + (f"; otherwise {lab(c['secondary_action'])}." if c['secondary_action'] else '.')
            + f" Merchant guidance: {c['merchant_explanation']} Safe message for the cardholder: \"{c['cardholder_message']}\""
            + (' Escalate to an engineer.' if c['escalate_to_human'] else '')
            + f" Sources: {', '.join(sorted(pubs.get(c['code_id'], [])))}. Confidence: {c['confidence']}.")
    docs.append(dict(id=c['code_id'], title=f"{name(c)}: {c['short_name']}", text=text.replace('  ', ' '),
                     metadata=dict(type='code', network=c['network'], code=c['code'], code_system=c['code_system'])))
for r in rules:
    parts = [name(by_id[r['response_code_id']]) if r['response_code_id'] else 'any response code',
             'with ' + name(by_id[r['advice_code_id']]) if r['advice_code_id'] else None,
             'on a recurring payment' if r['is_recurring'] else None]
    when = ' '.join(p for p in parts if p)
    docs.append(dict(id=f"rule:{r['rule_id']}", title=f"Decision rule: {when}",
                     text=f"When a decline has {when}, the next step is {lab(r['resulting_action'])}. {r['rationale']} Priority {r['priority']}: higher-priority rules override the response code's usual advice.",
                     metadata=dict(type='rule')))
for p in pmap:
    t = by_id[p['code_id']]
    docs.append(dict(id=f"processor:{p['processor']}:{p['processor_code']}", title=f"First Data processor code {p['processor_code']}: {p['processor_label']}",
                     text=f"First Data processor code {p['processor_code']} ({p['processor_label']}) corresponds to {name(t)} ({t['short_name']}). Diagnose it as {lab(t['category'])} and follow the guidance for that code: {lab(t['primary_action'])}.",
                     metadata=dict(type='processor_map', processor_code=p['processor_code'])))
GUIDES = [
 ('guide:visa_reattempt', 'Visa reattempt limit', 'Visa limits how often a merchant may retry a declined card. Under the rule assumed in this study, a card may be reattempted at most 15 times in 30 days by the same merchant; after that, stop retrying, because further attempts incur fees. Verify against Visa\'s current published rules.'),
 ('guide:advice_override', 'Advice codes override response codes', 'A Mastercard merchant advice code or Visa decline category, when present, takes priority over the response code\'s usual guidance. For example, insufficient funds normally allows a later retry, but with Mastercard advice code 03 the merchant must not retry.'),
 ('guide:mc65_region', 'Mastercard 65 depends on region', 'Mastercard response code 65 signals that strong customer authentication is required for payments in Europe under PSD2; outside Europe it usually means an activity count limit was exceeded and a later retry may succeed.'),
 ('guide:cardholder_messages', 'Never expose raw decline reasons to cardholders', 'Processors such as Adyen instruct merchants not to show raw decline responses to shoppers, because detailed reasons can help fraudsters. Give the cardholder a general message and keep the specific reason for the merchant and support team.'),
 ('guide:soft_hard', 'Soft and hard declines', 'A soft decline is temporary, such as insufficient funds or an issuer timeout, and may succeed on a later retry. A hard decline, such as a lost, stolen or closed card, will not succeed on retry; the merchant needs a new payment method or updated card details.'),
 ('guide:recurring_cards', 'Cards that cannot support recurring billing', 'Non-reloadable prepaid cards and single-use virtual card numbers cannot be charged again for subscriptions. Ask the customer for a different payment method.'),
]
for gid, title, text in GUIDES: docs.append(dict(id=gid, title=title, text=text, metadata=dict(type='guide')))

# ---------------- fine-tuning examples ----------------
ex = []
def add(user, assistant): ex.append({'messages': [{'role': 'system', 'content': SYSTEM_PROMPT}, {'role': 'user', 'content': user}, {'role': 'assistant', 'content': assistant}]})
Q_MEAN = ['What does {n} mean?', 'A payment came back with {n}. What happened?', 'Explain {n} for a merchant.']
Q_ACT = ['A stored-card payment was declined with {n}. What should the merchant do?', 'We got {n} on a renewal. Next step?',
         'How should support handle {n}?']
for c in codes:
    full = answer_block(c['category'], c['primary_action'], c['retryable'], c['escalate_to_human'],
                        f"{c['meaning']} {c['merchant_explanation']}", c['cardholder_message'])
    for q in rng.sample(Q_MEAN, 2) + rng.sample(Q_ACT, 2): add(q.format(n=name(c)), full)
for r in rules:
    resp = by_id[r['response_code_id']] if r['response_code_id'] else None
    adv = by_id[r['advice_code_id']] if r['advice_code_id'] else None
    base = resp or by_id['mastercard:iso_response:05' if (adv and adv['network'] == 'mastercard') else 'visa:iso_response:05']
    cat = adv['category'] if adv and adv['category'] in ('recurring_cancelled', 'expired_card', 'restricted_card') else base['category']
    retry = {'retry_later': 'yes', 'retry_with_authentication': 'yes', 'update_credential': 'conditional', 'fix_request_data': 'conditional'}.get(r['resulting_action'], 'no')
    desc = name(base) + (f' together with {name(adv)}' if adv else '') + (' on a recurring payment' if r['is_recurring'] else '')
    for q in ['The decline has {d}. What should the merchant do?', 'We received {d}. Should we retry?']:
        add(q.format(d=desc), answer_block(cat, r['resulting_action'], retry, False, r['rationale'], base['cardholder_message']))
for p in pmap:
    t = by_id[p['code_id']]
    for q in ['The processor returned First Data code {c}. What does it mean and what should we do?', 'First Data code {c} on a stored-card payment. Diagnose it.']:
        add(q.format(c=p['processor_code']), answer_block(t['category'], t['primary_action'], t['retryable'], t['escalate_to_human'],
            f"First Data code {p['processor_code']} corresponds to {name(t)}. {t['merchant_explanation']}", t['cardholder_message']))
for code in ['05', '51', '91']:
    c = by_id[f'visa:iso_response:{code}']
    add(f'{name(c)} on a card we have already retried 18 times this month. Retry again?',
        answer_block(c['category'], 'do_not_retry', 'no', False, 'The Visa reattempt limit for this card has been reached, so stop retrying to avoid fees.', c['cardholder_message']))
rng.shuffle(ex)
n_val = max(1, len(ex) // 10)
with open(f'{OUT}/finetune_val.jsonl', 'w') as f:
    for e in ex[:n_val]: f.write(json.dumps(e) + '\n')
with open(f'{OUT}/finetune_train.jsonl', 'w') as f:
    for e in ex[n_val:]: f.write(json.dumps(e) + '\n')
with open(f'{OUT}/kb_documents.jsonl', 'w') as f:
    for d in docs: f.write(json.dumps(d) + '\n')
open(f'{OUT}/system_prompt.txt', 'w').write(SYSTEM_PROMPT + '\n')
print(len(docs), 'retrieval documents;', len(ex) - n_val, 'training and', n_val, 'validation examples')
