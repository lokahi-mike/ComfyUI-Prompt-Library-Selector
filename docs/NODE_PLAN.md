# ComfyUI Prompt Bundle and Template Composer Design

Implemented after the Workbench schema and authoring flow settled. The current
design deliberately uses one structured bundle path instead of retaining the
earlier string-concatenation sockets.

## Node contract

- `PromptLibrarySelector` selects and optionally edits one library segment.
- Its `bundle_in` accepts the preceding selector's bundle; its `bundle` output
  contains the complete ordered segment list.
- Its inspection outputs are `selected_prompt`, `selected_negative`, and
  `selected_tags`.
- `PromptLibraryTemplateComposer` selects templates through cascading category,
  subcategory, and template widgets, then assembles the final
  positive prompt, negative prompt, and deduplicated tags.
- Dynamic selections keep permissive `VALIDATE_INPUTS` handling so renamed or
  deleted YAML entries safely fall back to None.

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

The `alias` widget performs subject-alias substitution. Selectors also expose:

- `template_variable`: workflow-local name such as `character_a`.
- `seed`: deterministic resolution for a Random preset.
- `prompt_override`: empty means use the YAML positive prompt.
- `negative_override`: empty means use the YAML negative prompt.

Each selector accepts optional `bundle_in` and returns the selected positive,
selected negative, selected metadata tags, and the resulting prompt bundle.

Alias substitution replaces every case-insensitive `{{subject}}` token. For a
legacy preset without that token, retain the current `Alias: prompt` fallback.

## Random behavior

- Add `Random` only as a synthetic UI option; never write it into the library.
- Resolve it deterministically from seed plus template variable and selection
  scope.
- Return and display the concrete resolved preset label after execution.
- Changing the seed changes the choice; an unchanged seed reproduces it.

## Template Composer node

The Template Composer is the sole final assembly node.

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

## Model-agnostic behavior

- Keep prompt storage and composition independent of any particular checkpoint,
  text encoder, sampler, or hosted generation service.
- Expose assembled text without silently rewriting it for a specific model.
- Preserve negative prompts for workflows that use them without assuming every
  model or guidance configuration will consume them.
- Keep model-specific prompting choices in library content and user workflows,
  not in the node contract.

## Implementation order used

1. Extend the YAML parser and catalog for schema v3.
2. Add pure Prompt Bundle, alias-substitution, metadata, and seeded-Random
   helpers with unit tests.
3. Give the selector bundle chaining, overrides, aliases, and inspection outputs.
4. Add the Template Composer backend.
5. Add frontend cascading controls, override helpers, resolved-Random label,
   and live preview.
6. Test fresh nodes, renamed or removed presets, malformed YAML, bundle
   chaining, two-character templates, and refresh.
