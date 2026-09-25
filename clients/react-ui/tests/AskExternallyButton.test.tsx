import { act } from "react";
import { createRoot, type Root } from "react-dom/client";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { AskExternallyButton } from "../src/AskExternallyButton.js";

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

describe("AskExternallyButton", () => {
  it("renders nothing when no favorite is saved", () => {
    act(() => {
      root.render(<AskExternallyButton favorite={null} />);
    });
    expect(container.innerHTML).toBe("");
  });

  it("renders a single button naming the saved favorite", () => {
    act(() => {
      root.render(<AskExternallyButton favorite="claude" />);
    });
    const buttons = container.querySelectorAll("button");
    expect(buttons).toHaveLength(1);
    expect(buttons[0]?.textContent).toBe("Ask Claude");
  });

  it("clicking opens the favorite with the current question and reports the result", async () => {
    const open = vi.fn();
    const onExternalChat = vi.fn();
    act(() => {
      root.render(
        <AskExternallyButton
          favorite="claude"
          question="how do closures work?"
          onExternalChat={onExternalChat}
          externalChatDeps={{ open, clipboard: { writeText: vi.fn().mockResolvedValue(undefined) } }}
        />,
      );
    });

    const button = container.querySelector("button") as HTMLButtonElement;
    await act(async () => {
      button.click();
      await Promise.resolve();
    });

    expect(open).toHaveBeenCalledWith(expect.stringContaining("claude.ai/new?"));
    expect(onExternalChat).toHaveBeenCalledWith(
      expect.objectContaining({ provider: "claude", prefilled: true }),
    );
    expect(container.querySelector(".md-status")?.textContent).toContain("Claude");
  });

  it("omitting question opens an empty compose box rather than throwing", async () => {
    const open = vi.fn();
    act(() => {
      root.render(
        <AskExternallyButton
          favorite="groq"
          externalChatDeps={{ open, clipboard: { writeText: vi.fn().mockResolvedValue(undefined) } }}
        />,
      );
    });

    const button = container.querySelector("button") as HTMLButtonElement;
    await act(async () => {
      button.click();
      await Promise.resolve();
    });

    expect(open).toHaveBeenCalledWith("https://groq.com/");
  });

  it("renders French and Hebrew labels, keeping the provider name in English", () => {
    act(() => {
      root.render(<AskExternallyButton favorite="claude" locale="fr" />);
    });
    expect(container.querySelector("button")?.textContent).toBe("Demander à Claude");
    expect(container.querySelector(".md-ask-externally")?.getAttribute("dir")).toBe("ltr");

    act(() => {
      root.render(<AskExternallyButton favorite="claude" locale="he" />);
    });
    expect(container.querySelector("button")?.textContent).toBe("שאלו את Claude");
    expect(container.querySelector(".md-ask-externally")?.getAttribute("dir")).toBe("rtl");
  });
});
