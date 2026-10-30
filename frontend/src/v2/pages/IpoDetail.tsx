import {
  Accordion,
  Alert,
  Anchor,
  Button,
  Grid,
  Group,
  List,
  SimpleGrid,
  Stack,
  Table,
  Text,
  ThemeIcon,
  Timeline,
} from "@mantine/core";
import { AreaChart, BarChart } from "@mantine/charts";
import { notifications } from "@mantine/notifications";
import type { ReactNode } from "react";
import {
  LuArrowLeft,
  LuBookmark,
  LuCircleCheck,
  LuExternalLink,
  LuTriangleAlert,
} from "react-icons/lu";

import {
  AppLink,
  Delta,
  DescriptionList,
  EmptyState,
  InfoTip,
  Page,
  PageHeader,
  Panel,
  ScoreBar,
  StatusBadge,
  StrengthMeter,
  formatCompactInr,
  formatDate,
  formatInr,
  formatNumber,
  formatSigned,
} from "../components";
import type { Tone } from "../components";
import { findIpo, listingGainPct, statusLabel, verdictLabel } from "../mock/ipos";
import type { Ipo, IpoStatus, IpoVerdict } from "../mock/ipos";

const TODAY = "2026-10-30";

const statusTone: Record<IpoStatus, Tone> = {
  open: "gain",
  upcoming: "info",
  closed: "caution",
  listed: "neutral",
};

const verdictTone: Record<IpoVerdict, Tone> = {
  positive: "gain",
  neutral: "neutral",
  avoid: "loss",
};

function shortDate(iso: string) {
  return formatDate(iso).slice(0, 6);
}

function TimelinePanel({ ipo }: { ipo: Ipo }) {
  const steps = [
    { title: "Bidding opens", date: ipo.openDate, note: "Applications accepted via UPI / ASBA." },
    {
      title: "Bidding closes",
      date: ipo.closeDate,
      note: "UPI mandate cut-off at 17:00 IST on the closing day.",
    },
    {
      title: "Allotment",
      date: ipo.allotmentDate,
      note: "Basis of allotment published by the registrar; refunds start the next day.",
    },
    {
      title: "Listing",
      date: ipo.listingDate,
      note: "Shares credited to demat and trading begins at 10:00 IST.",
    },
  ];
  const active = steps.filter((s) => s.date <= TODAY).length - 1;
  return (
    <Panel
      title="Timeline"
      actions={
        <StatusBadge tone="gain" size="xs">
          On schedule
        </StatusBadge>
      }
    >
      <Timeline active={active} bulletSize={18} lineWidth={2} color="indigo">
        {steps.map((step, i) => (
          <Timeline.Item
            key={step.title}
            title={
              <Group gap={8}>
                <Text size="sm" fw={600}>
                  {step.title}
                </Text>
                {i === active && ipo.status !== "listed" ? (
                  <StatusBadge tone="brand" size="xs">
                    Current
                  </StatusBadge>
                ) : null}
              </Group>
            }
          >
            <Text size="xs" className="kv2-num">
              {formatDate(step.date)}
              {i <= active ? " · done" : ""}
            </Text>
            <Text size="xs" c="dimmed">
              {step.note}
            </Text>
          </Timeline.Item>
        ))}
      </Timeline>
    </Panel>
  );
}

function VerdictCard({ ipo }: { ipo: Ipo }) {
  const average = ipo.signals.reduce((sum, s) => sum + s.score, 0) / ipo.signals.length;
  return (
    <Panel
      title="How the verdict was made"
      info="The score runs from −1 (avoid) to +1 (likely to do well). Each input below is scored 1–10 and weighted; a score ≥ +0.30 is 'Likely to do well', ≤ −0.25 is 'Avoid', and anything between is 'Neutral / fair'."
      footer={
        <Text size="xs" c="dimmed">
          Scored {ipo.scoredAt} · sample model · not investment advice.
        </Text>
      }
    >
      <Stack gap={14}>
        <Stack gap={6}>
          <span className="kv2-eyebrow">Verdict</span>
          <Group gap={8}>
            <StatusBadge tone={verdictTone[ipo.verdict]}>{verdictLabel[ipo.verdict]}</StatusBadge>
            <Text size="lg" fw={700} className="kv2-num">
              {formatSigned(ipo.score)}
            </Text>
            <Text size="xs" c="dimmed">
              / +1.00
            </Text>
          </Group>
          <ScoreBar score={ipo.score} width={240} />
          <Group justify="space-between" maw={240}>
            <Text size="xs" c="dimmed">
              −1 Avoid
            </Text>
            <Text size="xs" c="dimmed">
              +1 Positive
            </Text>
          </Group>
        </Stack>
        {ipo.signals.length === 0 ? (
          <EmptyState title="There is no usable signal yet." />
        ) : (
          <Stack gap={10}>
            <Group gap={4}>
              <span className="kv2-eyebrow">Signal breakdown</span>
              <InfoTip>
                Average input strength {average.toFixed(1)} / 10. Stronger inputs push the score
                further from zero in their direction.
              </InfoTip>
            </Group>
            {ipo.signals.map((signal) => (
              <Stack key={signal.name} gap={2}>
                <Group justify="space-between" gap={8} wrap="nowrap">
                  <Text size="sm" fw={600}>
                    {signal.name}
                  </Text>
                  <Text size="xs" c="dimmed" className="kv2-num">
                    {signal.value}
                  </Text>
                </Group>
                <StrengthMeter
                  score={signal.score}
                  tone={signal.score >= 6 ? "gain" : signal.score <= 4 ? "loss" : "caution"}
                />
                <Text size="xs" c="dimmed">
                  {signal.note}
                </Text>
              </Stack>
            ))}
          </Stack>
        )}
      </Stack>
    </Panel>
  );
}

export function IpoDetailPage({ id }: { id: string }) {
  const ipo = findIpo(id);
  const gain = listingGainPct(ipo);
  const totalSub = ipo.subscription;
  const gmpData = ipo.gmpTrend.map((p) => ({ date: shortDate(p.date), GMP: p.gmp }));
  const financialData = ipo.financials.map((f) => ({
    year: f.year,
    Revenue: Number((f.revenue / 1e7).toFixed(1)),
    "Net profit": Number((f.profit / 1e7).toFixed(1)),
  }));

  const facts: Array<[string, ReactNode]> = [
    [
      "Price band",
      `${formatInr(ipo.priceLow, { decimals: 0 })} – ${formatInr(ipo.priceHigh, { decimals: 0 })}`,
    ],
    [
      "Lot size",
      `${ipo.lotSize} shares · ${formatInr(ipo.lotSize * ipo.priceHigh, { decimals: 0 })} min`,
    ],
    ["Issue size", formatCompactInr(ipo.issueSize)],
    ["Issue structure", `Fresh ${ipo.freshPct}% · Offer for sale ${100 - ipo.freshPct}%`],
    ["Bidding", `${formatDate(ipo.openDate)} – ${formatDate(ipo.closeDate)}`],
    ["Listing date", formatDate(ipo.listingDate)],
  ];
  const facts2: Array<[string, ReactNode]> = [
    ["Board", ipo.board],
    ["Sector", ipo.sector],
    ["Subscribed", totalSub == null ? "Not open yet" : `${formatNumber(totalSub, 2)}x`],
    [
      "GMP",
      ipo.gmp == null ? (
        "No quotes"
      ) : (
        <Group gap={6}>
          <span className="kv2-num">₹{formatSigned(ipo.gmp, 0)}</span>
          <Delta value={(ipo.gmp / ipo.priceHigh) * 100} decimals={1} size="xs" />
        </Group>
      ),
    ],
    [
      ipo.listedAt != null ? "Listing gain" : "Est. listing gain",
      gain == null ? "—" : <Delta value={gain} decimals={1} size="xs" />,
    ],
    ["Lead managers", ipo.managers],
    ["Registrar", ipo.registrar],
  ];

  return (
    <Page>
      <PageHeader
        crumbs={[{ label: "All IPOs", to: "/v2/ipos/" }, { label: ipo.name }]}
        title={ipo.name}
        meta={
          <Group gap={6}>
            <StatusBadge tone="outline" size="xs">
              <span className="kv2-mono">{ipo.symbol}</span>
            </StatusBadge>
            <StatusBadge tone={ipo.board === "SME" ? "caution" : "outline"} size="xs">
              {ipo.board}
            </StatusBadge>
            <StatusBadge tone={statusTone[ipo.status]} dot pulse={ipo.status === "open"} size="xs">
              {statusLabel[ipo.status]}
            </StatusBadge>
            <StatusBadge tone={verdictTone[ipo.verdict]} size="xs">
              {verdictLabel[ipo.verdict]} · {formatSigned(ipo.score)}
            </StatusBadge>
          </Group>
        }
        description={`${ipo.sector} · book-built issue · sample data`}
        actions={
          <>
            <Button
              variant="default"
              leftSection={<LuArrowLeft size={14} />}
              component={AppLink}
              href="/v2/ipos/"
            >
              All IPOs
            </Button>
            <Button
              leftSection={<LuBookmark size={14} />}
              onClick={() =>
                notifications.show({
                  title: "Added to watchlist",
                  message: `You'll be notified when ${ipo.name} changes status (sample).`,
                })
              }
            >
              Watch IPO
            </Button>
          </>
        }
      />

      <Grid gutter={16}>
        <Grid.Col span={{ base: 12, md: 8 }}>
          <Stack gap={16}>
            <Panel
              title="The issue"
              actions={
                <Anchor href="#" size="xs" onClick={(e) => e.preventDefault()}>
                  <Group gap={4} wrap="nowrap">
                    Offer document <LuExternalLink size={12} />
                  </Group>
                </Anchor>
              }
            >
              <SimpleGrid cols={{ base: 1, sm: 2 }} spacing={24}>
                <DescriptionList items={facts} />
                <DescriptionList items={facts2} />
              </SimpleGrid>
            </Panel>

            <TimelinePanel ipo={ipo} />

            <SimpleGrid cols={{ base: 1, md: 2 }} spacing={16}>
              <Panel
                title="Subscription by category"
                info="How many times each investor category's reserved portion has been bid for. QIB = qualified institutions, NII = high-net-worth individuals."
                actions={
                  totalSub == null ? null : (
                    <Text size="xs" fw={600} className="kv2-num">
                      {formatNumber(totalSub, 2)}x overall
                    </Text>
                  )
                }
              >
                {ipo.subByCategory.length === 0 ? (
                  <EmptyState
                    title="Bidding hasn't started"
                    description={`Subscription figures appear from ${formatDate(ipo.openDate)}.`}
                  />
                ) : (
                  <BarChart
                    h={200}
                    data={ipo.subByCategory}
                    dataKey="category"
                    orientation="vertical"
                    yAxisProps={{ width: 80 }}
                    series={[{ name: "times", label: "Subscribed (x)", color: "indigo.6" }]}
                    valueFormatter={(v) => `${formatNumber(v, 2)}x`}
                    gridAxis="x"
                  />
                )}
              </Panel>
              <Panel
                title="GMP trend"
                info="Grey market premium: the unofficial premium (₹ per share) traders quote before listing, captured once a day at 18:00 IST. Unregulated and indicative only."
              >
                {ipo.gmp == null ? (
                  <EmptyState
                    title="No grey market quotes"
                    description="No reliable GMP quotes have been seen for this issue yet."
                  />
                ) : (
                  <AreaChart
                    h={200}
                    data={gmpData}
                    dataKey="date"
                    series={[{ name: "GMP", color: "emerald.6" }]}
                    valueFormatter={(v) => `₹${formatSigned(v, 0)}`}
                    curveType="monotone"
                    withDots={false}
                    referenceLines={[{ y: 0, color: "slate.4" }]}
                  />
                )}
              </Panel>
            </SimpleGrid>

            <Panel
              title="Financials"
              info="Revenue and net profit from the offer document, in ₹ crore, for the last three financial years."
              flush
            >
              <Stack gap={0}>
                <div style={{ padding: 12 }}>
                  <BarChart
                    h={180}
                    data={financialData}
                    dataKey="year"
                    series={[
                      { name: "Revenue", color: "indigo.6" },
                      { name: "Net profit", color: "emerald.6" },
                    ]}
                    valueFormatter={(v) => `₹${formatNumber(v, 0)} Cr`}
                    withLegend
                  />
                </div>
                <div className="kv2-table-wrap">
                  <Table>
                    <Table.Thead>
                      <Table.Tr>
                        <Table.Th>Year</Table.Th>
                        <Table.Th data-align="right">Revenue</Table.Th>
                        <Table.Th data-align="right">Net profit</Table.Th>
                        <Table.Th data-align="right">Margin</Table.Th>
                        <Table.Th data-align="right">Net worth</Table.Th>
                      </Table.Tr>
                    </Table.Thead>
                    <Table.Tbody>
                      {ipo.financials.map((f) => (
                        <Table.Tr key={f.year}>
                          <Table.Td>{f.year}</Table.Td>
                          <Table.Td data-align="right" className="kv2-num">
                            {formatCompactInr(f.revenue)}
                          </Table.Td>
                          <Table.Td data-align="right" className="kv2-num">
                            {formatCompactInr(f.profit)}
                          </Table.Td>
                          <Table.Td data-align="right">
                            <Delta value={(f.profit / f.revenue) * 100} decimals={1} size="xs" />
                          </Table.Td>
                          <Table.Td data-align="right" className="kv2-num">
                            {formatCompactInr(f.netWorth)}
                          </Table.Td>
                        </Table.Tr>
                      ))}
                    </Table.Tbody>
                  </Table>
                </div>
              </Stack>
            </Panel>

            <SimpleGrid cols={{ base: 1, md: 2 }} spacing={16}>
              <Panel title="Strengths">
                <List
                  spacing={8}
                  size="sm"
                  icon={
                    <ThemeIcon size={18} radius="xl" color="emerald" variant="light">
                      <LuCircleCheck size={12} />
                    </ThemeIcon>
                  }
                >
                  {ipo.strengths.map((s) => (
                    <List.Item key={s}>{s}</List.Item>
                  ))}
                </List>
              </Panel>
              <Panel title="Risks">
                <List
                  spacing={8}
                  size="sm"
                  icon={
                    <ThemeIcon size={18} radius="xl" color="red" variant="light">
                      <LuTriangleAlert size={12} />
                    </ThemeIcon>
                  }
                >
                  {ipo.risks.map((r) => (
                    <List.Item key={r}>{r}</List.Item>
                  ))}
                </List>
              </Panel>
            </SimpleGrid>

            <Panel flush>
              <Accordion variant="default">
                <Accordion.Item value="raw">
                  <Accordion.Control>
                    <Text size="sm" fw={600}>
                      Timeline, registrar, subscription and complete saved facts
                    </Text>
                  </Accordion.Control>
                  <Accordion.Panel>
                    <DescriptionList
                      items={[
                        ["Saved", `${formatDate(TODAY)}, 09:12 IST`],
                        ["Symbol", <span className="kv2-mono">{ipo.symbol}</span>],
                        ["Open / close", `${ipo.openDate} → ${ipo.closeDate}`],
                        ["Allotment", ipo.allotmentDate],
                        ["Listing", ipo.listingDate],
                        ["Registrar", ipo.registrar],
                        [
                          "Subscription",
                          ipo.subByCategory.length
                            ? ipo.subByCategory.map((c) => `${c.category} ${c.times}x`).join(" · ")
                            : "—",
                        ],
                        [
                          "Listed at",
                          ipo.listedAt == null ? "Not listed" : formatInr(ipo.listedAt),
                        ],
                      ]}
                    />
                  </Accordion.Panel>
                </Accordion.Item>
              </Accordion>
            </Panel>
          </Stack>
        </Grid.Col>

        <Grid.Col span={{ base: 12, md: 4 }}>
          <div style={{ position: "sticky", top: 72 }}>
            <Stack gap={16}>
              <VerdictCard ipo={ipo} />
              <Alert
                color="amber"
                variant="light"
                icon={<LuTriangleAlert size={16} />}
                title="GMP is unofficial"
              >
                <Text size="xs">
                  Grey market trades have no exchange clearing or guarantee. Treat GMP as a rough
                  sentiment gauge, not a price forecast.
                </Text>
              </Alert>
            </Stack>
          </div>
        </Grid.Col>
      </Grid>
    </Page>
  );
}
