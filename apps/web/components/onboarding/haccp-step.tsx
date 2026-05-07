"use client";

import { Button } from "@/components/ui/button";

const SEED_TEMPLATES = [
  "Opening Check (daily)",
  "Closing Check (daily)",
  "Temperature Log (per shift)",
  "Delivery Check (on delivery)",
  "Cleaning Log (daily)",
  "Weekly Deep Clean (weekly)",
];

interface Props {
  onComplete: () => void;
  onSkip: () => void;
}

export function HACCPStep({ onComplete, onSkip }: Props) {
  return (
    <div className="space-y-4">
      <div>
        <h2 className="text-lg font-semibold">HACCP templates</h2>
        <p className="text-sm text-muted-foreground mt-1">
          We&apos;ve already set up six Irish food-safety templates for you. They
          will appear under the HACCP tab and can be customised at any time.
        </p>
      </div>

      <div className="rounded-md border bg-muted/30 p-4">
        <ul className="space-y-1.5 text-sm">
          {SEED_TEMPLATES.map((t) => (
            <li key={t} className="flex items-start gap-2">
              <span className="text-foreground/60">·</span>
              <span>{t}</span>
            </li>
          ))}
        </ul>
      </div>

      <p className="text-xs text-muted-foreground">
        Each template is a starting point. You can edit items, change frequencies,
        or add your own templates from the HACCP page after onboarding.
      </p>

      <div className="flex gap-2 pt-2">
        <Button variant="outline" className="flex-1" onClick={onSkip}>
          Customise later
        </Button>
        <Button className="flex-1" onClick={onComplete}>
          Use Irish defaults
        </Button>
      </div>
    </div>
  );
}
