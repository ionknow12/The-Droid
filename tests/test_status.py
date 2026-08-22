import unittest
from pathlib import Path
from shiplib import Recipe, status_rows
R1 = Recipe("com.a", "a", Path("/p"), ":t", Path("a.apk"), None, {})
R2 = Recipe("com.b", "b", Path("/p"), ":t", Path("b.apk"), None, {})
class StatusTests(unittest.TestCase):
    def test_rows(self):
        probe = {"com.a": 5, "com.b": None}   # None = no built APK found
        rows = status_rows([R1, R2], {"com.a": 4}, probe)
        self.assertEqual(rows[0], ("a", "com.a", 5, 4, "STALE"))
        self.assertEqual(rows[1], ("b", "com.b", None, None, "UNBUILT"))
    def test_current(self):
        self.assertEqual(status_rows([R1], {"com.a": 5}, {"com.a": 5})[0][4], "CURRENT")
