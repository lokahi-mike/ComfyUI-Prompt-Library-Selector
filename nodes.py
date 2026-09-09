import json
import re
import shutil
import unicodedata
from pathlib import Path

import yaml
from aiohttp import web
from server import PromptServer

try:
    import folder_paths
except ImportError:  # Allows standalone tests to run without ComfyUI installed.
    folder_paths = None

from .prompt_library import (
    NONE_KEY,
    PromptLibrary,
    append_bundle,
    apply_alias,
    assemble_template,
    compose_fragments,
    deduplicate,
    map_bundle_to_template,
)


BUILTIN_LIBRARY_PATH = Path(__file__).with_name("prompt_library.yml")


def user_library_path(user_directory=None):
    if user_directory is None and folder_paths is not None:
        user_directory = folder_paths.get_user_directory()
    if not user_directory:
        return None
    return Path(user_directory) / "prompt_library_selector" / "prompt_library.yml"


def preferred_library_path(user_directory=None):
    user_path = user_library_path(user_directory)
    if user_path and user_path.is_file():
        return user_path
    return BUILTIN_LIBRARY_PATH


LIBRARY = PromptLibrary(preferred_library_path())
_MANAGED_LIBRARY = LIBRARY
BUILDER = Path(__file__).with_name("tools") / "yaml-library-builder.html"


def active_library():
    """Follow ComfyUI's current user directory instead of freezing startup state."""
    # Tests and embedding hosts may deliberately inject a separate library.
    if LIBRARY is not _MANAGED_LIBRARY:
        return LIBRARY
    desired_path = preferred_library_path()
    if LIBRARY.path != desired_path:
        LIBRARY.path = desired_path
    return LIBRARY


def save_user_library(text, user_directory=None):
    """Validate and atomically save YAML without ever modifying the fallback."""
    target = user_library_path(user_directory)
    if target is None:
        raise ValueError("ComfyUI did not provide a user directory")
    if not isinstance(text, str) or not text.strip():
        raise ValueError("Library YAML cannot be empty")
    data = yaml.safe_load(text)
    if not isinstance(data, dict):
        raise ValueError("prompt_library.yml must contain a YAML mapping")
    if not isinstance(data.get("categories", {}), dict):
        raise ValueError("'categories' must be a mapping")
    if not isinstance(data.get("templates", {}), dict):
        raise ValueError("'templates' must be a mapping")

    target.parent.mkdir(parents=True, exist_ok=True)
    backup = target.with_name("prompt_library.backup.yml")
    temporary = target.with_name(".prompt_library.yml.tmp")
    try:
        if target.is_file():
            shutil.copy2(target, backup)
        temporary.write_text(text, encoding="utf-8")
        temporary.replace(target)
    finally:
        temporary.unlink(missing_ok=True)
    return target, backup if backup.is_file() else None


def safe_filename_stem(
    resolved_names, prefix="", suffix="", separator="_", seed=0,
    include_seed=False, max_length=160,
):
    """Build a portable filename stem while preserving useful human labels."""
    names = str(resolved_names or "").strip()
    if not names:
        return ""
    requested_joiner = unicodedata.normalize("NFKD", str(separator or "_"))
    joiner = re.sub(r"[^A-Za-z0-9_-]+", "", requested_joiner) or "_"
    raw_parts = [str(prefix or "").strip(), names, str(suffix or "").strip()]
    if include_seed:
        raw_parts.append(f"seed-{int(seed)}")
    raw = joiner.join(part for part in raw_parts if part)
    ascii_text = unicodedata.normalize("NFKD", raw).encode(
        "ascii", "ignore"
    ).decode("ascii")
    sanitized = re.sub(r"[^A-Za-z0-9_-]+", joiner, ascii_text)
    if joiner:
        sanitized = re.sub(rf"(?:{re.escape(joiner)})+", joiner, sanitized)
        sanitized = sanitized.strip(f" ._-{joiner}")
    else:
        sanitized = sanitized.strip(" ._-")
    limit = max(1, min(int(max_length), 240))
    return sanitized[:limit].rstrip(" ._-")


def make_prompt_packet(
    positive_prompt, negative_prompt="", resolved_names="",
    filename_stem="", seed=0, packet_format="JSON", notes="",
):
    data = {
        "resolved_names": str(resolved_names or "").strip(),
        "filename_stem": str(filename_stem or "").strip(),
        "seed": int(seed),
        "positive_prompt": str(positive_prompt or "").strip(),
        "negative_prompt": str(negative_prompt or "").strip(),
        "notes": str(notes or "").strip(),
    }
    if str(packet_format).lower() == "json":
        return json.dumps(data, ensure_ascii=False, indent=2)
    sections = []
    for heading, key in (
        ("RESOLVED NAMES", "resolved_names"),
        ("FILENAME", "filename_stem"),
        ("SEED", "seed"),
        ("POSITIVE PROMPT", "positive_prompt"),
        ("NEGATIVE PROMPT", "negative_prompt"),
        ("NOTES", "notes"),
    ):
        value = data[key]
        if value == "" and key not in {"positive_prompt", "seed"}:
            continue
        sections.append(f"[{heading}]\n{value}")
    return "\n\n".join(sections)

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
                "enabled": ("BOOLEAN", {"default": True}),
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
                **{
                    f"addendum_{index}": ("BOOLEAN", {"default": False})
                    for index in range(1, 9)
                },
                "addenda_initialized": ("BOOLEAN", {"default": False}),
                "bundle_in": ("PROMPT_BUNDLE", {"forceInput": True}),
                "resolved_names_in": ("STRING", {"forceInput": True}),
                "name_separator": (
                    "STRING",
                    {
                        "default": ", ",
                        "multiline": False,
                        "dynamicPrompts": False,
                        "placeholder": "Separator between resolved names",
                    },
                ),
            }
        }

    RETURN_TYPES = ("STRING", "STRING", "STRING", "PROMPT_BUNDLE", "STRING")
    RETURN_NAMES = (
        "selected_prompt", "selected_negative", "selected_tags", "bundle",
        "resolved_preset_name",
    )
    FUNCTION = "select_prompt"
    CATEGORY = "prompt/library"
    DESCRIPTION = "Select a multiline prompt from prompt_library.yml."

    def select_prompt(
        self,
        category,
        subcategory,
        preset,
        enabled=True,
        alias="",
        template_variable="",
        seed=0,
        prompt_override="",
        negative_override="",
        addendum_1=False,
        addendum_2=False,
        addendum_3=False,
        addendum_4=False,
        addendum_5=False,
        addendum_6=False,
        addendum_7=False,
        addendum_8=False,
        addenda_initialized=False,
        bundle_in=None,
        resolved_names_in="",
        name_separator=", ",
    ):
        entry = active_library().resolve_entry(
            category, subcategory, preset, seed, template_variable
        )
        switches = (
            addendum_1, addendum_2, addendum_3, addendum_4,
            addendum_5, addendum_6, addendum_7, addendum_8,
        )
        if addenda_initialized:
            enabled_keys = {
                item["key"] for index, item in enumerate(entry["addenda"][:8])
                if switches[index]
            }
        else:
            enabled_keys = {
                item["key"] for item in entry["addenda"] if item["default_enabled"]
            }
        chosen_addenda = [
            item for item in entry["addenda"] if item["key"] in enabled_keys
        ]
        base_prompt = str(prompt_override or "").strip() or entry["prompt"]
        base_negative = str(negative_override or "").strip() or entry["negative_prompt"]
        raw_prompt = compose_fragments(
            (
                base_prompt,
                *(item["prompt"].strip() for item in chosen_addenda),
            ),
            "\n\n",
        )
        raw_negative = ", ".join(deduplicate(
            (
                base_negative,
                *(item["negative_prompt"].strip() for item in chosen_addenda),
            )
        ))
        selected_tags_list = deduplicate((
            *entry["tags"],
            *(tag for item in chosen_addenda for tag in item["tags"]),
        ))
        selected = apply_alias(raw_prompt, alias) if enabled else ""
        selected_negative = raw_negative if enabled else ""
        variable = str(template_variable or "").strip() or entry["template_slot"]
        segment = {
            "variable": variable,
            "source": entry["template_slot"],
            "alias": str(alias or "").strip(),
            "raw_positive": raw_prompt,
            "positive": selected,
            "negative": raw_negative,
            "tags": selected_tags_list,
            "addenda": [item["key"] for item in chosen_addenda],
            "category": category,
            "subcategory": subcategory,
            "preset": entry["key"],
            "label": entry["label"],
        }
        bundle = append_bundle(bundle_in, segment if enabled else None)
        selected_tags = ", ".join(selected_tags_list) if enabled else ""
        previous_names = str(resolved_names_in or "").strip()
        current_name = (
            str(entry["label"] or "").strip()
            if enabled and entry["key"] != NONE_KEY else ""
        )
        resolved_names = str(name_separator).join(
            value for value in (previous_names, current_name) if value
        )
        return {
            "ui": {
                "resolved": [entry["label"] if enabled else "Bypassed"],
                "preview": [selected],
            },
            "result": (
                selected, selected_negative, selected_tags, bundle,
                resolved_names,
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
        enabled=True,
        alias="",
        template_variable="",
        seed=0,
        prompt_override="",
        negative_override="",
        bundle_in=None,
        resolved_names_in="",
        name_separator=", ",
    ):
        return ":".join(str(value) for value in (
            active_library().fingerprint(), category, subcategory, preset,
            enabled, alias,
            template_variable, seed, prompt_override, negative_override,
            bundle_in, resolved_names_in, name_separator,
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

    RETURN_TYPES = ("STRING", "STRING")
    RETURN_NAMES = ("positive_prompt", "negative_prompt")
    FUNCTION = "compose_template"
    CATEGORY = "prompt/library"
    DESCRIPTION = "Assemble a Prompt Bundle with a YAML natural-language template."

    def compose_template(
        self, template_category, template_subcategory, template,
        template_override="", pre_text="", post_text="",
        bundle_in=None,
    ):
        template_entry = active_library().resolve_template(
            template_category, template_subcategory, template
        )
        template_text = str(template_override or "").strip() or template_entry["template"]
        mapped_bundle = map_bundle_to_template(
            bundle_in, template_entry["slots"], template_entry["aliases"],
            template_entry["defaults"],
        )
        positive, negative, _tags = assemble_template(
            template_text, mapped_bundle, pre_text, post_text
        )
        return {
            "ui": {
                "preview": [positive],
                "negative_preview": [negative],
            },
            "result": (positive, negative),
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
            f"{active_library().fingerprint()}:{template_category}:"
            f"{template_subcategory}:{template}:{template_override}"
        )


class PromptLibraryFilenameBuilder:
    @classmethod
    def INPUT_TYPES(cls):
        return {
            "required": {
                "resolved_names": ("STRING", {"forceInput": True}),
                "separator": (
                    "STRING",
                    {"default": "_", "multiline": False, "dynamicPrompts": False},
                ),
                "include_seed": ("BOOLEAN", {"default": False}),
                "seed": (
                    "INT",
                    {"default": 0, "min": 0, "max": 0xFFFFFFFFFFFFFFFF},
                ),
            },
            "optional": {
                "prefix": ("STRING", {"default": "", "multiline": False}),
                "suffix": ("STRING", {"default": "", "multiline": False}),
                "max_length": ("INT", {"default": 160, "min": 1, "max": 240}),
            },
        }

    RETURN_TYPES = ("STRING",)
    RETURN_NAMES = ("filename_stem",)
    FUNCTION = "build_filename"
    CATEGORY = "prompt/library"
    DESCRIPTION = "Build a filesystem-safe filename stem from resolved preset names."

    def build_filename(
        self, resolved_names, separator="_", include_seed=False, seed=0,
        prefix="", suffix="", max_length=160,
    ):
        return (safe_filename_stem(
            resolved_names, prefix, suffix, separator, seed, include_seed,
            max_length,
        ),)


class PromptLibraryPromptPacket:
    @classmethod
    def INPUT_TYPES(cls):
        return {
            "required": {
                "positive_prompt": ("STRING", {"forceInput": True}),
                "packet_format": (["JSON", "Plain text"], {"default": "JSON"}),
                "seed": (
                    "INT",
                    {"default": 0, "min": 0, "max": 0xFFFFFFFFFFFFFFFF},
                ),
            },
            "optional": {
                "negative_prompt": ("STRING", {"forceInput": True}),
                "resolved_names": ("STRING", {"forceInput": True}),
                "filename_stem": ("STRING", {"forceInput": True}),
                "notes": (
                    "STRING",
                    {"default": "", "multiline": True, "dynamicPrompts": False},
                ),
            },
        }

    RETURN_TYPES = ("STRING",)
    RETURN_NAMES = ("prompt_packet",)
    FUNCTION = "build_packet"
    CATEGORY = "prompt/library"
    DESCRIPTION = "Package prompts and generation labels as JSON or readable text."

    def build_packet(
        self, positive_prompt, packet_format="JSON", seed=0,
        negative_prompt="", resolved_names="", filename_stem="", notes="",
    ):
        return (make_prompt_packet(
            positive_prompt, negative_prompt, resolved_names, filename_stem,
            seed, packet_format, notes,
        ),)


@PromptServer.instance.routes.get("/prompt-library-selector/library")
async def get_prompt_library(_request):
    try:
        library = active_library()
        catalog = library.catalog()
        catalog["library_path"] = str(library.path)
        catalog["using_user_library"] = library.path != BUILTIN_LIBRARY_PATH
        return web.json_response(catalog)
    except (OSError, UnicodeError, ValueError) as error:
        return web.json_response({"error": str(error)}, status=400)


@PromptServer.instance.routes.get("/prompt-library-selector/builder")
async def get_prompt_library_builder(_request):
    return web.FileResponse(BUILDER)


@PromptServer.instance.routes.get("/prompt-library-selector/library-source")
async def get_prompt_library_source(_request):
    library = active_library()
    try:
        return web.json_response({
            "yaml": library.path.read_text(encoding="utf-8"),
            "library_path": str(library.path),
            "using_user_library": library.path != BUILTIN_LIBRARY_PATH,
        })
    except (OSError, UnicodeError) as error:
        return web.json_response({"error": str(error)}, status=400)


@PromptServer.instance.routes.put("/prompt-library-selector/library-source")
async def put_prompt_library_source(request):
    try:
        if request.content_length and request.content_length > 10 * 1024 * 1024:
            raise ValueError("Library YAML exceeds the 10 MB save limit")
        payload = await request.json()
        target, backup = save_user_library(payload.get("yaml"))
        active_library()
        notify = getattr(PromptServer.instance, "send_sync", None)
        if notify:
            notify("prompt-library-selector-updated", {
                "library_path": str(target),
            })
        return web.json_response({
            "saved": True,
            "library_path": str(target),
            "backup_path": str(backup) if backup else None,
        })
    except (OSError, UnicodeError, ValueError, yaml.YAMLError) as error:
        return web.json_response({"error": str(error)}, status=400)


NODE_CLASS_MAPPINGS = {
    "PromptLibrarySelector": PromptLibrarySelector,
    "PromptLibraryTemplateComposer": PromptLibraryTemplateComposer,
    "PromptLibraryFilenameBuilder": PromptLibraryFilenameBuilder,
    "PromptLibraryPromptPacket": PromptLibraryPromptPacket,
}
NODE_DISPLAY_NAME_MAPPINGS = {
    "PromptLibrarySelector": "Prompt Library Selector",
    "PromptLibraryTemplateComposer": "Prompt Library Template Composer",
    "PromptLibraryFilenameBuilder": "Prompt Library Filename Builder",
    "PromptLibraryPromptPacket": "Prompt Library Prompt Packet",
}
