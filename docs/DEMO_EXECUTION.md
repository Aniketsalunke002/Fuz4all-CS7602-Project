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

   ```bash
   salloc -N1 -n24
   ```

   Wait until you see `salloc: Granted job allocation` and the prompt switches to a workstation hostname (e.g. `ws-l1-001`). **Do not run anything heavy until you see this.**
4. Confirm the GPU:

   ```bash
   nvidia-smi
   ```

   Note the **`Driver Version`** and **`CUDA Version`** lines from the header — you will use the CUDA number in step 4. You should also see your GPU listed (e.g. `NVIDIA RTX 5000 Ada Generation`, 32 GB).

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

   You must see **`Python 3.10.x`** and a path under **`.../envs/fuzz4all/...`**.

   Then re-run step 3.

---

## 3. Install project dependencies

Run inside the activated `fuzz4all` env, from the **repo root**:

1. Go to the repo:

   ```bash
   cd /path/to/your/fuzz4all-cs-final  # skip if already in repo root
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

The `torch` from `requirements.txt` may not match the lab’s NVIDIA driver and you will see **`The NVIDIA driver on your system is too old`** at runtime. Replace it with the CUDA build that matches `nvidia-smi`.

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

   ```
   2.6.0+cu124
   cuda: True
   NVIDIA RTX 5000 Ada Generation
   ```

   If `cuda: False`, fix this **before** the fuzz runs (you would otherwise crash mid-run).

---

## 5. Hugging Face — account, gated model, token, terminal login

The model **`bigcode/starcoderbase-1b`** is **gated**: you must have an account, accept the licence on the model page, and use a token that can read gated repositories.

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

The two configs ship with the repo at **`num: 50`**. Verify before running:

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
- A progress bar that reaches **`50/50`** at the end.
- The folder **`outputs/baseline_n50_1b/`** contains `metrics.json`, `records.jsonl`, and `*.fuzz` files.


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
- Progress reaches **`50/50`**.
- `outputs/repair_n50_1b/` additionally contains **`repair_cache.json`** and accepted **`*_r1.fuzz` / `*_r2.fuzz`** files (the repaired programs).
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

When reading those files, focus on **`valid_rate`**, **`unique_valid_rate`**, and **`repair_success_rate`**.

Imp Note - The 1B model is **stochastic** and N=50 is small. A single live run can show **`Δ valid_rate < 0`** by chance; what proves the repair stage is working in **any** run is `repair_attempted_count > 0`, `repair_success_count > 0`, and the **`*_r*.fuzz`** files written under `outputs/repair_n50_1b/`.
- **Course-scale evidence** is the **N = 200 / 7B** metrics in **step 10** (`baseline_repro_7b_200` vs `repair_repro_7b_200`).


---

## 10. Recorded full-scale results (no GPU work needed)

Steps 7–9 are only a **small demo** (N = 50, 1B) to prove repair runs; for **stable, reportable** numbers use **N = 200** with **StarCoderBase-7B** (much more VRAM and time — on the order of **~28 GB** and **~1.5 h** per full fuzz on our hardware) or, if available, **15B** (often **~64 GB** or multi-GPU). The repo includes **one pre-recorded** 7B baseline vs repair at N = 200 below. **N = 200** is **one** fuzz job of 200 programs, not 30 repeated runs; default **`--batch_size` 30** only caps how many candidates each **`generate()`** returns, and repair can add extra LLM calls per failure (typically up to **`max_attempts` 2**).

```bash
python -m json.tool outputs/baseline_repro_7b_200/metrics.json
python -m json.tool outputs/repair_repro_7b_200/metrics.json
```

When reading those files, focus on **`valid_rate`**, **`unique_valid_rate`**, and **`repair_success_rate`**.



```
Quick demo note. Steps 7–9 are only a reduced smoke/demo run to verify that the repair pipeline executes end to end. This demo uses N = 50 programs and batch size = 2, and is meant only for a short sanity check.

Main result note. The report’s main quantitative results were obtained with StarCoderBase-7B at N = 200. On our hardware, this required approximately 28 GB of GPU memory, about 64 GB of system RAM, and substantially more runtime. If available, StarCoderBase-15B can also be used, but this often requires around 64 GB of GPU memory or a multi-GPU environment.

Recorded artifact note. The repository includes a pre-recorded 7B baseline-versus-repair run at N = 200. Here, N = 200 refers to one fuzzing run that generates 200 programs total, not 30 repeated runs. The default --batch_size 30 controls only how many candidates each generate() call returns at once; repair may add extra LLM calls for failed programs, typically up to max_attempts = 2.


```