import { render, screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, beforeAll } from "vitest";
import { existsSync } from "node:fs";
import { join } from "node:path";
import { ForecastExplorer } from "@/components/ForecastExplorer";
import { FrontierExplorer, RegistryExplorer } from "@/components/BenchmarksExplorer";
import { JourneyExplorer } from "@/components/JourneyExplorer";
import { LabExplorer } from "@/components/LabExplorer";
import PublicationPage from "@/app/publication/page";
import { evidence } from "@/lib/evidence";
import { MATERIAL } from "@/lib/publication";
import { REPO_ROOT } from "../../scripts/build-evidence.mjs";

beforeAll(() => {
  // jsdom has no ResizeObserver; charts fall back to their default width.
  (globalThis as unknown as { ResizeObserver?: unknown }).ResizeObserver = undefined;
});

const data = {
  scores: evidence.scores,
  contrasts: evidence.contrasts,
  shifts: evidence.shifts,
  group_cells: evidence.group_cells,
  scale_coverage: evidence.scale_coverage,
  pit: evidence.pit,
  studies: evidence.studies,
};

describe("ForecastExplorer", () => {
  it("states the sign convention and target Y", () => {
    render(<ForecastExplorer data={data} />);
    expect(screen.getAllByText(/lower-is-better/i).length).toBeGreaterThan(0);
    expect(screen.getAllByText(/target Y/).length).toBeGreaterThan(0);
  });

  it("changing selectors changes records, units and sources", async () => {
    const user = userEvent.setup();
    render(<ForecastExplorer data={data} />);
    const summary = screen.getByTestId("selection-summary");
    expect(summary).toHaveTextContent("5 model records");
    expect(summary).toHaveTextContent("observable_strength_forecasting");
    await user.click(screen.getByTestId("study-RES-639"));
    expect(summary).toHaveTextContent("3 model records");
    expect(summary).toHaveTextContent("history_conditional_uncertainty");
    await user.selectOptions(screen.getByLabelText("Scenario"), "VELOCITY_NOISE_SHIFT");
    expect(summary).toHaveTextContent("shift scenario");
    await user.selectOptions(screen.getByLabelText("Lift"), "squat");
    expect(summary).toHaveTextContent("Squat");
    expect(screen.getByText(/No interval for this slice/)).toBeInTheDocument();
  });

  it("disables plan/horizon for RES-639 and enables it for RES-616 strata", async () => {
    const user = userEvent.setup();
    render(<ForecastExplorer data={data} />);
    const group = screen.getByLabelText("Plan / horizon");
    expect(group).toBeEnabled();
    await user.selectOptions(group, "cessation/56");
    expect(screen.getByTestId("selection-summary")).toHaveTextContent("3 model records");
    await user.click(screen.getByTestId("study-RES-639"));
    expect(screen.getByLabelText("Plan / horizon")).toBeDisabled();
  });

  it("shows the paired Ridge-vs-GRU CI row with the documented sign", () => {
    render(<ForecastExplorer data={data} />);
    const table = screen.getByRole("region", { name: /Paired CRPS difference \(kg\), TEST_A/ });
    expect(within(table).getByText(/M2_C minus M1_C \(primary\)/)).toBeInTheDocument();
  });
});

describe("Benchmarks", () => {
  it("filters the registry by identity authority", async () => {
    const user = userEvent.setup();
    render(<RegistryExplorer registry={evidence.registry} />);
    expect(screen.getByText(/\(9 rows\)/)).toBeInTheDocument();
    await user.selectOptions(screen.getByLabelText("Identity authority"), "PUBLIC_NATIVE");
    expect(screen.getByText(/\(1 row\)/)).toBeInTheDocument();
  });

  it("shows one target at a time and filters candidate classes", async () => {
    const user = userEvent.setup();
    render(<FrontierExplorer frontier={evidence.frontier} />);
    expect(screen.getByTestId("frontier-summary")).toHaveTextContent("22 fit or ensemble identities");
    await user.selectOptions(screen.getByLabelText("Candidate class"), "RES-274_IMMUTABLE_PUBLIC_NATIVE_EXPERT");
    expect(screen.getByTestId("frontier-summary")).toHaveTextContent("4 fit or ensemble identities");
    await user.selectOptions(screen.getByLabelText(/Target lift/), "deadlift");
    expect(screen.getByTestId("frontier-summary")).toHaveTextContent("Deadlift");
  });
});

describe("Journey", () => {
  it("keeps G2 as unsupported, not impossible, and flags restricted aggregates", async () => {
    const user = userEvent.setup();
    render(<JourneyExplorer data={{ facts: evidence.facts, studies: evidence.studies, sources: evidence.sources }} />);
    await user.click(screen.getByTestId("stage-G2"));
    const panel = screen.getByTestId("stage-panel");
    expect(panel).toHaveTextContent("FULL_G2_IDENTIFICATION_UNSUPPORTED");
    expect(panel).toHaveTextContent(/not a proof of impossibility/);
    await user.click(screen.getByTestId("stage-RES-615"));
    expect(screen.getAllByText(/restricted raw evidence, aggregate report only/i).length).toBeGreaterThan(0);
  });
});

describe("Lab", () => {
  it("labels the demonstration and responds to the plan", async () => {
    const user = userEvent.setup();
    render(<LabExplorer />);
    expect(screen.getByText(/not research evidence, not athlete data/i)).toBeInTheDocument();
    const before = screen.getAllByRole("row").map((r) => r.textContent).join("|");
    await user.click(screen.getByTestId("plan-cessation"));
    const after = screen.getAllByRole("row").map((r) => r.textContent).join("|");
    expect(after).not.toBe(before);
  });
});

describe("Publication page", () => {
  it("shows the pending state with no DOI, no PDF and no private repository link", () => {
    const { container } = render(<PublicationPage />);
    expect(screen.getByTestId("publication-status")).toHaveTextContent(/in private preparation — public release pending/i);
    expect(screen.getByTestId("publication-status")).toHaveTextContent(/Release pending/i);
    const hrefs = [...container.querySelectorAll("a")].map((a) => a.getAttribute("href") ?? "");
    expect(hrefs.some((h) => /\.pdf($|\?)/i.test(h))).toBe(false);
    expect(hrefs.some((h) => /powerlifting-state-research-paper/.test(h))).toBe(false);
    expect(container.querySelector("a[download]")).toBeNull();
    expect(container.textContent).not.toMatch(/doi\.org|10\.\d{4,}\//);
    expect(hrefs.filter((h) => h.startsWith("https://github.com")).every((h) => h.startsWith("https://github.com/Litju/powerlifting-state-research/"))).toBe(true);
  });

  it("only lists files that exist in the public repository", () => {
    for (const m of MATERIAL) expect(existsSync(join(REPO_ROOT, m.path)), m.path).toBe(true);
  });
});
