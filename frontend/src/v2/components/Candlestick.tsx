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
import {
  LuArrowLeft,
  LuArrowRight,
  LuMaximize2,
  LuRotateCcw,
  LuZoomIn,
  LuZoomOut,
} from "react-icons/lu";

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
  projection = false,
}: {
  candles: Candle[];
  height?: number;
  overlays?: OverlayKey[];
  showVolume?: boolean;
  projection?: boolean;
}) {
  const [hover, setHover] = useState<number | null>(null);
  const width = 800;
  const padR = 56;
  const padB = 18;
  const volH = showVolume ? height * 0.18 : 0;
  const priceH = height - padB - volH - 8;

  const { min, max, maxVol, lines, projected } = useMemo(() => {
    const closes = candles.map((c) => c.close);
    const history = closes.slice(-20);
    const meanX = (history.length - 1) / 2;
    const meanY = history.reduce((sum, value) => sum + value, 0) / history.length;
    const denominator = history.reduce((sum, _, i) => sum + (i - meanX) ** 2, 0);
    const slope =
      denominator === 0
        ? 0
        : history.reduce((sum, value, i) => sum + (i - meanX) * (value - meanY), 0) / denominator;
    const projectionValues = projection
      ? Array.from({ length: 20 }, (_, i) => meanY + slope * (history.length + i - meanX))
      : [];
    const values = [...candles.flatMap((c) => [c.low, c.high]), ...projectionValues];
    return {
      min: Math.min(...values),
      max: Math.max(...values),
      maxVol: Math.max(1, ...candles.map((c) => c.volume)),
      lines: overlayDefs
        .filter((o) => overlays.includes(o.key))
        .map((o) => ({ ...o, values: sma(closes, o.period) })),
      projected: projectionValues,
    };
  }, [candles, overlays, projection]);

  const plotCount = candles.length + projected.length;
  const step = (width - padR) / plotCount;
  const y = (v: number) => 4 + ((max - v) / (max - min || 1)) * (priceH - 8);
  const ticks = [0, 0.25, 0.5, 0.75, 1].map((t) => min + (max - min) * t);
  const activeIndex = hover ?? candles.length - 1;
  const active = candles[activeIndex];

  if (!active)
    return (
      <Text size="sm" c="dimmed">
        No price history available.
      </Text>
    );

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
        {lines.map((line) => {
          const value = line.values[activeIndex];
          return value == null ? null : (
            <Text key={line.key} size="xs">
              <Text span c="dimmed" size="xs">
                {line.label}{" "}
              </Text>
              {formatNumber(value, 2)}
            </Text>
          );
        })}
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
        {projected.length > 0 ? (
          <polyline
            className="overlay"
            style={{
              stroke: "var(--mantine-color-violet-5)",
              strokeDasharray: "5 4",
            }}
            points={[
              `${(candles.length - 1) * step + step / 2},${y(candles.at(-1)!.close)}`,
              ...projected.map(
                (value, i) => `${(candles.length + i) * step + step / 2},${y(value)}`,
              ),
            ].join(" ")}
          />
        ) : null}
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

const ranges = ["1M", "3M", "6M", "1Y", "All"] as const;
const rangeDays: Record<(typeof ranges)[number], number> = {
  "1M": 22,
  "3M": 66,
  "6M": 130,
  "1Y": 250,
  All: Number.MAX_SAFE_INTEGER,
};

function ChartControls({
  range,
  setRange,
  overlays,
  setOverlays,
  showVolume,
  setShowVolume,
  projection,
  setProjection,
  zoomIn,
  zoomOut,
  earlier,
  later,
  reset,
}: {
  range: (typeof ranges)[number];
  setRange: (r: (typeof ranges)[number]) => void;
  overlays: OverlayKey[];
  setOverlays: (o: OverlayKey[]) => void;
  showVolume: boolean;
  setShowVolume: (value: boolean) => void;
  projection: boolean;
  setProjection: (value: boolean) => void;
  zoomIn: () => void;
  zoomOut: () => void;
  earlier: () => void;
  later: () => void;
  reset: () => void;
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
      <Chip size="xs" variant="outline" checked={showVolume} onChange={setShowVolume}>
        Volume
      </Chip>
      <Chip size="xs" variant="outline" checked={projection} onChange={setProjection}>
        Projection
      </Chip>
      <Group gap={2} ml="auto">
        <Tooltip label="Earlier">
          <ActionIcon aria-label="Show earlier price history" variant="default" onClick={earlier}>
            <LuArrowLeft size={14} />
          </ActionIcon>
        </Tooltip>
        <Tooltip label="Later">
          <ActionIcon aria-label="Show later price history" variant="default" onClick={later}>
            <LuArrowRight size={14} />
          </ActionIcon>
        </Tooltip>
        <Tooltip label="Zoom in">
          <ActionIcon aria-label="Zoom in on price history" variant="default" onClick={zoomIn}>
            <LuZoomIn size={14} />
          </ActionIcon>
        </Tooltip>
        <Tooltip label="Zoom out">
          <ActionIcon aria-label="Zoom out on price history" variant="default" onClick={zoomOut}>
            <LuZoomOut size={14} />
          </ActionIcon>
        </Tooltip>
        <Tooltip label="Reset chart">
          <ActionIcon aria-label="Reset price chart" variant="default" onClick={reset}>
            <LuRotateCcw size={14} />
          </ActionIcon>
        </Tooltip>
      </Group>
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
  const [zoom, setZoom] = useState(1);
  const [offset, setOffset] = useState(0);
  const [showVolume, setShowVolume] = useState(true);
  const [projection, setProjection] = useState(false);
  const visibleCount = Math.min(candles.length, Math.max(15, Math.round(rangeDays[range] / zoom)));
  const maxOffset = Math.max(0, candles.length - visibleCount);
  const end = candles.length - Math.min(offset, maxOffset);
  const slice = candles.slice(Math.max(0, end - visibleCount), end);
  const setChartRange = (value: (typeof ranges)[number]) => {
    setRange(value);
    setOffset(0);
    setZoom(1);
  };
  const moveBy = Math.max(1, Math.floor(visibleCount / 2));
  const reset = () => {
    setRange("3M");
    setOffset(0);
    setZoom(1);
    setOverlays(["sma20"]);
    setShowVolume(true);
    setProjection(false);
  };
  const controls = (
    <ChartControls
      range={range}
      setRange={setChartRange}
      overlays={overlays}
      setOverlays={setOverlays}
      showVolume={showVolume}
      setShowVolume={setShowVolume}
      projection={projection}
      setProjection={setProjection}
      zoomIn={() => setZoom((value) => Math.min(20, value * 1.25))}
      zoomOut={() => setZoom((value) => Math.max(0.2, value / 1.25))}
      earlier={() => setOffset((value) => Math.min(maxOffset, value + moveBy))}
      later={() => setOffset((value) => Math.max(0, value - moveBy))}
      reset={reset}
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
        <CandlestickChart
          candles={slice}
          overlays={overlays}
          showVolume={showVolume}
          projection={projection}
        />
        {projection ? (
          <Text size="xs" c="dimmed">
            Dashed line extends the latest 20 closes for visual context only; it is not a forecast.
          </Text>
        ) : null}
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
          <CandlestickChart
            candles={slice}
            overlays={overlays}
            showVolume={showVolume}
            projection={projection}
            height={520}
          />
          <Text size="xs" c="dimmed">
            Indicators are computed on daily closes. Sample data shown.
          </Text>
        </Stack>
      </Modal>
    </Panel>
  );
}
