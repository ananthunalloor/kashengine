import { Sparkline as MantineSparkline } from "@mantine/charts";

import { directionOf } from "./format";

/** Tiny trend line; colour follows the first→last direction. */
export function Sparkline({
  data,
  w = 96,
  h = 28,
}: {
  data: number[];
  w?: number | string;
  h?: number;
}) {
  const dir = directionOf(data.length > 1 ? data[data.length - 1] - data[0] : 0);
  const color = dir === "up" ? "emerald.6" : dir === "down" ? "red.6" : "slate.4";
  return (
    <MantineSparkline
      w={w}
      h={h}
      data={data}
      color={color}
      curveType="linear"
      fillOpacity={0.12}
      strokeWidth={1.5}
      aria-hidden
    />
  );
}
