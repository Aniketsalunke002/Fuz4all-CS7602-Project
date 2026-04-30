# Fuzz4All + Error-Guided Repair

> **Course project — CS8602 / CS7602: *Using AI to Explore a Security Research Problem*.**
> Built on top of [Fuzz4All (ICSE '24)](https://arxiv.org/abs/2308.04748) by Xia et al. The original
> code, prompts, and language documentation are reused as-is. The contributions in this repo are the
> **error-guided repair stage**, the **structured evaluator**, and the **AI-driven search harness**
> described below.

> *This `README.md` describes the course-project extension. The upstream Fuzz4All (ICSE '24)
> artifact instructions are preserved verbatim in [`README_artifact.md`](README_artifact.md).*

> *Attribution: files under `Fuzz4All/repair/`, `prompts/repair/`, `tools/`, `scripts/`, and the
> `repair:` section of any `config/*.yaml` are course-project additions. Everything else is reused
> from upstream Fuzz4All (CC-BY).*

LLM-based fuzzers throw away every program that fails to compile. This project asks one concrete
question:

> *Can compiler feedback (`stderr`) be used as a repair signal to recover the partially-correct
> programs instead of discarding them?*

The answer, on a course-scale but honest setup, is **yes** — and by a margin that's larger than
the run-to-run noise.

**Why it's a security problem.** Compiler fuzzing is a recognised path to surfacing
security-relevant compiler defects — miscompiles, sanitiser bypasses, and internal compiler errors
that mask undefined behaviour. Improving the rate at which an LLM-based fuzzer produces *valid*
programs directly increases the rate at which downstream differential and sanitiser oracles can
be applied to find such defects: the repair stage turns near-miss generations into usable
fuzzing-corpus inputs instead of throwing them away.

## Headline result

StarCoderBase-7B, C++23, N = 200 programs, oracle is `g++ -c`, single RTX 5000:

| Metric                | Baseline | + Repair  |        Δ |
| --------------------- | -------: | --------: | -------: |
| `valid_rate`          |    0.595 | **0.800** | **+0.205** |
| `unique_valid_rate`   |    0.490 | **0.655** | **+0.165** |
| `total_compiled_ok`   |      119 |   **160** |     **+41** |
| `repair_success_rate` |        — |    0.535  |        — |

Numbers come straight from
[`outputs/baseline_repro_7b_200/metrics.json`](outputs/baseline_repro_7b_200/metrics.json) and
[`outputs/repair_repro_7b_200/metrics.json`](outputs/repair_repro_7b_200/metrics.json) — the
final-submission re-run. The midterm run on the same setup reported a consistent +0.130 jump in
`valid_rate`; both runs are listed under [Recorded results](#recorded-results) below.

The repair policy used here (T1, `max_attempts=2`, `error_gate=compile_error`,
`repair.temperature=0.7`) is the same policy family the AI search loop ablated around in round 2 —
see [§AI search script](#ai-search-script). The 1B search and the 7B headline are not separate
experiments: the search explored policy space efficiently on the 1B model and the headline applies
the validated policy at scale.

---

## Where to find each rubric item

| Final-submission rubric item                            | Where in this repo |
|---|---|
| Evaluator                                               | [`tools/evaluate_candidate.py`](tools/evaluate_candidate.py) — usage in [§Evaluator script](#evaluator-script) |
| AI search script                                        | [`tools/run_search_round.py`](tools/run_search_round.py) — usage in [§AI search script](#ai-search-script) |
| Configuration — prompts                                 | [`prompts/repair/T1.txt`](prompts/repair/T1.txt) … [`T6.txt`](prompts/repair/T6.txt) (six repair templates) |
| Configuration — config files                            | [`config/*.yaml`](config) (baseline, repair, demo, smoke variants) |
| README — install dependencies                           | [§Installation (dependencies)](#installation-dependencies) |
| README — run a small demo                               | `bash scripts/demo.sh` — see [§Small demo and reduced-scale reproduction](#small-demo-and-reduced-scale-reproduction) |
| README — reproduce key findings on a reduced scale      | Same demo script, configs [`cpp_demo_n20.yaml`](config/cpp_demo_n20.yaml) + [`cpp_repair_demo_n20.yaml`](config/cpp_repair_demo_n20.yaml) |
| Recorded full-scale evidence (N = 200)                  | [`outputs/baseline_repro_7b_200/`](outputs/baseline_repro_7b_200), [`outputs/repair_repro_7b_200/`](outputs/repair_repro_7b_200) |
| Recorded search-round evidence (12 candidates, 2 rounds)| [`outputs/search/`](outputs/search) (`search_log.jsonl`, `next_prompt.md`, 12 `eval_*` folders) |
| AI-driven loop — LLM proposal evidence                  | [`outputs/search/ai_proposals/round_01_to_round_02.md`](outputs/search/ai_proposals/round_01_to_round_02.md) (round-1 evaluator summary, LLM-proposed `round_02.json`, round-2 outcome) |

---

## What this fork adds

The original Fuzz4All loop is *generate → validate → keep if valid*; failing programs are discarded.
This fork inserts a **repair stage** before the discard:

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
| Per-run logs | One JSONL record per program / repair attempt + a summary metrics file | `outputs/<run>/records.jsonl`, `metrics.json` |
| Fixed evaluator | Repeats a candidate config under a fixed budget, aggregates mean / std | `tools/evaluate_candidate.py` |
| Search harness | Evaluates a JSON list of candidates and emits a prompt for the next round | `tools/run_search_round.py` |

No paid APIs. Repair reuses the same local LLM (StarCoderBase) that already does generation.

---

## Recorded results

Two independent full-scale runs on StarCoderBase-7B, N = 200, same machine:

| Run | `valid_rate` (base → repair) | `unique_valid_rate` (base → repair) | `repair_success_rate` |
|---|---|---|---:|
| Midterm — [`outputs/baseline_7b_200/`](outputs/baseline_7b_200), [`outputs/repair_7b_200/`](outputs/repair_7b_200) | 0.605 → **0.735** (Δ +0.130) | 0.485 → **0.690** (Δ +0.205) | 0.459 |
| Final repro — [`outputs/baseline_repro_7b_200/`](outputs/baseline_repro_7b_200), [`outputs/repair_repro_7b_200/`](outputs/repair_repro_7b_200) | 0.595 → **0.800** (Δ +0.205) | 0.490 → **0.655** (Δ +0.165) | 0.535 |

Both runs land in the same direction with similar magnitude (Δ `valid_rate` between +0.130 and
+0.205) — the repair gain is real, not a single-run artefact.

Each output folder contains: `metrics.json`, `records.jsonl` (one row per generation and per repair
attempt), the original `*.fuzz` files, the accepted repair files (`*_r1.fuzz`, `*_r2.fuzz`), and
`repair_cache.json` (signature → cached repair).

Supporting artefacts:

- Evaluator example: [`outputs/eval_smoke/`](outputs/eval_smoke) (`summary.csv`, `summary_mean_std.json`).
- Search-harness example: [`outputs/search/`](outputs/search) (`search_log.jsonl`, `next_prompt.md`).

---

## Design tradeoff

Repair pays for itself with a slightly slower per-program time. Cost shows up as a higher
`avg_time_per_program` (a second LLM call is made on each failure that passes the gate); gain shows
up as a higher `valid_rate`:

|                          | Baseline | Repair |
| ------------------------ | -------: | -----: |
| `avg_time_per_program`   | ~0.25 s  | ~2–8 s |
| `valid_rate` (N = 200)   |   0.595  | **0.800** |

Two design knobs keep that overhead bounded by construction:

- **`error_gate`** — only specific failure classes (e.g. `compile_error`) trigger repair, so ICE /
  crash / timeout cases are skipped instead of burning extra LLM calls.
- **Repair cache** — recurring failure signatures reuse a cached repair instead of calling the LLM
  again.

For latency-sensitive runs, `repair.enabled: false` restores the original Fuzz4All behaviour with
zero overhead.

---

## Installation (dependencies)

Tested on Linux + CUDA (RTX 5000), `conda`, Python 3.10. Docker is not required.

```bash
conda create -n fuzz4all python=3.10 -y
conda activate fuzz4all
pip install -r requirements.txt
pip install -e .
export PYTHONPATH=$PWD:$PYTHONPATH
```

A C++ compiler must be on `PATH` (this is the target / oracle):

```bash
g++ --version   # any modern g++ that supports -std=c++23
```

For gated HuggingFace models like `bigcode/starcoderbase-7b`, accept the licence on HuggingFace once
and then:

```bash
python -c "from huggingface_hub import login; login()"
```

---

## Small demo and reduced-scale reproduction

*(satisfies the rubric's "run a small demo" and "reproduce key findings on a reduced scale" — single command, ~2–4 min.)*

For a graded demo or a quick sanity check, the packaged demo runs both a baseline and a repair fuzz
at N = 20 (same model, same prompt, same oracle, same repair templates as the full-scale run) and
prints a side-by-side comparison:

```bash
bash scripts/demo.sh
```

What it does, in order:

1. Prints the recorded full-scale numbers from `outputs/baseline_repro_7b_200/` and
   `outputs/repair_repro_7b_200/`.
2. Live baseline run, N = 20, 7B → `outputs/demo_baseline/`.
3. Live repair run, N = 20, 7B, T1, `max_attempts: 2`, `error_gate: compile_error`, cache on →
   `outputs/demo_repair/`.
4. Comparison table + cost summary + a single pass / fail line.

Indicative live output (numbers vary across runs because N is small):

| Metric (N = 20)         | Baseline | Repair    |        Δ |
| ----------------------- | -------: | --------: | -------: |
| `total_compiled_ok`     |   11–13  |   14–19   |  +3 to +7 |
| `valid_rate`            | 0.55–0.60 | 0.70–0.95 | **+0.15 to +0.35** |
| `unique_valid_rate`     |    ~0.50 |     ~0.75 | +0.20 to +0.30 |
| `repair_success_rate`   |        — | 0.40–0.75 |        — |

`avg_time_per_program` scales from ~0.25 s baseline to ~2–8 s repair (the LLM is invoked again per
failure). The headline trend is consistently positive: across two independent demo runs we
observed Δ `valid_rate` of **+0.350** and **+0.150** (mean **+0.250**), in line with the recorded
full-scale Δ of **+0.205** at N = 200.

The demo configs are dedicated copies so the originals (N = 200) stay usable for full-scale
reproduction:

- [`config/cpp_demo_n20.yaml`](config/cpp_demo_n20.yaml) — baseline, N = 20, 7B.
- [`config/cpp_repair_demo_n20.yaml`](config/cpp_repair_demo_n20.yaml) — repair, N = 20, 7B.

A 1B "smoke" path also exists (`config/cpp_smoke.yaml`, `config/cpp_repair_smoke.yaml`, ~1 min) but
only confirms the pipeline runs — the model is too small to demonstrate the actual quality
improvement. Use `scripts/demo.sh` for that.

---

## Full-scale reproduction (~20 min)

To reproduce the recorded N = 200 numbers:

```bash
# Baseline (no repair)
python Fuzz4All/fuzz.py --config config/cpp_demo.yaml main_with_config \
  --folder outputs/baseline_run \
  --batch_size 4 \
  --model_name bigcode/starcoderbase-7b \
  --target "$(command -v g++)"

# Repair-enabled
python Fuzz4All/fuzz.py --config config/cpp_repair_demo.yaml main_with_config \
  --folder outputs/repair_run \
  --batch_size 4 \
  --model_name bigcode/starcoderbase-7b \
  --target "$(command -v g++)"

# Compare
python -m json.tool outputs/baseline_run/metrics.json
python -m json.tool outputs/repair_run/metrics.json
```

The repair run additionally writes `*_r1.fuzz`, `*_r2.fuzz` files for accepted repairs and a
`repair_cache.json` keyed by normalized failure signature.

---

## Evaluator script

*(`tools/evaluate_candidate.py` — fixed budget, multiple repeats, mean / std aggregation. This is the evaluator the rubric asks for.)*

Re-run any candidate config under a fixed budget with multiple repeats and aggregate mean / std:

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

This is the script the search harness calls under the hood.

---

## AI search script

*(`tools/run_search_round.py` — AI-driven search harness. Full evidence in
[`outputs/search/`](outputs/search) and
[`outputs/search/ai_proposals/`](outputs/search/ai_proposals).)*

We used Claude (Anthropic's LLM) as the proposal engine in the AI search loop. After each round,
the evaluator summarized ranked candidate metrics and common failure signatures, and the LLM
proposed the next batch of repair-policy configurations within the fixed candidate schema. These
proposed configurations were then evaluated automatically under the same fixed evaluator. Across
two rounds, we evaluated 12 candidates in total; the AI-proposed second-round ablations helped
validate the repair-policy choices underlying the 7B headline result.

Top candidates by `valid_rate` reached **0.967 – 1.000** at the 30-program budget; per-candidate
metrics in [`outputs/search/search_log.jsonl`](outputs/search/search_log.jsonl). The full
round-1 → round-2 transition — the evaluator summary fed to the LLM, the LLM-proposed
`round_02.json`, and the round-2 outcome — is recorded in
[`outputs/search/ai_proposals/round_01_to_round_02.md`](outputs/search/ai_proposals/round_01_to_round_02.md).

### Run a search round yourself

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
- Generate `outputs/search/next_prompt.md` with ranked metrics + sample failure signatures and instructions for the next round.

Pasting `next_prompt.md` into any AI assistant produces the next candidate JSON. No paid API is invoked from the code itself.

---

## Repository layout

```
fuzz4all-cs-final/
├── Fuzz4All/
│   ├── fuzz.py                      # main fuzzing loop (with repair hook)
│   ├── repair/repair.py             # repair stage + RepairConfig + 6 templates
│   ├── target/target.py             # ValidationResult, CompileStatus
│   └── target/CPP/CPP.py            # g++ -c compile-only oracle
├── prompts/repair/T1..T6.txt        # completion-style repair templates
├── tools/
│   ├── evaluate_candidate.py        # fixed-budget evaluator
│   └── run_search_round.py          # AI-driven search harness
├── scripts/
│   └── demo.sh                      # 2–4 min reduced-scale reproduction
├── config/
│   ├── cpp_demo.yaml                # baseline      (N = 200, 7B)
│   ├── cpp_repair_demo.yaml         # repair        (N = 200, 7B)
│   ├── cpp_demo_n20.yaml            # demo baseline (N = 20,  7B)
│   ├── cpp_repair_demo_n20.yaml     # demo repair   (N = 20,  7B)
│   ├── cpp_smoke.yaml               # 1B smoke (pipeline check only)
│   └── cpp_repair_smoke.yaml        # 1B smoke (pipeline check only)
├── candidates/
│   ├── round_01.json                # example search round
│   └── materialized/                # auto-generated YAMLs per candidate
├── docs/
│   └── COURSE_PROJECT.md            # full extension docs (metrics, options)
├── outputs/                         # recorded evidence
├── README.md                        # this file
├── README_artifact.md               # original ICSE '24 artifact instructions
├── requirements.txt
└── setup.py
```

---

## References

- Original paper: [Fuzz4All: Universal Fuzzing with Large Language Models — arXiv:2308.04748](https://arxiv.org/abs/2308.04748)
- Original artifact: [Zenodo 10456883](https://doi.org/10.5281/zenodo.10456883)
- Course-extension docs: [`docs/COURSE_PROJECT.md`](docs/COURSE_PROJECT.md)

```bibtex
@inproceedings{fuzz4all,
  title     = {Fuzz4All: Universal Fuzzing with Large Language Models},
  author    = {Xia, Chunqiu Steven and Paltenghi, Matteo and Tian, Jia Le and Pradel, Michael and Zhang, Lingming},
  booktitle = {Proceedings of the 46th International Conference on Software Engineering},
  series    = {ICSE '24},
  year      = {2024}
}
```
