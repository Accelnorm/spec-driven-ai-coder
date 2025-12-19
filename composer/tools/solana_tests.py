from typing import Annotated, Optional, List
from pydantic import Field
import subprocess
from pathlib import Path

from graphcore.graph import WithToolCallId, tool_return

from langchain_core.tools import tool, InjectedToolCallId
from langchain_core.messages import ToolMessage
from langgraph.prebuilt import InjectedState
from langgraph.types import Command
from langgraph.runtime import get_runtime

from composer.core.state import AIComposerState
from composer.core.context import AIComposerContext, compute_state_digest
from composer.core.validation import tests as tests_key


class CargoTestResult:
    """Result of running cargo commands"""
    def __init__(self, success: bool, output: str, command: str):
        self.success = success
        self.output = output
        self.command = command


def run_cargo_command(
    project_dir: Path,
    args: List[str],
    capture_output: bool = True
) -> CargoTestResult:
    """Run a cargo command and return the result."""
    cmd = ["cargo"] + args
    
    result = subprocess.run(
        cmd,
        cwd=project_dir,
        capture_output=capture_output,
        encoding="utf-8"
    )
    
    output = ""
    if result.stdout:
        output += result.stdout
    if result.stderr:
        output += "\n" + result.stderr if output else result.stderr
    
    return CargoTestResult(
        success=(result.returncode == 0),
        output=output,
        command=" ".join(cmd)
    )


def run_quick_tests_impl(
    project_dir: Path,
    features: List[str] | None = None,
    run_tests: bool = True
) -> tuple[bool, str]:
    """
    Run quick tests on a Solana/Rust project.
    
    Steps:
    1. cargo check - verify compilation
    2. cargo test - run unit tests (if run_tests=True)
    3. cargo test --features <features> - run tests with features (if features provided)
    
    Returns (all_passed, report)
    """
    results: List[CargoTestResult] = []
    all_passed = True
    
    # Step 1: cargo check
    check_result = run_cargo_command(project_dir, ["check"])
    results.append(check_result)
    if not check_result.success:
        all_passed = False
    
    # Step 2: cargo test (only if check passed and run_tests enabled)
    if check_result.success and run_tests:
        test_result = run_cargo_command(project_dir, ["test"])
        results.append(test_result)
        if not test_result.success:
            all_passed = False
        
        # Step 3: cargo test with features (only if basic tests passed)
        if test_result.success and features:
            for feature in features:
                feature_test = run_cargo_command(
                    project_dir, 
                    ["test", "--features", feature]
                )
                results.append(feature_test)
                if not feature_test.success:
                    all_passed = False
    
    # Build report
    report_lines = []
    for r in results:
        status = "PASSED" if r.success else "FAILED"
        report_lines.append(f"## {r.command}\n**Status**: {status}\n")
        if not r.success or len(r.output) < 2000:
            # Include full output for failures or short outputs
            report_lines.append(f"```\n{r.output[:4000]}\n```\n")
        else:
            # Truncate long successful outputs
            report_lines.append(f"```\n{r.output[:500]}...(truncated)\n```\n")
    
    report = "\n".join(report_lines)
    return (all_passed, report)


class SolanaQuickTestsArgs(WithToolCallId):
    """
    Run quick compilation and test checks on a Solana/Rust project.
    
    This tool provides fast feedback before running the expensive Certora Prover.
    It runs:
    1. `cargo check` - Verify the code compiles
    2. `cargo test` - Run unit tests
    3. `cargo test --features <feature>` - Run tests with specific features (e.g., 'rt' for CVLR runtime tests)
    
    Use this tool to quickly iterate on compilation errors and test failures before
    invoking the formal verification prover. This is much faster than running the
    full prover and helps catch basic issues early.
    
    IMPORTANT: For Solana/CVLR projects, you should fix all compilation and test
    failures before running certoraSolanaProver. The prover is expensive and will
    fail immediately if the code doesn't compile.
    """
    
    features: Optional[List[str]] = Field(
        default=None,
        description="Optional list of Cargo features to test with. Common features for CVLR projects: 'rt' (CVLR runtime feature for running rules as tests), 'certora' (feature flag for Certora-specific code). If not specified, only basic cargo check and cargo test are run."
    )
    
    run_tests: bool = Field(
        default=True,
        description="Whether to run cargo test after cargo check. Set to False if you only want to verify compilation without running tests."
    )

    state: Annotated[AIComposerState, InjectedState]


@tool(args_schema=SolanaQuickTestsArgs)
def solana_quick_tests(
    state: Annotated[AIComposerState, InjectedState],
    tool_call_id: Annotated[str, InjectedToolCallId],
    features: Optional[List[str]] = None,
    run_tests: bool = True
) -> Command:
    """Run quick cargo check and tests on a Solana/Rust project."""
    runtime = get_runtime(AIComposerContext)
    ctxt = runtime.context
    
    with ctxt.vfs_materializer.materialize(state, debug=ctxt.prover_opts.keep_folder) as temp_dir:
        project_dir = Path(temp_dir)
        
        # Verify Cargo.toml exists
        cargo_toml = project_dir / "Cargo.toml"
        if not cargo_toml.exists():
            return tool_return(
                tool_call_id=tool_call_id,
                content="Error: Cargo.toml not found in project root. Cannot run cargo commands."
            )
        
        (all_passed, report) = run_quick_tests_impl(
            project_dir=project_dir,
            features=features,
            run_tests=run_tests
        )
        
        if all_passed:
            # Record successful tests in validation state
            state_digest = compute_state_digest(c=ctxt, state=state)
            return Command(
                update={
                    "messages": [
                        ToolMessage(
                            tool_call_id=tool_call_id,
                            content=f"All checks passed!\n\n{report}"
                        )
                    ],
                    "validation": {
                        tests_key: state_digest
                    }
                }
            )
        else:
            return tool_return(
                tool_call_id=tool_call_id,
                content=f"Some checks failed. Fix the issues before running the prover.\n\n{report}"
            )
