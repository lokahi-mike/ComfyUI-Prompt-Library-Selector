# ComfyUI Prompt Bundle and Template Composer Plan

This plan deliberately leaves the current nodes unchanged until the Workbench
schema and authoring flow have settled. Implementation must preserve existing
workflow files and output indices.

## Compatibility contract

- Keep `PromptLibrarySelector` output 0 as `selected_prompt` and output 1 as
  `combined_prompt`.
- Keep the existing `category`, `subcategory`, `preset`, `alias`, `join_style`,
  and `prompt_in` behavior.
- Append new optional inputs and outputs; do not reorder serialized widgets.
- Continue accepting schema v1 libraries and schema v2 libraries without
  templates, mappings, negative prompts, or metadata.
- Continue permissive `VALIDATE_INPUTS` handling for saved dynamic selections.

## Prompt Bundle

Add a custom `PROMPT_BUNDLE` value passed between selectors and the future
template composer. It should remain an ordinary serializable Python mapping:

```text
{
  segments: [
    {
      variable: "character_a",
      source: "character",
      alias: "Character A",
      positive: "Character A is ...",
      negative: "...",
      tags: ["character", "editorial"],
      category: "characters",
      subcategory: "people",
      preset: "example_person",
      label: "Example Person"
    }
  ]
}
```

Selectors append one segment. The composer resolves template variables by
`variable`, not by source, which allows `character_a` and `character_b` to draw
independently from the same `character` catalog.

## Selector additions

Append these widgets after the existing serialized widgets:

- `template_variable`: workflow-local name such as `character_a`.
- `subject_alias`: workflow-local alias such as `Character A`.
- `seed`: deterministic resolution for a Random preset.
- `prompt_override`: empty means use the YAML positive prompt.
- `negative_override`: empty means use the YAML negative prompt.

Add optional `bundle_in` and append these outputs after the two legacy outputs:

- selected negative prompt
- combined negative prompt
- selected metadata tags
- combined metadata tags
- prompt bundle

Alias substitution replaces every case-insensitive `{{subject}}` token. For a
legacy preset without that token, retain the current `Alias: prompt` fallback.

## Random behavior

- Add `Random` only as a synthetic UI option; never write it into the library.
- Resolve it deterministically from seed plus template variable and selection
  scope.
- Return and display the concrete resolved preset label after execution.
- Changing the seed changes the choice; an unchanged seed reproduces it.

## Template Composer node

Create a separate node rather than changing the legacy string composer.

Inputs:

- Prompt Bundle
- template selected from the YAML library
- editable template override
- optional pre-text and post-text

Outputs:

- positive prompt
- negative prompt
- comma-separated deduplicated metadata tags

The node substitutes mapped variables, removes unresolved optional variables,
normalizes excess blank lines, and exposes a read-only live preview in the
frontend before queueing. It must not silently rewrite the prose or call an
online prompt expander.

## Krea 2 Turbo behavior

- Treat the positive prompt as the primary artifact sent directly to the local
  Qwen3VL text encoder.
- Preserve negative prompts for compatibility, but clearly describe that the
  recommended eight-step Turbo workflow runs with CFG disabled.
- Keep sampler settings, resolution, LoRAs, and style-reference conditioning
  outside the text bundle.
- Do not imitate Krea's hosted creativity sliders or prompt-expansion service.

## Implementation order

1. Extend the YAML parser and catalog while retaining existing return values.
2. Add pure Prompt Bundle, alias-substitution, metadata, and seeded-Random
   helpers with unit tests.
3. Extend the selector by appending inputs and outputs.
4. Add the Template Composer backend.
5. Add frontend cascading controls, override helpers, resolved-Random label,
   and live preview.
6. Test fresh nodes, saved legacy workflows, renamed or removed presets,
   malformed YAML, bundle chaining, two-character templates, and refresh.

