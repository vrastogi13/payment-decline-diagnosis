"""Scoring tools for the agentic decline-diagnosis benchmark.

Commands
  lookup-baseline  Build variant A predictions: a static code-lookup table that ignores advice codes,
                   decision rules and context.
      python score_decline_benchmark.py lookup-baseline --key KEY.csv --schema SCHEMA.sql --seed SEED.sql --out A.csv

  score            Score one or more variants against the answer key.
      python score_decline_benchmark.py score --key KEY.csv --schema SCHEMA.sql --seed SEED.sql \
             --pred A=A.csv --pred B=B.csv ... --out results_dir

  parse            Convert raw model outputs (JSONL with scenario_id and output text in the system_prompt.txt format)
                   into a prediction CSV.
      python score_decline_benchmark.py parse --raw E_raw.jsonl --out E.csv

  merchant-baseline  Build variant A for the merchant test (group declines by code, rank by amount).
      python score_decline_benchmark.py merchant-baseline --transactions merchant_transactions.csv --out A_merchants.csv

  score-merchants  Score the merchant-level test (pattern detection, actions and ranking).
      python score_decline_benchmark.py score-merchants --key merchant_answer_key.csv --pred E=E_merchants.csv --out results_dir

  agreement        Compare Varun's returned workbook with the answer key (Cohen's kappa) and summarise his timed part.
      python score_decline_benchmark.py agreement --key KEY.csv --workbook Varun.xlsx --out results_dir

Prediction file format (CSV, one row per scenario; JSONL with the same fields also works)
  scenario_id          required, e.g. DB-001
  pred_category        required, a category key (insufficient_funds) or its label (Insufficient funds)
  pred_action          required, an action key (retry_later) or its label (Retry later)
  pred_retry           optional: yes / no / conditional
  pred_escalate        optional: yes / no
  explanation          optional: the agent's text; used for the hallucination check
  latency_ms           optional: wall-clock time per diagnosis
  cost_usd             optional: model cost per diagnosis
"""
import argparse, csv, glob, json, math, os, random, re, statistics as st
from collections import Counter, defaultdict

CATS = ['insufficient_funds', 'expired_card', 'invalid_account', 'lost_stolen', 'fraud_suspected', 'issuer_generic',
        'authentication_required', 'limit_exceeded', 'restricted_card', 'invalid_data', 'issuer_unavailable',
        'merchant_config', 'recurring_cancelled']
ACTS = ['retry_later', 'retry_with_authentication', 'update_credential', 'request_new_payment', 'contact_issuer',
        'do_not_retry', 'stop_recurring', 'fix_request_data', 'check_merchant_setup', 'escalate_to_engineer']

def norm(v, allowed):
    """Accept a key or a readable label; return the key, or '' if unrecognised."""
    if v is None: return ''
    k = str(v).strip().lower().replace('-', ' ').replace(' ', '_')
    return k if k in allowed else ''

def norm_yes(v):
    s = str(v or '').strip().lower()
    return {'yes': 'yes', 'y': 'yes', 'true': 'yes', 'no': 'no', 'n': 'no', 'false': 'no',
            'conditional': 'conditional', 'only after a change': 'conditional'}.get(s, '')

def read_rows(path):
    if not os.path.exists(path): raise SystemExit(f'file not found: {path} (did the run that writes it finish?)')
    if path.endswith('.jsonl'):
        rows = []
        for n, l in enumerate(open(path), 1):
            if not l.strip(): continue
            try: rows.append(json.loads(l))
            except json.JSONDecodeError: print(f'skipping unreadable line {n} in {path} (probably cut off when a run was interrupted)')
        return rows
    return list(csv.DictReader(open(path, newline='')))

def load_key(path): return {r['scenario_id']: r for r in read_rows(path)}

def load_kb(schema, seed):
    import duckdb
    db = duckdb.connect(); db.execute(open(schema).read()); db.execute(open(seed).read())
    cols = [d[0] for d in db.execute('select * from decline_code limit 0').description]
    return {r[0]: dict(zip(cols, r)) for r in db.execute('select * from decline_code').fetchall()}

# ---------------------------------------------------------------- statistics
def mean_ci(xs, n_boot=2000, seed=7):
    """Mean with a 95% bootstrap confidence interval."""
    if not xs: return (float('nan'),) * 3
    r = random.Random(seed); n = len(xs)
    boots = sorted(sum(xs[r.randrange(n)] for _ in range(n)) / n for _ in range(n_boot))
    return sum(xs) / n, boots[int(0.025 * n_boot)], boots[int(0.975 * n_boot)]

def mcnemar(a, b):
    """Exact McNemar test on paired correct/incorrect outcomes. Returns (b_only, a_only, p)."""
    a_only = sum(1 for x, y in zip(a, b) if x and not y)
    b_only = sum(1 for x, y in zip(a, b) if y and not x)
    n = a_only + b_only
    if n == 0: return b_only, a_only, 1.0
    k = min(a_only, b_only)
    p = min(1.0, 2 * sum(math.comb(n, i) for i in range(k + 1)) / 2 ** n)
    return b_only, a_only, p

def macro_f1(gold, pred, labels):
    f1s = []
    for l in labels:
        tp = sum(1 for g, p in zip(gold, pred) if g == l and p == l)
        fp = sum(1 for g, p in zip(gold, pred) if g != l and p == l)
        fn = sum(1 for g, p in zip(gold, pred) if g == l and p != l)
        if tp + fp + fn == 0: continue
        f1s.append(2 * tp / (2 * tp + fp + fn))
    return sum(f1s) / len(f1s) if f1s else float('nan')

def kappa(a, b):
    n = len(a)
    if n == 0: return float('nan')
    po = sum(x == y for x, y in zip(a, b)) / n
    ca, cb = Counter(a), Counter(b)
    pe = sum(ca[k] * cb[k] for k in set(ca) | set(cb)) / n ** 2
    return (po - pe) / (1 - pe) if pe < 1 else 1.0

def pct(x): return f'{100 * x:.1f}%' if x == x else 'n/a'

# ---------------------------------------------------------------- hallucination check
CODE_RE = re.compile(r'\b(?:code|response|MAC|advice code|category)\s*#?\s*([0-9]{2,3}|[0-9][A-Z]|[A-Z][0-9])\b', re.I)

def hallucinations(row, key_row, kb):
    """Flag code mentions that match neither the scenario's own codes nor any code on that network.
    Heuristic only: report it as an automated flag and confirm a sample by hand."""
    text = row.get('explanation') or ''
    if not text: return []
    net = key_row['network']
    known = {c['code'].upper() for c in kb.values() if c['network'] == net}
    scenario_codes = {key_row['response_code'].upper()} | set(re.findall(r'[0-9A-Z]{1,3}$', key_row.get('advice_code') or ''))
    bad = []
    for m in CODE_RE.findall(text):
        c = m.upper()
        if c not in scenario_codes and c not in known: bad.append(c)
    return bad

# ---------------------------------------------------------------- commands
def cmd_lookup(a):
    key = load_key(a.key); kb = load_kb(a.schema, a.seed)
    table = {(c['network'], c['code']): c for c in kb.values() if c['code_system'] == 'iso_response'}
    out = []
    for sid, k in key.items():
        # The lookup table sees only the network and the code shown; it ignores advice codes, retries and context.
        c = table.get((k['network'], k['response_code']))
        if c is None:
            out.append(dict(scenario_id=sid, pred_category='', pred_action='escalate_to_engineer', pred_retry='no',
                            pred_escalate='yes', explanation=f"Code {k['response_code']} is not in the lookup table.",
                            latency_ms=1, cost_usd=0))
            continue
        out.append(dict(scenario_id=sid, pred_category=c['category'], pred_action=c['primary_action'],
                        pred_retry=c['retryable'], pred_escalate='yes' if c['escalate_to_human'] else 'no',
                        explanation=f"Response code {c['code']}: {c['meaning']}", latency_ms=1, cost_usd=0))
    with open(a.out, 'w', newline='') as f:
        w = csv.DictWriter(f, fieldnames=list(out[0])); w.writeheader(); w.writerows(out)
    print(f'wrote {len(out)} lookup-table predictions to {a.out}')

def score_one(name, preds, key, kb):
    rows, per = [], []
    for sid, k in key.items():
        p = preds.get(sid)
        rec = dict(variant=name, scenario_id=sid, difficulty=k['difficulty'], hard_case_type=k['hard_case_type'],
                   network=k['network'], gold_category=k['answer_category'], gold_action=k['answer_action'],
                   gold_escalate=k['answer_escalate'].lower())
        if p is None:
            rec.update(missing=True, pred_category='', pred_action='', pred_escalate='', cat_ok=False, act_ok=False,
                       both_ok=False, esc_ok=False, halluc='', latency_ms='', cost_usd='')
        else:
            pc, pa = norm(p.get('pred_category'), CATS), norm(p.get('pred_action'), ACTS)
            pe = norm_yes(p.get('pred_escalate'))
            h = hallucinations(p, k, kb)
            rec.update(missing=False, pred_category=pc, pred_action=pa, pred_escalate=pe,
                       cat_ok=pc == k['answer_category'], act_ok=pa == k['answer_action'],
                       both_ok=pc == k['answer_category'] and pa == k['answer_action'],
                       esc_ok=(pe == k['answer_escalate'].lower()) if pe else None,
                       halluc=' '.join(h), latency_ms=p.get('latency_ms', ''), cost_usd=p.get('cost_usd', ''))
        per.append(rec)
    return per

def summarise(per):
    n = len(per)
    s = {}
    for m in ('cat_ok', 'act_ok', 'both_ok'):
        s[m] = mean_ci([1 if r[m] else 0 for r in per])
    s['cat_f1'] = macro_f1([r['gold_category'] for r in per], [r['pred_category'] for r in per], CATS)
    s['act_f1'] = macro_f1([r['gold_action'] for r in per], [r['pred_action'] for r in per], ACTS)
    esc = [r for r in per if r['esc_ok'] is not None]
    tp = sum(1 for r in esc if r['gold_escalate'] == 'yes' and r['pred_escalate'] == 'yes')
    fp = sum(1 for r in esc if r['gold_escalate'] == 'no' and r['pred_escalate'] == 'yes')
    fn = sum(1 for r in esc if r['gold_escalate'] == 'yes' and r['pred_escalate'] == 'no')
    s['esc_precision'] = tp / (tp + fp) if tp + fp else float('nan')
    s['esc_recall'] = tp / (tp + fn) if tp + fn else float('nan')
    s['halluc_rate'] = sum(1 for r in per if r['halluc']) / n
    s['missing'] = sum(1 for r in per if r['missing'])
    lat = [float(r['latency_ms']) for r in per if str(r['latency_ms']).strip() not in ('', 'None')]
    cost = [float(r['cost_usd']) for r in per if str(r['cost_usd']).strip() not in ('', 'None')]
    s['latency_median_ms'] = st.median(lat) if lat else float('nan')
    s['latency_p95_ms'] = sorted(lat)[int(0.95 * (len(lat) - 1))] if lat else float('nan')
    s['cost_total_usd'] = sum(cost) if cost else float('nan')
    return s

def cmd_score(a):
    key = load_key(a.key); kb = load_kb(a.schema, a.seed)
    os.makedirs(a.out, exist_ok=True)
    variants = []
    for spec in a.pred:
        name, path = spec.split('=', 1)
        preds = {r['scenario_id']: r for r in read_rows(path)}
        variants.append((name, score_one(name, preds, key, kb)))
    all_rows = [r for _, per in variants for r in per]
    with open(f'{a.out}/per_scenario.csv', 'w', newline='') as f:
        w = csv.DictWriter(f, fieldnames=list(all_rows[0])); w.writeheader(); w.writerows(all_rows)

    L = ['# Benchmark results', '', f'Scenarios: {len(key)}. Accuracy shown with 95% bootstrap confidence intervals.', '',
         '| Variant | Category acc. | Action acc. | Both correct | Category macro-F1 | Action macro-F1 | Escalation precision | Escalation recall | Hallucination flags | Median latency (ms) | Total cost ($) | Missing |',
         '| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |']
    sums = {}
    for name, per in variants:
        s = summarise(per); sums[name] = s
        ci = lambda t: f'{pct(t[0])} ({pct(t[1])} to {pct(t[2])})'
        L.append(f"| {name} | {ci(s['cat_ok'])} | {ci(s['act_ok'])} | {ci(s['both_ok'])} | {s['cat_f1']:.3f} | {s['act_f1']:.3f} | "
                 f"{pct(s['esc_precision'])} | {pct(s['esc_recall'])} | {pct(s['halluc_rate'])} | {s['latency_median_ms']:.0f} | "
                 f"{s['cost_total_usd']:.2f} | {s['missing']} |")
    L += ['', '## Action accuracy by difficulty', '', '| Variant | Standard | Hard |', '| --- | --- | --- |']
    for name, per in variants:
        std = [1 if r['act_ok'] else 0 for r in per if r['difficulty'] == 'standard']
        hrd = [1 if r['act_ok'] else 0 for r in per if r['difficulty'] == 'hard']
        L.append(f'| {name} | {pct(sum(std) / len(std))} | {pct(sum(hrd) / len(hrd))} |')
    types = sorted({r['hard_case_type'] for _, per in variants for r in per if r['hard_case_type']})
    L += ['', '## Action accuracy on hard-case types', '', '| Hard-case type | n | ' + ' | '.join(n for n, _ in variants) + ' |',
          '| --- | --- | ' + ' | '.join('---' for _ in variants) + ' |']
    for t in types:
        cells = []
        for _, per in variants:
            xs = [1 if r['act_ok'] else 0 for r in per if r['hard_case_type'] == t]
            cells.append(pct(sum(xs) / len(xs)))
        n_t = sum(1 for r in variants[0][1] if r['hard_case_type'] == t)
        L.append(f'| {t} | {n_t} | ' + ' | '.join(cells) + ' |')
    if len(variants) > 1:
        L += ['', '## Pairwise significance (exact McNemar test on action correctness)', '',
              '| Comparison | Only second correct | Only first correct | p-value |', '| --- | --- | --- | --- |']
        for i in range(len(variants)):
            for j in range(i + 1, len(variants)):
                (n1, p1), (n2, p2) = variants[i], variants[j]
                b, aa, p = mcnemar([r['act_ok'] for r in p1], [r['act_ok'] for r in p2])
                L.append(f'| {n1} vs {n2} | {b} | {aa} | {p:.4f} |')
    L += ['', 'Hallucination flags are automated: a code is flagged when the explanation cites one that is neither in the scenario '
          'nor in the knowledge base for that network. Review a sample by hand before reporting the rate.']
    open(f'{a.out}/results.md', 'w').write('\n'.join(L) + '\n')
    json.dump({k: {m: (list(v) if isinstance(v, tuple) else v) for m, v in s.items()} for k, s in sums.items()},
              open(f'{a.out}/summary.json', 'w'), indent=2)
    print('\n'.join(L))

def cmd_agreement(a):
    from openpyxl import load_workbook
    key = load_key(a.key); wb = load_workbook(a.workbook, data_only=True)
    os.makedirs(a.out, exist_ok=True)
    def rows(sheet):
        ws = wb[sheet]; hdr = [c.value for c in ws[1]]
        return [dict(zip(hdr, [c.value for c in r])) for r in ws.iter_rows(min_row=3)]
    lab = [r for r in rows('Part 2 Labeling') if r.get('Scenario ID') in key]
    done = [r for r in lab if r.get('Root-cause category') and r.get('Recommended next step')]
    gc = [key[r['Scenario ID']]['answer_category'] for r in done]; vc = [norm(r['Root-cause category'], CATS) for r in done]
    ga = [key[r['Scenario ID']]['answer_action'] for r in done]; va = [norm(r['Recommended next step'], ACTS) for r in done]
    ge = [key[r['Scenario ID']]['answer_escalate'].lower() for r in done]; ve = [norm_yes(r.get('Escalate to an engineer?')) for r in done]
    L = ['# Agreement with the second annotator', '', f'Labeled scenarios returned: {len(done)} of {len(lab)}.', '',
         '| Label | Raw agreement | Cohen\'s kappa |', '| --- | --- | --- |']
    for nm, g, v in [('Root-cause category', gc, vc), ('Recommended next step', ga, va), ('Escalate', ge, ve)]:
        L.append(f'| {nm} | {pct(sum(x == y for x, y in zip(g, v)) / len(g)) if g else "n/a"} | {kappa(g, v):.3f} |')
    L += ['', 'Kappa guide: 0.61 to 0.80 substantial, above 0.80 almost perfect (Landis and Koch, 1977).']
    dis = []
    for r, g1, v1, g2, v2 in zip(done, gc, vc, ga, va):
        if g1 != v1 or g2 != v2:
            k = key[r['Scenario ID']]
            dis.append(dict(scenario_id=r['Scenario ID'], hard_case_type=k['hard_case_type'], network=k['network'],
                            response_code=k['response_code'], advice_code=k['advice_code'],
                            key_category=g1, varun_category=v1, key_action=g2, varun_action=v2,
                            varun_confidence=r.get('Confidence') or '', varun_notes=r.get('Notes') or '', resolution=''))
    if dis:
        with open(f'{a.out}/disagreements_to_resolve.csv', 'w', newline='') as f:
            w = csv.DictWriter(f, fieldnames=list(dis[0])); w.writeheader(); w.writerows(dis)
    L += ['', f'Disagreements to resolve: {len(dis)} (see disagreements_to_resolve.csv).']
    timed = [r for r in rows('Part 1 Timed') if r.get('Scenario ID') in key and r.get('Minutes taken') not in (None, '')]
    if timed:
        mins = [float(r['Minutes taken']) for r in timed]
        acc = [norm(r.get('Recommended next step'), ACTS) == key[r['Scenario ID']]['answer_action'] for r in timed]
        L += ['', '## Human baseline (Part 1)', '', f'Scenarios timed: {len(timed)}',
              f'Minutes per diagnosis: mean {st.mean(mins):.1f}, median {st.median(mins):.1f}, max {max(mins):.1f}',
              f'Next-step accuracy against the answer key: {pct(sum(acc) / len(acc))}']
    open(f'{a.out}/agreement.md', 'w').write('\n'.join(L) + '\n')
    print('\n'.join(L))

def parse_answer(text):
    """Parse a model answer written in the shared format from system_prompt.txt into prediction fields."""
    f = {}
    for line in (text or '').splitlines():
        if ':' in line:
            k, v = line.split(':', 1); f[k.strip().lower()] = v.strip()
    return dict(pred_category=norm(f.get('category'), CATS) or f.get('category', ''),
                pred_action=norm(f.get('next step'), ACTS) or f.get('next step', ''),
                pred_retry=norm_yes(f.get('retry allowed')), pred_escalate=norm_yes(f.get('escalate')),
                explanation=f.get('explanation', ''), cardholder_message=f.get('cardholder message', ''))

def cmd_parse(a):
    """Turn raw model outputs (JSONL: scenario_id, output, optional latency_ms, cost_usd) into a prediction CSV."""
    out = []
    for r in read_rows(a.raw):
        p = parse_answer(r.get('output', '')); p.update(scenario_id=r['scenario_id'], latency_ms=r.get('latency_ms', ''), cost_usd=r.get('cost_usd', ''))
        out.append(p)
    fields = ['scenario_id', 'pred_category', 'pred_action', 'pred_retry', 'pred_escalate', 'explanation', 'cardholder_message', 'latency_ms', 'cost_usd']
    with open(a.out, 'w', newline='') as fh:
        w = csv.DictWriter(fh, fieldnames=fields); w.writeheader(); w.writerows(out)
    bad = sum(1 for p in out if not p['pred_category'] in CATS or not p['pred_action'] in ACTS)
    print(f'parsed {len(out)} outputs to {a.out}; {bad} did not follow the answer format')

PATTERNS = ['expired_card_spike', 'issuer_outage', 'retrying_hard_declines', 'excessive_soft_retries', 'prepaid_on_subscription',
            'missing_3ds_europe', 'integration_regression', 'merchant_setup_error', 'revoked_still_billed', 'none']

CODE_TO_PATTERN = {'54': 'expired_card_spike', '79': 'expired_card_spike', '101': 'expired_card_spike', '91': 'issuer_outage',
                   '41': 'retrying_hard_declines', '43': 'retrying_hard_declines', '59': 'retrying_hard_declines',
                   '1A': 'missing_3ds_europe', '65': 'missing_3ds_europe', '30': 'integration_regression',
                   '03': 'merchant_setup_error', '58': 'merchant_setup_error', 'R1': 'revoked_still_billed', 'R3': 'revoked_still_billed'}
PATTERN_ACTION = {'expired_card_spike': 'update_credential', 'issuer_outage': 'retry_later', 'retrying_hard_declines': 'do_not_retry',
                  'excessive_soft_retries': 'do_not_retry', 'prepaid_on_subscription': 'request_new_payment',
                  'missing_3ds_europe': 'retry_with_authentication', 'integration_regression': 'fix_request_data',
                  'merchant_setup_error': 'check_merchant_setup', 'revoked_still_billed': 'stop_recurring'}

def cmd_merchant_baseline(a):
    """Variant A for the merchant test: group declines by code, map the top three codes to patterns, rank by declined amount."""
    by = defaultdict(lambda: defaultdict(float))
    for r in read_rows(a.transactions):
        if r['status'] != 'declined': continue
        code = r['advice_code'].replace('MAC ', '') if r['advice_code'] in ('MAC 40', 'MAC 41') else r['response_code']
        by[r['merchant_id']][code] += float(r['amount'])
    out = []
    for m, codes_ in sorted(by.items()):
        rank = 0
        for code, amt in sorted(codes_.items(), key=lambda kv: -kv[1])[:3]:
            p = 'prepaid_on_subscription' if code in ('40', '41') else CODE_TO_PATTERN.get(code)
            if not p or any(o['merchant_id'] == m and o['pattern'] == p for o in out): continue
            rank += 1
            out.append(dict(merchant_id=m, pattern=p, action=PATTERN_ACTION[p], revenue_rank=rank))
    with open(a.out, 'w', newline='') as f:
        w = csv.DictWriter(f, fieldnames=['merchant_id', 'pattern', 'action', 'revenue_rank']); w.writeheader(); w.writerows(out)
    print(f'wrote {len(out)} baseline findings to {a.out}')

def cmd_score_merchants(a):
    """Merchant-level test. Prediction CSV columns: merchant_id, pattern (a PATTERNS key, or 'none'),
    action (an action key), revenue_rank (1 = fix first; leave blank for risk patterns)."""
    key = read_rows(a.key); os.makedirs(a.out, exist_ok=True)
    gold = defaultdict(dict)
    for k in key:
        if k['pattern'] != 'none': gold[k['merchant_id']][k['pattern']] = k
    merchants = sorted({k['merchant_id'] for k in key})
    L = ['# Merchant-level results', '', f'Merchants: {len(merchants)}; planted patterns: {sum(len(v) for v in gold.values())}.', '',
         '| Variant | Pattern precision | Pattern recall | Pattern F1 | False alarms on clean merchants | Action accuracy (found patterns) | Top revenue issue correct | Revenue ordering accuracy |',
         '| --- | --- | --- | --- | --- | --- | --- | --- |']
    msum = {}
    for spec in a.pred:
        name, path = spec.split('=', 1)
        pred = defaultdict(dict)
        for r in read_rows(path):
            pat = (r.get('pattern') or '').strip().lower()
            if pat in PATTERNS and pat != 'none':
                rk = str(r.get('revenue_rank') or '').strip()
                pred[r['merchant_id']][pat] = dict(action=norm(r.get('action'), ACTS), rank=int(float(rk)) if rk else None)
        tp = sum(1 for m in merchants for p in pred[m] if p in gold[m])
        fp = sum(1 for m in merchants for p in pred[m] if p not in gold[m])
        fn = sum(1 for m in merchants for p in gold[m] if p not in pred[m])
        prec = tp / (tp + fp) if tp + fp else float('nan'); rec = tp / (tp + fn) if tp + fn else float('nan')
        f1 = 2 * prec * rec / (prec + rec) if prec == prec and rec == rec and prec + rec else float('nan')
        clean = [m for m in merchants if not gold[m]]
        fa = sum(1 for m in clean if pred[m]) / len(clean) if clean else float('nan')
        act = [pred[m][p]['action'] == gold[m][p]['action'] for m in merchants for p in pred[m] if p in gold[m]]
        top, pairs, correct_pairs = [], 0, 0
        for m in merchants:
            rev = {p: int(g['revenue_rank']) for p, g in gold[m].items() if g['impact_type'] == 'revenue'}
            if not rev: continue
            true_top = min(rev, key=rev.get)
            ranked = {p: v['rank'] for p, v in pred[m].items() if v['rank'] is not None}
            top.append(bool(ranked) and min(ranked, key=ranked.get) == true_top)
            found = [p for p in rev if p in ranked]
            for i in range(len(found)):
                for j in range(i + 1, len(found)):
                    pairs += 1; x, y = found[i], found[j]
                    correct_pairs += (rev[x] < rev[y]) == (ranked[x] < ranked[y])
        msum[name] = dict(pattern_precision=prec, pattern_recall=rec, pattern_f1=f1, clean_false_alarm_rate=fa,
                          action_accuracy=sum(act) / len(act) if act else float('nan'),
                          top_revenue_correct=sum(top) / len(top) if top else float('nan'),
                          revenue_ordering_accuracy=correct_pairs / pairs if pairs else float('nan'))
        L.append(f'| {name} | {pct(prec)} | {pct(rec)} | {pct(f1)} | {pct(fa)} | {pct(sum(act) / len(act)) if act else "n/a"} | '
                 f'{pct(sum(top) / len(top)) if top else "n/a"} | {pct(correct_pairs / pairs) if pairs else "n/a"} |')
    L += ['', 'Revenue patterns are ranked by recoverable amount. Risk patterns (retrying hard declines, excessive soft retries, '
          'billing customers who revoked recurring payments) count toward detection and action accuracy but are not ranked.']
    open(f'{a.out}/merchant_results.md', 'w').write('\n'.join(L) + '\n'); print('\n'.join(L))
    json.dump(msum, open(f'{a.out}/merchant_summary.json', 'w'), indent=2)

def cmd_average_runs(a):
    """Average the repeated runs: mean and range of each metric, and how often the runs agree with each other."""
    runs = sorted(glob.glob(os.path.join(a.results, 'run*')))
    if not runs: raise SystemExit(f'no run folders in {a.results}')
    L = ['# Results averaged over runs', '', f'Runs: {", ".join(os.path.basename(r) for r in runs)}. Each cell: mean (min to max).', '']
    def table(fname, metrics, title):
        data = [json.load(open(os.path.join(r, fname))) for r in runs if os.path.exists(os.path.join(r, fname))]
        if not data: return []
        names = list(data[0])
        out = [f'## {title}', '', '| Variant | ' + ' | '.join(lbl for _, lbl in metrics) + ' |', '| --- |' + ' --- |' * len(metrics)]
        for n in names:
            cells = []
            for m, _ in metrics:
                xs = [d[n][m][0] if isinstance(d[n][m], list) else d[n][m] for d in data if n in d]
                xs = [x for x in xs if x == x]
                raw = m in ('latency_median_ms', 'cost_total_usd')  # not percentages
                cells.append('n/a' if not xs else (f'{st.mean(xs):,.2f} ({min(xs):,.2f} to {max(xs):,.2f})' if raw
                                                     else f'{pct(st.mean(xs))} ({pct(min(xs))} to {pct(max(xs))})'))
            out.append(f'| {n} | ' + ' | '.join(cells) + ' |')
        return out + ['']
    L += table('summary.json', [('cat_ok', 'Category acc.'), ('act_ok', 'Action acc.'), ('both_ok', 'Both correct'),
                                ('esc_precision', 'Escalation precision'), ('esc_recall', 'Escalation recall'),
                                ('halluc_rate', 'Hallucination flags'), ('latency_median_ms', 'Median latency (ms)'),
                                ('cost_total_usd', 'Cost per run ($)')], 'Payment-level test')
    L += table('merchant_summary.json', [('pattern_precision', 'Pattern precision'), ('pattern_recall', 'Pattern recall'),
                                         ('pattern_f1', 'Pattern F1'), ('clean_false_alarm_rate', 'False alarms (clean)'),
                                         ('action_accuracy', 'Action accuracy'), ('top_revenue_correct', 'Top revenue issue')],
               'Merchant-level test')
    per = defaultdict(lambda: defaultdict(list))
    for r in runs:
        f = os.path.join(r, 'per_scenario.csv')
        if os.path.exists(f):
            for row in read_rows(f): per[row['variant']][row['scenario_id']].append(row['pred_action'])
    if per:
        L += ['## Run-to-run consistency (payment test)', '', '| Variant | Scenarios with the same action in every run |', '| --- | --- |']
        for v, d in per.items():
            same = [len(set(xs)) == 1 for xs in d.values() if len(xs) == len(runs)]
            L.append(f'| {v} | {pct(sum(same) / len(same)) if same else "n/a"} |')
    open(os.path.join(a.results, 'averaged_results.md'), 'w').write('\n'.join(L) + '\n'); print('\n'.join(L))

if __name__ == '__main__':
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest='cmd', required=True)
    p = sub.add_parser('lookup-baseline'); p.add_argument('--key', required=True); p.add_argument('--schema', required=True)
    p.add_argument('--seed', required=True); p.add_argument('--out', required=True); p.set_defaults(f=cmd_lookup)
    p = sub.add_parser('score'); p.add_argument('--key', required=True); p.add_argument('--schema', required=True)
    p.add_argument('--seed', required=True); p.add_argument('--pred', action='append', required=True, help='NAME=path')
    p.add_argument('--out', required=True); p.set_defaults(f=cmd_score)
    p = sub.add_parser('agreement'); p.add_argument('--key', required=True); p.add_argument('--workbook', required=True)
    p.add_argument('--out', required=True); p.set_defaults(f=cmd_agreement)
    p = sub.add_parser('parse'); p.add_argument('--raw', required=True); p.add_argument('--out', required=True); p.set_defaults(f=cmd_parse)
    p = sub.add_parser('merchant-baseline'); p.add_argument('--transactions', required=True); p.add_argument('--out', required=True)
    p.set_defaults(f=cmd_merchant_baseline)
    p = sub.add_parser('average-runs'); p.add_argument('--results', required=True, help='folder holding run1, run2, run3')
    p.set_defaults(f=cmd_average_runs)
    p = sub.add_parser('score-merchants'); p.add_argument('--key', required=True); p.add_argument('--pred', action='append', required=True, help='NAME=path')
    p.add_argument('--out', required=True); p.set_defaults(f=cmd_score_merchants)
    a = ap.parse_args(); a.f(a)
