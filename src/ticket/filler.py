import glob
import io
import logging
import os
import platform
import random
from datetime import datetime, time, timedelta

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
    """
    Fills date/time fields and adds a DNI and signature annotation to a 
    ticket PDF.

    This class handles font resolution for both standard and handwritten 
    styles, processes an image-based signature to remove its background, 
    creates a transparent PDF overlay to mask old data and write new data, and 
    merges the overlay onto the original ticket PDF.
    """
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
        """
        Initializes the TicketFiller with file paths, replacement data, and an 
        optional signature.

        Args:
            input_path (str): Path to the original testo ticket PDF template.
            output_path (str): Destination path for the modified PDF.
            date1 (datetime.date): The new date to apply to both the testo 
                320 and 315-4 blocks.
            time1 (datetime.time): The new time for the testo 320 block.
            time2 (datetime.time): The new time for the testo 315-4 block.
            dni (str): The DNI string to write in a handwriting style.
            signature (Image.Image | None, optional): A PIL Image representing 
                the user's signature. Defaults to None.
        """
        self.input_path = input_path
        self.output_path = output_path

        self.time1, self.time2 = self._clean_times(time1, time2)

        self.date1 = date1.strftime("%d . %m . %Y")
        self.date2 = self.date1

        self.dni = dni
        self.signature = signature

        self._ticket_font_name: str = "Helvetica"
        self._handwrite_font_name: str = "Helvetica-Oblique"

    def fill(self) -> None:
        """
        Executes the PDF filling process and writes the output file.

        Resolves required fonts, reads the input PDF, generates a transparent 
        overlay containing the whiteout boxes, new text, and signature, merges 
        this overlay onto the first page of the PDF, and saves the final 
        document.
        """
        self._resolve_fonts()

        reader = PdfReader(self.input_path)
        page = reader.pages[0]

        overlay_bytes = self._build_overlay(
            self.date1, self.time1, self.date2, self.time2,
            self.dni, self.signature)

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
    def _clean_times(
            time1: datetime.time, time2: datetime.time) -> tuple[str, str]:
        # Convert times to total seconds from midnight to do math
        t1_sec = time1.hour * 3600 + time1.minute * 60 + time1.second
        t2_sec = time2.hour * 3600 + time2.minute * 60 + time2.second

        # Find the midpoint and +/- 30 seconds to ensure new_time1
        # doesn't always end in :00 or :30
        mid_sec = ((t1_sec + t2_sec) // 2) + random.randint(-30, 30)
        new_time1_dt = datetime.combine(
            datetime.today(), time(0)) + timedelta(seconds=mid_sec)

        # Add random offset (3 to 5 minutes, including random seconds)
        # 3 minutes = 180s, 5 minutes = 300s
        random_offset = random.randint(180, 300)
        new_time2_dt = new_time1_dt + timedelta(seconds=random_offset)

        # Format to "HH : MM : SS"
        fmt = "%H : %M : %S"
        return new_time1_dt.strftime(fmt), new_time2_dt.strftime(fmt)

    @staticmethod
    def _clean_signature(img: Image.Image) -> Image.Image:
        """
        Processes a signature image by removing its background and cropping it 
        tightly.

        Converts light-colored pixels (typically the Streamlit 
        canvas background) to transparent pixels, turns the drawn strokes into 
        dark blue ink, and crops the image to the bounding box of the actual 
        signature strokes.

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
        """
        Finds and registers both the ticket body font and the handwriting font.

        Searches the system directories for matching fonts. If found, they are 
        registered with ReportLab. If not, it falls back to standard built-in 
        PDF fonts (Helvetica and Helvetica-Oblique).
        """
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
        """
        Searches OS-specific font directories for the first matching candidate 
        filename.

        Args:
            candidates (list[str]): A list of font filenames 
            (e.g., "Arial.ttf") to search for.

        Returns:
            str | None: The absolute path to the first found font file, or 
            None if no match is found.
        """
        system = platform.system()
        if system == "Darwin":
            search_dirs = ["/Library/Fonts", "/System/Library/Fonts",
                           os.path.expanduser("~/Library/Fonts")]
        elif system == "Windows":
            search_dirs = [r"C:\Windows\Fonts"]
        else:
            search_dirs = [
                "/usr/share/fonts",
                "/usr/local/share/fonts",
                os.path.expanduser("~/.fonts")
            ]

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
        """
        Builds a transparent ReportLab overlay for the ticket modifications.

        This overlay performs three actions:
        1. Erases the original dates and times with white rectangles.
        2. Redraws the new dates and times in the ticket body font.
        3. Draws the DNI text and user signature image in their designated 
        zones.

        Args:
            date1 (str): Formatted date string for the first block.
            time1 (str): Formatted time string for the first block.
            date2 (str): Formatted date string for the second block.
            time2 (str): Formatted time string for the second block.
            dni (str): The DNI string to write.
            signature (Image.Image | None): The user's signature image 
                to overlay.

        Returns:
            bytes: Raw bytes of a single-page PDF containing the modifications.
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
        """
        Covers a specific rectangular area on the canvas with a solid 
        white box.

        Args:
            c (canvas.Canvas): The ReportLab canvas being drawn on.
            zone (dict): A dictionary defining the bounding box with 
                keys 'x0', 'x1', 'erase_y0', and 'erase_y1'.
        """
        c.setFillColor(white)
        c.setStrokeColor(white)
        c.rect(
            zone["x0"], zone["erase_y0"],
            zone["x1"] - zone["x0"],
            zone["erase_y1"] - zone["erase_y0"],
            fill=1, stroke=0,
        )

    def _draw_ticket_text(
            self, c: canvas.Canvas, text: str, zone: dict) -> None:
        """
        Draws replacement text on the canvas matching the original ticket 
        style.

        Args:
            c (canvas.Canvas): The ReportLab canvas being drawn on.
            text (str): The text string to draw.
            zone (dict): A dictionary defining the placement area, 
                using 'x0' for the left-alignment and 'erase_y0' to calculate 
                the baseline.
        """
        c.setFillColorRGB(0.0, 0.0, 0.0)
        c.setFont(self._ticket_font_name, self._TICKET_FONT_SIZE)
        baseline = zone["erase_y0"] + 2.0
        c.drawString(zone["x0"], baseline, text)
