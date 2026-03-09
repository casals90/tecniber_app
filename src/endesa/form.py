from __future__ import annotations

import io
import logging
import os
from dataclasses import dataclass
from typing import Any

from PIL import Image
from pypdf import PdfReader, PdfWriter
from reportlab.lib.utils import ImageReader
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
    "date":        TextField(rect=(26.26,   52.50, 101.25,  74.65)),
    "dni":         TextField(rect=(132.04,  27.91, 279.73,  39.48)),
    "signature":   TextField(rect=(132.00,  35.00, 280.00,  70.00)),
}


class EndesaFormFiller:
    """
    Fills an Endesa maintenance PDF form with the supplied field values 
    and signature.

    This class resolves a handwriting-style font, processes image-based 
    signatures (removing backgrounds and cropping), builds a transparent text 
    and image overlay using ReportLab, merges it onto the original PDF page 
    with pypdf, and writes the result to a specified output path.
    """

    #: Ink colour used for all text (dark blue).
    INK_COLOR: tuple[float, float, float] = (0.05, 0.05, 0.6)

    def __init__(
        self,
        input_path: str,
        output_path: str,
        fields: dict[str, Any],
    ) -> None:
        """
        Initializes the form filler with input/output paths and raw field data.

        Args:
            input_path (str): Path to the blank Endesa PDF template.
            output_path (str): Destination path for the filled PDF.
            fields (dict[str, Any]): Mapping of field keys to their values. 
                Values can be text strings or a PIL Image (for the signature).
        """
        self._input_path = input_path
        self._output_path = output_path

        cleaned_fields = self._clean_fields(fields)
        self._parsed_fields = self._parse_fields(cleaned_fields)

        self._font_name = self._register_font()

    def generate(self) -> None:
        """
        Processes the template, applies the overlay, and saves the final PDF.

        Reads the input PDF template, determines its dimensions, generates a 
        transparent overlay containing the text and signature image, merges the 
        overlay onto the first page, and writes the complete document to the 
        output path.

        Raises:
            FileNotFoundError: If the input PDF template does not exist.
        """
        reader = PdfReader(self._input_path)
        page = reader.pages[0]
        page_width = float(page.mediabox.width)
        page_height = float(page.mediabox.height)

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

    @staticmethod
    def _clean_fields(fields: dict[str, Any]) -> dict[str, Any]:
        """
        Maps raw input data to the internal field structure and default styles.

        Args:
            fields (dict[str, Any]): The raw dictionary of form data submitted 
                by the user or frontend.

        Returns:
            dict[str, Any]: A structured dictionary containing 'value' and 
            optional 'styles' (like 'font_size') for each specific PDF field.
        """
        cleaned_fields = {
            "num_service": {
                "value": fields.get("service_num")
            },
            "start_time": {
                "value": fields.get("start_time")
            },
            "end_time": {
                "value": fields.get("end_time")},
            "technician": {
                "value": fields.get("technician")},
            "company": {
                "value": fields.get("company", "FAKE")},
            "client": {
                "value": fields.get("client")},
            "address": {
                "value": fields.get("address")},
            "date": {
                "value": fields.get("service_date").strftime("%d/%m/%Y"),
                "styles": {"font_size": 12}
            },
            "dni": {
                "value": fields.get("dni"),
                "styles": {"font_size": 15}
            },
            "signature": {
                "value": fields.get("signature")
            }
        }

        return cleaned_fields

    @staticmethod
    def _parse_fields(
            fields: dict[str, Any]) -> dict[str, tuple[Any, float | None]]:
        """
        Validates and normalizes the structured field mapping.

        Checks against known `TEXT_FIELDS`, ensuring no invalid keys are 
        passed. It preserves PIL Image objects (for signatures) while 
        converting standard text fields to strings.

        Args:
            fields (dict[str, Any]): The structured dictionary 
                from `_clean_fields`.

        Returns:
            dict[str, tuple[Any, float | None]]: A dictionary mapping valid 
            keys to a tuple containing the content (str or PIL Image) and the 
            font size.

        Raises:
            ValueError: On unknown field keys or malformed dictionary entries.
            TypeError: When a provided `font_size` cannot be coerced to 
                a float.
        """

        unknown = set(fields) - set(TEXT_FIELDS)
        if unknown:
            raise ValueError(
                f"Unknown field key(s): {unknown}. "
                f"Valid keys: {set(TEXT_FIELDS)}"
            )

        parsed: dict[str, tuple[Any, float | None]] = {}
        for key, entry in fields.items():
            if not isinstance(entry, dict) or "value" not in entry:
                raise ValueError(
                    f"fields['{key}'] must be a dict with at least a 'value' "
                    f"key, got: {entry!r}"
                )

            # --- UPDATED LOGIC HERE ---
            val = entry["value"]
            if isinstance(val, Image.Image):
                # Clean and crop the signature image
                content = EndesaFormFiller._clean_signature(val)
            else:
                # Convert standard fields to strings
                content = str(val) if val is not None else ""

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

            parsed[key] = (content, font_size)

        return parsed

    @staticmethod
    def _clean_signature(img: Image.Image) -> Image.Image:
        """
        Processes a signature image by removing its background and cropping it.

        Converts light-colored pixels (typically the Streamlit canvas 
        background) to transparent pixels, turns the drawn strokes into dark 
        blue ink, and crops the image tightly around the actual signature 
        strokes using a bounding box.

        Args:
            img (Image.Image): The raw PIL Image object from the signature pad.

        Returns:
            Image.Image: A processed, tightly cropped PIL Image with a 
            transparent background.
        """
        img = img.convert("RGBA")
        data = img.getdata()

        new_data = []
        for item in data:
            # If the pixel is light-colored (the gray #EEEEEE background
            # or white). Make it completely transparent
            if item[0] > 200 and item[1] > 200 and item[2] > 200:
                new_data.append((255, 255, 255, 0))
            else:
                # Make the drawn strokes solid dark blue/black
                new_data.append((10, 10, 150, 255))

        img.putdata(new_data)

        # Crop the image tightly around the non-transparent pixels
        bbox = img.getbbox()
        if bbox:
            img = img.crop(bbox)

        return img

    @staticmethod
    def _register_font() -> str:
        """
        Locates a handwriting font, registers it with ReportLab, and 
        returns its name.

        Returns:
            str: `"Handwriting"` if a valid TTF is found, otherwise 
            `"Helvetica-Oblique"` as a fallback.
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
        """
        Renders all text fields and the signature image onto a transparent 
        canvas.

        Iterates over the parsed fields. If a field contains an image, it 
        scales and draws the image within the defined bounding box. If it 
        contains text, it truncates the text to fit the available width and 
        draws it vertically centered.

        Args:
            page_width (float): Width of the target PDF page in points.
            page_height (float): Height of the target PDF page in points.

        Returns:
            bytes: Raw bytes of a single-page PDF containing only the 
            text/image overlay.
        """
        buf = io.BytesIO()
        c = canvas.Canvas(buf, pagesize=(page_width, page_height))

        for field_key, (content, font_size) in self._parsed_fields.items():
            if not content:
                continue

            x0, y0, x1, y1 = TEXT_FIELDS[field_key].rect

            c.saveState()  # ← isolate every field's color state

            if isinstance(content, Image.Image):
                img_reader = ImageReader(content)
                c.drawImage(
                    img_reader, x0, y0,
                    width=x1 - x0, height=y1 - y0,
                    mask='auto', preserveAspectRatio=True)
            else:
                fs = font_size if font_size is not None else DEFAULT_FONT_SIZE
                available_width = x1 - x0 - 4
                c.setFont(self._font_name, fs)
                # ← set per field, not globally
                c.setFillColorRGB(*self.INK_COLOR)

                display = content
                while (
                    c.stringWidth(display, self._font_name,
                                  fs) > available_width
                    and len(display) > 1
                ):
                    display = display[:-1]

                c.drawString(x0 + 2, utils.text_y_center(y0, y1, fs), display)

            c.restoreState()

        c.save()
        return buf.getvalue()
