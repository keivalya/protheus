import { AlertTriangle, CheckCircle2, HelpCircle } from "lucide-react";
import type { NoveltySignal, QCResult } from "../types";

type QCSignalCardProps = {
  qc: QCResult;
};

const signalStyles: Record<
  NoveltySignal,
  {
    className: string;
    icon: typeof CheckCircle2;
  }
> = {
  "exact match found": {
    className: "border-red-200 bg-red-50 text-red-900",
    icon: AlertTriangle,
  },
  "similar work exists": {
    className: "border-amber-200 bg-amber-50 text-amber-950",
    icon: HelpCircle,
  },
  "not found": {
    className: "border-teal-200 bg-teal-50 text-teal-950",
    icon: CheckCircle2,
  },
};

export function QCSignalCard({ qc }: QCSignalCardProps) {
  const style = signalStyles[qc.novelty_signal];
  const Icon = style.icon;
  const confidencePercent = Math.round(qc.confidence * 100);

  return (
    <section className="rounded-lg border border-slate-200 bg-white p-5 shadow-soft">
      <div className="flex flex-col gap-4 sm:flex-row sm:items-start sm:justify-between">
        <div>
          <h2 className="text-lg font-semibold text-slate-950">Literature QC</h2>
          <div
            className={`mt-3 inline-flex items-center gap-2 rounded-md border px-3 py-2 text-sm font-semibold ${style.className}`}
          >
            <Icon className="h-4 w-4" aria-hidden="true" />
            {qc.novelty_signal}
          </div>
        </div>
        <div className="min-w-44">
          <div className="flex items-center justify-between text-sm">
            <span className="font-medium text-slate-600">Confidence</span>
            <span className="font-semibold text-slate-950">{confidencePercent}%</span>
          </div>
          <div className="mt-2 h-2 overflow-hidden rounded-full bg-slate-200">
            <div
              className="h-full rounded-full bg-teal-700"
              style={{ width: `${confidencePercent}%` }}
            />
          </div>
        </div>
      </div>
    </section>
  );
}
