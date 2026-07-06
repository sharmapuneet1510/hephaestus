import "@testing-library/jest-dom/vitest";

// jsdom lacks scrollTo/clipboard used by components; provide no-op stubs.
if (!("clipboard" in navigator)) {
  Object.defineProperty(navigator, "clipboard", {
    value: { writeText: () => Promise.resolve() },
    configurable: true,
  });
}
