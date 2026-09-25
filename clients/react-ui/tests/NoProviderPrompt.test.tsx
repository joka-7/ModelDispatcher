import { act } from "react";
import { createRoot, type Root } from "react-dom/client";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { NoProviderPrompt } from "../src/NoProviderPrompt.js";

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

describe("NoProviderPrompt", () => {
  it("always offers a way to open Settings", () => {
    const onOpenSettings = vi.fn();
    act(() => {
      root.render(<NoProviderPrompt favorite={null} onOpenSettings={onOpenSettings} />);
    });

    const settingsBtn = container.querySelector(".md-no-provider-settings-btn") as HTMLButtonElement;
    expect(settingsBtn.textContent).toBe("Open AI settings");
    settingsBtn.click();
    expect(onOpenSettings).toHaveBeenCalledTimes(1);
  });

  it("without a saved favorite, nudges toward saving one instead of offering to ask externally", () => {
    act(() => {
      root.render(<NoProviderPrompt favorite={null} onOpenSettings={vi.fn()} />);
    });

    expect(container.querySelector(".md-ask-externally-btn")).toBeNull();
    expect(container.querySelector(".md-no-provider-hint")?.textContent).toMatch(/favorite free AI app/);
  });

  it("with a saved favorite, also offers to ask it directly, no key required", async () => {
    const open = vi.fn();
    const onExternalChat = vi.fn();
    act(() => {
      root.render(
        <NoProviderPrompt
          favorite="claude"
          question="what's a closure?"
          onOpenSettings={vi.fn()}
          onExternalChat={onExternalChat}
          externalChatDeps={{ open, clipboard: { writeText: vi.fn().mockResolvedValue(undefined) } }}
        />,
      );
    });

    expect(container.querySelector(".md-no-provider-hint")).toBeNull();
    const askBtn = container.querySelector(".md-ask-externally-btn") as HTMLButtonElement;
    expect(askBtn.textContent).toBe("Ask Claude");

    await act(async () => {
      askBtn.click();
      await Promise.resolve();
    });

    expect(open).toHaveBeenCalledWith(expect.stringContaining("claude.ai/new?"));
    expect(onExternalChat).toHaveBeenCalledWith(expect.objectContaining({ provider: "claude" }));
  });

  it("renders Hebrew labels and dir=rtl when locale is he", () => {
    act(() => {
      root.render(<NoProviderPrompt favorite={null} onOpenSettings={vi.fn()} locale="he" />);
    });

    expect(container.querySelector(".md-no-provider")?.getAttribute("dir")).toBe("rtl");
    expect(container.querySelector(".md-no-provider-lead")?.textContent).toBe("עדיין לא הגדרתם ספק AI.");
  });
});
