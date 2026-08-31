import tempfile
import unittest
from pathlib import Path

from prompt_library import NONE_KEY, PromptLibrary, compose_fragments


SAMPLE = """
version: 1
categories:
  z_key:
    label: Alpha Category
    subcategories:
      sub:
        label: Friendly Subcategory
        presets:
          preset_key:
            label: Friendly Preset
            prompt: |-
              first line
              second line
  a_key:
    label: Zulu Category
    subcategories: {}
"""


class PromptLibraryTests(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.path = Path(self.temp_dir.name) / "prompt_library.yml"
        self.path.write_text(SAMPLE, encoding="utf-8")
        self.library = PromptLibrary(self.path)

    def tearDown(self):
        self.temp_dir.cleanup()

    def test_catalog_uses_labels_and_sorts_by_them(self):
        catalog = self.library.catalog()["categories"]
        self.assertEqual([item["key"] for item in catalog], ["z_key", "a_key"])
        self.assertEqual(catalog[0]["label"], "Alpha Category")
        self.assertEqual(
            catalog[0]["subcategories"][0]["presets"][0]["label"],
            "Friendly Preset",
        )
        self.assertEqual(
            catalog[0]["subcategories"][0]["presets"][0]["prompt"],
            "first line\nsecond line",
        )

    def test_resolve_preserves_multiline_prompt(self):
        self.assertEqual(
            self.library.resolve("z_key", "sub", "preset_key"),
            "first line\nsecond line",
        )

    def test_none_and_removed_selections_return_empty_string(self):
        self.assertEqual(self.library.resolve(NONE_KEY, NONE_KEY, NONE_KEY), "")
        self.assertEqual(self.library.resolve("missing", "sub", "preset_key"), "")

    def test_composer_strips_fragments_and_discards_empty_values(self):
        self.assertEqual(
            compose_fragments([" first ", "", None, "second\n"], "\n\n"),
            "first\n\nsecond",
        )


if __name__ == "__main__":
    unittest.main()
