import { expect, it } from "vitest";

import { ApiError, retryAfterMilliseconds, retryDelay, shouldRetry } from "./errors";

it.each(["unauthorized", "forbidden", "validation", "not-found", "contract"] as const)(
  "does not retry %s",
  (kind) => {
    expect(shouldRetry(0, new ApiError(kind, "Failed"))).toBe(false);
  },
);

it.each(["network", "server", "rate-limited"] as const)("limits retries for %s", (kind) => {
  expect(shouldRetry(0, new ApiError(kind, "Failed"))).toBe(true);
  expect(shouldRetry(2, new ApiError(kind, "Failed"))).toBe(false);
});

it("does not retry unexpected programming errors", () => {
  expect(shouldRetry(0, new Error("Bug"))).toBe(false);
});

it("honors Retry-After instead of the normal backoff", () => {
  expect(retryDelay(0, new ApiError("rate-limited", "Wait", { retryAfter: 60_000 }))).toBe(60_000);
  expect(retryDelay(1, new ApiError("server", "Failed"))).toBe(2000);
});

it("parses both Retry-After formats and rejects invalid values", () => {
  expect(retryAfterMilliseconds("12")).toBe(12_000);
  expect(
    retryAfterMilliseconds("Wed, 21 Oct 2015 07:28:00 GMT", Date.UTC(2015, 9, 21, 7, 27)),
  ).toBe(60_000);
  expect(retryAfterMilliseconds("invalid")).toBeNull();
  expect(retryAfterMilliseconds("-1")).toBeNull();
  expect(retryAfterMilliseconds(null)).toBeNull();
});
