from typing import Annotated, List, Dict, NotRequired
from typing_extensions import TypedDict
from langchain_core.messages import AnyMessage
from langgraph.graph.message import add_messages
from pydantic import BaseModel

class ResultStateSchema(BaseModel):
    source: Dict[str, str]
    comments: str


def merge_fs(left: Dict[str, str], right: Dict[str, str]) -> Dict[str, str]:
    to_ret = left.copy()
    for (k, v) in right.items():
        to_ret[k] = v
    return to_ret

class CryptoStateGen(TypedDict):
    messages: Annotated[List[AnyMessage], add_messages]
    virtual_fs: Annotated[Dict[str, str], merge_fs]
    generated_code: NotRequired[ResultStateSchema]

