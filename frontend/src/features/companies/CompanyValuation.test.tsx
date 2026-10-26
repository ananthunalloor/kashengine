import { fireEvent, render, screen, within } from "@testing-library/react";
import { expect, it } from "vitest";
import { ThemeProvider } from "../../app/ThemeProvider";
import { CompanyValuation, sectorValuation } from "./CompanyValuation";

const pair = (
  name: string,
  company_value: string | number | null,
  sector_value: string | number | null,
) => ({ name, company_value, sector_value });
const ratios = (...rows: ReturnType<typeof pair>[]) => ({ "key-ratios": rows });

it("reports a premium or discount with exact benchmark differences, not an absolute value claim", () => {
  const premium = sectorValuation(
    ratios(pair("P/E", 20, 15), pair("P/B", 4, 2), pair("EV/EBITDA", 12, 10)),
  );
  expect(premium.state).toBe("Sector premium");
  expect(premium.compared).toBe(3);
  expect(premium.rows[0].difference).toBeCloseTo(33.333333);
  expect(premium.rows[1].difference).toBe(100);
  const discount = sectorValuation(ratios(pair("P/E", 10, 20)));
  expect(discount.state).toBe("Sector discount");
  expect(discount.rows[0].difference).toBe(-50);
});

it("handles mixed and equal ratios without averaging them into a misleading verdict", () => {
  expect(sectorValuation(ratios(pair("P/E", 20, 15), pair("P/B", 1, 2))).state).toBe(
    "Mixed valuation",
  );
  expect(sectorValuation(ratios(pair("P/E", 20, 20))).state).toBe("In line with sector");
  expect(sectorValuation(ratios(pair("P/E", 20, 20), pair("P/B", 1, 2))).state).toBe(
    "Sector discount",
  );
});

it.each([null, "", " ", "N/A", "-", 0, -5, "20%", true, Number.NaN, Number.POSITIVE_INFINITY])(
  "excludes unusable company or sector values: %s",
  (value) => {
    const fundamentals = { ratios: [{ name: "P/E", company_value: value, sector_value: 15 }] };
    expect(sectorValuation(fundamentals).compared).toBe(0);
    expect(
      sectorValuation({ ratios: [{ name: "P/E", company_value: 15, sector_value: value }] }).state,
    ).toBe("Insufficient data");
  },
);

it("matches explicit supported aliases, not EPS, yield, unrelated profiles or future-period ratios", () => {
  const result = sectorValuation(
    ratios(
      pair("Price to Earnings Ratio", "1,200", "600"),
      pair("Price_to_Book", "3", "2"),
      pair("Enterprise Value to EBITDA", 15, 10),
      pair("EPS", 20, 10),
      pair("Forward P/E", 10, 20),
    ),
  );
  expect(result.compared).toBe(3);
  expect(result.state).toBe("Sector premium");
  expect(sectorValuation({ profile: { company_profile: "P/E 30" } }).state).toBe(
    "Insufficient data",
  );
});

it("deduplicates identical observations and excludes conflicting observations", () => {
  const same = ratios(pair("P/E", 20, 15), pair("PE Ratio", "20", "15"));
  expect(sectorValuation(same).compared).toBe(1);
  const conflict = sectorValuation(ratios(pair("P/E", 20, 15), pair("PE Ratio", 10, 15)));
  expect(conflict.state).toBe("Insufficient data");
  expect(conflict.rows[0]).toMatchObject({
    company: null,
    sector: null,
    reason: "Conflicting saved values",
  });
});

it("renders an understandable summary, table, timestamp and collapsed explanation", () => {
  render(
    <ThemeProvider>
      <CompanyValuation
        data={{
          fundamentals: ratios(pair("P/E", 20, 15)),
          fundamentals_as_of: "2026-10-22T10:00:00Z",
        }}
      />
    </ThemeProvider>,
  );
  expect(screen.getByRole("heading", { name: "Is this company overvalued?" })).toBeInTheDocument();
  expect(screen.getByRole("alert", { name: "Sector premium" })).toBeInTheDocument();
  expect(screen.getByText(/Limited evidence/)).toBeInTheDocument();
  const table = within(screen.getByRole("table", { name: "Valuation multiples vs sector" }));
  expect(table.getByText("33.33% premium")).toBeInTheDocument();
  expect(table.getByText("20x")).toBeInTheDocument();
  expect(screen.getByText(/22 Oct 2026/)).toHaveTextContent("not live");
  expect(screen.getByText(/not proof of overvaluation/)).toBeInTheDocument();
  const method = screen.getByRole("button", { name: "How to read this valuation" });
  expect(method).toHaveAttribute("aria-expanded", "false");
  fireEvent.click(method);
  expect(method).toHaveAttribute("aria-expanded", "true");
});

it("shows insufficient data and unknown freshness without manufacturing a valuation", () => {
  render(
    <ThemeProvider>
      <CompanyValuation
        data={{
          fundamentals: {},
          fundamentals_as_of: null,
        }}
      />
    </ThemeProvider>,
  );
  expect(screen.getByRole("alert", { name: "Insufficient data" })).toBeInTheDocument();
  expect(screen.getByText("0 of 3 multiples comparable")).toBeInTheDocument();
  expect(screen.getByText(/freshness cannot be verified/)).toBeInTheDocument();
});
