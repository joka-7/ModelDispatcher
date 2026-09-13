import { act } from "react";
import { createRoot, type Root } from "react-dom/client";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import type { AgentConfig } from "@joka-7/modeldispatcher-browser-agent";

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

const BASE_CONFIG: AgentConfig = {
  provider: "gemini",
  apiKey: "",
  model: "gemini-2.0-flash",
  ollamaUrl: "http://localhost:11434",
};

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

function render(props: {
  config: AgentConfig;
  onConfigChange: (config: AgentConfig) => void;
  question?: string;
  onExternalChat?: (result: unknown) => void;
}): void {
  act(() => {
    root.render(<ModelPicker {...props} />);
  });
}

describe("ModelPicker", () => {
  it("renders every known provider as a select option", () => {
    render({ config: BASE_CONFIG, onConfigChange: vi.fn() });

    const select = container.querySelector("#md-provider") as HTMLSelectElement;
    const values = Array.from(select.options).map((o) => o.value);
    expect(values).toEqual(["gemini", "groq", "ollama", "anthropic", "openai"]);
  });

  it("switching provider resets the key and applies the new default model", () => {
    const onConfigChange = vi.fn();
    render({
      config: { ...BASE_CONFIG, apiKey: "leftover-gemini-key" },
      onConfigChange,
    });

    const select = container.querySelector("#md-provider") as HTMLSelectElement;
    act(() => {
      select.value = "anthropic";
      select.dispatchEvent(new Event("change", { bubbles: true }));
    });

    expect(onConfigChange).toHaveBeenCalledWith({
      provider: "anthropic",
      apiKey: "",
      model: "claude-haiku-4-5-20251001",
      ollamaUrl: BASE_CONFIG.ollamaUrl,
    });
  });

  it("shows an API key field for a keyed provider and an Ollama URL field for one that needs no key", () => {
    render({ config: BASE_CONFIG, onConfigChange: vi.fn() });
    expect(container.querySelector("#md-api-key")).not.toBeNull();
    expect(container.querySelector("#md-ollama-url")).toBeNull();

    render({ config: { ...BASE_CONFIG, provider: "ollama" }, onConfigChange: vi.fn() });
    expect(container.querySelector("#md-api-key")).toBeNull();
    expect(container.querySelector("#md-ollama-url")).not.toBeNull();
  });

  it("editing the API key field reports the full updated config", () => {
    const onConfigChange = vi.fn();
    render({ config: BASE_CONFIG, onConfigChange });

    const input = container.querySelector("#md-api-key") as HTMLInputElement;
    act(() => setNativeInputValue(input, "AIza-new-key"));

    expect(onConfigChange).toHaveBeenCalledWith({ ...BASE_CONFIG, apiKey: "AIza-new-key" });
  });

  it("opens the external chat escape hatch with the current question and reports the result", async () => {
    const open = vi.fn();
    const onExternalChat = vi.fn();
    act(() => {
      root.render(
        <ModelPicker
          config={BASE_CONFIG}
          onConfigChange={vi.fn()}
          question="how do closures work?"
          onExternalChat={onExternalChat}
          externalChatDeps={{ open, clipboard: { writeText: vi.fn().mockResolvedValue(undefined) } }}
        />,
      );
    });

    const buttons = Array.from(container.querySelectorAll(".md-external-chat-btn"));
    const claudeButton = buttons.find((b) => b.textContent === "Claude") as HTMLButtonElement;

    await act(async () => {
      claudeButton.click();
      await Promise.resolve();
    });

    expect(onExternalChat).toHaveBeenCalledWith(
      expect.objectContaining({ provider: "claude", prefilled: true }),
    );
    expect(container.querySelector(".md-status")?.textContent).toContain("Claude");
  });

  it("links to the default glossary URL, or a custom one when given", () => {
    render({ config: BASE_CONFIG, onConfigChange: vi.fn() });
    const defaultLink = container.querySelector(".md-glossary-link") as HTMLAnchorElement;
    expect(defaultLink.href).toContain("docs/GLOSSARY.md");

    act(() => {
      root.render(
        <ModelPicker
          config={BASE_CONFIG}
          onConfigChange={vi.fn()}
          glossaryUrl="https://example.com/glossary"
        />,
      );
    });
    const customLink = container.querySelector(".md-glossary-link") as HTMLAnchorElement;
    expect(customLink.href).toBe("https://example.com/glossary");
  });
});
