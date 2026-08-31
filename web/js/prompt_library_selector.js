import { app } from "../../scripts/app.js";
import { api } from "../../scripts/api.js";

const NODE_TYPE = "PromptLibrarySelector";
const NONE_KEY = "__none__";
const NONE_LABEL = "None";

function valuesFor(items) {
    const values = { [NONE_LABEL]: NONE_KEY };
    for (const item of items ?? []) values[item.label] = item.key;
    return values;
}

function retainOrNone(widget, items) {
    const keys = new Set((items ?? []).map((item) => item.key));
    if (!keys.has(widget.value)) widget.value = NONE_KEY;
    widget.options.values = valuesFor(items);
}

app.registerExtension({
    name: "prompt-library-selector.cascading-selectors",

    async nodeCreated(node) {
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

        const reload = async () => {
            try {
                const response = await api.fetchApi(
                    `/prompt-library-selector/library?t=${Date.now()}`,
                    { cache: "no-store" },
                );
                const data = await response.json();
                if (!response.ok) throw new Error(data.error || "Unable to load prompt library");
                catalog = data.categories ?? [];
                updateCategory();
            } catch (error) {
                console.error("Prompt Library Selector:", error);
                catalog = [];
                updateCategory();
            }
        };

        node.addWidget("button", "Refresh library", null, reload);
        await reload();
    },
});
