import "@testing-library/jest-dom/vitest";

import { cleanup } from "@testing-library/react";
import { afterEach, vi } from "vitest";

import { MockWebSocket } from "./websocket";

afterEach(() => {
  cleanup();
  MockWebSocket.instances = [];
  vi.unstubAllGlobals();
});

Object.defineProperty(window, "matchMedia", {
  writable: true,
  value: (query: string) => ({
    matches: false,
    media: query,
    addEventListener: vi.fn(),
    removeEventListener: vi.fn(),
    addListener: vi.fn(),
    removeListener: vi.fn(),
    dispatchEvent: vi.fn(),
  }),
});

globalThis.ResizeObserver = class ResizeObserver {
  observe() {}
  unobserve() {}
  disconnect() {}
};

// Never open real sockets from jsdom; tests drive MockWebSocket instead.
Object.defineProperty(globalThis, "WebSocket", { writable: true, value: MockWebSocket });
