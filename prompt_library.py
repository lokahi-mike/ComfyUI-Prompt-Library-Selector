from __future__ import annotations

import re
from pathlib import Path
from typing import Any, Iterable

import yaml

NONE_KEY = "__none__"
RANDOM_KEY = "__random__"
SUBJECT_PATTERN = re.compile(r"{{\s*subject\s*}}", re.IGNORECASE)
VARIABLE_PATTERN = re.compile(r"{{\s*([a-zA-Z_][a-zA-Z0-9_-]*)\s*}}")


def compose_fragments(values: Iterable[Any], separator: str) -> str:
    fragments = [str(value).strip() for value in values if value is not None]
    return separator.join(fragment for fragment in fragments if fragment)


def apply_alias(prompt: str, alias: str) -> str:
    """Replace {{subject}}, retaining the original prefix behavior as fallback."""
    prompt = str(prompt or "").strip()
    alias = str(alias or "").strip()
    if not prompt or not alias:
        return prompt
    if SUBJECT_PATTERN.search(prompt):
        return SUBJECT_PATTERN.sub(alias, prompt)
    return f"{alias}: {prompt}"


def deduplicate(values: Iterable[Any]) -> list[str]:
    result, seen = [], set()
    for value in values:
        text = str(value or "").strip()
        marker = text.casefold()
        if text and marker not in seen:
            seen.add(marker)
            result.append(text)
    return result


def make_bundle(
    segments: Iterable[dict[str, Any]] = (), shared_seed: int | None = None
) -> dict[str, Any]:
    bundle = {"segments": [dict(segment) for segment in segments if segment]}
    if shared_seed is not None:
        bundle["shared_seed"] = max(0, int(shared_seed))
    return bundle


def bundle_seed(bundle: Any) -> int | None:
    if not isinstance(bundle, dict) or "shared_seed" not in bundle:
        return None
    try:
        return max(0, int(bundle["shared_seed"]))
    except (TypeError, ValueError):
        return None


def append_bundle(bundle: Any, segment: dict[str, Any] | None) -> dict[str, Any]:
    existing = bundle.get("segments", []) if isinstance(bundle, dict) else []
    segments = [dict(item) for item in existing if isinstance(item, dict)]
    if segment and (segment.get("positive") or segment.get("negative") or segment.get("tags")):
        segments.append(dict(segment))
    return make_bundle(segments, bundle_seed(bundle))


def bundle_strings(bundle: Any, separator: str = "\n\n") -> tuple[str, str, str]:
    segments = bundle.get("segments", []) if isinstance(bundle, dict) else []
    positives = [item.get("positive", "") for item in segments if isinstance(item, dict)]
    negatives = deduplicate(item.get("negative", "") for item in segments if isinstance(item, dict))
    tags = deduplicate(tag for item in segments if isinstance(item, dict) for tag in item.get("tags", []))
    return compose_fragments(positives, separator), ", ".join(negatives), ", ".join(tags)


def map_bundle_to_template(
    bundle: Any,
    slots: dict[str, Any],
    aliases: dict[str, Any],
    defaults: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Map source-level segments to repeated template variables in bundle order."""
    incoming = [dict(item) for item in (bundle or {}).get("segments", []) if isinstance(item, dict)]
    normalized_slots = {str(key): str(value) for key, value in (slots or {}).items()}
    explicit = {
        str(item.get("variable", "")).strip()
        for item in incoming
        if str(item.get("variable", "")).strip() in normalized_slots
    }
    available: dict[str, list[str]] = {}
    for variable, source in normalized_slots.items():
        if variable not in explicit:
            available.setdefault(source, []).append(variable)

    result = []
    for segment in incoming:
        variable = str(segment.get("variable", "")).strip()
        source = str(segment.get("source", "")).strip()
        if variable not in normalized_slots and available.get(source):
            variable = available[source].pop(0)
            segment["variable"] = variable
        template_alias = str((aliases or {}).get(variable, "")).strip()
        if template_alias and not str(segment.get("alias", "")).strip():
            segment["positive"] = apply_alias(
                segment.get("raw_positive", segment.get("positive", "")),
                template_alias,
            )
        result.append(segment)
    assigned = {
        str(segment.get("variable", "")).strip() for segment in result
        if str(segment.get("variable", "")).strip()
    }
    for variable in normalized_slots:
        default = str((defaults or {}).get(variable, "") or "").strip()
        if variable in assigned or not default:
            continue
        alias = str((aliases or {}).get(variable, "") or "").strip()
        result.append({
            "variable": variable,
            "source": normalized_slots[variable],
            "alias": alias,
            "raw_positive": default,
            "positive": apply_alias(default, alias),
            "negative": "",
            "tags": [],
            "defaulted": True,
            "label": "Template default",
        })
    return make_bundle(result, bundle_seed(bundle))


def assemble_template(template_text: str, bundle: Any, pre_text: str = "", post_text: str = "") -> tuple[str, str, str]:
    """Resolve original template variables without rewriting inserted prose."""
    template_text = str(template_text or "")
    segments = bundle.get("segments", []) if isinstance(bundle, dict) else []
    by_variable: dict[str, dict[str, Any]] = {}
    for segment in segments:
        if isinstance(segment, dict) and str(segment.get("variable", "")).strip():
            by_variable[str(segment["variable"]).strip()] = segment

    variables = list(dict.fromkeys(VARIABLE_PATTERN.findall(template_text)))
    positive = template_text
    for variable in variables:
        value = str(by_variable.get(variable, {}).get("positive", "") or "")
        positive = re.sub(rf"{{{{\s*{re.escape(variable)}\s*}}}}", lambda _match: value, positive)

    positive = compose_fragments((pre_text, positive, post_text), "\n\n")
    positive = re.sub(r"[ \t]+\n", "\n", positive)
    positive = re.sub(r"\n{3,}", "\n\n", positive).strip()
    used = [by_variable[name] for name in variables if name in by_variable]
    negative = ", ".join(deduplicate(item.get("negative", "") for item in used))
    tags = ", ".join(deduplicate(tag for item in used for tag in item.get("tags", [])))
    return positive, negative, tags


class PromptLibrary:
    def __init__(self, path: Path):
        self.path = path

    def load(self) -> dict[str, Any]:
        if not self.path.exists():
            return {"version": 1, "templates": {}, "categories": {}}
        data = yaml.safe_load(self.path.read_text(encoding="utf-8")) or {}
        if not isinstance(data, dict):
            raise ValueError("prompt_library.yml must contain a YAML mapping")
        categories, templates = data.get("categories", {}), data.get("templates", {}) or {}
        if not isinstance(categories, dict):
            raise ValueError("'categories' must be a mapping")
        if not isinstance(templates, dict):
            raise ValueError("'templates' must be a mapping")
        return {"version": data.get("version", 1), "templates": templates, "categories": categories}

    def catalog(self) -> dict[str, Any]:
        data, categories = self.load(), []
        for category_key, category in self._sorted_items(data["categories"]):
            category = self._mapping(category, f"category '{category_key}'")
            category_tags = self._tags(category)
            addenda_slots = self._addenda_slots(category)
            subcategories = []
            for subcategory_key, subcategory in self._sorted_items(category.get("subcategories", {})):
                subcategory = self._mapping(subcategory, f"subcategory '{subcategory_key}'")
                subcategory_tags, presets = self._tags(subcategory), []
                for preset_key, raw_preset in self._sorted_items(subcategory.get("presets", {})):
                    preset = self._entry_mapping(raw_preset)
                    presets.append({
                        "key": str(preset_key), "label": self._label(preset_key, preset),
                        "prompt": str(preset.get("prompt", "") or ""),
                        "negative_prompt": str(preset.get("negative_prompt", "") or ""),
                        "template_slot": str(preset.get("template_slot", "") or ""),
                        "tags": deduplicate((*category_tags, *subcategory_tags, *self._tags(preset))),
                        "addenda": self._addenda(preset, addenda_slots),
                    })
                subcategories.append({"key": str(subcategory_key), "label": self._label(subcategory_key, subcategory), "tags": subcategory_tags, "presets": presets})
            categories.append({
                "key": str(category_key), "label": self._label(category_key, category),
                "template_slot": str(category.get("template_slot", "") or ""),
                "tags": category_tags, "addenda_slots": addenda_slots,
                "subcategories": subcategories,
            })

        templates = []
        template_groups = self._normalized_template_groups(data["templates"])
        for category_key, category in self._sorted_items(template_groups):
            category = self._mapping(category, f"template category '{category_key}'")
            subcategories = []
            for subcategory_key, subcategory in self._sorted_items(category.get("subcategories", {})):
                subcategory = self._mapping(subcategory, f"template subcategory '{subcategory_key}'")
                entries = []
                for template_key, template in self._sorted_items(subcategory.get("templates", {})):
                    entries.append(self._template_catalog_entry(template_key, template))
                subcategories.append({
                    "key": str(subcategory_key),
                    "label": self._label(subcategory_key, subcategory),
                    "templates": entries,
                })
            templates.append({
                "key": str(category_key),
                "label": self._label(category_key, category),
                "subcategories": subcategories,
            })
        return {"version": data["version"], "categories": categories, "templates": templates}

    def resolve_entry(self, category: str, subcategory: str, preset: str, seed: int = 0, variable: str = "") -> dict[str, Any]:
        if NONE_KEY in (category, subcategory, preset):
            return self._empty_entry()
        data = self.load()
        try:
            category_data = self._mapping(data["categories"][category], category)
            subcategory_data = self._mapping(category_data["subcategories"][subcategory], subcategory)
            presets = self._mapping(subcategory_data.get("presets", {}), subcategory)
        except (KeyError, TypeError, ValueError):
            return self._empty_entry()

        resolved_key = preset
        if preset == RANDOM_KEY:
            candidates = list(self._sorted_items(presets))
            if not candidates:
                return self._empty_entry()
            resolved_key, raw_entry = candidates[self._stable_choice(seed, variable, category, subcategory, len(candidates))]
        else:
            try:
                raw_entry = presets[preset]
            except KeyError:
                return self._empty_entry()
        entry = self._entry_mapping(raw_entry)
        return {
            "key": str(resolved_key), "label": self._label(resolved_key, entry),
            "prompt": str(entry.get("prompt", "") or ""),
            "negative_prompt": str(entry.get("negative_prompt", "") or ""),
            "template_slot": str(entry.get("template_slot") or category_data.get("template_slot") or category),
            "tags": deduplicate((*self._tags(category_data), *self._tags(subcategory_data), *self._tags(entry))),
            "addenda": self._addenda(entry, self._addenda_slots(category_data)),
        }

    def resolve(self, category: str, subcategory: str, preset: str) -> str:
        return self.resolve_entry(category, subcategory, preset)["prompt"]

    def resolve_template(
        self, category: str, subcategory: str | None = None, key: str | None = None
    ) -> dict[str, Any]:
        empty = {"key": NONE_KEY, "label": "None", "template": "", "slots": {}, "aliases": {}, "defaults": {}}
        # Retain direct flat-template resolution for imported schema-v2 files.
        if key is None:
            key = category
            raw_templates = self.load()["templates"]
            if key and key != NONE_KEY and self._templates_are_flat(raw_templates):
                try:
                    return self._template_catalog_entry(key, raw_templates[key])
                except (KeyError, TypeError, ValueError):
                    return empty
            return empty
        if NONE_KEY in (category, subcategory, key):
            return empty
        groups = self._normalized_template_groups(self.load()["templates"])
        if not key or key == NONE_KEY:
            return empty
        try:
            entry = groups[category]["subcategories"][subcategory]["templates"][key]
        except (KeyError, TypeError, ValueError):
            return empty
        return self._template_catalog_entry(key, entry)

    def fingerprint(self) -> str:
        try:
            stat = self.path.stat()
            return f"{stat.st_mtime_ns}:{stat.st_size}"
        except OSError:
            return "missing"

    @staticmethod
    def _stable_choice(seed: int, *parts: Any) -> int:
        length, value = int(parts[-1]), 2166136261
        text = ":".join(str(item) for item in (seed, *parts[:-1]))
        for byte in text.encode("utf-8"):
            value = ((value ^ byte) * 16777619) & 0xFFFFFFFF
        return value % length

    @staticmethod
    def _empty_entry() -> dict[str, Any]:
        return {"key": NONE_KEY, "label": "None", "prompt": "", "negative_prompt": "", "template_slot": "", "tags": [], "addenda": []}

    @staticmethod
    def _mapping(value: Any, context: str) -> dict[str, Any]:
        if not isinstance(value, dict):
            raise ValueError(f"{context} must be a mapping")
        return value

    @staticmethod
    def _entry_mapping(value: Any) -> dict[str, Any]:
        return {"prompt": value} if isinstance(value, str) else value if isinstance(value, dict) else {"prompt": ""}

    @staticmethod
    def _tags(value: dict[str, Any]) -> list[str]:
        metadata = value.get("metadata", {}) or {}
        tags = metadata.get("tags", []) if isinstance(metadata, dict) else []
        return [tags] if isinstance(tags, str) else deduplicate(tags if isinstance(tags, list) else [])

    @classmethod
    def _addenda_slots(cls, value: dict[str, Any]) -> list[dict[str, Any]]:
        raw = value.get("addenda_slots", {}) or {}
        if not isinstance(raw, dict):
            return []
        result = []
        # Slot keys define the stable promoted-widget positions. Keep their order
        # independent from friendly labels so renaming a label cannot reshuffle a
        # saved subgraph interface.
        for key, raw_slot in raw.items():
            slot = cls._entry_mapping(raw_slot)
            result.append({
                "key": str(key),
                "label": cls._label(key, slot),
                "default_enabled": bool(slot.get("default_enabled", False)),
            })
        return result[:8]

    @classmethod
    def _addenda(
        cls, value: dict[str, Any], slots: list[dict[str, Any]] | None = None
    ) -> list[dict[str, Any]]:
        raw = value.get("addenda", {}) or {}
        if not isinstance(raw, dict):
            return []
        result = []
        slot_items = [(slot["key"], slot) for slot in (slots or [])]
        items = slot_items or list(cls._sorted_items(raw))
        for key, slot in items:
            available = not slot_items or key in raw
            raw_addendum = raw.get(key, {}) if slot_items else slot
            addendum = cls._entry_mapping(raw_addendum)
            label = (
                addendum.get("label") or slot.get("label") or cls._label(key, addendum)
                if available
                else slot.get("label") or cls._label(key, addendum)
            )
            result.append({
                "key": str(key),
                "label": str(label),
                "prompt": str(addendum.get("prompt", "") or ""),
                "negative_prompt": str(addendum.get("negative_prompt", "") or ""),
                "default_enabled": bool(addendum.get(
                    "default_enabled", slot.get("default_enabled", False)
                )),
                "tags": cls._tags(addendum),
                "available": available,
            })
        return result[:8]

    @staticmethod
    def _label(key: Any, value: dict[str, Any]) -> str:
        return str(value.get("label") or str(key).replace("_", " ").title())

    @classmethod
    def _templates_are_flat(cls, templates: dict[str, Any]) -> bool:
        return bool(templates) and all(
            isinstance(value, dict)
            and any(field in value for field in ("template", "slots", "aliases", "defaults"))
            for value in templates.values()
        )

    @classmethod
    def _normalized_template_groups(cls, templates: dict[str, Any]) -> dict[str, Any]:
        if not templates:
            return {}
        if cls._templates_are_flat(templates):
            return {
                "general": {
                    "label": "General",
                    "subcategories": {
                        "general": {"label": "General", "templates": templates}
                    },
                }
            }
        return templates

    @classmethod
    def _template_catalog_entry(cls, key: Any, raw_entry: Any) -> dict[str, Any]:
        entry = cls._mapping(raw_entry, f"template '{key}'")
        slots = entry.get("slots", {}) or {}
        aliases = entry.get("aliases", {}) or {}
        defaults = entry.get("defaults", {}) or {}
        if not all(isinstance(value, dict) for value in (slots, aliases, defaults)):
            raise ValueError(f"template '{key}' mappings must be mappings")
        return {
            "key": str(key),
            "label": cls._label(key, entry),
            "template": str(entry.get("template", "") or ""),
            "slots": {str(name): str(value) for name, value in slots.items()},
            "aliases": {str(name): str(value) for name, value in aliases.items()},
            "defaults": {str(name): str(value) for name, value in defaults.items()},
        }

    @classmethod
    def _sorted_items(cls, value: Any):
        if value is None:
            return []
        if not isinstance(value, dict):
            raise ValueError("Library groups must be mappings")
        return sorted(value.items(), key=lambda item: cls._label(item[0], cls._entry_mapping(item[1])).casefold())
