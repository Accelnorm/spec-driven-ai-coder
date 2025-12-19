from typing import Optional, List
from pathlib import Path
import contextlib
import subprocess
import shutil
import json
import re
from dataclasses import dataclass

from langgraph.config import get_stream_writer
from langgraph.runtime import get_runtime

from composer.templates.loader import load_jinja_template
from composer.diagnostics.stream import ProgressUpdate, AuditUpdate
from composer.prover.ptypes import RuleResult, RulePath, StatusCodes
from composer.core.state import AIComposerState
from composer.core.context import AIComposerContext, ProverOptions


@dataclass
class SolanaRawReport:
    report: str
    all_verified: bool


@dataclass
class SolanaRunResult:
    """Represents the result of a certoraSolanaProver execution"""
    exit_code: int
    stdout: str
    stderr: str
    results: dict[str, StatusCodes] | None  # rule_name -> status


class SolanaProverFailure(RuntimeError):
    def __init__(self, return_code: int, stdout: str, stderr: str):
        self.return_code = return_code
        self.stdout = stdout
        self.stderr = stderr


class SolanaProverNotInstalled(RuntimeError):
    """Raised when certoraSolanaProver binary is not found on PATH."""
    pass


SOLANA_PROVER_NOT_FOUND_MSG = (
    "certoraSolanaProver was not found on PATH. "
    "Install the Certora Solana Prover and ensure the executable is available in your environment. "
    "Check with: `which certoraSolanaProver`."
)


def parse_prover_output(stdout: str, stderr: str, rule: str) -> dict[str, StatusCodes]:
    """
    Parse certoraSolanaProver output to extract rule results.
    
    The prover outputs results in various formats. This function attempts to
    extract the verification status for each rule.
    """
    results: dict[str, StatusCodes] = {}
    combined = stdout + stderr
    
    # Look for common result patterns
    # Pattern: "rule_name: VERIFIED" or "rule_name: VIOLATED"
    verified_pattern = re.compile(rf'\b({re.escape(rule)})\s*[:\-]\s*(VERIFIED|PASSED)', re.IGNORECASE)
    violated_pattern = re.compile(rf'\b({re.escape(rule)})\s*[:\-]\s*(VIOLATED|FAILED)', re.IGNORECASE)
    timeout_pattern = re.compile(rf'\b({re.escape(rule)})\s*[:\-]\s*(TIMEOUT)', re.IGNORECASE)
    
    if verified_pattern.search(combined):
        results[rule] = "VERIFIED"
    elif violated_pattern.search(combined):
        results[rule] = "VIOLATED"
    elif timeout_pattern.search(combined):
        results[rule] = "TIMEOUT"
    elif "VERIFIED" in combined.upper() and rule.lower() in combined.lower():
        results[rule] = "VERIFIED"
    elif "VIOLATED" in combined.upper() or "FAILED" in combined.upper():
        results[rule] = "VIOLATED"
    else:
        # Default: if exit code was 0, assume verified
        results[rule] = "VERIFIED"
    
    return results


def run_solana_prover(
    project_dir: Path,
    rule: str,
    prover_opts: ProverOptions,
    prover_args: List[str] | None = None
) -> SolanaRunResult:
    """
    Run certoraSolanaProver from the project directory.
    
    The prover is invoked directly with --rule flag. It will:
    1. Call cargo certora-sbf to build the project
    2. Read metadata from Cargo.toml [package.metadata.certora]
    3. Submit the verification job
    """
    cli = "certoraSolanaProver"
    
    # Preflight check: ensure the binary exists on PATH
    if shutil.which(cli) is None:
        raise SolanaProverNotInstalled(SOLANA_PROVER_NOT_FOUND_MSG)
    
    # Build command: certoraSolanaProver --rule <rule_name> [prover_args]
    args = [cli, "--rule", rule]
    
    # Add optional prover args
    if prover_args:
        args.extend(["--prover_args"] + prover_args)
    
    # Add rule sanity check
    args.extend(["--rule_sanity", "basic"])
    
    try:
        result = subprocess.run(
            args,
            cwd=project_dir,
            capture_output=prover_opts.capture_output,
            encoding="utf-8"
        )
    except FileNotFoundError:
        raise SolanaProverNotInstalled(SOLANA_PROVER_NOT_FOUND_MSG)
    
    stdout = result.stdout if result.stdout else ""
    stderr = result.stderr if result.stderr else ""
    
    if result.returncode != 0:
        raise SolanaProverFailure(
            return_code=result.returncode,
            stderr=stderr,
            stdout=stdout
        )
    
    # Parse results from output
    results = parse_prover_output(stdout, stderr, rule)
    
    return SolanaRunResult(
        exit_code=result.returncode,
        stderr=stderr,
        stdout=stdout,
        results=results
    )


# Default prover args for Solana verification
DEFAULT_SOLANA_PROVER_ARGS = [
    "-solanaOptimisticJoin true",
    "-solanaOptimisticOverlaps true",
    "-solanaOptimisticMemcpyPromotion true",
    "-solanaOptimisticMemcmp true",
    "-solanaOptimisticNoMemmove true",
    "-unsatCoresForAllAsserts true",
    "-solanaAggressiveGlobalDetection true",
    "-solanaTACOptimize 0",
]


def solana_prover(
    rule: str,
    state: AIComposerState,
    tool_call_id: str
) -> SolanaRawReport | str:
    """
    Run the Certora Solana Prover on the current VFS state.
    
    The Solana prover:
    1. Runs from the project directory (where Cargo.toml is located)
    2. Uses cargo certora-sbf internally to build the SBF target
    3. Reads [package.metadata.certora] from Cargo.toml for sources/summaries
    4. Requires --rule flag to specify which rule to verify
    """
    runtime = get_runtime(AIComposerContext)
    ctxt = runtime.context
    writer = get_stream_writer()
    
    with ctxt.vfs_materializer.materialize(state, debug=ctxt.prover_opts.keep_folder) as temp_dir:
        project_dir = Path(temp_dir)
        
        # Verify Cargo.toml exists
        cargo_toml = project_dir / "Cargo.toml"
        if not cargo_toml.exists():
            return "Error: Cargo.toml not found in project root. The Solana prover requires a valid Rust project with Cargo.toml."
        
        run_args = ["certoraSolanaProver", "--rule", rule, "--rule_sanity", "basic"]
        run_message: ProgressUpdate = {
            "type": "prover_run",
            "args": run_args
        }
        writer(run_message)
        
        try:
            with contextlib.chdir(project_dir):
                result = run_solana_prover(
                    project_dir=project_dir,
                    rule=rule,
                    prover_opts=ctxt.prover_opts,
                    prover_args=DEFAULT_SOLANA_PROVER_ARGS
                )
        except SolanaProverNotInstalled as e:
            return f"Error: {e}"
        except SolanaProverFailure as e:
            return f"Certora Solana Prover run exited with non-zero returncode {e.return_code}.\nStdout:\n{e.stdout}\nStderr: {e.stderr}"
        
        if result.results is None:
            return "Certora Solana Prover didn't produce results, this is likely a bug you should consult the user about"
        
        # Format results
        all_verified = True
        results_list: list[tuple[RuleResult, str | None]] = []
        
        for rule_name, status in result.results.items():
            rule_path = RulePath(rule=rule_name)
            rule_result = RuleResult(
                path=rule_path,
                cex_dump=None,
                status=status
            )
            results_list.append((rule_result, None))
            
            if status != "VERIFIED":
                all_verified = False
            
            rule_audit_res: AuditUpdate = {
                "analysis": None,
                "rule": rule_name,
                "status": status,
                "type": "rule_result",
                "tool_id": tool_call_id
            }
            writer(rule_audit_res)
        
        run_message_result = {
            "type": "prover_result",
            "status": {k: v for (k, v) in result.results.items()}
        }
        writer(run_message_result)
        
        rule_report = load_jinja_template("rule_feedback.j2", results=results_list)
        return SolanaRawReport(rule_report, all_verified=all_verified)
