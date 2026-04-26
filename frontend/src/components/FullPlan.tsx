import { useMemo, useRef, useState } from "react";
import {
  fmtGenerated,
  fmtNumber,
  fmtRange,
  type MaterialTag,
  type Plan,
} from "../lib/planMock";
import type { OperationalPlanResponse } from "../types";

const TABS = [
  { id: "protocol", label: "Protocol" },
  { id: "materials", label: "Materials" },
  { id: "budget", label: "Budget" },
  { id: "timeline", label: "Timeline" },
  { id: "dependencies", label: "Dependencies" },
  { id: "validation", label: "Validation" },
  { id: "funding", label: "Funding" },
] as const;

type TabId = (typeof TABS)[number]["id"];

const BAR_COLORS = [
  "var(--accent)",
  "var(--ink-2)",
  "var(--ok)",
  "var(--warning)",
  "var(--muted-2)",
];

const GANTT_COLORS = [
  "var(--accent)",
  "var(--ink)",
  "var(--ok)",
  "var(--warning)",
  "var(--muted)",
];

function SciText({ html }: { html: string }) {
  const safe = html.replace(/<(?!\/?(?:sub|sup)\b)[^>]*>/gi, "");
  return <span dangerouslySetInnerHTML={{ __html: safe }} />;
}

async function exportToPdf(node: HTMLElement, planTitle: string) {
  const slug =
    planTitle
      .replace(/[^a-z0-9]+/gi, "-")
      .replace(/^-+|-+$/g, "")
      .slice(0, 60) || "protocol-plan";
  document.body.classList.add("is-pdf-export");
  try {
    const mod = await import("html2pdf.js");
    const html2pdf = mod.default as unknown as () => {
      from: (el: HTMLElement) => {
        set: (opts: object) => { save: () => Promise<void> };
      };
    };
    const opts = {
      margin: [10, 10, 12, 10],
      filename: `Protheus-${slug}.pdf`,
      html2canvas: {
        scale: 2,
        useCORS: true,
        backgroundColor: "#ffffff",
        windowWidth: 720,
      },
      jsPDF: { unit: "mm", format: "a4", orientation: "portrait" },
      pagebreak: { mode: ["css", "legacy"], avoid: [".pdf-avoid-break"] },
    };
    await html2pdf().from(node).set(opts).save();
  } finally {
    document.body.classList.remove("is-pdf-export");
  }
}

function ProtocolPanel({ plan }: { plan: Plan }) {
  return (
    <div className="protocol-panel">
      {plan.steps.map((step) => (
        <article className="protocol-step" key={step.number} id={`step-${step.number}`}>
          <header>
            <div className="step-num">{String(step.number).padStart(2, "0")}</div>
            <div className="step-title">
              <SciText html={step.title} />
            </div>
            <div className="step-time">{step.duration}</div>
          </header>
          <div className="step-body">
            <p>
              <SciText html={step.body} />
            </p>
          </div>
          {step.meta?.length ? (
            <div className="step-meta">
              {step.meta.map((m) => (
                <span key={m.k}>
                  <strong>{m.k}:</strong> {m.v}
                </span>
              ))}
            </div>
          ) : null}
          {step.source ? (
            <a className="step-source" href={step.source} target="_blank" rel="noreferrer">
              ↗ {step.source}
            </a>
          ) : null}
        </article>
      ))}
    </div>
  );
}

function MaterialsPanel({ plan }: { plan: Plan }) {
  const [filter, setFilter] = useState<"all" | MaterialTag>("all");
  const totalReagents = useMemo(
    () => plan.materials.reduce((sum, m) => sum + (m.cost || 0), 0),
    [plan.materials],
  );
  const visible = useMemo(
    () => plan.materials.filter((m) => filter === "all" || m.tag === filter),
    [plan.materials, filter],
  );

  return (
    <div className="materials-panel">
      <div className="materials-toolbar">
        <div className="total">
          <strong>{plan.materials.length}</strong>
          <small>line items · £{fmtNumber(totalReagents)} in reagents</small>
        </div>
        <div className="spacer" />
        <div className="filter-chips">
          {(["all", "critical", "standard", "bulk"] as const).map((f) => (
            <button
              key={f}
              type="button"
              className={`chip ${filter === f ? "is-on" : ""}`}
              onClick={() => setFilter(f)}
            >
              {f === "all" ? "All" : f.charAt(0).toUpperCase() + f.slice(1)}
            </button>
          ))}
        </div>
      </div>
      <div className="table-wrap">
        <table className="materials">
          <thead>
            <tr>
              <th style={{ width: "32%" }}>Item</th>
              <th>Catalog</th>
              <th>Supplier</th>
              <th style={{ textAlign: "center" }}>Qty</th>
              <th style={{ textAlign: "right" }}>Cost</th>
            </tr>
          </thead>
          <tbody>
            {visible.map((m) => (
              <tr key={`${m.catalog}-${m.name}`}>
                <td className="m-name">
                  <SciText html={m.name} />
                  <small>
                    <SciText html={m.spec} />
                  </small>
                </td>
                <td className="m-cat">{m.catalog}</td>
                <td className="m-supplier">
                  {m.supplier}
                  <span
                    className={`row-tag ${
                      m.tag === "critical" ? "crit" : m.tag === "bulk" ? "bulk" : "std"
                    }`}
                  >
                    {m.tag.charAt(0).toUpperCase() + m.tag.slice(1)}
                  </span>
                </td>
                <td style={{ textAlign: "center" }}>{m.qty}</td>
                <td className="m-cost">£{fmtNumber(m.cost, 0)}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}

function BudgetPanel({ plan }: { plan: Plan }) {
  const sym = plan.stats.currencySymbol;
  return (
    <div className="budget-grid">
      <div className="budget-bars">
        <h4>Cost breakdown</h4>
        <div>
          {plan.budget.rows.map((row) => (
            <div className="budget-row" key={row.label}>
              <span className="lbl">{row.label}</span>
              <span className="val">
                {sym}
                {fmtNumber(row.amount)}
              </span>
              <div
                className="bar"
                style={
                  {
                    "--pct": `${row.pct}%`,
                    "--c": BAR_COLORS[row.colorIndex - 1] || BAR_COLORS[0],
                  } as React.CSSProperties
                }
              />
            </div>
          ))}
        </div>
        <div className="budget-bars-footer">
          <span>{plan.budget.footerLeft}</span>
          <span className="alt">{plan.budget.rows.length} categories</span>
        </div>
      </div>
      <div className="budget-summary">
        <h4>Total estimated cost</h4>
        <div className="budget-total">
          <span className="currency">{sym}</span>
          <span>{fmtNumber(plan.stats.budgetTotal)}</span>
        </div>
        <div className="budget-sub">{plan.budget.contextNote}</div>
        <div className="budget-mini">
          <div>
            <div className="k">Cost / device</div>
            <div className="v">{plan.budget.metrics.costPerUnit}</div>
          </div>
          <div>
            <div className="k">Cost / week</div>
            <div className="v">{plan.budget.metrics.costPerWeek}</div>
          </div>
          <div>
            <div className="k">Lead time</div>
            <div className="v">{plan.budget.metrics.leadTime}</div>
          </div>
          <div>
            <div className="k">Re-order risk</div>
            <div className="v reorder-risk">{plan.budget.metrics.reorderRisk}</div>
          </div>
        </div>
      </div>
    </div>
  );
}

function TimelinePanel({ plan }: { plan: Plan }) {
  const weeks = plan.timeline.weeks;
  const headCols = Array.from({ length: weeks }, (_, i) => `W${i + 1}`);
  return (
    <div className="gantt">
      <div className="gantt-grid">
        <div className="gantt-head" style={{ "--weeks": weeks } as React.CSSProperties}>
          <div className="col first">Phase</div>
          {headCols.map((label) => (
            <div className="col" key={label}>
              {label}
            </div>
          ))}
        </div>
        {plan.timeline.phases.map((phase) => (
          <div
            className="gantt-row"
            key={phase.name}
            style={{ "--weeks": weeks } as React.CSSProperties}
          >
            <div className="label">
              {phase.name}
              <small>{phase.subtitle}</small>
            </div>
            <div
              className="gantt-bar"
              style={
                {
                  "--start": phase.startWeek + 1,
                  "--span": phase.duration,
                  "--bg-c": GANTT_COLORS[phase.colorIndex - 1] || GANTT_COLORS[0],
                } as React.CSSProperties
              }
            >
              {phase.label}
            </div>
          </div>
        ))}
      </div>
      <div className="milestones">
        {plan.timeline.milestones.map((m) => (
          <div className="milestone" key={`${m.week}-${m.title}`}>
            <div className="ms-week">
              W{m.week}
              <small>{m.type}</small>
            </div>
            <div className="ms-text">
              <strong>{m.title}</strong>
              {m.description}
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}

function DependenciesPanel({ plan }: { plan: Plan }) {
  return (
    <div className="deps-grid">
      {plan.dependencies.map((dep) => (
        <article className={`dep-card cat-${dep.category}`} key={dep.title}>
          <div className="dep-cat">{dep.category}</div>
          <h5>{dep.title}</h5>
          <p>
            <SciText html={dep.description} />
          </p>
          {dep.meta?.length ? (
            <div className="dep-meta">
              {dep.meta.map((m) => (
                <span key={m.k}>
                  <strong>{m.k}:</strong> {m.v}
                </span>
              ))}
            </div>
          ) : null}
        </article>
      ))}
    </div>
  );
}

function ValidationPanel({ plan }: { plan: Plan }) {
  return (
    <div className="val-grid">
      {plan.validation.map((v) => (
        <article className="val-card" key={v.title}>
          <span className={`vtag t-${v.tier}`}>{v.tier}</span>
          <h5>
            <SciText html={v.title} />
          </h5>
          <p>
            <SciText html={v.description} />
          </p>
          {v.thresholds.map((th) => (
            <div className="threshold" key={th.k}>
              <span className="k">{th.k}</span>
              <strong>{th.v}</strong>
            </div>
          ))}
        </article>
      ))}
    </div>
  );
}

function FundingPanel({ plan }: { plan: Plan }) {
  return (
    <div className="funding-panel">
      <div className="fund-intro">
        <div className="fi-icon">£</div>
        <div className="fi-text">
          <strong>Funding routes to verify.</strong> {plan.funding.intro}
        </div>
      </div>
      <div className="fund-list">
        {plan.funding.opportunities.map((o) => (
          <article className="fund-card" key={o.name}>
            <div>
              <div className="fund-head">
                <span className={`fund-type ${o.type}`}>{o.type.toUpperCase()}</span>
                <span className="fund-funder">{o.funder}</span>
              </div>
              <h5>{o.name}</h5>
              <p>{o.description}</p>
              <div className="fund-meta">
                <span>
                  <strong>Status:</strong> {o.deadline}
                </span>
                <span>
                  <strong>Why fit:</strong> {o.fitReason}
                </span>
              </div>
            </div>
            <div className="fund-right">
              <div className="fund-fit">
                <strong>{o.fitScore}</strong>
                fit score
              </div>
              <div className="fund-amount">
                {fmtRange(o.amountMin, o.amountMax, o.currencySymbol)}
                <small>award range</small>
              </div>
              <a className="fund-link" href={o.url} target="_blank" rel="noreferrer">
                View call ↗
              </a>
            </div>
          </article>
        ))}
      </div>
    </div>
  );
}

export default function FullPlan({
  plan,
  operationalPlan,
}: {
  plan: Plan;
  operationalPlan?: OperationalPlanResponse | null;
}) {
  const [tab, setTab] = useState<TabId>("protocol");
  const [exporting, setExporting] = useState(false);
  const pdfRef = useRef<HTMLDivElement>(null);
  const generated = useMemo(() => fmtGenerated(), []);
  const sym = plan.stats.currencySymbol;
  const suppliers = useMemo(
    () => new Set(plan.materials.map((m) => m.supplier)).size,
    [plan.materials],
  );

  async function handleExport() {
    if (!pdfRef.current || exporting) return;
    setExporting(true);
    try {
      await exportToPdf(pdfRef.current, plan.title);
    } finally {
      setExporting(false);
    }
  }

  return (
    <section className="plan is-visible">
      <header className="plan-hero">
        <div className="eyebrow-row">
          <span className="dot" />
          <span>Plan ready</span>
          <span className="sep">·</span>
          <span>{generated}</span>
        </div>
        <h2>
          <SciText html={plan.title} />
        </h2>
        <p className="blurb">
          <SciText html={plan.summary} />
        </p>
        <div className="plan-stats">
          <div className="stat">
            <span className="k">Budget</span>
            <span className="v">
              <small>{sym}</small>
              {fmtNumber(plan.stats.budgetTotal)}
            </span>
          </div>
          <div className="stat">
            <span className="k">Duration</span>
            <span className="v">
              {plan.stats.durationWeeks} <small>weeks</small>
            </span>
          </div>
          <div className="stat">
            <span className="k">Materials</span>
            <span className="v">
              {plan.stats.materialsCount} <small>SKUs</small>
            </span>
            <span className="delta">
              {suppliers} suppliers
            </span>
          </div>
          <div className="stat">
            <span className="k">Confidence</span>
            <span className="v">{plan.stats.confidence}</span>
          </div>
        </div>
        <nav className="tabs" role="tablist">
          {TABS.map((t) => (
            <button
              key={t.id}
              type="button"
              role="tab"
              aria-selected={tab === t.id}
              className={`tab ${tab === t.id ? "is-active" : ""}`}
              onClick={() => setTab(t.id)}
            >
              {t.label}
            </button>
          ))}
        </nav>
      </header>

      {operationalPlan && operationalPlan.warnings.length ? (
        <div className="op-banner op-banner-warn">
          <div className="op-banner-title">Operational plan warnings</div>
          <ul>
            {operationalPlan.warnings.map((w) => (
              <li key={w}>{w}</li>
            ))}
          </ul>
        </div>
      ) : null}
      {operationalPlan && operationalPlan.assumptions.length ? (
        <div className="op-banner op-banner-info">
          <div className="op-banner-title">Plan assumptions</div>
          <ul>
            {operationalPlan.assumptions.map((a) => (
              <li key={a}>{a}</li>
            ))}
          </ul>
        </div>
      ) : null}

      <div className={`tab-panel ${tab === "protocol" ? "is-active" : ""}`} role="tabpanel">
        {tab === "protocol" ? <ProtocolPanel plan={plan} /> : null}
      </div>
      <div className={`tab-panel ${tab === "materials" ? "is-active" : ""}`} role="tabpanel">
        {tab === "materials" ? <MaterialsPanel plan={plan} /> : null}
      </div>
      <div className={`tab-panel ${tab === "budget" ? "is-active" : ""}`} role="tabpanel">
        {tab === "budget" ? <BudgetPanel plan={plan} /> : null}
      </div>
      <div className={`tab-panel ${tab === "timeline" ? "is-active" : ""}`} role="tabpanel">
        {tab === "timeline" ? <TimelinePanel plan={plan} /> : null}
      </div>
      <div className={`tab-panel ${tab === "dependencies" ? "is-active" : ""}`} role="tabpanel">
        {tab === "dependencies" ? <DependenciesPanel plan={plan} /> : null}
      </div>
      <div className={`tab-panel ${tab === "validation" ? "is-active" : ""}`} role="tabpanel">
        {tab === "validation" ? <ValidationPanel plan={plan} /> : null}
      </div>
      <div className={`tab-panel ${tab === "funding" ? "is-active" : ""}`} role="tabpanel">
        {tab === "funding" ? <FundingPanel plan={plan} /> : null}
      </div>

      {/* Off-screen PDF document — html2pdf renders this into a downloadable PDF */}
      <div className="pdf-shell" aria-hidden="true">
        <div className="pdf-doc" ref={pdfRef}>
          <div className="pdf-hero pdf-avoid-break">
          <div className="pdf-eyebrow">Plan ready · {generated}</div>
          <h1 className="pdf-title">
            <SciText html={plan.title} />
          </h1>
          <p className="pdf-blurb">
            <SciText html={plan.summary} />
          </p>
          <div className="pdf-stats">
            <div>
              <div className="k">Budget</div>
              <div className="v">{sym}{fmtNumber(plan.stats.budgetTotal)}</div>
            </div>
            <div>
              <div className="k">Duration</div>
              <div className="v">{plan.stats.durationWeeks} weeks</div>
            </div>
            <div>
              <div className="k">Materials</div>
              <div className="v">{plan.stats.materialsCount} SKUs</div>
            </div>
            <div>
              <div className="k">Confidence</div>
              <div className="v">{plan.stats.confidence}</div>
            </div>
          </div>
        </div>
        <div className="pdf-section pdf-avoid-break">
          <h3 className="pdf-h">Protocol</h3>
          <ProtocolPanel plan={plan} />
        </div>
        <div className="pdf-section pdf-avoid-break">
          <h3 className="pdf-h">Materials</h3>
          <MaterialsPanel plan={plan} />
        </div>
        <div className="pdf-section pdf-avoid-break">
          <h3 className="pdf-h">Budget</h3>
          <BudgetPanel plan={plan} />
        </div>
        <div className="pdf-section pdf-avoid-break">
          <h3 className="pdf-h">Timeline</h3>
          <TimelinePanel plan={plan} />
        </div>
        <div className="pdf-section pdf-avoid-break">
          <h3 className="pdf-h">Dependencies</h3>
          <DependenciesPanel plan={plan} />
        </div>
        <div className="pdf-section pdf-avoid-break">
          <h3 className="pdf-h">Validation</h3>
          <ValidationPanel plan={plan} />
        </div>
          <div className="pdf-section pdf-avoid-break">
            <h3 className="pdf-h">Funding</h3>
            <FundingPanel plan={plan} />
          </div>
        </div>
      </div>

      <div className="plan-actions">
        <span className="spacer" />
        <button
          className="btn ghost"
          type="button"
          onClick={handleExport}
          disabled={exporting}
        >
          {exporting ? "Preparing PDF…" : "Export to PDF"}
        </button>
      </div>
    </section>
  );
}
