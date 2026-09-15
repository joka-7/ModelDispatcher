import { describe, expect, it } from "vitest";

import {
  DEFAULT_DISPATCHER_FEATURES,
  resolveDispatcherFeatures,
} from "../src/features.js";

describe("resolveDispatcherFeatures", () => {
  it("defaults both flags to enabled with no overrides", () => {
    expect(resolveDispatcherFeatures()).toEqual({ ui: true, dispatch: true });
  });

  it("defaults both flags to enabled with an empty overrides object", () => {
    expect(resolveDispatcherFeatures({})).toEqual({ ui: true, dispatch: true });
  });

  it("overrides only the ui flag, leaving dispatch enabled", () => {
    expect(resolveDispatcherFeatures({ ui: false })).toEqual({ ui: false, dispatch: true });
  });

  it("overrides only the dispatch flag, leaving ui enabled", () => {
    expect(resolveDispatcherFeatures({ dispatch: false })).toEqual({ ui: true, dispatch: false });
  });

  it("overrides both flags", () => {
    expect(resolveDispatcherFeatures({ ui: false, dispatch: false })).toEqual({
      ui: false,
      dispatch: false,
    });
  });

  it("never mutates the shared default object", () => {
    resolveDispatcherFeatures({ ui: false, dispatch: false });
    expect(DEFAULT_DISPATCHER_FEATURES).toEqual({ ui: true, dispatch: true });
  });
});
