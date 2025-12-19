import psycopg
from psycopg.rows import dict_row

from typing import Any

from langgraph.checkpoint.postgres import PostgresSaver
from langchain_core.language_models.chat_models import BaseChatModel
from langchain_core.tools import BaseTool
from langchain_anthropic import ChatAnthropic
from langgraph.graph import StateGraph
from langgraph.store.postgres import PostgresStore

from graphcore.graph import build_workflow, BoundLLM
from graphcore.tools.vfs import vfs_tools, VFSAccessor, VFSToolConfig, VFSState
from graphcore.tools.memory import PostgresMemoryBackend

from composer.workflow.types import Input, PromptParams, TargetPlatform
from composer.core.context import AIComposerContext
from composer.core.state import AIComposerState
from composer.input.types import ModelOptions

from composer.templates.loader import load_jinja_template
from composer.workflow.summarization import SummaryGeneration


def get_checkpointer() -> PostgresSaver:
    conn_string = "postgresql://langgraph_checkpoint_user:langgraph_checkpoint_password@localhost:5432/langgraph_checkpoint_db"
    conn = psycopg.connect(conn_string, autocommit=True, row_factory=dict_row)
    checkpointer = PostgresSaver(conn)
    checkpointer.setup()
    return checkpointer

def get_store() -> PostgresStore:
    conn_string = "postgresql://langgraph_store_user:langgraph_store_password@localhost:5432/langgraph_store_db"
    conn = psycopg.connect(conn_string, autocommit=True, row_factory=dict_row)
    store = PostgresStore(conn)
    store.setup()
    return store

def get_memory_ns(thread_id: str, ns: str) -> str:
    return f"ai-composer-{thread_id}-{ns}"

def get_memory(ns: str, init_from: str | None = None) -> PostgresMemoryBackend:
    conn_string = "postgresql://memory_tool_user:memory_tool_password@localhost:5432/memory_tool_db"
    conn = psycopg.connect(conn_string)
    return PostgresMemoryBackend(ns, conn, init_from)

def get_system_prompt(target: TargetPlatform = "evm") -> str:
    """Load and render the system prompt from Jinja template"""
    template_name = "system_prompt_solana.j2" if target == "svm" else "system_prompt.j2"
    return load_jinja_template(template_name)

def get_initial_prompt(target: TargetPlatform, prompt: PromptParams) -> str:
    """Load and render the initial prompt from Jinja template"""
    template_name = "synthesis_prompt_solana.j2" if target == "svm" else "synthesis_prompt.j2"
    return load_jinja_template(template_name, **prompt)


def create_llm(args: ModelOptions) -> BaseChatModel:
    """Create and configure the LLM."""
    return ChatAnthropic(
        model_name=args.model,
        max_tokens_to_sample=args.tokens,
        temperature=1,
        timeout=None,
        max_retries=2,
        stop=None,
        thinking={"type": "enabled", "budget_tokens": args.thinking_tokens},
        betas=([
            "files-api-2025-04-14",
            "context-management-2025-06-27"
        ] if args.memory_tool else [
            "files-api-2025-04-14"
        ])
    )

def get_vfs_tools(
    fs_layer: str | None,
    immutable: bool,
    target: TargetPlatform = "evm"
) -> tuple[list[BaseTool], VFSAccessor[VFSState]]:
    if immutable:
        return vfs_tools(VFSToolConfig(
            fs_layer=fs_layer,
            immutable=True
        ), VFSState)
    else:
        if target == "svm":
            # Solana mode: forbid edits to spec files only (agent needs to create Cargo.toml for tests)
            return vfs_tools(VFSToolConfig(
                fs_layer=fs_layer,
                immutable=False,
                forbidden_write=None,  # No forbidden writes - agent needs full control for Rust project setup
                put_doc_extra= \
    """
    By convention, Rust source files should follow standard Rust module conventions.
    The main library entry point should be in src/lib.rs.

    You MUST create a valid Cargo.toml for the project to compile and run tests.
    The Cargo.toml should include necessary dependencies like `cvlr` for CVLR macros.

    IMPORTANT: You may not use this tool to update the specification files.
    If changes to spec files are necessary, use the propose_spec_change tool or consult the user.
    """
            ), AIComposerState)
        else:
            return vfs_tools(VFSToolConfig(
                fs_layer=fs_layer,
                immutable=False,
                forbidden_write="^rules.spec$",
                put_doc_extra= \
    """
    By convention, every Solidity file placed into the virtual filesystem should contain exactly one contract/interface/library definitions.
    Further, the name of the contract/interface/library defined in that file should name the name of the solidity source file sans extension.
    For example, src/MyContract.sol should contain an interface/library/contract called `MyContract`"

    IMPORTANT: You may not use this tool to update the specification, nor should you attempt to
    add new specification files.
    """
            ), AIComposerState)

def get_cryptostate_builder(
    llm: BaseChatModel,
    prompt_params: PromptParams,
    fs_layer: str | None,
    summarization_threshold : int | None,
    extra_tools: list[BaseTool] = [],
    target: TargetPlatform = "evm"
) -> tuple[StateGraph[AIComposerState, AIComposerContext, Input, Any], BoundLLM, VFSAccessor[VFSState]]:
    (vfs_tooling, mat) = get_vfs_tools(fs_layer=fs_layer, immutable=False, target=target)
    # import here to avoid loading these for non-composer factory uses

    from composer.tools.proposal import propose_spec_change
    from composer.tools.question import human_in_the_loop
    from composer.tools.result import code_result
    from composer.tools.search import cvl_manual_search, cvlr_manual_search

    # Select prover and additional tools based on target platform
    if target == "svm":
        from composer.tools.solana_prover import solana_prover
        from composer.tools.solana_tests import solana_quick_tests
        prover_tool = solana_prover
        # For SVM, include quick tests tool for TDD workflow
        crypto_tools = [solana_quick_tests, prover_tool, propose_spec_change, human_in_the_loop, code_result, cvl_manual_search, cvlr_manual_search, *vfs_tooling]
    else:
        from composer.tools.prover import certora_prover
        prover_tool = certora_prover
        crypto_tools = [prover_tool, propose_spec_change, human_in_the_loop, code_result, cvl_manual_search, cvlr_manual_search, *vfs_tooling]
    crypto_tools.extend(extra_tools)

    conf : SummaryGeneration | None = SummaryGeneration(
        max_messages=summarization_threshold
    ) if summarization_threshold else None

    workflow_builder: tuple[StateGraph[AIComposerState, AIComposerContext, Input, Any], BoundLLM] = build_workflow(
        state_class=AIComposerState,
        input_type=Input,
        tools_list=crypto_tools,
        sys_prompt=get_system_prompt(target),
        initial_prompt=get_initial_prompt(target, prompt_params),
        output_key="generated_code",
        unbound_llm=llm,
        context_schema=AIComposerContext,
        summary_config=conf
    )

    return workflow_builder + (mat,)
