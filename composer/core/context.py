from dataclasses import dataclass, field
import hashlib

from graphcore.graph import BoundLLM
from graphcore.tools.vfs import VFSAccessor

from composer.core.state import AIComposerState
from composer.rag.db import PostgreSQLRAGDatabase
from composer.core.validation import ValidationType, prover
from composer.input.types import TargetPlatform, get_spec_filename

@dataclass
class ProverOptions:
    capture_output: bool
    keep_folder: bool

@dataclass
class AIComposerContext:
    llm: BoundLLM
    rag_db: PostgreSQLRAGDatabase
    prover_opts: ProverOptions
    vfs_materializer: VFSAccessor[AIComposerState]
    required_validations: list[ValidationType] = field(default_factory=lambda: [prover])
    cvlr_rag_db: PostgreSQLRAGDatabase | None = None
    target: TargetPlatform = "evm"
    spec_filename: str = "rules.spec"

def compute_state_digest(c: AIComposerContext, state: AIComposerState) -> str:
    # not interested in cryptographic bulletproofing, just need *some* digest
    digester = hashlib.md5()
    for (_, cont) in sorted(c.vfs_materializer.iterate(state), key = lambda x: x[0]):
        digester.update(cont)
    return digester.hexdigest()
