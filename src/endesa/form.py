from __future__ import annotations

import io
import logging
import os
from dataclasses import dataclass
from typing import Any

from pypdf import PdfReader, PdfWriter
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.pdfgen import canvas

from src.endesa import utils
from src.settings import DEFAULT_FONT_SIZE

logging.basicConfig(
    level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')


@dataclass
class TextField:
    """
    Describes the bounding rectangle of a single form field.

    NOTE: The AcroForm field IDs in this PDF are completely mislabelled.
    Coordinates come from the AcroForm rects but are mapped to their TRUE
    visual position, confirmed by overlaying the rects on the scanned image.

    Each rect is expressed as (x0, y0, x1, y1) in PDF points, y=0 at the
    bottom of the page.
    """

    rect: tuple[float, float, float, float]


TEXT_FIELDS: dict[str, TextField] = {
    "num_service": TextField(rect=(97.23,  349.19, 182.69, 359.19)),
    "start_time":  TextField(rect=(235.47, 348.06, 265.73, 357.96)),
    "end_time":    TextField(rect=(354.51, 348.07, 386.21, 357.97)),
    "technician":  TextField(rect=(71.28,  335.06, 287.30, 345.32)),
    "company":     TextField(rect=(385.20, 334.79, 547.46, 344.95)),
    "client":      TextField(rect=(65.50,  322.10, 286.56, 332.37)),
    "address":     TextField(rect=(332.38, 322.07, 547.44, 332.33)),
    "data":        TextField(rect=(26.26,   52.50, 101.25,  74.65)),
    "dni":         TextField(rect=(132.04,  27.91, 279.73,  39.48)),
}


class EndesaFormFiller:
    """Fills an Endesa maintenance PDF form with the supplied field values.

    The class resolves a handwriting-style font, builds a transparent text
    overlay with ReportLab, merges it onto the original PDF page with pypdf,
    and writes the result to *output_path*.

    Args:
        input_path: Path to the blank Endesa PDF template.
        output_path: Destination path for the filled PDF.
        fields: Mapping of field keys to value/style descriptors.
                Each entry must be a ``dict`` with:

                * ``"value"`` *(required)* – the text to write.
                * ``"styles"`` *(optional)* – a dict that may contain
                  ``"font_size"`` (number); omit to use
                  :data:`DEFAULT_FONT_SIZE`.

                **Valid keys:** ``num_service``, ``start_time``,
                ``end_time``, ``technician``, ``company``, ``client``,
                ``address``, ``data``, ``dni``.
    """

    #: Ink colour used for all text (dark blue).
    INK_COLOR: tuple[float, float, float] = (0.05, 0.05, 0.6)

    def __init__(
        self,
        input_path: str,
        output_path: str,
        fields: dict[str, Any],
    ) -> None:
        self._input_path = input_path
        self._output_path = output_path
        self._parsed_fields = self._parse_fields(fields)
        self._font_name = self._register_font()

    # ------------------------------------------------------------------
    # Public interface
    # ------------------------------------------------------------------

    def generate(self) -> None:
        """Fill the form and write the output PDF to *output_path*.

        Raises:
            FileNotFoundError: If *input_path* does not exist.
        """
        reader = PdfReader(self._input_path)
        page = reader.pages[0]
        page_width = float(page.mediabox.width)
        page_height = float(page.mediabox.height)
        logging.info(f"Page size: {page_width:.1f} x {page_height:.1f} pt")

        overlay_bytes = self._build_overlay(page_width, page_height)
        overlay_page = PdfReader(io.BytesIO(overlay_bytes)).pages[0]
        page.merge_page(overlay_page)

        writer = PdfWriter()
        writer.add_page(page)
        for extra_page in reader.pages[1:]:
            writer.add_page(extra_page)

        with open(self._output_path, "wb") as fh:
            writer.write(fh)

        logging.info(f"✅  Filled PDF saved to: {self._output_path}")

    # ------------------------------------------------------------------
    # Private helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _parse_fields(
            fields: dict[str, Any]) -> dict[str, tuple[str, float | None]]:
        """Validate and normalise the raw *fields* mapping.

        Args:
            fields: Raw input mapping supplied by the caller.

        Returns:
            A dict of ``{field_key: (text, font_size_or_none)}``.

        Raises:
            ValueError: On unknown field keys or malformed entries.
            TypeError: When ``font_size`` cannot be coerced to ``float``.
        """
        unknown = set(fields) - set(TEXT_FIELDS)
        if unknown:
            raise ValueError(
                f"Unknown field key(s): {unknown}. "
                f"Valid keys: {set(TEXT_FIELDS)}"
            )

        parsed: dict[str, tuple[str, float | None]] = {}
        for key, entry in fields.items():
            if not isinstance(entry, dict) or "value" not in entry:
                raise ValueError(
                    f"fields['{key}'] must be a dict with at least a 'value' "
                    f"key, got: {entry!r}"
                )

            text = str(entry["value"])
            styles = entry.get("styles") or {}
            raw_fs = styles.get("font_size")
            font_size: float | None = None

            if raw_fs is not None:
                try:
                    font_size = float(raw_fs)
                except (TypeError, ValueError):
                    raise TypeError(
                        f"fields['{key}']['styles']['font_size'] must be a "
                        f"number, got {type(raw_fs).__name__!r}: {raw_fs!r}"
                    )

            parsed[key] = (text, font_size)

        return parsed

    @staticmethod
    def _register_font() -> str:
        """Locate a handwriting font, register it with ReportLab, and return
        the font name to use in ``canvas.setFont`` calls.

        Returns:
            ``"Handwriting"`` when a TTF is found, otherwise
            ``"Helvetica-Oblique"`` as a fallback.
        """
        font_path = utils.find_handwriting_font()
        if font_path:
            pdfmetrics.registerFont(TTFont("Handwriting", font_path))
            logging.info(f"Font: {os.path.basename(font_path)}")
            return "Handwriting"

        logging.info(
            "No handwriting TTF found — using Helvetica-Oblique as fallback")
        return "Helvetica-Oblique"

    def _build_overlay(self, page_width: float, page_height: float) -> bytes:
        """Render all text fields onto a transparent ReportLab canvas.

        Args:
            page_width: Width of the target PDF page in points.
            page_height: Height of the target PDF page in points.

        Returns:
            Raw bytes of a single-page PDF containing only the text overlay.
        """
        buf = io.BytesIO()
        c = canvas.Canvas(buf, pagesize=(page_width, page_height))
        c.setFillColorRGB(*self.INK_COLOR)

        for field_key, (text, font_size) in self._parsed_fields.items():
            if not text:
                continue

            fs = font_size if font_size is not None else DEFAULT_FONT_SIZE
            x0, y0, x1, y1 = TEXT_FIELDS[field_key].rect
            available_width = x1 - x0 - 4

            c.setFont(self._font_name, fs)

            # Truncate text so it fits within the field width.
            display = text
            while (
                c.stringWidth(display, self._font_name, fs) > available_width
                and len(display) > 1
            ):
                display = display[:-1]

            c.drawString(x0 + 2, utils.text_y_center(y0, y1, fs), display)

        c.save()
        return buf.getvalue()
