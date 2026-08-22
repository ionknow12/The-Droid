import tempfile, unittest
from pathlib import Path
import yaml
from shiplib import Recipe, merge_repo_metadata, sync_metadata

class MetaTests(unittest.TestCase):
    def test_merge_keeps_hand_edits(self):
        self.assertEqual(merge_repo_metadata({"License": "MIT", "Donate": "x"}, {"License": "GPL-3.0-only"}),
                         {"License": "GPL-3.0-only", "Donate": "x"})
    def test_sync_writes_yml_and_copies_fastlane(self):
        with tempfile.TemporaryDirectory() as d:
            proj = Path(d, "proj"); (proj / "fl/en-US/changelogs").mkdir(parents=True)
            (proj / "fl/en-US/title.txt").write_text("Kookie")
            (proj / "fl/en-US/changelogs/15.txt").write_text("new")
            repo = Path(d, "repo"); (repo / "metadata").mkdir(parents=True)
            r = Recipe("com.k", "k", proj, ":a", Path("x.apk"), Path("fl"), {"License": "GPL-3.0-only"})
            warnings = sync_metadata(r, repo, version_code=15)
            self.assertEqual(warnings, [])
            self.assertEqual(yaml.safe_load((repo / "metadata/com.k.yml").read_text())["License"], "GPL-3.0-only")
            self.assertEqual((repo / "metadata/com.k/en-US/title.txt").read_text(), "Kookie")
    def test_missing_changelog_warns(self):
        with tempfile.TemporaryDirectory() as d:
            proj = Path(d, "proj"); (proj / "fl/en-US").mkdir(parents=True)
            repo = Path(d, "repo"); (repo / "metadata").mkdir(parents=True)
            r = Recipe("com.k", "k", proj, ":a", Path("x.apk"), Path("fl"), {})
            w = sync_metadata(r, repo, version_code=15)
            self.assertTrue(any("changelogs/15.txt" in x for x in w), w)
