import { defineChart } from "@tanstack/charts";
import { barY } from "@tanstack/charts/bar";
import { group } from "@tanstack/charts/group";
import { lineY } from "@tanstack/charts/line";
import { Chart } from "@tanstack/charts/react";
import { scaleBand } from "@tanstack/charts/scales/band";
import { scaleLinear } from "@tanstack/charts/scales/linear";
import { scalePoint } from "@tanstack/charts/scales/point";
import { useMemo } from "react";

type OpsChartPoint = { label: string; value: number; failed: number };
type OpsSeriesPoint = {
    label: string;
    series: "Total" | "Failed / alerts";
    value: number;
};
type TrendPoint = { label: string; value: number };

const illustrativePoints: TrendPoint[] = [
    { label: "1", value: 2 },
    { label: "2", value: 6 },
    { label: "3", value: 3 },
    { label: "4", value: 9 },
    { label: "5", value: 7 },
    { label: "6", value: 12 },
    { label: "7", value: 10 },
    { label: "8", value: 15 },
    { label: "9", value: 13 },
    { label: "10", value: 19 },
    { label: "11", value: 16 },
    { label: "12", value: 22 },
    { label: "13", value: 18 },
    { label: "14", value: 24 },
    { label: "15", value: 20 },
    { label: "16", value: 27 },
    { label: "17", value: 23 },
    { label: "18", value: 30 },
];

export function TrendChart({
    points,
    ariaLabel,
    height = 190,
    initialWidth = 760,
}: {
    points: TrendPoint[];
    ariaLabel: string;
    height?: number;
    initialWidth?: number;
}) {
    const rows = useMemo(
        () => points.map(({ label, value }) => ({ label, value })),
        [points],
    );
    const definition = useMemo(
        () =>
            defineChart({
                marks: [
                    lineY(rows, {
                        x: "label",
                        y: "value",
                        stroke: "var(--brand-purple)",
                        strokeWidth: 3,
                    }),
                ],
                scales: {
                    x: { scale: scalePoint, axis: { ticks: { count: 6 } } },
                    y: { scale: scaleLinear, nice: true, grid: true },
                },
            }),
        [rows],
    );

    return (
        <Chart
            definition={definition}
            height={height}
            initialWidth={initialWidth}
            ariaLabel={ariaLabel}
        />
    );
}

export function IllustrativeTrendChart() {
    return (
        <TrendChart
            points={illustrativePoints}
            height={120}
            initialWidth={400}
            ariaLabel="Illustrative rising trend, not live market data"
        />
    );
}

export function OpsSeriesChart({ points }: { points: OpsChartPoint[] }) {
    const rows = useMemo(
        () =>
            points.flatMap<OpsSeriesPoint>((point) => [
                { label: point.label, series: "Total", value: point.value },
                {
                    label: point.label,
                    series: "Failed / alerts",
                    value: point.failed,
                },
            ]),
        [points],
    );
    const definition = useMemo(
        () =>
            defineChart({
                marks: [
                    barY(rows, {
                        x: "label",
                        y: "value",
                        z: "series",
                        fill: (point) =>
                            point.series === "Total"
                                ? "var(--brand-purple)"
                                : "var(--brand-loss)",
                        layout: group({
                            scale: () => scaleBand().padding(0.12),
                        }),
                    }),
                ],
                scales: {
                    x: { scale: () => scaleBand().padding(0.2) },
                    y: { scale: scaleLinear, nice: true, grid: true },
                },
            }),
        [rows],
    );

    return (
        <Chart
            definition={definition}
            height={190}
            initialWidth={760}
            ariaLabel="daily totals and failures. Exact values are in the table below."
        />
    );
}
