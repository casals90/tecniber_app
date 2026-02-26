import glob
import io
import logging
import os
import platform
from datetime import datetime

from PIL import Image
from pypdf import PdfReader, PdfWriter
from reportlab.lib.colors import white
from reportlab.lib.utils import ImageReader
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.pdfgen import canvas

logging.basicConfig(
    level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

# ---------------------------------------------------------------------------
# Page geometry (PDF points)
# ---------------------------------------------------------------------------

PAGE_HEIGHT = 842.4
PAGE_WIDTH = 596.88

# ---------------------------------------------------------------------------
# Zone definitions
# ---------------------------------------------------------------------------

_BLOCK1_DATE = dict(x0=288.1, x1=350.0, erase_y0=737.2, erase_y1=746.2)
_BLOCK1_TIME = dict(x0=379.2, x1=427.0, erase_y0=737.2, erase_y1=746.2)
_BLOCK2_DATE = dict(x0=289.6, x1=350.0, erase_y0=441.5, erase_y1=450.5)
_BLOCK2_TIME = dict(x0=381.2, x1=428.0, erase_y0=441.5, erase_y1=450.5)
_DNI = dict(x0=295.6, y_baseline=500.0)
_SIGNATURE = dict(x=280.0, y=510.0, width=120.0, height=50.0)

# ---------------------------------------------------------------------------
# Fonts
# ---------------------------------------------------------------------------

_HANDWRITE_CANDIDATES = [
    "Bradley Hand Bold.ttf", "Noteworthy Bold.ttf", "Chalkboard.ttc",
    "Marker Felt Thin.ttf", "Apple Chancery.ttf", "Caladea-Italic.ttf",
    "Carlito-Italic.ttf", "DejaVuSerif-Italic.ttf", "FreeSerifItalic.ttf",
    "FreeSansOblique.ttf",
]

_TICKET_FONT_CANDIDATES = [
    "LiberationSans-Regular.ttf", "FreeSans.ttf", "DejaVuSans.ttf",
    "NotoSans-Regular.ttf", "Arial.ttf",
]


class TicketFiller:
    _TICKET_FONT_NAME = "TicketFont"
    _HANDWRITE_FONT_NAME = "Handwriting"
    _TICKET_FONT_SIZE = 7.0
    _DNI_FONT_SIZE = 12.0

    def __init__(
        self,
        input_path: str,
        output_path: str,
        date1: datetime.date,
        time1: datetime.time,
        time2: datetime.time,
        dni: str,
        signature: Image.Image | None = None,
    ) -> None:
        self.input_path = input_path
        self.output_path = output_path

        self.date1 = date1.strftime("%d . %m . %Y")
        self.time1 = time1.strftime("%H : %M : %S")
        self.date2 = self.date1
        self.time2 = time2.strftime("%H : %M : %S")
        self.dni = dni
        self.signature = signature

        self._ticket_font_name: str = "Helvetica"
        self._handwrite_font_name: str = "Helvetica-Oblique"

    def fill(self) -> None:
        self._resolve_fonts()

        reader = PdfReader(self.input_path)
        page = reader.pages[0]

        overlay_bytes = self._build_overlay(
            self.date1, self.time1, self.date2, self.time2, self.dni, self.signature)

        overlay_page = PdfReader(io.BytesIO(overlay_bytes)).pages[0]
        page.merge_page(overlay_page)

        writer = PdfWriter()
        writer.add_page(page)
        for extra in reader.pages[1:]:
            writer.add_page(extra)

        with open(self.output_path, "wb") as f:
            writer.write(f)

        logging.info(f"✅  Saved to: {self.output_path}")

    # ------------------------------------------------------------------
    # Image Cleaning
    # ------------------------------------------------------------------

    @staticmethod
    def _clean_signature(img: Image.Image) -> Image.Image:
        """Removes the gray/white background and crops the empty space."""
        img = img.convert("RGBA")
        data = img.getdata()

        new_data = []
        for item in data:
            if item[0] > 200 and item[1] > 200 and item[2] > 200:
                new_data.append((255, 255, 255, 0))
            else:
                new_data.append((10, 10, 150, 255))

        img.putdata(new_data)

        bbox = img.getbbox()
        if bbox:
            img = img.crop(bbox)

        return img

    # ------------------------------------------------------------------
    # Font resolution
    # ------------------------------------------------------------------

    def _resolve_fonts(self) -> None:
        ticket_path = self._find_font(_TICKET_FONT_CANDIDATES)
        handwrite_path = self._find_font(_HANDWRITE_CANDIDATES)

        if ticket_path:
            pdfmetrics.registerFont(
                TTFont(self._TICKET_FONT_NAME, ticket_path))
            self._ticket_font_name = self._TICKET_FONT_NAME
        else:
            logging.info("Ticket font: not found — using Helvetica fallback")

        if handwrite_path:
            pdfmetrics.registerFont(
                TTFont(self._HANDWRITE_FONT_NAME, handwrite_path))
            self._handwrite_font_name = self._HANDWRITE_FONT_NAME
        else:
            logging.info(
                "Handwrite font: not found — using Helvetica-Oblique fallback")

    @staticmethod
    def _find_font(candidates: list[str]) -> str | None:
        system = platform.system()
        if system == "Darwin":
            search_dirs = ["/Library/Fonts", "/System/Library/Fonts",
                           os.path.expanduser("~/Library/Fonts")]
        elif system == "Windows":
            search_dirs = [r"C:\Windows\Fonts"]
        else:
            search_dirs = [
                "/usr/share/fonts", "/usr/local/share/fonts", os.path.expanduser("~/.fonts")]

        for name in candidates:
            for directory in search_dirs:
                matches = glob.glob(os.path.join(
                    directory, "**", name), recursive=True)
                if matches:
                    return matches[0]
        return None

    # ------------------------------------------------------------------
    # Overlay builder
    # ------------------------------------------------------------------

    def _build_overlay(
        self,
        date1: str,
        time1: str,
        date2: str,
        time2: str,
        dni:   str,
        signature: Image.Image | None,
    ) -> bytes:
        with io.BytesIO() as buf:
            c = canvas.Canvas(buf, pagesize=(PAGE_WIDTH, PAGE_HEIGHT))

            # --- Date / time replacements ---
            for text, zone in [
                (date1, _BLOCK1_DATE),
                (time1, _BLOCK1_TIME),
                (date2, _BLOCK2_DATE),
                (time2, _BLOCK2_TIME),
            ]:
                if text:
                    self._erase(c, zone)
                    self._draw_ticket_text(c, text, zone)

            # --- 7. SIGNATURE ANNOTATION ---
            if signature and isinstance(signature, Image.Image):
                cleaned_sig = self._clean_signature(signature)
                img_reader = ImageReader(cleaned_sig)

                # Draw the signature inside the defined zone
                c.drawImage(
                    img_reader,
                    x=_SIGNATURE["x"],
                    y=_SIGNATURE["y"],
                    width=_SIGNATURE["width"],
                    height=_SIGNATURE["height"],
                    mask='auto',
                    preserveAspectRatio=True
                )

            # --- DNI annotation ---
            if dni:
                c.setFont(self._handwrite_font_name, self._DNI_FONT_SIZE)
                c.setFillColorRGB(0.05, 0.05, 0.6)   # dark-blue ink
                c.drawString(_DNI["x0"], _DNI["y_baseline"], dni)

            c.save()
            return buf.getvalue()

    @staticmethod
    def _erase(c: canvas.Canvas, zone: dict) -> None:
        c.setFillColor(white)
        c.setStrokeColor(white)
        c.rect(
            zone["x0"], zone["erase_y0"],
            zone["x1"] - zone["x0"],
            zone["erase_y1"] - zone["erase_y0"],
            fill=1, stroke=0,
        )

    def _draw_ticket_text(self, c: canvas.Canvas, text: str, zone: dict) -> None:
        c.setFillColorRGB(0.0, 0.0, 0.0)
        c.setFont(self._ticket_font_name, self._TICKET_FONT_SIZE)
        baseline = zone["erase_y0"] + 2.0
        c.drawString(zone["x0"], baseline, text)
