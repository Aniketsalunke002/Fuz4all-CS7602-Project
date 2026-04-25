<h1 align="center">🌌️ Fuzz4All + Error-Guided Repair</h1>

<p align="center">
  <a href="https://arxiv.org/abs/2308.04748"><img src="https://img.shields.io/badge/arXiv-2308.04748-b31b1b.svg?style=for-the-badge"></a>
  <a href="https://doi.org/10.5281/zenodo.10456883"><img src="https://img.shields.io/badge/DOI-10456883-blue?style=for-the-badge"></a>
  <a href="LICENSE"><img src="https://img.shields.io/badge/license-CC--BY-green?style=for-the-badge"></a>
</p>

This repository contains the source code for the ICSE'24 paper *"Fuzz4All: Universal Fuzzing with Large Language Models"* together with a course-project extension that adds an **error-guided repair stage**, a **fixed evaluator**, and an **AI-driven search harness** for C++ compiler fuzzing.

---

## ✨ What this fork adds

The original Fuzz4All loop is: *generate → validate → keep if valid*. Failing programs are simply discarded.

This fork inserts a **repair stage** between *validate* and *discard*:

```
generate ─► compile (g++ -c) ─► OK ─► keep
                       │
                       └─► FAIL ─► repair (LLM + stderr) ─► recompile ─► keep if OK
```

| Component | What it does | Where it lives |
|---|---|---|
| Structured validation | Returns `ValidationResult` (status, exit code, elapsed, stderr, normalized signature) | `Fuzz4All/target/target.py`, `Fuzz4All/target/CPP/CPP.py` |
| Repair stage | Completion-style prompt with compiler `stderr`; six templates (T1…T6) | `Fuzz4All/repair/repair.py`, `prompts/repair/` |
| Repair cache | Reuses past repairs keyed by failure signature | `outputs/<run>/repair_cache.json` |
| Per-run logs | One JSONL record per program/attempt + a summary metrics file | `outputs/<run>/records.jsonl`, `metrics.json` |
| Fixed evaluator | Repeats a candidate config under a fixed budget, aggregates mean/std | `tools/evaluate_candidate.py` |
| Search harness | Evaluates a JSON list of candidates and emits a prompt for the next round | `tools/run_search_round.py` |

No paid APIs are used. Repair reuses the same local LLM (StarCoderBase) already used for generation.

---

## 📊 Recorded Results (StarCoderBase-7B, 200 programs, `g++ -c`)

| Metric | Baseline | Repair | Δ |
|---|---:|---:|---:|
| `valid_rate` | 0.605 | **0.735** | **+0.130** |
| `unique_valid_rate` | 0.485 | **0.690** | **+0.205** |
| `duplicate_rate` | 0.120 | **0.045** | −0.075 |
| `repair_success_rate` | — | **0.459** | — |
| `total_compiled_ok` (of 200) | 121 | **147** | +26 |
| Repaired programs accepted | — | **45** | — |

- Full evidence: [`outputs/baseline_7b_200/`](outputs/baseline_7b_200), [`outputs/repair_7b_200/`](outputs/repair_7b_200) (`metrics.json`, `records.jsonl`, `.fuzz` and `_r*.fuzz` samples, `repair_cache.json`).
- Evaluator example: [`outputs/eval_smoke/`](outputs/eval_smoke) (`summary.csv`, `summary_mean_std.json`).
- Search-harness example: [`outputs/search/`](outputs/search) (`search_log.jsonl`, `next_prompt.md`).

---

## ⚖️ Design Tradeoffs

Repair invests an additional LLM call on each failing program in exchange for recovering it. We measure this with `llm_overhead` (LLM calls per valid program produced), which is the standard cost-side metric for LLM-driven pipelines:

| | Baseline | Repair |
|---|---:|---:|
| `llm_overhead` (calls per valid program) | ~0.4 | ~1.3 |
| `valid_rate` | 0.605 | **0.735** |

In short, repair spends roughly **one extra LLM call per valid program** in exchange for **+13 points of `valid_rate`** and **+20.5 points of `unique_valid_rate`**. Two design knobs keep this overhead bounded by construction:

- **`error_gate`** — only specific failure classes (e.g. `compile_error`) trigger repair, so ICE / crash / timeout cases can be skipped.
- **Repair cache (`repair_cache.json`)** — recurring failure signatures reuse a cached repair instead of calling the LLM again.

For latency-sensitive runs, setting `repair.enabled: false` restores the original Fuzz4All behavior with zero overhead.

---

## ⚡ Setup

Tested on Linux + CUDA (RTX 5000) with `conda` and Python 3.10. Docker is **not** required.

```bash
conda create -n fuzz4all python=3.10 -y
conda activate fuzz4all
pip install -r requirements.txt
pip install -e .
export PYTHONPATH=$PWD:$PYTHONPATH
```

A C++ compiler must be on `PATH` (the target):

```bash
g++ --version   # any modern g++ that supports -std=c++23
```

If you want to use a gated HuggingFace model (e.g. `bigcode/starcoderbase-7b`), accept its license on the HuggingFace website once and then log in:

```bash
python -c "from huggingface_hub import login; login()"
```

---

## 🚀 Run the experiment in 3 steps

### Step 1 — Baseline run

```bash
python Fuzz4All/fuzz.py --config config/cpp_demo.yaml main_with_config \
  --folder outputs/baseline_run \
  --batch_size 4 \
  --model_name bigcode/starcoderbase-7b \
  --target "$(command -v g++)"
```

### Step 2 — Repair-enabled run

```bash
python Fuzz4All/fuzz.py --config config/cpp_repair_demo.yaml main_with_config \
  --folder outputs/repair_run \
  --batch_size 4 \
  --model_name bigcode/starcoderbase-7b \
  --target "$(command -v g++)"
```

### Step 3 — Compare metrics

```bash
echo "=== BASELINE ===" && python -m json.tool outputs/baseline_run/metrics.json
echo "=== REPAIR  ===" && python -m json.tool outputs/repair_run/metrics.json
```

The repair run additionally produces `*_r1.fuzz`, `*_r2.fuzz` files for accepted repairs and a `repair_cache.json` keyed by normalized failure signature.

> **Tip:** for a fast smoke test, swap the configs above for `config/cpp_smoke.yaml` and `config/cpp_repair_smoke.yaml`.

---

## 🧪 Evaluator (fixed budget, repeats)

Run a candidate config under a fixed budget with multiple repeats and aggregate mean/std:

```bash
python tools/evaluate_candidate.py \
  --candidate config/cpp_repair_demo.yaml \
  --out outputs/eval_demo \
  --budget_programs 100 \
  --repeats 3 \
  --target "$(command -v g++)"
```

Outputs:

- `outputs/eval_demo/run_0/`, `run_1/`, `run_2/` — full per-run logs and `metrics.json`.
- `outputs/eval_demo/summary.csv` — one row per repeat.
- `outputs/eval_demo/summary_mean_std.json` — aggregated mean and std for every metric.

---

## 🔁 AI-driven search round

1. Define candidates in JSON (see [`candidates/round_01.json`](candidates/round_01.json) for an example).
2. Run a round:

```bash
python tools/run_search_round.py \
  --round candidates/round_01.json \
  --base_config config/cpp_repair_demo.yaml \
  --budget_programs 100 \
  --repeats 1
```

This will:

- Materialize one YAML per candidate under `candidates/materialized/`.
- Invoke the evaluator for each candidate.
- Append all results to `outputs/search/search_log.jsonl`.
- Generate `outputs/search/next_prompt.md` containing ranked metrics and instructions to propose the next round.

You can paste `next_prompt.md` into any AI assistant to obtain the next candidate JSON. No paid API is called from the code.

---

## 📁 Repository layout

```
fuzz4all/
├── Fuzz4All/
│   ├── fuzz.py                      # main fuzzing loop (with repair hook)
│   ├── repair/repair.py             # repair stage + RepairConfig + 6 templates
│   ├── target/target.py             # ValidationResult, CompileStatus
│   └── target/CPP/CPP.py            # g++ -c compile-only oracle
├── prompts/repair/T1..T6.txt        # completion-style repair templates
├── tools/
│   ├── evaluate_candidate.py        # fixed-budget evaluator
│   └── run_search_round.py          # AI-driven search harness
├── config/
│   ├── cpp_demo.yaml                # original baseline
│   ├── cpp_repair_demo.yaml         # repair-enabled
│   ├── cpp_smoke.yaml               # fast baseline smoke test
│   └── cpp_repair_smoke.yaml        # fast repair smoke test
├── candidates/
│   ├── round_01.json                # example search round
│   └── materialized/                # auto-generated YAMLs per candidate
├── docs/
│   ├── COURSE_PROJECT.md            # full extension docs (metrics, options)
│   └── report.tex                   # IEEE-format project report
├── outputs/                         # recorded evidence (baseline_7b_200, repair_7b_200, …)
├── bugs/                            # bugs found by original Fuzz4All
├── README.md                        # this file
├── README_artifact.md               # original ICSE'24 artifact instructions
├── requirements.txt
└── setup.py
```

---

## 📚 References

- Original Fuzz4All paper: [arXiv:2308.04748](https://arxiv.org/abs/2308.04748)
- Original artifact: [Zenodo 10456883](https://doi.org/10.5281/zenodo.10456883)
- Course-extension docs: [`docs/COURSE_PROJECT.md`](docs/COURSE_PROJECT.md)
- Course-project report: [`docs/report.tex`](docs/report.tex)

```bibtex
@inproceedings{fuzz4all,
  title     = {Fuzz4All: Universal Fuzzing with Large Language Models},
  author    = {Xia, Chunqiu Steven and Paltenghi, Matteo and Tian, Jia Le and Pradel, Michael and Zhang, Lingming},
  booktitle = {Proceedings of the 46th International Conference on Software Engineering},
  series    = {ICSE '24},
  year      = {2024}
}
```
