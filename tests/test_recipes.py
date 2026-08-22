import tempfile, unittest
from pathlib import Path
from shiplib import load_recipes, find_recipe, ShipError

REAL_APPS = Path(__file__).resolve().parent.parent / "apps"

class RecipeTests(unittest.TestCase):
    def test_loads_real_recipes(self):
        recipes = load_recipes(REAL_APPS)
        names = sorted(r.name for r in recipes)
        self.assertEqual(names, ["kookie", "thedroid"])
        td = find_recipe(recipes, "thedroid")
        self.assertEqual(td.package, "com.thedroid")
        self.assertEqual(td.apk, Path("thedroid/build/outputs/apk/release/thedroid-release.apk"))
        self.assertEqual(td.repo_metadata["License"], "GPL-3.0-or-later")

    def test_find_by_package_and_unknown(self):
        recipes = load_recipes(REAL_APPS)
        self.assertEqual(find_recipe(recipes, "com.kookie.music").name, "kookie")
        with self.assertRaises(ShipError):
            find_recipe(recipes, "nope")

    def test_missing_required_key_is_error(self):
        with tempfile.TemporaryDirectory() as d:
            Path(d, "x.yml").write_text("package: x\nname: x\n")
            with self.assertRaises(ShipError):
                load_recipes(Path(d))
