import tempfile, unittest
from pathlib import Path
from shiplib import load_env_file, load_recipes, ShipError

class EnvFileTests(unittest.TestCase):
    def test_parses_key_values_ignores_comments_and_export(self):
        with tempfile.TemporaryDirectory() as d:
            f = Path(d, "s.txt"); f.write_text("# c\nA=1\nexport B=two words\n\nC='q'\n")
            self.assertEqual(load_env_file(f), {"A": "1", "B": "two words", "C": "q"})
    def test_missing_file_is_error(self):
        with self.assertRaises(ShipError):
            load_env_file(Path("/nonexistent/secrets.txt"))
    def test_recipe_env_file_is_optional(self):
        with tempfile.TemporaryDirectory() as d:
            Path(d, "x.yml").write_text("package: x\nname: x\nproject: /p\ngradle_task: t\napk: a.apk\n")
            self.assertIsNone(load_recipes(Path(d))[0].env_file)
            Path(d, "x.yml").write_text("package: x\nname: x\nproject: /p\ngradle_task: t\napk: a.apk\nenv_file: s.txt\n")
            self.assertEqual(load_recipes(Path(d))[0].env_file, Path("s.txt"))
