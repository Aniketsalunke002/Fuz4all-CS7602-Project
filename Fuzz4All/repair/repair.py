"""Error-guided repair stage: use LLM + compiler stderr to repair failed programs."""

import os
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, Optional

from Fuzz4All.target.target import CompileStatus, Target, ValidationResult


@dataclass
class RepairConfig:
    enabled: bool = False
    max_attempts: int = 1
    template_id: str = "T1"
    include_stderr: bool = True
    timeout_sec: int = 3
    cache: bool = False
    error_gate: str = "compile_error"
    max_tokens: int = 512
    temperature: float = 0.7


def should_repair(validation_result: ValidationResult, error_gate: str) -> bool:
    """Return True if this failure type should trigger repair."""
    if validation_result.status == CompileStatus.OK:
        return False
    gate = (error_gate or "compile_error").lower()
    if gate == "all_non_timeout":
        return validation_result.status != CompileStatus.TIMEOUT
    if gate == "compile_error":
        return validation_result.status == CompileStatus.COMPILE_ERROR
    if gate == "ice":
        return validation_result.status == CompileStatus.ICE
    if gate == "crash":
        return validation_result.status == CompileStatus.CRASH
    if gate == "timeout":
        return validation_result.status == CompileStatus.TIMEOUT
    if gate == "syntax" or gate == "type":
        return validation_result.status == CompileStatus.COMPILE_ERROR
    return validation_result.status == CompileStatus.COMPILE_ERROR


def _default_template_dir() -> Path:
    """Default directory for repair templates (prompts/repair relative to repo root)."""
    cwd = Path.cwd()
    if (cwd / "prompts" / "repair").exists():
        return cwd / "prompts" / "repair"
    script_dir = Path(__file__).resolve().parent
    repo = script_dir.parent.parent
    return repo / "prompts" / "repair"


def build_repair_prompt(
    template_id: str,
    program_text: str,
    stderr_text: str,
    template_dir: Optional[os.PathLike] = None,
) -> str:
    """Load template and fill in program and stderr. Returns the prompt string."""
    template_dir = Path(template_dir) if template_dir else _default_template_dir()
    path = template_dir / f"{template_id}.txt"
    if not path.exists():
        fallback = template_dir / "T1.txt"
        path = fallback if fallback.exists() else path
    try:
        template = path.read_text(encoding="utf-8")
    except Exception:
        template = "Fix the following C++ program so it compiles with g++ -std=c++23.\n\nProgram:\n{program}\n\nCompiler stderr:\n{stderr}\n\nOutput ONLY the fixed C++ code, no explanations."
    prompt = template.replace("{program}", program_text).replace(
        "{stderr}", stderr_text[:4000] if stderr_text else "(no stderr)"
    )
    return prompt


def extract_program_from_model_output(text: str) -> str:
    """Strip markdown code fences and extra commentary; return C++ code only."""
    if not text or not text.strip():
        return ""
    s = text.strip()
    if "```" in s:
        parts = re.split(r"```\w*\n?", s)
        for part in parts:
            part = part.strip()
            if part and ("#include" in part or "int main" in part or "class " in part or "template" in part):
                return part
        match = re.search(r"```(?:cpp|c\+\+)?\s*\n(.*?)```", s, re.DOTALL)
        if match:
            return match.group(1).strip()
        first = re.search(r"```(?:cpp|c\+\+)?\s*\n(.*)", s, re.DOTALL)
        if first:
            return first.group(1).strip()
    return s


def normalize_error_signature(signature: str) -> str:
    """Normalize signature for cache key (light normalization)."""
    if not signature:
        return ""
    return signature.strip()[:500]


def repair_llm(
    target: Target,
    program_text: str,
    stderr_text: str,
    config: RepairConfig,
    template_dir: Optional[os.PathLike] = None,
) -> str:
    """Call LLM once to produce repaired program; return extracted C++ code."""
    prompt = build_repair_prompt(
        config.template_id,
        program_text,
        stderr_text if config.include_stderr else "",
        template_dir=template_dir,
    )
    raw = target.generate_single(
        prompt,
        max_length=config.max_tokens,
        temperature=config.temperature,
    )
    return extract_program_from_model_output(raw)


def repair_config_from_dict(d: Optional[Dict[str, Any]]) -> RepairConfig:
    """Build RepairConfig from YAML config section."""
    if not d:
        return RepairConfig(enabled=False)
    return RepairConfig(
        enabled=bool(d.get("enabled", False)),
        max_attempts=int(d.get("max_attempts", 1)),
        template_id=str(d.get("template_id", "T1")),
        include_stderr=bool(d.get("include_stderr", True)),
        timeout_sec=int(d.get("timeout_sec", 3)),
        cache=bool(d.get("cache", False)),
        error_gate=str(d.get("error_gate", "compile_error")),
        max_tokens=int(d.get("max_tokens", 512)),
        temperature=float(d.get("temperature", 0.7)),
    )
