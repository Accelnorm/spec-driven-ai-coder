from typing import TypedDict

from graphcore.graph import FlowInput
from composer.input.types import TargetPlatform

# Re-export for convenience
__all__ = ["TargetPlatform", "PromptParams", "Input"]

class PromptParams(TypedDict):
    is_resume: bool
    no_fv: bool

class Input(FlowInput):
    """
    Input state, with initial virtual fs definitions
    """
    vfs: dict[str, str]
