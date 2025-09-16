from typing import Callable, Optional, cast
from verisafe.human.types import ProposalType, QuestionType, HumanInteractionType
import difflib
from rich.console import Console

def prompt_input(prompt_str: str, filter: Optional[Callable[[str], Optional[str]]] = None) -> str:
    l = input(prompt_str + " (double newlines ends): ")
    buffer = ""
    num_consecutive_blank = 0
    while True:
        x = l.strip()
        buffer += x + "\n"
        if x == "":
            num_consecutive_blank += 1
        else:
            num_consecutive_blank = 0
        if num_consecutive_blank == 2:
            break
        l = input("> ")
    if filter is None:
        return buffer
    filter_res = filter(buffer)
    if filter_res is None:
        return buffer
    return prompt_input(prompt_str, filter)


def handle_proposal_interrupt(interrupt_ty: ProposalType) -> str:
    print("\n" + "=" * 80)
    print("SPEC CHANGE PROPOSAL")
    print("=" * 80)
    orig = interrupt_ty["current_spec"].splitlines(keepends=True)
    proposed = interrupt_ty["proposed_spec"].splitlines(keepends=True)

    diff = difflib.unified_diff(
        a = orig,
        fromfile="a/rules.spec",
        b = proposed,
        tofile="b/rules.spec",
        n=3,
    )

    print(f"Explanation: {interrupt_ty['explanation']}")
    print("Proposed diff is as follows:")

    console = Console(highlighter=None)

    for line in diff:
        if line.startswith("---"):
            console.print(line, style="bold white", end="")
        elif line.startswith("+++"):
            console.print(line, style="bold white", end="")
        elif line.startswith("@@"):
            console.print(line, style="cyan", end="")
        elif line.startswith("+"):
            console.print(line, style="green", end="")
        elif line.startswith("-"):
            console.print(line, style="red", end="")
        else:
            console.print(line, end="")
    
    print("")

    def filt(x: str) -> Optional[str]:
        if not (x.startswith("ACCEPTED") or x.startswith("REJECTED") or x.startswith("REFINE")):
            return "Response must begin with ACCEPTED/REJECTED/REFINE"
        return None

    return prompt_input("Response to proposal, must start with ACCEPTED/REJECTED/REFINE", filt)

def handle_question_interrupt(interrupt_data: QuestionType) -> str:
    print("\n" + "=" * 80)
    print("HUMAN ASSISTANCE REQUESTED")
    print("=" * 80)
    print(f"Question: {interrupt_data['question']}")
    print(f"Context: {interrupt_data['context']}")
    if interrupt_data["code"]:
        print(f"Code:\n{interrupt_data['code']}")
    return prompt_input("Enter your answer")


def handle_human_interrupt(interrupt_data: dict) -> str:
    """Handle human-in-the-loop interrupts and get user input."""
    interrupt_ty = cast(HumanInteractionType, interrupt_data)

    if interrupt_ty["type"] == "proposal":
        return handle_proposal_interrupt(interrupt_ty)
    else:
        assert interrupt_ty["type"] == "question"
        return handle_question_interrupt(interrupt_ty)