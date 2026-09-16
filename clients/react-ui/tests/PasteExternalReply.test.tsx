import { act } from "react";
import { createRoot, type Root } from "react-dom/client";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { PasteExternalReply } from "../src/PasteExternalReply.js";

let container: HTMLDivElement;
let root: Root;

const nativeValueDescriptor = Object.getOwnPropertyDescriptor(
  window.HTMLTextAreaElement.prototype,
  "value",
);
if (!nativeValueDescriptor?.set) {
  throw new Error("HTMLTextAreaElement.prototype.value has no native setter in this environment");
}
const nativeTextareaValueSetter = nativeValueDescriptor.set;

function setTextareaValue(textarea: HTMLTextAreaElement, value: string): void {
  nativeTextareaValueSetter.call(textarea, value);
  textarea.dispatchEvent(new Event("input", { bubbles: true }));
}

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

describe("PasteExternalReply", () => {
  it("renders a labeled textarea and a disabled apply button when empty", () => {
    act(() => {
      root.render(<PasteExternalReply onApply={vi.fn()} />);
    });
    const textarea = container.querySelector("textarea") as HTMLTextAreaElement;
    const button = container.querySelector("button") as HTMLButtonElement;
    expect(textarea).not.toBeNull();
    expect(button.disabled).toBe(true);
  });

  it("enables apply once non-whitespace text is entered", () => {
    act(() => {
      root.render(<PasteExternalReply onApply={vi.fn()} />);
    });
    const textarea = container.querySelector("textarea") as HTMLTextAreaElement;
    act(() => setTextareaValue(textarea, "   "));
    expect((container.querySelector("button") as HTMLButtonElement).disabled).toBe(true);

    act(() => setTextareaValue(textarea, '{"day": 1}'));
    expect((container.querySelector("button") as HTMLButtonElement).disabled).toBe(false);
  });

  it("calls onApply with the trimmed raw text and clears the textarea", () => {
    const onApply = vi.fn();
    act(() => {
      root.render(<PasteExternalReply onApply={onApply} />);
    });
    const textarea = container.querySelector("textarea") as HTMLTextAreaElement;
    act(() => setTextareaValue(textarea, "  some raw reply text  "));

    const button = container.querySelector("button") as HTMLButtonElement;
    act(() => button.click());

    expect(onApply).toHaveBeenCalledWith("some raw reply text");
    expect(textarea.value).toBe("");
    expect(button.disabled).toBe(true);
  });

  it("never parses or inspects the text — passes it through unchanged aside from trimming", () => {
    const onApply = vi.fn();
    act(() => {
      root.render(<PasteExternalReply onApply={onApply} />);
    });
    const textarea = container.querySelector("textarea") as HTMLTextAreaElement;
    const notJson = "Day 1: arrive. Day 2: explore.\nNot valid JSON at all.";
    act(() => setTextareaValue(textarea, notJson));
    act(() => (container.querySelector("button") as HTMLButtonElement).click());

    expect(onApply).toHaveBeenCalledWith(notJson);
  });

  it("supports custom label, placeholder, and apply button text", () => {
    act(() => {
      root.render(
        <PasteExternalReply
          onApply={vi.fn()}
          label="Paste your itinerary here"
          placeholder="e.g. Day 1: ..."
          applyLabel="Update trip"
        />,
      );
    });
    expect(container.querySelector("label")?.textContent).toBe("Paste your itinerary here");
    expect(container.querySelector("textarea")?.getAttribute("placeholder")).toBe("e.g. Day 1: ...");
    expect(container.querySelector("button")?.textContent).toBe("Update trip");
  });
});
