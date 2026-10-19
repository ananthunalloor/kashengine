import { z } from "zod";

export const pageSizeSchema = z.coerce.number().int().min(1).max(100).optional();

export function tableParams(
  params: URLSearchParams,
  filters: { sort?: string; page_size?: number },
) {
  if (filters.sort) params.set("sort", filters.sort);
  if (filters.page_size !== undefined) params.set("page_size", String(filters.page_size));
  return params;
}
