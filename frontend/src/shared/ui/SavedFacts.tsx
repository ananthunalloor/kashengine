import { Stack, Text, Title } from "@mantine/core";

import { DataTable } from "./DataTable";
import type { TableColumn } from "./DataTable";

type FlatFact = Record<string, string | number | boolean | null>;

function isFlatFact(value: unknown): value is FlatFact {
  return Boolean(
    value &&
    typeof value === "object" &&
    !Array.isArray(value) &&
    Object.values(value).every(
      (cell) => cell === null || ["string", "number", "boolean"].includes(typeof cell),
    ),
  );
}

function label(value: string) {
  return value.replaceAll("_", " ").replaceAll("-", " ");
}

/** Render stored provider facts as escaped values, never provider HTML or executable links. */
export function SavedFacts({ value }: { value: unknown }) {
  if (value === null || value === undefined || value === "")
    return <Text c="dimmed">Not available</Text>;
  if (typeof value !== "object") return <Text>{String(value)}</Text>;
  if (Array.isArray(value)) {
    if (!value.length) return <Text c="dimmed">No saved records.</Text>;
    if (value.every(isFlatFact)) {
      const columns = [...new Set(value.flatMap((row) => Object.keys(row)))];
      const definitions: TableColumn<FlatFact>[] = columns.map((key) => ({
        id: key,
        label: label(key),
        value: (row) => (typeof row[key] === "boolean" ? String(row[key]) : row[key]),
        render: (row) => String(row[key] ?? "Not available"),
      }));
      return (
        <DataTable
          data={value}
          columns={definitions}
          label="Saved provider facts"
          initialSort={columns.length ? [{ id: columns[0]!, desc: false }] : []}
        />
      );
    }
    return (
      <Stack gap="md">
        {value.map((item, index) => (
          <SavedFacts key={index} value={item} />
        ))}
      </Stack>
    );
  }
  const entries = Object.entries(value);
  if (!entries.length) return <Text c="dimmed">No saved data.</Text>;
  return (
    <Stack gap="sm">
      {entries.map(([key, item]) => (
        <section key={key}>
          <Title order={4} size="sm" tt="capitalize">
            {label(key)}
          </Title>
          <SavedFacts value={item} />
        </section>
      ))}
    </Stack>
  );
}
