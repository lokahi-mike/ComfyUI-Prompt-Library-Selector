import { app } from "../../scripts/app.js";
import { api } from "../../scripts/api.js";

const NODE_TYPE = "PromptLibrarySelector";
const TEMPLATE_COMPOSER_NODE_TYPE = "PromptLibraryTemplateComposer";
const NONE_KEY = "__none__";
const RANDOM_KEY = "__random__";
const NONE_LABEL = "None";

function activeGraph() {
    return app.canvas?.graph ?? app.rootGraph ?? app.graph;
}

function graphLink(linkId) {
    const links = activeGraph()?.links;
    if (links instanceof Map) return links.get(linkId) ?? links.get(String(linkId));
    return links?.[linkId] ?? links?.[String(linkId)];
}

function graphNode(nodeId) {
    return activeGraph()?.getNodeById?.(nodeId) ?? null;
}

function refreshComposerPreviews() {
    for (const node of activeGraph()?._nodes ?? []) {
        node._updatePromptLibraryLivePreview?.();
    }
}

function applyAlias(prompt, alias) {
    const text = String(prompt ?? "").trim();
    const name = String(alias ?? "").trim();
    if (!text || !name) return text;
    if (/{{\s*subject\s*}}/i.test(text)) {
        return text.replace(/{{\s*subject\s*}}/gi, name);
    }
    return `${name}: ${text}`;
}

function stableChoice(seed, parts, length) {
    let hash = 2166136261;
    for (const character of [seed, ...parts].join(":")) {
        hash ^= character.charCodeAt(0);
        hash = Math.imul(hash, 16777619);
    }
    return length ? (hash >>> 0) % length : -1;
}

function selectedLibraryEntry(node) {
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
    const candidates = subcategory?.presets ?? [];
    const variable = String(node.widgets?.find((widget) => widget.name === "template_variable")?.value ?? "").trim();
    const seed = node.widgets?.find((widget) => widget.name === "seed")?.value ?? 0;
    const preset = presetKey === RANDOM_KEY
        ? candidates[stableChoice(seed, [variable, categoryKey, subcategoryKey], candidates.length)]
        : candidates.find((item) => item.key === presetKey);
    const promptOverride = String(node.widgets?.find((widget) => widget.name === "prompt_override")?.value ?? "").trim();
    const negativeOverride = String(node.widgets?.find((widget) => widget.name === "negative_override")?.value ?? "").trim();
    const alias = String(
        node.widgets?.find((widget) => widget.name === "alias")?.value ?? "",
    ).trim();
    const libraryPositive = preset?.prompt || "";
    const libraryNegative = preset?.negative_prompt || "";
    const rawPositive = promptOverride || libraryPositive;
    return {
        variable: variable || preset?.template_slot || category?.template_slot || categoryKey || "",
        source: preset?.template_slot || category?.template_slot || categoryKey || "",
        alias,
        raw_positive: rawPositive,
        positive: applyAlias(rawPositive, alias),
        negative: negativeOverride || libraryNegative,
        library_positive: libraryPositive,
        library_negative: libraryNegative,
        tags: preset?.tags ?? [],
        label: preset?.label ?? NONE_LABEL,
        preset: preset?.key ?? NONE_KEY,
    };
}

function retainOrNone(widget, items, includeRandom = false) {
    const labels = new Map([[NONE_KEY, NONE_LABEL]]);
    if (includeRandom && items?.length) labels.set(RANDOM_KEY, "Random");
    for (const item of items ?? []) labels.set(item.key, item.label);

    const keys = new Set(labels.keys());
    if (!keys.has(widget.value)) widget.value = NONE_KEY;
    widget.options.values = [...keys];
    widget.options.getOptionLabel = (value) => labels.get(value) ?? String(value);
}

app.registerExtension({
    name: "prompt-library-selector.cascading-selectors",

    loadedGraphNode(node) {
        if (![NODE_TYPE, TEMPLATE_COMPOSER_NODE_TYPE].includes(node.comfyClass)) return;
        node._schedulePromptLibraryReload?.();
    },

    async nodeCreated(node) {
        if (node.comfyClass === TEMPLATE_COMPOSER_NODE_TYPE) {
            await setupTemplateComposer(node);
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
            retainOrNone(preset, selectedSubcategory?.presets ?? [], true);
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

        const clearOverrides = () => {
            const promptOverride = node.widgets?.find((widget) => widget.name === "prompt_override");
            const negativeOverride = node.widgets?.find((widget) => widget.name === "negative_override");
            if (promptOverride) promptOverride.value = "";
            if (negativeOverride) negativeOverride.value = "";
        };
        category.callback = () => { clearOverrides(); updateSubcategory(); };
        subcategory.callback = () => { clearOverrides(); updatePreset(); };
        preset.callback = () => {
            clearOverrides();
            refreshComposerPreviews();
        };
        const alias = node.widgets?.find((widget) => widget.name === "alias");
        if (alias) {
            alias.label = "Subject alias (optional)";
            alias.callback = refreshComposerPreviews;
        }
        for (const [name, label] of [
            ["template_variable", "Template variable"],
            ["prompt_override", "Positive override"],
            ["negative_override", "Negative override"],
            ["seed", "Random seed"],
        ]) {
            const widget = node.widgets?.find((item) => item.name === name);
            if (!widget) continue;
            widget.label = label;
            widget.callback = refreshComposerPreviews;
        }

        node.addWidget("button", "Load selected into overrides", null, () => {
            const entry = selectedLibraryEntry(node);
            const positive = node.widgets?.find((widget) => widget.name === "prompt_override");
            const negative = node.widgets?.find((widget) => widget.name === "negative_override");
            if (positive) positive.value = entry.library_positive;
            if (negative) negative.value = entry.library_negative;
            refreshComposerPreviews();
            node.setDirtyCanvas(true, true);
        });
        node.addWidget("button", "Clear overrides", null, () => {
            for (const name of ["prompt_override", "negative_override"]) {
                const widget = node.widgets?.find((item) => item.name === name);
                if (widget) widget.value = "";
            }
            refreshComposerPreviews();
            node.setDirtyCanvas(true, true);
        });
        const resolvedWidget = node.addWidget(
            "text", "Resolved preset", NONE_LABEL, null, {serialize: false},
        );
        resolvedWidget.disabled = true;
        const originalExecuted = node.onExecuted;
        node.onExecuted = function (message) {
            originalExecuted?.apply(this, arguments);
            const value = Array.isArray(message?.resolved)
                ? message.resolved[0]
                : message?.resolved;
            resolvedWidget.value = value || selectedLibraryEntry(node).label;
            node.setDirtyCanvas(true, true);
        };

        const originalConnectionsChange = node.onConnectionsChange;
        node.onConnectionsChange = function () {
            originalConnectionsChange?.apply(this, arguments);
            setTimeout(refreshComposerPreviews, 0);
        };

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
                node._promptLibraryTemplates = data.templates ?? [];
                updateCategory();
                resolvedWidget.value = selectedLibraryEntry(node).label;
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

function bundleSegmentsFromSelector(node, visited = new Set()) {
    if (!node || visited.has(node.id)) return [];
    visited.add(node.id);
    const segments = [];
    const bundleInput = node.inputs?.find((input) => input.name === "bundle_in");
    if (bundleInput?.link != null) {
        const link = graphLink(bundleInput.link);
        const source = link ? graphNode(link.origin_id) : null;
        if (source?.comfyClass === NODE_TYPE) {
            segments.push(...bundleSegmentsFromSelector(source, visited));
        }
    }
    const segment = selectedLibraryEntry(node);
    if (segment.positive || segment.negative || segment.tags?.length) segments.push(segment);
    return segments;
}

function liveTemplateAssembly(node) {
    const templateKey = node.widgets?.find((widget) => widget.name === "template")?.value;
    const template = node._promptLibraryTemplates?.find((item) => item.key === templateKey);
    const override = String(node.widgets?.find((widget) => widget.name === "template_override")?.value ?? "").trim();
    let text = override || template?.template || "";
    const input = node.inputs?.find((item) => item.name === "bundle_in");
    const link = input?.link != null ? graphLink(input.link) : null;
    const source = link ? graphNode(link.origin_id) : null;
    const segments = source?.comfyClass === NODE_TYPE
        ? bundleSegmentsFromSelector(source)
        : [];
    const byVariable = new Map();
    const templateSlots = template?.slots ?? {};
    const explicit = new Set(segments.map((item) => item.variable).filter((variable) => variable in templateSlots));
    const availableBySource = new Map();
    for (const [variable, sourceName] of Object.entries(templateSlots)) {
        if (explicit.has(variable)) continue;
        if (!availableBySource.has(sourceName)) availableBySource.set(sourceName, []);
        availableBySource.get(sourceName).push(variable);
    }
    for (const sourceSegment of segments) {
        const segment = {...sourceSegment};
        if (!(segment.variable in templateSlots)) {
            const available = availableBySource.get(segment.source);
            if (available?.length) segment.variable = available.shift();
        }
        const alias = template?.aliases?.[segment.variable];
        if (alias && !segment.alias) segment.positive = applyAlias(segment.raw_positive, alias);
        if (segment.variable) byVariable.set(segment.variable, segment);
    }
    const variables = [...new Set([...text.matchAll(/{{\s*([a-zA-Z_][a-zA-Z0-9_-]*)\s*}}/g)].map((match) => match[1]))];
    for (const variable of variables) {
        const value = byVariable.get(variable)?.positive ?? "";
        text = text.replace(new RegExp(`{{\\s*${variable}\\s*}}`, "g"), () => value);
    }
    const pre = node.widgets?.find((widget) => widget.name === "pre_text")?.value;
    const post = node.widgets?.find((widget) => widget.name === "post_text")?.value;
    const positive = [pre, text, post]
        .map((value) => String(value ?? "").trim()).filter(Boolean).join("\n\n")
        .replace(/[ \t]+\n/g, "\n").replace(/\n{3,}/g, "\n\n").trim();
    const used = variables.map((variable) => byVariable.get(variable)).filter(Boolean);
    const unique = (values) => [...new Map(values.filter(Boolean).map((value) => [String(value).trim().toLowerCase(), String(value).trim()])).values()];
    return {
        positive,
        negative: unique(used.map((item) => item.negative)).join(", "),
        tags: unique(used.flatMap((item) => item.tags ?? [])).join(", "),
    };
}

async function setupTemplateComposer(node) {
    if (node._promptLibraryTemplateComposerReady) return;
    node._promptLibraryTemplateComposerReady = true;
    const templateWidget = node.widgets?.find((widget) => widget.name === "template");
    const overrideWidget = node.widgets?.find((widget) => widget.name === "template_override");
    if (!templateWidget || !overrideWidget) return;

    const container = document.createElement("div");
    container.style.display = "grid";
    container.style.gap = "6px";
    const makePreview = (label, rows) => {
        const wrapper = document.createElement("label");
        wrapper.textContent = label;
        wrapper.style.display = "grid";
        wrapper.style.gap = "3px";
        wrapper.style.fontSize = "12px";
        const area = document.createElement("textarea");
        area.readOnly = true;
        area.rows = rows;
        area.style.width = "100%";
        area.style.boxSizing = "border-box";
        area.style.resize = "vertical";
        area.style.padding = "7px";
        wrapper.append(area);
        container.append(wrapper);
        return area;
    };
    const positivePreview = makePreview("Live positive prompt", 10);
    const negativePreview = makePreview("Combined negative prompt", 3);
    const tagsPreview = makePreview("Metadata tags", 2);
    if (typeof node.addDOMWidget === "function") {
        const widget = node.addDOMWidget("template_preview", "preview", container, {
            serialize: false,
            hideOnZoom: false,
        });
        widget.computeSize = (width) => [width, 360];
    }

    node._updatePromptLibraryLivePreview = () => {
        const assembled = liveTemplateAssembly(node);
        positivePreview.value = assembled.positive;
        negativePreview.value = assembled.negative;
        tagsPreview.value = assembled.tags;
        node._promptLibraryLiveValue = assembled.positive;
    };

    const refresh = async () => {
        try {
            const response = await api.fetchApi(
                `/prompt-library-selector/library?t=${Date.now()}`,
                {cache: "no-store"},
            );
            const data = await response.json();
            if (!response.ok) throw new Error(data.error || "Unable to load prompt library");
            node._promptLibraryTemplates = data.templates ?? [];
            retainOrNone(templateWidget, node._promptLibraryTemplates);
        } catch (error) {
            console.error("Prompt Library Template Composer:", error);
            node._promptLibraryTemplates = [];
            retainOrNone(templateWidget, []);
        }
        node._updatePromptLibraryLivePreview();
        node.setDirtyCanvas(true, true);
    };

    for (const [name, label] of [
        ["template", "Template"],
        ["template_override", "Editable template override"],
        ["pre_text", "Pre-text"],
        ["post_text", "Post-text"],
    ]) {
        const widget = node.widgets?.find((item) => item.name === name);
        if (!widget) continue;
        widget.label = label;
        const originalCallback = widget.callback;
        widget.callback = function () {
            originalCallback?.apply(this, arguments);
            node._updatePromptLibraryLivePreview();
        };
    }

    node.addWidget("button", "Load selected template for editing", null, () => {
        const selected = node._promptLibraryTemplates?.find((item) => item.key === templateWidget.value);
        overrideWidget.value = selected?.template ?? "";
        node._updatePromptLibraryLivePreview();
        node.setDirtyCanvas(true, true);
    });
    node.addWidget("button", "Use library template", null, () => {
        overrideWidget.value = "";
        node._updatePromptLibraryLivePreview();
        node.setDirtyCanvas(true, true);
    });
    node.addWidget("button", "Refresh library", null, refresh);

    node._schedulePromptLibraryReload = () => {
        clearTimeout(node._promptLibraryReloadTimer);
        node._promptLibraryReloadTimer = setTimeout(refresh, 100);
    };

    const originalConnectionsChange = node.onConnectionsChange;
    node.onConnectionsChange = function () {
        originalConnectionsChange?.apply(this, arguments);
        setTimeout(refreshComposerPreviews, 0);
    };
    const originalExecuted = node.onExecuted;
    node.onExecuted = function (message) {
        originalExecuted?.apply(this, arguments);
        positivePreview.value = Array.isArray(message?.preview) ? message.preview[0] : message?.preview ?? "";
        negativePreview.value = Array.isArray(message?.negative_preview) ? message.negative_preview[0] : message?.negative_preview ?? "";
        tagsPreview.value = Array.isArray(message?.tags_preview) ? message.tags_preview[0] : message?.tags_preview ?? "";
    };
    await refresh();
    node._schedulePromptLibraryReload();
}
