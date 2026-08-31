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

## Notes

- The browser extension calls a read-only local ComfyUI route to refresh the
  catalog. The prompt library is not sent to any external service.
- A YAML syntax error is reported in the browser console and the selectors fall
  back to `None`; correct the file and click **Refresh library** again.
- Copy `prompt_library.yml` before replacing it if you have built a large custom
  library.

## License

MIT
