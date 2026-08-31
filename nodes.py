from pathlib import Path

from aiohttp import web
from server import PromptServer

from .prompt_library import NONE_KEY, PromptLibrary, compose_fragments


LIBRARY = PromptLibrary(Path(__file__).with_name("prompt_library.yml"))

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
            }
        }

    RETURN_TYPES = ("STRING",)
    RETURN_NAMES = ("prompt",)
    FUNCTION = "select_prompt"
    CATEGORY = "prompt/library"
    DESCRIPTION = "Select a multiline prompt from prompt_library.yml."

    def select_prompt(self, category, subcategory, preset):
        return (LIBRARY.resolve(category, subcategory, preset),)

    @classmethod
    def VALIDATE_INPUTS(cls, category, subcategory, preset):
        # The browser extension populates these combo values from YAML after
        # ComfyUI has loaded the node's static schema. Accept those dynamic
        # stable keys here; resolve() safely returns an empty string for stale
        # or deleted selections.
        return True

    @classmethod
    def IS_CHANGED(cls, category, subcategory, preset):
        return LIBRARY.fingerprint()


class PromptLibraryComposer:
    @classmethod
    def INPUT_TYPES(cls):
        return {
            "required": {
                "separator": (list(SEPARATORS), {"default": "Blank line"}),
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

    def compose_prompt(self, separator, text_1=None, **kwargs):
        numbered = [(1, text_1)]
        for name, value in kwargs.items():
            if name.startswith("text_") and name[5:].isdigit():
                numbered.append((int(name[5:]), value))

        values = [value for _, value in sorted(numbered)]
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


NODE_CLASS_MAPPINGS = {
    "PromptLibrarySelector": PromptLibrarySelector,
    "PromptLibraryComposer": PromptLibraryComposer,
}
NODE_DISPLAY_NAME_MAPPINGS = {
    "PromptLibrarySelector": "Prompt Library Selector",
    "PromptLibraryComposer": "Prompt Library Composer",
}
