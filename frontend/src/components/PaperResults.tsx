import { ExternalLink } from "lucide-react";
import type { Paper } from "../types";

type PaperResultsProps = {
  papers: Paper[];
};

function scoreLabel(score: number) {
  return `${Math.round(score * 100)}% match`;
}

export function PaperResults({ papers }: PaperResultsProps) {
  return (
    <section>
      <div className="mb-3 flex items-end justify-between gap-3">
        <div>
          <h2 className="text-lg font-semibold text-slate-950">Papers found</h2>
          <p className="text-sm text-slate-600">
            {papers.length} OpenAlex result{papers.length === 1 ? "" : "s"}
          </p>
        </div>
      </div>

      {papers.length ? (
        <div className="grid gap-3">
          {papers.map((paper) => (
            <article
              key={paper.id}
              className="rounded-lg border border-slate-200 bg-white p-4 shadow-soft"
            >
              <div className="min-w-0">
                <div className="flex flex-col gap-3 sm:flex-row sm:items-start sm:justify-between">
                  <div className="min-w-0">
                    <h3 className="break-words text-base font-semibold leading-6 text-slate-950">
                      {paper.title}
                    </h3>
                    <p className="mt-1 text-sm text-slate-600">
                      {paper.source}
                      {paper.year ? ` · ${paper.year}` : ""}
                      {paper.citation_count ? ` · ${paper.citation_count} citations` : ""}
                    </p>
                  </div>
                  <div className="flex shrink-0 items-center gap-2 sm:flex-col sm:items-end">
                    <span className="w-fit rounded-md bg-slate-100 px-2.5 py-1 text-xs font-semibold text-slate-700">
                      {scoreLabel(paper.match_score)}
                    </span>
                    {paper.url ? (
                      <a
                        href={paper.url}
                        target="_blank"
                        rel="noreferrer"
                        className="inline-flex items-center gap-1 rounded-md border border-slate-300 px-2.5 py-1 text-xs font-semibold text-teal-700 transition hover:border-teal-700 hover:text-teal-900"
                      >
                        Paper
                        <ExternalLink className="h-3.5 w-3.5" aria-hidden="true" />
                      </a>
                    ) : null}
                  </div>
                </div>
              </div>
            </article>
          ))}
        </div>
      ) : (
        <div className="rounded-lg border border-dashed border-slate-300 bg-white p-5 text-sm text-slate-600">
          No papers returned.
        </div>
      )}
    </section>
  );
}
