import { expect, it } from "vitest";

import { companyMarketsQuery } from "./companies";

it("refreshes saved company market quotes every five seconds", () => {
  expect(companyMarketsQuery({ q: "", page: 1 }).refetchInterval).toBe(5_000);
});
