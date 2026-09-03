from pathlib import Path

from aiohttp import web
from server import PromptServer

from .prompt_library import (
    NONE_KEY,
    PromptLibrary,
    append_bundle,
    apply_alias,
    assemble_template,
    bundle_strings,
    compose_fragments,
    map_bundle_to_template,
)


LIBRARY = PromptLibrary(Path(__file__).with_name("prompt_library.yml"))
BUILDER = Path(__file__).with_name("tools") / "yaml-library-builder.html"

SEPARATORS = {
    "Blank line": "\n\n",
    "New line": "\n",
    "Comma + space": ", ",
    "Space": " ",
}


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
                "join_style": (list(SEPARATORS), {"default": "Blank line"}),
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
                "prompt_in": ("STRING", {"forceInput": True}),
                "bundle_in": ("PROMPT_BUNDLE", {"forceInput": True}),
            }
        }

    RETURN_TYPES = (
        "STRING", "STRING", "STRING", "STRING", "STRING", "STRING",
        "PROMPT_BUNDLE",
    )
    RETURN_NAMES = (
        "selected_prompt", "combined_prompt", "selected_negative",
        "combined_negative", "selected_tags", "combined_tags", "bundle",
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
        join_style="Blank line",
        template_variable="",
        seed=0,
        prompt_override="",
        negative_override="",
        prompt_in=None,
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
        combined = compose_fragments(
            (prompt_in, selected), SEPARATORS.get(join_style, "\n\n")
        )
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
        bundle_positive, combined_negative, combined_tags = bundle_strings(
            bundle, SEPARATORS.get(join_style, "\n\n")
        )
        # prompt_in is the legacy string chain and cannot carry negative/tag data.
        if prompt_in is not None:
            bundle_positive = compose_fragments(
                (prompt_in, selected), SEPARATORS.get(join_style, "\n\n")
            )
        selected_tags = ", ".join(entry["tags"])
        return {
            "ui": {"resolved": [entry["label"]], "preview": [selected]},
            "result": (
                selected, combined or bundle_positive, raw_negative,
                combined_negative, selected_tags, combined_tags, bundle,
            ),
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
        join_style="Blank line",
        template_variable="",
        seed=0,
        prompt_override="",
        negative_override="",
        prompt_in=None,
        bundle_in=None,
    ):
        return ":".join(str(value) for value in (
            LIBRARY.fingerprint(), category, subcategory, preset, alias,
            join_style, template_variable, seed, prompt_override,
            negative_override, prompt_in, bundle_in,
        ))


class PromptLibraryTemplateComposer:
    @classmethod
    def INPUT_TYPES(cls):
        empty_choice = ([NONE_KEY], {"default": NONE_KEY})
        return {
            "required": {
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
        self, template, template_override="", pre_text="", post_text="",
        bundle_in=None,
    ):
        template_entry = LIBRARY.resolve_template(template)
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
    def VALIDATE_INPUTS(cls, template, **kwargs):
        return True

    @classmethod
    def IS_CHANGED(cls, template, template_override="", **kwargs):
        return f"{LIBRARY.fingerprint()}:{template}:{template_override}"


class PromptLibraryComposer:
    @classmethod
    def INPUT_TYPES(cls):
        return {
            "required": {
                "separator": (list(SEPARATORS), {"default": "Blank line"}),
                "pre_text": (
                    "STRING",
                    {
                        "default": "",
                        "multiline": True,
                        "dynamicPrompts": False,
                        "placeholder": "Optional text placed before all connected fragments",
                    },
                ),
                "post_text": (
                    "STRING",
                    {
                        "default": "",
                        "multiline": True,
                        "dynamicPrompts": False,
                        "placeholder": "Optional text placed after all connected fragments",
                    },
                ),
            },
            "optional": {
                "text_1": ("STRING", {"forceInput": True}),
            },
        }

    RETURN_TYPES = ("STRING",)
    RETURN_NAMES = ("prompt",)
    FUNCTION = "compose_prompt"
    CATEGORY = "prompt/library"
    DESCRIPTION = "Join any number of non-empty string inputs into one prompt."

    def compose_prompt(
        self, separator, pre_text="", post_text="", text_1=None, **kwargs
    ):
        numbered = [(1, text_1)]
        for name, value in kwargs.items():
            if name.startswith("text_") and name[5:].isdigit():
                numbered.append((int(name[5:]), value))

        values = [pre_text]
        values.extend(value for _, value in sorted(numbered))
        values.append(post_text)
        prompt = compose_fragments(values, SEPARATORS.get(separator, "\n\n"))
        return {"ui": {"preview": [prompt]}, "result": (prompt,)}

    @classmethod
    def VALIDATE_INPUTS(cls, input_types=None, **kwargs):
        # Extra text_N sockets are created by the autogrow frontend extension.
        return True


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
    "PromptLibraryComposer": PromptLibraryComposer,
    "PromptLibraryTemplateComposer": PromptLibraryTemplateComposer,
}
NODE_DISPLAY_NAME_MAPPINGS = {
    "PromptLibrarySelector": "Prompt Library Selector",
    "PromptLibraryComposer": "Prompt Library Composer",
    "PromptLibraryTemplateComposer": "Prompt Library Template Composer",
}
