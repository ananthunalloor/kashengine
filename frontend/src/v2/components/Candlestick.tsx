import {
  ActionIcon,
  Chip,
  Group,
  Modal,
  SegmentedControl,
  Stack,
  Text,
  Tooltip,
} from "@mantine/core";
import { useMemo, useState } from "react";
import { LuMaximize2 } from "react-icons/lu";

import { formatDate, formatInr, formatNumber } from "./format";
import { Panel } from "./Layout";
import { sma } from "../mock/generate";
import type { Candle } from "../mock/generate";

const overlayDefs = [
  { key: "sma20", label: "SMA 20", period: 20, color: "var(--mantine-color-indigo-5)" },
  { key: "sma50", label: "SMA 50", period: 50, color: "var(--mantine-color-amber-5)" },
] as const;

type OverlayKey = (typeof overlayDefs)[number]["key"];

/** Pure SVG OHLC chart (CSP-safe, no canvas). Width is fluid via viewBox. */
export function CandlestickChart({
  candles,
  height = 280,
  overlays = [],
  showVolume = true,
}: {
  candles: Candle[];
  height?: number;
  overlays?: OverlayKey[];
  showVolume?: boolean;
}) {
  const [hover, setHover] = useState<number | null>(null);
  const width = 800;
  const padR = 56;
  const padB = 18;
  const volH = showVolume ? height * 0.18 : 0;
  const priceH = height - padB - volH - 8;
  const step = (width - padR) / candles.length;

  const { min, max, maxVol, lines } = useMemo(() => {
    const closes = candles.map((c) => c.close);
    return {
      min: Math.min(...candles.map((c) => c.low)),
      max: Math.max(...candles.map((c) => c.high)),
      maxVol: Math.max(...candles.map((c) => c.volume)),
      lines: overlayDefs
        .filter((o) => overlays.includes(o.key))
        .map((o) => ({ ...o, values: sma(closes, o.period) })),
    };
  }, [candles, overlays]);

  const y = (v: number) => 4 + ((max - v) / (max - min || 1)) * (priceH - 8);
  const ticks = [0, 0.25, 0.5, 0.75, 1].map((t) => min + (max - min) * t);
  const active = hover != null ? candles[hover] : candles[candles.length - 1];

  return (
    <Stack gap={4}>
      <Group gap={12} className="kv2-num" wrap="wrap">
        <Text size="xs" c="dimmed">
          {formatDate(active.date)}
        </Text>
        {(["open", "high", "low", "close"] as const).map((k) => (
          <Text key={k} size="xs">
            <Text span c="dimmed" size="xs" tt="uppercase">
              {k[0]}{" "}
            </Text>
            {formatNumber(active[k], 2)}
          </Text>
        ))}
        <Text size="xs">
          <Text span c="dimmed" size="xs">
            VOL{" "}
          </Text>
          {formatNumber(active.volume)}
        </Text>
      </Group>
      <svg
        className="kv2-candles"
        viewBox={`0 0 ${width} ${height}`}
        preserveAspectRatio="none"
        style={{ height }}
        role="img"
        aria-label="Price chart"
        onMouseLeave={() => setHover(null)}
      >
        {ticks.map((t) => (
          <g key={t}>
            <line className="grid" x1={0} x2={width - padR} y1={y(t)} y2={y(t)} />
            <text className="axis" x={width - padR + 6} y={y(t) + 3}>
              {formatNumber(t, 0)}
            </text>
          </g>
        ))}
        {candles.map((c, i) => {
          const x = i * step + step / 2;
          const up = c.close >= c.open;
          const bodyTop = y(Math.max(c.open, c.close));
          const bodyH = Math.max(1, Math.abs(y(c.open) - y(c.close)));
          const vh = (c.volume / maxVol) * volH;
          return (
            <g key={c.date} className={up ? "up" : "down"} onMouseEnter={() => setHover(i)}>
              <rect
                x={i * step}
                y={0}
                width={step}
                height={height}
                fill="transparent"
                stroke="none"
              />
              <line x1={x} x2={x} y1={y(c.high)} y2={y(c.low)} strokeWidth={1} />
              <rect x={x - step * 0.35} y={bodyTop} width={step * 0.7} height={bodyH} />
              {showVolume ? (
                <rect
                  x={x - step * 0.35}
                  y={height - padB - vh}
                  width={step * 0.7}
                  height={vh}
                  opacity={0.35}
                  stroke="none"
                />
              ) : null}
            </g>
          );
        })}
        {lines.map((line) => (
          <polyline
            key={line.key}
            className="overlay"
            style={{ stroke: line.color }}
            points={line.values
              .map((v, i) => (v == null ? null : `${i * step + step / 2},${y(v)}`))
              .filter(Boolean)
              .join(" ")}
          />
        ))}
        {hover != null ? (
          <line
            className="grid"
            x1={hover * step + step / 2}
            x2={hover * step + step / 2}
            y1={0}
            y2={height - padB}
            strokeDasharray="3 3"
          />
        ) : null}
        {[0, Math.floor(candles.length / 2), candles.length - 1].map((i) => (
          <text key={i} className="axis" x={i * step} y={height - 4}>
            {formatDate(candles[i].date).slice(0, 6)}
          </text>
        ))}
      </svg>
    </Stack>
  );
}

const ranges = ["1M", "3M", "6M", "1Y"] as const;
const rangeDays: Record<(typeof ranges)[number], number> = {
  "1M": 22,
  "3M": 66,
  "6M": 130,
  "1Y": 250,
};

function ChartControls({
  range,
  setRange,
  overlays,
  setOverlays,
}: {
  range: (typeof ranges)[number];
  setRange: (r: (typeof ranges)[number]) => void;
  overlays: OverlayKey[];
  setOverlays: (o: OverlayKey[]) => void;
}) {
  return (
    <Group gap={8} wrap="wrap">
      <SegmentedControl
        data={[...ranges]}
        value={range}
        onChange={(v) => setRange(v as (typeof ranges)[number])}
        aria-label="Range"
      />
      <Chip.Group multiple value={overlays} onChange={(v) => setOverlays(v as OverlayKey[])}>
        <Group gap={4}>
          {overlayDefs.map((o) => (
            <Chip key={o.key} value={o.key} size="xs" variant="outline">
              {o.label}
            </Chip>
          ))}
        </Group>
      </Chip.Group>
    </Group>
  );
}

/** Chart panel with range/indicator controls and a fullscreen modal. */
export function PriceChartPanel({
  title,
  candles,
  last,
}: {
  title: string;
  candles: Candle[];
  last?: number;
}) {
  const [range, setRange] = useState<(typeof ranges)[number]>("3M");
  const [overlays, setOverlays] = useState<OverlayKey[]>(["sma20"]);
  const [full, setFull] = useState(false);
  const slice = candles.slice(-rangeDays[range]);
  const controls = (
    <ChartControls
      range={range}
      setRange={setRange}
      overlays={overlays}
      setOverlays={setOverlays}
    />
  );

  return (
    <Panel
      title={title}
      actions={
        <>
          {last != null ? (
            <Text size="sm" fw={600} className="kv2-num" visibleFrom="sm">
              {formatInr(last)}
            </Text>
          ) : null}
          <Tooltip label="Fullscreen">
            <ActionIcon aria-label="Open fullscreen chart" onClick={() => setFull(true)}>
              <LuMaximize2 />
            </ActionIcon>
          </Tooltip>
        </>
      }
    >
      <Stack gap={8}>
        {controls}
        <CandlestickChart candles={slice} overlays={overlays} />
      </Stack>
      <Modal
        opened={full}
        onClose={() => setFull(false)}
        fullScreen
        title={`${title} · Technical view`}
        centered={false}
      >
        <Stack gap={12}>
          {controls}
          <CandlestickChart candles={slice} overlays={overlays} height={520} />
          <Text size="xs" c="dimmed">
            Indicators are computed on daily closes. Sample data shown.
          </Text>
        </Stack>
      </Modal>
    </Panel>
  );
}
