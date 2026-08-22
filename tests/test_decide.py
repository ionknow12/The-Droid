import unittest
from pathlib import Path
from shiplib import Recipe, ApkInfo, decide

R = Recipe("com.kookie.music", "kookie", Path("/p"), ":app:assembleRelease", Path("a.apk"), None, {})
def apk(code=15, pkg="com.kookie.music", dn="CN=Kookie"):
    return ApkInfo(pkg, code, "0.9", dn)

class DecideTests(unittest.TestCase):
    def test_newer_signed_matching_is_ok(self):
        d = decide(R, apk(), {"com.kookie.music": 14}); self.assertTrue(d.ok, d.reason)
    def test_first_release_is_ok(self):
        self.assertTrue(decide(R, apk(), {}).ok)
    def test_same_or_older_code_refused(self):
        self.assertFalse(decide(R, apk(14), {"com.kookie.music": 14}).ok)
        self.assertFalse(decide(R, apk(13), {"com.kookie.music": 14}).ok)
    def test_package_mismatch_refused(self):
        d = decide(R, apk(pkg="com.other"), {}); self.assertFalse(d.ok); self.assertIn("com.other", d.reason)
    def test_debug_signer_refused(self):
        self.assertFalse(decide(R, apk(dn="CN=Android Debug, O=Android"), {}).ok)
