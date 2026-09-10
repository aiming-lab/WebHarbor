"""Small offline HTTP fixtures; no bulk downloads are performed by these tests."""
from io import BytesIO
import importlib.util
import os
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import MagicMock, patch
from urllib.error import HTTPError

from PIL import Image


class SourceImageTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        source = Path(os.environ.get('ROTTEN_TOMATOES_SOURCE', Path(__file__).resolve().parents[1]))
        sys.path.insert(0, str(source))
        cls.addClassCleanup(sys.path.remove, str(source))
        spec = importlib.util.spec_from_file_location('_source_image_downloads', source / 'download_source_images.py')
        cls.module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(cls.module)

    def test_exact_verified_url_and_decoded_image(self):
        observed = 'https://images.example.test/card.jpg?signature=unchanged'
        verified = 'https://images.example.test/original.jpg?signature=exact'
        buffer = BytesIO()
        Image.new('RGB', (12, 18), 'white').save(buffer, 'PNG')
        response = MagicMock()
        response.__enter__.return_value = response
        response.read.return_value = buffer.getvalue()
        response.url = verified
        catalog = {'persons': [{'slug': 'source-person', 'photo_url': observed, 'photo_download_url': verified}]}
        with tempfile.TemporaryDirectory() as directory:
            with patch.object(self.module, 'urlopen', return_value=response) as request:
                result = self.module.download_images(catalog, 'people', directory)
            self.assertEqual(request.call_args.args[0].full_url, verified)
            self.assertEqual(result['counts'], {'SUCCESS': 1})
            with Image.open(Path(directory) / 'source-person.jpg') as image:
                self.assertEqual((image.format, image.size), ('JPEG', (12, 18)))

    def test_failure_does_not_claim_an_old_file_and_unknown_does_not_fetch(self):
        url = 'https://images.example.test/exact.jpg'
        catalog = {'movies': [{'slug': 'failed', 'poster_url': url}, {'slug': 'unknown', 'poster_url': None}]}
        with tempfile.TemporaryDirectory() as directory:
            existing = Path(directory) / 'failed.jpg'
            existing.write_bytes(b'untrusted-old-file')
            with patch.object(self.module, 'urlopen', side_effect=HTTPError(url, 404, 'missing', {}, None)) as request:
                result = self.module.download_images(catalog, 'posters', directory)
            self.assertEqual(request.call_count, 1)
            self.assertEqual(result['counts'], {'FAILED': 1, 'NOT_VERIFIED': 1})
            self.assertEqual(existing.read_bytes(), b'untrusted-old-file')
            self.assertFalse((Path(directory) / 'unknown.jpg').exists())

    def test_cli_returns_nonzero_for_a_failed_explicit_url(self):
        url = 'https://images.example.test/missing.jpg'
        catalog = {'persons': [{'slug': 'missing-person', 'photo_url': url}]}
        with tempfile.TemporaryDirectory() as directory:
            with patch.object(self.module, 'load_catalog', return_value=catalog):
                with patch.object(self.module, 'urlopen', side_effect=HTTPError(url, 404, 'missing', {}, None)):
                    with patch.object(sys, 'argv', ['download_people.py', '--output-dir', directory]):
                        with patch('builtins.print'):
                            self.assertEqual(self.module.main('people'), 1)


if __name__ == '__main__':
    unittest.main()
