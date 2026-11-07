"""Bounded, decoder-independent artwork fetches without contacting the CDN."""
from importlib.util import module_from_spec, spec_from_file_location
from pathlib import Path
import subprocess
import tempfile
import unittest
from unittest.mock import patch

from PIL import Image

SPEC = spec_from_file_location('artwork', Path(__file__).resolve().parents[1] / 'shell/services/fetch-artwork.py')
artwork = module_from_spec(SPEC)
SPEC.loader.exec_module(artwork)


class ArtworkTests(unittest.TestCase):
    def test_webp_cover_becomes_png_and_url_cache_avoids_repeat_network(self):
        with tempfile.TemporaryDirectory() as temporary:
            cache = Path(temporary) / 'cache'
            def download(args, **kwargs):
                self.assertIn('--retry-all-errors', args)
                self.assertLessEqual(kwargs['timeout'], 20)
                destination = Path(args[args.index('--output') + 1])
                Image.new('RGB', (1200, 900), '#8dbabe').save(destination, 'WEBP')
                return subprocess.CompletedProcess(args, 0)
            with patch.object(artwork.subprocess, 'run', side_effect=download) as request:
                url = 'https://i.scdn.co/image/fixture'
                first = artwork.fetch(url, cache)
                second = artwork.fetch(url, cache)
                self.assertEqual(first, second)
                self.assertEqual(request.call_count, 1)
            with Image.open(next(cache.glob('*.png'))) as result:
                self.assertEqual(result.format, 'PNG')
                self.assertEqual(result.size, (768, 576))
            self.assertEqual(next(cache.glob('*.png')).stat().st_mode & 0o777, 0o600)

    def test_download_errors_and_non_images_are_not_cached(self):
        with tempfile.TemporaryDirectory() as temporary:
            cache = Path(temporary)
            with patch.object(artwork.subprocess, 'run', return_value=subprocess.CompletedProcess([], 22)):
                with self.assertRaises(ValueError):
                    artwork.fetch('https://i.scdn.co/image/fixture', cache)
            self.assertEqual(list(cache.iterdir()), [])

    def test_corrupt_cached_cover_is_replaced(self):
        with tempfile.TemporaryDirectory() as temporary:
            cache = Path(temporary)
            url = 'https://i.scdn.co/image/fixture'
            target = cache / (artwork.hashlib.sha256(url.encode()).hexdigest() + '.png')
            target.write_bytes(b'broken')
            def download(args, **kwargs):
                Image.new('RGB', (32, 32)).save(Path(args[args.index('--output') + 1]), 'JPEG')
                return subprocess.CompletedProcess(args, 0)
            with patch.object(artwork.subprocess, 'run', side_effect=download) as request:
                self.assertEqual(artwork.fetch(url, cache), target.as_uri())
                self.assertEqual(request.call_count, 1)
            with Image.open(target) as image:
                image.verify()

    def test_local_paths_credentials_and_non_http_schemes_are_rejected(self):
        with tempfile.TemporaryDirectory() as temporary:
            for url in ['file:///etc/passwd', 'ftp://example.com/art', 'https://user:pass@example.com/art', '/tmp/art']:
                with self.subTest(url=url), self.assertRaises(ValueError):
                    artwork.fetch(url, Path(temporary))


if __name__ == '__main__':
    unittest.main()
