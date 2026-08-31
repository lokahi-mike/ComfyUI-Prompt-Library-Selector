import { app } from "../../scripts/app.js";
import { api } from "../../scripts/api.js";

const NODE_TYPE = "PromptLibrarySelector";
const COMPOSER_NODE_TYPE = "PromptLibraryComposer";
const NONE_KEY = "__none__";
const NONE_LABEL = "None";
const SEPARATORS = {
    "Blank line": "\n\n",
    "New line": "\n",
    "Comma + space": ", ",
    "Space": " ",
};

function refreshComposerPreviews() {
    for (const graphNode of app.graph?._nodes ?? []) {
        graphNode._updatePromptLibraryLivePreview?.();
    }
}

function selectedLibraryPrompt(node) {
    const categoryKey = node.widgets?.find((widget) => widget.name === "category")?.value;
    const subcategoryKey = node.widgets?.find(
        (widget) => widget.name === "subcategory",
    )?.value;
    const presetKey = node.widgets?.find((widget) => widget.name === "preset")?.value;
    const category = node._promptLibraryCatalog?.find(
        (item) => item.key === categoryKey,
    );
    const subcategory = category?.subcategories?.find(
        (item) => item.key === subcategoryKey,
    );
    return subcategory?.presets?.find((item) => item.key === presetKey)?.prompt ?? "";
}

function retainOrNone(widget, items) {
    const labels = new Map([[NONE_KEY, NONE_LABEL]]);
    for (const item of items ?? []) labels.set(item.key, item.label);

    const keys = new Set(labels.keys());
    if (!keys.has(widget.value)) widget.value = NONE_KEY;
    widget.options.values = [...keys];
    widget.options.getOptionLabel = (value) => labels.get(value) ?? String(value);
}

app.registerExtension({
    name: "prompt-library-selector.cascading-selectors",

    loadedGraphNode(node) {
        if (node.comfyClass !== NODE_TYPE) return;
        node._schedulePromptLibraryReload?.();
    },

    async nodeCreated(node) {
        if (node.comfyClass === COMPOSER_NODE_TYPE) {
            setupComposer(node);
            return;
        }
        if (node.comfyClass !== NODE_TYPE) return;

        const category = node.widgets?.find((widget) => widget.name === "category");
        const subcategory = node.widgets?.find((widget) => widget.name === "subcategory");
        const preset = node.widgets?.find((widget) => widget.name === "preset");
        if (!category || !subcategory || !preset) return;

        let catalog = [];

        const updatePreset = () => {
            const selectedCategory = catalog.find((item) => item.key === category.value);
            const selectedSubcategory = selectedCategory?.subcategories?.find(
                (item) => item.key === subcategory.value,
            );
            retainOrNone(preset, selectedSubcategory?.presets ?? []);
            node.setDirtyCanvas(true, true);
            refreshComposerPreviews();
        };

        const updateSubcategory = () => {
            const selectedCategory = catalog.find((item) => item.key === category.value);
            retainOrNone(subcategory, selectedCategory?.subcategories ?? []);
            updatePreset();
        };

        const updateCategory = () => {
            retainOrNone(category, catalog);
            updateSubcategory();
        };

        category.callback = updateSubcategory;
        subcategory.callback = updatePreset;
        preset.callback = refreshComposerPreviews;

        const reload = async () => {
            try {
                const response = await api.fetchApi(
                    `/prompt-library-selector/library?t=${Date.now()}`,
                    { cache: "no-store" },
                );
                const data = await response.json();
                if (!response.ok) throw new Error(data.error || "Unable to load prompt library");
                catalog = data.categories ?? [];
                node._promptLibraryCatalog = catalog;
                updateCategory();
            } catch (error) {
                console.error("Prompt Library Selector:", error);
                catalog = [];
                node._promptLibraryCatalog = catalog;
                updateCategory();
            }
        };

        node._schedulePromptLibraryReload = () => {
            clearTimeout(node._promptLibraryReloadTimer);
            node._promptLibraryReloadTimer = setTimeout(reload, 100);
        };

        node.addWidget("button", "Refresh library", null, reload);
        await reload();
        node._schedulePromptLibraryReload();
    },
});

function setupComposer(node) {
    if (node._promptLibraryComposerReady) return;
    node._promptLibraryComposerReady = true;

    const inputNumber = (input) => Number.parseInt(input.name.slice(5), 10);
    const textInputs = () =>
        (node.inputs ?? [])
            .filter((input) => /^text_\d+$/.test(input.name))
            .sort((left, right) => inputNumber(left) - inputNumber(right));

    const updateInputs = () => {
        if (app.configuringGraph) {
            setTimeout(updateInputs, 50);
            return;
        }

        let inputs = textInputs();
        if (!inputs.length) {
            node.addInput("text_1", "STRING");
            inputs = textInputs();
        }

        let highestConnected = -1;
        for (let index = 0; index < inputs.length; index += 1) {
            if (inputs[index].link != null) highestConnected = index;
        }

        const desiredCount = Math.max(1, highestConnected + 2);
        while (inputs.length < desiredCount) {
            const nextNumber = Math.max(...inputs.map(inputNumber), 0) + 1;
            node.addInput(`text_${nextNumber}`, "STRING");
            inputs = textInputs();
        }

        while (inputs.length > desiredCount) {
            const last = inputs.at(-1);
            if (last.link != null) break;
            node.removeInput(node.inputs.indexOf(last));
            inputs = textInputs();
        }

        node.setDirtyCanvas(true, true);
    };

    const originalConnectionsChange = node.onConnectionsChange;
    node.onConnectionsChange = function () {
        originalConnectionsChange?.apply(this, arguments);
        setTimeout(updateInputs, 0);
        setTimeout(refreshComposerPreviews, 0);
    };

    const preview = document.createElement("textarea");
    preview.readOnly = true;
    preview.placeholder = "The composed prompt appears here after execution.";
    preview.rows = 8;
    preview.style.width = "100%";
    preview.style.height = "160px";
    preview.style.boxSizing = "border-box";
    preview.style.resize = "vertical";
    preview.style.padding = "8px";

    if (typeof node.addDOMWidget === "function") {
        const previewWidget = node.addDOMWidget("preview", "preview", preview, {
            serialize: false,
            hideOnZoom: false,
        });
        previewWidget.computeSize = (width) => [width, 180];
    }

    const originalExecuted = node.onExecuted;
    node.onExecuted = function (message) {
        originalExecuted?.apply(this, arguments);
        const value = Array.isArray(message?.preview)
            ? message.preview[0]
            : message?.preview;
        preview.value = value ?? "";
        node._promptLibraryLiveValue = preview.value;
    };

    node._updatePromptLibraryLivePreview = () => {
        const preText = node.widgets?.find((widget) => widget.name === "pre_text")?.value;
        const postText = node.widgets?.find((widget) => widget.name === "post_text")?.value;
        const fragments = [preText];
        for (const input of textInputs()) {
            if (input.link == null) continue;
            const link = app.graph?.links?.[input.link];
            const source = link ? app.graph?.getNodeById(link.origin_id) : null;
            let value = "";
            if (source?.comfyClass === NODE_TYPE) value = selectedLibraryPrompt(source);
            if (source?.comfyClass === COMPOSER_NODE_TYPE) {
                value = source._promptLibraryLiveValue ?? "";
            }
            value = String(value ?? "").trim();
            if (value) fragments.push(value);
        }
        fragments.push(postText);

        const separatorName = node.widgets?.find(
            (widget) => widget.name === "separator",
        )?.value;
        preview.value = fragments
            .map((value) => String(value ?? "").trim())
            .filter(Boolean)
            .join(SEPARATORS[separatorName] ?? "\n\n");
        node._promptLibraryLiveValue = preview.value;
    };

    const separatorWidget = node.widgets?.find((widget) => widget.name === "separator");
    if (separatorWidget) separatorWidget.callback = refreshComposerPreviews;

    for (const [name, label] of [
        ["pre_text", "Pre-text"],
        ["post_text", "Post-text"],
    ]) {
        const widget = node.widgets?.find((item) => item.name === name);
        if (!widget) continue;
        widget.label = label;
        const originalCallback = widget.callback;
        widget.callback = function () {
            originalCallback?.apply(this, arguments);
            refreshComposerPreviews();
        };
    }

    setTimeout(updateInputs, 0);
    setTimeout(refreshComposerPreviews, 0);
}
