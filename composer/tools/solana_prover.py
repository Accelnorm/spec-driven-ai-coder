from typing import Annotated
from pydantic import Field

from graphcore.graph import WithToolCallId, tool_return

from langchain_core.tools import tool, InjectedToolCallId
from langchain_core.messages import ToolMessage
from langgraph.prebuilt import InjectedState
from langgraph.types import Command
from langgraph.runtime import get_runtime

from composer.core.state import AIComposerState
from composer.core.context import AIComposerContext, compute_state_digest
from composer.core.validation import prover as prover_key, tests as tests_key
from composer.prover.solana_runner import solana_prover as prover_impl, SolanaRawReport


def check_tdd_gate(state: AIComposerState, ctxt: AIComposerContext) -> str | None:
    """
    Check if TDD enforcement is enabled and tests have passed.
    
    Returns an error message if the prover should be blocked, None otherwise.
    """
    # Check if tests validation is required
    if tests_key not in ctxt.required_validations:
        return None
    
    # Check if tests have passed for the current state
    validation = state.get("validation", {})
    if tests_key not in validation:
        return (
            "TDD enforcement is enabled. You must run `solana_quick_tests` and have all tests pass "
            "before invoking the Certora Solana Prover. The prover is expensive and will fail "
            "immediately if the code doesn't compile.\n\n"
            "Please run `solana_quick_tests` first to verify:\n"
            "1. The code compiles (`cargo check`)\n"
            "2. Unit tests pass (`cargo test`)\n\n"
            "Once tests pass, you can run the prover."
        )
    
    # Tests have passed at some point - check if state has changed since
    current_digest = compute_state_digest(c=ctxt, state=state)
    tests_digest = validation[tests_key]
    
    if current_digest != tests_digest:
        return (
            "The code has changed since tests last passed. Please run `solana_quick_tests` again "
            "to verify the code still compiles and tests pass before invoking the prover."
        )
    
    return None


class SolanaProverArgs(WithToolCallId):
    """
    Invoke the Certora Solana Prover, a powerful symbolic reasoning tool for verifying the correctness of Solana programs.

    The Certora Solana Prover operates on Solana programs written in Rust, and a specification for their behavior
    written using CVLR (Certora Verification Language for Rust). A specification for the code you are generating
    has been provided for you, and is composed of multiple `rules`. Each rule, marked with the `#[rule]` attribute,
    defines the acceptable behavior of the Solana program in terms of assertions.

    The Certora Solana Prover will automatically check whether a Solana program satisfies the provided specification
    on a per rule basis.
     
    For each rule, the prover will give one of the following results:
    1. VERIFIED: the program satisfies the rule for all possible inputs
    2. VIOLATED: The program violates the specification. As part of this result, the prover will provide
       a concrete counter example for the input/states which lead to the violation
    3. TIMEOUT: The automated reasoning used by the prover timed out before giving a response either way
    4. SANITY_FAIL: The rule succeeded, but was vacuously true, perhaps due to contradicting assumptions
    5. ERROR/other: There was some internal error within the prover

    IMPORTANT: The Solana prover requires rules to be specified via the --rule flag. You must specify
    which rule to verify.
    
    IMPORTANT: When TDD enforcement is enabled (default for Solana), you MUST run `solana_quick_tests`
    and have all tests pass before invoking this prover. The prover is expensive - fix compilation
    and test failures first!
    """

    rule: str = Field(description="""
      The specific rule to check. This is REQUIRED for the Solana prover.
      The rule name should match a function marked with #[rule] in the specification.
      For example: "rule_vault_solvency_deposit" or "rule_correct_add_performs_addition".
    """)

    state: Annotated[AIComposerState, InjectedState]


@tool(args_schema=SolanaProverArgs)
def solana_prover(
    rule: str,
    state: Annotated[AIComposerState, InjectedState],
    tool_call_id: Annotated[str, InjectedToolCallId]
) -> Command:
    ctxt = get_runtime(AIComposerContext).context
    
    # TDD enforcement: check if tests must pass first
    tdd_error = check_tdd_gate(state, ctxt)
    if tdd_error:
        return tool_return(tool_call_id=tool_call_id, content=tdd_error)
    
    result = prover_impl(
        rule=rule,
        state=state,
        tool_call_id=tool_call_id
    )
    match result:
        case str():
            return tool_return(tool_call_id=tool_call_id, content=result)
        case SolanaRawReport():
            if result.all_verified:
                state_digest = compute_state_digest(c=ctxt, state=state)
                return Command(
                    update={
                        "messages": [
                            ToolMessage(
                                tool_call_id=tool_call_id,
                                content=result.report
                            )
                        ],
                        "validation": {
                            prover_key: state_digest
                        }
                    }
                )
            return tool_return(tool_call_id=tool_call_id, content=result.report)
