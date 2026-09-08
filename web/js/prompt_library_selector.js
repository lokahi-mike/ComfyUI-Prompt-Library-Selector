import { app } from "../../scripts/app.js";
import { api } from "../../scripts/api.js";

const NODE_TYPE = "PromptLibrarySelector";
const TEMPLATE_COMPOSER_NODE_TYPE = "PromptLibraryTemplateComposer";
const NONE_KEY = "__none__";
const RANDOM_KEY = "__random__";
const NONE_LABEL = "None";
let globalLibraryRefreshTimer;
let lastLibraryCatalog;

function activeGraph() {
    return app.canvas?.graph ?? app.rootGraph ?? app.graph;
}

function rootGraph(contextNode) {
    return contextNode?.graph?.rootGraph
        ?? activeGraph()?.rootGraph
        ?? app.rootGraph
        ?? app.graph
        ?? activeGraph();
}

function graphLink(graph, linkId) {
    const links = graph?._links ?? graph?.links;
    if (links instanceof Map) {
        return links.get(linkId) ?? links.get(Number(linkId)) ?? links.get(String(linkId));
    }
    return links?.[linkId] ?? links?.[String(linkId)];
}

function graphNode(graph, nodeId) {
    return graph?.getNodeById?.(nodeId)
        ?? graph?._nodes?.find((node) => String(node.id) === String(nodeId))
        ?? null;
}

function visitGraphNodes(graph, callback, visited = new Set()) {
    if (!graph || visited.has(graph)) return;
    visited.add(graph);
    for (const node of graph._nodes ?? []) {
        callback(node);
        if (node.subgraph) visitGraphNodes(node.subgraph, callback, visited);
    }
}

function refreshComposerPreviews() {
    visitGraphNodes(rootGraph(), (node) => {
        node._updatePromptLibraryLivePreview?.();
    });
}

async function fetchLibraryCatalog() {
    const response = await api.fetchApi(
        `/prompt-library-selector/library?t=${Date.now()}`,
        {cache: "no-store"},
    );
    const data = await response.json();
    if (!response.ok) throw new Error(data.error || "Unable to load prompt library");
    lastLibraryCatalog = data;
    return data;
}

async function refreshEntireLibrary(graph = rootGraph()) {
    try {
        const data = await fetchLibraryCatalog();
        visitGraphNodes(graph, (node) => {
            node._applyPromptLibraryCatalog?.(data);
        });
        refreshComposerPreviews();
        return data;
    } catch (error) {
        console.error("Prompt Library Selector:", error);
        throw error;
    }
}

function scheduleEntireLibraryRefresh(delay = 100) {
    clearTimeout(globalLibraryRefreshTimer);
    globalLibraryRefreshTimer = setTimeout(() => {
        refreshEntireLibrary().catch(() => {});
    }, delay);
}

const subgraphWidgetSnapshots = new WeakMap();

function refreshWhenSubgraphWidgetsChange() {
    let changed = false;
    let hasSubgraphs = false;
    visitGraphNodes(rootGraph(), (node) => {
        if (
            node.comfyClass === TEMPLATE_COMPOSER_NODE_TYPE
            && lastLibraryCatalog
            && composerCatalogNeedsRepair(node)
        ) {
            node._applyPromptLibraryCatalog?.(lastLibraryCatalog);
        }
        if (!node.subgraph) return;
        hasSubgraphs = true;
        syncPromotedSelectorWidgets(node);
        const snapshot = JSON.stringify((node.widgets ?? []).map((widget) => [
            widget.widgetId ?? widget.name,
            widget.value,
        ]));
        const previous = subgraphWidgetSnapshots.get(node);
        subgraphWidgetSnapshots.set(node, snapshot);
        if (previous !== undefined && previous !== snapshot) changed = true;
    });
    // Promoted widget values live in ComfyUI's host-scoped store and do not
    // consistently produce callbacks. While subgraphs exist, keep Composer
    // requirements authoritative even when no observable widget changed.
    if (changed || hasSubgraphs) refreshComposerPreviews();
}

// Current ComfyUI promoted widgets are host-owned and do not consistently invoke
// the interior widget callback. A lightweight watcher keeps previews truly live.
setInterval(refreshWhenSubgraphWidgetsChange, 250);

function composerCatalogNeedsRepair(node) {
    for (const name of ["template_category", "template_subcategory", "template"]) {
        const widget = node.widgets?.find((item) => item.name === name);
        if (!widget || widget.value === NONE_KEY) continue;
        const values = widget.options?.values ?? [];
        if (!Array.from(values).includes(widget.value)) return true;
    }
    return false;
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

function widgetValue(node, name, overrides) {
    if (overrides?.has(name)) return overrides.get(name);
    return node.widgets?.find((widget) => widget.name === name)?.value;
}

function selectedLibraryEntry(node, overrides) {
    const enabled = widgetValue(node, "enabled", overrides) !== false;
    const categoryKey = widgetValue(node, "category", overrides);
    const subcategoryKey = widgetValue(node, "subcategory", overrides);
    const presetKey = widgetValue(node, "preset", overrides);
    const category = node._promptLibraryCatalog?.find(
        (item) => item.key === categoryKey,
    );
    const subcategory = category?.subcategories?.find(
        (item) => item.key === subcategoryKey,
    );
    const candidates = subcategory?.presets ?? [];
    const variable = String(widgetValue(node, "template_variable", overrides) ?? "").trim();
    const seed = widgetValue(node, "seed", overrides) ?? 0;
    const preset = presetKey === RANDOM_KEY
        ? candidates[stableChoice(seed, [variable, categoryKey, subcategoryKey], candidates.length)]
        : candidates.find((item) => item.key === presetKey);
    const promptOverride = String(widgetValue(node, "prompt_override", overrides) ?? "").trim();
    const negativeOverride = String(widgetValue(node, "negative_override", overrides) ?? "").trim();
    const alias = String(widgetValue(node, "alias", overrides) ?? "").trim();
    const libraryPositive = preset?.prompt || "";
    const libraryNegative = preset?.negative_prompt || "";
    const rawPositive = promptOverride || libraryPositive;
    return {
        variable: variable || preset?.template_slot || category?.template_slot || categoryKey || "",
        source: preset?.template_slot || category?.template_slot || categoryKey || "",
        alias,
        raw_positive: rawPositive,
        positive: enabled ? applyAlias(rawPositive, alias) : "",
        negative: enabled ? (negativeOverride || libraryNegative) : "",
        library_positive: libraryPositive,
        library_negative: libraryNegative,
        tags: enabled ? (preset?.tags ?? []) : [],
        label: preset?.label ?? NONE_LABEL,
        preset: preset?.key ?? NONE_KEY,
        enabled,
    };
}

function retainOrNone(widget, items, includeRandom = false) {
    if (!widget) return;
    const labels = new Map([[NONE_KEY, NONE_LABEL]]);
    if (includeRandom && items?.length) labels.set(RANDOM_KEY, "Random");
    for (const item of items ?? []) labels.set(item.key, item.label);

    const keys = new Set(labels.keys());
    if (!keys.has(widget.value)) widget.value = NONE_KEY;
    widget.options.values = [...keys];
    widget.options.getOptionLabel = (value) => labels.get(value) ?? String(value);
}

function promotedWidgetBindings(subgraphNode) {
    const bindingsByNode = new Map();
    const subgraph = subgraphNode?.subgraph;
    for (let index = 0; index < (subgraphNode?.inputs?.length ?? 0); index += 1) {
        const hostInput = subgraphNode.inputs[index];
        const boundarySlot = subgraph?.inputNode?.slots?.[index];
        if (!hostInput?.widgetId || !boundarySlot) continue;
        const hostWidget = subgraphNode.getWidgetFromSlot?.(hostInput)
            ?? subgraphNode.widgets?.find((widget) =>
                widget.widgetId === hostInput.widgetId || widget.name === hostInput.name);
        if (!hostWidget) continue;
        for (const linkId of boundarySlot.linkIds ?? []) {
            const link = graphLink(subgraph, linkId);
            const target = link ? graphNode(subgraph, link.target_id) : null;
            const targetInput = target?.inputs?.[link?.target_slot];
            const widgetName = targetInput?.widget?.name ?? targetInput?.name;
            if (!target || !widgetName) continue;
            if (!bindingsByNode.has(target)) bindingsByNode.set(target, new Map());
            bindingsByNode.get(target).set(widgetName, {hostInput, hostWidget});
        }
    }
    return bindingsByNode;
}

function syncPromotedSelectorWidgets(subgraphNode) {
    let updated = false;
    for (const [selector, bindings] of promotedWidgetBindings(subgraphNode)) {
        if (selector.comfyClass !== NODE_TYPE || !selector._promptLibraryCatalog) continue;
        const resolvedWidget = (name) => bindings.get(name)?.hostWidget
            ?? selector.widgets?.find((widget) => widget.name === name);
        const category = resolvedWidget("category");
        const subcategory = resolvedWidget("subcategory");
        const preset = resolvedWidget("preset");
        if (!bindings.size) continue;

        const before = JSON.stringify([
            category?.value, category?.options?.values,
            subcategory?.value, subcategory?.options?.values,
            preset?.value, preset?.options?.values,
        ]);
        retainOrNone(category, selector._promptLibraryCatalog);
        const selectedCategory = selector._promptLibraryCatalog.find(
            (item) => item.key === category?.value,
        );
        retainOrNone(subcategory, selectedCategory?.subcategories ?? []);
        const selectedSubcategory = selectedCategory?.subcategories?.find(
            (item) => item.key === subcategory?.value,
        );
        retainOrNone(preset, selectedSubcategory?.presets ?? [], true);
        const after = JSON.stringify([
            category?.value, category?.options?.values,
            subcategory?.value, subcategory?.options?.values,
            preset?.value, preset?.options?.values,
        ]);
        updated ||= before !== after;
    }
    if (updated) subgraphNode.setDirtyCanvas?.(true, true);
}

app.registerExtension({
    name: "prompt-library-selector.cascading-selectors",

    loadedGraphNode(node) {
        if (![NODE_TYPE, TEMPLATE_COMPOSER_NODE_TYPE].includes(node.comfyClass)) return;
        if (lastLibraryCatalog) {
            setTimeout(() => node._applyPromptLibraryCatalog?.(lastLibraryCatalog), 0);
        }
        node._schedulePromptLibraryReload?.();
        scheduleEntireLibraryRefresh();
    },

    afterConfigureGraph() {
        scheduleEntireLibraryRefresh(0);
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
            ["enabled", "Include preset"],
            ["template_variable", "Template variable"],
            ["prompt_override", "Positive override"],
            ["negative_override", "Negative override"],
            ["name_separator", "Resolved-name separator"],
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

        node._applyPromptLibraryCatalog = (data) => {
            catalog = data.categories ?? [];
            node._promptLibraryCatalog = catalog;
            node._promptLibraryTemplates = data.templates ?? [];
            updateCategory();
            resolvedWidget.value = selectedLibraryEntry(node).label;
            node.setDirtyCanvas(true, true);
        };

        const reload = async () => {
            try {
                node._applyPromptLibraryCatalog(await fetchLibraryCatalog());
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

        await reload();
        node._schedulePromptLibraryReload();
    },
});

function promotedWidgetValues(subgraphNode, inheritedOverrides) {
    const valuesByNode = new Map();
    const subgraph = subgraphNode?.subgraph;
    for (let index = 0; index < (subgraphNode?.inputs?.length ?? 0); index += 1) {
        const hostInput = subgraphNode.inputs[index];
        const boundarySlot = subgraph?.inputNode?.slots?.[index];
        if (!hostInput?.widgetId || !boundarySlot) continue;
        const hostWidget = subgraphNode.getWidgetFromSlot?.(hostInput)
            ?? subgraphNode.widgets?.find((widget) =>
                widget.widgetId === hostInput.widgetId || widget.name === hostInput.name);
        const value = inheritedOverrides?.has(hostInput.name)
            ? inheritedOverrides.get(hostInput.name)
            : hostWidget?.value;
        for (const linkId of boundarySlot.linkIds ?? []) {
            const link = graphLink(subgraph, linkId);
            const target = link ? graphNode(subgraph, link.target_id) : null;
            const targetInput = target?.inputs?.[link?.target_slot];
            const widgetName = targetInput?.widget?.name ?? targetInput?.name;
            if (!target || !widgetName) continue;
            if (!valuesByNode.has(target)) valuesByNode.set(target, new Map());
            valuesByNode.get(target).set(widgetName, value);
        }
    }
    return valuesByNode;
}

function markBundleNodeVisited(visited, node, overrideContext) {
    const scope = overrideContext?.hostNode ?? node.graph ?? node;
    if (!visited.has(node)) visited.set(node, new Set());
    const scopes = visited.get(node);
    if (scopes.has(scope)) return true;
    scopes.add(scope);
    return false;
}

function bundleSegmentsFromSource(node, outputSlot, visited = new Map(), overrideContext) {
    if (!node) return [];
    if (node.comfyClass === NODE_TYPE) {
        return bundleSegmentsFromSelector(node, visited, overrideContext);
    }
    if (!node.subgraph || markBundleNodeVisited(visited, node, overrideContext)) return [];
    const boundarySlot = node.subgraph.outputNode?.slots?.[outputSlot];
    const internalLinkId = boundarySlot?.linkIds?.[0];
    const internalLink = internalLinkId != null
        ? graphLink(node.subgraph, internalLinkId)
        : null;
    const internalSource = internalLink
        ? graphNode(node.subgraph, internalLink.origin_id)
        : null;
    const nestedContext = promotedWidgetValues(node, overrideContext?.get(node));
    nestedContext.hostNode = node;
    nestedContext.parentContext = overrideContext;
    return internalSource
        ? bundleSegmentsFromSource(
            internalSource, internalLink.origin_slot, visited, nestedContext,
        )
        : [];
}

function bundleSegmentsFromSelector(node, visited = new Map(), overrideContext) {
    if (!node || markBundleNodeVisited(visited, node, overrideContext)) return [];
    const segments = [];
    const graph = node.graph ?? activeGraph();
    const bundleInput = node.inputs?.find((input) => input.name === "bundle_in");
    if (bundleInput?.link != null) {
        const link = graphLink(graph, bundleInput.link);
        const source = link ? graphNode(graph, link.origin_id) : null;
        if (
            link && String(link.origin_id) === String(graph.inputNode?.id)
        ) {
            const hostNode = overrideContext?.hostNode;
            const hostInput = hostNode?.inputs?.[link.origin_slot];
            const parentGraph = hostNode?.graph;
            const parentLink = hostInput?.link != null
                ? graphLink(parentGraph, hostInput.link)
                : null;
            const parentSource = parentLink
                ? graphNode(parentGraph, parentLink.origin_id)
                : null;
            segments.push(...bundleSegmentsFromSource(
                parentSource, parentLink?.origin_slot, visited,
                overrideContext?.parentContext,
            ));
        } else if (source) {
            segments.push(...bundleSegmentsFromSource(
                source, link.origin_slot, visited, overrideContext,
            ));
        }
    }
    const segment = selectedLibraryEntry(node, overrideContext?.get(node));
    if (segment.positive || segment.negative || segment.tags?.length) segments.push(segment);
    return segments;
}

function liveTemplateAssembly(node) {
    const categoryKey = node.widgets?.find((widget) => widget.name === "template_category")?.value;
    const subcategoryKey = node.widgets?.find((widget) => widget.name === "template_subcategory")?.value;
    const templateKey = node.widgets?.find((widget) => widget.name === "template")?.value;
    const category = node._promptLibraryTemplates?.find((item) => item.key === categoryKey);
    const subcategory = category?.subcategories?.find((item) => item.key === subcategoryKey);
    const template = subcategory?.templates?.find((item) => item.key === templateKey);
    const override = String(node.widgets?.find((widget) => widget.name === "template_override")?.value ?? "").trim();
    let text = override || template?.template || "";
    const input = node.inputs?.find((item) => item.name === "bundle_in");
    const graph = node.graph ?? activeGraph();
    const link = input?.link != null ? graphLink(graph, input.link) : null;
    const source = link ? graphNode(graph, link.origin_id) : null;
    const segments = bundleSegmentsFromSource(source, link?.origin_slot);
    const byVariable = new Map();
    const templateSlots = template?.slots ?? {};
    const templateDefaults = template?.defaults ?? {};
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
    for (const variable of Object.keys(templateSlots)) {
        if (byVariable.has(variable) || !String(templateDefaults[variable] ?? "").trim()) continue;
        byVariable.set(variable, {
            variable,
            source: templateSlots[variable],
            positive: applyAlias(templateDefaults[variable], template?.aliases?.[variable]),
            negative: "",
            tags: [],
            label: "Template default",
            defaulted: true,
        });
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
    const requirements = Object.entries(templateSlots).map(([variable, sourceName]) => {
        const segment = byVariable.get(variable);
        const matchingCategories = (node._promptLibraryCatalog ?? [])
            .filter((categoryEntry) =>
                (categoryEntry.template_slot || categoryEntry.key) === sourceName)
            .map((categoryEntry) => categoryEntry.label);
        return {
            variable,
            source: sourceName,
            categories: matchingCategories,
            alias: template?.aliases?.[variable] ?? "",
            connected: Boolean(segment),
            selection: segment?.defaulted ? "Template default" : (segment?.label ?? ""),
            defaulted: Boolean(segment?.defaulted),
        };
    });
    for (const variable of variables) {
        if (variable in templateSlots) continue;
        requirements.push({
            variable,
            source: "unmapped",
            categories: [],
            alias: template?.aliases?.[variable] ?? "",
            connected: Boolean(byVariable.get(variable)),
            selection: byVariable.get(variable)?.label ?? "",
        });
    }
    return {
        positive,
        negative: unique(used.map((item) => item.negative)).join(", "),
        requirements,
    };
}

async function setupTemplateComposer(node) {
    if (node._promptLibraryTemplateComposerReady) return;
    node._promptLibraryTemplateComposerReady = true;
    const categoryWidget = node.widgets?.find((widget) => widget.name === "template_category");
    const subcategoryWidget = node.widgets?.find((widget) => widget.name === "template_subcategory");
    const templateWidget = node.widgets?.find((widget) => widget.name === "template");
    const overrideWidget = node.widgets?.find((widget) => widget.name === "template_override");
    if (!categoryWidget || !subcategoryWidget || !templateWidget || !overrideWidget) return;

    const selectedTemplate = () => {
        const category = node._promptLibraryTemplates?.find(
            (item) => item.key === categoryWidget.value,
        );
        const subcategory = category?.subcategories?.find(
            (item) => item.key === subcategoryWidget.value,
        );
        return subcategory?.templates?.find((item) => item.key === templateWidget.value);
    };

    const updateTemplate = () => {
        const category = node._promptLibraryTemplates?.find(
            (item) => item.key === categoryWidget.value,
        );
        const subcategory = category?.subcategories?.find(
            (item) => item.key === subcategoryWidget.value,
        );
        retainOrNone(templateWidget, subcategory?.templates ?? []);
        node._updatePromptLibraryLivePreview?.();
    };

    const updateSubcategory = () => {
        const category = node._promptLibraryTemplates?.find(
            (item) => item.key === categoryWidget.value,
        );
        retainOrNone(subcategoryWidget, category?.subcategories ?? []);
        updateTemplate();
    };

    const updateCategory = () => {
        retainOrNone(categoryWidget, node._promptLibraryTemplates ?? []);
        updateSubcategory();
    };

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
    const requirementsWrapper = document.createElement("div");
    requirementsWrapper.style.display = "grid";
    requirementsWrapper.style.gap = "4px";
    const requirementsLabel = document.createElement("div");
    requirementsLabel.textContent = "Template requires";
    requirementsLabel.style.fontSize = "12px";
    const requirementsList = document.createElement("div");
    requirementsList.style.display = "grid";
    requirementsList.style.gap = "3px";
    requirementsList.style.fontSize = "11px";
    requirementsList.style.lineHeight = "1.35";
    requirementsWrapper.append(requirementsLabel, requirementsList);
    container.append(requirementsWrapper);
    const positivePreview = makePreview("Live positive prompt", 10);
    const negativePreview = makePreview("Combined negative prompt", 3);
    if (typeof node.addDOMWidget === "function") {
        const widget = node.addDOMWidget("template_preview", "preview", container, {
            serialize: false,
            hideOnZoom: false,
        });
        widget.computeSize = (width) => [width, 470];
    }

    node._updatePromptLibraryLivePreview = () => {
        const assembled = liveTemplateAssembly(node);
        requirementsList.replaceChildren();
        if (!assembled.requirements.length) {
            const empty = document.createElement("div");
            empty.textContent = "Choose a template to see its required selector sources.";
            empty.style.opacity = "0.7";
            requirementsList.append(empty);
        }
        for (const requirement of assembled.requirements) {
            const status = requirement.connected ? "✓" : "○";
            const alias = requirement.alias ? ` (${requirement.alias})` : "";
            const categories = requirement.categories.length
                ? ` [${requirement.categories.join(", ")}]`
                : requirement.source === "unmapped" ? " [no source mapping]" : " [no matching category]";
            const selection = requirement.connected
                ? ` — ${requirement.selection || "connected"}`
                : " — missing";
            const line = document.createElement("div");
            line.textContent = `${status} ${requirement.variable} ← ${requirement.source}${categories}${alias}${selection}`;
            line.style.whiteSpace = "normal";
            line.style.overflowWrap = "anywhere";
            line.style.color = requirement.connected ? "#8fd6a3" : "inherit";
            line.style.padding = "3px 6px";
            line.style.borderLeft = `3px solid ${requirement.connected ? "#5cae75" : "#8a7a55"}`;
            line.style.background = "rgba(127, 127, 127, 0.08)";
            line.style.borderRadius = "2px";
            requirementsList.append(line);
        }
        positivePreview.value = assembled.positive;
        negativePreview.value = assembled.negative;
        node._promptLibraryLiveValue = assembled.positive;
    };

    node._applyPromptLibraryCatalog = (data) => {
        node._promptLibraryTemplates = data.templates ?? [];
        node._promptLibraryCatalog = data.categories ?? [];
        updateCategory();
        node._updatePromptLibraryLivePreview();
        node.setDirtyCanvas(true, true);
    };

    const refresh = async () => {
        await refreshEntireLibrary(rootGraph(node));
    };

    for (const [name, label] of [
        ["template_category", "Template category"],
        ["template_subcategory", "Template subcategory"],
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
    categoryWidget.callback = () => { overrideWidget.value = ""; updateSubcategory(); };
    subcategoryWidget.callback = () => { overrideWidget.value = ""; updateTemplate(); };
    templateWidget.callback = () => { overrideWidget.value = ""; node._updatePromptLibraryLivePreview(); };

    node.addWidget("button", "Load selected template for editing", null, () => {
        const selected = selectedTemplate();
        overrideWidget.value = selected?.template ?? "";
        node._updatePromptLibraryLivePreview();
        node.setDirtyCanvas(true, true);
    });
    node.addWidget("button", "Use library template", null, () => {
        overrideWidget.value = "";
        node._updatePromptLibraryLivePreview();
        node.setDirtyCanvas(true, true);
    });
    node.addWidget("button", "Refresh entire library", null, refresh);

    node._schedulePromptLibraryReload = () => {
        clearTimeout(node._promptLibraryReloadTimer);
        node._promptLibraryReloadTimer = setTimeout(() => {
            refresh().catch(() => {});
        }, 100);
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
    };
    await refresh();
    node._schedulePromptLibraryReload();
}
