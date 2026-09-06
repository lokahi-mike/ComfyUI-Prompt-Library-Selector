from pathlib import Path

from aiohttp import web
from server import PromptServer

from .prompt_library import (
    NONE_KEY,
    PromptLibrary,
    append_bundle,
    apply_alias,
    assemble_template,
    map_bundle_to_template,
)


LIBRARY = PromptLibrary(Path(__file__).with_name("prompt_library.yml"))
BUILDER = Path(__file__).with_name("tools") / "yaml-library-builder.html"

class PromptLibrarySelector:
    @classmethod
    def INPUT_TYPES(cls):
        empty_choice = ([NONE_KEY], {"default": NONE_KEY})
        return {
            "required": {
                "category": empty_choice,
                "subcategory": empty_choice,
                "preset": empty_choice,
            },
            "optional": {
                "alias": (
                    "STRING",
                    {
                        "default": "",
                        "multiline": False,
                        "dynamicPrompts": False,
                        "placeholder": "Optional workflow alias, e.g. female_one",
                    },
                ),
                "template_variable": (
                    "STRING",
                    {
                        "default": "",
                        "multiline": False,
                        "dynamicPrompts": False,
                        "placeholder": "e.g. character_a or wardrobe_b",
                    },
                ),
                "seed": (
                    "INT",
                    {
                        "default": 0,
                        "min": 0,
                        "max": 0xFFFFFFFFFFFFFFFF,
                        "control_after_generate": True,
                    },
                ),
                "prompt_override": (
                    "STRING",
                    {
                        "default": "",
                        "multiline": True,
                        "dynamicPrompts": False,
                        "placeholder": "Empty uses the selected YAML prompt",
                    },
                ),
                "negative_override": (
                    "STRING",
                    {
                        "default": "",
                        "multiline": True,
                        "dynamicPrompts": False,
                        "placeholder": "Empty uses the selected YAML negative prompt",
                    },
                ),
                "bundle_in": ("PROMPT_BUNDLE", {"forceInput": True}),
            }
        }

    RETURN_TYPES = ("STRING", "STRING", "STRING", "PROMPT_BUNDLE")
    RETURN_NAMES = (
        "selected_prompt", "selected_negative", "selected_tags", "bundle",
    )
    FUNCTION = "select_prompt"
    CATEGORY = "prompt/library"
    DESCRIPTION = "Select a multiline prompt from prompt_library.yml."

    def select_prompt(
        self,
        category,
        subcategory,
        preset,
        alias="",
        template_variable="",
        seed=0,
        prompt_override="",
        negative_override="",
        bundle_in=None,
    ):
        entry = LIBRARY.resolve_entry(
            category, subcategory, preset, seed, template_variable
        )
        raw_prompt = str(prompt_override or "").strip() or entry["prompt"]
        raw_negative = (
            str(negative_override or "").strip() or entry["negative_prompt"]
        )
        selected = apply_alias(raw_prompt, alias)
        variable = str(template_variable or "").strip() or entry["template_slot"]
        segment = {
            "variable": variable,
            "source": entry["template_slot"],
            "alias": str(alias or "").strip(),
            "raw_positive": raw_prompt,
            "positive": selected,
            "negative": raw_negative,
            "tags": entry["tags"],
            "category": category,
            "subcategory": subcategory,
            "preset": entry["key"],
            "label": entry["label"],
        }
        bundle = append_bundle(bundle_in, segment)
        selected_tags = ", ".join(entry["tags"])
        return {
            "ui": {"resolved": [entry["label"]], "preview": [selected]},
            "result": (selected, raw_negative, selected_tags, bundle),
        }

    @classmethod
    def VALIDATE_INPUTS(cls, category, subcategory, preset, **kwargs):
        # The browser extension populates these combo values from YAML after
        # ComfyUI has loaded the node's static schema. Accept those dynamic
        # stable keys here; resolve() safely returns an empty string for stale
        # or deleted selections.
        return True

    @classmethod
    def IS_CHANGED(
        cls,
        category,
        subcategory,
        preset,
        alias="",
        template_variable="",
        seed=0,
        prompt_override="",
        negative_override="",
        bundle_in=None,
    ):
        return ":".join(str(value) for value in (
            LIBRARY.fingerprint(), category, subcategory, preset, alias,
            template_variable, seed, prompt_override, negative_override,
            bundle_in,
        ))


class PromptLibraryTemplateComposer:
    @classmethod
    def INPUT_TYPES(cls):
        empty_choice = ([NONE_KEY], {"default": NONE_KEY})
        return {
            "required": {
                "template_category": empty_choice,
                "template_subcategory": empty_choice,
                "template": empty_choice,
                "template_override": (
                    "STRING",
                    {
                        "default": "",
                        "multiline": True,
                        "dynamicPrompts": False,
                        "placeholder": "Empty uses the selected library template",
                    },
                ),
                "pre_text": (
                    "STRING",
                    {"default": "", "multiline": True, "dynamicPrompts": False},
                ),
                "post_text": (
                    "STRING",
                    {"default": "", "multiline": True, "dynamicPrompts": False},
                ),
            },
            "optional": {"bundle_in": ("PROMPT_BUNDLE", {"forceInput": True})},
        }

    RETURN_TYPES = ("STRING", "STRING", "STRING")
    RETURN_NAMES = ("positive_prompt", "negative_prompt", "metadata_tags")
    FUNCTION = "compose_template"
    CATEGORY = "prompt/library"
    DESCRIPTION = "Assemble a Prompt Bundle with a YAML natural-language template."

    def compose_template(
        self, template_category, template_subcategory, template,
        template_override="", pre_text="", post_text="",
        bundle_in=None,
    ):
        template_entry = LIBRARY.resolve_template(
            template_category, template_subcategory, template
        )
        template_text = str(template_override or "").strip() or template_entry["template"]
        mapped_bundle = map_bundle_to_template(
            bundle_in, template_entry["slots"], template_entry["aliases"]
        )
        positive, negative, tags = assemble_template(
            template_text, mapped_bundle, pre_text, post_text
        )
        return {
            "ui": {
                "preview": [positive],
                "negative_preview": [negative],
                "tags_preview": [tags],
            },
            "result": (positive, negative, tags),
        }

    @classmethod
    def VALIDATE_INPUTS(
        cls, template_category, template_subcategory, template, **kwargs
    ):
        return True

    @classmethod
    def IS_CHANGED(
        cls, template_category, template_subcategory, template,
        template_override="", **kwargs
    ):
        return (
            f"{LIBRARY.fingerprint()}:{template_category}:"
            f"{template_subcategory}:{template}:{template_override}"
        )


@PromptServer.instance.routes.get("/prompt-library-selector/library")
async def get_prompt_library(_request):
    try:
        return web.json_response(LIBRARY.catalog())
    except (OSError, UnicodeError, ValueError) as error:
        return web.json_response({"error": str(error)}, status=400)


@PromptServer.instance.routes.get("/prompt-library-selector/builder")
async def get_prompt_library_builder(_request):
    return web.FileResponse(BUILDER)


NODE_CLASS_MAPPINGS = {
    "PromptLibrarySelector": PromptLibrarySelector,
    "PromptLibraryTemplateComposer": PromptLibraryTemplateComposer,
}
NODE_DISPLAY_NAME_MAPPINGS = {
    "PromptLibrarySelector": "Prompt Library Selector",
    "PromptLibraryTemplateComposer": "Prompt Library Template Composer",
}
