# AI Authoring Guide

This document teaches an AI assistant how to create content for ComfyUI Prompt
Library Selector. It is intentionally model-neutral: the library can contain
photographic prompts, illustrations, environments, products, creatures, audio
visualizations, or any other reusable text.

The taxonomy below is a recommended convention, not a required schema. Users
may create any category, subcategory, template slot, or prose style that suits
their workflow.

## Ready-to-copy project instruction

Copy the following block into the project instructions for the AI that will
help maintain your library:

```text
You are an author for ComfyUI Prompt Library Selector. Create modular prompt
snippets and complete templates that can be imported into its browser-based
Prompt Library Workbench.

Return only valid JSON unless I explicitly ask for discussion. Never wrap the
JSON in Markdown fences. Use this outer form:

{"items": [ ... ]}

Every reusable snippet is a preset item with:
- type: "preset"
- category: an object containing stable key, friendly label, and optionally
  template_slot; imported addenda automatically create missing category controls
- subcategory: an object containing stable key and friendly label
- key: a stable snake_case identifier
- label: a friendly display name
- prompt: the positive prompt text
- optional negative_prompt
- optional template_slot override
- optional tags array
- optional addenda object containing toggleable prompt fragments

Every complete prompt framework is a template item with:
- type: "template"
- category and subcategory objects
- stable key and friendly label
- template containing placeholders such as {{character_a}}
- slots mapping every placeholder to the source library slot
- optional aliases mapping a placeholder to the subject name that should
  replace {{subject}} inside the selected snippet
- optional defaults mapping a placeholder to text used when it is unconnected

Stable keys use ASCII snake_case, start with a letter or underscore, and must
remain unchanged once workflows use them. Friendly labels may be renamed.

Write snippets so they describe only their own concern. Keep wardrobe out of
characters, camera framing out of poses, lighting out of locations, and scene
objects out of composition unless those details are inseparable. Use the
literal {{subject}} placeholder when a snippet must refer to its assigned
character. Do not include section headings unless I request them. Avoid
sentence fragments when the target model benefits from natural language.

Characters should usually be atomic, coherent presets. Do not turn every body,
face, hair, or anatomy trait into an independently randomized runtime snippet
unless I explicitly request that design. When writing a detailed original
character, keep identity, age, stature, build, proportions, face, hair, and
persistent distinguishing traits together in one character preset.

Before returning JSON, verify that it parses, every item has a unique key in
its destination category/subcategory, every template placeholder has a slots
entry, aliases are used only when subject substitution is needed, and all
newlines inside JSON strings are escaped correctly.
```

Addenda are optional extensions to a preset. Their stable keys identify shared
controls at the category level; the Workbench automatically adds a missing
category control when importing an addendum. Each addendum has a friendly label
and any combination of `prompt`, `negative_prompt`, and `tags`. Set
`default_enabled` to `true` only when the fragment should be active
until the user explicitly disables it. Keep the base preset complete and use
addenda for genuinely optional detail rather than splitting it into dozens of
tiny required fragments.

You can add model-specific preferences after that instruction. For example,
you might ask for concise natural-language prose, tag-oriented prompting, or a
particular model's preferred ordering without changing the import format.

## Import packet format

Open the Workbench, choose **Import sections**, paste the JSON, select
**Preview import**, and then merge it. The importer adds missing categories and
subcategories automatically. If the same item key already exists in the same
destination, it is skipped rather than overwritten.

The importer accepts any of these outer forms:

```json
{"items": [{"type": "preset"}]}
```

```json
[{"type": "preset"}, {"type": "template"}]
```

```json
{"type": "preset"}
```

The `items` wrapper is recommended because it works cleanly for one item or a
large mixed packet.

### Preset example

```json
{
  "items": [
    {
      "type": "preset",
      "category": {
        "key": "lighting",
        "label": "Lighting",
        "template_slot": "lighting"
      },
      "subcategory": {
        "key": "neon",
        "label": "Neon"
      },
      "key": "rainy_neon",
      "label": "Rainy Neon",
      "prompt": "Soft cyan and magenta neon mixes with warm storefront light, creating restrained colored highlights and long reflections across rain-damp surfaces.",
      "negative_prompt": "flat lighting, clipped highlights",
      "tags": ["night", "neon", "rain"],
      "addenda": {
        "stronger_reflections": {
          "label": "Stronger Reflections",
          "prompt": "Elongated colored reflections remain especially visible across the wet pavement.",
          "tags": ["reflections"]
        },
        "highlight_guardrails": {
          "label": "Highlight Guardrails",
          "negative_prompt": "blown neon highlights",
          "default_enabled": true
        }
      }
    }
  ]
}
```

`type: "snippet"` is accepted as an alias for `type: "preset"`. The importer
also understands `stable_key` in place of `key`, but `key` is preferred.

### Character preset example

```json
{
  "items": [
    {
      "type": "preset",
      "category": {
        "key": "characters",
        "label": "Characters",
        "template_slot": "character"
      },
      "subcategory": {
        "key": "original_characters",
        "label": "Original Characters"
      },
      "key": "mara_vale",
      "label": "Mara Vale",
      "prompt": "{{subject}} is an adult woman with a compact, naturally strong build, warm brown skin, an oval face, dark expressive eyes, and shoulder-length black curls. Her composed manner and small scar through her left eyebrow remain consistent across the series.",
      "negative_prompt": "inconsistent identity, altered age, altered build",
      "tags": ["adult", "original_character"]
    }
  ]
}
```

The literal `{{subject}}` token is replaced by the selector or template alias,
such as `Character A`. This makes one preset safe to reuse in solo and
multi-character templates.

### Template example

```json
{
  "items": [
    {
      "type": "template",
      "category": {
        "key": "dual",
        "label": "Two Characters"
      },
      "subcategory": {
        "key": "environmental",
        "label": "Environmental"
      },
      "key": "two_character_environmental_portrait",
      "label": "Two-Character Environmental Portrait",
      "slots": {
        "character_a": "character",
        "outfit_a": "outfit",
        "pose_a": "pose",
        "character_b": "character",
        "outfit_b": "outfit",
        "pose_b": "pose",
        "interaction": "interaction",
        "location": "location",
        "composition": "composition",
        "lighting": "lighting",
        "photography": "photography",
        "performance": "performance"
      },
      "aliases": {
        "character_a": "Character A",
        "outfit_a": "Character A",
        "pose_a": "Character A",
        "character_b": "Character B",
        "outfit_b": "Character B",
        "pose_b": "Character B"
      },
      "defaults": {
        "interaction": "The two characters occupy the scene naturally without forced physical interaction."
      },
      "template": "{{character_a}}\n\n{{outfit_a}}\n\n{{pose_a}}\n\n{{character_b}}\n\n{{outfit_b}}\n\n{{pose_b}}\n\n{{interaction}}\n\n{{location}}\n\n{{composition}}\n\n{{lighting}}\n\n{{photography}}\n\n{{performance}}"
    }
  ]
}
```

Each placeholder in `template` should appear in `slots`. Repeated source slots
such as `character` are assigned in bundle order unless selectors explicitly
set their template variables. Defaults fill only variables that receive no
connected value.

## Recommended modular boundaries

These category names are suggestions, not reserved words:

| Category | Owns | Should normally avoid |
| --- | --- | --- |
| Characters | Identity and persistent physical traits | Wardrobe, pose, lighting, location |
| Outfits | Clothing, accessories, worn-material behavior | Pose, camera, environment |
| Individual poses | One subject's posture or movement | Lens, lighting, unrelated props |
| Interactions | Spatial and emotional relationship among participants | Individual identities and wardrobes |
| Locations | Physical place and persistent contents | Camera, pose, transient lighting |
| Composition | Framing, visual emphasis, subject placement | Detailed appearance and wardrobe |
| Lighting | Sources, direction, softness, color, shadows | Lens and body position |
| Photography | Camera distance, viewpoint, lens character, depth, finish | Wardrobe and identity |
| Performance | Expression, gaze, camera awareness, emotional behavior | Anatomy and scene construction |
| Style / Medium | Photograph, illustration, painting, 3D, genre treatment | Subject-specific facts |
| Actions | Events such as walking, dressing, or opening a door | Photographic treatment |
| Props / Vehicles | Swappable object appearance | Character-object interaction |
| Atmosphere / Weather | Rain, fog, steam, snow, dust | Permanent location architecture |

Not every scene should be decomposed into every category. If a pose depends on
a motorcycle, bench, doorway, or another participant, keep the inseparable
relationship in an interaction snippet or in the complete template. Modularize
only the pieces the user will actually want to swap.

## Character-authoring checklist

For an original or LoRA-backed character, consider these fields while drafting
one coherent preset:

- Identity or trigger phrase
- Adult age or age range
- Height and stature
- Overall build and weight distribution
- Torso, waist, chest, hips, limbs, and other persistent proportions
- Skin, face, eyes, hair, and distinguishing features
- Identity-preservation or consistency language
- Traits that should not drift, placed in `negative_prompt` when appropriate

Only include details the user supplies or explicitly requests. Avoid internal
contradictions such as simultaneously describing an extremely narrow waist and
a broad, straight torso. Prefer observable visual language over measurements
unless exact measurements are important to the character design.

### Private character parts

The Workbench Character Builder can keep reusable authoring fragments in a
separate browser-local collection. These parts are not prompt-library presets
and never appear in ComfyUI dropdowns. Normally, an AI should return a finished
character preset import packet. If the user explicitly requests reusable
Character Builder parts, use this backup-compatible shape:

```json
{
  "version": 1,
  "parts": {
    "identity": [],
    "age": [],
    "build": [
      {
        "key": "compact_grounded_build",
        "label": "Compact Grounded Build",
        "text": "She has a compact, naturally full build with grounded proportions."
      }
    ],
    "proportions": [],
    "anatomy": [],
    "face": [],
    "hair": [],
    "features": [],
    "consistency": []
  }
}
```

The allowed part types are exactly those keys. Each part requires a unique
stable `key`, friendly `label`, and reusable `text`. Keep the text limited to
that part's concern so it can combine cleanly with other parts.

## JSON safety rules

- Return strict JSON: double quotes, no comments, and no trailing commas.
- Escape newlines inside string values as `\n`; do not insert raw line breaks
  inside a JSON string.
- Stable keys should match `^[a-zA-Z_][a-zA-Z0-9_-]*$`.
- A preset requires non-empty `prompt` text.
- A template requires non-empty `template` text.
- Category and subcategory may be strings, but objects with both `key` and
  `label` are clearer and safer.
- Put the category's shared `template_slot` on the category object. Use an
  item-level `template_slot` only to override it.
- Tags are optional organizational metadata; they do not change the assembled
  prompt unless another workflow intentionally consumes them.
- Do not overwrite an existing stable key accidentally. Use a new key for a
  genuinely different preset.

## What the AI should return

When the user asks for importable content, the ideal response contains the JSON
packet only. Discussion, alternatives, and warnings should be provided before
the final packet only when the user asks for them; otherwise they make copying
into the importer needlessly annoying.
