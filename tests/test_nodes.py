import importlib.util
import sys
import tempfile
import types
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
PACKAGE_NAME = "prompt_selector_node_tests"


def load_nodes_module():
    package = types.ModuleType(PACKAGE_NAME)
    package.__path__ = [str(ROOT)]
    sys.modules.setdefault(PACKAGE_NAME, package)

    library_name = f"{PACKAGE_NAME}.prompt_library"
    if library_name not in sys.modules:
        spec = importlib.util.spec_from_file_location(library_name, ROOT / "prompt_library.py")
        module = importlib.util.module_from_spec(spec)
        sys.modules[library_name] = module
        spec.loader.exec_module(module)

    class Routes:
        @staticmethod
        def get(_path):
            return lambda function: function

    server = types.ModuleType("server")
    server.PromptServer = types.SimpleNamespace(
        instance=types.SimpleNamespace(routes=Routes())
    )
    sys.modules.setdefault("server", server)
    if "aiohttp" not in sys.modules:
        aiohttp = types.ModuleType("aiohttp")
        aiohttp.web = types.SimpleNamespace(
            json_response=lambda *args, **kwargs: (args, kwargs),
            FileResponse=lambda *args, **kwargs: (args, kwargs),
        )
        sys.modules["aiohttp"] = aiohttp

    nodes_name = f"{PACKAGE_NAME}.nodes"
    spec = importlib.util.spec_from_file_location(nodes_name, ROOT / "nodes.py")
    module = importlib.util.module_from_spec(spec)
    sys.modules[nodes_name] = module
    spec.loader.exec_module(module)
    return module, sys.modules[library_name]


SAMPLE = """
version: 3
templates:
  dual:
    label: Dual
    subcategories:
      editorial:
        label: Editorial
        templates:
          pair:
            label: Pair
            slots:
              character_a: character
              character_b: character
            aliases:
              character_a: Character A
              character_b: Character B
            defaults:
              character_b: Character B is an unspecified adult.
            template: |-
              {{character_a}}

              {{character_b}}
categories:
  characters:
    label: Characters
    template_slot: character
    metadata:
      tags: [subject]
    subcategories:
      people:
        label: People
        presets:
          alpha:
            label: Alpha
            prompt: '{{subject}} is Alpha.'
            negative_prompt: duplicate face
            metadata:
              tags: [alpha]
          beta:
            label: Beta
            prompt: '{{subject}} is Beta.'
            metadata:
              tags: [beta]
"""


class NodeIntegrationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        try:
            cls.nodes, cls.library_module = load_nodes_module()
        except ModuleNotFoundError as error:
            raise unittest.SkipTest(f"Node runtime dependency unavailable: {error}")

    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        path = Path(self.temp_dir.name) / "prompt_library.yml"
        path.write_text(SAMPLE, encoding="utf-8")
        self.original_library = self.nodes.LIBRARY
        self.nodes.LIBRARY = self.library_module.PromptLibrary(path)

    def tearDown(self):
        self.nodes.LIBRARY = self.original_library
        self.temp_dir.cleanup()

    def test_selector_outputs_selected_values_and_bundle(self):
        response = self.nodes.PromptLibrarySelector().select_prompt(
            "characters", "people", "alpha", alias="Character A",
            template_variable="character_a",
        )
        result = response["result"]
        self.assertEqual(len(result), 5)
        self.assertEqual(result[0], "Character A is Alpha.")
        self.assertEqual(result[1], "duplicate face")
        self.assertEqual(result[2], "subject, alpha")
        self.assertEqual(result[3]["segments"][0]["variable"], "character_a")
        self.assertEqual(result[4], "Alpha")

    def test_template_composer_assigns_repeated_sources_and_template_aliases(self):
        selector = self.nodes.PromptLibrarySelector()
        first = selector.select_prompt("characters", "people", "alpha")["result"][3]
        second = selector.select_prompt(
            "characters", "people", "beta", bundle_in=first
        )["result"][3]
        response = self.nodes.PromptLibraryTemplateComposer().compose_template(
            "dual", "editorial", "pair", bundle_in=second
        )
        positive, negative = response["result"]
        self.assertEqual(positive, "Character A is Alpha.\n\nCharacter B is Beta.")
        self.assertEqual(negative, "duplicate face")

    def test_resolved_names_chain_with_custom_separator_and_skip_none(self):
        selector = self.nodes.PromptLibrarySelector()
        first = selector.select_prompt(
            "characters", "people", "alpha", name_separator=" + "
        )["result"][4]
        second = selector.select_prompt(
            "characters", "people", "beta",
            resolved_names_in=first, name_separator=" + ",
        )["result"][4]
        skipped = selector.select_prompt(
            "__none__", "__none__", "__none__",
            resolved_names_in=second, name_separator=" + ",
        )["result"][4]

        self.assertEqual(first, "Alpha")
        self.assertEqual(second, "Alpha + Beta")
        self.assertEqual(skipped, "Alpha + Beta")

    def test_disabled_selector_contributes_nothing_and_passes_chains_through(self):
        selector = self.nodes.PromptLibrarySelector()
        first_result = selector.select_prompt(
            "characters", "people", "alpha"
        )["result"]
        response = selector.select_prompt(
            "characters", "people", "beta", enabled=False,
            bundle_in=first_result[3], resolved_names_in=first_result[4],
        )
        result = response["result"]

        self.assertEqual(result[0], "")
        self.assertEqual(result[1], "")
        self.assertEqual(result[2], "")
        self.assertEqual(len(result[3]["segments"]), 1)
        self.assertEqual(result[3]["segments"][0]["label"], "Alpha")
        self.assertEqual(result[4], "Alpha")
        self.assertEqual(response["ui"]["resolved"], ["Bypassed"])

    def test_filename_builder_sanitizes_names_and_can_include_seed(self):
        result = self.nodes.PromptLibraryFilenameBuilder().build_filename(
            "Alpha, Bé / Beta", separator="_", include_seed=True, seed=42,
            prefix="portrait", suffix="final",
        )[0]
        self.assertEqual(result, "portrait_Alpha_Be_Beta_final_seed-42")

    def test_filename_builder_returns_empty_without_resolved_names(self):
        result = self.nodes.PromptLibraryFilenameBuilder().build_filename(
            "", prefix="portrait", include_seed=True, seed=42,
        )[0]
        self.assertEqual(result, "")

    def test_prompt_packet_outputs_json_and_plain_text(self):
        packet_node = self.nodes.PromptLibraryPromptPacket()
        json_packet = packet_node.build_packet(
            "A positive prompt.", "JSON", 42, "bad anatomy",
            "Alpha + Beta", "alpha_beta_seed-42",
        )[0]
        payload = __import__("json").loads(json_packet)
        self.assertEqual(payload["resolved_names"], "Alpha + Beta")
        self.assertEqual(payload["seed"], 42)
        plain_packet = packet_node.build_packet(
            "A positive prompt.", "Plain text", 42,
        )[0]
        self.assertIn("[POSITIVE PROMPT]\nA positive prompt.", plain_packet)
        self.assertNotIn("[NEGATIVE PROMPT]", plain_packet)

    def test_user_library_is_preferred_with_builtin_fallback(self):
        with tempfile.TemporaryDirectory() as directory:
            self.assertEqual(
                self.nodes.preferred_library_path(directory),
                self.nodes.BUILTIN_LIBRARY_PATH,
            )
            user_library = (
                Path(directory) / "prompt_library_selector" /
                "prompt_library.yml"
            )
            user_library.parent.mkdir(parents=True)
            user_library.write_text(SAMPLE, encoding="utf-8")
            self.assertEqual(
                self.nodes.preferred_library_path(directory), user_library
            )

    def test_active_library_rechecks_user_path_after_startup(self):
        original_folder_paths = self.nodes.folder_paths
        injected_library = self.nodes.LIBRARY
        original_path = self.nodes._MANAGED_LIBRARY.path
        try:
            with tempfile.TemporaryDirectory() as directory:
                self.nodes.LIBRARY = self.nodes._MANAGED_LIBRARY
                self.nodes.folder_paths = types.SimpleNamespace(
                    get_user_directory=lambda: directory
                )
                self.nodes.LIBRARY.path = self.nodes.BUILTIN_LIBRARY_PATH
                self.assertEqual(
                    self.nodes.active_library().path,
                    self.nodes.BUILTIN_LIBRARY_PATH,
                )

                user_library = (
                    Path(directory) / "prompt_library_selector" /
                    "prompt_library.yml"
                )
                user_library.parent.mkdir(parents=True)
                user_library.write_text(SAMPLE, encoding="utf-8")

                self.assertEqual(
                    self.nodes.active_library().path,
                    user_library,
                )
        finally:
            self.nodes.folder_paths = original_folder_paths
            self.nodes._MANAGED_LIBRARY.path = original_path
            self.nodes.LIBRARY = injected_library


if __name__ == "__main__":
    unittest.main()
