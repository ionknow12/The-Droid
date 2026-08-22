import unittest
from pathlib import Path
from shiplib import parse_apksigner_certs, inspect_apk, ShipError

REAL_APK = sorted((Path(__file__).resolve().parent.parent / "repo").glob("*.apk"))

SAMPLE = """Signer #1 certificate DN: CN=The Droid, O=jinoy
Signer #1 certificate SHA-256 digest: 75c53e64
Signer #1 certificate SHA-1 digest: abc
"""

class ApkTests(unittest.TestCase):
    def test_parse_dn(self):
        self.assertEqual(parse_apksigner_certs(SAMPLE), "CN=The Droid, O=jinoy")
    def test_parse_missing_dn_is_error(self):
        with self.assertRaises(ShipError):
            parse_apksigner_certs("Verifies\n")
    @unittest.skipUnless(REAL_APK, "no APK in repo/ to inspect")
    def test_inspect_real_thedroid_apk(self):
        info = inspect_apk(REAL_APK[0])
        self.assertEqual(info.package, "com.thedroid")
        self.assertGreaterEqual(info.version_code, 3)
        self.assertNotIn("Android Debug", info.signer_dn)
