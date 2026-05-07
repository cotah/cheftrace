"use client";

const STEP_LABELS = ["Restaurant", "Catalogue", "HACCP", "Orders"];

export function ProgressIndicator({
  current,
  total,
}: {
  current: number;
  total: number;
}) {
  return (
    <div className="space-y-2">
      <p className="text-xs text-muted-foreground">
        Step {current} of {total} — {STEP_LABELS[current - 1]}
      </p>
      <div className="flex gap-1">
        {Array.from({ length: total }).map((_, i) => {
          const stepNum = i + 1;
          const isDone = stepNum < current;
          const isCurrent = stepNum === current;
          return (
            <div
              key={stepNum}
              className={`h-1.5 flex-1 rounded-full transition-colors ${
                isDone
                  ? "bg-foreground"
                  : isCurrent
                    ? "bg-foreground/70"
                    : "bg-muted"
              }`}
            />
          );
        })}
      </div>
    </div>
  );
}
