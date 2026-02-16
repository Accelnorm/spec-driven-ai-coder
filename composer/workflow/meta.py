# for meta iteration

from typing import Any
from langchain_core.language_models.chat_models import BaseChatModel
from langchain_core.messages import BaseMessage, ToolMessage, HumanMessage
from langchain_anthropic import ChatAnthropic

from pydantic import BaseModel, Field

from composer.core.state import AIComposerState
from composer.templates.loader import load_jinja_template

class ResumeCommentary(BaseModel):
    """
    The structured output to use for generating the resume commentary.
    """

    commentary: str = Field(description="Your commentary describing your work, what you did, and " \
    "what should be kept in mind if this work needs to be resume.")

    interface_path: str = Field(description="The path of the interface file on the VFS")


def _content_block_to_text(block: Any) -> str:
    """Convert a single content block (string or dict) to plain text."""
    if isinstance(block, str):
        return block
    if isinstance(block, dict):
        if block.get("type") == "text":
            return block.get("text", "")
        # Anthropic-specific blocks (e.g. "document" with file_id) have no
        # portable text representation; skip them.
        return ""
    return str(block)


def _sanitize_message_content(msg: BaseMessage) -> BaseMessage:
    """Return a copy of *msg* whose content is a plain string.

    Messages produced during the workflow may carry multipart content
    (a list mixing strings and Anthropic-specific dicts such as
    ``{"type": "document", "source": {"type": "file", ...}}``).
    OpenAI-compatible providers cannot handle these, so we flatten
    the list into a single text string.
    """
    if not isinstance(msg.content, list):
        return msg
    text = "\n".join(
        t for block in msg.content
        if (t := _content_block_to_text(block))
    )
    return msg.model_copy(update={"content": text})


def create_resume_commentary(state: AIComposerState, llm: BaseChatModel) -> ResumeCommentary:
    structured_llm: BaseChatModel = llm
    is_anthropic = isinstance(llm, ChatAnthropic)
    if is_anthropic:
        thinking = getattr(llm, "thinking", None)
        if isinstance(thinking, dict) and thinking.get("type") == "enabled":
            try:
                structured_llm = llm.model_copy(update={"thinking": {"type": "disabled"}})
            except Exception:
                try:
                    structured_llm = llm.copy(update={"thinking": {"type": "disabled"}})
                except Exception:
                    structured_llm = llm

    bound = structured_llm.with_structured_output(ResumeCommentary)
    messages = state["messages"].copy()

    last = messages[-1]
    assert isinstance(last, ToolMessage)

    # Non-Anthropic providers cannot handle Anthropic-specific multipart
    # content blocks (e.g. file_id references).  Flatten to plain text.
    if not is_anthropic:
        messages = [_sanitize_message_content(m) for m in messages]

    messages.append(HumanMessage(load_jinja_template("final_commentary_prompt.j2")))

    res = bound.invoke(messages)
    assert isinstance(res, ResumeCommentary)
    return res
