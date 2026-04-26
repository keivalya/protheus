import type { StructuredHypothesis } from "../types";

type StructuredHypothesisCardProps = {
  hypothesis: StructuredHypothesis;
};

const fields: Array<[keyof StructuredHypothesis, string]> = [
  ["domain", "Domain"],
  ["model_system", "Model system"],
  ["intervention", "Intervention"],
  ["control", "Control"],
  ["outcome", "Outcome"],
  ["effect_size", "Effect size"],
  ["assay", "Assay"],
  ["mechanism", "Mechanism"],
];

export function StructuredHypothesisCard({ hypothesis }: StructuredHypothesisCardProps) {
  return (
    <section className="rounded-lg border border-slate-200 bg-white p-5 shadow-soft">
      <h2 className="text-lg font-semibold text-slate-950">Structured hypothesis</h2>
      <dl className="mt-4 grid gap-3 sm:grid-cols-2">
        {fields.map(([key, label]) => {
          const value = hypothesis[key];
          return (
            <div key={key} className="rounded-md border border-slate-200 bg-slate-50 p-3">
              <dt className="text-xs font-semibold uppercase text-slate-500">{label}</dt>
              <dd className="mt-1 break-words text-sm font-medium text-slate-900">
                {typeof value === "string" && value ? value : "Unknown"}
              </dd>
            </div>
          );
        })}
      </dl>

      <div className="mt-4">
        <h3 className="text-xs font-semibold uppercase text-slate-500">Keywords</h3>
        <div className="mt-2 flex flex-wrap gap-2">
          {hypothesis.keywords.length ? (
            hypothesis.keywords.map((keyword) => (
              <span
                key={keyword}
                className="rounded-md border border-slate-200 bg-emerald-50 px-2.5 py-1 text-xs font-medium text-emerald-900"
              >
                {keyword}
              </span>
            ))
          ) : (
            <span className="text-sm text-slate-500">No keywords extracted.</span>
          )}
        </div>
      </div>
    </section>
  );
}

