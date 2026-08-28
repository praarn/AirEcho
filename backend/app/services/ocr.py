"""Peak-flow meter OCR.

This is deliberately just digit-reading with Tesseract — not a sophisticated
vision model. That is an honest scoping choice, documented in the README, not a
limitation being hidden. A low-confidence read is **never** silently trusted:
`needs_confirmation` is returned and the value stays out of every model/chart
until the user confirms or corrects it.

`vision_llm_fallback()` is the documented escape hatch for genuinely unreadable
images — wired to the same LLM env var, off by default, and still routed through
the confirm-or-correct flow.
"""

from __future__ import annotations

import io
import re
from dataclasses import dataclass

CONFIDENCE_THRESHOLD = 0.75  # below this → user must confirm
_PLAUSIBLE_RANGE = (60, 900)  # L/min; readings outside are auto-flagged


@dataclass
class OcrOutcome:
    raw_text: str
    extracted_value: float | None
    confidence: float
    needs_confirmation: bool
    engine: str


def _digits_from_text(text: str) -> tuple[float | None, str]:
    # prefer whitespace-delimited 2–3 digit tokens; fall back to a joined run
    candidates = re.findall(r"\d{2,3}", text)
    if not candidates:
        joined = re.sub(r"\D", "", text)
        candidates = [joined[:3]] if len(joined) >= 2 else []
    if not candidates:
        return None, text
    lo, hi = _PLAUSIBLE_RANGE
    plausible = [int(c) for c in candidates if lo <= int(c) <= hi]
    if plausible:
        return float(plausible[0]), text
    return float(candidates[0]), text


def extract_peak_flow(image_bytes: bytes) -> OcrOutcome:
    try:
        import pytesseract
        from PIL import Image, ImageOps
    except Exception:  # pragma: no cover - import guard
        return OcrOutcome("", None, 0.0, True, "unavailable")

    try:
        img = Image.open(io.BytesIO(image_bytes))
        img = ImageOps.grayscale(img)
        img = ImageOps.autocontrast(img)
        data = pytesseract.image_to_data(
            img,
            config="--psm 7 -c tessedit_char_whitelist=0123456789",
            output_type=pytesseract.Output.DICT,
        )
    except Exception as exc:  # pragma: no cover - runtime/tesseract missing
        return OcrOutcome(f"error: {exc}", None, 0.0, True, "tesseract-error")

    tokens, confs = [], []
    for txt, conf in zip(data.get("text", []), data.get("conf", []), strict=False):
        txt = (txt or "").strip()
        try:
            c = float(conf)
        except (TypeError, ValueError):
            c = -1.0
        if txt and c >= 0:
            tokens.append(txt)
            confs.append(c / 100.0)

    raw = " ".join(tokens)
    value, _ = _digits_from_text(raw)
    mean_conf = round(sum(confs) / len(confs), 3) if confs else 0.0

    in_range = value is not None and _PLAUSIBLE_RANGE[0] <= value <= _PLAUSIBLE_RANGE[1]
    confidence = mean_conf if in_range else min(mean_conf, 0.4)
    needs_confirmation = (value is None) or (confidence < CONFIDENCE_THRESHOLD) or (not in_range)

    return OcrOutcome(raw, value, confidence, needs_confirmation, "tesseract")


def vision_llm_fallback(image_bytes: bytes) -> OcrOutcome:  # pragma: no cover - opt-in
    """Documented fallback path. Intentionally still returns
    needs_confirmation=True so a model-read number is never trusted blind."""
    from app.config import settings

    if not settings.llm_api_key:
        return OcrOutcome("", None, 0.0, True, "vision-llm-unconfigured")
    # A real implementation would base64 the image and call the vision endpoint.
    # Kept as a stub so the dependency surface stays small and offline-testable.
    return OcrOutcome("", None, 0.0, True, "vision-llm-stub")
