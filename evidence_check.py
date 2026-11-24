"""Evidence check: a deterministic validator that admits an agent's answer only if its claims are backed by tool results.

Payment test. An answer passes only if
  1. its Evidence line (variant E) cites the record's response code, and every cited field=value matches the record
     and every cited doc=<title> was actually returned to the agent in that session;
  2. every decline code mentioned in the Explanation is the record's own response or advice code, or appears in a
     document returned to the agent;
  3. every network named in the Explanation is the record's network (or First Data for processor codes);
  4. every retry or attempt count stated in the Explanation equals a count in the record or in a returned document;
  5. the Explanation does not state a card region or card type that contradicts the record.
An answer that fails is not repaired by the model: its next step becomes "escalate to engineer" and Escalate becomes yes,
so a person sees it with the reasons attached.

Merchant test. A finding passes only if
  1. every number in its evidence sentence appears in a tool result the agent received;
  2. its evidence cites what the pattern requires: decline codes whose knowledge-base category fits the pattern
     (for example, an expired-card spike needs an expired-card code), retry-chain numbers for retry patterns,
     prepaid or single-use cards for prepaid_on_subscription;
  3. its evidence does not deny the pattern it reports (for example "no cards declined more than once").
A finding that fails is dropped and listed for review; a merchant left with no findings is reported as none.

Used two ways:
  * inside run_variants.py as variant E (variant D plus this check, with an Evidence line added to the prompt), where the
    check sees exactly the tool results of the session;
  * offline on variant D's published outputs, which have no Evidence line and did not save their tool results:
        python evidence_check.py offline-payments --raw raw/D_run1.jsonl --out raw/Dcheck_run1.jsonl
        python evidence_check.py offline-merchants --raw raw/D_merchants_run1_raw.jsonl --out raw/Dcheck_merchants_run1.csv
    Offline, the documents the agent saw are approximated by the knowledge-base documents that name the record's own
    codes, and a merchant's tool results by every aggregate the analysis tool can return for that merchant. Both are
    supersets of what the agent saw in most cases, so the offline check is lenient; report it as an approximation.
"""
import argparse, csv, json, os, re, sys

HERE = os.path.dirname(os.path.abspath(__file__))
def path(name): return os.path.join(HERE, name)

NETWORKS = {'visa': 'Visa', 'mastercard': 'Mastercard', 'amex': 'American Express', 'discover': 'Discover'}
NETWORK_WORDS = {'visa': r'\bvisa\b', 'mastercard': r'\bmastercard\b', 'amex': r'\b(?:american express|amex)\b',
                 'discover': r'\bdiscover\b'}
REGION_WORDS = {'Europe': r'\beurop(?:e|ean)\b|\bEEA\b|\bUK\b|\bSCA\b'}
CARD_TYPE_WORDS = {'Prepaid': r'\bprepaid\b', 'Credit': r'\bcredit card\b', 'Debit': r'\bdebit card\b'}
CODE_RE = re.compile(r'\b(?:response code|processor code|advice code|decline code|code|MAC|category)\s*#?\s*'
                     r'([0-9]{1,3}|[0-9][A-Z]|[A-Z][0-9])\b', re.I)
COUNT_RE = re.compile(r'\b(\d{1,3})\s+(?:previous |earlier |prior |failed |declined |more )?(?:re)?(?:tries|retries|attempts?)\b'
                      r'|\b(?:retries|attempts?|retried|tried)\b[^.]{0,25}?\b(\d{1,3})\b(?! ?(?:%|days?|hours?|minutes?|weeks?))', re.I)


def norm(v): return re.sub(r'\s+', ' ', str(v or '')).strip().lower()


def canon(code):
    """Decline codes as text: '05' and '5' are the same code (spreadsheet tools drop leading zeros)."""
    c = norm(code)
    return str(int(c)) if c.isdigit() else c


def record_codes(rec):
    codes = {canon(rec.get('response_code'))}
    adv = rec.get('advice_code') or ''
    if adv: codes.add(canon(adv.split()[-1]))
    return {c for c in codes if c}


# ---------------------------------------------------------------- payment test
def parse_fields(text):
    f = {}
    for line in (text or '').splitlines():
        if ':' in line:
            k, v = line.split(':', 1); f[k.strip().lower()] = v.strip()
    return f


def parse_evidence(s):
    """'response_code=51; advice_code=MAC 03; doc=Mastercard response code 51: Insufficient funds' -> [(key, value)]"""
    items = []
    for part in re.split(r';|\n', s or ''):
        if '=' in part:
            k, v = part.split('=', 1); items.append((k.strip().lower().replace(' ', '_'), v.strip().strip('"\'')))
    return items


def docs_for_record(rec, docs):
    """Offline stand-in for the documents retrieval attached: knowledge-base documents that name the record's own codes."""
    net = NETWORKS.get(rec['network'], rec['network'])
    want = []
    if rec.get('code_source') == 'processor': want.append(f"First Data processor code {rec['response_code']}:")
    else: want.append(f"{net} response code {rec['response_code']}:")
    adv = rec.get('advice_code') or ''
    if adv.startswith('MAC '): want.append(f"Mastercard merchant advice code {adv[4:]}:")
    elif adv.startswith('Visa category'): want.append(f"Visa decline category {adv.split()[-1]}")
    out = [d for d in docs if any(d['title'].startswith(w) or w.rstrip(':') in d['title'] for w in want)]
    # decision rules that name the record's codes
    for d in docs:
        if d['title'].startswith('Decision rule') and d not in out:
            t = d['title'].lower()
            if (adv and adv.split()[-1].lower() in t.split()) or f"response code {rec['response_code'].lower()} " in t + ' ':
                out.append(d)
    return out


def check_payment(output, rec, docs, require_evidence):
    """Returns (passed, reasons). docs = the documents returned to the agent (title, text)."""
    f = parse_fields(output)
    expl = f.get('explanation', '')
    reasons = []
    doc_text = ' '.join(f"{d['title']} {d['text']}" for d in docs).lower()
    doc_titles = {norm(d['title']) for d in docs}

    if require_evidence:
        ev = parse_evidence(f.get('evidence', ''))
        if not ev: reasons.append('no Evidence line')
        cited_fields = {k for k, _ in ev}
        if 'response_code' not in cited_fields: reasons.append('Evidence does not cite the response code')
        for k, v in ev:
            if k in ('doc', 'document'):
                t = norm(v)
                if not any(t == dt or dt.startswith(t) or t.startswith(dt) for dt in doc_titles):
                    reasons.append(f'cited document was not returned: {v[:60]}')
            elif k not in rec:
                reasons.append(f'cited field is not in the record: {k}')
            elif norm(rec[k]) != norm(v) and canon(rec[k]) != canon(v) and not (k == 'advice_code' and canon(rec[k].split()[-1] if rec[k] else '') == canon(v.split()[-1] if v else '')):
                reasons.append(f'cited {k}={v} but the record has {rec[k] or "(blank)"}')

    own = record_codes(rec)
    doc_codes = {canon(c) for c in CODE_RE.findall(doc_text)}
    for c in CODE_RE.findall(expl):
        c = canon(c)
        if c in own or c in doc_codes: continue
        reasons.append(f'mentions code {c.upper()}, which is not in the record or the documents returned')

    low = expl.lower()
    for netk, rx in NETWORK_WORDS.items():
        if netk != rec['network'] and re.search(rx, low) and not re.search(rx, doc_text):
            reasons.append(f'names {NETWORKS[netk]} but the payment ran on {NETWORKS.get(rec["network"], rec["network"])}')

    counts = {canon(rec.get('retries_last_30_days')), canon(rec.get('attempt_number'))}
    for a, b in COUNT_RE.findall(expl):
        n = (a or b).lstrip('0') or '0'
        if n in counts or re.search(rf'\b{n}\b (?:authorization )?attempts', doc_text): continue
        reasons.append(f'states a count of {n} retries or attempts, which the record does not show')

    for region, rx in REGION_WORDS.items():
        if re.search(rx, expl) and region.lower() not in norm(rec.get('card_region')) and 'outside' not in low:
            reasons.append(f'refers to {region} but the card region is {rec.get("card_region")}')
    for ct, rx in CARD_TYPE_WORDS.items():
        if re.search(rx, low) and norm(rec.get('card_type')) != ct.lower() and not re.search(r'\b(?:not|no|non)[- ]' + rx[2:], low):
            reasons.append(f'refers to a {ct.lower()} card but the card type is {rec.get("card_type")}')

    return (not reasons), sorted(set(reasons))


def escalate(output, reasons):
    """Replace the next step with an escalation and keep the rest, so a person sees the model's answer and why it failed."""
    out, seen = [], set()
    for line in (output or '').splitlines():
        k = line.split(':', 1)[0].strip().lower()
        seen.add(k)
        if k == 'next step': line = 'Next step: escalate to engineer'
        elif k == 'escalate': line = 'Escalate: yes'
        elif k == 'retry allowed': line = 'Retry allowed: no'
        out.append(line)
    if 'next step' not in seen: out.append('Next step: escalate to engineer')
    if 'escalate' not in seen: out.append('Escalate: yes')
    out.append('Evidence check: failed; ' + '; '.join(reasons))
    return '\n'.join(out)


# ---------------------------------------------------------------- merchant test
PATTERN_CATEGORIES = {
    'expired_card_spike': {'expired_card'}, 'issuer_outage': {'issuer_unavailable'},
    'missing_3ds_europe': {'authentication_required'}, 'integration_regression': {'invalid_data'},
    'merchant_setup_error': {'merchant_config'}, 'revoked_still_billed': {'recurring_cancelled'},
}
RETRY_PATTERNS = {'retrying_hard_declines': 'hard', 'excessive_soft_retries': 'soft'}
NEGATION = re.compile(r'\b(?:no|zero|0|none of the) (?:cards?|declines?|transactions?|retries)\b|\bnot (?:declined|retried|present|seen|observed)\b', re.I)
NUM_RE = re.compile(r'(?<![A-Za-z0-9])\$?(\d{1,3}(?:,\d{3})+(?:\.\d+)?|\d+(?:\.\d+)?)(%?)')
CODE_LIST_RE = re.compile(r'\b(?:codes?|MAC)\s+((?:[0-9A-Z]{1,3}\b(?:\s*\([^)]*\))?(?:\s*(?:,|and|or|/)\s*)?)+)', re.I)


def kb_codes():
    import duckdb
    db = duckdb.connect(); db.execute(open(path('decline_kb_schema.sql')).read()); db.execute(open(path('decline_kb_seed.sql')).read())
    out = {}
    for code, cat, dtype, name in db.execute('select code, category, decline_type, short_name from decline_code').fetchall():
        out.setdefault(code.upper(), []).append((cat, dtype))
        # "Not permitted to terminal" and similar codes describe the merchant's own setup, whatever their category
        if re.search(r'terminal|merchant', name, re.I): out[code.upper()].append(('merchant_config', dtype))
    return out


def evidence_codes(ev):
    codes = set()
    for m in CODE_LIST_RE.findall(ev):
        for tok in re.findall(r'\b([0-9A-Z]{1,3})\b', re.sub(r'\([^)]*\)', '', m)):
            if tok.upper() not in ('AND', 'OR'): codes.add(tok.upper())
    return codes


def numbers_in(text):
    """Numbers stated in text, normalised; years, dates and small ordinals are left out (dates are checked as strings)."""
    out = set()
    t = re.sub(r'\b\d{4}-\d{2}-\d{2}\b', ' ', text)
    t = re.sub(r'\b(?:codes?|MAC|rank)\s+[0-9A-Z]{1,3}(?:\s*(?:,|and|or|/)\s*[0-9A-Z]{1,3})*', ' ', t, flags=re.I)
    for n, _ in NUM_RE.findall(t):
        v = float(n.replace(',', ''))
        if v < 3 and '.' not in n: continue  # "1 card", "2 issuers" are too common to check meaningfully
        out.add(v)
    return out


def result_values(results):
    vals, strings = set(), set()
    for r in results:
        if not isinstance(r, dict): continue
        for k, v in r.items():
            if isinstance(v, (int, float)): vals.add(round(float(v), 2))
        for row in r.get('rows', []):
            for cell in row:
                strings.add(str(cell))
                try: vals.add(round(float(str(cell).replace(',', '')), 2))
                except ValueError: pass
    return vals, strings


def check_finding(f, results, kb):
    """f = dict(pattern, action, revenue_rank, evidence). Returns (passed, reasons)."""
    pat, ev = f['pattern'], f.get('evidence') or ''
    if pat == 'none': return True, []
    reasons = []
    vals, strings = result_values(results)
    for v in numbers_in(ev):
        if not any(abs(v - x) <= max(0.051, 0.0005 * abs(x)) for x in vals):
            reasons.append(f'number {v:g} is not in any tool result')
    for d in re.findall(r'\b\d{4}-\d{2}-\d{2}\b', ev):
        if not any(d in s for s in strings): reasons.append(f'date {d} is not in any tool result')
    codes = evidence_codes(ev)
    if pat in PATTERN_CATEGORIES:
        fits = [c for c in codes if any(cat in PATTERN_CATEGORIES[pat] for cat, _ in kb.get(c, []))]
        if not fits:
            reasons.append(f'cites no decline code of a kind that shows {pat}' + (f' (cites {", ".join(sorted(codes))})' if codes else ''))
    elif pat in RETRY_PATTERNS:
        want = RETRY_PATTERNS[pat]
        if not re.search(r'more than once|retr|declines? on one card|repeated|chain', ev, re.I):
            reasons.append('cites no retry-chain evidence')
        if codes and not any(any(dt == want for _, dt in kb.get(c, [])) for c in codes):
            reasons.append(f'cites only codes that are not {want} declines ({", ".join(sorted(codes))})')
    elif pat == 'prepaid_on_subscription':
        if not re.search(r'prepaid|single[- ]use|virtual|MAC 4[01]', ev, re.I):
            reasons.append('cites no prepaid or single-use card evidence')
    if NEGATION.search(ev): reasons.append('evidence denies the pattern it reports')
    return (not reasons), sorted(set(reasons))


def parse_findings(merchant_id, out):
    """Same parsing as run_variants.run_merchants."""
    rows = []
    for line in (out or '').splitlines():
        line = re.sub(r'^[\s>*#`\-\d.)]*', '', line.replace('**', '').replace('`', ''))
        if line.lower().startswith('finding'):
            parts = [x.strip() for x in line.split(':', 1)[-1].split('|', 3)] + ['', '', '']
            rows.append(dict(merchant_id=merchant_id, pattern=parts[0].lower().replace(' ', '_'),
                             action=parts[1].lower().replace(' ', '_'), revenue_rank=re.sub(r'\D', '', parts[2]),
                             evidence=parts[3].strip().rstrip('|').strip()))
    if any(r['pattern'] != 'none' for r in rows): rows = [r for r in rows if r['pattern'] != 'none']
    return rows


def check_merchant(merchant_id, out, results, kb):
    """Returns (kept rows for the prediction CSV, flagged rows with reasons)."""
    kept, flagged = [], []
    for r in parse_findings(merchant_id, out):
        ok, why = check_finding(r, results, kb)
        (kept if ok else flagged).append(r if ok else dict(r, reasons='; '.join(why)))
    return kept or [dict(merchant_id=merchant_id, pattern='none', action='', revenue_rank='', evidence='')], flagged


def all_merchant_results(merchant_id, sql):
    """Offline stand-in for the merchant's tool results: every grouping, unfiltered and filtered by each declined code."""
    dims = ['response_code', 'advice_code', 'issuer', 'network', 'card_type', 'card_region', 'transaction_type', 'week', 'day', 'retry_chain']
    res = []
    def run(**kw):
        sql.last = None; r = sql.analyze(merchant_id=merchant_id, **kw)
        res.append(r); return r
    for g in dims: run(group_by=g)
    codes = [row[0] for row in run(group_by='response_code').get('rows', []) if row[0]]
    advs = [row[0] for row in run(group_by='advice_code').get('rows', []) if row[0]]
    issuers = [row[0] for row in run(group_by='issuer').get('rows', []) if row[0]]
    regions = [row[0] for row in run(group_by='card_region').get('rows', []) if row[0]]
    for g in dims:
        for c in codes: run(group_by=g, response_code=c)
        for c in advs: run(group_by=g, advice_code=c)
        for c in issuers: run(group_by=g, issuer=c)
        for c in regions: run(group_by=g, card_region=c)
    return res


# ---------------------------------------------------------------- offline commands
def cmd_offline_payments(a):
    key = {r['scenario_id']: r for r in csv.DictReader(open(a.key))}
    docs = [json.loads(l) for l in open(a.docs)]
    from run_variants import RECORD_FIELDS
    n = fails = 0
    report = []
    with open(a.out, 'w') as fo:
        for l in open(a.raw):
            if not l.strip(): continue
            r = json.loads(l); k = key[r['scenario_id']]
            rec = {f: k[f] for f in RECORD_FIELDS}
            ok, why = check_payment(r['output'], rec, docs_for_record(rec, docs), require_evidence=False)
            n += 1; fails += not ok
            r2 = dict(r, model_output=r['output'], output=r['output'] if ok else escalate(r['output'], why),
                      evidence_check='passed' if ok else 'failed', evidence_reasons=why)
            fo.write(json.dumps(r2) + '\n')
            if not ok: report.append(dict(scenario_id=r['scenario_id'], reasons='; '.join(why)))
    if report:
        with open(a.out.rsplit('.', 1)[0] + '_flagged.csv', 'w', newline='') as f:
            w = csv.DictWriter(f, fieldnames=['scenario_id', 'reasons']); w.writeheader(); w.writerows(report)
    print(f'{a.raw}: {fails} of {n} answers failed the evidence check and were escalated; wrote {a.out}')


def cmd_offline_merchants(a):
    sys.path.insert(0, HERE)
    from run_variants import SQL
    sql, kb = SQL(), kb_codes()
    cache = {}
    kept_all, flagged_all = [], []
    for l in open(a.raw):
        if not l.strip(): continue
        r = json.loads(l); m = r['merchant_id']
        if m not in cache: cache[m] = all_merchant_results(m, sql)
        kept, flagged = check_merchant(m, r['output'], cache[m], kb)
        kept_all += kept; flagged_all += flagged
    with open(a.out, 'w', newline='') as f:
        w = csv.DictWriter(f, fieldnames=['merchant_id', 'pattern', 'action', 'revenue_rank', 'evidence'])
        w.writeheader(); w.writerows(kept_all)
    with open(a.out.rsplit('.', 1)[0] + '_flagged.csv', 'w', newline='') as f:
        w = csv.DictWriter(f, fieldnames=['merchant_id', 'pattern', 'action', 'revenue_rank', 'evidence', 'reasons'])
        w.writeheader(); w.writerows(flagged_all)
    print(f'{a.raw}: kept {sum(1 for k in kept_all if k["pattern"] != "none")} findings, dropped {len(flagged_all)}; wrote {a.out}')


if __name__ == '__main__':
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest='cmd', required=True)
    p = sub.add_parser('offline-payments'); p.add_argument('--raw', required=True); p.add_argument('--out', required=True)
    p.add_argument('--key', default=path('benchmark_scenarios_answer_key.csv')); p.add_argument('--docs', default=path('kb_documents.jsonl'))
    p.set_defaults(f=cmd_offline_payments)
    p = sub.add_parser('offline-merchants'); p.add_argument('--raw', required=True); p.add_argument('--out', required=True)
    p.set_defaults(f=cmd_offline_merchants)
    a = ap.parse_args(); a.f(a)
