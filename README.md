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
- Prompt Library Composer with autogrowing string inputs and an execution preview
- Optional workflow-specific selector aliases for multi-subject prompts

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
4. Connect its `prompt` output to a text input or prompt-combining node.
5. After editing YAML, click **Refresh library** on the node.

The YAML is also re-read whenever the workflow executes. Invalid or deleted
saved selections intentionally return an empty string instead of selecting a
different prompt by surprise.

### Subject aliases

Each selector has an optional workflow-specific alias. Setting a character
selector's alias to `female_one` prefixes its output as `female_one: <prompt>`.
Use multiple character selectors with aliases such as `female_one` and
`female_two`, then reference those aliases from pose and composition presets.
Aliases are saved in the workflow, not the YAML library, so the same character
preset remains reusable in different scenes.

## Compose a complete prompt

Add one Prompt Library Selector for each prompt concern, such as character,
wardrobe, pose, expression, location, photography, and style. Connect their
outputs to **Prompt Library Composer** in the order they should appear.

The composer always keeps one spare `STRING` socket at the bottom. Connecting
that socket adds another, so there is no fixed input limit. It removes empty
fragments, joins the rest using the selected separator, and outputs the complete
prompt. Its read-only preview updates whenever the workflow executes. Upstream
Prompt Library Selector values also update the preview live before queueing.
Outputs from arbitrary nodes that calculate strings during execution appear
after the workflow runs because those values do not yet exist in the browser.

Optional multiline **Pre-text** and **Post-text** fields place fixed instructions
before and after all connected fragments. They participate in the live preview.
Use ordinary connected text nodes instead when those outer instructions need to
be reusable, generated, or switched elsewhere in the workflow.

Dynamic autogrow inputs currently need to remain outside ComfyUI subgraphs.

## Library format

```yaml
version: 1
categories:
  poses:                         # stable key stored in workflows
    label: Poses                 # friendly text shown in the selector
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
            metadata:
              tags: [single, standing]
```

Keep keys stable and unique within their parent group. Labels are presentation
text and can be renamed safely. YAML multiline scalars (`>-` or `|`) are ideal
for longer prompts.

## Browser-based YAML builder

Open `/prompt-library-selector/builder` on your running ComfyUI server to manage
the library with a visual editor. For example, append that path to the same
host and port used by the ComfyUI interface. You can also open
`tools/yaml-library-builder.html` directly on a local computer. It can import
this project's schema, add and remove categories,
subcategories, and presets, edit tags and multiline prompts, validate duplicate
or missing keys, copy the generated YAML, and download `prompt_library.yml`.

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
