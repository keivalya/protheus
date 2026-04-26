import type {
  BudgetBreakdownItem as RealBudgetBreakdownItem,
  BudgetSummary as RealBudgetSummary,
  OperationalPlanResponse,
  Paper,
  SupplyChainItem,
  TimelineTask,
} from "../types";

export type MaterialTag = "critical" | "standard" | "bulk";

export type PlanMaterial = {
  name: string;
  spec: string;
  catalog: string;
  supplier: string;
  qty: number;
  cost: number;
  tag: MaterialTag;
};

export type BudgetRow = {
  label: string;
  amount: number;
  pct: number;
  colorIndex: number;
};

export type Phase = {
  name: string;
  subtitle: string;
  startWeek: number;
  duration: number;
  colorIndex: number;
  label: string;
};

export type MilestoneType = "milestone" | "gate" | "decision";

export type Milestone = {
  week: number;
  type: MilestoneType;
  title: string;
  description: string;
};

export type DependencyCategory =
  | "equipment"
  | "personnel"
  | "approval"
  | "external"
  | "training";

export type Dependency = {
  category: DependencyCategory;
  title: string;
  description: string;
  meta?: { k: string; v: string }[];
};

export type ValidationTier = "primary" | "secondary" | "tertiary" | "statistical";

export type Validation = {
  tier: ValidationTier;
  title: string;
  description: string;
  thresholds: { k: string; v: string }[];
};

export type ProtocolStepView = {
  number: number;
  title: string;
  duration: string;
  body: string;
  meta?: { k: string; v: string }[];
  source?: string;
};

export type FundingType = "gov" | "foundation" | "industry" | "eu";

export type FundingOpportunity = {
  name: string;
  funder: string;
  type: FundingType;
  amountMin: number;
  amountMax: number;
  currencySymbol: string;
  deadline: string;
  url: string;
  fitScore: number;
  fitReason: string;
  description: string;
};

export type Funding = {
  intro: string;
  opportunities: FundingOpportunity[];
};

export type Plan = {
  title: string;
  summary: string;
  basedOn?: { title: string; url: string };
  stats: {
    budgetTotal: number;
    currency: string;
    currencySymbol: string;
    durationWeeks: number;
    materialsCount: number;
    phases: number;
    confidence: string;
    confidenceReason: string;
  };
  steps: ProtocolStepView[];
  materials: PlanMaterial[];
  budget: {
    rows: BudgetRow[];
    metrics: {
      costPerUnit: string;
      costPerWeek: string;
      leadTime: string;
      reorderRisk: string;
    };
    contextNote: string;
    footerLeft: string;
  };
  timeline: {
    weeks: number;
    phases: Phase[];
    milestones: Milestone[];
  };
  dependencies: Dependency[];
  validation: Validation[];
  funding: Funding;
};

const SAMPLE_PLAN: Plan = {
  title:
    "Materials protocol: Can we improve solar cell efficiency by testing alternative materials? operational plan",
  summary:
    "Grounded in Can we improve the record efficiency of CdS/CdTe solar cells?.",
  stats: {
    budgetTotal: 12450,
    currency: "GBP",
    currencySymbol: "£",
    durationWeeks: 10,
    materialsCount: 14,
    phases: 4,
    confidence: "Draft",
    confidenceReason: "Needs source and SOP review",
  },
  steps: [
    {
      number: 1,
      title: "Define formulation matrix",
      duration: "~ 1 hr",
      body:
        "Set the test material, baseline, and controlled variables. Keep processing conditions constant unless the selected source justifies a change.",
      meta: [{ k: "Design", v: "source-aligned" }],
      source: "https://doi.org/10.1016/j.solmat.2006.02.019",
    },
    {
      number: 2,
      title: "Prepare matched batches",
      duration: "~ 0.5–2 days",
      body:
        "Prepare small batches with documented purity, atmosphere, timing, and storage conditions.",
      meta: [{ k: "Preparation", v: "verify before execution" }],
      source: "https://doi.org/10.1016/j.solmat.2006.02.019",
    },
    {
      number: 3,
      title: "Fabricate matched devices",
      duration: "~ 2–4 days",
      body:
        "Run identical fabrication on each batch. Track every parameter (spin speed, anneal time, atmosphere) so any deviation can be linked to a single variable.",
      meta: [{ k: "Fabrication", v: "matched conditions" }],
    },
    {
      number: 4,
      title: "Characterize J-V & EQE",
      duration: "~ 2 days",
      body:
        "Measure J-V under AM 1.5G, EQE across 300–900 nm, and stabilized maximum-power-point output. n ≥ 8 devices per condition.",
      meta: [{ k: "Readout", v: "PCE / Voc / Jsc / FF" }],
    },
    {
      number: 5,
      title: "Operational stability",
      duration: "~ 3 wk",
      body:
        "Run 500 h MPP tracking under continuous 1-sun illumination at 30 °C in N₂ atmosphere. Capture T₈₀ and document failure modes.",
      meta: [{ k: "Stability", v: "T₈₀ at 30 °C" }],
    },
    {
      number: 6,
      title: "Decision & write-up",
      duration: "~ 1 wk",
      body:
        "If best-composition PCE meets the target, prepare a manuscript draft and identify follow-up scaling steps. Otherwise document failure modes and propose a pivot.",
      meta: [{ k: "Output", v: "manuscript + decision memo" }],
    },
  ],
  materials: [
    {
      name: "Lead(II) iodide, 99.99%",
      spec: "PbI₂ · 5 g",
      catalog: "211168-5G",
      supplier: "Sigma-Aldrich",
      qty: 2,
      cost: 1840,
      tag: "critical",
    },
    {
      name: "Methylammonium iodide, anhydrous",
      spec: "MAI · 5 g",
      catalog: "793493-5G",
      supplier: "Sigma-Aldrich",
      qty: 1,
      cost: 312,
      tag: "critical",
    },
    {
      name: "Formamidinium iodide, 99%",
      spec: "FAI · 5 g",
      catalog: "736902-5G",
      supplier: "Sigma-Aldrich",
      qty: 1,
      cost: 428,
      tag: "standard",
    },
    {
      name: "Cesium iodide, 99.999%",
      spec: "CsI · 5 g",
      catalog: "203033-5G",
      supplier: "Sigma-Aldrich",
      qty: 1,
      cost: 260,
      tag: "standard",
    },
    {
      name: "Spiro-OMeTAD, 99%",
      spec: "HTL · 1 g",
      catalog: "792071-1G",
      supplier: "Sigma-Aldrich",
      qty: 2,
      cost: 1860,
      tag: "critical",
    },
    {
      name: "PCBM, 99.5%",
      spec: "ETL · 1 g",
      catalog: "684465-1G",
      supplier: "Sigma-Aldrich",
      qty: 1,
      cost: 540,
      tag: "standard",
    },
    {
      name: "DMF, anhydrous, 99.8%",
      spec: "Solvent · 100 mL",
      catalog: "227056-100ML",
      supplier: "Sigma-Aldrich",
      qty: 2,
      cost: 184,
      tag: "bulk",
    },
    {
      name: "DMSO, anhydrous, 99.9%",
      spec: "Solvent · 100 mL",
      catalog: "276855-100ML",
      supplier: "Sigma-Aldrich",
      qty: 2,
      cost: 162,
      tag: "bulk",
    },
    {
      name: "Chlorobenzene, anhydrous",
      spec: "Antisolvent · 100 mL",
      catalog: "284513-100ML",
      supplier: "Sigma-Aldrich",
      qty: 1,
      cost: 96,
      tag: "bulk",
    },
    {
      name: "ITO-coated glass substrates",
      spec: "25 × 25 mm · 15 Ω/sq",
      catalog: "578274",
      supplier: "Ossila",
      qty: 40,
      cost: 480,
      tag: "standard",
    },
    {
      name: "Gold pellets, 99.999%",
      spec: "Au · 1 g",
      catalog: "G-1G",
      supplier: "Kurt J. Lesker",
      qty: 1,
      cost: 410,
      tag: "standard",
    },
    {
      name: "Lithium bis(trifluoromethanesulfonyl)imide",
      spec: "Li-TFSI · 5 g",
      catalog: "544094-5G",
      supplier: "Sigma-Aldrich",
      qty: 1,
      cost: 218,
      tag: "standard",
    },
    {
      name: "tert-Butylpyridine, 99%",
      spec: "tBP · 100 mL",
      catalog: "T28207-100ML",
      supplier: "Sigma-Aldrich",
      qty: 1,
      cost: 86,
      tag: "bulk",
    },
    {
      name: "Encapsulation glass + UV epoxy kit",
      spec: "Bench kit",
      catalog: "ENC-KIT-2",
      supplier: "Ossila",
      qty: 1,
      cost: 144,
      tag: "bulk",
    },
  ],
  budget: {
    rows: [
      { label: "Reagents & consumables", amount: 6920, pct: 56, colorIndex: 1 },
      { label: "Equipment time (booked)", amount: 2800, pct: 23, colorIndex: 2 },
      { label: "Characterization fees", amount: 1250, pct: 10, colorIndex: 3 },
      { label: "RA personnel (0.4 FTE × 10wk)", amount: 980, pct: 8, colorIndex: 4 },
      { label: "Contingency (4%)", amount: 500, pct: 4, colorIndex: 5 },
    ],
    metrics: {
      costPerUnit: "~£520 / device",
      costPerWeek: "£1,245",
      leadTime: "8 days",
      reorderRisk: "Low",
    },
    contextNote:
      "Within the typical envelope for a 10-week perovskite device study at this scale (literature avg: £9k–£18k).",
    footerLeft: "Quoted prices · GBP · ex VAT",
  },
  timeline: {
    weeks: 10,
    phases: [
      {
        name: "Phase 1 · Setup",
        subtitle: "Procurement & substrate prep",
        startWeek: 2,
        duration: 2,
        colorIndex: 1,
        label: "P1 · setup",
      },
      {
        name: "Phase 2 · Synthesis",
        subtitle: "Precursor & spin-coating",
        startWeek: 4,
        duration: 3,
        colorIndex: 2,
        label: "P2 · fabricate",
      },
      {
        name: "Phase 3 · Devices",
        subtitle: "HTL & contact deposition",
        startWeek: 6,
        duration: 2,
        colorIndex: 3,
        label: "P3 · finish",
      },
      {
        name: "Phase 4 · Characterize",
        subtitle: "J-V, EQE, MPP tracking",
        startWeek: 8,
        duration: 2,
        colorIndex: 4,
        label: "P4 · measure",
      },
      {
        name: "Reporting",
        subtitle: "Analysis & manuscript draft",
        startWeek: 10,
        duration: 1,
        colorIndex: 5,
        label: "Write-up",
      },
    ],
    milestones: [
      {
        week: 2,
        type: "milestone",
        title: "All reagents on bench",
        description: "Cleaned ITO substrates ready; precursors prepared.",
      },
      {
        week: 6,
        type: "gate",
        title: "First working device",
        description:
          "If PCE < 12% on baseline composition, abort & debug spin-coater calibration.",
      },
      {
        week: 10,
        type: "decision",
        title: "Stability data complete",
        description:
          "500h MPP tracking finished. Decision: scale-up or pivot composition.",
      },
    ],
  },
  dependencies: [
    {
      category: "equipment",
      title: "Laurell WS-650 spin coater",
      description:
        "Primary deposition tool. Must be booked across the synthesis phase; no fall-back instrument available in the building.",
      meta: [
        { k: "Booked", v: "weeks 3–6" },
        { k: "Backup", v: "None — block calendar" },
      ],
    },
    {
      category: "equipment",
      title: "Kurt J. Lesker NANO 36 evaporator",
      description:
        "Required for gold contact deposition. Shared resource with adjacent group; reserve via shared calendar 4 weeks ahead.",
      meta: [
        { k: "Booked", v: "weeks 5–7" },
        { k: "Lead time", v: "4 weeks" },
      ],
    },
    {
      category: "personnel",
      title: "0.4 FTE research assistant",
      description:
        "Trained postgrad needed for spin-coating runs and J–V measurements. Confirm availability during weeks 3–8.",
      meta: [
        { k: "FTE", v: "0.4" },
        { k: "Period", v: "weeks 3–8" },
      ],
    },
    {
      category: "training",
      title: "Glovebox & solvent handling certification",
      description:
        "All operators must hold current N₂ glovebox certification and DMF/DMSO solvent training. Refresh dated > 12 months.",
      meta: [
        { k: "Owners", v: "Lab safety officer" },
        { k: "Lead time", v: "~5 days" },
      ],
    },
    {
      category: "approval",
      title: "Departmental safety review",
      description:
        "Solvent inventory and disposal pathway must be re-approved before first synthesis run.",
      meta: [
        { k: "Reviewer", v: "Dept. safety committee" },
        { k: "Turn-around", v: "~2 weeks" },
      ],
    },
    {
      category: "external",
      title: "Synchrotron beamtime (optional)",
      description:
        "GIWAXS beamtime requested as a stretch dependency for crystallinity confirmation; not blocking the primary readout.",
      meta: [
        { k: "Source", v: "Diamond I07" },
        { k: "Lead time", v: "~3 months" },
      ],
    },
  ],
  validation: [
    {
      tier: "primary",
      title: "Power conversion efficiency (PCE)",
      description:
        "Champion device PCE measured under AM 1.5G illumination at 100 mW/cm², stabilized output. Compared across all three compositions (n = 8 devices each).",
      thresholds: [
        { k: "Success", v: "PCE ≥ 23.0% on best composition" },
        { k: "Floor", v: "≥ 18% on baseline (sanity check)" },
      ],
    },
    {
      tier: "secondary",
      title: "Hysteresis index",
      description:
        "Difference between forward- and reverse-scan PCE divided by their average. Lower is better; indicates ion-migration stability.",
      thresholds: [
        { k: "Success", v: "Hysteresis index < 0.05" },
        { k: "Method", v: "10 / 100 / 500 mV/s scans" },
      ],
    },
    {
      tier: "tertiary",
      title: "Operational stability (T₈₀)",
      description:
        "Time for stabilized power output to decay to 80% of initial value under continuous 1-sun illumination at 30 °C in N₂ atmosphere.",
      thresholds: [
        { k: "Success", v: "T₈₀ ≥ 500 h" },
        { k: "Track", v: "Continuous MPP" },
      ],
    },
    {
      tier: "statistical",
      title: "Reproducibility",
      description:
        "Standard deviation of PCE across 8 devices per composition. Tight distributions are more publishable than higher means with broad spread.",
      thresholds: [
        { k: "Success", v: "σ(PCE) ≤ 1.0 percentage point" },
        { k: "Sample", v: "n = 8 per condition" },
      ],
    },
  ],
  funding: {
    intro:
      "Solar PV / advanced materials projects of this scale typically draw from national agencies, EU programmes, and clean-energy foundations. Check the linked source pages for current deadlines and eligibility.",
    opportunities: [
      {
        name: "EPSRC responsive-mode research grants",
        funder: "UK Research and Innovation (EPSRC)",
        type: "gov",
        amountMin: 50000,
        amountMax: 1000000,
        currencySymbol: "£",
        deadline: "Check official call page",
        url: "https://www.ukri.org/councils/epsrc/",
        fitScore: 92,
        fitReason:
          "Direct route for UK-based engineering and physical sciences research with a materials-science framing.",
        description:
          "Responsive-mode route for fundamental engineering and physical sciences research; eligibility and deadlines must be checked on UKRI.",
      },
      {
        name: "ERC frontier research grants",
        funder: "European Research Council",
        type: "eu",
        amountMin: 1000000,
        amountMax: 2500000,
        currencySymbol: "$",
        deadline: "Check ERC work programme",
        url: "https://erc.europa.eu/",
        fitScore: 78,
        fitReason:
          "ERC schemes vary by PI career stage. Use the official ERC work programme for current call dates and limits.",
        description:
          "ERC schemes vary by PI career stage. Use the official ERC work programme for current call dates and limits.",
      },
      {
        name: "Horizon Europe — Climate, Energy & Mobility cluster",
        funder: "European Commission",
        type: "eu",
        amountMin: 500000,
        amountMax: 5000000,
        currencySymbol: "$",
        deadline: "See cluster work programme",
        url: "https://ec.europa.eu/info/funding-tenders",
        fitScore: 71,
        fitReason: "Strong alignment with clean-energy and PV materials calls.",
        description:
          "Collaborative R&I actions on clean energy technologies, with photovoltaic and materials topics opening on rolling work programmes.",
      },
      {
        name: "Royal Society Research Project Grants",
        funder: "The Royal Society",
        type: "foundation",
        amountMin: 5000,
        amountMax: 25000,
        currencySymbol: "£",
        deadline: "Rolling — see scheme page",
        url: "https://royalsociety.org/grants-schemes-awards/grants/",
        fitScore: 64,
        fitReason:
          "Smaller seed-style grants for early-stage materials investigations.",
        description:
          "Small project grants useful for pilot and feasibility work that can de-risk a larger application.",
      },
    ],
  },
};

function titleCase(value: string) {
  if (!value) return "";
  return value.charAt(0).toUpperCase() + value.slice(1);
}

function shortQuestion(question: string, max = 90) {
  const clean = question.replace(/\s+/g, " ").trim();
  if (!clean) return "";
  return clean.length > max ? `${clean.slice(0, max - 1).trim()}…` : clean;
}

export function buildPlanFromContext(args: {
  question: string;
  draftTitle?: string;
  basedOn?: Paper | null;
}): Plan {
  const plan = JSON.parse(JSON.stringify(SAMPLE_PLAN)) as Plan;
  const q = shortQuestion(args.question);
  if (q) {
    plan.title = `${titleCase(args.draftTitle || "Materials protocol")}: ${q} operational plan`;
    plan.summary = args.basedOn
      ? `Grounded in ${args.basedOn.title}.`
      : `Grounded in ${q}.`;
  } else if (args.draftTitle) {
    plan.title = `${titleCase(args.draftTitle)} operational plan`;
  }
  if (args.basedOn) {
    plan.basedOn = {
      title: args.basedOn.title,
      url: args.basedOn.url || (args.basedOn.doi ? `https://doi.org/${args.basedOn.doi}` : "#"),
    };
    plan.steps = plan.steps.map((step) => ({
      ...step,
      source: step.source || plan.basedOn?.url,
    }));
  }
  return plan;
}

export function fmtNumber(value: number, dp = 0): string {
  if (typeof value !== "number" || Number.isNaN(value)) return "—";
  return value.toLocaleString("en-GB", { maximumFractionDigits: dp });
}

export function fmtRange(min: number, max: number, sym = "£"): string {
  if (min == null && max == null) return "—";
  if (min === max) return `${sym}${fmtNumber(min)}`;
  return `${sym}${fmtNumber(min)}–${sym}${fmtNumber(max)}`;
}

export function fmtGenerated(date = new Date()): string {
  return `Generated ${date.toLocaleString("en-GB", {
    day: "numeric",
    month: "short",
    year: "numeric",
    hour: "2-digit",
    minute: "2-digit",
  })}`.replace(/\b([a-z])/g, (m) => m.toUpperCase());
}

const CURRENCY_SYMBOLS: Record<string, string> = {
  USD: "$",
  GBP: "£",
  EUR: "€",
  CAD: "C$",
  AUD: "A$",
};

function symbolFor(currency: string | undefined | null): string {
  if (!currency) return "$";
  return CURRENCY_SYMBOLS[currency] || `${currency} `;
}

function categoryLabel(category: string): string {
  return category
    .replace(/_/g, " ")
    .replace(/\band\b/gi, "&")
    .replace(/\b([a-z])/g, (m) => m.toUpperCase());
}

function categoryToTag(category: string): MaterialTag {
  const c = category.toLowerCase();
  if (c.includes("equipment")) return "bulk";
  if (c.includes("consumable") || c.includes("kits")) return "standard";
  if (c.includes("cell") || c.includes("biological") || c.includes("reagent")) return "critical";
  return "standard";
}

function parseQty(quantity: string): number {
  const match = quantity.match(/-?\d+(?:\.\d+)?/);
  if (!match) return 1;
  const value = Number(match[0]);
  return Number.isFinite(value) && value > 0 ? Math.max(1, Math.round(value)) : 1;
}

function rangeMid(min?: number | null, max?: number | null): number {
  if (min == null && max == null) return 0;
  if (min == null) return max ?? 0;
  if (max == null) return min ?? 0;
  return (min + max) / 2;
}

function fmtCurrency(value: number, sym: string): string {
  if (!Number.isFinite(value) || value <= 0) return "—";
  return `${sym}${fmtNumber(value, 0)}`;
}

function supplyChainToMaterials(items: SupplyChainItem[]): PlanMaterial[] {
  return items.map((item) => {
    const top = item.supplier_candidates[0];
    const cost = rangeMid(item.item_cost_range?.min, item.item_cost_range?.max)
      || rangeMid(top?.estimated_price_range?.min, top?.estimated_price_range?.max);
    return {
      name: item.item_name,
      spec: top?.package_size || item.quantity_needed || "",
      catalog: top?.catalog_number || "—",
      supplier: top?.vendor || "—",
      qty: parseQty(item.quantity_needed),
      cost,
      tag: categoryToTag(item.category),
    };
  });
}

function budgetSummaryToBudget(
  summary: RealBudgetSummary,
  breakdown: RealBudgetBreakdownItem[],
): Plan["budget"] {
  const totals = breakdown.map((row) => rangeMid(row.min, row.max));
  const grandTotal = totals.reduce((a, b) => a + b, 0);
  const sym = symbolFor(summary.estimated_total_range.currency);
  const rows: BudgetRow[] = breakdown.map((row, idx) => {
    const amount = totals[idx] || 0;
    const pct = grandTotal > 0 ? Math.round((amount / grandTotal) * 100) : 0;
    return {
      label: row.label,
      amount,
      pct,
      colorIndex: ((idx % 5) + 1) as BudgetRow["colorIndex"],
    };
  });
  return {
    rows,
    metrics: {
      costPerUnit: summary.priced_items
        ? `${sym}${fmtNumber(grandTotal / summary.priced_items, 0)} / item`
        : "—",
      costPerWeek: "—",
      leadTime: summary.notes[0] ? "See notes" : "—",
      reorderRisk:
        summary.confidence === "high"
          ? "Low"
          : summary.confidence === "medium"
          ? "Medium"
          : "High",
    },
    contextNote:
      summary.priced_items === summary.total_items
        ? "All extracted line items have at least one supplier price."
        : `${summary.priced_items} of ${summary.total_items} line items have a price; ${summary.missing_prices} need procurement confirmation.`,
    footerLeft: `Quoted prices · ${summary.estimated_total_range.currency} · ex VAT`,
  };
}

function timelineTasksToPhases(tasks: TimelineTask[]): Plan["timeline"] {
  if (!tasks.length) {
    return { weeks: 1, phases: [], milestones: [] };
  }
  const starts = tasks
    .map((t) => Date.parse(t.scheduled_start))
    .filter((n) => !Number.isNaN(n));
  const ends = tasks
    .map((t) => Date.parse(t.scheduled_end))
    .filter((n) => !Number.isNaN(n));
  if (!starts.length || !ends.length) {
    return { weeks: 1, phases: [], milestones: [] };
  }
  const planStart = Math.min(...starts);
  const planEnd = Math.max(...ends);
  const dayMs = 1000 * 60 * 60 * 24;
  const totalDays = Math.max(1, Math.ceil((planEnd - planStart) / dayMs));
  const weeks = Math.max(1, Math.ceil(totalDays / 7));

  const byPhase = new Map<string, TimelineTask[]>();
  for (const t of tasks) {
    const arr = byPhase.get(t.phase) || [];
    arr.push(t);
    byPhase.set(t.phase, arr);
  }

  const phases: Phase[] = Array.from(byPhase.entries()).map(([name, group], idx) => {
    const phaseStart = Math.min(...group.map((t) => Date.parse(t.scheduled_start)).filter((n) => !Number.isNaN(n)));
    const phaseEnd = Math.max(...group.map((t) => Date.parse(t.scheduled_end)).filter((n) => !Number.isNaN(n)));
    const startWeek = Math.max(0, Math.floor((phaseStart - planStart) / dayMs / 7));
    const span = Math.max(1, Math.ceil((phaseEnd - phaseStart) / dayMs / 7));
    return {
      name,
      subtitle: `${group.length} task${group.length === 1 ? "" : "s"}`,
      startWeek,
      duration: span,
      colorIndex: (idx % 5) + 1,
      label: name,
    };
  });

  return { weeks, phases, milestones: [] };
}

export function mergeOperationalPlan(plan: Plan, op: OperationalPlanResponse | null): Plan {
  if (!op) return plan;
  const sym = symbolFor(op.budget_summary.estimated_total_range.currency);
  const totalMax = op.budget_summary.estimated_total_range.max ?? 0;
  const totalMin = op.budget_summary.estimated_total_range.min ?? totalMax;
  const total = totalMax || totalMin || 0;

  const realMaterials = supplyChainToMaterials(op.supply_chain_items);
  const realBudget = budgetSummaryToBudget(op.budget_summary, op.budget_breakdown);
  const realTimeline = timelineTasksToPhases(op.timeline);

  return {
    ...plan,
    stats: {
      ...plan.stats,
      budgetTotal: total > 0 ? Math.round(total) : plan.stats.budgetTotal,
      currency: op.budget_summary.estimated_total_range.currency || plan.stats.currency,
      currencySymbol: sym,
      durationWeeks: realTimeline.weeks || plan.stats.durationWeeks,
      materialsCount: op.supply_chain_items.length || plan.stats.materialsCount,
      phases: realTimeline.phases.length || plan.stats.phases,
      confidence: categoryLabel(op.budget_summary.confidence),
      confidenceReason: op.budget_summary.notes[0] || plan.stats.confidenceReason,
    },
    materials: realMaterials.length ? realMaterials : plan.materials,
    budget: op.budget_breakdown.length ? realBudget : plan.budget,
    timeline: realTimeline.phases.length
      ? { ...realTimeline, milestones: plan.timeline.milestones }
      : plan.timeline,
  };
}

export type { OperationalPlanResponse };

