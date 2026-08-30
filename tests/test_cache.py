import tempfile
import unittest
from pathlib import Path

from repo_scout.cache import FileCache


class CacheTests(unittest.TestCase):
    def test_get_set_round_trip(self):
        with tempfile.TemporaryDirectory() as tmp:
            cache = FileCache(Path(tmp))
            cache.set("repos/search", {"items": [1, 2, 3]})

            self.assertEqual(cache.get("repos/search"), {"items": [1, 2, 3]})

    def test_missing_key_returns_none(self):
        with tempfile.TemporaryDirectory() as tmp:
            cache = FileCache(Path(tmp))

            self.assertIsNone(cache.get("missing"))


if __name__ == "__main__":
    unittest.main()
