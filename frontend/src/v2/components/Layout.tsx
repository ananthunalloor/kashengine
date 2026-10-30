import {
  Anchor,
  Breadcrumbs,
  Group,
  Popover,
  SimpleGrid,
  Stack,
  Text,
  UnstyledButton,
} from "@mantine/core";
import { LuInfo } from "react-icons/lu";
import type { ReactNode } from "react";

import { AppLink } from "../../shared/ui/AppLink";

export type Crumb = { label: string; to?: string };

/** Page title row: breadcrumbs, title, optional meta line, actions on the right. */
export function PageHeader({
  title,
  crumbs,
  description,
  meta,
  actions,
}: {
  title: ReactNode;
  crumbs?: Crumb[];
  description?: ReactNode;
  meta?: ReactNode;
  actions?: ReactNode;
}) {
  return (
    <header className="kv2-page-header">
      <Stack gap={4} style={{ minWidth: 0 }}>
        {crumbs?.length ? (
          <Breadcrumbs separator="/" separatorMargin={6} fz="xs">
            {crumbs.map((crumb) =>
              crumb.to ? (
                <Anchor key={crumb.label} component={AppLink} href={crumb.to} fz="xs" c="dimmed">
                  {crumb.label}
                </Anchor>
              ) : (
                <Text key={crumb.label} fz="xs" c="dimmed">
                  {crumb.label}
                </Text>
              ),
            )}
          </Breadcrumbs>
        ) : null}
        <Group gap={8} wrap="wrap">
          <h1 className="kv2-page-title">{title}</h1>
          {meta}
        </Group>
        {description ? (
          <Text size="sm" c="dimmed" maw={720}>
            {description}
          </Text>
        ) : null}
      </Stack>
      {actions ? (
        <Group gap={8} wrap="wrap">
          {actions}
        </Group>
      ) : null}
    </header>
  );
}

/** Small (i) trigger that explains a metric in a popover. */
export function InfoTip({
  children,
  label = "About this",
}: {
  children: ReactNode;
  label?: string;
}) {
  return (
    <Popover width={280} position="bottom-start" withArrow>
      <Popover.Target>
        <UnstyledButton aria-label={label} c="dimmed" style={{ display: "inline-flex" }}>
          <LuInfo size={14} />
        </UnstyledButton>
      </Popover.Target>
      <Popover.Dropdown>
        <Text size="xs">{children}</Text>
      </Popover.Dropdown>
    </Popover>
  );
}

/** Bordered surface with optional header (title, info, actions) and footer. */
export function Panel({
  title,
  info,
  actions,
  footer,
  flush = false,
  children,
  className,
}: {
  title?: ReactNode;
  info?: ReactNode;
  actions?: ReactNode;
  footer?: ReactNode;
  flush?: boolean;
  children: ReactNode;
  className?: string;
}) {
  return (
    <section className={`kv2-panel ${className ?? ""}`}>
      {title || actions ? (
        <div className="kv2-panel-header">
          <Group gap={6} wrap="nowrap" style={{ minWidth: 0 }}>
            {typeof title === "string" ? <h2 className="kv2-panel-title">{title}</h2> : title}
            {info ? <InfoTip>{info}</InfoTip> : null}
          </Group>
          {actions ? (
            <Group gap={6} wrap="nowrap">
              {actions}
            </Group>
          ) : null}
        </div>
      ) : null}
      <div className="kv2-panel-body" data-flush={flush}>
        {children}
      </div>
      {footer ? <div className="kv2-panel-footer">{footer}</div> : null}
    </section>
  );
}

/** Compact metric tile: label, value, optional delta/hint line and trailing visual. */
export function KpiTile({
  label,
  value,
  delta,
  hint,
  info,
  aside,
}: {
  label: ReactNode;
  value: ReactNode;
  delta?: ReactNode;
  hint?: ReactNode;
  info?: ReactNode;
  aside?: ReactNode;
}) {
  return (
    <div className="kv2-kpi">
      <Group gap={4} justify="space-between" wrap="nowrap">
        <Group gap={4} wrap="nowrap">
          <span className="kv2-eyebrow">{label}</span>
          {info ? <InfoTip>{info}</InfoTip> : null}
        </Group>
        {aside}
      </Group>
      <span className="kv2-kpi-value">{value}</span>
      {delta || hint ? (
        <Group gap={6} wrap="wrap">
          {delta}
          {hint ? (
            <Text size="xs" c="dimmed">
              {hint}
            </Text>
          ) : null}
        </Group>
      ) : null}
    </div>
  );
}

export function KpiGrid({ children, cols = 4 }: { children: ReactNode; cols?: number }) {
  return (
    <SimpleGrid
      cols={{ base: 1, xs: Math.min(2, cols), sm: cols === 3 ? 3 : 2, md: cols }}
      spacing={12}
      verticalSpacing={12}
    >
      {children}
    </SimpleGrid>
  );
}

/** Two-column term/definition list. */
export function DescriptionList({ items }: { items: Array<[ReactNode, ReactNode]> }) {
  return (
    <dl className="kv2-dl">
      {items.map(([term, detail], index) => (
        <div key={index} style={{ display: "contents" }}>
          <dt>{term}</dt>
          <dd>{detail}</dd>
        </div>
      ))}
    </dl>
  );
}

export function Page({ children }: { children: ReactNode }) {
  return <div className="kv2-page">{children}</div>;
}
