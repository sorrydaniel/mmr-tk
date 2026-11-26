"""M / N / I / OP signal detection.

Whether a requirement is mandatory or negotiable is an RKIK procurement decision, not
something stated in the MMR. So the rule is: default to M, and deviate only on an explicit
lexical signal. Used by the mock converter, and as a fallback when the model returns a
classification without naming the word that caused it.
"""

from __future__ import annotations

import re

# Longer phrases first so "kui võimalik" wins over "võimalusel" inside the same sentence.
N_SIGNALS: tuple[str, ...] = (
    "kui võimalik",
    "võimalusel",
    "eelistatavalt",
    "soovitavalt",
    "soovituslik",
    "näidistoode",
    "näiteks nagu",
    "peaks",
    "võiks",
)

OP_SIGNALS: tuple[str, ...] = (
    "pakkuda eraldi hinnaga",
    "lisavõimalusena",
    "valikuliselt",
    "optsioon",
)

M_SIGNALS: tuple[str, ...] = (
    "on kohustuslik",
    "peab",
    "tuleb",
)

# Statements of intent, purpose and scope - informative only, no compliance assessment.
I_SIGNALS: tuple[str, ...] = (
    "käesoleva dokumendi eesmärk",
    "dokumendi eesmärk",
    "hankija eesmärk",
    "hanke eesmärk",
    "eesmärk on",
    "on ette nähtud",
    "kasutusotstarve",
    "üldine kirjeldus",
)

UNCERTAIN_CLASSIFICATION_REASON = "klassifikatsioon ebaselge"


def _find(text: str, signals: tuple[str, ...]) -> str | None:
    lowered = text.casefold()
    for signal in signals:
        if re.search(rf"(?<!\w){re.escape(signal)}", lowered):
            return signal
    return None


def detect(text: str) -> tuple[str, str | None, bool]:
    """Return (classification, signal, ambiguous).

    `ambiguous` is true when signals from more than one non-mandatory class appear in the
    same sentence. In that case the classification stays M and the caller is expected to
    mark the row uncertain.
    """
    body = text or ""

    op_signal = _find(body, OP_SIGNALS)
    n_signal = _find(body, N_SIGNALS)
    i_signal = _find(body, I_SIGNALS)
    m_signal = _find(body, M_SIGNALS)

    hits = [s for s in (op_signal, n_signal, i_signal) if s]
    if len(hits) > 1:
        return "M", hits[0], True

    if op_signal:
        return "OP", op_signal, False
    if n_signal:
        # "peab ... võimalusel" is contradictory: a hard modal and a soft one together.
        if m_signal:
            return "M", n_signal, True
        return "N", n_signal, False
    if i_signal:
        return "I", i_signal, False
    if m_signal:
        return "M", m_signal, False
    # No modal at all is still mandatory, per RKIK practice.
    return "M", None, False


def backfill_signal(classification: str, text: str) -> str | None:
    """Find the word that justifies a classification the model already chose."""
    signals = {
        "N": N_SIGNALS,
        "OP": OP_SIGNALS,
        "I": I_SIGNALS,
        "M": M_SIGNALS,
    }.get(classification, ())
    return _find(text or "", signals)
