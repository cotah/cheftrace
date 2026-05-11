"use client";

import { use, useState } from "react";
import { useQuery } from "@tanstack/react-query";
import Link from "next/link";
import { useToken } from "@/hooks/use-token";
import { haccpApi } from "@/lib/api/resources";
import { downloadPdf } from "@/lib/pdf-download";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";

const ANY = "__any__";

const STATUS_OPTIONS = [
  { value: "pending", label: "Pending" },
  { value: "in_progress", label: "In progress" },
  { value: "completed", label: "Completed" },
  { value: "missed", label: "Missed" },
];

function statusBadge(status: string) {
  if (status === "completed")
    return <Badge className="bg-green-100 text-green-800">Completed</Badge>;
  if (status === "in_progress") return <Badge variant="secondary">In progress</Badge>;
  if (status === "missed") return <Badge variant="destructive">Missed</Badge>;
  return <Badge variant="outline">Pending</Badge>;
}

export default function HACCPRunsHistoryPage({
  params,
}: {
  params: Promise<{ restaurantId: string }>;
}) {
  const { restaurantId: rid } = use(params);
  const token = useToken();

  const [dateFrom, setDateFrom] = useState("");
  const [dateTo, setDateTo] = useState("");
  const [status, setStatus] = useState<string>(ANY);
  const [templateId, setTemplateId] = useState<string>(ANY);

  const { data: templates = [] } = useQuery({
    queryKey: ["haccp-templates", rid],
    queryFn: () => haccpApi.listTemplates(rid, token!),
    enabled: !!rid && !!token,
  });

  const filters = {
    date_from: dateFrom || undefined,
    date_to: dateTo || undefined,
    status: status === ANY ? undefined : status,
    template_id: templateId === ANY ? undefined : templateId,
  };

  const { data: runs = [], isLoading } = useQuery({
    queryKey: ["haccp-runs-history", rid, filters],
    queryFn: () => haccpApi.listRuns(rid, filters, token!),
    enabled: !!rid && !!token,
  });

  const templateMap = Object.fromEntries(templates.map((t) => [t.id, t.name]));

  function clearFilters() {
    setDateFrom("");
    setDateTo("");
    setStatus(ANY);
    setTemplateId(ANY);
  }

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <Link
            href={`/app/${rid}/haccp`}
            className="text-sm text-muted-foreground hover:underline"
          >
            ← HACCP today
          </Link>
          <h1 className="text-2xl font-semibold mt-2">HACCP runs history</h1>
        </div>
      </div>

      <div className="grid grid-cols-1 gap-3 sm:grid-cols-2 lg:grid-cols-5 lg:items-end">
        <div className="space-y-1">
          <Label className="text-xs">From</Label>
          <Input type="date" value={dateFrom} onChange={(e) => setDateFrom(e.target.value)} />
        </div>
        <div className="space-y-1">
          <Label className="text-xs">To</Label>
          <Input type="date" value={dateTo} onChange={(e) => setDateTo(e.target.value)} />
        </div>
        <div className="space-y-1">
          <Label className="text-xs">Status</Label>
          <Select value={status} onValueChange={setStatus}>
            <SelectTrigger>
              <SelectValue />
            </SelectTrigger>
            <SelectContent>
              <SelectItem value={ANY}>Any status</SelectItem>
              {STATUS_OPTIONS.map((s) => (
                <SelectItem key={s.value} value={s.value}>
                  {s.label}
                </SelectItem>
              ))}
            </SelectContent>
          </Select>
        </div>
        <div className="space-y-1">
          <Label className="text-xs">Template</Label>
          <Select value={templateId} onValueChange={setTemplateId}>
            <SelectTrigger>
              <SelectValue />
            </SelectTrigger>
            <SelectContent>
              <SelectItem value={ANY}>Any template</SelectItem>
              {templates.map((t) => (
                <SelectItem key={t.id} value={t.id}>
                  {t.name}
                </SelectItem>
              ))}
            </SelectContent>
          </Select>
        </div>
        <Button variant="ghost" size="sm" onClick={clearFilters}>
          Clear filters
        </Button>
      </div>

      {isLoading ? (
        <p className="text-muted-foreground">Loading...</p>
      ) : runs.length === 0 ? (
        <p className="text-muted-foreground">No runs match the current filters.</p>
      ) : (
        <div className="overflow-x-auto">
          <Table>
            <TableHeader>
              <TableRow>
                <TableHead className="w-32">Date</TableHead>
                <TableHead>Template</TableHead>
                <TableHead className="w-20">Shift</TableHead>
                <TableHead className="w-32">Status</TableHead>
                <TableHead className="w-44">Completed at</TableHead>
                <TableHead className="text-right">Actions</TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {runs.map((r) => (
                <TableRow key={r.id}>
                  <TableCell>{r.run_date}</TableCell>
                  <TableCell className="font-medium">
                    {templateMap[r.template_id] ?? r.template_id.slice(0, 8)}
                  </TableCell>
                  <TableCell>{r.shift_number ?? "—"}</TableCell>
                  <TableCell>{statusBadge(r.status)}</TableCell>
                  <TableCell className="text-sm text-muted-foreground">
                    {r.completed_at
                      ? new Date(r.completed_at).toLocaleString("en-IE", {
                          dateStyle: "short",
                          timeStyle: "short",
                        })
                      : "—"}
                  </TableCell>
                  <TableCell className="text-right space-x-1">
                    <Link href={`/app/${rid}/haccp/${r.id}`}>
                      <Button variant="ghost" size="sm">
                        View
                      </Button>
                    </Link>
                    {token && r.status === "completed" && (
                      <Button
                        variant="outline"
                        size="sm"
                        onClick={() =>
                          void downloadPdf(
                            `/restaurants/${rid}/reports/daily-checklist.pdf?run_id=${r.id}`,
                            token,
                            `checklist-${r.run_date}-${r.id.slice(0, 8)}.pdf`,
                          )
                        }
                      >
                        Download PDF
                      </Button>
                    )}
                  </TableCell>
                </TableRow>
              ))}
            </TableBody>
          </Table>
        </div>
      )}
    </div>
  );
}
