"""OCR pipeline: the safety property is that a low-confidence or implausible read
is ALWAYS flagged for manual confirmation, never silently trusted.
"""

from __future__ import annotations

import io
import shutil

import pytest

from app.services.ocr import _digits_from_text, extract_peak_flow

_HAS_TESSERACT = shutil.which("tesseract") is not None


def _render_digits(text: str) -> bytes:
    from PIL import Image, ImageDraw

    img = Image.new("RGB", (240, 120), "white")
    d = ImageDraw.Draw(img)
    try:
        from PIL import ImageFont

        font = ImageFont.truetype("DejaVuSans-Bold.ttf", 72)
    except Exception:
        font = None
    d.text((40, 20), text, fill="black", font=font)
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    return buf.getvalue()


def test_digit_parser_prefers_plausible_peakflow_token():
    # a stray "12" plus the real reading "430"
    val, _ = _digits_from_text("12 430")
    assert val == 430.0


def test_digit_parser_returns_none_when_no_digits():
    val, _ = _digits_from_text("no numbers here")
    assert val is None


def test_unreadable_image_is_flagged_for_confirmation():
    outcome = extract_peak_flow(b"not-an-image")
    assert outcome.needs_confirmation is True
    assert outcome.extracted_value is None
    assert outcome.confidence < 0.75


def test_blank_image_is_flagged():
    from PIL import Image

    buf = io.BytesIO()
    Image.new("RGB", (200, 100), "white").save(buf, format="PNG")
    outcome = extract_peak_flow(buf.getvalue())
    assert outcome.needs_confirmation is True


@pytest.mark.skipif(not _HAS_TESSERACT, reason="tesseract binary not installed")
def test_real_ocr_reads_a_clear_number_or_asks_to_confirm():
    outcome = extract_peak_flow(_render_digits("430"))
    if not outcome.needs_confirmation:
        # if it was confident, it must have read something near 430
        assert outcome.extracted_value == pytest.approx(430, abs=40)
        assert outcome.engine == "tesseract"
    else:
        # otherwise it correctly deferred to the user
        assert outcome.confidence < 0.75


def test_api_typed_peakflow_is_trusted_low_confidence_photo_is_not(client, auth):
    typed = client.post("/symptoms", json={"severity": 4, "peak_flow_value": 410}).json()
    assert typed["manually_confirmed"] is True
    assert typed["needs_confirmation"] is False

    files = {"file": ("m.png", _render_digits("garbled"), "image/png")}
    r = client.post("/symptoms/with-photo", data={"severity": "5"}, files=files)
    assert r.status_code == 201
    photo = r.json()
    # a garbled photo must never come back as a trusted value
    if photo["peak_flow_value"] is not None:
        assert photo["needs_confirmation"] is True

    # confirm-or-correct flow makes it trusted
    if photo["peak_flow_value"] is not None:
        fixed = client.post(
            f"/symptoms/{photo['id']}/confirm-peak-flow", json={"peak_flow_value": 395}
        ).json()
        assert fixed["manually_confirmed"] is True
        assert fixed["peak_flow_value"] == 395
