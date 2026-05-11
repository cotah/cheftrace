"use client";

import { use, useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import Link from "next/link";
import { useToken } from "@/hooks/use-token";
import { posApi } from "@/lib/api/resources";
import type { POSEvent, POSEventStatus } from "@/lib/api/types";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
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

const STATUS_OPTIONS: { value: POSEventStatus; label: string }[] = [
  { value: "pending", label: "Pending" },
  { value: "pending_approval", label: "Pending approval" },
  { value: "needs_mapping", label: "Needs mapping" },
  { value: "insufficient_stock", label: "Insufficient stock" },
  { value: "failed", label: "Failed" },
  { value: "processed", label: "Processed" },
  { value: "ignored", label: "Ignored" },
];

const TERMINAL_STATUSES: Set<POSEventStatus> = new Set(["processed", "ignored"]);

function statusBadge(status: POSEventStatus) {
  if (status === "processed")
    return <Badge className="bg-green-100 text-green-800">Processed</Badge>;
  if (status === "pending_approval")
    return <Badge className="bg-blue-100 text-blue-800">Pending approval</Badge>;
  if (status === "needs_mapping")
    return <Badge className="bg-amber-100 text-amber-800">Needs mapping</Badge>;
  if (status === "insufficient_stock")
    return (
      <Badge className="bg-amber-100 text-amber-800">Insufficient stock</Badge>
    );
  if (status === "failed") return <Badge variant="destructive">Failed</Badge>;
  if (status === "ignored") return <Badge variant="outline">Ignored</Badge>;
  return <Badge variant="secondary">Pending</Badge>;
}

export default function POSEventsPage({
  params,
}: {
  params: Promise<{ restaurantId: string }>;
}) {
  const { restaurantId: rid } = use(params);
  const token = useToken();
  const qc = useQueryClient();

  const [status, setStatus] = useState<string>(ANY);
  const [pendingDismiss, setPendingDismiss] = useState<POSEvent | null>(null);
  const [dismissReason, setDismissReason] = useState("");

  const { data: events = [], isLoading } = useQuery({
    queryKey: ["pos-events", rid, status],
    queryFn: () =>
      posApi.listEvents(
        rid,
        status === ANY ? undefined : (status as POSEventStatus),
        token!,
      ),
    enabled: !!rid && !!token,
  });

  const processMutation = useMutation({
    mutationFn: (args: { id: string; force: boolean }) =>
      posApi.processEvent(rid, args.id, args.force, token!),
    onSuccess: () => {
      void qc.invalidateQueries({ queryKey: ["pos-events", rid] });
      void qc.invalidateQueries({ queryKey: ["stock-lots", rid] });
      void qc.invalidateQueries({ queryKey: ["dashboard", rid] });
    },
  });

  const dismissMutation = useMutation({
    mutationFn: (args: { id: string; reason: string }) =>
      posApi.dismissEvent(rid, args.id, args.reason, token!),
    onSuccess: () => {
      void qc.invalidateQueries({ queryKey: ["pos-events", rid] });
      setPendingDismiss(null);
      setDismissReason("");
    },
  });

  return (
    <div className="space-y-6">
      <div className="flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
        <div>
          <Link
            href={`/app/${rid}/pos`}
            className="text-sm text-muted-foreground hover:underline"
          >
            ← POS integrations
          </Link>
          <h1 className="text-2xl font-semibold mt-2">POS event queue</h1>
          <p className="text-sm text-muted-foreground mt-1">
            Every sale arriving via webhook lands here. Approve, retry, or
            dismiss as needed.
          </p>
        </div>
      </div>

      <div className="grid grid-cols-1 gap-3 sm:max-w-xs">
        <div className="space-y-1">
          <Label className="text-xs">Status</Label>
          <Select value={status} onValueChange={setStatus}>
            <SelectTrigger>
              <SelectValue />
            </SelectTrigger>
            <SelectContent>
              <SelectItem value={ANY}>Any status</SelectItem>
              {STATUS_OPTIONS.map((opt) => (
                <SelectItem key={opt.value} value={opt.value}>
                  {opt.label}
                </SelectItem>
              ))}
            </SelectContent>
          </Select>
        </div>
      </div>

      {processMutation.isError && (
        <p className="rounded-md bg-destructive/10 p-3 text-sm text-destructive">
          {processMutation.error.message}
        </p>
      )}

      {isLoading ? (
        <p className="text-muted-foreground">Loading...</p>
      ) : events.length === 0 ? (
        <p className="text-muted-foreground">
          No events match this filter. Test webhooks from the Square Sandbox
          appear here as they arrive.
        </p>
      ) : (
        <div className="overflow-x-auto">
          <Table>
            <TableHeader>
              <TableRow>
                <TableHead className="w-44">Received</TableHead>
                <TableHead>External ID</TableHead>
                <TableHead>Type</TableHead>
                <TableHead>Status</TableHead>
                <TableHead>Note</TableHead>
                <TableHead className="text-right">Actions</TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {events.map((event) => {
                const terminal = TERMINAL_STATUSES.has(event.processing_status);
                const canApprove = event.processing_status === "pending_approval";
                return (
                  <TableRow key={event.id}>
                    <TableCell className="text-sm text-muted-foreground">
                      {new Date(event.received_at).toLocaleString("en-IE", {
                        dateStyle: "short",
                        timeStyle: "short",
                      })}
                    </TableCell>
                    <TableCell className="font-mono text-xs">
                      {event.external_event_id}
                    </TableCell>
                    <TableCell className="text-sm">{event.event_type}</TableCell>
                    <TableCell>
                      {statusBadge(event.processing_status)}
                    </TableCell>
                    <TableCell className="text-xs text-muted-foreground max-w-xs truncate">
                      {event.error_message ?? "—"}
                    </TableCell>
                    <TableCell className="text-right space-x-1">
                      {canApprove && (
                        <Button
                          variant="default"
                          size="sm"
                          disabled={processMutation.isPending}
                          onClick={() =>
                            processMutation.mutate({
                              id: event.id,
                              force: true,
                            })
                          }
                        >
                          Approve
                        </Button>
                      )}
                      {!canApprove && !terminal && (
                        <Button
                          variant="outline"
                          size="sm"
                          disabled={processMutation.isPending}
                          onClick={() =>
                            processMutation.mutate({
                              id: event.id,
                              force: false,
                            })
                          }
                        >
                          Process
                        </Button>
                      )}
                      {!terminal && (
                        <Button
                          variant="ghost"
                          size="sm"
                          className="text-destructive hover:text-destructive"
                          onClick={() => {
                            setPendingDismiss(event);
                            setDismissReason("");
                          }}
                        >
                          Dismiss
                        </Button>
                      )}
                    </TableCell>
                  </TableRow>
                );
              })}
            </TableBody>
          </Table>
        </div>
      )}

      <Dialog
        open={pendingDismiss !== null}
        onOpenChange={(open) => {
          if (!open && !dismissMutation.isPending) {
            setPendingDismiss(null);
            setDismissReason("");
          }
        }}
      >
        <DialogContent>
          <DialogHeader>
            <DialogTitle>Dismiss event</DialogTitle>
            <DialogDescription>
              The event is marked as ignored. Stock is not deducted. A reason
              is required for the audit trail.
            </DialogDescription>
          </DialogHeader>
          {pendingDismiss && (
            <div className="space-y-3 text-sm">
              <p>
                <span className="text-muted-foreground">Event ID:</span>{" "}
                <span className="font-mono text-xs">
                  {pendingDismiss.external_event_id}
                </span>
              </p>
              <div className="space-y-2">
                <Label>Reason</Label>
                <Input
                  value={dismissReason}
                  onChange={(e) => setDismissReason(e.target.value)}
                  placeholder="e.g. test event from sandbox"
                  maxLength={500}
                />
              </div>
            </div>
          )}
          {dismissMutation.isError && (
            <p className="rounded-md bg-destructive/10 p-3 text-sm text-destructive">
              {dismissMutation.error.message}
            </p>
          )}
          <DialogFooter>
            <Button
              variant="ghost"
              onClick={() => {
                setPendingDismiss(null);
                setDismissReason("");
              }}
              disabled={dismissMutation.isPending}
            >
              Cancel
            </Button>
            <Button
              variant="destructive"
              disabled={
                !pendingDismiss ||
                !dismissReason.trim() ||
                dismissMutation.isPending
              }
              onClick={() => {
                if (pendingDismiss) {
                  dismissMutation.mutate({
                    id: pendingDismiss.id,
                    reason: dismissReason.trim(),
                  });
                }
              }}
            >
              {dismissMutation.isPending ? "Dismissing..." : "Confirm dismiss"}
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </div>
  );
}
