# ComfyUI Prompt Library Selector

Build large, reusable prompts without rebuilding them by hand every time.

ComfyUI Prompt Library Selector keeps characters, wardrobes, poses, locations,
lighting, photography, moods, and other prompt components in one portable YAML
library. Select the pieces you want in ComfyUI, chain them together, and render
them through a reusable natural-language template.

The project also includes a private, browser-based Prompt Library Workbench for
building the YAML, organizing templates, testing combinations, and importing
AI-authored prompt sections without touching raw YAML.

## Why use it?

A conventional ComfyUI workflow often buries long prompt text inside nodes.
That works until you want to replace one character, compare ten outfits, reuse a
lighting setup, or maintain the same prompt collection across a laptop and a
RunPod instance.

This project separates reusable content from workflow wiring:

```text
prompt_library.yml
        ↓
Prompt Library Selectors (character, outfit, pose, lighting...)
        ↓
Prompt Bundle
        ↓
Template Composer
        ↓
Positive prompt + negative prompt + metadata tags
```

Change a dropdown instead of rewriting a prompt. Edit the library once instead
of hunting through workflows.

## Highlights

### Prompt Library Selector

- Cascading **Category → Subcategory → Preset** dropdowns
- Friendly labels in the UI with stable machine keys saved in workflows
- Alphabetical sorting by friendly label
- `None` selections that safely produce empty output
- Graceful fallback when a saved item is renamed or removed
- Seeded **Random** selection for repeatable batch experiments
- Editable positive and negative overrides without changing the YAML
- Workflow-specific subject aliases such as `Character A` and `Character B`
- Automatic Prompt Bundle chaining between selector nodes
- Manual template-variable override when automatic assignment is not desired
- Library refresh without restarting ComfyUI after YAML-only edits
- Live selected-prompt preview
- Resolved friendly preset-name output for labels, overlays, and filenames

### Template Composer

- Cascading **Template Category → Template Subcategory → Template** selection
- Natural-language templates using variables such as `{{character_a}}`
- Automatic assignment of repeated sources in bundle order
- Per-variable subject aliases
- Per-variable defaults when no selector supplies a value
- Editable workflow-local template override
- Optional pre-text and post-text
- Live positive-prompt, negative-prompt, and metadata previews
- A **Template requires** checklist showing exactly what should be connected
- Automatic blank-line cleanup and omission of empty variables
- Deduplicated negative prompts and metadata tags

### Prompt Library Workbench

- Runs locally as a single JavaScript-only HTML page
- Visual editors for libraries and templates—raw YAML editing is optional
- Collapsible category and subcategory trees with remembered UI state
- Automatic snake-case stable keys with duplicate-key validation
- Live generated YAML with internal round-trip validation
- Prompt Playground for testing complete assembled prompts offline
- Seeded Random testing and temporary per-variable overrides
- Model-neutral checks for modular, cleanly assembled prompts
- Safe JSON import packets for prompt sections created by an AI
- Browser-local autosave, with no analytics or external service calls

## Installation

From the `custom_nodes` directory inside ComfyUI:

```bash
git clone https://github.com/lokahi-mike/ComfyUI-Prompt-Library-Selector.git
cd ComfyUI-Prompt-Library-Selector
python -m pip install -r requirements.txt
```

Fully restart ComfyUI after installation. The nodes appear under:

```text
Add Node → prompt → library
```

The only Python dependency is [PyYAML](https://pyyaml.org/).

### Updating

From the installed custom-node directory:

```bash
git pull
python -m pip install -r requirements.txt
```

Restart ComfyUI and hard-refresh the browser after Python or frontend updates.
YAML-only changes do not require a restart—use **Refresh library** on a node.

## Quick start

### 1. Build or edit your library

Open the Workbench from the same server running ComfyUI:

```text
http://127.0.0.1:8188/prompt-library-selector/builder
```

Replace the host and port if your ComfyUI address is different. You may also
open `tools/yaml-library-builder.html` directly for completely offline use.

Create presets under **Library**, create a framework under **Templates**, and
use **Prompt Playground** to verify the assembled result. Download the generated
YAML as `prompt_library.yml` and place it in this custom-node folder.

The Workbench deliberately does not overwrite server files. Its working state
is stored in that browser, and **Download YAML** or **Copy YAML** gives you the
finished library.

### 2. Add selector nodes

Add one Prompt Library Selector for every independently swappable component:

```text
Character → Wardrobe → Pose → Location → Lighting → Photography
```

Choose a category, subcategory, and preset on each node.

### 3. Chain the bundles

Connect the first selector's `bundle` output to the next selector's `bundle_in`.
Continue until the complete chain reaches the Template Composer:

```text
Character bundle → Wardrobe bundle_in
Wardrobe bundle  → Pose bundle_in
Pose bundle      → Lighting bundle_in
Lighting bundle  → Template Composer bundle_in
```

You can reorder or omit selectors. Empty selections are ignored.

### 4. Choose a template

On Prompt Library Template Composer, choose the template category,
subcategory, and template. Its `positive_prompt` output can feed your positive
text encoder. Optional outputs provide the combined negative prompt and
deduplicated metadata tags.

The live **Template requires** panel shows whether each variable is connected,
which library source it expects, and which preset currently fills it.

## Aliases and multiple characters

Reusable character and wardrobe presets should use `{{subject}}` instead of
hard-coding `Female A`, `Character B`, or a specific name:

```text
{{subject}} wears a fitted black leather jacket with a weathered finish.
```

The template defines the role for each variable:

```yaml
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
```

When two character selectors enter the bundle, the first is assigned to
`character_a` and the second to `character_b`. The aliases transform
`{{subject}}` appropriately during composition. Set a selector's **Template
variable** only when you need to override this automatic assignment.

## Template defaults

Every template variable can have a **Default when unconnected** value. A default
is used only when no incoming selector fills that variable; a connected selector
always wins.

Keep the template syntax simple:

```text
{{character_a}}

{{outfit_a}}

{{location}}
```

Store fallbacks separately:

```yaml
defaults:
  outfit_a: "{{subject}} wears a simple black dress."
  location: "The scene takes place in a quiet photography studio."
```

Defaults support punctuation, quotes, colons, and multiline text. They may also
contain `{{subject}}`, which uses that variable's alias.

## Random selections and resolved names

Choose **Random** on any preset selector to resolve a real preset at execution
time. The result is deterministic for the same seed, making experiments
repeatable. Change or increment the seed to reroll.

The selector's `resolved_preset_name` STRING output returns the friendly label
of the concrete selection—even when Random was used. Connect it to a text
overlay, filename node, contact-sheet label, or metadata node so generated
images remain identifiable.

## Selector outputs

| Output | Purpose |
| --- | --- |
| `selected_prompt` | Resolved positive text after aliasing or override |
| `selected_negative` | Resolved negative text |
| `selected_tags` | Comma-separated metadata tags for this selection |
| `bundle` | Structured bundle for the next selector or Composer |
| `resolved_preset_name` | Friendly name of the concrete selected preset |

The individual STRING outputs are useful for inspection and conditional
workflows. Normal template workflows primarily use `bundle`.

## Prompt Library Workbench

### Library tab

Organize reusable snippets into categories, subcategories, and presets. Each
category can define a default template slot such as `character`, `outfit`,
`pose`, `location`, `lighting`, `photography`, or `mood`.

Each preset supports:

- Friendly label and stable key
- Multiline positive prompt
- Optional negative prompt
- Optional template-slot override
- Optional metadata tags

New keys follow the label automatically until manually edited. Categories and
subcategories start collapsed, remember their state, and can be expanded or
collapsed together.

### Templates tab

Templates are complete prompt frameworks organized into their own category and
subcategory hierarchy. Write natural prose with variable placeholders, then
configure each variable's library source, optional subject alias, and optional
default when unconnected.

The sample preview updates immediately. Template text can remain scene-specific
while characters, wardrobes, poses, lighting, and other useful pieces stay
swappable.

### Prompt Playground

The Playground assembles a selected template entirely in the browser. Choose a
preset or Random value for each variable and inspect the final positive prompt,
negative prompt, and tags before spending generation credits.

Temporary overrides let you experiment without modifying the library. **Load
selected text** copies a preset into the override editor; **Use library
original** discards the temporary edit.

The model-neutral advisory checks flag common composition problems such as fixed
legacy aliases, missing `{{subject}}` placeholders, unresolved variables,
duplicated paragraphs, redundant modular section headings, and sentence
fragments. These are warnings only—the Workbench never rewrites your prose or
dictates a particular prompting style.

### Import AI-created sections

Use **Import sections** when ChatGPT, Grok, or another assistant creates new
prompt components. Paste a JSON import packet, preview exactly where each item
will be placed, and merge it into the current Workbench library.

The importer accepts one preset or template object, an array of objects, or an
object containing an `items` array. Missing categories and subcategories are
created automatically. Existing item keys in the same destination are skipped
instead of overwritten. Click **Insert example** for a complete packet.

For future requests, ask an assistant:

```text
Return these as a Prompt Library import packet.
```

## YAML format

The Workbench manages this structure automatically, but the file remains
readable and hand-editable:

```yaml
version: 3

templates:
  solo:
    label: "Solo"
    subcategories:
      portraits:
        label: "Portraits"
        templates:
          environmental_portrait:
            label: "Environmental Portrait"
            slots:
              character_a: "character"
              outfit_a: "outfit"
              location: "location"
              lighting: "lighting"
            aliases:
              character_a: "Character A"
              outfit_a: "Character A"
            defaults:
              outfit_a: "{{subject}} wears a simple black dress."
            template: |-
              {{character_a}}

              {{outfit_a}}

              {{location}}

              {{lighting}}

categories:
  characters:
    label: "Characters"
    template_slot: "character"
    metadata:
      tags: ["subject"]
    subcategories:
      original_characters:
        label: "Original Characters"
        presets:
          example_character:
            label: "Example Character"
            prompt: |-
              {{subject}} is an adult woman with a confident expression and a
              naturally proportioned build.
            negative_prompt: |-
              distorted face, inconsistent identity
            metadata:
              tags: ["adult", "original"]
```

Keys are saved in workflows and should remain stable. Labels are presentation
text and may be renamed safely. YAML block scalars such as `|-` and `>-` work
well for long prompt text.

## Refresh and reload behavior

- After editing only `prompt_library.yml`, click **Refresh library**.
- The YAML is read again during execution, so queued prompts use current text.
- After changing or updating Python or JavaScript files, restart ComfyUI and
  hard-refresh the browser.
- Deleted or stale saved selections return empty output rather than silently
  choosing a different preset.

## Privacy and portability

The library is a local YAML file. The Workbench is a static HTML application
with no analytics, accounts, build process, or external API calls. Its draft
state remains in browser local storage. Nothing is uploaded by this project.

One file can be copied between computers, synchronized privately, backed up, or
versioned with Git. A database is not required for ordinary-sized libraries.

## Troubleshooting

### The nodes do not appear

- Confirm the repository is directly inside `ComfyUI/custom_nodes`.
- Confirm `__init__.py` exists directly inside the repository folder.
- Install `requirements.txt` using the same Python environment that launches
  ComfyUI.
- Inspect the ComfyUI startup output for `IMPORT FAILED` messages.
- Fully restart ComfyUI; refreshing the web page alone does not load Python
  nodes.

### Dropdowns show only None or red values

- Click **Refresh library**.
- Check the browser console and ComfyUI output for YAML errors.
- Confirm you pulled the current Python and frontend files.
- Restart ComfyUI and perform a browser hard refresh after updating the node.

### The Workbench does not overwrite prompt_library.yml

This is intentional. Use **Download YAML** and replace the file yourself. Keep a
backup if the library contains important custom work.

### Negative prompts seem ineffective

Negative-prompt behavior depends on the model, text encoder, sampler, guidance
configuration, and workflow. The selector and Composer preserve and combine the
text, but your generation pipeline determines whether and how it is used.

## Compatibility

The current workflow uses the schema-v3 Prompt Bundle and Template Composer
design. Older workflows built around the removed `prompt_in` or
`combined_prompt` interface must be rebuilt. Flat schema-v2 templates can still
be imported; the Workbench places them under General / General and exports them
in schema-v3 format.

See [docs/NODE_PLAN.md](docs/NODE_PLAN.md) for the underlying node contract and
design notes.

## License

[MIT](LICENSE)
