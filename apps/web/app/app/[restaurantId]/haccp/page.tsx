"use client";

import { use, useEffect, useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { useToken } from "@/hooks/use-token";
import { useRestaurant } from "@/hooks/use-restaurant";
import { haccpApi } from "@/lib/api/resources";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import type { HACCPRun, HACCPTemplate } from "@/lib/api/types";

const today = new Date().toISOString().split("T")[0]!;

function frequencyLabel(t: HACCPTemplate) {
  if (t.frequency === "shift" && t.shifts_per_day) {
    return `${t.shifts_per_day}× daily`;
  }
  return t.frequency.replace("_", " ");
}

function runStatusBadge(status: string) {
  if (status === "completed")
    return <Badge className="bg-green-100 text-green-800">Completed</Badge>;
  if (status === "in_progress") return <Badge variant="secondary">In progress</Badge>;
  if (status === "missed") return <Badge variant="destructive">Missed</Badge>;
  return <Badge variant="outline">Pending</Badge>;
}

export default function HACCPPage({
  params,
}: {
  params: Promise<{ restaurantId: string }>;
}) {
  const { restaurantId: rid } = use(params);
  const token = useToken();
  const router = useRouter();
  const qc = useQueryClient();
  const { active } = useRestaurant();
  const isOwner = active?.role === "owner";
  const canToggle = active?.role === "owner" || active?.role === "manager";

  const [reseedBanner, setReseedBanner] = useState<{
    kind: "ok" | "error";
    text: string;
  } | null>(null);

  useEffect(() => {
    if (!reseedBanner) return;
    const t = setTimeout(() => setReseedBanner(null), 5000);
    return () => clearTimeout(t);
  }, [reseedBanner]);

  const { data: templates = [], isLoading } = useQuery({
    queryKey: ["haccp-templates", rid, "with-inactive"],
    queryFn: () => haccpApi.listTemplates(rid, token!, { includeInactive: true }),
    enabled: !!rid && !!token,
  });

  const toggleActiveMutation = useMutation({
    mutationFn: ({ templateId, isActive }: { templateId: string; isActive: boolean }) =>
      haccpApi.setTemplateActive(rid, templateId, isActive, token!),
    onSuccess: () => {
      void qc.invalidateQueries({ queryKey: ["haccp-templates", rid, "with-inactive"] });
    },
  });

  const reseedMutation = useMutation({
    mutationFn: () => haccpApi.reseedTemplates(rid, token!),
    onSuccess: (result) => {
      const created = result.created.length;
      const skipped = result.skipped.length;
      setReseedBanner({
        kind: "ok",
        text:
          created === 0
            ? `All FSAI templates already in place (${skipped} existed).`
            : `Created ${created} new template${created === 1 ? "" : "s"}, ${skipped} already existed.`,
      });
      void qc.invalidateQueries({ queryKey: ["haccp-templates", rid] });
    },
    onError: (err: Error) => {
      setReseedBanner({ kind: "error", text: err.message });
    },
  });

  const { data: todayRuns = [] } = useQuery({
    queryKey: ["haccp-runs", rid, today],
    queryFn: () => haccpApi.listRuns(rid, { run_date: today }, token!),
    enabled: !!rid && !!token,
  });

  const startMutation = useMutation({
    mutationFn: ({
      templateId,
      shiftNumber,
    }: {
      templateId: string;
      shiftNumber?: number;
    }) =>
      haccpApi.startRun(
        rid,
        {
          template_id: templateId,
          run_date: today,
          shift_number: shiftNumber,
        },
        token!,
      ),
    onSuccess: (run: HACCPRun) => {
      void qc.invalidateQueries({ queryKey: ["haccp-runs", rid, today] });
      router.push(`/app/${rid}/haccp/${run.id}`);
    },
  });

  const runsMap = Object.fromEntries(
    todayRuns.map((r) => [`${r.template_id}-${r.shift_number ?? 0}`, r]),
  );

  if (isLoading) {
    return (
      <div className="space-y-6">
        <h1 className="text-2xl font-semibold">HACCP</h1>
        <p className="text-muted-foreground">Loading...</p>
      </div>
    );
  }

  return (
    <div className="space-y-6">
      <div className="flex items-start justify-between gap-4">
        <div>
          <h1 className="text-2xl font-semibold">HACCP</h1>
          <p className="text-sm text-muted-foreground mt-1">
            Today — {new Date().toLocaleDateString("en-IE")}
          </p>
        </div>
        <div className="flex items-center gap-2">
          <Link href={`/app/${rid}/haccp/runs`}>
            <Button variant="outline" size="sm">
              Runs history
            </Button>
          </Link>
          {isOwner && (
            <Button
              variant="outline"
              size="sm"
              disabled={reseedMutation.isPending}
              onClick={() => reseedMutation.mutate()}
            >
              {reseedMutation.isPending ? "Updating..." : "Update HACCP Templates"}
            </Button>
          )}
        </div>
      </div>

      {reseedBanner && (
        <div
          className={
            reseedBanner.kind === "ok"
              ? "rounded-md border border-green-200 bg-green-50 px-4 py-3 text-sm text-green-800"
              : "rounded-md border border-destructive/30 bg-destructive/5 px-4 py-3 text-sm text-destructive"
          }
        >
          {reseedBanner.text}
        </div>
      )}

      {templates.length === 0 ? (
        <Card>
          <CardContent className="py-8 text-center">
            <p className="text-muted-foreground">No HACCP templates configured.</p>
          </CardContent>
        </Card>
      ) : (
        <div className="space-y-3">
          {templates.map((t) => {
            const shifts = t.frequency === "shift" && t.shifts_per_day ? t.shifts_per_day : 1;

            return Array.from({ length: shifts }, (_, i) => {
              const shiftNum = t.frequency === "shift" ? i + 1 : undefined;
              const key = `${t.id}-${shiftNum ?? 0}`;
              const run = runsMap[key];
              const inactive = !t.is_active;

              return (
                <Card key={key} className={inactive ? "opacity-60 bg-muted/30" : undefined}>
                  <CardHeader className="pb-2">
                    <div className="flex items-center justify-between">
                      <CardTitle className="text-base">
                        {t.name}
                        {shiftNum && (
                          <span className="text-muted-foreground font-normal ml-2 text-sm">
                            Shift {shiftNum}
                          </span>
                        )}
                        {inactive && (
                          <Badge variant="outline" className="ml-2 text-xs">
                            Disabled
                          </Badge>
                        )}
                      </CardTitle>
                      <div className="flex items-center gap-2">
                        <span className="text-xs text-muted-foreground">
                          {frequencyLabel(t)}
                        </span>
                        {!inactive &&
                          (run ? (
                            runStatusBadge(run.status)
                          ) : (
                            <Badge variant="outline">Pending</Badge>
                          ))}
                      </div>
                    </div>
                  </CardHeader>
                  <CardContent>
                    <div className="flex items-center justify-between gap-2">
                      <div>
                        {inactive ? (
                          <p className="text-sm text-muted-foreground">
                            Disabled — won&apos;t appear on dashboard alerts.
                          </p>
                        ) : run?.status === "completed" ? (
                          <p className="text-sm text-muted-foreground">
                            Completed
                            {run.completed_at
                              ? ` at ${new Date(run.completed_at).toLocaleTimeString("en-IE", { hour: "2-digit", minute: "2-digit" })}`
                              : ""}
                          </p>
                        ) : run?.status === "in_progress" ? (
                          <Button
                            size="sm"
                            onClick={() => router.push(`/app/${rid}/haccp/${run.id}`)}
                          >
                            Continue
                          </Button>
                        ) : (
                          <Button
                            size="sm"
                            disabled={startMutation.isPending}
                            onClick={() =>
                              startMutation.mutate({
                                templateId: t.id,
                                shiftNumber: shiftNum,
                              })
                            }
                          >
                            Start
                          </Button>
                        )}
                      </div>
                      {canToggle && (shiftNum === undefined || shiftNum === 1) && (
                        <Button
                          variant="outline"
                          size="sm"
                          disabled={toggleActiveMutation.isPending}
                          onClick={() =>
                            toggleActiveMutation.mutate({
                              templateId: t.id,
                              isActive: !t.is_active,
                            })
                          }
                        >
                          {t.is_active ? "Disable" : "Enable"}
                        </Button>
                      )}
                    </div>
                  </CardContent>
                </Card>
              );
            });
          })}
        </div>
      )}
    </div>
  );
}
