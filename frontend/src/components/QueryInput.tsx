import { Loader2, Search } from "lucide-react";

type QueryInputProps = {
  query: string;
  examples: string[];
  isLoading: boolean;
  onQueryChange: (query: string) => void;
  onExampleSelect: (query: string) => void;
  onSubmit: () => void;
};

export function QueryInput({
  query,
  examples,
  isLoading,
  onQueryChange,
  onExampleSelect,
  onSubmit,
}: QueryInputProps) {
  const canSubmit = query.trim().length >= 3 && !isLoading;

  return (
    <section className="rounded-lg border border-slate-200 bg-white p-5 shadow-soft">
      <div className="flex flex-col gap-4">
        <div>
          <h1 className="text-2xl font-semibold tracking-normal text-slate-950">
            AI Scientist Lite
          </h1>
        </div>

        <label className="text-sm font-medium text-slate-800" htmlFor="hypothesis">
          Scientific hypothesis
        </label>
        <textarea
          id="hypothesis"
          value={query}
          onChange={(event) => onQueryChange(event.target.value)}
          className="min-h-36 w-full resize-y rounded-md border border-slate-300 bg-slate-50 px-4 py-3 text-base leading-7 text-slate-950 outline-none transition focus:border-teal-600 focus:bg-white focus:ring-4 focus:ring-teal-600/10"
          placeholder="Replacing sucrose with trehalose as a cryoprotectant..."
        />

        <div className="flex flex-col gap-3 lg:flex-row lg:items-center lg:justify-between">
          <div className="flex flex-wrap gap-2">
            {examples.map((example, index) => (
              <button
                key={example}
                type="button"
                onClick={() => onExampleSelect(example)}
                className="rounded-md border border-slate-300 bg-white px-3 py-2 text-sm font-medium text-slate-700 transition hover:border-teal-600 hover:text-teal-700 focus:outline-none focus:ring-4 focus:ring-teal-600/10"
              >
                Example {index + 1}
              </button>
            ))}
          </div>

          <button
            type="button"
            onClick={onSubmit}
            disabled={!canSubmit}
            className="inline-flex min-h-11 items-center justify-center gap-2 rounded-md bg-teal-700 px-5 py-3 text-sm font-semibold text-white transition hover:bg-teal-800 focus:outline-none focus:ring-4 focus:ring-teal-700/20 disabled:cursor-not-allowed disabled:bg-slate-300"
          >
            {isLoading ? (
              <Loader2 className="h-4 w-4 animate-spin" aria-hidden="true" />
            ) : (
              <Search className="h-4 w-4" aria-hidden="true" />
            )}
            Run Literature QC
          </button>
        </div>
      </div>
    </section>
  );
}
