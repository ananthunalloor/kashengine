import { Button, Skeleton, Stack, Text } from "@mantine/core";
import { LuCircleAlert, LuInbox } from "react-icons/lu";
import type { ReactNode } from "react";

export function EmptyState({
  title,
  description,
  action,
  icon,
}: {
  title: string;
  description?: ReactNode;
  action?: ReactNode;
  icon?: ReactNode;
}) {
  return (
    <div className="kv2-state">
      <span className="kv2-state-icon">{icon ?? <LuInbox size={18} />}</span>
      <Text size="sm" fw={600} c="var(--kv2-text)">
        {title}
      </Text>
      {description ? (
        <Text size="xs" maw={360}>
          {description}
        </Text>
      ) : null}
      {action}
    </div>
  );
}

export function ErrorState({
  title = "Couldn't load this section",
  description = "Something went wrong while fetching data. Try again in a moment.",
  onRetry,
}: {
  title?: string;
  description?: ReactNode;
  onRetry?: () => void;
}) {
  return (
    <div className="kv2-state" role="alert">
      <span className="kv2-state-icon" data-tone="loss">
        <LuCircleAlert size={18} />
      </span>
      <Text size="sm" fw={600} c="var(--kv2-text)">
        {title}
      </Text>
      <Text size="xs" maw={360}>
        {description}
      </Text>
      {onRetry ? (
        <Button size="xs" variant="default" onClick={onRetry}>
          Retry
        </Button>
      ) : null}
    </div>
  );
}

export function SkeletonRows({ rows = 5 }: { rows?: number }) {
  return (
    <Stack gap={10} p={12}>
      {Array.from({ length: rows }, (_, i) => (
        <Skeleton key={i} height={14} width={`${90 - (i % 3) * 15}%`} />
      ))}
    </Stack>
  );
}
