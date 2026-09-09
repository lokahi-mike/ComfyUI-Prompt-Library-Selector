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
Prompt Library Controller (optional shared seed + refresh)
        ↓
Prompt Library Selectors (character, outfit, pose, lighting...)
        ↓
Prompt Bundle
        ↓
Template Composer
        ↓
Positive prompt + negative prompt
```

Change a dropdown instead of rewriting a prompt. Edit the library once instead
of hunting through workflows.

## Highlights

### Prompt Library Controller

- Starts a Selector bundle chain with one shared deterministic seed
- Makes every Random Selector in that chain use the same workflow seed
- Outputs the same seed directly as `INT` and readable `Seed: …` text
- Provides **New random seed** and **Refresh entire library** buttons
- Remains optional; Selector-only workflows continue to use local seeds

### Prompt Library Selector

- Cascading **Category → Subcategory → Preset** dropdowns
- Friendly labels in the UI with stable machine keys saved in workflows
- Alphabetical sorting by friendly label
- `None` selections that safely produce empty output
- Promotable **Include preset** switch for bypassing individual subgraph parts
- Graceful fallback when a saved item is renamed or removed
- Seeded **Random** selection for repeatable batch experiments
- Editable positive and negative overrides without changing the YAML
- Per-preset optional addenda with workflow-saved toggles
- Addenda can contribute positive text, negative text, and metadata tags
- Workflow-specific subject aliases such as `Character A` and `Character B`
- Automatic Prompt Bundle chaining between selector nodes
- Manual template-variable override when automatic assignment is not desired
- One Composer-level refresh updates every selector, including subgraphs
- Live selected-prompt preview
- Resolved friendly preset-name output for labels, overlays, and filenames

The Random seed is always a non-negative integer. To reroll a Random preset,
change or increment the seed; the Selector intentionally does not use
ComfyUI's after-generation `randomize` mode because promoted subgraph widgets
can confuse that mode string with the numeric seed value.

When a Controller bundle is connected upstream, its shared seed takes priority
and the Selector's **Local random seed (no Controller)** value is ignored.

When a category defines `addenda_slots`, the Selector creates one stable
**Add:** toggle position for each slot. Presets may fill any of those positions
with their own visible label, optional text, and default. Unused positions stay
hidden. For example, the first Character slot can appear as **Add Nipple
Detail** for one preset while the first Outfit slot appears as **Add Puka Shell
Necklace** for another. Enabled positive addenda follow the preset text with
natural single-space separation before alias replacement and bundle composition.
Their negative prompts and tags join the
corresponding selector outputs. Toggle state is stored in the workflow, and a
Random preset uses the same category controls for its resolved choice.

### Template Composer

- Cascading **Template Category → Template Subcategory → Template** selection
- Natural-language templates using variables such as `{{character_a}}`
- Automatic assignment of repeated sources in bundle order
- Per-variable subject aliases
- Per-variable defaults when no selector supplies a value
- Editable workflow-local template override
- Optional pre-text and post-text
- Live positive-prompt and negative-prompt previews
- A **Template requires** checklist showing exactly what should be connected
- Automatic blank-line cleanup and omission of empty variables
- Deduplicated negative prompts

### Prompt Library Workbench

- Runs locally as a single JavaScript-only HTML page
- Visual editors for libraries and templates—raw YAML editing is optional
- Dedicated Character Builder with live atomic-preset assembly
- Private reusable character-parts collection kept out of runtime dropdowns
- Collapsible category and subcategory trees with remembered UI state
- Clone presets with automatically collision-safe stable keys
- Move presets between subcategories without losing prompts or addenda
- Copy any preset as importable JSON for transfer between libraries
- Automatic snake-case stable keys with duplicate-key validation
- Live generated YAML with internal round-trip validation
- Prompt Playground for testing complete assembled prompts offline
- Seeded Random testing and temporary per-variable overrides
- Model-neutral checks for modular, cleanly assembled prompts
- Safe JSON import packets for prompt sections created by an AI
- Dedicated [AI authoring guide](docs/AI_AUTHORING_GUIDE.md) with a copyable
  project instruction and exact import-packet examples
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
YAML-only changes do not require a restart—use **Refresh entire library** on
the Controller or Composer.

### Library file location

Keep your editable library in ComfyUI's user directory:

```text
ComfyUI/user/prompt_library_selector/prompt_library.yml
```

ComfyUI's `--user-directory` setting is respected automatically, so a relocated
user folder works without additional configuration. Create the
`prompt_library_selector` folder, copy your current `prompt_library.yml` into
it, and click **Refresh entire library**. The active location is rechecked on
every refresh and queue, so creating or moving the user library does not require
a ComfyUI restart.

If that user-owned file does not exist, the node falls back to the example
`prompt_library.yml` bundled in its custom-node directory. This gives new
installations working examples while preventing later git pulls, reinstalls,
or upgrades from overwriting your real library.

## Quick start

### 1. Build or edit your library

Open the Workbench from the same server running ComfyUI:

```text
http://127.0.0.1:8188/prompt-library-selector/builder
```

Replace the host and port if your ComfyUI address is different. You may also
open `tools/yaml-library-builder.html` directly for completely offline use.

Create presets under **Library**, create a framework under **Templates**, and
use **Prompt Playground** to verify the assembled result. When opened through
ComfyUI, **Load active library** reads the file currently in use and **Save to
ComfyUI** safely writes it to
`ComfyUI/user/prompt_library_selector/prompt_library.yml`.

The optional **Auto-save** switch writes valid changes after a short delay and
notifies open Selector and Composer nodes to refresh. It is deliberately off
when the page opens. Every server save validates the YAML, writes atomically,
and preserves the previous user file as `prompt_library.backup.yml`.

**Download YAML** and **Copy YAML** remain available for portable or completely
offline editing. Directly opening the HTML file does not grant filesystem write
access, so server load/save controls require the ComfyUI-hosted address.

### 2. Add an optional Controller

Add **Prompt Library Controller** when you want one seed for Random library
choices and image generation. Connect its `bundle` output to the first
Selector's `bundle_in`. Its `seed` output can feed a sampler directly, or you
can use the identical seed emitted later by the Composer.

Skip the Controller for a simple workflow; every Selector will continue using
its own local seed.

### 3. Add selector nodes

Add one Prompt Library Selector for every independently swappable component:

```text
Character → Wardrobe → Pose → Location → Lighting → Photography
```

Choose a category, subcategory, and preset on each node.

### 4. Chain the bundles

Connect the first selector's `bundle` output to the next selector's `bundle_in`.
Continue until the complete chain reaches the Template Composer:

```text
Controller bundle → Character bundle_in  (optional)
Character bundle  → Wardrobe bundle_in
Wardrobe bundle  → Pose bundle_in
Pose bundle      → Lighting bundle_in
Lighting bundle  → Template Composer bundle_in
```

You can reorder or omit selectors. Empty selections are ignored.

### 5. Choose a template

On Prompt Library Template Composer, choose the template category,
subcategory, and template. Its `positive_prompt` output can feed your positive
text encoder, while `negative_prompt` provides the combined negative text for
workflows that use it. Both outputs remain visible in live previews. When the
chain begins at a Controller, the Composer's `shared_seed` output can feed the
Krea or sampler seed input and `seed_text` can feed an overlay, filename, or
metadata node. Without a Controller, `shared_seed` is `0` and `seed_text` is
empty so the Composer does not imply that unrelated local Selector seeds were
shared.

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

For a coordinated workflow, start the chain with a Prompt Library Controller.
All Random Selectors use its seed but still resolve independently: the category,
subcategory, and template variable are mixed into each choice. Reusing the seed
therefore reproduces the combination without forcing every Random dropdown to
choose the same list position. Two otherwise identical Random Selectors with
the same template variable may resolve identically; assign explicit variables
such as `character_a` and `character_b` when you want distinct deterministic
random streams. The seed controls selection only; send the
Composer's `shared_seed` output to the generation node when you also want it to
control image sampling.

The selector's `resolved_preset_name` STRING output returns the friendly label
of the concrete selection—even when Random was used. Connect it to a text
overlay, filename node, contact-sheet label, or metadata node so generated
images remain identifiable.

Resolved names can also be daisy-chained between selectors. Connect one
selector's `resolved_preset_name` output to the next selector's
`resolved_names_in` input. **Resolved-name separator** controls the text placed
between names, such as `, `, ` + `, ` / `, or a newline. A selector set to
**None** contributes no name and adds no separator; an existing incoming name
chain passes through unchanged.

## Selector outputs

| Output | Purpose |
| --- | --- |
| `selected_prompt` | Resolved positive text after aliasing or override |
| `selected_negative` | Resolved negative text |
| `selected_tags` | Comma-separated metadata tags for this selection |
| `bundle` | Structured bundle for the next selector or Composer |
| `resolved_preset_name` | Friendly resolved name, optionally appended to an incoming name chain |

The individual STRING outputs are useful for inspection and conditional
workflows. Normal template workflows primarily use `bundle`.

## Bypassing selectors inside subgraphs

Every Selector has an **Include preset** switch. Promote that widget onto a
subgraph when you want workflow-level control over optional pieces such as an
individual character's outfit or pose.

When switched off, the Selector contributes no positive prompt, negative
prompt, tags, or resolved name. Its incoming Prompt Bundle and resolved-name
chain pass through unchanged, so disabling a middle Selector does not break the
rest of the chain. This is safer than ComfyUI's native node bypass for a node
with several differently typed outputs.

### Optional addenda on a subgraph

The addendum interface is designed primarily for **ComfyUI Nodes 2.0**.
Optional-addendum switches are native Boolean widgets, so they can live safely
on the outside of a subgraph. Open the subgraph and promote whichever visible
**Add:** switches you want to control from the parent, just as you promote the
category, subcategory, preset, or seed.

The promoted switches are real subgraph inputs—not a JSON field with a cosmetic
button layered over it. Their positions come from the category's stable
`addenda_slots`; changing presets changes the label, text, and default carried
by those positions without changing the subgraph interface.
Only positions configured by the selected preset are visible, up to the
category's declared capacity of eight.
For nested subgraphs, promote each desired switch once through every boundary
where it should be available.

Nodes 1.0 may also render the controls, but its widget hiding and promotion
behavior is not the primary UI contract. When troubleshooting a promoted
addendum, verify it in Nodes 2.0 before treating a Nodes 1.0 presentation
difference as a selector bug.

## Filenames and prompt packets

**Prompt Library Filename Builder** turns a resolved-name chain into a portable
filename stem. It removes filesystem-hostile punctuation, normalizes accented
characters, supports a prefix and suffix, optionally adds the seed, and limits
the result to a configurable safe length. If `resolved_names` is empty, its
output is empty—even when a prefix or seed is configured—so an empty selection
cannot create a misleading filename.

**Prompt Library Prompt Packet** collects the positive prompt, optional negative
prompt, resolved names, filename stem, seed, and notes. Choose formatted JSON
for metadata and automation, or Plain text for a readable sidecar file. Its
`prompt_packet` output is an ordinary STRING that can feed Save Text nodes or
image-metadata nodes.

```text
resolved_preset_name ──► Filename Builder ──► filename_stem
                                │
Composer positive/negative ─────┼──► Prompt Packet ──► Save Text / metadata
resolved names + seed ──────────┘
```

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
- Optional toggleable addenda, including defaults

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

### Character Builder

Build one coherent character preset from identity, age, build, proportions,
anatomy, face, hair, distinguishing features, and consistency guidance. The
live preview adds `{{subject}}` correctly, supports an optional LoRA trigger,
generates stable keys, checks destination duplicates, and can either add the
finished character directly to the Library or copy it as importable JSON.

Reusable fragments live in the Builder's separate **Private Character Parts**
collection. Save and apply parts such as a body build, face description, hair,
or identity-preservation language without putting those fragments into
`prompt_library.yml` or cluttering ComfyUI dropdowns. Parts persist in browser
storage and can be backed up or restored as JSON.

The recommended organization deliberately stays three levels deep:

```text
Characters → Actresses → Florence Pugh
Characters → Original Women → Nadia
Characters → Musicians → Example Musician
Characters → LoRA-Trained Women → Rhiannon
```

These names are conventions, not requirements. A fourth runtime hierarchy
level would add another selector to every workflow; narrower subcategories or
future search/filtering scale more cleanly.

### Prompt Playground

The Playground assembles a selected template entirely in the browser. Choose a
preset or Random value for each variable and inspect the final positive prompt,
negative prompt, and tags before spending generation credits.
Addenda appear as switches beneath the selected preset, so their combined
effect can be tested offline too.

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

Each preset editor also provides **Clone preset**, **Move preset**, and
**Copy import JSON**. Cloning creates an independent copy beside the original
with a unique stable key. Moving preserves the key unless it would collide in
the destination subcategory. When moving across categories, required addendum
controls are carried into the destination category when they fit within the
eight-control limit; otherwise the Workbench blocks the move instead of
discarding content. Copied JSON can be pasted into **Import sections** in the
same or another library.

For future requests, ask an assistant:

```text
Return these as a Prompt Library import packet.
```

For reliable results, give the assistant the complete
[AI Authoring Guide](docs/AI_AUTHORING_GUIDE.md). It documents the accepted JSON
shape, modular-writing conventions, template variables, aliases, defaults, and
a suggested—but entirely optional—library taxonomy.

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
    addenda_slots:
      body_details:
        label: "Body Details"
      identity_guardrails:
        label: "Stronger Identity Guardrails"
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
            addenda:
              identity_guardrails:
                negative_prompt: |-
                  duplicate person, altered identity
                default_enabled: true
                metadata:
                  tags: ["identity_guardrail"]
            metadata:
              tags: ["adult", "original"]
```

Keys are saved in workflows and should remain stable. Labels are presentation
text and may be renamed safely. YAML block scalars such as `|-` and `>-` work
well for long prompt text.

`addenda_slots` declares the category's stable checkbox positions, with a
maximum capacity of eight. Slot order is structural and is not changed when a
friendly label is renamed. A preset's `addenda` mapping decides which positions
are available and supplies each position's visible label, text, negative text,
tags, and default state. Positions omitted by the selected preset remain hidden.
The Workbench creates and maintains these mappings without raw YAML editing.

## Refresh and reload behavior

- After editing only `prompt_library.yml`, click **Refresh entire library** on
  a Controller or Composer. One fetch updates every Selector and Composer in
  the workflow, including nodes nested inside subgraphs.
- The YAML is read again during execution, so queued prompts use current text.
- After changing or updating Python or JavaScript files, restart ComfyUI and
  hard-refresh the browser.
- Deleted or stale saved selections return empty output rather than silently
  choosing a different preset.

## Privacy and portability

The library is a local YAML file. The Workbench is a static HTML application
with no analytics, accounts, build process, or external services. Its draft
state and private Character Parts remain in browser local storage. When opened
through ComfyUI, its same-origin API reads and writes only the local user
library described above. Nothing is uploaded by this project.

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

- Click **Refresh entire library** on the Composer.
- Check the browser console and ComfyUI output for YAML errors.
- Confirm you pulled the current Python and frontend files.
- Restart ComfyUI and perform a browser hard refresh after updating the node.

### Workbench server save is unavailable

- Open the Workbench from ComfyUI's
  `/prompt-library-selector/builder` address rather than directly from disk or
  another lightweight file server.
- Pull the current plugin version, restart ComfyUI, and hard-refresh the page.
- Fix any validation errors shown below Generated YAML before saving.
- The previous successful user file is retained as
  `prompt_library.backup.yml` beside the active library.

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
