# Fuzz4All + Error-Guided Repair

> **Course project — CS8602 / CS7602: *Using AI to Explore a Security Research Problem*.**
> Built on top of [Fuzz4All (ICSE '24)](https://arxiv.org/abs/2308.04748) by Xia et al. The original
> code, prompts, and language documentation are reused as-is. The contributions in this repo are the
> **error-guided repair stage**, the **structured evaluator**, and the **AI-driven search harness**
> described below.

> *This `README.md` describes the course-project extension. The upstream Fuzz4All (ICSE '24)
> artifact instructions are preserved verbatim in `[README_artifact.md](README_artifact.md)`.*

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


| Metric                | Baseline | + Repair  | Δ          |
| --------------------- | -------- | --------- | ---------- |
| `valid_rate`          | 0.595    | **0.800** | **+0.205** |
| `unique_valid_rate`   | 0.490    | **0.655** | **+0.165** |
| `total_compiled_ok`   | 119      | **160**   | **+41**    |
| `repair_success_rate` | —        | 0.535     | —          |


Numbers come straight from
`[outputs/baseline_repro_7b_200/metrics.json](outputs/baseline_repro_7b_200/metrics.json)` and
`[outputs/repair_repro_7b_200/metrics.json](outputs/repair_repro_7b_200/metrics.json)` — the
final-submission re-run. The midterm run on the same setup reported a consistent +0.130 jump in
`valid_rate`; both runs are listed under [Recorded results](#recorded-results) below.

The repair policy used here (T1, `max_attempts=2`, `error_gate=compile_error`,
`repair.temperature=0.7`) is the same policy family the AI search loop ablated around in round 2 —
see [§AI search script](#ai-search-script). The 1B search and the 7B headline are not separate
experiments: the search explored policy space efficiently on the 1B model and the headline applies
the validated policy at scale.

---

## Where to find each rubric item


| Final-submission rubric item                             | Where in this repo                                                                                                                                                                      |
| -------------------------------------------------------- | --------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| Evaluator                                                | `[tools/evaluate_candidate.py](tools/evaluate_candidate.py)` — usage in [§Evaluator script](#evaluator-script)                                                                          |
| AI search script                                         | `[tools/run_search_round.py](tools/run_search_round.py)` — usage in [§AI search script](#ai-search-script)                                                                              |
| Configuration — prompts                                  | `[prompts/repair/T1.txt](prompts/repair/T1.txt)` … `[T6.txt](prompts/repair/T6.txt)` (six repair templates)                                                                             |
| Configuration — config files                             | `[config/*.yaml](config)` (baseline, repair, demo, smoke variants)                                                                                                                      |
| README — install dependencies                            | [§Installation (dependencies)](#installation-dependencies)                                                                                                                              |
| README — run a small demo                                | `bash scripts/demo.sh` — see [§Small demo and reduced-scale reproduction](#small-demo-and-reduced-scale-reproduction)                                                                   |
| README — reproduce key findings on a reduced scale       | Same demo script, configs `[cpp_demo_n20.yaml](config/cpp_demo_n20.yaml)` + `[cpp_repair_demo_n20.yaml](config/cpp_repair_demo_n20.yaml)`                                               |
| Recorded full-scale evidence (N = 200)                   | `[outputs/baseline_repro_7b_200/](outputs/baseline_repro_7b_200)`, `[outputs/repair_repro_7b_200/](outputs/repair_repro_7b_200)`                                                        |
| Recorded search-round evidence (12 candidates, 2 rounds) | `[outputs/search/](outputs/search)` (`search_log.jsonl`, `next_prompt.md`, 12 `eval_`* folders)                                                                                         |
| AI-driven loop — LLM proposal evidence                   | `[outputs/search/ai_proposals/round_01_to_round_02.md](outputs/search/ai_proposals/round_01_to_round_02.md)` (round-1 evaluator summary, LLM-proposed `round_02.json`, round-2 outcome) |


---

## What this fork adds

The original Fuzz4All loop is *generate → validate → keep if valid*; failing programs are discarded.
This fork inserts a **repair stage** before the discard:

```
generate ─► compile (g++ -c) ─► OK ─► keep
                       │
                       └─► FAIL ─► repair (LLM + stderr) ─► recompile ─► keep if OK
```


| Component             | What it does                                                                          | Where it lives                                            |
| --------------------- | ------------------------------------------------------------------------------------- | --------------------------------------------------------- |
| Structured validation | Returns `ValidationResult` (status, exit code, elapsed, stderr, normalized signature) | `Fuzz4All/target/target.py`, `Fuzz4All/target/CPP/CPP.py` |
| Repair stage          | Completion-style prompt with compiler `stderr`; six templates (T1…T6)                 | `Fuzz4All/repair/repair.py`, `prompts/repair/`            |
| Repair cache          | Reuses past repairs keyed by failure signature                                        | `outputs/<run>/repair_cache.json`                         |
| Per-run logs          | One JSONL record per program / repair attempt + a summary metrics file                | `outputs/<run>/records.jsonl`, `metrics.json`             |
| Fixed evaluator       | Repeats a candidate config under a fixed budget, aggregates mean / std                | `tools/evaluate_candidate.py`                             |
| Search harness        | Evaluates a JSON list of candidates and emits a prompt for the next round             | `tools/run_search_round.py`                               |


No paid APIs. Repair reuses the same local LLM (StarCoderBase) that already does generation.

---

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


| Metric (N = 20)       | Baseline  | Repair    | Δ                  |
| --------------------- | --------- | --------- | ------------------ |
| `total_compiled_ok`   | 11–13     | 14–19     | +3 to +7           |
| `valid_rate`          | 0.55–0.60 | 0.70–0.95 | **+0.15 to +0.35** |
| `unique_valid_rate`   | ~0.50     | ~0.75     | +0.20 to +0.30     |
| `repair_success_rate` | —         | 0.40–0.75 | —                  |


`avg_time_per_program` scales from ~0.25 s baseline to ~2–8 s repair (the LLM is invoked again per
failure). The headline trend is consistently positive: across two independent demo runs we
observed Δ `valid_rate` of **+0.350** and **+0.150** (mean **+0.250**), in line with the recorded
full-scale Δ of **+0.205** at N = 200.

The demo configs are dedicated copies so the originals (N = 200) stay usable for full-scale
reproduction:

- `[config/cpp_demo_n20.yaml](config/cpp_demo_n20.yaml)` — baseline, N = 20, 7B.
- `[config/cpp_repair_demo_n20.yaml](config/cpp_repair_demo_n20.yaml)` — repair, N = 20, 7B.

A 1B "smoke" path also exists (`config/cpp_smoke.yaml`, `config/cpp_repair_smoke.yaml`, ~1 min) but
only confirms the pipeline runs — the model is too small to demonstrate the actual quality
improvement. Use `scripts/demo.sh` for that.

---

---

## AI search loop

The AI-guided search harness is `tools/run_search_round.py`. Each round evaluates a batch of repair-policy candidates, appends per-candidate metrics to `outputs/search/search_log.jsonl`, and writes `outputs/search/next_prompt.md`, which summarizes ranked results and example failure signatures for the next proposal round.

Archived search evidence is included in:

- `outputs/search/`
- `outputs/search/ai_proposals/round_01_to_round_02.md`

Example command:

```bash
python tools/run_search_round.py \
  --round candidates/round_01.json \
  --base_config config/cpp_repair_demo.yaml \
  --budget_programs 100 \
  --repeats 1

## Repository layout

```

fuzz4all-cs-final/
├── Fuzz4All/
│   ├── fuzz.py                      # main fuzzing loop (with repair hook)
│   ├── make_target.py
│   ├── model.py
│   ├── repair/
│   │   └── repair.py                # repair stage + RepairConfig + templates
│   ├── target/
│   │   ├── target.py                # ValidationResult, CompileStatus
│   │   └── CPP/
│   │       └── CPP.py               # g++ -c compile-only oracle
│   └── util/
├── prompts/
│   └── repair/
│       └── T1.txt … T6.txt          # completion-style repair templates
├── tools/
│   ├── evaluate_candidate.py        # fixed-budget evaluator
│   └── run_search_round.py          # AI-driven search harness
├── scripts/
│   └── demo.sh                      # 2–4 min reduced-scale reproduction (N=20, 7B)
├── config/
│   ├── cpp_demo.yaml                # baseline       (N = 200, 7B)
│   ├── cpp_repair_demo.yaml         # repair         (N = 200, 7B)
│   ├── cpp_demo_n20.yaml            # demo baseline  (N = 20,  7B)
│   ├── cpp_repair_demo_n20.yaml     # demo repair    (N = 20,  7B)
│   ├── cpp_smoke.yaml               # 1B smoke (pipeline check)
│   ├── cpp_repair_smoke.yaml
│   ├── cpp_smoke_n50.yaml           # HPC / README demo (N = 50, 1B)
│   ├── cpp_repair_smoke_n50.yaml
│   ├── ablation/                    # upstream Fuzz4All ablation configs
│   ├── targeted/
│   ├── full_run/
│   └── documentation/               # per-language prompt docs (upstream)
├── candidates/
│   ├── round_01.json
│   ├── round_02.json
│   └── materialized/                # YAMLs materialized from candidate JSON
├── docs/
│   ├── COURSE_PROJECT.md            # extension docs (metrics, options)
│   └── DEMO_EXECUTION.md            # copy-paste HPC demo (also appended below)
├── outputs/                         # run artefacts (e.g. *_repro_7b_200/, search/, eval_smoke/)
├── README.md                        # this file
├── README_artifact.md               # original ICSE '24 artifact instructions
├── requirements.txt
└── setup.py

```


# Demo execution guide — N = 50 (StarCoderBase-1B)

End-to-end, copy-paste path that works on a **fresh machine / HPC compute node**. Every command below is one we have run successfully. Replace **`/path/to/your/fuzz4all-cs-final`** with the real clone path on your machine (e.g. `~/fuzz4all-cs-final`).

**What this produces:** baseline vs repair fuzzing at **N = 50** with **`bigcode/starcoderbase-1b`**, then a **comparison table**.

> **Tip:** open this file alongside the terminal. Run **one numbered step at a time** and only move on when the verification at the end of that step works.

---

## 1. (HPC only) Get a compute node

The login node is shared and slow. Reserve a workstation first.

1. SSH into your cluster the way your course documents (e.g. `ssh <user>@login-student-lab.<your-domain>`). Your prompt will look like `<user>@zap-fe-1` or similar.
2. (Recommended) Start a `tmux` session so an SSH disconnect does **not** kill your work:

   ```bash
   tmux new -s fuzzdemo
```

   To detach later: press `Ctrl-b` then `d`. To reattach: `tmux attach -t fuzzdemo`.
3. Reserve a workstation with Slurm (use your lab’s exact flags — this is the pattern from MBZUAI’s docs):

   Wait until you see `salloc: Granted job allocation` and the prompt switches to a workstation hostname (e.g. `ws-l1-001`). **Do not run anything heavy until you see this.**
4. Confirm the GPU:

   Note the `**Driver Version`** and `**CUDA Version**` lines from the header — you will use the CUDA number in step 4. You should also see your GPU listed (e.g. `NVIDIA RTX 5000 Ada Generation`, 32 GB).

If you are on a personal Linux machine that already has `g++` and an NVIDIA GPU, skip this section.

---

## 2. Conda environment (Python 3.10)

The project pins older packages (e.g. `pandas==2.0.3`) that fail on Python **3.13**. Use **3.10**.

1. Create the env (one time per machine):
  ```bash
   conda create -n fuzz4all python=3.10 -y
  ```
2. Activate it:
  ```bash
   conda activate fuzz4all
  ```
3. Verify the interpreter is the new env (not `base` / 3.13):
  ```bash
   python --version
   which python
  ```
   You must see `**Python 3.10.x**` and a path under `**.../envs/fuzz4all/...**`.
   Then re-run step 3.

---

## 3. Install project dependencies

Run inside the activated `fuzz4all` env, from the **repo root**:

1. Go to the repo:
  ```bash
   cd /path/to/your/fuzz4all-cs-final or You will be in same folder
  ```
2. Upgrade packaging tools (prevents the `pkg_resources` / `Failed to build pandas` errors):
  ```bash
   python -m pip install --upgrade pip setuptools wheel
  ```
3. Install Python requirements:
  ```bash
   python -m pip install -r requirements.txt
  ```
4. Install this project itself in editable mode (registers `Fuzz4All` as a package):
  ```bash
   python -m pip install -e .
  ```
5. Quick sanity check (should print versions, no import error):
  ```bash
   python -c "import torch, pandas; print('ok', torch.__version__, pandas.__version__)"
  ```

---

## 4. Install a GPU-matching PyTorch (CUDA 12.x)

The `torch` from `requirements.txt` may not match the lab’s NVIDIA driver and you will see `**The NVIDIA driver on your system is too old**` at runtime. Replace it with the CUDA build that matches `nvidia-smi`.

1. Uninstall whatever version was installed by `requirements.txt`: if it does not match your driver
  ```bash
   pip uninstall -y torch torchvision torchaudio
  ```
2. Install the CUDA 12.4 wheel (matches `CUDA Version: 12.4` from `nvidia-smi`):
  ```bash
   pip install torch torchvision torchaudio --index-url https://download.pytorch.org/whl/cu124
  ```
   If your `nvidia-smi` shows a different CUDA (e.g. 11.8), use the matching index from [pytorch.org/get-started/locally](https://pytorch.org/get-started/locally/) — for CUDA 11.8: `--index-url https://download.pytorch.org/whl/cu118`.
3. Verify CUDA is visible inside Python:
  ```bash
   python -c "import torch; print(torch.__version__); print('cuda:', torch.cuda.is_available()); print(torch.cuda.get_device_name(0))"
  ```
   You should see something like:
   If `cuda: False`, fix this **before** the fuzz runs (you would otherwise crash mid-run).

---

## 5. Hugging Face — account, gated model, token, terminal login

The model `**bigcode/starcoderbase-1b`** is **gated**: you must have an account, accept the licence on the model page, and use a token that can read gated repositories.

### 5a. Browser steps

1. Go to [huggingface.co/join](https://huggingface.co/join) and **create a free account** (skip if you already have one).
2. Log in at [huggingface.co](https://huggingface.co).
3. Open the model page **while logged in**: [https://huggingface.co/bigcode/starcoderbase-1b](https://huggingface.co/bigcode/starcoderbase-1b).
4. If the page shows **“Agree and access repository”** (or “You need to agree to share your contact information…”), click it and accept. After this, you should be able to see the **Files and versions** tab without a gate banner.
5. Open [https://huggingface.co/settings/tokens](https://huggingface.co/settings/tokens) → **Create new token**.
  - Choose **Classic** (not Fine-grained).
  - Permission: **Read**.
  - Click create, then **copy** the full `hf_…` string. *It is shown only once — keep it somewhere safe for now.*

> Why classic Read? Fine-grained tokens often report `canReadGatedRepos: false` and silently fail to download `starcoderbase-1b`.

### 5b. Terminal steps (inside the `fuzz4all` env)

1. Make sure the Hugging Face client is installed:
  ```bash
   pip install -U "huggingface_hub[cli]"
  ```
2. Set the token in this shell  run the following command
  ```bash
   read -s HF_TOKEN && export HF_TOKEN
  ```
   After `read -s HF_TOKEN && export HF_TOKEN`, press enter and then paste the **full** `hf_...` token below remove brackets press **Enter**. Nothing will appear while pasting (that is normal).
3. Confirm the variable is set and looks reasonable:
  ```bash
   echo ${#HF_TOKEN}
  ```
   You should see a non-trivial number (e.g. **30+**), **not** `0` or `4`.
4. Confirm Hugging Face accepts the token:
  ```bash
   python -c "from huggingface_hub import whoami; print(whoami())"
  ```
   You should see your Hugging Face username in the output.
5. Confirm the gated model is downloadable end-to-end (downloads one tiny file):
  ```bash
   python -c "from huggingface_hub import hf_hub_download; hf_hub_download('bigcode/starcoderbase-1b', 'config.json')"
  ```
   On success it prints a path under `~/.cache/huggingface/...`. If you see **401/403** here, repeat **5a step 4** (accept on the model page) and **5a step 5** (Classic Read token).

> The token is **per-session**: if you open a new terminal, run `read -s HF_TOKEN && export HF_TOKEN` again.

---

## 6. Confirm the N=50 configs

The two configs ship with the repo at `**num: 50`**. Verify before running:

```bash
grep '^  num:' config/cpp_smoke_n50.yaml config/cpp_repair_smoke_n50.yaml
```

Expected output (both lines must say **50**):

```
config/cpp_smoke_n50.yaml:  num: 50
config/cpp_repair_smoke_n50.yaml:  num: 50
```

If either says `10`, edit the file and change `num: 10` to `num: 50` before continuing.

---

## 7. Baseline run (50 programs, no repair)

```bash
rm -rf outputs/baseline_n50_1b

python Fuzz4All/fuzz.py --config config/cpp_smoke_n50.yaml main_with_config \
  --folder outputs/baseline_n50_1b \
  --batch_size 2 \
  --model_name bigcode/starcoderbase-1b \
  --target "$(command -v g++)"
```

What to look for:

- A progress bar that reaches `**50/50**` at the end.
- The folder `**outputs/baseline_n50_1b/**` contains `metrics.json`, `records.jsonl`, and `*.fuzz` files.

---

## 8. Repair run (50 programs, with stderr-guided repair)

```bash
rm -rf outputs/repair_n50_1b

python Fuzz4All/fuzz.py --config config/cpp_repair_smoke_n50.yaml main_with_config \
  --folder outputs/repair_n50_1b \
  --batch_size 2 \
  --model_name bigcode/starcoderbase-1b \
  --target "$(command -v g++)"
```

What to look for:

- Progress reaches `**50/50**`.
- `outputs/repair_n50_1b/` additionally contains `**repair_cache.json**` and accepted `***_r1.fuzz` / `*_r2.fuzz**` files (the repaired programs).
- It is normal for this to take **longer** than baseline — repair calls the LLM again per failed compile.

---

## 9. Comparison table

```bash
export BASE_DIR=outputs/baseline_n50_1b
export REP_DIR=outputs/repair_n50_1b

BASE_DIR="$BASE_DIR" REP_DIR="$REP_DIR" python <<'PY'
import json, glob, os
base = json.load(open(os.path.join(os.environ["BASE_DIR"], "metrics.json")))
rep = json.load(open(os.path.join(os.environ["REP_DIR"], "metrics.json")))
rep_dir = os.environ["REP_DIR"]

def fmt(v):
    if isinstance(v, float):
        return f"{v:.3f}"
    return str(v)

rows = [
    ("total_compiled_ok", "compiled OK / N"),
    ("valid_rate", "valid_rate"),
    ("unique_valid_rate", "unique_valid_rate"),
    ("duplicate_rate", "duplicate_rate"),
    ("repair_attempted_count", "repair_attempted"),
    ("repair_success_count", "repair_success"),
    ("repair_success_rate", "repair_success_rate"),
]
print()
print(f"  {'metric':24s}  {'baseline':>10s}  {'repair':>10s}  {'delta':>10s}")
print(f"  {'-'*24}  {'-'*10}  {'-'*10}  {'-'*10}")
for key, label in rows:
    b, r = base.get(key), rep.get(key)
    if b is None and r is None:
        continue
    bs = fmt(b if b is not None else "-")
    rs = fmt(r if r is not None else "-")
    if isinstance(b, (int, float)) and isinstance(r, (int, float)):
        d = r - b
        ds = f"{d:+.3f}" if isinstance(d, float) else f"{d:+d}"
    else:
        ds = "-"
    print(f"  {label:24s}  {bs:>10s}  {rs:>10s}  {ds:>10s}")
bt = base.get("avg_time_per_program", 0) or 0
rt = rep.get("avg_time_per_program", 0) or 0
print()
print("  cost summary:")
print(f"    avg time / program : {bt:.2f}s  ->  {rt:.2f}s")
dv = (rep.get("valid_rate", 0) or 0) - (base.get("valid_rate", 0) or 0)
rsucc = rep.get("repair_success_count", 0) or 0
n = len(glob.glob(os.path.join(rep_dir, "*_r*.fuzz")))
print()
print(f"  delta valid_rate = {dv:+.3f}  |  repair_success = {rsucc}  |  *_r*.fuzz count = {n}")
print()
PY
```

You will get a table with `baseline`, `repair`, and `delta` columns plus a one-line summary of `delta valid_rate`, `repair_success`, and the count of `*_r*.fuzz` files written.

---

## 10. Recorded full-scale results (no GPU work needed)

Steps 7–9 are only a **small demo** (N = 50, 1B) to prove repair runs; for **stable, reportable** numbers use **N = 200** with **StarCoderBase-7B** (much more VRAM and time — on the order of **~28 GB** and **~1.5 h** per full fuzz on our hardware) or, if available, **15B** (often **~64 GB** or multi-GPU). The repo includes **one pre-recorded** 7B baseline vs repair at N = 200 below. **N = 200** is **one** fuzz job of 200 programs, not 30 repeated runs; default `**--batch_size` 30** only caps how many candidates each `**generate()`** returns, and repair can add extra LLM calls per failure (typically up to `**max_attempts` 2**).

```bash
python -m json.tool outputs/baseline_repro_7b_200/metrics.json
python -m json.tool outputs/repair_repro_7b_200/metrics.json
```

When reading those files, focus on `**valid_rate**`, `**unique_valid_rate**`, and `**repair_success_rate**`.

---

## Notes for the live N=50 table

- The 1B model is **stochastic** and N=50 is small. A single live run can show `**Δ valid_rate < 0`** by chance; what proves the repair stage is working in **any** run is `repair_attempted_count > 0`, `repair_success_count > 0`, and the `***_r*.fuzz`** files written under `outputs/repair_n50_1b/`.
- **Course-scale evidence** is the **N = 200 / 7B** metrics in **step 10** (`baseline_repro_7b_200` vs `repair_repro_7b_200`).

---

## Recorded 7B full-scale results


| Run                                                                                                                                            | `valid_rate` (base → repair) | `unique_valid_rate` (base → repair) | `repair_success_rate` |
| ---------------------------------------------------------------------------------------------------------------------------------------------- | ---------------------------- | ----------------------------------- | --------------------- |
| Midterm — `[outputs/baseline_7b_200/](outputs/baseline_7b_200)`, `[outputs/repair_7b_200/](outputs/repair_7b_200)`                             | 0.605 → **0.735** (Δ +0.130) | 0.485 → **0.690** (Δ +0.205)        | 0.459                 |
| Final repro — `[outputs/baseline_repro_7b_200/](outputs/baseline_repro_7b_200)`, `[outputs/repair_repro_7b_200/](outputs/repair_repro_7b_200)` | 0.595 → **0.800** (Δ +0.205) | 0.490 → **0.655** (Δ +0.165)        | 0.535                 |


Both runs land in the same direction with similar magnitude (Δ `valid_rate` between +0.130 and
+0.205) — the repair gain is real, not a single-run artefact.

Each output folder contains: `metrics.json`, `records.jsonl` (one row per generation and per repair  
attempt), the original `*.fuzz` files, the accepted repair files (`*_r1.fuzz`, `*_r2.fuzz`), and  
`repair_cache.json` (signature → cached repair).

---

## Design tradeoff

Repair pays for itself with a slightly slower per-program time. Cost shows up as a higher
`avg_time_per_program` (a second LLM call is made on each failure that passes the gate); gain shows
up as a higher `valid_rate`:


|                        | Baseline | Repair    |
| ---------------------- | -------- | --------- |
| `avg_time_per_program` | ~0.25 s  | ~2–8 s    |
| `valid_rate` (N = 200) | 0.595    | **0.800** |


## References

- Original paper: [Fuzz4All: Universal Fuzzing with Large Language Models — arXiv:2308.04748](https://arxiv.org/abs/2308.04748)
- Original artifact: [Zenodo 10456883](https://doi.org/10.5281/zenodo.10456883)
- Course-extension docs: `[docs/COURSE_PROJECT.md](docs/COURSE_PROJECT.md)`

```bibtex
@inproceedings{fuzz4all,
  title     = {Fuzz4All: Universal Fuzzing with Large Language Models},
  author    = {Xia, Chunqiu Steven and Paltenghi, Matteo and Tian, Jia Le and Pradel, Michael and Zhang, Lingming},
  booktitle = {Proceedings of the 46th International Conference on Software Engineering},
  series    = {ICSE '24},
  year      = {2024}
}
```

