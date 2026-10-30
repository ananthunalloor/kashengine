import { BarChart, DonutChart } from "@mantine/charts";
import {
  Anchor,
  Box,
  Button,
  Chip,
  Collapse,
  Grid,
  Group,
  Progress,
  SegmentedControl,
  Select,
  Stack,
  Text,
  TextInput,
  Tooltip,
  UnstyledButton,
} from "@mantine/core";
import { useDebouncedValue } from "@mantine/hooks";
import { notifications } from "@mantine/notifications";
import { useMemo, useState } from "react";
import {
  LuChevronDown,
  LuChevronUp,
  LuExternalLink,
  LuRefreshCw,
  LuSearch,
  LuSparkles,
  LuX,
} from "react-icons/lu";

import {
  AppLink,
  DescriptionList,
  EmptyState,
  FreshnessTag,
  KpiGrid,
  KpiTile,
  Page,
  PageHeader,
  Panel,
  ScoreBar,
  SentimentPill,
  StatusBadge,
  SymbolChip,
  formatSigned,
} from "../components";
import { companies, sampleUser } from "../mock/data";
import { NEWS_NOW, articles, newsSources, sentimentByHour } from "../mock/news";
import type { Article } from "../mock/news";

type Bucket = "positive" | "neutral" | "negative";

const companyById = new Map(companies.map((c) => [c.id, c]));

function bucketOf(score: number | null): Bucket | null {
  if (score == null) return null;
  return score >= 0.15 ? "positive" : score <= -0.15 ? "negative" : "neutral";
}

function clock(minutesAgo: number) {
  const at = (((NEWS_NOW.minutes - minutesAgo) % 1440) + 1440) % 1440;
  const hhmm = `${String(Math.floor(at / 60)).padStart(2, "0")}:${String(at % 60).padStart(2, "0")} IST`;
  return minutesAgo > NEWS_NOW.minutes ? `Yesterday ${hhmm}` : hhmm;
}

function ago(minutes: number) {
  if (minutes < 60) return `${minutes}m ago`;
  const h = Math.floor(minutes / 60);
  return h < 24 ? `${h}h ${minutes % 60}m ago` : `${Math.floor(h / 24)}d ago`;
}

const timeWindows: Record<string, number> = { "1h": 60, "6h": 360, "24h": 1440, all: Infinity };

function ArticleRow({
  article,
  expanded,
  onToggle,
}: {
  article: Article;
  expanded: boolean;
  onToggle: () => void;
}) {
  return (
    <Box px={12} py={10} style={{ borderTop: "1px solid var(--kv2-border)" }}>
      <Group align="flex-start" gap={12} wrap="nowrap">
        <Box w={{ base: 92, sm: 132 }} style={{ flexShrink: 0 }}>
          {article.sentiment == null ? (
            <StatusBadge tone="caution" size="xs">
              Not scored yet
            </StatusBadge>
          ) : (
            <Stack gap={6}>
              <SentimentPill score={article.sentiment} size="xs" />
              <Box visibleFrom="sm">
                <ScoreBar score={article.sentiment} width={110} />
              </Box>
            </Stack>
          )}
        </Box>
        <Stack gap={4} style={{ flex: 1, minWidth: 0 }}>
          <Anchor
            href={article.url}
            target="_blank"
            rel="noopener noreferrer"
            size="sm"
            fw={600}
            c="var(--kv2-text)"
            lineClamp={2}
          >
            {article.title}{" "}
            <LuExternalLink size={11} style={{ verticalAlign: "-1px", opacity: 0.6 }} />
          </Anchor>
          <Text size="xs" c="dimmed" lineClamp={1}>
            {article.sentiment == null
              ? "Waiting for the scoring job — usually within 5 minutes."
              : article.reason}
          </Text>
          <Group gap={6} wrap="wrap">
            <StatusBadge tone="outline" size="xs">
              {article.topic}
            </StatusBadge>
            {article.companyIds.map((id) => {
              const c = companyById.get(id);
              return c ? (
                <Tooltip key={id} label={c.name}>
                  <Anchor component={AppLink} href={`/v2/companies/${id}/`} underline="never">
                    <SymbolChip symbol={c.symbol} />
                  </Anchor>
                </Tooltip>
              ) : null;
            })}
            {article.sentiment != null ? (
              <UnstyledButton
                onClick={onToggle}
                aria-expanded={expanded}
                c="var(--kv2-brand)"
                fz="xs"
                fw={500}
              >
                <Group gap={2} wrap="nowrap">
                  Why this score{" "}
                  {expanded ? <LuChevronUp size={12} /> : <LuChevronDown size={12} />}
                </Group>
              </UnstyledButton>
            ) : null}
          </Group>
          <Group gap={6} hiddenFrom="sm">
            <Text size="xs" c="dimmed">
              {article.source} · {ago(article.minutesAgo)}
            </Text>
          </Group>
        </Stack>
        <Stack gap={4} align="flex-end" w={150} visibleFrom="sm" style={{ flexShrink: 0 }}>
          <Text size="xs" fw={500} ta="right">
            {article.source}
          </Text>
          <Text size="xs" c="dimmed" className="kv2-num" ta="right">
            {ago(article.minutesAgo)} · {clock(article.minutesAgo)}
          </Text>
          <Group gap={6} wrap="nowrap">
            <StatusBadge tone={article.region === "local" ? "neutral" : "info"} size="xs">
              {article.region === "local" ? "Local" : "Intl"}
            </StatusBadge>
            <Tooltip label={`Relevance ${article.relevance.toFixed(2)} / 1`}>
              <Progress
                value={article.relevance * 100}
                w={48}
                size={4}
                color="indigo.6"
                aria-label="Relevance"
              />
            </Tooltip>
          </Group>
        </Stack>
      </Group>
      <Collapse in={expanded}>
        <Box
          mt={10}
          ml={{ base: 0, sm: 144 }}
          p={10}
          style={{ background: "var(--kv2-surface-muted)", borderRadius: 4 }}
        >
          <Group gap={6} mb={6}>
            <LuSparkles size={14} color="var(--kv2-brand)" />
            <Text size="xs" fw={600}>
              How the score was built
            </Text>
          </Group>
          <Text size="xs" mb={8}>
            {article.reason}
          </Text>
          <Stack gap={4} mb={10}>
            {article.factors.map((f) => (
              <Group key={f.phrase} gap={8} wrap="nowrap">
                <Text
                  size="xs"
                  fw={600}
                  w={44}
                  ta="right"
                  className={`kv2-num ${f.effect >= 0 ? "kv2-gain" : "kv2-loss"}`}
                >
                  {formatSigned(f.effect)}
                </Text>
                <ScoreBar score={f.effect * 2} width={64} />
                <Text size="xs" c="dimmed">
                  “{f.phrase}”
                </Text>
              </Group>
            ))}
          </Stack>
          <DescriptionList
            items={[
              [
                "Sentiment",
                <span className="kv2-num">{formatSigned(article.sentiment)} (−1 to +1)</span>,
              ],
              [
                "Relevance",
                <span className="kv2-num">
                  {article.relevance.toFixed(2)} — how directly the story affects the linked
                  companies
                </span>,
              ],
              [
                "Confidence",
                <span className="kv2-num">{Math.round(article.confidence * 100)}%</span>,
              ],
              [
                "Linked by",
                article.companyIds.length
                  ? "Company name match in headline and body"
                  : "Sector keywords",
              ],
            ]}
          />
        </Box>
      </Collapse>
    </Box>
  );
}

export function NewsPage() {
  const [coverage, setCoverage] = useState("all");
  const [search, setSearch] = useState("");
  const [debounced] = useDebouncedValue(search, 250);
  const [buckets, setBuckets] = useState<string[]>([]);
  const [source, setSource] = useState<string | null>(null);
  const [company, setCompany] = useState<string | null>(null);
  const [window_, setWindow] = useState<string | null>("all");
  const [expanded, setExpanded] = useState<string | null>(null);
  const [limit, setLimit] = useState(15);

  const counts = useMemo(
    () => ({
      all: articles.length,
      local: articles.filter((a) => a.region === "local").length,
      international: articles.filter((a) => a.region === "international").length,
    }),
    [],
  );

  const filtered = useMemo(() => {
    const q = debounced.trim().toLowerCase();
    const maxAge = timeWindows[window_ ?? "all"];
    return articles.filter((a) => {
      if (coverage !== "all" && a.region !== coverage) return false;
      if (buckets.length) {
        const b = bucketOf(a.sentiment);
        if (!b || !buckets.includes(b)) return false;
      }
      if (source && a.source !== source) return false;
      if (company && !a.companyIds.includes(company)) return false;
      if (a.minutesAgo > maxAge) return false;
      if (q && !`${a.title} ${a.reason} ${a.topic}`.toLowerCase().includes(q)) return false;
      return true;
    });
  }, [coverage, debounced, buckets, source, company, window_]);

  const filtersActive =
    search !== "" ||
    buckets.length > 0 ||
    source != null ||
    company != null ||
    window_ !== "all" ||
    coverage !== "all";
  const clear = () => {
    setCoverage("all");
    setSearch("");
    setBuckets([]);
    setSource(null);
    setCompany(null);
    setWindow("all");
  };

  const day = articles.filter((a) => a.minutesAgo <= 1440);
  const scored = day.filter((a) => a.sentiment != null);
  const avg = scored.reduce((s, a) => s + (a.sentiment ?? 0), 0) / Math.max(1, scored.length);
  const mix = {
    positive: scored.filter((a) => bucketOf(a.sentiment) === "positive").length,
    neutral: scored.filter((a) => bucketOf(a.sentiment) === "neutral").length,
    negative: scored.filter((a) => bucketOf(a.sentiment) === "negative").length,
  };
  const unscored = articles.filter((a) => a.sentiment == null).length;

  const mentions = useMemo(() => {
    const map = new Map<string, { n: number; sum: number }>();
    for (const a of articles) {
      if (a.sentiment == null) continue;
      for (const id of a.companyIds) {
        const m = map.get(id) ?? { n: 0, sum: 0 };
        map.set(id, { n: m.n + 1, sum: m.sum + a.sentiment });
      }
    }
    return [...map.entries()].sort((a, b) => b[1].n - a[1].n).slice(0, 6);
  }, []);

  const companyOptions = useMemo(() => {
    const ids = new Set(articles.flatMap((a) => a.companyIds));
    return companies
      .filter((c) => ids.has(c.id))
      .map((c) => ({ value: c.id, label: `${c.name} (${c.symbol})` }));
  }, []);

  const visible = filtered.slice(0, limit);

  return (
    <Page>
      <PageHeader
        title="Scored news"
        meta={<FreshnessTag state="live" detail="updated 2m ago" />}
        description="Every article is scored for sentiment (−1 very negative … +1 very positive) and relevance (0–1), with a one-line reason and the companies it affects. Open a row's “Why this score” to see what drove it."
        actions={
          <Button
            variant="default"
            leftSection={<LuRefreshCw size={14} />}
            onClick={() =>
              notifications.show({
                title: "Feeds refreshed (sample)",
                message: "No new articles since the last check.",
              })
            }
          >
            Refresh feeds
          </Button>
        }
      />

      <Stack gap={16}>
        <KpiGrid>
          <KpiTile
            label="Articles (24h)"
            value={<span className="kv2-num">{day.length}</span>}
            hint={`${scored.length} scored`}
          />
          <KpiTile
            label="Average sentiment"
            value={<span className="kv2-num">{formatSigned(avg)}</span>}
            aside={<SentimentPill score={avg} size="xs" />}
            info="Mean sentiment of scored articles in the last 24 hours. Between −0.15 and +0.15 counts as neutral."
          />
          <KpiTile
            label="Positive / negative"
            value={
              <span className="kv2-num">
                <span className="kv2-gain">▲ {mix.positive}</span> /{" "}
                <span className="kv2-loss">▼ {mix.negative}</span>
              </span>
            }
            hint={`${mix.neutral} neutral`}
            info="Count of articles in each sentiment bucket over the last 24 hours."
          />
          <KpiTile
            label="Not scored yet"
            value={<span className="kv2-num">{unscored}</span>}
            aside={
              unscored ? (
                <StatusBadge tone="caution" size="xs">
                  Queued
                </StatusBadge>
              ) : undefined
            }
            hint="Scoring runs every 5 minutes"
            info="Articles already ingested but still waiting for the scoring job."
          />
        </KpiGrid>

        <Grid gutter={16}>
          <Grid.Col span={{ base: 12, lg: 8 }}>
            <Panel flush>
              <div className="kv2-toolbar">
                <Stack gap={8} style={{ flex: 1, minWidth: 0 }}>
                  <Group gap={8} wrap="wrap">
                    <SegmentedControl
                      size="xs"
                      aria-label="Coverage"
                      value={coverage}
                      onChange={setCoverage}
                      data={[
                        { value: "all", label: `All (${counts.all})` },
                        { value: "local", label: `Local (${counts.local})` },
                        {
                          value: "international",
                          label: `International (${counts.international})`,
                        },
                      ]}
                    />
                    <TextInput
                      aria-label="Search news"
                      placeholder="Search headlines"
                      leftSection={<LuSearch size={14} />}
                      value={search}
                      onChange={(e) => setSearch(e.currentTarget.value)}
                      style={{ flex: 1, minWidth: 180 }}
                    />
                  </Group>
                  <Group gap={8} wrap="wrap">
                    <Chip.Group multiple value={buckets} onChange={setBuckets}>
                      <Group gap={4}>
                        <Chip size="xs" value="positive" color="emerald">
                          ▲ Positive
                        </Chip>
                        <Chip size="xs" value="neutral" color="slate">
                          – Neutral
                        </Chip>
                        <Chip size="xs" value="negative" color="red">
                          ▼ Negative
                        </Chip>
                      </Group>
                    </Chip.Group>
                    <Select
                      aria-label="Source"
                      placeholder="Any source"
                      clearable
                      w={170}
                      value={source}
                      onChange={setSource}
                      data={newsSources}
                    />
                    <Select
                      aria-label="Company"
                      placeholder="Any company"
                      clearable
                      searchable
                      w={190}
                      value={company}
                      onChange={setCompany}
                      data={companyOptions}
                    />
                    <Select
                      aria-label="Published within"
                      w={120}
                      allowDeselect={false}
                      value={window_}
                      onChange={setWindow}
                      data={[
                        { value: "1h", label: "Last hour" },
                        { value: "6h", label: "Last 6h" },
                        { value: "24h", label: "Last 24h" },
                        { value: "all", label: "Any time" },
                      ]}
                    />
                    {filtersActive ? (
                      <Button
                        variant="subtle"
                        size="xs"
                        leftSection={<LuX size={12} />}
                        onClick={clear}
                      >
                        Clear
                      </Button>
                    ) : null}
                    <Text size="xs" c="dimmed" ml="auto" className="kv2-num">
                      {filtered.length} articles
                    </Text>
                  </Group>
                </Stack>
              </div>
              {filtered.length === 0 ? (
                <EmptyState
                  title="No articles match these filters"
                  description={
                    sampleUser.staff ? (
                      <>
                        Widen the time window or clear filters. If feeds look stuck, check{" "}
                        <Anchor component={AppLink} href="/v2/delivery/" inherit>
                          delivery and jobs
                        </Anchor>
                        .
                      </>
                    ) : (
                      "Widen the time window or clear the filters."
                    )
                  }
                  action={
                    <Button size="xs" variant="default" onClick={clear}>
                      Clear filters
                    </Button>
                  }
                />
              ) : (
                <div style={{ marginTop: -1 }}>
                  {visible.map((a) => (
                    <ArticleRow
                      key={a.id}
                      article={a}
                      expanded={expanded === a.id}
                      onToggle={() => setExpanded((e) => (e === a.id ? null : a.id))}
                    />
                  ))}
                  <Group
                    justify="space-between"
                    px={12}
                    py={10}
                    style={{ borderTop: "1px solid var(--kv2-border)" }}
                  >
                    <Text size="xs" c="dimmed" className="kv2-num">
                      Showing {visible.length} of {filtered.length}
                    </Text>
                    {visible.length < filtered.length ? (
                      <Button size="xs" variant="default" onClick={() => setLimit((l) => l + 15)}>
                        Load more
                      </Button>
                    ) : null}
                  </Group>
                </div>
              )}
            </Panel>
          </Grid.Col>

          <Grid.Col span={{ base: 12, lg: 4 }}>
            <Stack gap={16}>
              <Panel
                title="Sentiment by hour"
                info="Scored articles per hour, split by sentiment bucket. Last 8 hours, IST."
              >
                <BarChart
                  h={180}
                  data={sentimentByHour}
                  dataKey="hour"
                  type="stacked"
                  withLegend
                  legendProps={{ verticalAlign: "bottom", height: 24 }}
                  gridAxis="y"
                  tickLine="none"
                  series={[
                    { name: "Positive", color: "emerald.6" },
                    { name: "Neutral", color: "slate.4" },
                    { name: "Negative", color: "red.6" },
                  ]}
                />
              </Panel>
              <Panel title="Mix (24h)" info="Share of scored articles in each sentiment bucket.">
                <Group gap={16} wrap="nowrap">
                  <DonutChart
                    size={110}
                    thickness={16}
                    withTooltip
                    data={[
                      { name: "Positive", value: mix.positive, color: "emerald.6" },
                      { name: "Neutral", value: mix.neutral, color: "slate.4" },
                      { name: "Negative", value: mix.negative, color: "red.6" },
                    ]}
                  />
                  <Stack gap={4}>
                    {(
                      [
                        ["▲ Positive", mix.positive, "kv2-gain"],
                        ["– Neutral", mix.neutral, "kv2-flat"],
                        ["▼ Negative", mix.negative, "kv2-loss"],
                      ] as const
                    ).map(([label, n, cls]) => (
                      <Text key={label} size="xs" className="kv2-num">
                        <span className={cls}>{label}</span> · {n} (
                        {Math.round((n / Math.max(1, scored.length)) * 100)}%)
                      </Text>
                    ))}
                  </Stack>
                </Group>
              </Panel>
              <Panel
                title="Most mentioned"
                info="Companies linked to the most scored articles, with their average sentiment. Click a name to filter the feed."
              >
                <Stack gap={6}>
                  {mentions.map(([id, m]) => {
                    const c = companyById.get(id);
                    if (!c) return null;
                    return (
                      <Group key={id} justify="space-between" gap={8} wrap="nowrap">
                        <UnstyledButton onClick={() => setCompany(id)} style={{ minWidth: 0 }}>
                          <Text size="sm" fw={500} truncate>
                            {c.name}
                          </Text>
                          <Text size="xs" c="dimmed">
                            {m.n} articles
                          </Text>
                        </UnstyledButton>
                        <SentimentPill score={m.sum / m.n} size="xs" />
                      </Group>
                    );
                  })}
                </Stack>
              </Panel>
            </Stack>
          </Grid.Col>
        </Grid>
      </Stack>
    </Page>
  );
}
