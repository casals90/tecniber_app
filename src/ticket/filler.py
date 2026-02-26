import glob
import io
import logging
import os
import platform
from datetime import datetime

from pypdf import PdfReader, PdfWriter
from reportlab.lib.colors import white
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
# All coordinates in ReportLab points (y=0 at BOTTOM).
# Derived from pdfplumber extraction:  rl_y = PAGE_HEIGHT - pdfplumber_top/bottom
#
# Each zone: x0      = left edge of text block
#            x1      = right edge of erase rectangle
#            erase_y0 = bottom of white erase rectangle
#            erase_y1 = top   of white erase rectangle
# ---------------------------------------------------------------------------

_BLOCK1_DATE = dict(x0=288.1, x1=350.0, erase_y0=737.2, erase_y1=746.2)
_BLOCK1_TIME = dict(x0=379.2, x1=427.0, erase_y0=737.2, erase_y1=746.2)
_BLOCK2_DATE = dict(x0=289.6, x1=350.0, erase_y0=441.5, erase_y1=450.5)
_BLOCK2_TIME = dict(x0=381.2, x1=428.0, erase_y0=441.5, erase_y1=450.5)

# DNI sits in the empty gap just above "testo 315-4" (rl_y1 ≈ 482.8)
# _DNI = dict(x0=289.6, y_baseline=488.0)
_DNI = dict(x0=289.6, y_baseline=522.0)

# ---------------------------------------------------------------------------
# Font candidates for the handwriting-style DNI
# ---------------------------------------------------------------------------

_HANDWRITE_CANDIDATES = [
    # macOS
    "Bradley Hand Bold.ttf",
    "Noteworthy Bold.ttf",
    "Chalkboard.ttc",
    "Marker Felt Thin.ttf",
    "Apple Chancery.ttf",
    # Linux / cross-platform
    "Caladea-Italic.ttf",
    "Carlito-Italic.ttf",
    "DejaVuSerif-Italic.ttf",
    "FreeSerifItalic.ttf",
    "FreeSansOblique.ttf",
    # TODO: Windows
]

# Candidates for the ticket body font (metric-compatible with MS Sans Serif)
_TICKET_FONT_CANDIDATES = [
    # exact metric match for Arial/MS Sans Serif
    "LiberationSans-Regular.ttf",
    "FreeSans.ttf",
    "DejaVuSans.ttf",
    "NotoSans-Regular.ttf",
    "Arial.ttf",
]


class TicketFiller:
    """
    Fills date/time fields and adds a DNI annotation to a testo ticket PDF.

    The class separates concerns into three responsibilities:
      - Font resolution  (_resolve_fonts)
      - Overlay creation (_build_overlay)
      - PDF merge + save (fill)
    """

    _TICKET_FONT_NAME = "TicketFont"    # ReportLab internal name
    _HANDWRITE_FONT_NAME = "Handwriting"   # ReportLab internal name
    _TICKET_FONT_SIZE = 7.0             # matches original PDF
    _DNI_FONT_SIZE = 12.0             # same size as ticket body

    def __init__(
        self,
        input_path: str,
        output_path: str,
        date1: datetime.date,
        time1: datetime.time,
        time2: datetime.time,
        dni: str,
        signature,
    ) -> None:
        self.input_path = input_path
        self.output_path = output_path

        self.date1 = date1.strftime("%d . %m . %Y")
        self.time1 = time1.strftime("%H : %M : %S")
        self.date2 = self.date1
        self.time2 = time2.strftime("%H : %M : %S")
        self.dni = dni

        # fallback
        self._ticket_font_name: str = "Helvetica"
        # fallback
        self._handwrite_font_name: str = "Helvetica-Oblique"

    def fill(self) -> None:
        """
        Fill the ticket and write the output PDF.

        Args:
            date1: New date for testo 320 block   (e.g. "15.01.2026")
            time1: New time for testo 320 block   (e.g. "08:45:00")
            date2: New date for testo 315-4 block (e.g. "15.01.2026")
            time2: New time for testo 315-4 block (e.g. "08:44:00")
            dni:   Text to write above "testo 315-4" in handwriting style
        """
        self._resolve_fonts()

        reader = PdfReader(self.input_path)
        page = reader.pages[0]

        overlay_bytes = self._build_overlay(
            self.date1, self.time1, self.date2, self.time2, self.dni)
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
    # Font resolution
    # ------------------------------------------------------------------

    def _resolve_fonts(self) -> None:
        """Find and register both the ticket body font and handwriting font."""
        ticket_path = self._find_font(_TICKET_FONT_CANDIDATES)
        handwrite_path = self._find_font(_HANDWRITE_CANDIDATES)

        if ticket_path:
            pdfmetrics.registerFont(
                TTFont(self._TICKET_FONT_NAME, ticket_path))
            self._ticket_font_name = self._TICKET_FONT_NAME
            logging.info(f"Ticket font   : {os.path.basename(ticket_path)}")
        else:
            logging.info(
                "Ticket font   : not found — using Helvetica fallback")

        if handwrite_path:
            pdfmetrics.registerFont(
                TTFont(self._HANDWRITE_FONT_NAME, handwrite_path))
            self._handwrite_font_name = self._HANDWRITE_FONT_NAME
            logging.info(f"Handwrite font: {os.path.basename(handwrite_path)}")
        else:
            logging.info(
                "Handwrite font: not found — using Helvetica-Oblique fallback")

    @staticmethod
    def _find_font(candidates: list[str]) -> str | None:
        """Search OS font directories for the first matching candidate filename."""
        system = platform.system()
        if system == "Darwin":
            search_dirs = ["/Library/Fonts", "/System/Library/Fonts",
                           os.path.expanduser("~/Library/Fonts")]
        elif system == "Windows":
            search_dirs = [r"C:\Windows\Fonts"]
        else:
            search_dirs = ["/usr/share/fonts", "/usr/local/share/fonts",
                           os.path.expanduser("~/.fonts")]

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
    ) -> bytes:
        """
        Build a transparent ReportLab overlay that:
          1. Erases each original date/time with a white rectangle
          2. Redraws the new value in the ticket body font (black, 7pt)
          3. Writes the DNI above "testo 315-4" in handwriting style
        """
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

            # --- DNI annotation ---
            if dni:
                c.setFont(self._handwrite_font_name, self._DNI_FONT_SIZE)
                c.setFillColorRGB(0.05, 0.05, 0.6)   # dark-blue ink
                c.drawString(_DNI["x0"], _DNI["y_baseline"], dni)

            c.save()
            return buf.getvalue()

    @staticmethod
    def _erase(c: canvas.Canvas, zone: dict) -> None:
        """Cover the original text with a white rectangle."""
        c.setFillColor(white)
        c.setStrokeColor(white)
        c.rect(
            zone["x0"], zone["erase_y0"],
            zone["x1"] - zone["x0"],
            zone["erase_y1"] - zone["erase_y0"],
            fill=1, stroke=0,
        )

    def _draw_ticket_text(self, c: canvas.Canvas, text: str, zone: dict) -> None:
        """Draw replacement text matching the original ticket style (black, 7pt)."""
        c.setFillColorRGB(0.0, 0.0, 0.0)
        c.setFont(self._ticket_font_name, self._TICKET_FONT_SIZE)
        baseline = zone["erase_y0"] + 2.0
        c.drawString(zone["x0"], baseline, text)
