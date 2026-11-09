"""Build Varun's labeling workbook. Usage: python make_varun_workbook.py <out_dir> <schema.sql> <seed.sql> <xlsx_path>"""
import sys, json
import duckdb
from openpyxl import Workbook
from openpyxl.styles import Font, PatternFill, Alignment, Border, Side
from openpyxl.worksheet.datavalidation import DataValidation
from openpyxl.utils import get_column_letter

OUT, SCHEMA, SEED, XLSX = sys.argv[1:5]
scen = {s['scenario_id']: s for s in json.load(open(f'{OUT}/_scenarios.json'))}
sets = json.load(open(f'{OUT}/varun_sets.json'))
db = duckdb.connect(); db.execute(open(SCHEMA).read()); db.execute(open(SEED).read())
cats = db.execute('select category, description from decline_category order by category').fetchall()
acts = db.execute('select action, description, actor from recommended_action order by action').fetchall()
def label(k): return k.replace('_', ' ').capitalize()

F = 'Arial'
H = Font(name=F, bold=True, color='FFFFFF', size=10); HF = PatternFill('solid', fgColor='1F3A5F')
IN = PatternFill('solid', fgColor='FFF2CC'); CTX = PatternFill('solid', fgColor='F2F5F9')
B = Font(name=F, size=10); EX = Font(name=F, size=10, italic=True, color='7F7F7F')
thin = Side(style='thin', color='BFC8D4'); BOX = Border(top=thin, bottom=thin, left=thin, right=thin)
WRAP = Alignment(wrap_text=True, vertical='top')

wb = Workbook()
# ---------------- Instructions ----------------
ws = wb.active; ws.title = 'Instructions'
lines = [
 ('Decline diagnosis study: expert labeling', True),
 ('Thank you for helping. This workbook has two parts and should take about 3 to 4 hours in total.', False),
 ('', False),
 ('Please do Part 1 before you open Part 2, and do not discuss the scenarios with Vaibhav until you have finished both.', True),
 ('', False),
 ('Part 1: Timed diagnosis (25 scenarios)', True),
 ('Each row is a declined card payment with the question a support agent might ask. Diagnose it the way you would at work, using any references you normally use (network documentation, processor guides, search).', False),
 ('For each row, write your diagnosis in your own words, pick the next step from the list, say whether you would escalate to an engineer, and record how many minutes it took you.', False),
 ('Time each scenario on its own, from first reading the row to finishing your answer. Rough minutes are fine.', False),
 ('', False),
 ('Part 2: Labeling (75 scenarios)', True),
 ('For each row, choose the root-cause category, the recommended next step, whether a retry is allowed, and whether to escalate, all from the drop-down lists. Add a confidence level and any notes, especially where you think more than one answer is defensible.', False),
 ('Definitions of every category and action are on the Reference sheet.', False),
 ('', False),
 ('How to fill in', True),
 ('Only the yellow columns need input. Grey columns describe the scenario and should not be changed.', False),
 ('The first row of each part is a worked example in grey italics showing the expected format. Leave it as it is.', False),
 ('"Advice code" is the Mastercard Merchant Advice Code (MAC) or Visa decline category returned with the decline, when there was one.', False),
 ('"Code source" says whether the response code is the card network\'s code or the processor\'s own code (First Data). Processor codes differ from network codes.', False),
 ('"Merchant report" is what the merchant or account manager told support, in their own words. It may be incomplete or misleading.', False),
 ('"Retries in last 30 days" counts earlier attempts on this card by this merchant.', False),
 ('All scenarios are synthetic. No real cardholder or merchant data is included.', False),
 ('', False),
 ('When you finish, save the file and send it back to Vaibhav.', True),
]
for i, (t, bold) in enumerate(lines, 1):
    c = ws.cell(row=i, column=1, value=t); c.font = Font(name=F, size=12 if i == 1 else 10, bold=bold); c.alignment = Alignment(wrap_text=True, vertical='top')
ws.column_dimensions['A'].width = 110

# ---------------- Reference ----------------
ref = wb.create_sheet('Reference')
ref['A1'] = 'Root-cause categories'; ref['A1'].font = Font(name=F, bold=True, size=11)
ref.append(['Category', 'Meaning'])
for c in ref[2]: c.font = H; c.fill = HF
for k, d in cats: ref.append([label(k), d])
cat_first, cat_last = 3, 2 + len(cats)
start = cat_last + 3
ref.cell(row=start, column=1, value='Recommended next steps').font = Font(name=F, bold=True, size=11)
ref.cell(row=start + 1, column=1, value='Next step'); ref.cell(row=start + 1, column=2, value='Meaning'); ref.cell(row=start + 1, column=3, value='Who acts')
for col in (1, 2, 3):
    ref.cell(row=start + 1, column=col).font = H; ref.cell(row=start + 1, column=col).fill = HF
for i, (k, d, a) in enumerate(acts):
    ref.cell(row=start + 2 + i, column=1, value=label(k)); ref.cell(row=start + 2 + i, column=2, value=d); ref.cell(row=start + 2 + i, column=3, value=a.capitalize())
act_first, act_last = start + 2, start + 1 + len(acts)
for row in ref.iter_rows(min_row=1, max_row=act_last):
    for c in row:
        if c.font is None or not c.font.bold: c.font = B
ref.column_dimensions['A'].width = 28; ref.column_dimensions['B'].width = 80; ref.column_dimensions['C'].width = 12

CTX_COLS = [('Scenario ID', 'scenario_id', 11), ('Question', 'question', 36), ('Merchant report', 'merchant_report', 36),
            ('Network', 'network', 11), ('Code source', 'code_source', 10), ('Response code', 'response_code', 10),
            ('Advice code', 'advice_code', 13), ('Transaction type', 'transaction_type', 20), ('Merchant type', 'merchant_type', 22),
            ('Amount', 'amount', 9), ('Currency', 'currency', 8), ('Card type', 'card_type', 9), ('Card region', 'card_region', 13),
            ('Attempt #', 'attempt_number', 8), ('Previous attempt', 'previous_attempt', 20), ('Retries in last 30 days', 'retries_last_30_days', 10)]

def build(name, ids, inputs, example):
    sh = wb.create_sheet(name)
    headers = [c[0] for c in CTX_COLS] + [i[0] for i in inputs]
    sh.append(headers)
    for j, c in enumerate(sh[1], 1):
        c.font = H; c.fill = HF; c.alignment = Alignment(wrap_text=True, vertical='center'); c.border = BOX
    sh.row_dimensions[1].height = 32
    sh.append(example)
    for c in sh[2]: c.font = EX; c.alignment = WRAP; c.border = BOX
    for sid in ids:
        s = scen[sid]
        def show(k):
            if k == 'network': return s[k].capitalize().replace('Amex', 'American Express')
            if k == 'code_source': return 'Processor (First Data)' if s[k] == 'processor' else 'Network'
            return s[k]
        vals = [show(k) for _, k, _ in CTX_COLS]
        sh.append(vals + [None] * len(inputs))
    n = len(CTX_COLS)
    for r in range(3, 3 + len(ids)):
        for col in range(1, n + len(inputs) + 1):
            c = sh.cell(row=r, column=col); c.font = B; c.alignment = WRAP; c.border = BOX
            c.fill = CTX if col <= n else IN
    for j, (_, _, w) in enumerate(CTX_COLS, 1): sh.column_dimensions[get_column_letter(j)].width = w
    for j, (_, kind, w) in enumerate(inputs, n + 1):
        sh.column_dimensions[get_column_letter(j)].width = w
        rng_ = f'{get_column_letter(j)}3:{get_column_letter(j)}{2 + len(ids)}'
        dv = None
        if kind == 'category': dv = DataValidation(type='list', formula1=f'=Reference!$A${cat_first}:$A${cat_last}', allow_blank=True)
        elif kind == 'action': dv = DataValidation(type='list', formula1=f'=Reference!$A${act_first}:$A${act_last}', allow_blank=True)
        elif kind == 'yesno': dv = DataValidation(type='list', formula1='"Yes,No"', allow_blank=True)
        elif kind == 'retry': dv = DataValidation(type='list', formula1='"Yes,No,Only after a change"', allow_blank=True)
        elif kind == 'conf': dv = DataValidation(type='list', formula1='"High,Medium,Low"', allow_blank=True)
        elif kind == 'minutes': dv = DataValidation(type='decimal', operator='between', formula1='0', formula2='240', allow_blank=True)
        if dv:
            dv.error = 'Please choose from the list.' if kind != 'minutes' else 'Enter minutes between 0 and 240.'
            sh.add_data_validation(dv); dv.add(rng_)
    sh.freeze_panes = 'C3'
    return sh

ex_ctx = ['EX-1', 'A subscription payment was declined. What went wrong and should the merchant retry?',
          'The card was saved a few years ago and the renewal suddenly started failing this month.', 'Visa', 'Network', '54', '',
          'Recurring renewal', 'Video streaming subscription', '14.99', 'USD', 'Credit', 'United States', 1, 'None (first attempt)', 0]
build('Part 1 Timed', sets['timed'],
      [('Your diagnosis: why did it fail?', 'text', 40), ('Recommended next step', 'action', 24), ('Escalate to an engineer?', 'yesno', 12),
       ('Minutes taken', 'minutes', 10), ('References used', 'text', 26)],
      ex_ctx + ['The card on file has expired, so the renewal was declined.', 'Update credential', 'No', 4, 'Visa response code list'])
build('Part 2 Labeling', sets['labeling'],
      [('Root-cause category', 'category', 22), ('Recommended next step', 'action', 24), ('Retry allowed?', 'retry', 14),
       ('Escalate to an engineer?', 'yesno', 12), ('Confidence', 'conf', 11), ('Notes', 'text', 34)],
      ex_ctx + ['Expired card', 'Update credential', 'Only after a change', 'No', 'High', 'An account updater would likely fix this.'])
wb.move_sheet('Reference', offset=2)
wb.save(XLSX)
print('saved', XLSX)
