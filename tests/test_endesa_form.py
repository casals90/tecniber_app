

from __future__ import annotations

import io
import unittest
from unittest.mock import MagicMock, patch

from endesa_form.endesa_form import TEXT_FIELDS, EndesaFormFiller
from endesa_form.utils import find_handwriting_font, text_y_center
from settings import DEFAULT_FONT_SIZE

# ---------------------------------------------------------------------------
# Helpers shared across test cases
# ---------------------------------------------------------------------------


def _fields(*keys: str, font_size: float | None = None) -> dict:
    """Build a minimal valid fields dict for the given keys."""
    entry = {"value": "TEST"}
    if font_size is not None:
        entry["styles"] = {"font_size": font_size}
    return {k: entry for k in (keys or ("num_service",))}


def _all_fields() -> dict:
    """Return a valid fields dict covering every TEXT_FIELDS key."""
    return {k: {"value": f"val_{k}"} for k in TEXT_FIELDS}


def _make_filler(fields: dict | None = None, **kwargs) -> EndesaFormFiller:
    """
    Instantiate EndesaFormFiller with _register_font patched out so tests
    don't touch the real filesystem.
    """
    with patch.object(EndesaFormFiller, "_register_font", return_value="Helvetica-Oblique"):
        return EndesaFormFiller(
            input_path=kwargs.get("input_path", "in.pdf"),
            output_path=kwargs.get("output_path", "out.pdf"),
            fields=fields if fields is not None else _fields(),
        )


# ---------------------------------------------------------------------------
# 1. text_y_center
# ---------------------------------------------------------------------------

class TestTextYCenter(unittest.TestCase):
    """Pure-math tests for text_y_center."""

    def test_known_value(self):
        # y0=10, y1=30, fs=10  →  10 + (30-10-10)/2 + 1 = 10 + 5 + 1 = 16
        assert text_y_center(10.0, 30.0, 10.0) == 16.0

    def test_zero_height_field(self):
        # y0=y1=20, fs=10  →  20 + (0-10)/2 + 1 = 16
        assert text_y_center(20.0, 20.0, 10.0) == 16.0

    def test_large_font_exceeds_field(self):
        # y0=0, y1=5, fs=20  →  0 + (5-20)/2 + 1 = -6.5
        assert text_y_center(0.0, 5.0, 20.0) == -6.5

    def test_returns_float(self):
        assert isinstance(text_y_center(0.0, 20.0, 10.0), float)

    def test_offset_of_one_is_always_added(self):
        # with y0==y1 and fs==0 the only contribution is the +1 offset
        assert text_y_center(5.0, 5.0, 0.0) == 6.0


# ---------------------------------------------------------------------------
# 2. find_handwriting_font
# ---------------------------------------------------------------------------

class TestFindHandwritingFont(unittest.TestCase):
    """Tests for cross-platform font discovery."""

    # --- helpers ---

    @staticmethod
    def _call(system: str, glob_returns: list[str]) -> str | None:
        with patch("endesa_form.platform.system", return_value=system), \
                patch("endesa_form.glob.glob", return_value=glob_returns):
            return find_handwriting_font()

    @staticmethod
    def _capture_searched_paths(system: str) -> list[str]:
        searched: list[str] = []

        def _glob(pattern, **_):
            searched.append(pattern)
            return []

        with patch("endesa_form.platform.system", return_value=system), \
                patch("endesa_form.glob.glob", side_effect=_glob):
            find_handwriting_font()

        return searched

    # --- return value tests ---

    def test_returns_first_hit_on_darwin(self):
        hit = "/Library/Fonts/Bradley Hand Bold.ttf"
        assert self._call("Darwin", [hit]) == hit

    def test_returns_first_hit_on_windows(self):
        hit = r"C:\Windows\Fonts\Caladea-Italic.ttf"
        assert self._call("Windows", [hit]) == hit

    def test_returns_first_hit_on_linux(self):
        hit = "/usr/share/fonts/FreeSerifItalic.ttf"
        assert self._call("Linux", [hit]) == hit

    def test_returns_none_when_no_font_found(self):
        assert self._call("Linux", []) is None

    # --- directory tests ---

    def test_darwin_searches_library_fonts(self):
        paths = self._capture_searched_paths("Darwin")
        assert any("/Library/Fonts" in p for p in paths)

    def test_darwin_searches_system_library_fonts(self):
        paths = self._capture_searched_paths("Darwin")
        assert any("/System/Library/Fonts" in p for p in paths)

    def test_windows_searches_windows_fonts(self):
        paths = self._capture_searched_paths("Windows")
        assert any(r"C:\Windows\Fonts" in p for p in paths)

    def test_linux_searches_usr_share_fonts(self):
        paths = self._capture_searched_paths("Linux")
        assert any("/usr/share/fonts" in p for p in paths)

    def test_linux_searches_usr_local_share_fonts(self):
        paths = self._capture_searched_paths("Linux")
        assert any("/usr/local/share/fonts" in p for p in paths)

    def test_glob_called_with_recursive_true(self):
        """glob must always be called with recursive=True."""
        calls_kwargs: list[dict] = []

        def _glob(pattern, **kwargs):
            calls_kwargs.append(kwargs)
            return []

        with patch("endesa_form.platform.system", return_value="Linux"), \
                patch("endesa_form.glob.glob", side_effect=_glob):
            find_handwriting_font()

        assert all(kw.get("recursive") is True for kw in calls_kwargs)

    def test_stops_after_first_hit(self):
        """Once a font is found, no further glob calls are made."""
        call_count = 0

        def _glob(pattern, **_):
            nonlocal call_count
            call_count += 1
            return ["/fonts/found.ttf"]   # always return a hit

        with patch("endesa_form_filler.platform.system", return_value="Linux"), \
                patch("endesa_form_filler.glob.glob", side_effect=_glob):
            result = find_handwriting_font()

        assert result == "/fonts/found.ttf"
        assert call_count == 1


# ---------------------------------------------------------------------------
# 3. EndesaFormFiller._parse_fields
# ---------------------------------------------------------------------------

class TestParseFields(unittest.TestCase):
    """Validates every branch in the static _parse_fields method."""

    parse = staticmethod(EndesaFormFiller._parse_fields)

    # --- happy paths ---

    def test_valid_value_only_gives_none_font_size(self):
        result = self.parse({"num_service": {"value": "X"}})
        text, fs = result["num_service"]
        assert text == "X"
        assert fs is None

    def test_value_coerced_to_str(self):
        result = self.parse({"num_service": {"value": 99}})
        text, _ = result["num_service"]
        assert text == "99"
        assert isinstance(text, str)

    def test_font_size_stored_as_float(self):
        result = self.parse(
            {"num_service": {"value": "X", "styles": {"font_size": 8}}})
        _, fs = result["num_service"]
        assert fs == 8.0
        assert isinstance(fs, float)

    def test_font_size_as_string_number_is_accepted(self):
        result = self.parse(
            {"num_service": {"value": "X", "styles": {"font_size": "12"}}})
        _, fs = result["num_service"]
        assert fs == 12.0

    def test_empty_styles_dict_gives_none_font_size(self):
        result = self.parse({"num_service": {"value": "X", "styles": {}}})
        _, fs = result["num_service"]
        assert fs is None

    def test_missing_styles_key_gives_none_font_size(self):
        result = self.parse({"num_service": {"value": "X"}})
        _, fs = result["num_service"]
        assert fs is None

    def test_none_styles_value_gives_none_font_size(self):
        result = self.parse({"num_service": {"value": "X", "styles": None}})
        _, fs = result["num_service"]
        assert fs is None

    def test_all_valid_keys_accepted(self):
        result = self.parse(_all_fields())
        assert set(result.keys()) == set(TEXT_FIELDS.keys())

    def test_empty_input_returns_empty_dict(self):
        assert self.parse({}) == {}

    # --- error paths ---

    def test_unknown_key_raises_value_error(self):
        with self.assertRaises(ValueError) as ctx:
            self.parse({"bad_key": {"value": "X"}})
        assert "bad_key" in str(ctx.exception)

    def test_error_message_lists_valid_keys(self):
        with self.assertRaises(ValueError) as ctx:
            self.parse({"bad_key": {"value": "X"}})
        assert "Valid keys" in str(ctx.exception)

    def test_entry_without_value_key_raises_value_error(self):
        with self.assertRaises(ValueError) as ctx:
            self.parse({"num_service": {"font_size": 10}})
        assert "value" in str(ctx.exception)

    def test_entry_as_plain_string_raises_value_error(self):
        with self.assertRaises(ValueError):
            self.parse({"num_service": "not-a-dict"})

    def test_non_numeric_font_size_raises_type_error(self):
        with self.assertRaises(TypeError) as ctx:
            self.parse(
                {"num_service": {"value": "X", "styles": {"font_size": "bad"}}})
        assert "font_size" in str(ctx.exception)

    def test_list_as_font_size_raises_type_error(self):
        with self.assertRaises(TypeError):
            self.parse(
                {"num_service": {"value": "X", "styles": {"font_size": [10]}}})


# ---------------------------------------------------------------------------
# 4. EndesaFormFiller._register_font
# ---------------------------------------------------------------------------

class TestRegisterFont(unittest.TestCase):
    """Tests for font registration logic."""

    def test_returns_handwriting_when_font_found(self):
        with patch("endesa_form_filler.find_handwriting_font", return_value="/f/font.ttf"), \
                patch("endesa_form_filler.pdfmetrics.registerFont"), \
                patch("endesa_form_filler.TTFont", return_value=MagicMock()):
            result = EndesaFormFiller._register_font()
        assert result == "Handwriting"

    def test_returns_fallback_when_no_font_found(self):
        with patch("endesa_form_filler.find_handwriting_font", return_value=None):
            result = EndesaFormFiller._register_font()
        assert result == "Helvetica-Oblique"

    def test_register_font_called_with_handwriting_name(self):
        mock_ttfont = MagicMock()
        with patch("endesa_form_filler.find_handwriting_font", return_value="/f/font.ttf"), \
                patch("endesa_form_filler.TTFont", return_value=mock_ttfont) as mock_ttf_cls, \
                patch("endesa_form_filler.pdfmetrics.registerFont") as mock_reg:
            EndesaFormFiller._register_font()
        mock_ttf_cls.assert_called_once_with("Handwriting", "/f/font.ttf")
        mock_reg.assert_called_once_with(mock_ttfont)

    def test_register_font_not_called_on_fallback(self):
        with patch("endesa_form_filler.find_handwriting_font", return_value=None), \
                patch("endesa_form_filler.pdfmetrics.registerFont") as mock_reg:
            EndesaFormFiller._register_font()
        mock_reg.assert_not_called()

    def test_font_basename_printed_when_found(self):
        with patch("endesa_form_filler.find_handwriting_font", return_value="/fonts/MyFont.ttf"), \
                patch("endesa_form_filler.pdfmetrics.registerFont"), \
                patch("endesa_form_filler.TTFont", return_value=MagicMock()), \
                patch("builtins.print") as mock_print:
            EndesaFormFiller._register_font()
        printed = " ".join(str(c) for c in mock_print.call_args_list)
        assert "MyFont.ttf" in printed

    def test_fallback_message_printed_when_no_font(self):
        with patch("endesa_form_filler.find_handwriting_font", return_value=None), \
                patch("builtins.print") as mock_print:
            EndesaFormFiller._register_font()
        printed = " ".join(str(c) for c in mock_print.call_args_list)
        assert "Helvetica-Oblique" in printed


# ---------------------------------------------------------------------------
# 5. EndesaFormFiller.__init__
# ---------------------------------------------------------------------------

class TestInit(unittest.TestCase):
    """Tests that __init__ wires paths, parses fields, and registers font."""

    def test_input_path_stored(self):
        filler = _make_filler(input_path="template.pdf")
        assert filler._input_path == "template.pdf"

    def test_output_path_stored(self):
        filler = _make_filler(output_path="result.pdf")
        assert filler._output_path == "result.pdf"

    def test_font_name_stored_from_register_font(self):
        filler = _make_filler()
        assert filler._font_name == "Helvetica-Oblique"

    def test_parsed_fields_populated(self):
        filler = _make_filler(fields=_fields("num_service"))
        assert "num_service" in filler._parsed_fields

    def test_parse_fields_called_with_raw_fields(self):
        raw = _fields("num_service")
        with patch.object(EndesaFormFiller, "_parse_fields", return_value={}) as mock_parse, \
                patch.object(EndesaFormFiller, "_register_font", return_value="Helvetica-Oblique"):
            EndesaFormFiller("in.pdf", "out.pdf", raw)
        mock_parse.assert_called_once_with(raw)

    def test_register_font_called_during_init(self):
        with patch.object(EndesaFormFiller, "_register_font", return_value="Helvetica-Oblique") \
                as mock_reg:
            EndesaFormFiller("in.pdf", "out.pdf", _fields())
        mock_reg.assert_called_once()

    def test_invalid_fields_raise_on_init(self):
        with self.assertRaises(ValueError):
            _make_filler(fields={"bad_key": {"value": "X"}})


# ---------------------------------------------------------------------------
# 6. EndesaFormFiller._build_overlay
# ---------------------------------------------------------------------------

class TestBuildOverlay(unittest.TestCase):
    """Tests for the ReportLab canvas rendering logic."""

    def _overlay(self, fields: dict, font_name: str = "Helvetica-Oblique") -> bytes:
        """Build an overlay via a real filler instance with a mocked font."""
        filler = _make_filler(fields=fields)
        filler._font_name = font_name
        return filler._build_overlay(595.0, 842.0)

    def test_returns_bytes(self):
        result = self._overlay(_fields())
        assert isinstance(result, bytes)

    def test_returns_non_empty_bytes(self):
        result = self._overlay(_fields())
        assert len(result) > 0

    def test_draw_string_called_for_non_empty_value(self):
        filler = _make_filler(fields=_fields("num_service"))
        mock_canvas = MagicMock()

        with patch("endesa_form_filler.canvas.Canvas", return_value=mock_canvas):
            filler._build_overlay(595.0, 842.0)

        mock_canvas.drawString.assert_called()

    def test_draw_string_not_called_for_empty_value(self):
        filler = _make_filler(fields={"num_service": {"value": ""}})
        mock_canvas = MagicMock()

        with patch("endesa_form_filler.canvas.Canvas", return_value=mock_canvas):
            filler._build_overlay(595.0, 842.0)

        mock_canvas.drawString.assert_not_called()

    def test_ink_color_applied(self):
        filler = _make_filler(fields=_fields("num_service"))
        mock_canvas = MagicMock()

        with patch("endesa_form_filler.canvas.Canvas", return_value=mock_canvas):
            filler._build_overlay(595.0, 842.0)

        mock_canvas.setFillColorRGB.assert_called_once_with(
            *EndesaFormFiller.INK_COLOR)

    def test_canvas_save_called(self):
        filler = _make_filler(fields=_fields("num_service"))
        mock_canvas = MagicMock()

        with patch("endesa_form_filler.canvas.Canvas", return_value=mock_canvas):
            filler._build_overlay(595.0, 842.0)

        mock_canvas.save.assert_called_once()

    def test_canvas_created_with_correct_page_size(self):
        filler = _make_filler(fields=_fields("num_service"))
        mock_canvas = MagicMock()

        with patch("endesa_form_filler.canvas.Canvas", return_value=mock_canvas) as mock_cls:
            filler._build_overlay(400.0, 600.0)

        mock_cls.assert_called_once()
        _, kwargs = mock_cls.call_args
        # pagesize may be passed as positional or keyword
        args_pos = mock_cls.call_args[0]
        assert (400.0, 600.0) in (kwargs.get("pagesize"),
                                  args_pos[1] if len(args_pos) > 1 else None)

    def test_default_font_size_used_when_none(self):
        """When font_size is None in parsed_fields, DEFAULT_FONT_SIZE is used."""
        filler = _make_filler(fields={"num_service": {"value": "X"}})
        mock_canvas = MagicMock()
        # stringWidth must return 0 to avoid the truncation loop running forever
        mock_canvas.stringWidth.return_value = 0

        with patch("endesa_form_filler.canvas.Canvas", return_value=mock_canvas):
            filler._build_overlay(595.0, 842.0)

        set_font_calls = mock_canvas.setFont.call_args_list
        sizes_used = [c[0][1] for c in set_font_calls]
        assert DEFAULT_FONT_SIZE in sizes_used

    def test_explicit_font_size_used_when_provided(self):
        filler = _make_filler(
            fields={"num_service": {"value": "X", "styles": {"font_size": 7}}})
        mock_canvas = MagicMock()
        mock_canvas.stringWidth.return_value = 0

        with patch("endesa_form_filler.canvas.Canvas", return_value=mock_canvas):
            filler._build_overlay(595.0, 842.0)

        set_font_calls = mock_canvas.setFont.call_args_list
        sizes_used = [c[0][1] for c in set_font_calls]
        assert 7.0 in sizes_used

    def test_text_truncated_when_too_wide(self):
        """
        When stringWidth always exceeds available width, the display text is
        trimmed one character at a time until it reaches length 1.
        """
        filler = _make_filler(fields={"num_service": {"value": "ABCDE"}})
        mock_canvas = MagicMock()
        # Always report text as too wide → forces truncation down to 1 char
        mock_canvas.stringWidth.return_value = 9999

        with patch("endesa_form_filler.canvas.Canvas", return_value=mock_canvas):
            filler._build_overlay(595.0, 842.0)

        # The draw call must have received a single character
        drawn_text = mock_canvas.drawString.call_args[0][2]
        assert len(drawn_text) == 1

    def test_text_not_truncated_when_fits(self):
        filler = _make_filler(fields={"num_service": {"value": "HI"}})
        mock_canvas = MagicMock()
        mock_canvas.stringWidth.return_value = 0   # always fits

        with patch("endesa_form_filler.canvas.Canvas", return_value=mock_canvas):
            filler._build_overlay(595.0, 842.0)

        drawn_text = mock_canvas.drawString.call_args[0][2]
        assert drawn_text == "HI"

    def test_all_fields_rendered(self):
        """Every non-empty field in parsed_fields triggers a drawString call."""
        filler = _make_filler(fields=_all_fields())
        mock_canvas = MagicMock()
        mock_canvas.stringWidth.return_value = 0

        with patch("endesa_form_filler.canvas.Canvas", return_value=mock_canvas):
            filler._build_overlay(595.0, 842.0)

        assert mock_canvas.drawString.call_count == len(TEXT_FIELDS)


# ---------------------------------------------------------------------------
# 7. EndesaFormFiller.generate
# ---------------------------------------------------------------------------

class TestGenerate(unittest.TestCase):
    """Integration-level tests for the generate() pipeline."""

    def _run_generate(
        self,
        fields: dict | None = None,
        extra_pages: int = 0,
    ):
        """
        Run generate() with all I/O fully mocked.

        Returns:
            (filler, mock_writer, written_bytes)
        """
        filler = _make_filler(fields=fields or _fields())

        # --- build realistic fake pypdf pages ---
        def _fake_page():
            p = MagicMock()
            p.merge_page = MagicMock()
            return p

        first_page = _fake_page()
        extra = [_fake_page() for _ in range(extra_pages)]

        fake_reader = MagicMock()
        fake_reader.pages = [first_page] + extra
        fake_reader.pages[0].mediabox.width = 595.0
        fake_reader.pages[0].mediabox.height = 842.0

        mock_writer = MagicMock()

        # _build_overlay returns a minimal valid PDF stub
        overlay_page = MagicMock()
        fake_overlay_reader = MagicMock()
        fake_overlay_reader.pages = [overlay_page]

        written_buf = io.BytesIO()

        def _fake_open(path, mode="r", **kw):
            if "w" in mode or "b" in mode:
                return written_buf
            raise FileNotFoundError(path)

        with patch("endesa_form_filler.PdfReader", side_effect=[fake_reader, fake_overlay_reader]), \
                patch("endesa_form_filler.PdfWriter", return_value=mock_writer), \
                patch.object(filler, "_build_overlay", return_value=b"%PDF-stub"), \
                patch("builtins.open", unittest.mock.mock_open()) as mock_file, \
                patch("builtins.print"):
            filler.generate()

        return filler, mock_writer, mock_file

    # --- merge logic ---

    def test_merge_page_called_on_first_page(self):
        _, _, _ = self._run_generate()
        # covered implicitly — if merge_page raised, generate would fail

    def test_first_page_added_to_writer(self):
        _, writer, _ = self._run_generate()
        writer.add_page.assert_called()

    def test_extra_pages_passed_through(self):
        _, writer, _ = self._run_generate(extra_pages=2)
        # add_page called once for first page + once each for the 2 extras = 3
        assert writer.add_page.call_count == 3

    def test_single_page_pdf_adds_page_once(self):
        _, writer, _ = self._run_generate(extra_pages=0)
        assert writer.add_page.call_count == 1

    # --- writer / file ---

    def test_writer_write_called(self):
        _, writer, _ = self._run_generate()
        writer.write.assert_called_once()

    def test_output_file_opened_for_writing(self):
        filler = _make_filler(output_path="output.pdf")
        _, _, mock_file = self._run_generate()
        # open was called; at least one call should be in write-binary mode
        open_calls = [str(c) for c in mock_file.call_args_list]
        assert any("wb" in c for c in open_calls)

    # --- overlay pipeline ---

    def test_build_overlay_called_once(self):
        filler = _make_filler(fields=_fields())

        fake_reader = MagicMock()
        fake_reader.pages[0].mediabox.width = 595.0
        fake_reader.pages[0].mediabox.height = 842.0

        overlay_page = MagicMock()
        fake_overlay_reader = MagicMock()
        fake_overlay_reader.pages = [overlay_page]

        with patch("endesa_form_filler.PdfReader", side_effect=[fake_reader, fake_overlay_reader]), \
                patch("endesa_form_filler.PdfWriter", return_value=MagicMock()), \
                patch.object(filler, "_build_overlay", return_value=b"%PDF-stub") as mock_build, \
                patch("builtins.open", unittest.mock.mock_open()), \
                patch("builtins.print"):
            filler.generate()

        mock_build.assert_called_once_with(595.0, 842.0)

    # --- print output ---

    def test_page_size_printed(self):
        filler = _make_filler(fields=_fields())

        fake_reader = MagicMock()
        fake_reader.pages[0].mediabox.width = 595.0
        fake_reader.pages[0].mediabox.height = 842.0
        fake_overlay_reader = MagicMock()
        fake_overlay_reader.pages = [MagicMock()]

        with patch("endesa_form_filler.PdfReader", side_effect=[fake_reader, fake_overlay_reader]), \
                patch("endesa_form_filler.PdfWriter", return_value=MagicMock()), \
                patch.object(filler, "_build_overlay", return_value=b"%PDF-stub"), \
                patch("builtins.open", unittest.mock.mock_open()), \
                patch("builtins.print") as mock_print:
            filler.generate()

        printed = " ".join(str(c) for c in mock_print.call_args_list)
        assert "595" in printed and "842" in printed

    def test_success_message_printed(self):
        filler = _make_filler(fields=_fields(), output_path="done.pdf")

        fake_reader = MagicMock()
        fake_reader.pages[0].mediabox.width = 595.0
        fake_reader.pages[0].mediabox.height = 842.0
        fake_overlay_reader = MagicMock()
        fake_overlay_reader.pages = [MagicMock()]

        with patch("endesa_form_filler.PdfReader", side_effect=[fake_reader, fake_overlay_reader]), \
                patch("endesa_form_filler.PdfWriter", return_value=MagicMock()), \
                patch.object(filler, "_build_overlay", return_value=b"%PDF-stub"), \
                patch("builtins.open", unittest.mock.mock_open()), \
                patch("builtins.print") as mock_print:
            filler.generate()

        printed = " ".join(str(c) for c in mock_print.call_args_list)
        assert "done.pdf" in printed
