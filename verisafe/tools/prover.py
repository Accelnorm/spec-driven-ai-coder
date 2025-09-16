from typing import Annotated, List, Optional
from graphcore.graph import WithToolCallId
from pydantic import Field

from graphcore.graph import WithToolCallId
from langchain_core.tools import tool, InjectedToolCallId
from langchain_core.messages import ToolMessage
from langgraph.prebuilt import InjectedState
from verisafe.core.state import CryptoStateGen
from verisafe.prover.runner import certora_prover as prover_impl

class CertoraProverArgs(WithToolCallId):
    """
    Invoke the Certora Prover, a powerful symbolic reasoning tool for verifying the correctness of smart contracts.

    The Certora Prover operates on one or more smart contracts files, and a specification for their behavior, written in a domain
    specific language called CVL, for which you have the documentation. A specification for the code you are generating
    has been provided for you, and is composed of multiple `rules`. Each rule defines the acceptable behavior
    of the smart contract in terms of assertions; a violated assertion means the smart contract's behavior is
    unacceptable.

    The Certora Prover will automatically check whether a smart contract instance (the "contract under verifiction")
     satisfies the provided specification on a per rule basis. For each rule, the prover will give one of the following result:
    1. VERIFIED: the smart contract satisfies the rule for all possible inputs
    2. VIOLATED: The smart contract violates the specification. As part of this result, the prover will provide
    a concrete counter example for the input/states which lead to the violation
    3. TIMEOUT: The automated reasoning used by the prover timed out before giving a response either way
    4. ERROR/other: There was some internal error within the prover
    """

    source_files: List[str] = Field(description="""
      The (relative) filenames to verify. These files MUST have been put into the virtual filesystem with
      prior invocations of the PutFile tool.

      IMPORTANT: Only the files containing the contracts to be verified need to be passed as this
      argument. Thus, if verifying `MyContract`, only `src/MyContract.sol` needs to be provided here.
      HOWEVER: any files necessary to the compilation of `MyContract` must also have been placed on the
      virtual filesystem before calling the prover.
    """)

    target_contract: str = Field(description="""
       The name of the contract to check the specification against. This contract should be
       the main "entry point" for the functionality being synthesized. NB: the name of this
       contract should match one of the names provided in `source_files` according to that input's rules.
    """)

    compiler_version: str = \
        Field(description="The compiler to use when compiling the Solidity source code."
              "This parameter is specified as 'solcX.Y' where X.Y indicate solidity version 0.X.Y, or simply `solc`, which uses the system "
              "default. For example, solc8.29 uses the Solidity compiler for version 0.8.29, solc7.0 uses 0.7.0, etc." \
              "When possible, use specific compiler versions, falling back on the system default `solc` only as a last resort." \
              "Attempt to use the most recent compiler version if you can, which is solc8.29.")

    loop_iter: int = \
        Field(description="The Certora Prover uses bounded verification for looping code; "
              "any statically unbounded loops are unrolled a fixed number time, and then the loop condition is *assumed*. "
              "You should set this number as low as possible so that non-trivial looping behavior is observed. "
              "While values above 3 are technically supported, performance becomes exponentially worse, and thus"
              "should be avoided whenever possible.")

    rule: Optional[str] = \
        Field(description="The specific rule to check from the `spec_file`. If unspecified,"
              "all rules are run. Before delivering the finished code to the user, ensure that all rules pass on the most"
              "up to date version of the code. However, when iteratively developing code, it may be useful to focus on a"
              "single, 'problematic' rule.")

    state: Annotated[CryptoStateGen, InjectedState]


@tool(args_schema=CertoraProverArgs)
def certora_prover(
    source_files: List[str],
    # spec_file: str,
    target_contract: str,
    compiler_version: str,
    loop_iter: int,
    rule: Optional[str],
    state: Annotated[CryptoStateGen, InjectedState],
    tool_call_id: Annotated[str, InjectedToolCallId]
) -> str:
    return prover_impl(
        source_files,
        target_contract,
        compiler_version,
        loop_iter,
        rule, state,
        tool_call_id
    )