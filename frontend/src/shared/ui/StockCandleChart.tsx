import { Button, Checkbox, Group, Modal, Stack, Text } from "@mantine/core";
import { useElementSize, useViewportSize } from "@mantine/hooks";
import { useId, useRef, useState } from "react";
import type { PointerEvent } from "react";

type Candle = {
  label: string;
  open: number;
  high: number;
  low: number;
  close: number;
  volume: number;
};
type Projection = { label: string; value: number };
const number = new Intl.NumberFormat("en-IN", { maximumFractionDigits: 2 });

export function movingAverage(candles: Candle[], index: number, period: number) {
  if (index + 1 < period) return null;
  return (
    candles.slice(index + 1 - period, index + 1).reduce((sum, bar) => sum + bar.close, 0) / period
  );
}

export function StockCandleChart({
  candles,
  projectionPoints = [],
  ariaLabel,
  height: requestedHeight = 440,
}: {
  candles: Candle[];
  projectionPoints?: Projection[];
  ariaLabel: string;
  height?: number;
}) {
  const [windowSize, setWindowSize] = useState(60);
  const [offset, setOffset] = useState(0);
  const [active, setActive] = useState<number | null>(null);
  const [volume, setVolume] = useState(true);
  const [sma20, setSma20] = useState(true);
  const [sma50, setSma50] = useState(false);
  const [projection, setProjection] = useState(true);
  const [expanded, setExpanded] = useState(false);
  const { height: viewportHeight } = useViewportSize();
  const height = expanded ? Math.max(440, viewportHeight - 240) : requestedHeight;
  const drag = useRef<{ x: number; offset: number } | null>(null);
  const { ref, width: measuredWidth } = useElementSize();
  const id = useId();
  const width = Math.max(320, measuredWidth || 900);
  const size = Math.min(candles.length, windowSize);
  const safeOffset = Math.min(offset, Math.max(0, candles.length - size));
  const end = candles.length - safeOffset;
  const start = Math.max(0, end - size);
  const visible = candles.slice(start, end);
  const future =
    projection && visible.length > 0 && end === candles.length ? projectionPoints.slice(1) : [];
  const count = visible.length + future.length;
  const tickCount = Math.min(count, width < 500 ? 2 : 4);
  const left = 12;
  const right = width - 78;
  const top = 18;
  const bottom = height - (volume ? 112 : 38);
  const step = (right - left) / Math.max(1, count);
  const x = (index: number) => left + (index + 0.5) * step;
  const averages = visible.map((_, index) => ({
    short: sma20 ? movingAverage(candles, start + index, 20) : null,
    long: sma50 ? movingAverage(candles, start + index, 50) : null,
  }));
  const prices = [
    ...visible.flatMap((bar) => [bar.low, bar.high]),
    ...future.map((point) => point.value),
    ...averages.flatMap((point) => [point.short, point.long].filter((value) => value !== null)),
  ];
  const min = prices.length ? Math.min(...prices) : 0;
  const max = prices.length ? Math.max(...prices) : 1;
  const padding = Math.max((max - min) * 0.08, Math.abs(max) * 0.005, 0.01);
  const y = (price: number) =>
    bottom - ((price - min + padding) / (max - min + 2 * padding)) * (bottom - top);
  const maxVolume = Math.max(1, ...visible.map((bar) => bar.volume));
  const selected = active === null ? visible.length - 1 : Math.min(active, count - 1);
  const bar = visible[selected];
  const forecast = future[selected - visible.length];
  const pan = (amount: number) => {
    setOffset(Math.max(0, Math.min(candles.length - size, safeOffset + amount)));
    setActive(null);
  };
  const zoom = (factor: number) => {
    setWindowSize(
      Math.min(candles.length, Math.max(Math.min(10, candles.length), Math.round(size * factor))),
    );
    setActive(null);
  };
  const path = (values: { index: number; value: number | null }[]) => {
    let started = false;
    return values
      .map(({ index, value }) => {
        if (value === null) {
          started = false;
          return "";
        }
        const command = started ? "L" : "M";
        started = true;
        return `${command}${x(index)},${y(value)}`;
      })
      .join(" ");
  };
  const pointerPosition = (event: PointerEvent<SVGRectElement>) => {
    const bounds = event.currentTarget.ownerSVGElement!.getBoundingClientRect();
    return ((event.clientX - bounds.left) * width) / (bounds.width || width);
  };
  const chart = (
    <Stack gap="sm" className="stock-chart">
      <Group gap="xs" wrap="wrap" aria-label="Chart controls">
        {(
          [
            ["1M", 20],
            ["3M", 60],
            ["6M", 120],
            ["All", candles.length],
          ] as const
        ).map(([label, sessions]) => (
          <Button
            key={label}
            size="xs"
            variant={windowSize === sessions ? "filled" : "default"}
            aria-pressed={windowSize === sessions}
            onClick={() => {
              setWindowSize(sessions);
              setOffset(0);
              setActive(null);
            }}
          >
            {label}
          </Button>
        ))}
        <Button
          size="xs"
          variant="default"
          aria-label="Zoom in"
          disabled={size <= Math.min(10, candles.length)}
          onClick={() => zoom(0.7)}
        >
          +
        </Button>
        <Button
          size="xs"
          variant="default"
          aria-label="Zoom out"
          disabled={size >= candles.length}
          onClick={() => zoom(1.4)}
        >
          -
        </Button>
        <Button
          size="xs"
          variant="default"
          disabled={start === 0}
          onClick={() => pan(Math.max(1, Math.round(size / 4)))}
        >
          Earlier
        </Button>
        <Button
          size="xs"
          variant="default"
          disabled={safeOffset === 0}
          onClick={() => pan(-Math.max(1, Math.round(size / 4)))}
        >
          Later
        </Button>
        <Button
          size="xs"
          variant="default"
          onClick={() => {
            setWindowSize(60);
            setOffset(0);
            setActive(null);
          }}
        >
          Reset view
        </Button>
        <Button size="xs" variant="default" onClick={() => setExpanded(!expanded)}>
          {expanded ? "Exit fullscreen" : "Fullscreen"}
        </Button>
      </Group>
      <Group gap="md">
        <Checkbox
          label="Volume"
          checked={volume}
          onChange={(event) => setVolume(event.currentTarget.checked)}
        />
        <Checkbox
          label="SMA 20"
          checked={sma20}
          onChange={(event) => setSma20(event.currentTarget.checked)}
        />
        <Checkbox
          label="SMA 50"
          checked={sma50}
          onChange={(event) => setSma50(event.currentTarget.checked)}
        />
        <Checkbox
          label="Projection"
          disabled={!projectionPoints.length}
          checked={projection}
          onChange={(event) => setProjection(event.currentTarget.checked)}
        />
      </Group>
      <div
        className="stock-chart-readout"
        aria-label="Selected chart values"
        aria-live="polite"
        aria-atomic="true"
      >
        {bar ? (
          <Text size="sm">
            <strong>{bar.label}</strong>
            {" | "}O {number.format(bar.open)} · H {number.format(bar.high)} · L{" "}
            {number.format(bar.low)} · C {number.format(bar.close)} INR
            {" | "}Volume {number.format(bar.volume)}
            {sma20 &&
              ` | SMA 20: ${averages[selected]?.short === null ? "Not enough history" : number.format(averages[selected].short!)}`}
            {sma50 &&
              ` | SMA 50: ${averages[selected]?.long === null ? "Not enough history" : number.format(averages[selected].long!)}`}
          </Text>
        ) : forecast ? (
          <Text size="sm">
            {forecast.label} | Illustrative projection: INR {number.format(forecast.value)}; not an
            observed price
          </Text>
        ) : (
          <Text size="sm">No saved candles.</Text>
        )}
      </div>
      <div ref={ref}>
        <svg
          width="100%"
          height={height}
          viewBox={`0 0 ${width} ${height}`}
          role="img"
          aria-label={`${ariaLabel}; visible history ${visible[0]?.label ?? "unavailable"} to ${visible.at(-1)?.label ?? "unavailable"}${future.length ? ", followed by a 20-session history-only linear projection" : ""}`}
          aria-describedby={`${id}-help`}
          tabIndex={0}
          className="stock-chart-svg"
          onBlur={() => setActive(null)}
          onKeyDown={(event) => {
            if (event.key === "ArrowLeft" || event.key === "ArrowRight") {
              event.preventDefault();
              const delta = event.key === "ArrowLeft" ? -1 : 1;
              if (event.shiftKey) pan(-delta * Math.max(1, Math.round(size / 4)));
              else setActive(Math.max(0, Math.min(count - 1, selected + delta)));
            } else if (event.key === "+" || event.key === "=" || event.key === "-") {
              event.preventDefault();
              zoom(event.key === "-" ? 1.4 : 0.7);
            } else if (event.key === "Escape") setActive(null);
          }}
        >
          <defs>
            <clipPath id={`${id}-plot`}>
              <rect x={left} y={top} width={right - left} height={height - top - 24} />
            </clipPath>
          </defs>
          {Array.from({ length: 5 }, (_, index) => {
            const price = min - padding + ((max - min + 2 * padding) * index) / 4;
            return (
              <g key={index}>
                <line
                  x1={left}
                  x2={right}
                  y1={y(price)}
                  y2={y(price)}
                  className="stock-chart-grid"
                />
                <text x={right + 8} y={y(price) + 4}>
                  {number.format(price)}
                </text>
              </g>
            );
          })}
          <text x={right + 8} y={12}>
            INR
          </text>
          <g clipPath={`url(#${id}-plot)`}>
            {visible.map((bar, index) => {
              const color = bar.close >= bar.open ? "var(--brand-gain)" : "var(--brand-loss)";
              const bodyWidth = Math.min(16, step * 0.7);
              return (
                <g key={bar.label} data-candle={bar.label}>
                  <line
                    x1={x(index)}
                    x2={x(index)}
                    y1={y(bar.high)}
                    y2={y(bar.low)}
                    stroke={color}
                    strokeWidth={1.5}
                  />
                  <rect
                    x={x(index) - bodyWidth / 2}
                    y={Math.min(y(bar.open), y(bar.close))}
                    width={bodyWidth}
                    height={Math.max(1.5, Math.abs(y(bar.open) - y(bar.close)))}
                    fill={color}
                  />
                  {volume && (
                    <rect
                      x={x(index) - bodyWidth / 2}
                      y={height - 32 - (bar.volume / maxVolume) * 55}
                      width={bodyWidth}
                      height={(bar.volume / maxVolume) * 55}
                      fill={color}
                      opacity={0.5}
                      data-volume={bar.volume}
                    />
                  )}
                </g>
              );
            })}
            {sma20 && (
              <path
                d={path(averages.map((point, index) => ({ index, value: point.short })))}
                fill="none"
                stroke="var(--brand-purple)"
                strokeWidth={2}
                aria-label="20-session moving average"
              />
            )}
            {sma50 && (
              <path
                d={path(averages.map((point, index) => ({ index, value: point.long })))}
                fill="none"
                stroke="var(--brand-muted)"
                strokeWidth={2}
                strokeDasharray="3 2"
                aria-label="50-session moving average"
              />
            )}
            {future.length > 0 && (
              <path
                d={path([
                  { index: visible.length - 1, value: visible.at(-1)!.close },
                  ...future.map((point, index) => ({
                    index: visible.length + index,
                    value: point.value,
                  })),
                ])}
                fill="none"
                stroke="var(--brand-purple)"
                strokeWidth={2}
                strokeDasharray="6 5"
                aria-label="History-only projection"
              />
            )}
          </g>
          {volume && (
            <text x={left} y={height - 94}>
              Volume · max {number.format(maxVolume)}
            </text>
          )}
          {Array.from({ length: tickCount }, (_, index) =>
            Math.round((index * (count - 1)) / Math.max(1, tickCount - 1)),
          ).map((index) => (
            <text
              key={index}
              x={x(index)}
              y={height - 8}
              textAnchor={index === 0 ? "start" : index === count - 1 ? "end" : "middle"}
            >
              {visible[index]?.label ?? future[index - visible.length]?.label}
            </text>
          ))}
          <rect
            x={left}
            y={top}
            width={right - left}
            height={height - top - 24}
            fill="transparent"
            className="stock-chart-hit-area"
            onPointerDown={(event) => {
              const position = pointerPosition(event);
              setActive(Math.max(0, Math.min(count - 1, Math.floor((position - left) / step))));
              drag.current = { x: position, offset: safeOffset };
              event.currentTarget.setPointerCapture?.(event.pointerId);
            }}
            onPointerMove={(event) => {
              const position = pointerPosition(event);
              if (drag.current && Math.abs(position - drag.current.x) >= step) {
                const delta = Math.round((position - drag.current.x) / step);
                setOffset(
                  Math.max(0, Math.min(candles.length - size, drag.current.offset + delta)),
                );
                setActive(null);
              } else if (!drag.current)
                setActive(Math.max(0, Math.min(count - 1, Math.floor((position - left) / step))));
            }}
            onPointerUp={() => {
              drag.current = null;
            }}
            onPointerCancel={() => {
              drag.current = null;
            }}
            onLostPointerCapture={() => {
              drag.current = null;
            }}
            onPointerLeave={() => {
              if (!drag.current) setActive(null);
            }}
          />
          {active !== null && (bar || forecast) && (
            <g pointerEvents="none" className="stock-chart-crosshair">
              <line x1={x(selected)} x2={x(selected)} y1={top} y2={height - 24} />
              <line
                x1={left}
                x2={right}
                y1={y(bar?.close ?? forecast.value)}
                y2={y(bar?.close ?? forecast.value)}
              />
              <circle cx={x(selected)} cy={y(bar?.close ?? forecast.value)} r={3} />
            </g>
          )}
        </svg>
      </div>
      <Text id={`${id}-help`} size="xs" c="dimmed">
        {visible[0]?.label} to {visible.at(-1)?.label} · {visible.length} daily sessions. Hover or
        touch for OHLCV. Drag horizontally or use Earlier/Later to pan. Focus chart: arrows inspect,
        Shift+arrows pan, +/- zoom. Ranges use 20 sessions per month. SMA 20 is purple; SMA 50 is
        dashed gray. Saved daily data, not an intraday feed.
      </Text>
    </Stack>
  );
  return expanded ? (
    <Modal
      opened
      onClose={() => setExpanded(false)}
      fullScreen
      title="Daily price chart"
      transitionProps={{ duration: 0 }}
    >
      {chart}
    </Modal>
  ) : (
    chart
  );
}
