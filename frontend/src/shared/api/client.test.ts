import { describe, expect, it, vi } from "vitest";

import { appRequest, csrfToken, loginUrl } from "./client";
import { ApiError } from "./errors";

function jsonResponse(body: unknown, status = 200, headers: Record<string, string> = {}) {
  return new Response(JSON.stringify(body), {
    status,
    headers: { "Content-Type": "application/json", ...headers },
  });
}

describe("appRequest", () => {
  it("uses same-origin sessions, JSON, and the caller's abort signal", async () => {
    const fetch = vi.fn().mockResolvedValue(jsonResponse({ ok: true }));
    vi.stubGlobal("fetch", fetch);
    const controller = new AbortController();
    expect(await appRequest("/api/app/session", { signal: controller.signal })).toEqual({
      ok: true,
    });
    const [, init] = fetch.mock.calls[0];
    expect(init.credentials).toBe("same-origin");
    expect(init.redirect).toBe("error");
    expect(init.signal).toBe(controller.signal);
    expect(init.headers.get("Accept")).toBe("application/json");
    expect(init.headers.has("X-CSRFToken")).toBe(false);
  });

  it("sends CSRF only on unsafe methods", async () => {
    document.cookie = "csrftoken=test-csrf; path=/";
    const fetch = vi.fn().mockResolvedValue(new Response(null, { status: 204 }));
    vi.stubGlobal("fetch", fetch);
    await appRequest("/api/app/example", { method: "post" });
    const [, init] = fetch.mock.calls[0];
    expect(init.method).toBe("POST");
    expect(init.headers.get("X-CSRFToken")).toBe("test-csrf");
    document.cookie = "csrftoken=; Max-Age=0; path=/";
  });

  it("reports a missing CSRF token instead of sending an unsafe request", async () => {
    const fetch = vi.fn();
    vi.stubGlobal("fetch", fetch);
    await expect(appRequest("/api/app/example", { method: "POST" })).rejects.toMatchObject({
      kind: "forbidden",
      code: "csrf_failed",
    });
    expect(fetch).not.toHaveBeenCalled();
  });

  it.each([
    [401, "unauthorized"],
    [403, "forbidden"],
    [404, "not-found"],
    [422, "validation"],
    [429, "rate-limited"],
    [500, "server"],
  ])("maps HTTP %i to %s and preserves the problem code", async (status, kind) => {
    vi.stubGlobal(
      "fetch",
      vi
        .fn()
        .mockResolvedValue(
          jsonResponse({ detail: "Request rejected.", code: "test_problem" }, status),
        ),
    );
    await expect(appRequest("/api/app/session")).rejects.toMatchObject({
      status,
      kind,
      code: "test_problem",
      message: "Request rejected.",
    });
  });

  it("preserves Retry-After on a rate-limit response", async () => {
    vi.stubGlobal(
      "fetch",
      vi
        .fn()
        .mockResolvedValue(
          jsonResponse({ detail: "Wait.", code: "rate_limited" }, 429, { "Retry-After": "45" }),
        ),
    );
    await expect(appRequest("/api/app/session")).rejects.toMatchObject({ retryAfter: 45_000 });
  });

  it("does not turn an HTML login response into valid data", async () => {
    vi.stubGlobal(
      "fetch",
      vi
        .fn()
        .mockResolvedValue(
          new Response("<html>Sign in</html>", { headers: { "Content-Type": "text/html" } }),
        ),
    );
    await expect(appRequest("/api/app/session")).rejects.toMatchObject({ kind: "contract" });
  });

  it("reports malformed JSON", async () => {
    vi.stubGlobal(
      "fetch",
      vi
        .fn()
        .mockResolvedValue(new Response("{", { headers: { "Content-Type": "application/json" } })),
    );
    await expect(appRequest("/api/app/session")).rejects.toMatchObject({ kind: "contract" });
  });

  it("reports network failures explicitly", async () => {
    vi.stubGlobal("fetch", vi.fn().mockRejectedValue(new TypeError("Failed to fetch")));
    await expect(appRequest("/api/app/session")).rejects.toBeInstanceOf(ApiError);
    await expect(appRequest("/api/app/session")).rejects.toMatchObject({ kind: "network" });
  });

  it("preserves cancellation instead of reporting an outage", async () => {
    const controller = new AbortController();
    controller.abort();
    const abort = new DOMException("Aborted", "AbortError");
    vi.stubGlobal("fetch", vi.fn().mockRejectedValue(abort));
    await expect(appRequest("/api/app/session", { signal: controller.signal })).rejects.toBe(abort);
  });
});

it("preserves cancellation while reading the response body", async () => {
  const controller = new AbortController();
  const abort = new DOMException("Aborted", "AbortError");
  const response = new Response(null, { headers: { "Content-Type": "application/json" } });
  vi.spyOn(response, "json").mockImplementation(() => {
    controller.abort();
    return Promise.reject(abort);
  });
  vi.stubGlobal("fetch", vi.fn().mockResolvedValue(response));

  await expect(appRequest("/api/app/session", { signal: controller.signal })).rejects.toBe(abort);
});

it("extracts only the exact CSRF cookie", () => {
  expect(csrfToken("other=x; csrftoken=abc%3D; foo=bar")).toBe("abc=");
  expect(csrfToken("notcsrftoken=x")).toBeNull();
});

it("keeps the current path, filters, and fragment in the sign-in return URL", () => {
  const url = loginUrl({ pathname: "/app/", search: "?q=banks", hash: "#recent" });
  expect(new URL(url, "http://localhost").searchParams.get("next")).toBe("/app/?q=banks#recent");
});
