import { useMemo, useState } from "react";
import {
  AlertTriangle,
  Calendar,
  Clock,
  DollarSign,
  ExternalLink,
  ImageOff,
  Package,
  RefreshCw,
} from "lucide-react";
import type {
  BudgetBreakdownItem,
  MoneyRange,
  OperationalPlanResponse,
  SupplierCandidate,
  SupplyChainItem,
  TimelineTask,
} from "../types";

type OperationalPlanPageProps = {
  plan: OperationalPlanResponse | null;
  isLoading: boolean;
  error: string | null;
  onGenerate: () => void;
};

type PlanTab = "supply_chain" | "budget" | "timeline";

const tabs: { id: PlanTab; label: string }[] = [
  { id: "supply_chain", label: "Supply Chain" },
  { id: "budget", label: "Budget" },
  { id: "timeline", label: "Timeline" },
];

function buttonClass(active = false): string {
  return `inline-flex min-h-10 items-center justify-center rounded-md border px-3 py-2 text-sm font-semibold transition ${
    active
      ? "border-teal-700 bg-teal-50 text-teal-900"
      : "border-slate-300 bg-white text-slate-700 hover:border-teal-600"
  }`;
}

function money(value: number | null | undefined, currency = "USD"): string {
  if (typeof value !== "number") {
    return "missing";
  }
  return new Intl.NumberFormat("en-US", {
    style: "currency",
    currency,
    maximumFractionDigits: value >= 100 ? 0 : 2,
  }).format(value);
}

function moneyRange(range: MoneyRange | null | undefined): string {
  if (!range || typeof range.min !== "number" || typeof range.max !== "number") {
    return "Price not found";
  }
  if (range.min === range.max) {
    return money(range.min, range.currency);
  }
  return `${money(range.min, range.currency)} - ${money(range.max, range.currency)}`;
}

function categoryLabel(value: string): string {
  return value.replace(/_/g, " ");
}

function statusLabel(value: string): string {
  return value.replace(/_/g, " ");
}

function formatHours(value: number): string {
  if (!Number.isFinite(value)) {
    return "0 hr";
  }
  return `${Math.round(value * 10) / 10} hr`;
}

function primaryCandidate(item: SupplyChainItem): SupplierCandidate | null {
  return item.supplier_candidates[0] ?? null;
}

function SupplyChainCard({ item }: { item: SupplyChainItem }) {
  const candidate = primaryCandidate(item);
  const imageUrl = candidate?.image_url;
  return (
    <article className="grid gap-4 rounded-lg border border-slate-200 bg-white p-4 shadow-soft sm:grid-cols-[5rem_1fr]">
      <div className="flex h-20 w-20 items-center justify-center overflow-hidden rounded-md border border-slate-200 bg-slate-50">
        {imageUrl ? (
          <img
            src={imageUrl}
            alt=""
            className="h-full w-full object-contain p-2"
            loading="lazy"
            onError={(event) => {
              event.currentTarget.style.display = "none";
            }}
          />
        ) : (
          <ImageOff className="h-7 w-7 text-slate-400" aria-hidden="true" />
        )}
      </div>
      <div className="min-w-0">
        <div className="flex flex-col gap-2 sm:flex-row sm:items-start sm:justify-between">
          <div>
            <h4 className="text-base font-semibold text-slate-950">{item.item_name}</h4>
            <p className="mt-1 text-sm text-slate-600">{categoryLabel(item.category)}</p>
          </div>
          <span className="w-fit rounded-md border border-slate-200 bg-slate-50 px-2.5 py-1 text-xs font-semibold text-slate-700">
            {candidate ? statusLabel(candidate.confidence) : "low"} confidence
          </span>
        </div>

        <dl className="mt-4 grid gap-3 text-sm sm:grid-cols-2 lg:grid-cols-3">
          <div>
            <dt className="font-semibold text-slate-950">Vendor</dt>
            <dd className="mt-1 text-slate-700">{candidate?.vendor ?? "not resolved"}</dd>
          </div>
          <div>
            <dt className="font-semibold text-slate-950">Catalog number</dt>
            <dd className="mt-1 text-slate-700">{candidate?.catalog_number ?? "not found"}</dd>
          </div>
          <div>
            <dt className="font-semibold text-slate-950">Package size</dt>
            <dd className="mt-1 text-slate-700">{candidate?.package_size ?? "not found"}</dd>
          </div>
          <div>
            <dt className="font-semibold text-slate-950">Estimated price</dt>
            <dd className="mt-1 text-slate-700">
              {moneyRange(candidate?.estimated_price_range)}
            </dd>
          </div>
          <div>
            <dt className="font-semibold text-slate-950">Price status</dt>
            <dd className="mt-1 text-slate-700">
              {candidate ? statusLabel(candidate.price_status) : "price not found"}
            </dd>
          </div>
          <div>
            <dt className="font-semibold text-slate-950">Quantity</dt>
            <dd className="mt-1 text-slate-700">{item.quantity_needed}</dd>
          </div>
        </dl>

        {candidate?.product_url ? (
          <a
            href={candidate.product_url}
            target="_blank"
            rel="noreferrer"
            className="mt-4 inline-flex items-center gap-1 text-sm font-semibold text-teal-800 hover:text-teal-950"
          >
            Source link
            <ExternalLink className="h-3.5 w-3.5" aria-hidden="true" />
          </a>
        ) : null}
      </div>
    </article>
  );
}

function BudgetRow({ item }: { item: BudgetBreakdownItem }) {
  return (
    <div className="grid gap-2 border-b border-slate-100 py-3 text-sm last:border-b-0 sm:grid-cols-[1fr_auto_auto] sm:items-center">
      <div>
        <p className="font-semibold text-slate-950">{item.label}</p>
        <p className="mt-1 text-slate-600">
          {item.items_count} priced, {item.excluded_count} excluded
        </p>
      </div>
      <p className="font-semibold text-slate-900">{moneyRange({ min: item.min, max: item.max, currency: item.currency })}</p>
    </div>
  );
}

function TimelinePhase({ phase, tasks }: { phase: string; tasks: TimelineTask[] }) {
  return (
    <div className="rounded-lg border border-slate-200 bg-white p-4">
      <div className="flex flex-col gap-1 sm:flex-row sm:items-center sm:justify-between">
        <h4 className="text-base font-semibold text-slate-950">{phase}</h4>
        <p className="text-sm text-slate-600">
          {tasks[0]?.scheduled_start} - {tasks[tasks.length - 1]?.scheduled_end}
        </p>
      </div>
      <div className="mt-4 grid gap-3">
        {tasks.map((task) => (
          <div key={`${task.phase}-${task.task_name}-${task.scheduled_start}`} className="grid gap-2">
            <div className="flex flex-col gap-1 text-sm sm:flex-row sm:items-center sm:justify-between">
              <p className="font-semibold text-slate-900">{task.task_name}</p>
              <p className="text-slate-600">
                {task.scheduled_start} - {task.scheduled_end}
              </p>
            </div>
            <div className="h-2 overflow-hidden rounded-full bg-slate-100">
              <div
                className={`h-full rounded-full ${
                  task.passive_wait_hours > 0 ? "bg-amber-500" : "bg-teal-700"
                }`}
                style={{ width: "100%" }}
              />
            </div>
            <p className="text-xs leading-5 text-slate-600">
              {task.hands_on_hours} hands-on hr
              {task.passive_wait_hours ? `, ${task.passive_wait_hours} passive hr` : ""}. Depends on{" "}
              {task.dependencies.join(", ")}.
            </p>
          </div>
        ))}
      </div>
    </div>
  );
}

export function OperationalPlanPage({
  plan,
  isLoading,
  error,
  onGenerate,
}: OperationalPlanPageProps) {
  const [activeTab, setActiveTab] = useState<PlanTab>("supply_chain");
  const [showAllMaterials, setShowAllMaterials] = useState(false);

  const missingPriceItems = useMemo(
    () =>
      plan?.supply_chain_items.filter((item) =>
        item.budget_status === "missing_price" || item.budget_status === "missing_price_and_quantity",
      ) ?? [],
    [plan],
  );
  const missingQuantityItems = useMemo(
    () =>
      plan?.supply_chain_items.filter((item) =>
        item.budget_status === "missing_quantity" || item.budget_status === "missing_price_and_quantity",
      ) ?? [],
    [plan],
  );
  const phases = useMemo(() => {
    const grouped = new Map<string, TimelineTask[]>();
    for (const task of plan?.timeline ?? []) {
      grouped.set(task.phase, [...(grouped.get(task.phase) ?? []), task]);
    }
    return Array.from(grouped.entries()).map(([phase, tasks]) => ({ phase, tasks }));
  }, [plan]);
  const visibleSupplyItems = useMemo(() => {
    const items = plan?.supply_chain_items ?? [];
    return showAllMaterials ? items : items.slice(0, 8);
  }, [plan, showAllMaterials]);
  const timelineSummary = useMemo(() => {
    const tasks = plan?.timeline ?? [];
    const handsOn = tasks.reduce((sum, task) => sum + (task.effective_hands_on_hours || task.hands_on_hours || 0), 0);
    const passive = tasks.reduce((sum, task) => sum + (task.passive_wait_hours || 0), 0);
    const longestPassive = tasks.reduce<TimelineTask | null>(
      (current, task) =>
        !current || (task.passive_wait_hours || 0) > (current.passive_wait_hours || 0)
          ? task
          : current,
      null,
    );
    return {
      planWindow: tasks.length
        ? `${tasks[0].scheduled_start} - ${tasks[tasks.length - 1].scheduled_end}`
        : "missing",
      handsOn,
      passive,
      criticalPath: longestPassive?.task_name ?? tasks[tasks.length - 1]?.task_name ?? "missing",
    };
  }, [plan]);

  return (
    <section className="rounded-lg border border-slate-200 bg-white p-5 shadow-soft">
      <div className="flex flex-col gap-4 lg:flex-row lg:items-start lg:justify-between">
        <div>
          <p className="text-sm font-semibold uppercase tracking-wide text-teal-800">
            Operational plan
          </p>
          <h3 className="mt-1 text-xl font-semibold text-slate-950">
            Supply chain, budget and timeline
          </h3>
        </div>
        <button
          type="button"
          onClick={onGenerate}
          disabled={isLoading}
          className="inline-flex min-h-10 items-center justify-center gap-2 rounded-md border border-slate-300 bg-white px-3 py-2 text-sm font-semibold text-slate-800 transition hover:border-teal-600 disabled:cursor-not-allowed disabled:opacity-60"
        >
          <RefreshCw className={`h-4 w-4 ${isLoading ? "animate-spin" : ""}`} aria-hidden="true" />
          {plan ? "Regenerate plan" : "Generate plan"}
        </button>
      </div>

      {error ? (
        <p className="mt-4 rounded-md border border-red-200 bg-red-50 p-3 text-sm text-red-900">
          {error}
        </p>
      ) : null}

      {isLoading && !plan ? (
        <div className="mt-4 rounded-md border border-slate-200 bg-slate-50 p-4 text-sm font-medium text-slate-700">
          Building operational plan...
        </div>
      ) : null}

      {plan ? (
        <>
          {plan.warnings.length ? (
            <div className="mt-4 grid gap-2">
              {plan.warnings.map((warning) => (
                <p
                  key={warning}
                  className="flex gap-2 rounded-md border border-amber-200 bg-amber-50 p-3 text-sm text-amber-950"
                >
                  <AlertTriangle className="mt-0.5 h-4 w-4 shrink-0" aria-hidden="true" />
                  <span>{warning}</span>
                </p>
              ))}
            </div>
          ) : null}

          <div className="mt-5 grid gap-3 lg:grid-cols-4">
            <div className="rounded-md border border-teal-200 bg-teal-50 p-3">
              <p className="text-sm font-semibold text-teal-950">Estimated budget</p>
              <p className="mt-1 text-lg font-semibold text-teal-950">
                {moneyRange(plan.budget_summary.estimated_total_range)}
              </p>
            </div>
            <div className="rounded-md border border-slate-200 bg-slate-50 p-3">
              <p className="text-sm font-semibold text-slate-950">Materials priced</p>
              <p className="mt-1 text-lg font-semibold text-slate-950">
                {plan.budget_summary.priced_items} / {plan.budget_summary.total_items}
              </p>
            </div>
            <div className="rounded-md border border-slate-200 bg-slate-50 p-3">
              <p className="text-sm font-semibold text-slate-950">Plan window</p>
              <p className="mt-1 text-sm text-slate-700">{timelineSummary.planWindow}</p>
            </div>
            <div className="rounded-md border border-slate-200 bg-slate-50 p-3">
              <p className="text-sm font-semibold text-slate-950">Critical dependency</p>
              <p className="mt-1 text-sm text-slate-700">{timelineSummary.criticalPath}</p>
            </div>
          </div>

          <div className="mt-5 flex flex-wrap gap-2">
            {tabs.map((tab) => (
              <button
                key={tab.id}
                type="button"
                onClick={() => setActiveTab(tab.id)}
                className={buttonClass(activeTab === tab.id)}
              >
                {tab.label}
              </button>
            ))}
          </div>

          {activeTab === "supply_chain" ? (
            <div className="mt-5 grid gap-4">
              <div className="grid gap-3 sm:grid-cols-3">
                <div className="rounded-md border border-slate-200 bg-slate-50 p-3">
                  <div className="flex items-center gap-2 text-sm font-semibold text-slate-950">
                    <Package className="h-4 w-4 text-teal-700" aria-hidden="true" />
                    Items
                  </div>
                  <p className="mt-1 text-2xl font-semibold text-slate-950">
                    {plan.supply_chain_items.length}
                  </p>
                </div>
                <div className="rounded-md border border-slate-200 bg-slate-50 p-3">
                  <p className="text-sm font-semibold text-slate-950">Missing prices</p>
                  <p className="mt-1 text-2xl font-semibold text-slate-950">
                    {plan.budget_summary.missing_prices}
                  </p>
                </div>
                <div className="rounded-md border border-slate-200 bg-slate-50 p-3">
                  <p className="text-sm font-semibold text-slate-950">Quantity assumptions</p>
                  <p className="mt-1 text-2xl font-semibold text-slate-950">
                    {plan.budget_summary.excluded_due_to_missing_quantity}
                  </p>
                </div>
              </div>
              {visibleSupplyItems.map((item) => (
                <SupplyChainCard key={`${item.item_name}-${item.category}`} item={item} />
              ))}
              {plan.supply_chain_items.length > visibleSupplyItems.length ? (
                <button
                  type="button"
                  className={buttonClass(false)}
                  onClick={() => setShowAllMaterials(true)}
                >
                  Show all materials
                </button>
              ) : null}
            </div>
          ) : null}

          {activeTab === "budget" ? (
            <div className="mt-5 grid gap-5">
              <div className="grid gap-3 lg:grid-cols-[1fr_1fr_1fr]">
                <div className="rounded-md border border-teal-200 bg-teal-50 p-4">
                  <div className="flex items-center gap-2 text-sm font-semibold text-teal-950">
                    <DollarSign className="h-4 w-4" aria-hidden="true" />
                    Estimated budget
                  </div>
                  <p className="mt-2 text-2xl font-semibold text-teal-950">
                    {moneyRange(plan.budget_summary.estimated_total_range)}
                  </p>
                </div>
                <div className="rounded-md border border-slate-200 bg-slate-50 p-4">
                  <p className="text-sm font-semibold text-slate-950">Priced items</p>
                  <p className="mt-2 text-2xl font-semibold text-slate-950">
                    {plan.budget_summary.priced_items} / {plan.budget_summary.total_items}
                  </p>
                </div>
                <div className="rounded-md border border-slate-200 bg-slate-50 p-4">
                  <p className="text-sm font-semibold text-slate-950">Confidence</p>
                  <p className="mt-2 text-2xl font-semibold capitalize text-slate-950">
                    {plan.budget_summary.confidence}
                  </p>
                </div>
              </div>

              <div className="rounded-lg border border-slate-200 bg-white p-4">
                <h4 className="text-base font-semibold text-slate-950">Category breakdown</h4>
                <div className="mt-2">
                  {plan.budget_breakdown.map((item) => (
                    <BudgetRow key={item.category} item={item} />
                  ))}
                </div>
              </div>

              <div className="grid gap-4 lg:grid-cols-2">
                <div className="rounded-lg border border-slate-200 bg-white p-4">
                  <h4 className="text-base font-semibold text-slate-950">Missing price items</h4>
                  <div className="mt-3 grid gap-2 text-sm text-slate-700">
                    {missingPriceItems.length ? (
                      missingPriceItems.map((item) => <p key={item.item_name}>{item.item_name}</p>)
                    ) : (
                      <p>None</p>
                    )}
                  </div>
                </div>
                <div className="rounded-lg border border-slate-200 bg-white p-4">
                  <h4 className="text-base font-semibold text-slate-950">Quantity assumptions</h4>
                  <div className="mt-3 grid gap-2 text-sm text-slate-700">
                    {missingQuantityItems.length ? (
                      missingQuantityItems.map((item) => <p key={item.item_name}>{item.item_name}</p>)
                    ) : (
                      <p>None</p>
                    )}
                  </div>
                </div>
              </div>
            </div>
          ) : null}

          {activeTab === "timeline" ? (
            <div className="mt-5 grid gap-5">
              <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-4">
                <div className="rounded-md border border-slate-200 bg-slate-50 p-3">
                  <div className="flex items-center gap-2 text-sm font-semibold text-slate-950">
                    <Calendar className="h-4 w-4 text-teal-700" aria-hidden="true" />
                    Plan window
                  </div>
                  <p className="mt-1 text-sm text-slate-700">{timelineSummary.planWindow}</p>
                </div>
                <div className="rounded-md border border-slate-200 bg-slate-50 p-3">
                  <div className="flex items-center gap-2 text-sm font-semibold text-slate-950">
                    <Clock className="h-4 w-4 text-teal-700" aria-hidden="true" />
                    Hands-on effort
                  </div>
                  <p className="mt-1 text-sm text-slate-700">
                    {formatHours(timelineSummary.handsOn)}
                  </p>
                </div>
                <div className="rounded-md border border-slate-200 bg-slate-50 p-3">
                  <p className="text-sm font-semibold text-slate-950">Passive wait</p>
                  <p className="mt-1 text-sm text-slate-700">
                    {formatHours(timelineSummary.passive)}
                  </p>
                </div>
                <div className="rounded-md border border-slate-200 bg-slate-50 p-3">
                  <p className="text-sm font-semibold text-slate-950">Critical dependency</p>
                  <p className="mt-1 text-sm text-slate-700">
                    {timelineSummary.criticalPath}
                  </p>
                </div>
              </div>

              <div className="grid gap-4">
                {phases.map(({ phase, tasks }) => (
                  <TimelinePhase key={phase} phase={phase} tasks={tasks} />
                ))}
              </div>

              <div className="rounded-lg border border-slate-200 bg-white p-4">
                <h4 className="text-base font-semibold text-slate-950">Assumptions</h4>
                <div className="mt-3 grid gap-2 text-sm text-slate-700">
                  {plan.assumptions.map((assumption) => (
                    <p key={assumption}>{assumption}</p>
                  ))}
                </div>
              </div>
            </div>
          ) : null}
        </>
      ) : null}
    </section>
  );
}
