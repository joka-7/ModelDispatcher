import { act } from "react";
import { createRoot, type Root } from "react-dom/client";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import type { AgentConfig, ExternalChatProviderId } from "@joka-7/modeldispatcher-browser-agent";

import { ModelPicker } from "../src/ModelPicker.js";

let container: HTMLDivElement;
let root: Root;

beforeEach(() => {
  container = document.createElement("div");
  document.body.appendChild(container);
  root = createRoot(container);
});

afterEach(() => {
  act(() => root.unmount());
  container.remove();
  vi.restoreAllMocks();
});

const EMPTY_CONFIG: AgentConfig = { providers: [], ollamaUrl: "http://localhost:11434" };

const nativeValueDescriptor = Object.getOwnPropertyDescriptor(
  window.HTMLInputElement.prototype,
  "value",
);
if (!nativeValueDescriptor?.set) {
  throw new Error("HTMLInputElement.prototype.value has no native setter in this environment");
}
const nativeInputValueSetter = nativeValueDescriptor.set;

/** Set a controlled input's value bypassing React's own value tracker, so
 * the subsequent "input" event is recognised as an actual change — plain
 * `input.value = x` gets silently absorbed by React's tracker instead. */
function setNativeInputValue(input: HTMLInputElement, value: string): void {
  nativeInputValueSetter.call(input, value);
  input.dispatchEvent(new Event("input", { bubbles: true }));
}

function selectOption(select: HTMLSelectElement, value: string): void {
  select.value = value;
  select.dispatchEvent(new Event("change", { bubbles: true }));
}

function render(props: {
  config: AgentConfig;
  onConfigChange: (config: AgentConfig) => void;
  externalChatFavorite?: ExternalChatProviderId | null;
  onExternalChatFavoriteChange?: (favorite: ExternalChatProviderId | null) => void;
  glossaryUrl?: string;
}): void {
  act(() => {
    root.render(
      <ModelPicker
        externalChatFavorite={null}
        onExternalChatFavoriteChange={vi.fn()}
        {...props}
      />,
    );
  });
}

/** The "Choose a provider…" select and its "+ Add provider" button. */
function addProviderControls(): { select: HTMLSelectElement; button: HTMLButtonElement } {
  const select = Array.from(container.querySelectorAll("select")).find((s) =>
    s.getAttribute("aria-label") === "Choose a provider to add",
  ) as HTMLSelectElement;
  const button = Array.from(container.querySelectorAll("button")).find(
    (b) => b.textContent === "+ Add provider",
  ) as HTMLButtonElement;
  return { select, button };
}

describe("ModelPicker — empty state and adding a provider", () => {
  it("shows an empty-state message with no providers configured", () => {
    render({ config: EMPTY_CONFIG, onConfigChange: vi.fn() });
    expect(container.querySelector(".md-empty-state")?.textContent).toContain("No providers added yet");
  });

  it("offers every provider (none configured yet) in the add-provider select", () => {
    render({ config: EMPTY_CONFIG, onConfigChange: vi.fn() });
    const { select } = addProviderControls();
    const values = Array.from(select.options).map((o) => o.value).filter(Boolean);
    expect(values).toEqual(["gemini", "groq", "ollama", "anthropic", "openai"]);
  });

  it("adding a provider appends a credential with its default model and one empty key", () => {
    const onConfigChange = vi.fn();
    render({ config: EMPTY_CONFIG, onConfigChange });

    const { select, button } = addProviderControls();
    act(() => selectOption(select, "anthropic"));
    act(() => button.click());

    expect(onConfigChange).toHaveBeenCalledWith({
      providers: [{ provider: "anthropic", model: "claude-haiku-4-5-20251001", apiKeys: [""] }],
      ollamaUrl: "http://localhost:11434",
    });
  });

  it("adding ollama starts with no key fields at all (apiKeys: [])", () => {
    const onConfigChange = vi.fn();
    render({ config: EMPTY_CONFIG, onConfigChange });

    const { select, button } = addProviderControls();
    act(() => selectOption(select, "ollama"));
    act(() => button.click());

    expect(onConfigChange).toHaveBeenCalledWith({
      providers: [{ provider: "ollama", model: "llama3.2", apiKeys: [] }],
      ollamaUrl: "http://localhost:11434",
    });
  });

  it("does not offer a provider that's already configured", () => {
    const config: AgentConfig = {
      providers: [{ provider: "gemini", model: "gemini-2.0-flash", apiKeys: ["k"] }],
      ollamaUrl: "http://localhost:11434",
    };
    render({ config, onConfigChange: vi.fn() });
    const { select } = addProviderControls();
    const values = Array.from(select.options).map((o) => o.value).filter(Boolean);
    expect(values).not.toContain("gemini");
  });

  it("hides the add-provider control once every provider is configured", () => {
    const config: AgentConfig = {
      providers: (["gemini", "groq", "ollama", "anthropic", "openai"] as const).map((provider) => ({
        provider,
        model: "m",
        apiKeys: [],
      })),
      ollamaUrl: "http://localhost:11434",
    };
    render({ config, onConfigChange: vi.fn() });
    expect(container.querySelector(".md-add-provider")).toBeNull();
  });
});

describe("ModelPicker — a configured keyed provider", () => {
  const config: AgentConfig = {
    providers: [{ provider: "anthropic", model: "claude-haiku-4-5-20251001", apiKeys: ["sk-ant-a"] }],
    ollamaUrl: "http://localhost:11434",
  };

  it("renders the model select with the curated options and the current model chosen", () => {
    render({ config, onConfigChange: vi.fn() });
    const modelSelect = document.getElementById("md-model-anthropic") as HTMLSelectElement;
    expect(modelSelect.value).toBe("claude-haiku-4-5-20251001");
    expect(Array.from(modelSelect.options).map((o) => o.value)).toContain("claude-opus-4-8");
  });

  it("changing the model reports the full updated config", () => {
    const onConfigChange = vi.fn();
    render({ config, onConfigChange });
    const modelSelect = document.getElementById("md-model-anthropic") as HTMLSelectElement;
    act(() => selectOption(modelSelect, "claude-opus-4-8"));
    expect(onConfigChange).toHaveBeenCalledWith({
      ...config,
      providers: [{ ...config.providers[0], model: "claude-opus-4-8" }],
    });
  });

  it("editing a key field reports the full updated config", () => {
    const onConfigChange = vi.fn();
    render({ config, onConfigChange });
    const keyInput = container.querySelector(".md-key-row .md-input") as HTMLInputElement;
    act(() => setNativeInputValue(keyInput, "sk-ant-new"));
    expect(onConfigChange).toHaveBeenCalledWith({
      ...config,
      providers: [{ ...config.providers[0], apiKeys: ["sk-ant-new"] }],
    });
  });

  it("adding another key appends an empty pooled key", () => {
    const onConfigChange = vi.fn();
    render({ config, onConfigChange });
    const addKeyBtn = Array.from(container.querySelectorAll("button")).find(
      (b) => b.textContent === "+ Add another key",
    ) as HTMLButtonElement;
    act(() => addKeyBtn.click());
    expect(onConfigChange).toHaveBeenCalledWith({
      ...config,
      providers: [{ ...config.providers[0], apiKeys: ["sk-ant-a", ""] }],
    });
  });

  it("removing a key drops just that one", () => {
    const twoKeys: AgentConfig = {
      providers: [{ provider: "anthropic", model: "m", apiKeys: ["a", "b"] }],
      ollamaUrl: "",
    };
    const onConfigChange = vi.fn();
    render({ config: twoKeys, onConfigChange });
    const removeButtons = container.querySelectorAll(".md-remove-btn-small");
    act(() => (removeButtons[0] as HTMLButtonElement).click());
    expect(onConfigChange).toHaveBeenCalledWith({
      ...twoKeys,
      providers: [{ ...twoKeys.providers[0], apiKeys: ["b"] }],
    });
  });

  it("removing the provider drops its whole card", () => {
    const onConfigChange = vi.fn();
    render({ config, onConfigChange });
    const removeProviderBtn = container.querySelector(".md-provider-card .md-remove-btn") as HTMLButtonElement;
    act(() => removeProviderBtn.click());
    expect(onConfigChange).toHaveBeenCalledWith({ ...config, providers: [] });
  });

  it("shows a free/no-key badge only where it applies", () => {
    const withFreeAndNoKey: AgentConfig = {
      providers: [
        { provider: "groq", model: "m", apiKeys: ["k"] },
        { provider: "ollama", model: "m", apiKeys: [] },
        { provider: "openai", model: "m", apiKeys: ["k"] },
      ],
      ollamaUrl: "http://localhost:11434",
    };
    render({ config: withFreeAndNoKey, onConfigChange: vi.fn() });
    expect(container.querySelectorAll(".md-badge-free")).toHaveLength(2); // groq + ollama are both `free`
    expect(container.querySelectorAll(".md-badge-nokey")).toHaveLength(1); // only ollama
  });
});

describe("ModelPicker — a configured Ollama entry", () => {
  const config: AgentConfig = {
    providers: [{ provider: "ollama", model: "llama3.2", apiKeys: [] }],
    ollamaUrl: "http://localhost:11434",
  };

  it("shows a URL field bound to config.ollamaUrl instead of any key field", () => {
    render({ config, onConfigChange: vi.fn() });
    expect(container.querySelector("#md-ollama-url")).not.toBeNull();
    expect(container.querySelector(".md-key-row")).toBeNull();
  });

  it("editing the URL updates config.ollamaUrl, not a provider entry", () => {
    const onConfigChange = vi.fn();
    render({ config, onConfigChange });
    const urlInput = document.getElementById("md-ollama-url") as HTMLInputElement;
    act(() => setNativeInputValue(urlInput, "http://example.com:11434"));
    expect(onConfigChange).toHaveBeenCalledWith({ ...config, ollamaUrl: "http://example.com:11434" });
  });
});

describe("ModelPicker — never navigates", () => {
  it("clicking every rendered button never calls window.open", () => {
    const open = vi.fn();
    const originalOpen = window.open;
    window.open = open;

    const config: AgentConfig = {
      providers: [{ provider: "anthropic", model: "m", apiKeys: ["a", "b"] }],
      ollamaUrl: "http://localhost:11434",
    };
    render({ config, onConfigChange: vi.fn(), externalChatFavorite: "claude" });

    for (const button of Array.from(container.querySelectorAll("button"))) {
      act(() => button.click());
    }

    expect(open).not.toHaveBeenCalled();
    window.open = originalOpen;
  });
});

describe("ModelPicker — favorite free AI app", () => {
  it("lists every external chat provider plus a None option as radio inputs", () => {
    render({ config: EMPTY_CONFIG, onConfigChange: vi.fn() });
    const radios = Array.from(container.querySelectorAll<HTMLInputElement>('input[type="radio"]'));
    const labels = radios.map((r) => r.closest("label")?.textContent);
    expect(labels).toEqual(["None", "ChatGPT", "Claude", "Gemini (Google AI Mode)", "Groq"]);
  });

  it("checks the radio matching the current externalChatFavorite", () => {
    render({ config: EMPTY_CONFIG, onConfigChange: vi.fn(), externalChatFavorite: "claude" });
    const radios = Array.from(container.querySelectorAll<HTMLInputElement>('input[type="radio"]'));
    expect(radios.find((r) => r.checked)?.closest("label")?.textContent).toBe("Claude");
  });

  it("picking a favorite only reports the choice", () => {
    const onExternalChatFavoriteChange = vi.fn();
    render({ config: EMPTY_CONFIG, onConfigChange: vi.fn(), onExternalChatFavoriteChange });
    const radios = Array.from(container.querySelectorAll<HTMLInputElement>('input[type="radio"]'));
    const claudeRadio = radios.find((r) => r.closest("label")?.textContent === "Claude");
    act(() => claudeRadio?.click());
    expect(onExternalChatFavoriteChange).toHaveBeenCalledWith("claude");
  });

  it("picking None reports null", () => {
    const onExternalChatFavoriteChange = vi.fn();
    render({ config: EMPTY_CONFIG, onConfigChange: vi.fn(), externalChatFavorite: "groq", onExternalChatFavoriteChange });
    const radios = Array.from(container.querySelectorAll<HTMLInputElement>('input[type="radio"]'));
    const noneRadio = radios.find((r) => r.closest("label")?.textContent === "None");
    act(() => noneRadio?.click());
    expect(onExternalChatFavoriteChange).toHaveBeenCalledWith(null);
  });
});

describe("ModelPicker — glossary link", () => {
  it("links to the default glossary URL, or a custom one when given", () => {
    render({ config: EMPTY_CONFIG, onConfigChange: vi.fn() });
    expect((container.querySelector(".md-glossary-link") as HTMLAnchorElement).href).toContain(
      "docs/ai-glossary.html",
    );

    render({ config: EMPTY_CONFIG, onConfigChange: vi.fn(), glossaryUrl: "https://example.com/glossary" });
    expect((container.querySelector(".md-glossary-link") as HTMLAnchorElement).href).toBe(
      "https://example.com/glossary",
    );
  });
});
