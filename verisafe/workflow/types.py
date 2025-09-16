from graphcore.graph import FlowInput
from typing import Dict

class Input(FlowInput):
    """
    Input state, with initial virtual fs definitions
    """
    virtual_fs: Dict[str, str]
