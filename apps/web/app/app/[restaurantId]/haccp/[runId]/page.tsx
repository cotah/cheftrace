"use client";

import { use, useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useRouter } from "next/navigation";
import { useToken } from "@/hooks/use-token";
import { haccpApi } from "@/lib/api/resources";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import type {
  EquipmentSnapshot,
  HACCPAnswer,
  HACCPItem,
} from "@/lib/api/types";

const SKIP_REASONS = [
  { value: "equipment_in_defrost", label: "Equipment in defrost cycle" },
  { value: "under_maintenance", label: "Under maintenance" },
  { value: "equipment_newly_added", label: "Equipment newly added" },
  { value: "equipment_temporarily_offline", label: "Temporarily offline" },
  { value: "other", label: "Other" },
];

const NO_SKIP = "__none__";

function YesNoInput({
  value,
  onChange,
}: {
  value: boolean | null;
  onChange: (v: boolean) => void;
}) {
  return (
    <div className="flex gap-2">
      <Button
        size="sm"
        variant={value === true ? "default" : "outline"}
        onClick={() => onChange(true)}
      >
        Yes
      </Button>
      <Button
        size="sm"
        variant={value === false ? "destructive" : "outline"}
        onClick={() => onChange(false)}
      >
        No
      </Button>
    </div>
  );
}

function MultiSelectInput({
  options,
  value,
  onChange,
  minSelections,
}: {
  options: string[];
  value: string[];
  onChange: (v: string[]) => void;
  minSelections: number | null;
}) {
  const toggle = (opt: string) => {
    if (value.includes(opt)) {
      onChange(value.filter((v) => v !== opt));
    } else {
      onChange([...value, opt]);
    }
  };
  return (
    <div className="space-y-1">
      {options.map((opt) => (
        <label key={opt} className="flex items-center gap-2 text-sm cursor-pointer">
          <input
            type="checkbox"
            checked={value.includes(opt)}
            onChange={() => toggle(opt)}
          />
          {opt}
        </label>
      ))}
      {minSelections && value.length === 0 && (
        <p className="text-xs text-muted-foreground">
          Select at least {minSelections} area
        </p>
      )}
    </div>
  );
}

interface ItemState {
  answer_bool?: boolean | null;
  answer_numeric?: number | null;
  answer_text?: string;
  answer_options?: string[];
  skip_reason?: string;
  skip_reason_text?: string;
}

export default function HACCPRunPage({
  params,
}: {
  params: Promise<{ restaurantId: string; runId: string }>;
}) {
  const { restaurantId: rid, runId } = use(params);
  const token = useToken();
  const router = useRouter();
  const qc = useQueryClient();
  const [answers, setAnswers] = useState<Record<string, ItemState>>({});

  const { data: run, isLoading: runLoading, error: runError } = useQuery({
    queryKey: ["haccp-run", rid, runId],
    queryFn: () => haccpApi.getRun(rid, runId, token!),
    enabled: !!rid && !!runId && !!token,
  });

  const isDynamic =
    run?.equipment_snapshot_json !== null && run?.equipment_snapshot_json !== undefined;

  const { data: items = [] } = useQuery({
    queryKey: ["haccp-items", rid, run?.template_id],
    queryFn: () => haccpApi.listItems(rid, run!.template_id, token!),
    enabled: !!rid && !!token && !!run && !isDynamic,
  });

  const { data: existingAnswers = [] } = useQuery({
    queryKey: ["haccp-answers", rid, runId],
    queryFn: () => haccpApi.listAnswers(rid, runId, token!),
    enabled: !!rid && !!runId && !!token,
  });

  const submitMutation = useMutation({
    mutationFn: (data: Partial<HACCPAnswer>) =>
      haccpApi.submitAnswer(rid, runId, data, token!),
    onSuccess: () => {
      void qc.invalidateQueries({ queryKey: ["haccp-answers", rid, runId] });
    },
  });

  const completeMutation = useMutation({
    mutationFn: () => haccpApi.completeRun(rid, runId, token!),
    onSuccess: () => {
      void qc.invalidateQueries({ queryKey: ["haccp-all-runs", rid] });
      router.push(`/app/${rid}/haccp`);
    },
  });

  const equipment: EquipmentSnapshot[] = run?.equipment_snapshot_json ?? [];

  const answeredIds = new Set(
    existingAnswers.map((a) => a.item_template_id ?? a.equipment_id ?? ""),
  );

  const updateAnswer = (key: string, update: Partial<ItemState>) => {
    setAnswers((prev) => ({
      ...prev,
      [key]: { ...prev[key], ...update },
    }));
  };

  const submitItemAnswer = (
    key: string,
    itemTemplateId: string | null,
    equipmentId: string | null,
  ) => {
    const state = answers[key] ?? {};
    const payload: Partial<HACCPAnswer> = {
      item_template_id: itemTemplateId ?? undefined,
      equipment_id: equipmentId ?? undefined,
      answer_bool: state.answer_bool ?? undefined,
      answer_numeric: state.answer_numeric ?? undefined,
      answer_text: state.answer_text ?? undefined,
      answer_options:
        state.answer_options && state.answer_options.length > 0
          ? state.answer_options
          : undefined,
      skip_reason: state.skip_reason ?? undefined,
      skip_reason_text: state.skip_reason_text ?? undefined,
    };
    submitMutation.mutate(payload);
  };

  if (runLoading) {
    return (
      <div className="space-y-4">
        <h1 className="text-2xl font-semibold">HACCP Run</h1>
        <p className="text-muted-foreground">Loading...</p>
      </div>
    );
  }

  if (runError || !run) {
    return (
      <div className="space-y-4">
        <h1 className="text-2xl font-semibold">HACCP Run</h1>
        <p className="text-sm text-destructive">
          {runError ? (runError as Error).message : "Run not found."}
        </p>
      </div>
    );
  }

  const isCompleted = run.status === "completed";

  return (
    <div className="max-w-2xl space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-semibold">
            {isDynamic ? "Temperature Log" : "HACCP Checklist"}
          </h1>
          <p className="text-sm text-muted-foreground mt-1">
            {run.run_date}
            {run.shift_number ? ` — Shift ${run.shift_number}` : ""}
          </p>
        </div>
        {!isCompleted && (
          <Button
            onClick={() => completeMutation.mutate()}
            disabled={completeMutation.isPending}
          >
            {completeMutation.isPending ? "Completing..." : "Complete run"}
          </Button>
        )}
      </div>

      {completeMutation.isError && (
        <p className="text-sm text-destructive">{completeMutation.error.message}</p>
      )}

      {isCompleted && (
        <Card className="border-green-200 bg-green-50">
          <CardContent className="py-4 text-center text-green-800">
            Run completed
          </CardContent>
        </Card>
      )}

      {isDynamic
        ? equipment.map((eq) => {
            const key = eq.id;
            const alreadyAnswered = answeredIds.has(eq.id);
            const state = answers[key] ?? {};
            const isSkipping = !!state.skip_reason;

            return (
              <Card key={key} className={alreadyAnswered ? "opacity-60" : ""}>
                <CardHeader className="pb-2">
                  <CardTitle className="text-base">{eq.name}</CardTitle>
                  {eq.min_temp !== null && eq.max_temp !== null && (
                    <p className="text-xs text-muted-foreground">
                      Range: {eq.min_temp}°C to {eq.max_temp}°C
                    </p>
                  )}
                </CardHeader>
                <CardContent className="space-y-3">
                  {alreadyAnswered ? (
                    <p className="text-sm text-green-700">Recorded</p>
                  ) : (
                    <>
                      {!isSkipping && (
                        <div className="space-y-1">
                          <Label>Temperature (°C)</Label>
                          <Input
                            type="number"
                            step="0.1"
                            value={state.answer_numeric ?? ""}
                            onChange={(e) =>
                              updateAnswer(key, {
                                answer_numeric: parseFloat(e.target.value),
                              })
                            }
                            placeholder="e.g. 3.5"
                          />
                        </div>
                      )}
                      <div className="space-y-1">
                        <Label>Skip reason (optional)</Label>
                        <Select
                          value={state.skip_reason ?? NO_SKIP}
                          onValueChange={(v) =>
                            updateAnswer(key, {
                              skip_reason: v === NO_SKIP ? undefined : v,
                              answer_numeric:
                                v !== NO_SKIP ? undefined : state.answer_numeric,
                            })
                          }
                        >
                          <SelectTrigger>
                            <SelectValue placeholder="— No skip —" />
                          </SelectTrigger>
                          <SelectContent>
                            <SelectItem value={NO_SKIP}>— No skip —</SelectItem>
                            {SKIP_REASONS.map((r) => (
                              <SelectItem key={r.value} value={r.value}>
                                {r.label}
                              </SelectItem>
                            ))}
                          </SelectContent>
                        </Select>
                      </div>
                      <Button
                        size="sm"
                        disabled={
                          (!isSkipping && !state.answer_numeric) ||
                          submitMutation.isPending
                        }
                        onClick={() => submitItemAnswer(key, null, eq.id)}
                      >
                        Save
                      </Button>
                    </>
                  )}
                </CardContent>
              </Card>
            );
          })
        : items.map((item: HACCPItem) => {
            const key = item.id;
            const alreadyAnswered = answeredIds.has(item.id);
            const state = answers[key] ?? {};
            const isSkipping = !!state.skip_reason;
            const options = item.options_json?.options ?? [];

            return (
              <Card key={key} className={alreadyAnswered ? "opacity-60" : ""}>
                <CardHeader className="pb-2">
                  <CardTitle className="text-sm font-medium">
                    {item.order_index}. {item.question}
                    {item.is_required && (
                      <span className="text-destructive ml-1">*</span>
                    )}
                  </CardTitle>
                </CardHeader>
                <CardContent className="space-y-3">
                  {alreadyAnswered ? (
                    <p className="text-sm text-green-700">Recorded</p>
                  ) : (
                    <>
                      {!isSkipping && (
                        <>
                          {item.item_type === "yes_no" && (
                            <YesNoInput
                              value={state.answer_bool ?? null}
                              onChange={(v) => updateAnswer(key, { answer_bool: v })}
                            />
                          )}
                          {(item.item_type === "temperature" ||
                            item.item_type === "numeric") && (
                            <Input
                              type="number"
                              step="0.1"
                              value={state.answer_numeric ?? ""}
                              onChange={(e) =>
                                updateAnswer(key, {
                                  answer_numeric: parseFloat(e.target.value),
                                })
                              }
                              placeholder="Enter value"
                            />
                          )}
                          {item.item_type === "text" && (
                            <Input
                              value={state.answer_text ?? ""}
                              onChange={(e) =>
                                updateAnswer(key, {
                                  answer_text: e.target.value,
                                })
                              }
                              placeholder="Enter text"
                            />
                          )}
                          {item.item_type === "multi_select" && (
                            <MultiSelectInput
                              options={options}
                              value={state.answer_options ?? []}
                              onChange={(v) => updateAnswer(key, { answer_options: v })}
                              minSelections={item.min_selections}
                            />
                          )}
                          {item.item_type === "single_select" && (
                            <Select
                              value={state.answer_options?.[0] ?? ""}
                              onValueChange={(v) =>
                                updateAnswer(key, { answer_options: [v] })
                              }
                            >
                              <SelectTrigger>
                                <SelectValue placeholder="Select option" />
                              </SelectTrigger>
                              <SelectContent>
                                {options.map((opt) => (
                                  <SelectItem key={opt} value={opt}>
                                    {opt}
                                  </SelectItem>
                                ))}
                              </SelectContent>
                            </Select>
                          )}
                        </>
                      )}
                      <div className="flex items-center gap-2">
                        <Select
                          value={state.skip_reason ?? NO_SKIP}
                          onValueChange={(v) =>
                            updateAnswer(key, {
                              skip_reason: v === NO_SKIP ? undefined : v,
                            })
                          }
                        >
                          <SelectTrigger className="text-xs h-8">
                            <SelectValue placeholder="Skip?" />
                          </SelectTrigger>
                          <SelectContent>
                            <SelectItem value={NO_SKIP}>— No skip —</SelectItem>
                            {SKIP_REASONS.map((r) => (
                              <SelectItem key={r.value} value={r.value}>
                                {r.label}
                              </SelectItem>
                            ))}
                          </SelectContent>
                        </Select>
                        <Button
                          size="sm"
                          disabled={submitMutation.isPending}
                          onClick={() => submitItemAnswer(key, item.id, null)}
                        >
                          Save
                        </Button>
                      </div>
                    </>
                  )}
                </CardContent>
              </Card>
            );
          })}
    </div>
  );
}
