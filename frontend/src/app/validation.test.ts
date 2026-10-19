import "./validation";

import { z } from "zod";
import { expect, it, vi } from "vitest";

it("validates generated-style objects without probing eval under CSP", () => {
  const probe = vi.spyOn(globalThis, "Function");
  expect(z.config().jitless).toBe(true);
  const schema = z.object({ value: z.number().min(1) });
  expect(schema.safeParse({ value: 2 }).success).toBe(true);
  expect(schema.safeParse({ value: 0 }).success).toBe(false);
  expect(probe).not.toHaveBeenCalled();
});
