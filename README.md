# Agentic diagnosis of declined card payments: benchmark, knowledge base and code

This repository contains everything needed to reproduce the experiments in
*Agentic AI for Payment Decline Diagnosis* (Rastogi, 2026): a knowledge base of card-network decline codes,
a payment-level benchmark of 398 scenarios, a merchant-level benchmark of 90 days of transactions for 30 merchants,
the agent and scoring code, and every model output and score reported in the paper.

Everything here is synthetic or built from public card-network and processor documentation.
No cardholder, merchant or company data is included.

## What is in the repository

| File | What it is |
| --- | --- |
| `decline_kb_schema.sql` | Knowledge-base tables and label vocabularies (13 root-cause categories, 10 recommended actions) |
| `decline_kb_seed.sql` | 160 decline codes (Visa, Mastercard, American Express, Discover), 20 decision rules, 27 First Data processor-code mappings, 5 public sources |
| `decline_kb_codes_review.csv` | The codes in spreadsheet form |
| `kb_documents.jsonl` | 213 retrieval documents generated from the knowledge base (variant D) |
| `benchmark_scenarios_answer_key.csv` | 398 payment-level scenarios with answers; 198 are hard cases where context changes the right action |
| `archive_visa15/` | The answer keys and retrieval documents of the first version, which used Visa's earlier limit of 15 attempts |
| `Decline_Study_Labeling_Expert.xlsx` | The blank workbook given to the independent expert (25 timed and 75 labeling scenarios, no answers) |
| `expert/` | The expert's returned workbook (`expert_labels.xlsx`), agreement with the answer key (`agreement.md`) and every disagreement (`disagreements.csv`), reported in Section 7.6 |
| `merchant_transactions.csv` | 44,341 synthetic stored-card transactions for 30 merchants over 90 days |
| `merchant_profiles.csv` | Merchant type, region and size |
| `merchant_answer_key.csv` | The 51 planted decline patterns per merchant, with revenue ranking and risk flags; 4 merchants are clean |
| `system_prompt.txt`, `merchant_system_prompt.txt` | The prompts shared by all model variants |
| `gen_benchmark.py`, `gen_merchants.py`, `make_expert_workbook.py`, `build_training_data.py` | Generators for all of the data above (fixed random seeds) |
| `run_variants.py` | Runs model variants B, C, D and E against any OpenAI-compatible API |
| `evidence_check.py` | The evidence check used by variant E, and an offline mode for checking saved outputs |
| `results/variant_E/` | Variant E scores per run and a summary; `cardholder_keyword_check.py` compares cardholder messages of D and E |
| `score_decline_benchmark.py` | Baselines (variant A), answer parsing, scoring, merchant scoring, averaging over runs, expert agreement |
| `raw/` | Every model output from the three runs of each variant, with latency and token counts |
| `results/` | Scores per run and averaged over runs (`results/averaged_results.md`) |
| `explanation_review_sample.csv` | The manual review of 90 sampled explanations reported in Section 7.3 |
| `finetune_train.jsonl`, `finetune_val.jsonl` | Chat-format training examples from the same knowledge base. Not used in this study; provided for the fine-tuning comparison left to future work |

## The five variants

| Variant | What it sees | Domain knowledge |
| --- | --- | --- |
| A. Lookup table | Network and response code only | Knowledge-base code table |
| B. LLM without tools | Question and the merchant's description | Base model only |
| C. LLM with tools | As B, plus the authorization record (payment test) or an aggregate analysis tool (merchant test) | Base model only |
| D. LLM with tools and retrieval | As C, plus the 5 most relevant knowledge-base documents attached to each tool result | Retrieved at query time |
| E. LLM with tools, retrieval and evidence check | As D; the payment answer must end with an Evidence line citing the record fields and documents it used, and `evidence_check.py` verifies it | Retrieved at query time; citations checked deterministically |

Variants B to E use Qwen3.5-9B (`qwen/qwen3.5-9b`) through OpenRouter, pinned to DeepInfra's unquantized BF16 deployment,
temperature 0, thinking disabled, at most 2,048 output tokens per call. Retrieval uses Qwen3-Embedding-0.6B
(Hugging Face revision `97b0c614be4d77ee51c0cef4e5f07c00f9eb65b3`). Variants B and C were run on 5 and 6 November 2026 and variant D on 11 and 12 November 2026, after the
benchmark was updated to Visa's current reattempt limit (variants B and C were rescored against the updated key; they see
neither the answer key nor the retrieval documents, so the update does not change their outputs). Variant E was run on
22 and 23 November 2026 with the same model, provider and settings as D.

## Reproducing the paper

Python 3.9 or later.

```bash
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
```

### 1. Score the published outputs (no API key needed)

This recomputes every number and table in Section 7 from the outputs in `raw/`.

```bash
python score_decline_benchmark.py lookup-baseline --key benchmark_scenarios_answer_key.csv --schema decline_kb_schema.sql --seed decline_kb_seed.sql --out A.csv
python score_decline_benchmark.py merchant-baseline --transactions merchant_transactions.csv --out A_merchants.csv
for r in 1 2 3; do
  for v in B C D; do python score_decline_benchmark.py parse --raw raw/${v}_run$r.jsonl --out ${v}_run$r.csv; done
  python score_decline_benchmark.py score --key benchmark_scenarios_answer_key.csv --schema decline_kb_schema.sql --seed decline_kb_seed.sql \
    --pred A=A.csv --pred B=B_run$r.csv --pred C=C_run$r.csv --pred D=D_run$r.csv --out results/run$r
  python score_decline_benchmark.py score-merchants --key merchant_answer_key.csv \
    --pred A=A_merchants.csv --pred B=raw/B_merchants_run$r.csv --pred C=raw/C_merchants_run$r.csv --pred D=raw/D_merchants_run$r.csv --out results/run$r
done
python score_decline_benchmark.py average-runs --results results
python score_decline_benchmark.py agreement --key benchmark_scenarios_answer_key.csv --workbook expert/expert_labels.xlsx --out expert
```

### 2. Run the models again

Set an OpenAI-compatible endpoint. To match the paper, use OpenRouter pinned to DeepInfra's BF16 deployment:

```bash
export LLM_BASE_URL=https://openrouter.ai/api/v1
export LLM_API_KEY=<your key>
export LLM_MODEL=qwen/qwen3.5-9b
P=deepinfra/bf16
for v in B C D; do for r in 1 2 3; do
  python run_variants.py payments  --openrouter-provider $P --variant $v --run $r --out raw/${v}_run$r.jsonl
  python run_variants.py merchants --openrouter-provider $P --variant $v --run $r --out raw/${v}_merchants_run$r.csv
done; done
```

Runs resume where they stop, so an interrupted run can be restarted with the same command. The whole study, including the pilot
and the rerun of variant D, used about 26 million tokens in 12,400 requests and cost US$2.64. Then score as in step 1.

To test a different model, change `LLM_MODEL` (and `LLM_BASE_URL` for another provider). Variant D embeds the
retrieval documents on the CPU the first time it runs (`--embed local`); `--embed api` uses the provider's embedding endpoint instead.

### Evidence check (variant E)

`evidence_check.py` is a deterministic validator that admits an answer only if its claims are backed by tool results.
In the payment test the answer gains an Evidence line (`response_code=51; advice_code=MAC 03; doc=<title>`); every cited
field must match the record, every cited document must have been returned, and every code, network, count, region and card
type stated in the explanation must be in the record or the returned documents. An answer that fails is escalated to an
engineer with the reasons attached. In the merchant test every number in a finding's evidence must appear in a tool result,
the codes it cites must be of a kind that shows the pattern, and the evidence must not deny the pattern; failing findings are
dropped. Rules are listed at the top of `evidence_check.py`.

Run variant E (as variant D plus the check, three runs):

```bash
for r in 1 2 3; do
  python run_variants.py payments  --openrouter-provider $P --variant E --run $r --out raw/E_run$r.jsonl
  python run_variants.py merchants --openrouter-provider $P --variant E --run $r --out raw/E_merchants_run$r.csv
  python score_decline_benchmark.py parse --raw raw/E_run$r.jsonl --out E_run$r.csv
done
```

Then score as in step 1 with `--pred E=E_run$r.csv` and `--pred E=raw/E_merchants_run$r.csv` added. Each E output keeps the
model's own answer (`model_output`) beside the checked one, with the check's verdict and reasons; dropped merchant findings
are in `raw/E_merchants_run*_flagged.csv`. `results/evidence_check_offline/` applies the same check to D's published outputs.

### 3. Regenerate the data

The data files are already in the repository; these commands recreate them exactly.

```bash
python gen_benchmark.py decline_kb_schema.sql decline_kb_seed.sql .
python gen_merchants.py .
python build_training_data.py decline_kb_schema.sql decline_kb_seed.sql .
python make_expert_workbook.py . decline_kb_schema.sql decline_kb_seed.sql Decline_Study_Labeling_Expert.xlsx
```

## Notes

- **Leakage control.** The retrieval documents contain knowledge-base facts only; no benchmark scenario, merchant
  report or scenario identifier appears in them.
- **The lookup table and the answer key share a source.** Both are derived from the knowledge base, which is why variant A
  is perfect on standard cases. The hard cases are where context changes the right action.
- **Visa reattempt limit.** The benchmark follows the current Visa Rules (Visa Core Rules and Visa Product and Service Rules,
  Table 7-2): at most 20 authorization attempts per card in 30 days for decline categories 2, 3 and 4, and none for category 1.
  Visa raised the limit from 15 to 20 on 25 May 2025. The 40 retry-limit scenarios have 15 to 24 earlier attempts, so half are
  beyond the limit and half are close to it but still allowed.
- **Expert files.** In both workbooks the author's first name in two instruction lines is replaced with "the author"; the expert's answers and times are unchanged.
- **Hallucination flags** are automated and only detect codes that do not exist on the scenario's network.
  Misreadings of real codes appear as category errors instead.
- **Card-network documentation changes.** The knowledge base is a snapshot of public sources as of 2026; each code links to its source.

## Versions

- **v1.1** adds the evidence check and variant E, and restores `benchmark_scenarios_answer_key.csv`: in v1.0 a
  spreadsheet save had removed the leading zeros of 81 response codes (05 became 5) and trailing zeros in the amount column.
  Variants A to D were run on the intact file, and the scorer reads both forms identically, so no published score changes.
- **v1.0** data and code for variants A to D.

## Citation

```
Rastogi, V. (2026). Agentic AI for Payment Decline Diagnosis: What the Agent Needs, and What It Still Misses.
Data and code: https://github.com/vrastogi13/payment-decline-diagnosis, archived at Zenodo
(v1.0: https://doi.org/10.5281/zenodo.24328510; later versions are listed on the same Zenodo record)
```

## License

Code is released under the MIT License (`LICENSE`). Data, prompts and model outputs are released under the
Creative Commons Attribution 4.0 International License (`LICENSE-DATA`).
