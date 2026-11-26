"""The real converter.

Streamed, because an ~80-row TK is a long generation and a non-streamed request is the
kind of thing that dies quietly behind a proxy. One retry on a schema failure, with the
validation error fed back to the model verbatim -- a second failure is recorded as a
failed run rather than retried forever.
"""

from __future__ import annotations

import time

from app.config import MAX_OUTPUT_TOKENS
from app.converter.base import ConversionFailed, ConverterResult
from app.schemas import LlmRow, SchemaFailure, parse_rows

RETRY_INSTRUCTION = (
    "Eelmine vastus ei vastanud skeemile. Viga:\n{error}\n\n"
    "Paranda see ja vasta UUESTI ainult korrektse JSON-massiiviga, "
    "ilma selgitusteta ja ilma koodiplokkideta."
)


def _user_message(numbered_mmr: str) -> str:
    return (
        "Allpool on MMR, mille iga lõik on nummerdatud ja märgistatud tüübiga.\n"
        "Teisenda see TK ridadeks vastavalt juhendile. Vasta ainult JSON-massiiviga.\n\n"
        f"{numbered_mmr}"
    )


def _collect(stream) -> str:
    chunks: list[str] = []
    for text in stream.text_stream:
        chunks.append(text)
    return "".join(chunks)


def convert(
    *,
    api_key: str,
    model: str,
    system_prompt: str,
    numbered_mmr: str,
    temperature: float,
    valid_sids: set[str],
    max_tokens: int = MAX_OUTPUT_TOKENS,
) -> ConverterResult:
    try:
        from anthropic import Anthropic
    except ImportError as exc:  # pragma: no cover - dependency is in requirements.txt
        raise ConversionFailed(f"Anthropic SDK ei ole saadaval: {exc}") from exc

    client = Anthropic(api_key=api_key)
    messages: list[dict] = [{"role": "user", "content": _user_message(numbered_mmr)}]

    input_tokens = 0
    output_tokens = 0
    elapsed = 0.0
    retry_used = False
    last_text = ""
    last_error = ""

    for attempt in (1, 2):
        started = time.perf_counter()
        try:
            with client.messages.stream(
                model=model,
                max_tokens=max_tokens,
                temperature=temperature,
                system=system_prompt,
                messages=messages,
            ) as stream:
                text = _collect(stream)
                final = stream.get_final_message()
        except Exception as exc:  # network, auth, rate limit, overload
            elapsed += time.perf_counter() - started
            raise ConversionFailed(
                f"Mudeli päring ebaõnnestus: {type(exc).__name__}: {exc}",
                raw_text=last_text,
                retry_used=retry_used,
            ) from exc

        elapsed += time.perf_counter() - started
        last_text = text
        usage = getattr(final, "usage", None)
        if usage is not None:
            input_tokens += int(getattr(usage, "input_tokens", 0) or 0)
            output_tokens += int(getattr(usage, "output_tokens", 0) or 0)

        try:
            rows: list[LlmRow] = parse_rows(text, valid_sids)
        except SchemaFailure as failure:
            last_error = str(failure)
            if attempt == 2:
                break
            retry_used = True
            messages.append({"role": "assistant", "content": text})
            messages.append(
                {"role": "user", "content": RETRY_INSTRUCTION.format(error=last_error)}
            )
            continue

        return ConverterResult(
            rows=rows,
            model=model,
            input_tokens=input_tokens,
            output_tokens=output_tokens,
            processing_seconds=round(elapsed, 3),
            retry_used=retry_used,
            mock=False,
            raw_text=text,
        )

    raise ConversionFailed(
        "Mudeli vastus ei vastanud skeemile ka pärast kordust. " + last_error,
        raw_text=last_text,
        retry_used=True,
    )
