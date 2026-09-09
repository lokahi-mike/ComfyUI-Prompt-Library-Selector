import tempfile
import unittest
from pathlib import Path

from prompt_library import (
    NONE_KEY,
    RANDOM_KEY,
    PromptLibrary,
    append_bundle,
    apply_alias,
    assemble_template,
    bundle_strings,
    compose_fragments,
    map_bundle_to_template,
)


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
version: 3
templates:
  solo:
    label: Solo
    subcategories:
      natural_language:
        label: Natural Language
        templates:
          natural:
            label: Natural
            slots:
              character_a: character
              wardrobe_a: outfit
            aliases:
              character_a: Character A
            defaults:
              wardrobe_a: '{{subject}} is completely nude.'
            template: |-
              {{character_a}}

              {{wardrobe_a}}
categories:
  characters:
    label: Characters
    template_slot: character
    metadata:
      tags: [subject]
    subcategories:
      originals:
        label: Originals
        presets:
          rhiannon:
            label: Rhiannon
            prompt: '{{subject}} is Rhiannon.'
            negative_prompt: distorted face
            addenda:
              freckles:
                label: Freckles
                prompt: '{{subject}} has freckles.'
                metadata:
                  tags: [freckles]
              identity_guardrails:
                label: Identity Guardrails
                negative_prompt: duplicate person
                default_enabled: true
            metadata:
              tags: [adult, original]
          zara:
            label: Zara
            prompt: '{{subject}} is Zara.'
"""

SAMPLE_FLAT_V2 = """
version: 2
templates:
  old_template:
    label: Old Template
    template: '{{character}}'
categories: {}
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

    def test_alias_replaces_subject_placeholder_before_legacy_fallback(self):
        self.assertEqual(
            apply_alias("{{subject}} wears black. {{SUBJECT}} smiles.", "Character B"),
            "Character B wears black. Character B smiles.",
        )

    def test_version_three_workbench_fields_do_not_break_prompt_resolution(self):
        self.path.write_text(SAMPLE_V2, encoding="utf-8")
        self.assertEqual(self.library.load()["version"], 3)
        self.assertEqual(
            self.library.resolve("characters", "originals", "rhiannon"),
            "{{subject}} is Rhiannon.",
        )

    def test_catalog_exposes_templates_negative_prompts_slots_and_tags(self):
        self.path.write_text(SAMPLE_V2, encoding="utf-8")
        catalog = self.library.catalog()
        template = catalog["templates"][0]["subcategories"][0]["templates"][0]
        self.assertEqual(template["slots"]["character_a"], "character")
        self.assertEqual(template["defaults"]["wardrobe_a"], "{{subject}} is completely nude.")
        self.assertEqual(
            self.library.resolve_template("solo", "natural_language", "natural")["label"],
            "Natural",
        )
        preset = catalog["categories"][0]["subcategories"][0]["presets"][0]
        self.assertEqual(preset["negative_prompt"], "distorted face")
        self.assertEqual(preset["template_slot"], "")
        self.assertEqual(preset["tags"], ["subject", "adult", "original"])
        self.assertEqual(
            [item["key"] for item in preset["addenda"]],
            ["freckles", "identity_guardrails"],
        )
        self.assertTrue(preset["addenda"][1]["default_enabled"])

    def test_flat_v2_templates_are_exposed_under_general_groups(self):
        self.path.write_text(SAMPLE_FLAT_V2, encoding="utf-8")
        catalog = self.library.catalog()["templates"]
        self.assertEqual(catalog[0]["key"], "general")
        self.assertEqual(catalog[0]["subcategories"][0]["key"], "general")
        self.assertEqual(
            catalog[0]["subcategories"][0]["templates"][0]["label"],
            "Old Template",
        )
        self.assertEqual(
            self.library.resolve_template("old_template")["template"],
            "{{character}}",
        )

    def test_seeded_random_is_reproducible_and_resolves_a_real_preset(self):
        self.path.write_text(SAMPLE_V2, encoding="utf-8")
        first = self.library.resolve_entry("characters", "originals", RANDOM_KEY, 42, "character_a")
        second = self.library.resolve_entry("characters", "originals", RANDOM_KEY, 42, "character_a")
        self.assertEqual(first, second)
        self.assertIn(first["key"], {"rhiannon", "zara"})
        self.assertIn(first["label"], {"Rhiannon", "Zara"})

    def test_bundle_aggregation_and_template_assembly(self):
        bundle = append_bundle(None, {
            "variable": "character_a", "positive": "Character A is Rhiannon.",
            "negative": "distorted face", "tags": ["subject", "adult"],
        })
        bundle = append_bundle(bundle, {
            "variable": "wardrobe_a", "positive": "Character A wears black.",
            "negative": "distorted face", "tags": ["fashion", "adult"],
        })
        self.assertEqual(
            bundle_strings(bundle),
            ("Character A is Rhiannon.\n\nCharacter A wears black.", "distorted face", "subject, adult, fashion"),
        )
        positive, negative, tags = assemble_template(
            "{{character_a}}\n\n{{wardrobe_a}}\n\n{{missing}}", bundle, "Opening", "Closing"
        )
        self.assertEqual(
            positive,
            "Opening\n\nCharacter A is Rhiannon.\n\nCharacter A wears black.\n\nClosing",
        )
        self.assertEqual(negative, "distorted face")
        self.assertEqual(tags, "subject, adult, fashion")

    def test_repeated_sources_map_to_template_variables_in_bundle_order(self):
        bundle = {"segments": [
            {"variable": "character", "source": "character", "raw_positive": "{{subject}} is Rhiannon.", "positive": "{{subject}} is Rhiannon."},
            {"variable": "character", "source": "character", "raw_positive": "{{subject}} is Florence.", "positive": "{{subject}} is Florence."},
        ]}
        mapped = map_bundle_to_template(
            bundle,
            {"character_a": "character", "character_b": "character"},
            {"character_a": "Character A", "character_b": "Character B"},
        )
        self.assertEqual(
            [(item["variable"], item["positive"]) for item in mapped["segments"]],
            [
                ("character_a", "Character A is Rhiannon."),
                ("character_b", "Character B is Florence."),
            ],
        )

    def test_template_default_fills_only_an_unconnected_variable(self):
        bundle = map_bundle_to_template(
            {"segments": [{
                "variable": "character_a", "source": "character",
                "positive": "Character A is Nadia.",
            }]},
            {"character_a": "character", "outfit_a": "outfit"},
            {"outfit_a": "Character A"},
            {"outfit_a": "{{subject}} is completely nude."},
        )
        positive, _, _ = assemble_template(
            "{{character_a}}\n\n{{outfit_a}}", bundle
        )
        self.assertEqual(
            positive,
            "Character A is Nadia.\n\nCharacter A is completely nude.",
        )
        connected = append_bundle(bundle, {
            "variable": "outfit_a", "source": "outfit",
            "alias": "Character A",
            "raw_positive": "{{subject}} wears a red dress.",
            "positive": "Character A wears a red dress.",
        })
        remapped = map_bundle_to_template(
            connected,
            {"character_a": "character", "outfit_a": "outfit"},
            {"outfit_a": "Character A"},
            {"outfit_a": "{{subject}} is completely nude."},
        )
        overridden, _, _ = assemble_template(
            "{{character_a}}\n\n{{outfit_a}}", remapped
        )
        self.assertEqual(
            overridden,
            "Character A is Nadia.\n\nCharacter A wears a red dress.",
        )


if __name__ == "__main__":
    unittest.main()
