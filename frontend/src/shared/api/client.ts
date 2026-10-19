import { z } from "zod";

import { ApiError, retryAfterMilliseconds } from "./errors";

const problemSchema = z.object({
  detail: z.string(),
  code: z.string(),
});

export function csrfToken(cookie = document.cookie): string | null {
  const value = cookie
    .split(";")
    .map((part) => part.trim())
    .find((part) => part.startsWith("csrftoken="));
  return value ? decodeURIComponent(value.slice("csrftoken=".length)) : null;
}

export function loginUrl(
  current: Pick<Location, "pathname" | "search" | "hash"> = window.location,
): string {
  return `/login/?${new URLSearchParams({ next: current.pathname + current.search + current.hash })}`;
}

export async function appRequest(
  path: `/api/app/${string}`,
  init: RequestInit = {},
): Promise<unknown> {
  const headers = new Headers(init.headers);
  headers.set("Accept", "application/json");
  const method = (init.method ?? "GET").toUpperCase();
  if (!["GET", "HEAD", "OPTIONS"].includes(method)) {
    const token = csrfToken();
    if (!token) {
      throw new ApiError(
        "forbidden",
        "Your security token is missing. Reload the page and try again.",
        {
          code: "csrf_failed",
        },
      );
    }
    headers.set("X-CSRFToken", token);
  }

  let response: Response;
  try {
    response = await fetch(path, {
      ...init,
      method,
      headers,
      credentials: "same-origin",
      redirect: "error",
    });
  } catch (error) {
    if (init.signal?.aborted) throw error;
    throw new ApiError("network", "Cannot reach the server. Check your connection and try again.");
  }

  const contentType = response.headers.get("Content-Type") ?? "";
  let body: unknown;
  if (contentType.includes("json")) {
    try {
      body = await response.json();
    } catch (error) {
      if (init.signal?.aborted) throw error;
      throw new ApiError(
        "contract",
        "The server returned an unreadable response. Reload the page.",
      );
    }
  }

  if (!response.ok) {
    const problem = problemSchema.safeParse(body);
    const kind =
      response.status === 401
        ? "unauthorized"
        : response.status === 403
          ? "forbidden"
          : response.status === 404
            ? "not-found"
            : response.status === 422
              ? "validation"
              : response.status === 429
                ? "rate-limited"
                : response.status >= 500
                  ? "server"
                  : "contract";
    throw new ApiError(
      kind,
      problem.success
        ? problem.data.detail
        : `Request failed (${response.status}). Please try again.`,
      {
        status: response.status,
        code: problem.success ? problem.data.code : undefined,
        retryAfter: retryAfterMilliseconds(response.headers.get("Retry-After")),
      },
    );
  }

  if (response.status !== 204 && body === undefined) {
    throw new ApiError(
      "contract",
      "The server did not return JSON. Reload the page and try again.",
    );
  }
  return body;
}
