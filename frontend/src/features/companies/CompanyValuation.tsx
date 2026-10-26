import { Accordion, Alert, Badge, Group, Paper, Stack, Table, Text, Title } from "@mantine/core";
import type { CompanyDetail } from "../../shared/api/generated/types.gen";
import { collectFacts, comparableNumber } from "./fundamentalFacts";

const number = new Intl.NumberFormat("en-IN", { maximumFractionDigits: 2 });
const timestamp = new Intl.DateTimeFormat("en-IN", {
  timeZone: "Asia/Kolkata",
  dateStyle: "medium",
  timeStyle: "short",
});
const metrics = [
  {
    label: "P/E",
    aliases: [
      "pe",
      "peratio",
      "pricetoearnings",
      "priceearnings",
      "priceearningsratio",
      "pricetoearningsratio",
    ],
    meaning: "Price paid per unit of earnings",
  },
  {
    label: "P/B",
    aliases: [
      "pb",
      "pbratio",
      "pricetobook",
      "pricebook",
      "pricebookratio",
      "pricetobookratio",
      "pricetobookvalue",
    ],
    meaning: "Price paid per unit of book value",
  },
  {
    label: "EV/EBITDA",
    aliases: ["evebitda", "evebitdaratio", "enterprisevaluetoebitda"],
    meaning: "Enterprise value relative to operating earnings",
  },
] as const;

export function sectorValuation(fundamentals: CompanyDetail["fundamentals"]) {
  const facts = collectFacts(fundamentals);
  const rows = metrics.map((metric) => {
    const matches = facts.filter((fact) => {
      const label = fact.label
        .split(" · ")
        .at(-1)!
        .toLowerCase()
        .replace(/[^a-z0-9]/g, "");
      return metric.aliases.some((alias) => alias === label);
    });
    const fact = matches[0];
    const company = fact ? comparableNumber(fact.value) : null;
    const sector = fact ? comparableNumber(fact.comparison) : null;
    const conflict = matches.some(
      (other) =>
        comparableNumber(other.value) !== company || comparableNumber(other.comparison) !== sector,
    );
    const invalid = matches.some((other) =>
      [other.value, other.comparison].some(
        (value) => typeof value === "string" && value.includes("%"),
      ),
    );
    const reason = conflict
      ? "Conflicting saved values"
      : invalid
        ? "Unexpected percentage unit"
        : company === null || sector === null
          ? "Missing company or sector value"
          : company <= 0 || sector <= 0
            ? "Non-positive multiple; not comparable"
            : null;
    const difference =
      reason === null && company !== null && sector !== null ? (company / sector - 1) * 100 : null;
    return {
      ...metric,
      company: conflict || invalid ? null : company,
      sector: conflict || invalid ? null : sector,
      difference,
      reason,
    };
  });
  const compared = rows.filter((row) => row.difference !== null);
  const premium = compared.some((row) => row.difference! > 1e-10);
  const discount = compared.some((row) => row.difference! < -1e-10);
  const state = !compared.length
    ? "Insufficient data"
    : premium && discount
      ? "Mixed valuation"
      : premium
        ? "Sector premium"
        : discount
          ? "Sector discount"
          : "In line with sector";
  return { rows, compared: compared.length, state };
}

export function CompanyValuation({
  data,
}: {
  data: Pick<CompanyDetail, "fundamentals" | "fundamentals_as_of">;
}) {
  const valuation = sectorValuation(data.fundamentals);
  const color =
    valuation.state === "Sector premium"
      ? "orange"
      : valuation.state === "Sector discount"
        ? "blue"
        : "gray";
  const saved = data.fundamentals_as_of ? Date.parse(data.fundamentals_as_of) : Number.NaN;
  const explanation =
    valuation.state === "Sector premium"
      ? "More expensive than the sector on the available multiples. This may flag relative overvaluation, but stronger growth or returns can justify a premium."
      : valuation.state === "Sector discount"
        ? "Cheaper than the sector on the available multiples. A discount is not proof of undervaluation; weaker earnings, debt or business risk can explain it."
        : valuation.state === "Mixed valuation"
          ? "Some multiples are above the sector and others below. There is no clear relative valuation verdict."
          : valuation.state === "In line with sector"
            ? "The available multiples match their sector benchmarks. This does not establish fair value."
            : "There are not enough comparable positive company and sector multiples to judge relative valuation.";
  return (
    <Paper
      component="section"
      id="company-valuation"
      aria-label="Company valuation"
      withBorder
      p="lg"
    >
      <Stack gap="md">
        <Group justify="space-between" align="center">
          <Title order={2} size="h3">
            Is this company overvalued?
          </Title>
          <Badge variant="light" color="gray">
            Sector-relative check
          </Badge>
        </Group>
        <Alert color={color} title={valuation.state}>
          {explanation}
        </Alert>
        <Group gap="sm">
          <Badge variant="light" color="gray">
            {valuation.compared} of 3 multiples comparable
          </Badge>
          <Text size="xs" c="dimmed">
            {Number.isFinite(saved)
              ? `Saved ${timestamp.format(new Date(saved))} IST · not live`
              : "Save time unknown · freshness cannot be verified"}
          </Text>
        </Group>
        {valuation.compared === 1 && (
          <Text size="sm" c="dimmed">
            Limited evidence: the verdict relies on just one multiple.
          </Text>
        )}
        <Table.ScrollContainer minWidth={500}>
          <Table withTableBorder withRowBorders>
            <Table.Caption>Valuation multiples vs sector</Table.Caption>
            <Table.Thead>
              <Table.Tr>
                <Table.Th>Multiple</Table.Th>
                <Table.Th>Company</Table.Th>
                <Table.Th>Sector</Table.Th>
                <Table.Th>Comparison</Table.Th>
              </Table.Tr>
            </Table.Thead>
            <Table.Tbody>
              {valuation.rows.map((row) => (
                <Table.Tr key={row.label}>
                  <Table.Td>
                    <Text fw={600} size="sm">
                      {row.label}
                    </Text>
                    <Text size="xs" c="dimmed">
                      {row.meaning}
                    </Text>
                  </Table.Td>
                  <Table.Td>
                    {row.company === null ? "Not available" : `${number.format(row.company)}x`}
                  </Table.Td>
                  <Table.Td>
                    {row.sector === null ? "Not available" : `${number.format(row.sector)}x`}
                  </Table.Td>
                  <Table.Td>
                    {row.difference === null ? (
                      <Text size="sm" c="dimmed">
                        {row.reason}
                      </Text>
                    ) : Math.abs(row.difference) <= 1e-10 ? (
                      "In line"
                    ) : (
                      `${number.format(Math.abs(row.difference))}% ${row.difference > 0 ? "premium" : "discount"}`
                    )}
                  </Table.Td>
                </Table.Tr>
              ))}
            </Table.Tbody>
          </Table>
        </Table.ScrollContainer>
        <Text size="xs" c="dimmed">
          A sector premium is not proof of overvaluation. This is not a fair-value price, price
          target or buy/sell recommendation.
        </Text>
        <Accordion variant="separated">
          <Accordion.Item value="valuation-method">
            <Accordion.Control>How to read this valuation</Accordion.Control>
            <Accordion.Panel>
              <Stack gap="sm">
                <Text size="sm">
                  Premium/discount = (company multiple / sector multiple - 1) x 100. All usable
                  multiples above the sector (allowing equal ones) indicate a premium; all below
                  indicate a discount. Opposing comparisons are mixed. No ratios are averaged into a
                  fair-value price.
                </Text>
                <Text size="sm">
                  Only positive P/E, P/B and EV/EBITDA company/sector pairs are compared. Missing,
                  negative, zero, conflicting or incorrectly unit-labelled values are excluded.
                  Identical duplicate observations count once. Missing ratios are not treated as
                  zero.
                </Text>
                <Text size="sm">
                  Check reporting periods, trailing versus forward estimates, accounting basis and
                  sector composition. These may not be supplied with the saved data. Growth,
                  profitability, cash flow and debt can justify different multiples; the sector
                  itself can be expensive or cheap.
                </Text>
              </Stack>
            </Accordion.Panel>
          </Accordion.Item>
        </Accordion>
      </Stack>
    </Paper>
  );
}
