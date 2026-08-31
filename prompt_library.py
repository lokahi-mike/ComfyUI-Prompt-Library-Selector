from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml


NONE_KEY = "__none__"


def compose_fragments(values: list[Any], separator: str) -> str:
    """Normalize, discard empty fragments, and join them in input order."""
    fragments = [str(value).strip() for value in values if value is not None]
    return separator.join(fragment for fragment in fragments if fragment)


class PromptLibrary:
    """Load and query a prompt library without retaining stale YAML in memory."""

    def __init__(self, path: Path):
        self.path = path

    def load(self) -> dict[str, Any]:
        if not self.path.exists():
            return {"version": 1, "categories": {}}

        data = yaml.safe_load(self.path.read_text(encoding="utf-8")) or {}
        if not isinstance(data, dict):
            raise ValueError("prompt_library.yml must contain a YAML mapping")

        categories = data.get("categories", {})
        if not isinstance(categories, dict):
            raise ValueError("'categories' must be a mapping")

        return {"version": data.get("version", 1), "categories": categories}

    def catalog(self) -> dict[str, Any]:
        data = self.load()
        categories = []

        for category_key, category in self._sorted_items(data["categories"]):
            category = self._mapping(category, f"category '{category_key}'")
            subcategories = []
            for subcategory_key, subcategory in self._sorted_items(
                category.get("subcategories", {})
            ):
                subcategory = self._mapping(
                    subcategory, f"subcategory '{subcategory_key}'"
                )
                presets = []
                for preset_key, preset in self._sorted_items(
                    subcategory.get("presets", {})
                ):
                    preset = self._mapping(preset, f"preset '{preset_key}'")
                    presets.append(
                        {
                            "key": str(preset_key),
                            "label": self._label(preset_key, preset),
                            "prompt": str(preset.get("prompt", "")),
                        }
                    )
                subcategories.append(
                    {
                        "key": str(subcategory_key),
                        "label": self._label(subcategory_key, subcategory),
                        "presets": presets,
                    }
                )
            categories.append(
                {
                    "key": str(category_key),
                    "label": self._label(category_key, category),
                    "subcategories": subcategories,
                }
            )

        return {"version": data["version"], "categories": categories}

    def resolve(self, category: str, subcategory: str, preset: str) -> str:
        if NONE_KEY in (category, subcategory, preset):
            return ""

        try:
            entry = self.load()["categories"][category]["subcategories"][
                subcategory
            ]["presets"][preset]
        except (KeyError, TypeError):
            return ""

        if isinstance(entry, str):
            return entry
        if isinstance(entry, dict):
            prompt = entry.get("prompt", "")
            return prompt if isinstance(prompt, str) else str(prompt)
        return ""

    def fingerprint(self) -> str:
        try:
            stat = self.path.stat()
            return f"{stat.st_mtime_ns}:{stat.st_size}"
        except OSError:
            return "missing"

    @staticmethod
    def _mapping(value: Any, context: str) -> dict[str, Any]:
        if not isinstance(value, dict):
            raise ValueError(f"{context} must be a mapping")
        return value

    @staticmethod
    def _label(key: Any, value: dict[str, Any]) -> str:
        return str(value.get("label") or str(key).replace("_", " ").title())

    @classmethod
    def _sorted_items(cls, value: Any):
        if value is None:
            return []
        if not isinstance(value, dict):
            raise ValueError("Library groups must be mappings")
        return sorted(
            value.items(),
            key=lambda item: cls._label(item[0], cls._mapping(item[1], str(item[0]))).casefold(),
        )
