"""Run model variants B, C and D against a hosted OpenAI-compatible API (for example, a provider serving Qwen3.5-9B).

Variant B: no tools. The model sees the question and the merchant's description only.
Variant C: tools. The model can call get_payment_record (payment test) or analyze_merchant (merchant test).
Variant D: as C, plus search_decline_docs, which returns the top 5 knowledge-base documents by embedding similarity.

Setup (works on an Intel Mac; nothing runs on a GPU locally):
    pip install openai duckdb numpy            # all variants
    pip install sentence-transformers          # only for variant D with --embed local
    export LLM_BASE_URL=https://<provider>/v1  LLM_API_KEY=...  LLM_MODEL=<provider's Qwen3.5-9B identifier>

OpenRouter (the setup used in the paper): pin ONE backend so every request runs on the same deployment:
    export LLM_BASE_URL=https://openrouter.ai/api/v1  LLM_API_KEY=<OpenRouter key>  LLM_MODEL=qwen/qwen3.5-9b
    python run_variants.py payments --openrouter-provider deepinfra/bf16 --variant C --run 1 --out raw/C_test.jsonl --limit 5
  If OpenRouter rejects that tag, use: --openrouter-provider deepinfra --openrouter-quantization bf16
  The slug comes from the Providers tab of the model's OpenRouter page. Pick one that lists tool support and note its
  quantization. Requests fail rather than silently moving to another backend if that provider is down.

Alibaba Cloud Model Studio (if your region offers qwen3-8b): add --dashscope to every command, and set
    export LLM_BASE_URL=https://<WorkspaceId>.us-east-1.maas.aliyuncs.com/compatible-mode/v1   # US (Virginia) region
    export LLM_MODEL=qwen3-8b  LLM_API_KEY=<your Model Studio API key>

Payment-level test (writes raw JSONL for: score_decline_benchmark.py parse):
    python run_variants.py payments --variant B --run 1 --out raw/B_run1.jsonl
    python run_variants.py payments --variant D --run 1 --out raw/D_run1.jsonl --embed local

Merchant-level test (writes a prediction CSV for: score_decline_benchmark.py score-merchants):
    python run_variants.py merchants --variant C --run 1 --out raw/C_merchants_run1.csv

Data: the merchant test loads merchant_transactions.csv into DuckDB. The analyze_merchant tool runs fixed aggregate queries
(group by one dimension, optional filters), so the model never writes SQL itself.

Options: --limit N (try a few scenarios first), --price-in / --price-out (USD per million tokens, for the cost column),
--no-think-tag (append /no_think to the system prompt; Qwen3's soft switch, not supported by Qwen3.5).
Outputs are appended scenario by scenario, so an interrupted run resumes where it stopped.
"""
import argparse, csv, json, os, re, sys, time

HERE = os.path.dirname(os.path.abspath(__file__))
RECORD_FIELDS = ['network', 'code_source', 'response_code', 'advice_code', 'transaction_type', 'merchant_type', 'amount',
                 'currency', 'card_type', 'card_region', 'attempt_number', 'previous_attempt', 'retries_last_30_days']
PATTERNS = ['expired_card_spike', 'issuer_outage', 'retrying_hard_declines', 'excessive_soft_retries', 'prepaid_on_subscription',
            'missing_3ds_europe', 'integration_regression', 'merchant_setup_error', 'revoked_still_billed']
ACTIONS = ['retry_later', 'retry_with_authentication', 'update_credential', 'request_new_payment', 'contact_issuer',
           'do_not_retry', 'stop_recurring', 'fix_request_data', 'check_merchant_setup', 'escalate_to_engineer']
MAX_OUTPUT_TOKENS = 2048  # stops runaway generations; a full answer needs a few hundred tokens
MAX_TURNS = 16  # tool-calling rounds before the agent must answer


def path(name): return os.path.join(HERE, name)


def client():
    from openai import OpenAI
    for v in ('LLM_BASE_URL', 'LLM_API_KEY', 'LLM_MODEL'):
        if not os.environ.get(v): sys.exit(f'set {v} first (see the top of this file)')
    return OpenAI(base_url=os.environ['LLM_BASE_URL'], api_key=os.environ['LLM_API_KEY'], timeout=120, max_retries=2)


# ---------------- retrieval (variant D) ----------------
class Retriever:
    """Embeds kb_documents.jsonl once (cached to kb_embeddings.npy) and returns the top k documents by cosine similarity."""
    def __init__(self, mode, k=5):
        import numpy as np
        self.np, self.k, self.mode = np, k, mode
        self.docs = [json.loads(l) for l in open(path('kb_documents.jsonl'))]
        texts = [f"{d['title']}\n{d['text']}" for d in self.docs]
        if mode == 'local':
            from sentence_transformers import SentenceTransformer
            self.model = SentenceTransformer(os.environ.get('EMBED_MODEL', 'Qwen/Qwen3-Embedding-0.6B'),
                                             revision=os.environ.get('EMBED_REVISION', '97b0c614be4d77ee51c0cef4e5f07c00f9eb65b3'))
        else:
            self.api, self.embed_model = client(), os.environ.get('EMBED_MODEL', 'Qwen/Qwen3-Embedding-0.6B')
        cache = path(f'kb_embeddings_{mode}.npy')
        if os.path.exists(cache): self.mat = np.load(cache)
        else: self.mat = self._embed(texts, query=False); np.save(cache, self.mat)

    def _embed(self, texts, query):
        np = self.np
        if self.mode == 'local':
            v = self.model.encode(texts, prompt_name='query' if query else None, normalize_embeddings=True)
        else:
            v = np.array([d.embedding for d in self.api.embeddings.create(model=self.embed_model, input=texts).data])
            v = v / np.linalg.norm(v, axis=1, keepdims=True)
        return np.asarray(v, dtype='float32')

    def search(self, query, k=None):
        scores = self.mat @ self._embed([query], query=True)[0]
        top = scores.argsort()[::-1][:k or self.k]
        return [dict(title=self.docs[i]['title'], text=self.docs[i]['text']) for i in top]

    def for_queries(self, queries, total=5):
        """Top documents for several queries in turn, without duplicates, at most `total` in all."""
        out, seen = [], set()
        for q, k in queries:
            for d in self.search(q, k):
                if d['title'] not in seen and len(out) < total: seen.add(d['title']); out.append(d)
        return out


NETWORK_NAMES = {'visa': 'Visa', 'mastercard': 'Mastercard', 'amex': 'American Express', 'discover': 'Discover'}


def record_queries(rec):
    """Retrieval queries built from a payment record's own fields (never from the answer)."""
    net = NETWORK_NAMES.get(rec['network'], rec['network'])
    code = (f"First Data processor code {rec['response_code']}" if rec['code_source'] == 'processor'
            else f"{net} response code {rec['response_code']}")
    qs = [(code, 3)]
    adv = rec.get('advice_code') or ''
    if adv.startswith('MAC '): qs.append((f"Mastercard merchant advice code {adv[4:]}", 2))
    elif adv.startswith('Visa category'): qs.append((f"Visa decline category {adv.split()[-1]}", 2))
    qs.append((f"{code} on a {rec['transaction_type']} payment, card region {rec['card_region']}, "
               f"attempt {rec['attempt_number']}, {rec['retries_last_30_days']} retries in the last 30 days", 5))
    return qs


# ---------------- tools ----------------
def tool(name, desc, props, required):
    return dict(type='function', function=dict(name=name, description=desc,
                parameters=dict(type='object', properties=props, required=required)))

T_PAYMENT = tool('get_payment_record', 'Look up the authorization record for a declined payment.',
                 {'payment_id': {'type': 'string', 'description': 'The payment ID, for example DB-001'}}, ['payment_id'])
DIMENSIONS = ['response_code', 'advice_code', 'issuer', 'network', 'card_type', 'card_region', 'transaction_type', 'week', 'day']
T_SQL = tool('analyze_merchant',
             "Summarize a merchant's last 90 days of stored-card transactions. Groups transactions by one dimension and returns, "
             "for each group, total transactions, declines, decline rate and declined amount (largest declined amount first, "
             "at most 40 groups), plus the merchant's overall decline rate. Use group_by='retry_chain' to see, per response code, "
             "how many cards were declined repeatedly and the most declines on one card. Filters narrow the data first, for example "
             "group_by='day' with response_code='91' shows when one code spiked.",
             {'merchant_id': {'type': 'string', 'description': 'for example M001'},
              'group_by': {'type': 'string', 'enum': DIMENSIONS + ['retry_chain']},
              'response_code': {'type': 'string', 'description': 'optional filter, for example 05'},
              'advice_code': {'type': 'string', 'description': 'optional filter, for example MAC 01'},
              'issuer': {'type': 'string', 'description': 'optional filter'},
              'card_region': {'type': 'string', 'description': 'optional filter'}},
             ['merchant_id', 'group_by'])
T_DOCS = tool('search_decline_docs', 'Search card-network decline documentation (response codes, advice codes, decision rules, '
              'processor code mappings). Returns the 5 most relevant passages.', {'query': {'type': 'string'}}, ['query'])


class SQL:
    """The merchant analysis tool: fixed aggregate queries over merchant_transactions.csv in DuckDB."""
    def __init__(self):
        import duckdb
        self.conn = duckdb.connect()
        self.conn.execute(f"""create table transactions as select *, cast(substr(timestamp, 1, 10) as date) as day,
            cast(date_trunc('week', cast(substr(timestamp, 1, 10) as date)) as date) as week
            from read_csv_auto('{path('merchant_transactions.csv')}', all_varchar=true)""")
        self.conn.execute('alter table transactions alter amount type double')
        self.conn.execute('alter table transactions alter attempt_number type integer')
        self.last = None

    def analyze(self, merchant_id, group_by, response_code='', advice_code='', issuer='', card_region=''):
        key = json.dumps([merchant_id, group_by, response_code, advice_code, issuer, card_region])
        if key == self.last:
            return {'note': 'You just ran this exact analysis. Try a different group_by or filter, or give your final answer.'}
        self.last = key
        where, params = ['merchant_id = ?'], [merchant_id]
        for col, val in [('response_code', response_code), ('advice_code', advice_code), ('issuer', issuer), ('card_region', card_region)]:
            if val: where.append(f'{col} = ?'); params.append(val)
        w = ' and '.join(where)
        overall = self.conn.execute(f"select count(*), sum(status = 'declined') from transactions where merchant_id = ?", [merchant_id]).fetchone()
        if not overall[0]: return {'error': f'no transactions for merchant {merchant_id}'}
        if group_by == 'retry_chain':
            q = f"""select response_code, count(*) as cards_declined_more_than_once, max(n) as most_declines_on_one_card,
                    sum(n) as declines_in_these_chains from (select card_id, response_code, count(*) as n from transactions
                    where {w} and status = 'declined' group by 1, 2 having count(*) > 1) group by 1 order by 4 desc limit 40"""
        elif group_by in ('response_code', 'advice_code'):
            # Grouping by the decline outcome itself: a per-group decline rate would always read 100%, so report each
            # group's share of the merchant's declines instead.
            q = f"""select coalesce(cast({group_by} as varchar), '') as {group_by}, sum(status = 'declined') as declines,
                    round(100.0 * sum(status = 'declined') / {max(overall[1], 1)}, 1) as share_of_all_declines_pct,
                    round(sum(case when status = 'declined' then amount else 0 end), 2) as declined_amount
                    from transactions where {w} and status = 'declined' group by 1 order by declined_amount desc, 1 limit 40"""
        elif group_by in ('day', 'week'):
            # Time series in date order, so onsets and bursts are visible (90 days fit in one result).
            q = f"""select cast({group_by} as varchar) as {group_by}, count(*) as transactions, sum(status = 'declined') as declines,
                    round(100.0 * sum(status = 'declined') / count(*), 1) as decline_rate_pct,
                    round(sum(case when status = 'declined' then amount else 0 end), 2) as declined_amount
                    from transactions where {w} group by 1 order by 1 limit 100"""
        elif group_by in DIMENSIONS:
            q = f"""select coalesce(cast({group_by} as varchar), '') as {group_by}, count(*) as transactions,
                    sum(status = 'declined') as declines, round(100.0 * sum(status = 'declined') / count(*), 1) as decline_rate_pct,
                    round(sum(case when status = 'declined' then amount else 0 end), 2) as declined_amount
                    from transactions where {w} group by 1 order by declined_amount desc, 1 limit 40"""
        else:
            return {'error': f'group_by must be one of {DIMENSIONS + ["retry_chain"]}'}
        cur = self.conn.execute(q, params)
        cols = [d[0] for d in cur.description]
        return {'merchant_overall_decline_rate_pct': round(100.0 * overall[1] / overall[0], 1), 'columns': cols,
                'rows': [[str(v) for v in r] for r in cur.fetchall()]}


# ---------------- agent loop ----------------
def dump(args, label, msgs):
    os.makedirs(args.debug_dir, exist_ok=True)
    with open(os.path.join(args.debug_dir, f'{label or "chat"}.json'), 'w') as f: json.dump(msgs, f, indent=1)


def create_with_backoff(api, kw, tries=8):
    """Retry rate limits (429) and provider errors (5xx) with growing waits: 15s, 30s, 60s, then 120s.
    A retried request is identical, so retries do not change results."""
    import openai
    for i in range(tries):
        try:
            return api.chat.completions.create(**kw)
        except (openai.RateLimitError, openai.APIConnectionError, openai.APITimeoutError, openai.InternalServerError) as e:
            if i == tries - 1: raise
            wait = min(120, 15 * 2 ** i)
            print(f'    {type(e).__name__}; waiting {wait}s before retry {i + 1} of {tries - 1}', file=sys.stderr, flush=True)
            time.sleep(wait)


def chat(api, system, user, tools, handlers, args, label=''):
    msgs = [{'role': 'system', 'content': system}, {'role': 'user', 'content': user}]
    tin = tout = calls = 0
    for _ in range(MAX_TURNS):
        kw = dict(model=os.environ['LLM_MODEL'], messages=msgs, temperature=0, max_tokens=MAX_OUTPUT_TOKENS)
        if tools: kw['tools'] = tools
        if args.openrouter_provider:
            prov = {'order': [args.openrouter_provider], 'allow_fallbacks': False, 'require_parameters': True}
            if args.openrouter_quantization: prov['quantizations'] = [args.openrouter_quantization]
            kw['extra_body'] = {'provider': prov,
                                'reasoning': {'enabled': False}}
        elif args.dashscope: kw['extra_body'] = {'enable_thinking': False}
        elif args.chat_template_kwargs: kw['extra_body'] = {'chat_template_kwargs': {'enable_thinking': False}}
        t = time.time()
        r = create_with_backoff(api, kw)
        if r.usage: tin += r.usage.prompt_tokens; tout += r.usage.completion_tokens
        m = r.choices[0].message
        print(f'    model call: {time.time() - t:.1f}s, {r.usage.completion_tokens if r.usage else "?"} tokens out, '
              f'finish={getattr(r.choices[0], "finish_reason", "?")}', file=sys.stderr, flush=True)
        if not m.tool_calls:
            if args.debug_dir: dump(args, label, msgs + [{'role': 'assistant', 'content': m.content}])
            return re.sub(r'<think>.*?</think>', '', m.content or '', flags=re.S).strip(), tin, tout, calls
        msgs.append({'role': 'assistant', 'content': m.content or '', 'tool_calls': [
            {'id': c.id, 'type': 'function', 'function': {'name': c.function.name, 'arguments': c.function.arguments}} for c in m.tool_calls]})
        for c in m.tool_calls:
            calls += 1
            print(f'    tool {calls}: {c.function.name} {(c.function.arguments or "")[:120]}', file=sys.stderr, flush=True)
            try: res = handlers[c.function.name](**json.loads(c.function.arguments or '{}'))
            except Exception as e: res = {'error': f'{type(e).__name__}: {e}'}
            msgs.append({'role': 'tool', 'tool_call_id': c.id, 'content': json.dumps(res)})
    # Out of tool rounds: ask once more for the final answer with tools switched off.
    msgs.append({'role': 'user', 'content': 'You have used all your tool calls. Give your final answer now in the required format.'})
    kw.pop('tools', None)
    r = create_with_backoff(api, kw)
    if r.usage: tin += r.usage.prompt_tokens; tout += r.usage.completion_tokens
    if args.debug_dir: dump(args, label, msgs + [{'role': 'assistant', 'content': r.choices[0].message.content}])
    return re.sub(r'<think>.*?</think>', '', r.choices[0].message.content or '', flags=re.S).strip(), tin, tout, calls


def done_ids(out, key):
    if not os.path.exists(out): return set()
    if out.endswith('.jsonl'):
        ids = set()
        for l in open(out):
            try: ids.add(json.loads(l)[key])
            except (json.JSONDecodeError, KeyError): pass  # a line cut off by an interrupted run is redone
        return ids
    return {r[key] for r in csv.DictReader(open(out))}


def system_prompt(args, extra=''):
    s = open(path('system_prompt.txt')).read().strip() + extra
    return s + ('\n/no_think' if args.no_think_tag else '')  # Qwen3 soft switch only; Qwen3.5 does not support it


def run_payments(args):
    api = client()
    scen = list(csv.DictReader(open(path('benchmark_scenarios_answer_key.csv'))))
    by_id = {s['scenario_id']: s for s in scen}
    retr = Retriever(args.embed) if args.variant == 'D' else None
    def lookup(payment_id):
        if payment_id not in by_id: return {'error': 'payment not found'}
        rec = {f: by_id[payment_id][f] for f in RECORD_FIELDS}
        if retr:  # variant D: the record arrives with the 5 most relevant knowledge-base documents attached
            return {'record': rec, 'relevant_documentation': retr.for_queries(record_queries(rec))}
        return rec
    handlers = {'get_payment_record': lookup,
                'search_decline_docs': lambda query: retr.search(query)}
    tools = {'B': [], 'C': [T_PAYMENT], 'D': [T_PAYMENT, T_DOCS]}[args.variant]
    system = system_prompt(args)
    os.makedirs(os.path.dirname(os.path.abspath(args.out)), exist_ok=True)
    skip = done_ids(args.out, 'scenario_id')
    todo = [s for s in scen if s['scenario_id'] not in skip][:args.limit or None]
    if os.path.exists(args.out) and os.path.getsize(args.out) and not open(args.out, 'rb').read().endswith(b'\n'):
        open(args.out, 'a').write('\n')  # start fresh after a line cut off by an interrupted run
    with open(args.out, 'a') as f:
        for i, s in enumerate(todo, 1):
            user = f"{s['question']}\nMerchant's description: {s['merchant_report']}"
            if args.variant != 'B': user += f"\nPayment ID: {s['scenario_id']}"
            t0 = time.time()
            out, tin, tout, calls = chat(api, system, user, tools, handlers, args, label=f"{s['scenario_id']}_{args.variant}_run{args.run}")
            f.write(json.dumps(dict(scenario_id=s['scenario_id'], variant=args.variant, run=args.run, output=out,
                                    latency_ms=round(1000 * (time.time() - t0)), tool_calls=calls, tokens_in=tin, tokens_out=tout,
                                    cost_usd=round((tin * args.price_in + tout * args.price_out) / 1e6, 6))) + '\n'); f.flush()
            print(f'{i}/{len(todo)} {s["scenario_id"]} tools={calls}', file=sys.stderr)


PATTERN_DEFINITIONS = {
    'expired_card_spike': 'many stored cards are declining because they have expired',
    'issuer_outage': 'a burst of declines from one issuer within a few hours or days, because that issuer was unavailable',
    'retrying_hard_declines': 'the merchant keeps retrying cards whose declines are permanent, such as lost, stolen or closed cards',
    'excessive_soft_retries': 'temporary declines are retried far more often than card-network retry limits allow',
    'prepaid_on_subscription': 'prepaid or single-use virtual cards are failing on recurring charges',
    'missing_3ds_europe': 'European card payments are declining because strong customer authentication (3-D Secure) was not performed',
    'integration_regression': 'declines for malformed or invalid request data that begin on a particular date',
    'merchant_setup_error': "declines showing the merchant's own account is misconfigured, beginning on a particular date across many cards",
    'revoked_still_billed': 'the merchant keeps charging customers who have revoked or cancelled recurring payments',
}


def merchant_system_prompt(args):
    """The merchant test has its own prompt (saved to merchant_system_prompt.txt), shared by variants B to D."""
    defs = '\n'.join(f'- {k}: {v}' for k, v in PATTERN_DEFINITIONS.items())
    s = f"""You are a payments support assistant that investigates why a merchant's stored-card payments are declining.
Use your tools to examine the merchant's last 90 days of transactions before answering. Read each result before deciding
what to look at next, and drill into anything unusual with filters (for example, one response code by day or by issuer).
Compare what you see with the merchant's overall decline rate, so that you separate real problems from ordinary background
declines. Report a pattern only if your tool results clearly show it; reporting a pattern that is not there counts as an error.

The patterns you can report:
{defs}

Do not use a single-payment answer format. Answer only with findings, one per line, in exactly this format:
Finding: <pattern> | <next step> | <revenue rank> | <evidence>
<pattern> is one of the patterns above.
<next step> is one of: {', '.join(ACTIONS)}.
<revenue rank> is 1 for the problem whose fix would recover the most revenue, 2 for the next, and so on. Leave it blank for risk
patterns (retrying_hard_declines, excessive_soft_retries, revoked_still_billed), which are flagged but not ranked.
<evidence> is one short sentence quoting the numbers from your tool results that show the pattern.
If only ordinary background declines are present, answer exactly: Finding: none | | | <evidence>"""
    open(path('merchant_system_prompt.txt'), 'w').write(s + '\n')
    return s + ('\n/no_think' if args.no_think_tag else '')


def run_merchants(args):
    api = client()
    merchants = [r['merchant_id'] for r in csv.DictReader(open(path('merchant_profiles.csv')))]
    profiles = {r['merchant_id']: r for r in csv.DictReader(open(path('merchant_profiles.csv')))}
    sql = SQL() if args.variant != 'B' else None
    retr = Retriever(args.embed) if args.variant == 'D' else None
    def analyze(**kw):
        res = sql.analyze(**kw)
        if retr and kw.get('group_by') in ('response_code', 'advice_code') and res.get('rows'):
            # variant D: attach documentation for the codes that account for the most declined money (5 documents in all)
            col = 'response code' if kw['group_by'] == 'response_code' else 'merchant advice code'
            codes = [r[0] for r in res['rows'] if r[0]][:3]
            res['relevant_documentation'] = retr.for_queries([(f'{col} {c}', 2) for c in codes])
        return res
    handlers = {'analyze_merchant': analyze, 'search_decline_docs': lambda query: retr.search(query)}
    tools = {'B': [], 'C': [T_SQL], 'D': [T_SQL, T_DOCS]}[args.variant]
    system = merchant_system_prompt(args)
    skip = done_ids(args.out, 'merchant_id')
    todo = [m for m in merchants if m not in skip][:args.limit or None]
    new = not os.path.exists(args.out)
    os.makedirs(os.path.dirname(os.path.abspath(args.out)), exist_ok=True)
    with open(args.out, 'a', newline='') as f, open(args.out.rsplit('.', 1)[0] + '_raw.jsonl', 'a') as raw:
        w = csv.DictWriter(f, fieldnames=['merchant_id', 'pattern', 'action', 'revenue_rank', 'evidence'])
        if new: w.writeheader()
        for i, m in enumerate(todo, 1):
            p = profiles[m]
            user = (f"Merchant {m} ({p['merchant_type']}, {p['region']}) says too many stored-card payments are declining. "
                    f"What is going wrong, and what should they fix first? Answer only with Finding lines.")
            t0 = time.time()
            out, tin, tout, calls = chat(api, system, user, tools, handlers, args, label=f'{m}_{args.variant}_run{args.run}')
            raw.write(json.dumps(dict(merchant_id=m, variant=args.variant, run=args.run, output=out, latency_ms=round(1000 * (time.time() - t0)),
                                      tool_calls=calls, tokens_in=tin, tokens_out=tout)) + '\n')
            rows = []
            for line in out.splitlines():
                line = re.sub(r'^[\s>*#`\-\d.)]*', '', line.replace('**', '').replace('`', ''))  # tolerate markdown bullets and bold
                if line.lower().startswith('finding'):
                    parts = [x.strip() for x in line.split(':', 1)[-1].split('|', 3)] + ['', '', '']
                    pat = parts[0].lower().replace(' ', '_')
                    rank = re.sub(r'\D', '', parts[2])
                    rows.append(dict(merchant_id=m, pattern=pat, action=parts[1].lower().replace(' ', '_'), revenue_rank=rank,
                                     evidence=parts[3].strip().rstrip('|').strip()))
            if any(r['pattern'] != 'none' for r in rows): rows = [r for r in rows if r['pattern'] != 'none']  # 'none' beside real findings is ignored
            w.writerows(rows or [dict(merchant_id=m, pattern='none', action='', revenue_rank='', evidence='')]); f.flush(); raw.flush()
            print(f'{i}/{len(todo)} {m} findings={len(rows)} tools={calls}', file=sys.stderr)


if __name__ == '__main__':
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('test', choices=['payments', 'merchants'])
    ap.add_argument('--variant', choices=['B', 'C', 'D'], required=True)
    ap.add_argument('--run', type=int, default=1)
    ap.add_argument('--out', required=True)
    ap.add_argument('--embed', choices=['local', 'api'], default='local', help='variant D: embed locally or with the provider')
    ap.add_argument('--limit', type=int, default=0)
    ap.add_argument('--price-in', type=float, default=0.0)
    ap.add_argument('--price-out', type=float, default=0.0)
    ap.add_argument('--no-think-tag', action='store_true', help='append /no_think to the system prompt (Qwen3 only, not Qwen3.5)')
    ap.add_argument('--openrouter-provider', default='', help='OpenRouter: pin this one backend (slug from the model\'s Providers tab), no fallbacks, reasoning off')
    ap.add_argument('--openrouter-quantization', default='', help='OpenRouter: only accept this quantization, for example bf16')
    ap.add_argument('--debug-dir', default='', help='save each full conversation (prompts, tool calls, tool results) as JSON here')
    ap.add_argument('--dashscope', action='store_true', help='Alibaba Cloud Model Studio: send enable_thinking=false (no /no_think tag)')
    ap.add_argument('--chat-template-kwargs', action='store_true', help='send enable_thinking=false (vLLM-based providers)')
    a = ap.parse_args()
    (run_payments if a.test == 'payments' else run_merchants)(a)
