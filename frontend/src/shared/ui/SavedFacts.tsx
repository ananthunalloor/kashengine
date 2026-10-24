import { Stack, Table, Text, Title } from "@mantine/core";

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
    if (
      value.every(
        (row) =>
          row &&
          typeof row === "object" &&
          !Array.isArray(row) &&
          Object.values(row).every((cell) => cell === null || typeof cell !== "object"),
      )
    ) {
      const columns = [...new Set(value.flatMap((row) => Object.keys(row)))];
      return (
        <Table.ScrollContainer minWidth={400}>
          <Table captionSide="top" striped>
            <Table.Thead>
              <Table.Tr>
                {columns.map((key) => (
                  <Table.Th key={key}>{label(key)}</Table.Th>
                ))}
              </Table.Tr>
            </Table.Thead>
            <Table.Tbody>
              {value.map((row, index) => (
                <Table.Tr key={index}>
                  {columns.map((key) => (
                    <Table.Td key={key}>{String(row[key] ?? "Not available")}</Table.Td>
                  ))}
                </Table.Tr>
              ))}
            </Table.Tbody>
          </Table>
        </Table.ScrollContainer>
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
