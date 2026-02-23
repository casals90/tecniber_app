import glob
import os
import platform

from settings import FONT_CANDIDATES


def find_handwriting_font() -> str | None:
    """
    Search common system font directories for a handwriting-style TTF.

    Returns:
        The absolute path to the first matching font file, or ``None`` when
        no candidate is found on the current platform.
    """
    system = platform.system()
    if system == "Darwin":
        search_dirs = [
            "/Library/Fonts",
            "/System/Library/Fonts",
            os.path.expanduser("~/Library/Fonts"),
        ]
    elif system == "Windows":
        search_dirs = [r"C:\Windows\Fonts"]
    else:
        search_dirs = [
            "/usr/share/fonts",
            "/usr/local/share/fonts",
            os.path.expanduser("~/.fonts"),
        ]

    for name in FONT_CANDIDATES:
        for directory in search_dirs:
            matches = glob.glob(os.path.join(
                directory, "**", name), recursive=True)
            if matches:
                return matches[0]

    return None


def text_y_center(y0: float, y1: float, font_size: float) -> float:
    """
    Compute the baseline y-coordinate to vertically centre text in a field.

    Args:
        y0: Bottom edge of the field rectangle (PDF points).
        y1: Top edge of the field rectangle (PDF points).
        font_size: Font size in points.

    Returns:
        The y baseline position for ``canvas.drawString``.
    """
    return y0 + (y1 - y0 - font_size) / 2 + 1
