from django.test import TestCase

from .flowbite_fields import FlowbiteImageDropzoneField
from .flowbite_widgets import FlowbiteImageDropzone


class FlowbiteImageDropzoneCompressTests(TestCase):
    """FlowbiteImageDropzoneField.compress() combines the [file, url] subfield
    values submitted by the MultiWidget into the single (file, url) tuple
    stored as the field's cleaned value."""

    def setUp(self):
        self.field = FlowbiteImageDropzoneField()

    def test_compress_empty_list_returns_none(self):
        self.assertIsNone(self.field.compress([]))

    def test_compress_none_returns_none(self):
        self.assertIsNone(self.field.compress(None))

    def test_compress_file_only(self):
        file_stub = object()
        self.assertEqual(self.field.compress([file_stub, '']), (file_stub, None))

    def test_compress_url_only(self):
        self.assertEqual(
            self.field.compress(['', 'https://example.com/x.jpg']),
            (None, 'https://example.com/x.jpg'),
        )

    def test_compress_neither_provided(self):
        # Non-empty subfield list, but both values falsy -> normalized to (None, None),
        # distinct from compress([]) which short-circuits to bare None.
        self.assertEqual(self.field.compress([None, None]), (None, None))


class FlowbiteImageDropzoneDecompressTests(TestCase):
    """FlowbiteImageDropzone.decompress() rehydrates a stored (file, url) value
    back into the [file, url] list the MultiWidget renders its two subwidgets
    from -- must never raise, even for missing/malformed input."""

    def setUp(self):
        self.widget = FlowbiteImageDropzone()

    def test_decompress_none_returns_default(self):
        self.assertEqual(self.widget.decompress(None), [None, None])

    def test_decompress_empty_string_returns_default(self):
        self.assertEqual(self.widget.decompress(''), [None, None])

    def test_decompress_malformed_value_returns_default(self):
        # Not a 2-length tuple/list -> safe default, no raise.
        self.assertEqual(self.widget.decompress(('only-one',)), [None, None])

    def test_decompress_two_tuple_returns_list(self):
        self.assertEqual(self.widget.decompress(('a', 'b')), ['a', 'b'])


class FlowbiteImageDropzoneRoundTripTests(TestCase):
    """compress() then decompress() must reproduce the original subfield
    values -- this is what makes a bound form re-render its previous value
    correctly after a validation error or on an edit page."""

    def setUp(self):
        self.field = FlowbiteImageDropzoneField()
        self.widget = FlowbiteImageDropzone()

    def test_round_trip_file_only(self):
        file_stub = object()
        compressed = self.field.compress([file_stub, ''])
        self.assertEqual(self.widget.decompress(compressed), [file_stub, None])

    def test_round_trip_url_only(self):
        compressed = self.field.compress(['', 'https://example.com/x.jpg'])
        self.assertEqual(
            self.widget.decompress(compressed),
            [None, 'https://example.com/x.jpg'],
        )

    def test_round_trip_empty_input_matches_decompress_default(self):
        compressed = self.field.compress([])
        self.assertIsNone(compressed)
        self.assertEqual(self.widget.decompress(compressed), [None, None])
