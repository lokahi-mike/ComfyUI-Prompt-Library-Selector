from pathlib import Path

from aiohttp import web
from server import PromptServer

from .prompt_library import NONE_KEY, PromptLibrary


LIBRARY = PromptLibrary(Path(__file__).with_name("prompt_library.yml"))


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
    def IS_CHANGED(cls, category, subcategory, preset):
        return LIBRARY.fingerprint()


@PromptServer.instance.routes.get("/prompt-library-selector/library")
async def get_prompt_library(_request):
    try:
        return web.json_response(LIBRARY.catalog())
    except (OSError, UnicodeError, ValueError) as error:
        return web.json_response({"error": str(error)}, status=400)


NODE_CLASS_MAPPINGS = {"PromptLibrarySelector": PromptLibrarySelector}
NODE_DISPLAY_NAME_MAPPINGS = {
    "PromptLibrarySelector": "Prompt Library Selector"
}
