export type ApiErrorKind =
  | "unauthorized"
  | "forbidden"
  | "rate-limited"
  | "validation"
  | "not-found"
  | "server"
  | "network"
  | "contract";

export class ApiError extends Error {
  readonly kind: ApiErrorKind;
  readonly status: number;
  readonly code: string;
  readonly retryAfter: number | null;

  constructor(
    kind: ApiErrorKind,
    message: string,
    options: { status?: number; code?: string; retryAfter?: number | null } = {},
  ) {
    super(message);
    this.name = "ApiError";
    this.kind = kind;
    this.status = options.status ?? 0;
    this.code = options.code ?? kind;
    this.retryAfter = options.retryAfter ?? null;
  }
}

export function retryAfterMilliseconds(value: string | null, now = Date.now()): number | null {
  if (value === null) return null;
  const seconds = Number(value);
  if (value.trim() && Number.isFinite(seconds)) return seconds >= 0 ? seconds * 1000 : null;
  const timestamp = Date.parse(value);
  return Number.isFinite(timestamp) ? Math.max(0, timestamp - now) : null;
}

export function shouldRetry(failureCount: number, error: Error): boolean {
  if (!(error instanceof ApiError) || failureCount >= 2) return false;
  return ["network", "server", "rate-limited"].includes(error.kind);
}

export function retryDelay(attempt: number, error: Error): number {
  if (error instanceof ApiError && error.retryAfter !== null) return error.retryAfter;
  return Math.min(1000 * 2 ** attempt, 30_000);
}
