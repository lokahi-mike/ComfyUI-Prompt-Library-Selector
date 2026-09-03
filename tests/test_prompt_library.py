import tempfile
import unittest
from pathlib import Path

from prompt_library import NONE_KEY, PromptLibrary, apply_alias, compose_fragments


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

SAMPLE_V2 = """
version: 2
templates:
  natural:
    label: Natural
    template: '{{character}}'
categories:
  characters:
    label: Characters
    template_slot: character
    subcategories:
      originals:
        label: Originals
        presets:
          rhiannon:
            label: Rhiannon
            prompt: Rhiannon character prompt
            negative_prompt: distorted face
            metadata:
              tags: [adult, original]
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

    def test_alias_is_workflow_specific_and_optional(self):
        self.assertEqual(apply_alias("Kaley Cuoco", "female_one"), "female_one: Kaley Cuoco")
        self.assertEqual(apply_alias("Kaley Cuoco", ""), "Kaley Cuoco")
        self.assertEqual(apply_alias("", "female_one"), "")

    def test_version_two_workbench_fields_do_not_break_prompt_resolution(self):
        self.path.write_text(SAMPLE_V2, encoding="utf-8")
        self.assertEqual(self.library.load()["version"], 2)
        self.assertEqual(
            self.library.resolve("characters", "originals", "rhiannon"),
            "Rhiannon character prompt",
        )


if __name__ == "__main__":
    unittest.main()
