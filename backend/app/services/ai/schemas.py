from dataclasses import dataclass, field
from typing import Any, Awaitable, Callable


@dataclass
class ToolSpec:
    """A backend function the model may call. `handler(args) -> dict` runs on our server."""
    name: str
    description: str
    input_schema: dict
    handler: Callable[[dict], Awaitable[dict]]


@dataclass
class ChatOutcome:
    text: str
    tool_results: list[dict] = field(default_factory=list)   # every result the model saw, for checking the answer
    refused: bool = False
    input_tokens: int = 0
    output_tokens: int = 0
    model: str = ""


@dataclass
class Usage:
    input_tokens: int
    output_tokens: int
    model: str
    raw: Any = None
