import { act } from "react";
import { createRoot, type Root } from "react-dom/client";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { ConversationIntro } from "../src/ConversationIntro.js";

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

describe("ConversationIntro", () => {
  it("defaults to an English, ltr notice", () => {
    act(() => {
      root.render(<ConversationIntro />);
    });
    const note = container.querySelector(".md-conversation-intro");
    expect(note?.getAttribute("dir")).toBe("ltr");
    expect(note?.getAttribute("role")).toBe("note");
    expect(note?.textContent).toMatch(/You're chatting with AI/);
  });

  it("renders French text", () => {
    act(() => {
      root.render(<ConversationIntro locale="fr" />);
    });
    expect(container.querySelector(".md-conversation-intro")?.textContent).toMatch(
      /Vous discutez avec une IA/,
    );
  });

  it("renders Hebrew text with dir=rtl", () => {
    act(() => {
      root.render(<ConversationIntro locale="he" />);
    });
    const note = container.querySelector(".md-conversation-intro");
    expect(note?.getAttribute("dir")).toBe("rtl");
    expect(note?.textContent).toBe("אתם משוחחים עם AI — התשובות עלולות להיות שגויות, בדקו כל דבר חשוב בעצמכם.");
  });
});
