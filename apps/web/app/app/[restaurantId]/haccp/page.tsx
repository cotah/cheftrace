"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useRouter } from "next/navigation";
import { useToken } from "@/hooks/use-token";
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
  params: { restaurantId: string };
}) {
  const rid = params.restaurantId;
  const token = useToken();
  const router = useRouter();
  const qc = useQueryClient();

  const { data: templates = [], isLoading } = useQuery({
    queryKey: ["haccp-templates", rid],
    queryFn: () => haccpApi.listTemplates(rid, token!),
    enabled: !!token,
  });

  const { data: todayRuns = [] } = useQuery({
    queryKey: ["haccp-runs", rid, today],
    queryFn: () => haccpApi.listRuns(rid, today, token!),
    enabled: !!token,
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
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-semibold">HACCP</h1>
          <p className="text-sm text-muted-foreground mt-1">
            Today — {new Date().toLocaleDateString("en-IE")}
          </p>
        </div>
      </div>

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

              return (
                <Card key={key}>
                  <CardHeader className="pb-2">
                    <div className="flex items-center justify-between">
                      <CardTitle className="text-base">
                        {t.name}
                        {shiftNum && (
                          <span className="text-muted-foreground font-normal ml-2 text-sm">
                            Shift {shiftNum}
                          </span>
                        )}
                      </CardTitle>
                      <div className="flex items-center gap-2">
                        <span className="text-xs text-muted-foreground">
                          {frequencyLabel(t)}
                        </span>
                        {run ? runStatusBadge(run.status) : <Badge variant="outline">Pending</Badge>}
                      </div>
                    </div>
                  </CardHeader>
                  <CardContent>
                    {run?.status === "completed" ? (
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
