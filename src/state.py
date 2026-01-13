from typing import TypedDict, Optional

class AgentState(TypedDict):
    task: str                # The user's original request (e.g., "Build a Snake Game")
    plan: Optional[str]      # The step-by-step plan from the Architect
    code: Optional[str]      # The Python code written by the Coder
    review: Optional[str]    # The feedback/errors from the Reviewer
    revision_number: int     # How many times have we tried to fix it?
    max_revisions: int       # The limit (so they don't loop forever)