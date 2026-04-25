# Task 1 — Static Analysis Evidence Summary

**Codebase:** `fuzz4all-cs` — Fuzz4All + course-extension (error-guided repair).
**Scope analysed:** `Fuzz4All/` and `tools/` (≈ 2,440 LOC, Python 3.10).

## 0. Tools matrix

| # | Tool | Version | Technique class | Why it was chosen |
|---|------|---------|-----------------|-------------------|
| 1 | **Manual review + threat model (STRIDE)** | — | Human, white-box | Establish trust boundaries (config/CLI → target → subprocess) and design PoCs the way an attacker would. |
| 2 | **Bandit** | 1.9.4 | AST-based pattern static analysis | Python-native, fast, broad CWE coverage (B602/B108/B506/B615…). |
| 3 | **Semgrep (registry rules)** | 1.161.0 | Pattern + intra/inter-procedural taint static analysis | Independent confirmation of Bandit + a true source→sink **taint flow** result. |
| 4 | **Semgrep (custom rule)** | 1.161.0 | Project-specific taint rule | Encodes the *application-level* trust boundary (`target_name`/`compiler` → `subprocess`) that generic rules miss. |
| 5 | **CodeQL** | 2.25.2 + `codeql/python-queries@1.8.0` | Inter-procedural semantic dataflow (declarative QL) | Most rigorous OSS dataflow engine; complements pattern tools and produces a *useful null result* on stock command-injection. |
| 6 | **flake8 + dlint** | flake8 7.3.0 / dlint 0.16.0 | Security linting (DUO* checks) | Lightweight third opinion confirming `shell=True`, weak RNG, ReDoS, unsafe yaml. |
| 7 | **pip-audit** | 2.10.0 (PyPI Advisory DB / OSV) | Software-Composition-Analysis (SCA) | Vulnerable third-party dependency detection (CVEs in installed packages). |
| 8 | **detect-secrets** | 1.5.0 | Secret scanning | Verify there are no committed credentials / API keys (null-result evidence). |

Raw artefacts in `outputs/security/`:

```
bandit_report.txt / .json
semgrep_report.txt / .json                 # registry rules
semgrep_custom.txt / .json                 # custom rule
codeql.sarif                               # python-security-and-quality.qls
codeql_security_extended.sarif             # python-security-extended.qls
codeql_injections.sarif                    # CWE-078/022/094 only
codeql_summary.txt                         # human-readable summary
flake8_dlint.txt
pip_audit.txt / .json
detect_secrets.json
```

---

## 1. Headline numbers

| Tool                    | Total findings | High / Error | Medium | Low | Notes |
|-------------------------|---------------:|-------------:|-------:|----:|-------|
| Bandit                  | 77             | 23           | 22     | 32  | 23× B602 HIGH = main F1 evidence |
| Semgrep (registry)      | 24             | 24           | 0      | 0   | All ERROR / blocking |
| Semgrep (custom rule)   | **6**          | 6            | 0      | 0   | Project-specific taint, F1 |
| CodeQL `security-and-quality` | 59       | —            | —      | —   | Quality + security, 7 rules |
| CodeQL `security-extended`    | 0        | 0            | 0      | 0   | Useful **null result**, see §5 |
| CodeQL `CWE-078/022/094`      | 0        | 0            | 0      | 0   | Useful **null result**, see §5 |
| flake8 + dlint          | 27             | —            | —      | —   | DUO116/DUO109/DUO138/DUO102 |
| pip-audit               | **7 CVEs / 6 packages** | — | — | — | qiskit-terra CVE-2025-2000, requests CVE-2026-25645, pillow CVE-2026-40192, … |
| detect-secrets          | 0              | 0            | 0      | 0   | No committed secrets (null result) |

## 2. Bandit — by check

| Test ID | Severity | Rule | Count | Maps to manual finding |
|---------|----------|------|-------|------------------------|
| **B602** | **HIGH** | `subprocess_popen_with_shell_equals_true` | **23** | **F1 — CWE-78** |
| **B108** | **MED**  | `hardcoded_tmp_directory` | **19** | **F2 — CWE-377** |
| B110    | LOW  | `try_except_pass`                                | 16 | hardening (CWE-703) |
| B404    | LOW  | `import_subprocess` (informational)              | 8  | meta — context for B602/B603 |
| B615    | MED  | `huggingface_unsafe_download`                    | 2  | supplementary (CWE-494) |
| B603    | LOW  | `subprocess_without_shell_equals_true`           | 2  | meta — confirms safe sites |
| B602    | LOW  | `subprocess_popen_with_shell_equals_true` (low-conf) | 1 | F1 |
| B506    | MED  | `yaml_load`                                      | 1  | null result (CWE-502, FullLoader) |
| B105    | LOW  | `hardcoded_password_string`                      | 2  | false positive (prompt strings) |
| B607    | LOW  | `start_process_with_partial_path`                | 1  | hardening |
| B311    | LOW  | `random` (non-cryptographic)                     | 1  | informational |
| B101    | LOW  | `assert_used`                                    | 1  | informational |

## 3. Semgrep — registry packs

All 24 findings are severity **ERROR (blocking)**.

| Rule | Count | CWE | Comment |
|------|------:|-----|---------|
| `subprocess-shell-true` | 23 | CWE-78 | Same sites as Bandit B602 — independent confirmation of F1. |
| `dangerous-subprocess-use-tainted-env-args` | 1 | CWE-78 | **Taint flow** at `tools/run_search_round.py:92`: candidate JSON → `subprocess.run`. End-to-end source→sink. |

## 4. Semgrep — *custom* rule (`tools/semgrep_rules/cmd_inject_target.yml`)

Designed for the fuzz4all-cs trust boundary: source = `self.target_name` / local alias `compiler`; sink = `subprocess.run/Popen/call(..., shell=True, …)` or `os.system(...)`.

| File | Line | Sink | CWE |
|------|-----:|------|-----|
| `Fuzz4All/target/C/C.py`    | 25  | `subprocess.run(f"{compiler} … ", shell=True)` | CWE-78 |
| `Fuzz4All/target/CPP/CPP.py`  | 100 | `subprocess.run(f"{compiler} -x c++ -std=c++23 … ", shell=True)` | CWE-78 |
| `Fuzz4All/target/GO/GO.py`    | 67  | `subprocess.run(f"{self.target_name} build …", shell=True)` | CWE-78 |
| `Fuzz4All/target/JAVA/JAVA.py`| 86  | `subprocess.run(f"{self.target_name} --source 22 …", shell=True)` | CWE-78 |
| `Fuzz4All/target/SMT/SMT.py`  | 117 | `subprocess.run(f"{self.target_name} -m -i -q --check-models …", shell=True)` | CWE-78 |
| `Fuzz4All/target/SMT/SMT.py`  | 126 | second SMT shell-true site | CWE-78 |

Reading: this rule shows the bug is **systemic** — it appears in every per-language target, not only in the C++ validator we discussed in F1. That elevates severity of F1.

## 5. CodeQL — security-and-quality + null-result analysis

CodeQL ran the full `python-security-and-quality.qls` suite over the project database (13 Python source files, 2 169 source lines).

**Quality / hygiene findings (59 total):**

| Rule | Count | Reason it matters for security |
|------|------:|-----|
| `py/unused-import`         | 25 | Code hygiene; harmless. |
| `py/empty-except`          | 15 | **Helps F2:** silently swallows the `OSError` that a symlink-following write would otherwise raise. |
| `py/file-not-closed`       |  7 | **Helps F2:** temp-file lifecycle issues compound the symlink-clobber risk. |
| `py/catch-base-exception`  |  6 | Same hygiene class. |
| `py/str-format/surplus-argument` | 3 | Misformatted error logging in `Fuzz4All/target/target.py:441–452` could mask validator failures. |
| `py/uninitialized-local-variable` | 2 | `code` may be used before assignment in C/GO validators. |
| `py/unused-local-variable` | 1 | minor. |

**Null result on injection queries (intentional, valuable):**

CodeQL's stock `Security/CWE-078/CommandInjection.ql`, `CWE-022/PathInjection.ql` and `CWE-094/CodeInjection.ql` all return **0 findings**. The reason is that CodeQL's default Python taint model classifies HTTP requests, environment variables and `argparse` CLI args as *remote sources* but does **not** model the YAML config file (loaded by `Fuzz4All/util/util.py:65` via `yaml.load(f, Loader=yaml.FullLoader)`) as a tainted source. Because the attacker-controlled value `target_name` reaches the subprocess sink only through that YAML config, CodeQL's stock model misses it.

This null result is itself an important methodological finding:

1. it shows that off-the-shelf taint engines under-report in projects that load configuration from disk and treat the disk as untrusted;
2. it justifies the **custom Semgrep rule** in §4, which encodes the project-specific source (`self.target_name` / `compiler`) and recovers 6 high-confidence findings;
3. it justifies the **manual review** in the report — without a human-modelled trust boundary the systemic bug stays hidden.

## 6. flake8 + dlint

27 DUO* findings (truncated to categories):

| Check  | Meaning                                | Count | Maps to |
|--------|----------------------------------------|------:|---------|
| DUO116 | `subprocess` `shell=True` is insecure  | 24    | F1 |
| DUO109 | `yaml.load` insecure (FullLoader still flagged) | 1 | discussed as null result |
| DUO138 | Catastrophic regex (potential ReDoS)   | 1     | hardening (`Fuzz4All/util/util.py:16`) |
| DUO102 | `random` not cryptographically strong  | 1     | informational |

## 7. pip-audit (SCA)

Run inside the `fuzz4all` conda env. Found **7 CVEs across 6 installed packages**:

| Package        | Installed | CVE              | Fixed in |
|----------------|-----------|------------------|----------|
| cryptography   | 46.0.5    | CVE-2026-34073   | 46.0.6 |
| cryptography   | 46.0.5    | CVE-2026-39892   | 46.0.7 |
| pillow         | 12.1.1    | CVE-2026-40192   | 12.2.0 |
| pip            | 26.0.1    | CVE-2026-3219    | (no fix) |
| pygments       | 2.19.2    | CVE-2026-4539    | 2.20.0 |
| qiskit-terra   | 0.24.1    | CVE-2025-2000    | (no fix) |
| requests       | 2.32.5    | CVE-2026-25645   | 2.33.0 |

This is a separate, externally-validated category of evidence (vulnerable third-party code) that complements the project-internal findings.

## 8. detect-secrets

Run on every tracked file (excluding `.git/`, `outputs/`, generated `*.fuzz`). Result: **0 hits**. Useful null result — no plaintext credentials are committed.

---

## 9. Cross-evidence mapping (rubric column "Clarity / Evidence")

| Manual finding | Bandit | Semgrep registry | Semgrep custom | CodeQL | flake8/dlint |
|----------------|:------:|:----------------:|:--------------:|:------:|:------------:|
| **F1** CWE-78 cmd injection via `target_name`/`--target` | 23× B602 HIGH | 23× `subprocess-shell-true` + 1× taint | 6 (C/CPP/GO/JAVA/SMT) | quality only (null on stock CommandInjection ⇒ §5) | 24× DUO116 |
| **F2** CWE-377/CWE-59 insecure `/tmp` temp file | 19× B108 + 16× B110 | n/a | n/a | 15× `py/empty-except` + 7× `py/file-not-closed` (compounding) | n/a |
| **F3** CWE-94 oracle executes generated code | every Qiskit shell-true site | every Qiskit shell-true site | (rule not aimed at Qiskit) | quality only | DUO116 on Qiskit sites |
| Null — CWE-502 PyYAML | 1× B506 | n/a | n/a | n/a | 1× DUO109 |
| Null — secrets | n/a | n/a | n/a | n/a | n/a (detect-secrets: 0) |
| Supplementary — vulnerable deps | n/a | n/a | n/a | n/a | n/a (pip-audit: 7 CVEs) |

---

## 10. Reproducing this evidence

```bash
# Activate project env (HPC, no Docker)
source ~/miniconda3/etc/profile.d/conda.sh && conda activate fuzz4all
pip install --user bandit semgrep pip-audit detect-secrets flake8 dlint
export PATH="$HOME/.local/bin:$PATH"

# Bandit
bandit -r Fuzz4All/ tools/ -f txt  -o outputs/security/bandit_report.txt
bandit -r Fuzz4All/ tools/ -f json -o outputs/security/bandit_report.json

# Semgrep — registry packs
semgrep --config p/python --config p/command-injection --config p/security-audit \
        Fuzz4All/ tools/ --metrics off --quiet \
        > outputs/security/semgrep_report.txt
semgrep --config p/python --config p/command-injection --config p/security-audit \
        Fuzz4All/ tools/ --json --metrics off \
        --output outputs/security/semgrep_report.json

# Semgrep — custom rule
semgrep --config tools/semgrep_rules/cmd_inject_target.yml \
        --output outputs/security/semgrep_custom.txt   Fuzz4All/ tools/
semgrep --config tools/semgrep_rules/cmd_inject_target.yml --json \
        --output outputs/security/semgrep_custom.json  Fuzz4All/ tools/

# flake8 + dlint
flake8 --select=DUO Fuzz4All tools | tee outputs/security/flake8_dlint.txt

# pip-audit (inside the conda env so it sees the project deps)
python -m pip_audit --format json \
        --output outputs/security/pip_audit.json --progress-spinner off
python -m pip_audit \
        --output outputs/security/pip_audit.txt  --progress-spinner off

# detect-secrets
detect-secrets scan --exclude-files '\.git/|outputs/|\.fuzz$|\.cpp$|node_modules/|__pycache__/' \
        > outputs/security/detect_secrets.json

# CodeQL (one-time setup)
curl -sSL -o ~/codeql.zip \
  https://github.com/github/codeql-cli-binaries/releases/latest/download/codeql-linux64.zip
unzip -q ~/codeql.zip -d ~/codeql-tooling/
export PATH="$HOME/codeql-tooling/codeql:$PATH"
codeql pack download codeql/python-queries

# CodeQL — build DB and analyze
codeql database create .codeql_db --language=python --source-root=. --overwrite
codeql database analyze .codeql_db \
       codeql/python-queries:codeql-suites/python-security-and-quality.qls \
       --format=sarifv2.1.0 --output=outputs/security/codeql.sarif --threads=4 --ram=8000
codeql database analyze .codeql_db \
       codeql/python-queries:codeql-suites/python-security-extended.qls \
       --format=sarifv2.1.0 --output=outputs/security/codeql_security_extended.sarif --threads=4
codeql database analyze .codeql_db \
       codeql/python-queries:Security/CWE-078/CommandInjection.ql \
       codeql/python-queries:Security/CWE-022/PathInjection.ql \
       codeql/python-queries:Security/CWE-094/CodeInjection.ql \
       --format=sarifv2.1.0 --output=outputs/security/codeql_injections.sarif --threads=4
```
