# ComfyUI Prompt Library Selector

A small ComfyUI custom node for keeping reusable prompts in one readable YAML
file. Choose **Category → Subcategory → Preset** and receive the selected
multiline prompt as a `STRING`.

## Features

- One `prompt_library.yml` for the whole library
- Cascading selectors with friendly labels and stable saved keys
- Alphabetical sorting by label
- `None` at every level, producing an empty string
- Safe fallback to `None` when a saved category, subcategory, or preset is gone
- **Refresh library** button; YAML edits do not require a ComfyUI restart
- Reloads YAML during execution, so queued prompts always use current content
- Optional `metadata` at every level for future fields such as `tags`
- Optional workflow-specific selector aliases for multi-subject prompts
- Offline template authoring and prompt assembly playground
- Prompt Bundle chaining with automatic repeated-slot assignment
- YAML Template Composer with live positive, negative, and metadata previews
- Seeded `Random` preset selection and editable per-selector overrides

## Installation

From your ComfyUI directory:

```bash
cd custom_nodes
git clone https://github.com/lokahi-mike/ComfyUI-Prompt-Library-Selector.git
cd ComfyUI-Prompt-Library-Selector
python -m pip install -r requirements.txt
```

Restart ComfyUI once after installation. Find the node at
**Add Node → prompt → library → Prompt Library Selector**.

## Usage

1. Edit `prompt_library.yml` in this node's folder.
2. Add or select the Prompt Library Selector node.
3. Choose a category, subcategory, and preset.
4. Daisy-chain each selector's `bundle` output into the next selector's
   `bundle_in` socket, then connect the final bundle to Prompt Library Template
   Composer.
5. After editing YAML, click **Refresh library** on the node.

The YAML is also re-read whenever the workflow executes. Invalid or deleted
saved selections intentionally return an empty string instead of selecting a
different prompt by surprise.

### Subject aliases

Each selector has an optional workflow-specific alias. When a preset contains
`{{subject}}`, the alias replaces that placeholder everywhere in the preset.
Legacy presets without the placeholder retain the original
`alias: <prompt>` prefix behavior.
Aliases are saved in the workflow, not the YAML library, so the same character
preset remains reusable in different scenes.

## Compose with a YAML template

Daisy-chain selectors using their Prompt Bundle sockets:

```text
Character A bundle → Character B bundle_in
Character B bundle → Wardrobe A bundle_in
Wardrobe A bundle → Wardrobe B bundle_in
Wardrobe B bundle → Template Composer bundle_in
```

Choose **Template Category → Template Subcategory → Template** in **Prompt
Library Template Composer**. Its three
outputs are the assembled positive prompt, combined negative prompt, and
deduplicated metadata tags. All three have live previews before queueing.

Incoming selectors are assigned by source and connection order. With template
slots `character_a: character` and `character_b: character`, the first connected
character becomes `character_a` and the second becomes `character_b`. Template
aliases then resolve `{{subject}}` to `Character A` and `Character B`. Set a
selector's optional **Template variable** only when you want to override this
automatic assignment.

Each selector also provides:

- **Random**, resolved reproducibly from its seed
- positive and negative editable overrides
- buttons to load the selected YAML text into those overrides or clear them
- selected positive, negative, and tag outputs for inspection or optional
  downstream use
- the concrete resolved preset label after execution

The Template Composer's editable override is empty by default, which keeps it
synced to the YAML template. **Load selected template for editing** creates a
workflow-local copy; **Use library template** clears that copy and resumes using
the YAML version.

## Library format

```yaml
version: 3
templates:
  dual:
    label: Dual
    subcategories:
      cinematic:
        label: Cinematic
        templates:
          two_character_editorial:
            label: Two-Character Editorial
            slots:
              character_a: character
              character_b: character
              outfit_a: outfit
              outfit_b: outfit
            aliases:
              character_a: Character A
              character_b: Character B
              outfit_a: Character A
              outfit_b: Character B
            template: |-
              {{character_a}}
              {{character_b}}
              [WARDROBE]
              {{outfit_a}}
              {{outfit_b}}
              {{pose}}
              {{location}} {{lighting}} {{photography}} {{mood}}

categories:
  poses:                         # stable key stored in workflows
    label: Poses                 # friendly text shown in the selector
    template_slot: pose
    metadata:
      tags: [composition]
    subcategories:
      standing:
        label: Standing
        presets:
          relaxed:
            label: Relaxed Stance
            prompt: >-
              A relaxed standing pose with natural posture and grounded feet.
            negative_prompt: >-
              stiff posture, floating feet
            metadata:
              tags: [single, standing]
```

Keep keys stable and unique within their parent group. Labels are presentation
text and can be renamed safely. YAML multiline scalars (`>-` or `|`) are ideal
for longer prompts.

## Browser-based YAML builder

Open `/prompt-library-selector/builder` on your running ComfyUI server to use
the Prompt Library Workbench. For example, append that path to the same host
and port used by the ComfyUI interface. You can also open
`tools/yaml-library-builder.html` directly on a local computer with no server.

The **Library** tab manages categories, subcategories, presets, positive and
negative prompt text, template slots, and tags. The **Templates** tab organizes
full prompt frameworks under template categories and subcategories, then creates
named `{{variable}}` inlays with an immediate sample preview. Every variable
has its own library source and optional alias. For example, `character_a` and
`character_b` can both draw from `character`, while replacing `{{subject}}` in
their selected presets with `Character A` and `Character B`. The ready-made
**Two characters** template wires this up for two characters and their separate
wardrobes.

The **Prompt Playground** fills those variables from the library and displays the final
positive prompt, combined negative prompt, and deduplicated metadata tags. It
also supports reproducible seeded random choices and temporary per-variable
edits that do not modify the underlying presets. **Load selected text** copies
a chosen segment into its editable override; **Use library original** discards
that preview-only customization.

For local Krea 2 Turbo workflows, the Workbench provides advisory prompt checks
without changing or rejecting your text. It flags fixed aliases such as
`Female A`, subject-specific character or wardrobe presets missing
`{{subject}}`, section headings that are unnecessary in a modular template,
unfinished sentence fragments, unresolved variables, and duplicated assembled
paragraphs. Negative prompts remain available for compatibility, but essential
constraints should also be stated positively because the recommended Turbo
workflow runs with CFG disabled.
Categories and subcategories start collapsed, remember their expanded state in
the browser, and can be expanded or collapsed together. Entries and generated
YAML are sorted alphabetically by friendly label. Newly created entries derive
snake-case stable keys from their labels until the key is manually edited;
imported keys remain unchanged unless explicitly regenerated. Duplicate keys
are reported inline and in the validation status.

Tags are optional metadata. They do not alter prompt text, but selectors and the
Template Composer now expose them as deduplicated comma-separated strings for
embedding in saved image metadata or downstream routing.

Schema v3 adds nested template categories and subcategories to the bundle-only
node workflow described in
[`docs/NODE_PLAN.md`](docs/NODE_PLAN.md). Workflows made with the earlier
`prompt_in`/`combined_prompt` design must be rebuilt after upgrading.
Flat schema-v2 templates still import into a General / General group and are
exported in the nested schema-v3 format.

Builder state is autosaved in that browser's local storage. The page has no
server, build step, analytics, or external dependencies, and library content
never leaves the browser.

## Notes

- The browser extension calls a read-only local ComfyUI route to refresh the
  catalog. The prompt library is not sent to any external service.
- A YAML syntax error is reported in the browser console and the selectors fall
  back to `None`; correct the file and click **Refresh library** again.
- Copy `prompt_library.yml` before replacing it if you have built a large custom
  library.

## License

MIT
