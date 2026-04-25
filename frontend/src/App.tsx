import { useCallback, useEffect, useMemo, useState } from "react";
import { Beaker, CheckCircle2, Circle, Loader2 } from "lucide-react";
import { runLiteratureQC } from "./api";
import { PaperResults } from "./components/PaperResults";
import { ProtocolDraftPage } from "./components/ProtocolDraftPage";
import { ProtocolResults } from "./components/ProtocolResults";
import { QCSignalCard } from "./components/QCSignalCard";
import { QueryInput } from "./components/QueryInput";
import { StructuredHypothesisCard } from "./components/StructuredHypothesisCard";
import type { LiteratureQCResponse } from "./types";

const examples = [
  "Replacing sucrose with trehalose as a cryoprotectant in the freezing medium will increase post-thaw viability of HeLa cells by at least 15 percentage points compared to the standard DMSO protocol.",
  "A paper-based electrochemical biosensor functionalized with anti-CRP antibodies will detect C-reactive protein in whole blood below 0.5 mg/L within 10 minutes.",
  "Supplementing C57BL/6 mice with Lactobacillus rhamnosus GG for 4 weeks will reduce intestinal permeability by at least 30 percent compared to controls.",
];

const loadingSteps = [
  "Structuring hypothesis",
  "Searching papers",
  "Searching protocols",
  "Running literature QC",
];

export default function App() {
  const [query, setQuery] = useState(examples[0]);
  const [result, setResult] = useState<LiteratureQCResponse | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [isLoading, setIsLoading] = useState(false);
  const [loadingStep, setLoadingStep] = useState<number | null>(null);
  const [selectedProtocolIds, setSelectedProtocolIds] = useState<Set<string>>(() => new Set());

  useEffect(() => {
    if (!isLoading) {
      return undefined;
    }

    setLoadingStep(0);
    const timers = [700, 1500, 2300].map((delay, index) =>
      window.setTimeout(() => setLoadingStep(index + 1), delay),
    );

    return () => {
      timers.forEach((timer) => window.clearTimeout(timer));
    };
  }, [isLoading]);

  const handleRun = useCallback(async () => {
    const trimmedQuery = query.trim();
    if (trimmedQuery.length < 3 || isLoading) {
      return;
    }

    setIsLoading(true);
    setError(null);
    setResult(null);
    setSelectedProtocolIds(new Set());

    try {
      const response = await runLiteratureQC(trimmedQuery);
      setResult(response);
    } catch (requestError) {
      setError(
        requestError instanceof Error
          ? requestError.message
          : "The literature QC request failed.",
      );
    } finally {
      setIsLoading(false);
      setLoadingStep(null);
    }
  }, [isLoading, query]);

  const toggleProtocol = useCallback((id: string) => {
    setSelectedProtocolIds((current) => {
      const next = new Set(current);
      if (next.has(id)) {
        next.delete(id);
      } else {
        next.add(id);
      }
      return next;
    });
  }, []);

  const loadingStatus = useMemo(() => {
    if (!isLoading || loadingStep === null) {
      return null;
    }
    return loadingSteps.map((step, index) => ({
      label: step,
      state: index < loadingStep ? "done" : index === loadingStep ? "active" : "pending",
    }));
  }, [isLoading, loadingStep]);

  const selectedProtocols = useMemo(
    () => result?.protocols.filter((protocol) => selectedProtocolIds.has(protocol.id)) ?? [],
    [result, selectedProtocolIds],
  );

  return (
    <main className="min-h-screen bg-slate-50 px-4 py-6 sm:px-6 lg:px-8">
      <div className="mx-auto flex max-w-6xl flex-col gap-6">
        <QueryInput
          query={query}
          examples={examples}
          isLoading={isLoading}
          onQueryChange={setQuery}
          onExampleSelect={setQuery}
          onSubmit={handleRun}
        />

        {loadingStatus ? (
          <section className="rounded-lg border border-slate-200 bg-white p-5 shadow-soft">
            <div className="mb-4 flex items-center gap-2 text-sm font-semibold text-slate-900">
              <Beaker className="h-4 w-4 text-teal-700" aria-hidden="true" />
              Literature QC pipeline
            </div>
            <div className="grid gap-3 sm:grid-cols-4">
              {loadingStatus.map((step) => {
                const Icon =
                  step.state === "done"
                    ? CheckCircle2
                    : step.state === "active"
                      ? Loader2
                      : Circle;
                return (
                  <div
                    key={step.label}
                    className="flex min-h-14 items-center gap-2 rounded-md border border-slate-200 bg-slate-50 px-3 py-2 text-sm font-medium text-slate-700"
                  >
                    <Icon
                      className={`h-4 w-4 ${
                        step.state === "active"
                          ? "animate-spin text-teal-700"
                          : step.state === "done"
                            ? "text-teal-700"
                            : "text-slate-400"
                      }`}
                      aria-hidden="true"
                    />
                    <span>{step.label}</span>
                  </div>
                );
              })}
            </div>
          </section>
        ) : null}

        {error ? (
          <section className="rounded-lg border border-red-200 bg-red-50 p-4 text-sm text-red-900">
            {error}
          </section>
        ) : null}

        {result?.warnings?.length ? (
          <section className="rounded-lg border border-amber-200 bg-amber-50 p-4 text-sm text-amber-950">
            {result.warnings.join(" ")}
          </section>
        ) : null}

        {result ? (
          <>
            <div className="grid gap-6 lg:grid-cols-[1.1fr_0.9fr]">
              <StructuredHypothesisCard hypothesis={result.structured_hypothesis} />
              <QCSignalCard qc={result.qc} />
            </div>

            <div className="grid gap-6 lg:grid-cols-2">
              <PaperResults papers={result.papers} />
              <ProtocolResults
                protocols={result.protocols}
                selectedIds={selectedProtocolIds}
                onToggle={toggleProtocol}
              />
            </div>

            {selectedProtocols.length ? (
              <ProtocolDraftPage
                originalQuery={result.query}
                structuredHypothesis={result.structured_hypothesis}
                selectedProtocols={selectedProtocols}
              />
            ) : null}
          </>
        ) : null}
      </div>
    </main>
  );
}
