import { QueryClient } from "@tanstack/react-query";
import { expect, it, vi } from "vitest";

import { session } from "../../test/session";
import { sessionQuery } from "./session";

it("validates the generated session contract", async () => {
  vi.stubGlobal(
    "fetch",
    vi.fn().mockResolvedValue(
      new Response(JSON.stringify(session), {
        headers: { "Content-Type": "application/json" },
      }),
    ),
  );
  const client = new QueryClient({ defaultOptions: { queries: { retry: false, gcTime: 0 } } });
  expect(await client.fetchQuery(sessionQuery)).toEqual(session);
  client.clear();
});

it("rejects response drift instead of inventing permission defaults", async () => {
  vi.stubGlobal(
    "fetch",
    vi.fn().mockResolvedValue(
      new Response('{"id": 1}', {
        headers: { "Content-Type": "application/json" },
      }),
    ),
  );
  const client = new QueryClient({ defaultOptions: { queries: { retry: false, gcTime: 0 } } });
  await expect(client.fetchQuery(sessionQuery)).rejects.toMatchObject({ kind: "contract" });
  client.clear();
});
