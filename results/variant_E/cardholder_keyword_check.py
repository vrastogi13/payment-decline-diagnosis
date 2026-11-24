"""Keyword rule for cardholder messages that hint at the decline reason, used to compare variants D and E in Section 7.3.
Run from decline_study_toolkit: python results/variant_E/cardholder_keyword_check.py
It is broader than the manual count reported for B, C and D, so its rates are comparable only with each other."""
import json,re,sys
PAT=re.compile(r'fund|balance|spending limit|credit limit|\blimit\b|over ?limit|exceed|restrict|security|fraud|suspicious|lost|stolen|blocked|frozen|insufficient|available credit', re.I)
AUTH=re.compile(r'security check|security verification|verify (your|the) (card|identity)|authenticat|verify your identity|3-?d ?secure|one-time (pass)?code|confirm the payment in your bank', re.I)
def msg(o):
    for line in (o or '').splitlines():
        if line.lower().startswith('cardholder message'): return line.split(':',1)[1]
    return ''
def rate(files, field='output'):
    n=d=0
    for f in files:
        for l in open(f):
            j=json.loads(l); m=msg(j.get(field) or j['output']); n+=1
            if PAT.search(m) and not (AUTH.search(m) and not re.search(r'fund|limit|fraud|stolen|lost|restrict|balance',m,re.I)): d+=1
    return d/n, n
for v in 'BCD':
    print(v, rate([f'raw/{v}_run{r}.jsonl' for r in (1,2,3)]))
print('E', rate([f'raw/E_run{r}.jsonl' for r in (1,2,3)],'model_output'))
