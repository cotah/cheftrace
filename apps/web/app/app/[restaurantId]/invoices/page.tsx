"use client";

import { use, useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import Link from "next/link";
import { useToken } from "@/hooks/use-token";
import { invoicesApi } from "@/lib/api/resources";
import type { Invoice, InvoiceStatus } from "@/lib/api/types";
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

const STATUS_OPTIONS: { value: InvoiceStatus; label: string }[] = [
  { value: "uploaded", label: "Uploaded" },
  { value: "processing", label: "Processing" },
  { value: "needs_review", label: "Needs review" },
  { value: "confirmed", label: "Confirmed" },
  { value: "rejected", label: "Rejected" },
];

const DELETABLE_STATUSES: InvoiceStatus[] = ["uploaded", "needs_review"];

function statusBadge(status: string) {
  if (status === "confirmed")
    return <Badge className="bg-green-100 text-green-800">Confirmed</Badge>;
  if (status === "needs_review")
    return <Badge className="bg-amber-100 text-amber-800">Needs review</Badge>;
  if (status === "processing") return <Badge variant="secondary">Processing</Badge>;
  if (status === "rejected") return <Badge variant="destructive">Rejected</Badge>;
  return <Badge variant="outline">Uploaded</Badge>;
}

function formatMoney(value: number | null): string {
  if (value === null) return "—";
  return new Intl.NumberFormat("en-IE", { style: "currency", currency: "EUR" }).format(value);
}

export default function InvoicesListPage({
  params,
}: {
  params: Promise<{ restaurantId: string }>;
}) {
  const { restaurantId: rid } = use(params);
  const token = useToken();
  const qc = useQueryClient();

  const [status, setStatus] = useState<string>(ANY);
  const [pendingDelete, setPendingDelete] = useState<Invoice | null>(null);
  const [deleteError, setDeleteError] = useState<string | null>(null);

  const { data: invoices = [], isLoading } = useQuery({
    queryKey: ["invoices", rid, status],
    queryFn: () => invoicesApi.list(rid, status === ANY ? undefined : status, token!),
    enabled: !!rid && !!token,
  });

  const deleteMut = useMutation({
    mutationFn: (id: string) => invoicesApi.delete(rid, id, token!),
    onSuccess: (_data, id) => {
      // Remove from cache immediately so the row disappears without waiting
      // for the next refetch.
      qc.setQueryData<Invoice[]>(["invoices", rid, status], (current) =>
        (current ?? []).filter((inv) => inv.id !== id),
      );
      void qc.invalidateQueries({ queryKey: ["invoices", rid] });
      setPendingDelete(null);
    },
    onError: (e: Error) => {
      setDeleteError(e.message);
    },
  });

  function requestDelete(inv: Invoice) {
    setDeleteError(null);
    setPendingDelete(inv);
  }

  function confirmDelete() {
    if (pendingDelete) {
      deleteMut.mutate(pendingDelete.id);
    }
  }

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <h1 className="text-2xl font-semibold">Invoices</h1>
        <Link href={`/app/${rid}/invoices/upload`}>
          <Button>Upload invoice</Button>
        </Link>
      </div>

      <div className="grid grid-cols-1 gap-3 sm:grid-cols-3 sm:items-end">
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
        {status !== ANY && (
          <Button variant="ghost" size="sm" onClick={() => setStatus(ANY)}>
            Clear filter
          </Button>
        )}
      </div>

      {isLoading ? (
        <p className="text-muted-foreground">Loading...</p>
      ) : invoices.length === 0 ? (
        <p className="text-muted-foreground">
          No invoices yet. Click <span className="font-medium">Upload invoice</span> to start.
        </p>
      ) : (
        <Table>
          <TableHeader>
            <TableRow>
              <TableHead className="w-32">Date</TableHead>
              <TableHead>Supplier</TableHead>
              <TableHead className="w-40">Number</TableHead>
              <TableHead className="w-32 text-right">Total</TableHead>
              <TableHead className="w-36">Status</TableHead>
              <TableHead className="text-right">Actions</TableHead>
            </TableRow>
          </TableHeader>
          <TableBody>
            {invoices.map((inv) => {
              const canDelete = DELETABLE_STATUSES.includes(inv.status);
              return (
                <TableRow key={inv.id}>
                  <TableCell>{inv.invoice_date ?? "—"}</TableCell>
                  <TableCell className="font-medium">
                    {inv.supplier_name_raw ?? (
                      <span className="text-muted-foreground">—</span>
                    )}
                  </TableCell>
                  <TableCell>{inv.invoice_number ?? "—"}</TableCell>
                  <TableCell className="text-right">{formatMoney(inv.total_amount)}</TableCell>
                  <TableCell>{statusBadge(inv.status)}</TableCell>
                  <TableCell className="space-x-1 text-right">
                    <Link href={`/app/${rid}/invoices/${inv.id}`}>
                      <Button variant="ghost" size="sm">
                        View
                      </Button>
                    </Link>
                    {canDelete && (
                      <Button
                        variant="ghost"
                        size="sm"
                        className="text-destructive hover:text-destructive"
                        onClick={() => requestDelete(inv)}
                      >
                        Delete
                      </Button>
                    )}
                  </TableCell>
                </TableRow>
              );
            })}
          </TableBody>
        </Table>
      )}

      <Dialog
        open={pendingDelete !== null}
        onOpenChange={(open) => {
          if (!open && !deleteMut.isPending) {
            setPendingDelete(null);
            setDeleteError(null);
          }
        }}
      >
        <DialogContent>
          <DialogHeader>
            <DialogTitle>Delete invoice?</DialogTitle>
            <DialogDescription>
              Are you sure? This cannot be undone. The invoice file and all its OCR
              line items will be permanently removed.
            </DialogDescription>
          </DialogHeader>
          {pendingDelete && (
            <p className="text-sm">
              <span className="text-muted-foreground">Invoice: </span>
              {pendingDelete.supplier_name_raw ?? "—"}
              {pendingDelete.invoice_number ? ` · ${pendingDelete.invoice_number}` : ""}
              {pendingDelete.invoice_date ? ` · ${pendingDelete.invoice_date}` : ""}
            </p>
          )}
          {deleteError && (
            <p className="rounded-md bg-destructive/10 p-3 text-sm text-destructive">
              {deleteError}
            </p>
          )}
          <DialogFooter>
            <Button
              variant="ghost"
              onClick={() => {
                setPendingDelete(null);
                setDeleteError(null);
              }}
              disabled={deleteMut.isPending}
            >
              Cancel
            </Button>
            <Button
              variant="destructive"
              onClick={confirmDelete}
              disabled={deleteMut.isPending}
            >
              {deleteMut.isPending ? "Deleting..." : "Delete"}
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </div>
  );
}
