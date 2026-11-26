from __future__ import annotations

from dataclasses import dataclass, field

from app.schemas import LlmRow


@dataclass
class ConverterResult:
    rows: list[LlmRow] = field(default_factory=list)
    model: str = ""
    input_tokens: int = 0
    output_tokens: int = 0
    # Model time only. Queue time is measured by the runner and stored separately.
    processing_seconds: float = 0.0
    retry_used: bool = False
    mock: bool = False
    raw_text: str = ""


class ConversionFailed(RuntimeError):
    """Carries an Estonian message that is safe to show the user."""

    def __init__(self, message: str, *, raw_text: str = "", retry_used: bool = False) -> None:
        super().__init__(message)
        self.message = message
        self.raw_text = raw_text
        self.retry_used = retry_used
