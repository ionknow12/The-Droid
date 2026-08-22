import unittest
from pathlib import Path
from shiplib import published_version_codes
FIX = Path(__file__).parent / "fixtures" / "index-v2.sample.json"

class IndexTests(unittest.TestCase):
    def test_max_per_package(self):
        self.assertEqual(published_version_codes(FIX),
                         {"com.thedroid": 3, "com.kookie.music": 14})
    def test_missing_index_is_empty(self):
        self.assertEqual(published_version_codes(Path("/nonexistent/index-v2.json")), {})
