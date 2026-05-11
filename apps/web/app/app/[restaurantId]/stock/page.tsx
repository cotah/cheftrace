"use client";

import { use, useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import Link from "next/link";
import { useToken } from "@/hooks/use-token";
import { stockLotsApi, productsApi } from "@/lib/api/resources";
import { useRestaurant } from "@/hooks/use-restaurant";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
  DialogTrigger,
} from "@/components/ui/dialog";
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
import type { StockLot } from "@/lib/api/types";

const EXPIRY_REASONS = [
  { value: "typo", label: "Typo on entry" },
  { value: "supplier_error", label: "Supplier error" },
  { value: "inspection_finding", label: "Inspection finding" },
  { value: "other", label: "Other" },
];

function expiryBadge(lot: StockLot, warningDays: number, criticalDays: number) {
  if (lot.status === "discarded") return <Badge variant="outline">Discarded</Badge>;
  if (lot.status === "depleted") return <Badge variant="secondary">Depleted</Badge>;
  if (!lot.expiry_date) return <Badge variant="outline">No expiry</Badge>;

  const today = new Date();
  const expiry = new Date(lot.expiry_date);
  const diffDays = Math.ceil((expiry.getTime() - today.getTime()) / (1000 * 60 * 60 * 24));

  if (diffDays < 0) return <Badge variant="destructive">Expired</Badge>;
  if (diffDays <= criticalDays) return <Badge variant="destructive">{diffDays}d left</Badge>;
  if (diffDays <= warningDays)
    return (
      <Badge className="bg-amber-500 text-white hover:bg-amber-500">{diffDays}d left</Badge>
    );
  return (
    <Badge variant="outline" className="text-green-700 border-green-700">
      {diffDays}d left
    </Badge>
  );
}

function EditExpiryDialog({
  rid,
  lot,
  productName,
  token,
}: {
  rid: string;
  lot: StockLot;
  productName: string;
  token: string;
}) {
  const qc = useQueryClient();
  const [open, setOpen] = useState(false);
  const [expiryDate, setExpiryDate] = useState(lot.expiry_date ?? "");
  const [reason, setReason] = useState("");

  const editMutation = useMutation({
    mutationFn: () =>
      stockLotsApi.updateExpiry(
        rid,
        lot.id,
        { expiry_date: expiryDate, reason },
        token,
      ),
    onSuccess: () => {
      void qc.invalidateQueries({ queryKey: ["stock-lots", rid] });
      void qc.invalidateQueries({ queryKey: ["dashboard", rid] });
      setOpen(false);
    },
  });

  return (
    <Dialog open={open} onOpenChange={setOpen}>
      <DialogTrigger asChild>
        <Button variant="outline" size="sm">
          Edit expiry
        </Button>
      </DialogTrigger>
      <DialogContent>
        <DialogHeader>
          <DialogTitle>Edit expiry — {productName}</DialogTitle>
        </DialogHeader>
        <div className="space-y-4 pt-2">
          <p className="text-xs text-muted-foreground">
            Current expiry: {lot.expiry_date ?? "—"}. Editing creates an audit log
            entry. A reason is required.
          </p>
          <div className="space-y-2">
            <Label>New expiry date</Label>
            <Input
              type="date"
              value={expiryDate}
              onChange={(e) => setExpiryDate(e.target.value)}
            />
          </div>
          <div className="space-y-2">
            <Label>Reason</Label>
            <Select value={reason} onValueChange={setReason}>
              <SelectTrigger>
                <SelectValue placeholder="Select reason" />
              </SelectTrigger>
              <SelectContent>
                {EXPIRY_REASONS.map((r) => (
                  <SelectItem key={r.value} value={r.value}>
                    {r.label}
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>
          </div>
          <Button
            className="w-full"
            disabled={!expiryDate || !reason || editMutation.isPending}
            onClick={() => editMutation.mutate()}
          >
            {editMutation.isPending ? "Saving..." : "Save change"}
          </Button>
          {editMutation.isError && (
            <p className="text-sm text-destructive">{editMutation.error.message}</p>
          )}
        </div>
      </DialogContent>
    </Dialog>
  );
}

function DiscardDialog({
  rid,
  lot,
  productName,
  token,
}: {
  rid: string;
  lot: StockLot;
  productName: string;
  token: string;
}) {
  const qc = useQueryClient();
  const [open, setOpen] = useState(false);

  const discardMutation = useMutation({
    mutationFn: () => stockLotsApi.discard(rid, lot.id, token),
    onSuccess: () => {
      void qc.invalidateQueries({ queryKey: ["stock-lots", rid] });
      void qc.invalidateQueries({ queryKey: ["dashboard", rid] });
      setOpen(false);
    },
  });

  return (
    <Dialog open={open} onOpenChange={setOpen}>
      <DialogTrigger asChild>
        <Button variant="ghost" size="sm" className="text-destructive">
          Discard
        </Button>
      </DialogTrigger>
      <DialogContent>
        <DialogHeader>
          <DialogTitle>Discard lot?</DialogTitle>
        </DialogHeader>
        <div className="space-y-4 pt-2">
          <p className="text-sm">
            About to discard{" "}
            <span className="font-semibold">
              {lot.quantity_remaining} {lot.unit}
            </span>{" "}
            of <span className="font-semibold">{productName}</span>. This sets
            remaining quantity to 0 and records a movement of kind{" "}
            <code className="text-xs bg-muted px-1 rounded">discard</code>. The
            lot is not deleted — movements remain in the log.
          </p>
          <div className="flex justify-end gap-2">
            <Button
              variant="outline"
              size="sm"
              onClick={() => setOpen(false)}
              disabled={discardMutation.isPending}
            >
              Cancel
            </Button>
            <Button
              variant="destructive"
              size="sm"
              disabled={discardMutation.isPending}
              onClick={() => discardMutation.mutate()}
            >
              {discardMutation.isPending ? "Discarding..." : "Discard lot"}
            </Button>
          </div>
          {discardMutation.isError && (
            <p className="text-sm text-destructive">
              {discardMutation.error.message}
            </p>
          )}
        </div>
      </DialogContent>
    </Dialog>
  );
}

export default function StockPage({
  params,
}: {
  params: Promise<{ restaurantId: string }>;
}) {
  const { restaurantId: rid } = use(params);
  const token = useToken();
  const { active } = useRestaurant();

  const { data: lots = [], isLoading } = useQuery({
    queryKey: ["stock-lots", rid],
    queryFn: () => stockLotsApi.list(rid, token!),
    enabled: !!rid && !!token,
  });

  const { data: products = [] } = useQuery({
    queryKey: ["products", rid],
    queryFn: () => productsApi.list(rid, token!),
    enabled: !!rid && !!token,
  });

  const productMap = Object.fromEntries(products.map((p) => [p.id, p.name]));
  const warningDays = active?.expiry_warning_days ?? 3;
  const criticalDays = active?.critical_expiry_days ?? 1;

  const activeLots = lots.filter((l) => l.status === "active" && l.quantity_remaining > 0);

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <h1 className="text-2xl font-semibold">Stock</h1>
        <div className="flex gap-2">
          <Link href={`/app/${rid}/stock/movements`}>
            <Button variant="outline">Movement log</Button>
          </Link>
          <Link href={`/app/${rid}/stock/receive`}>
            <Button>Receive delivery</Button>
          </Link>
        </div>
      </div>

      {isLoading ? (
        <p className="text-muted-foreground">Loading...</p>
      ) : activeLots.length === 0 ? (
        <p className="text-muted-foreground">No active stock lots.</p>
      ) : (
        <div className="overflow-x-auto">
          <Table>
            <TableHeader>
              <TableRow>
                <TableHead>Product</TableHead>
                <TableHead>Remaining</TableHead>
                <TableHead>Unit</TableHead>
                <TableHead>Expiry</TableHead>
                <TableHead>Received</TableHead>
                <TableHead className="text-right">Actions</TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {activeLots.map((lot) => {
                const productName =
                  productMap[lot.product_id] ?? lot.product_id.slice(0, 8);
                return (
                  <TableRow key={lot.id}>
                    <TableCell className="font-medium">{productName}</TableCell>
                    <TableCell>{lot.quantity_remaining}</TableCell>
                    <TableCell>{lot.unit}</TableCell>
                    <TableCell>{expiryBadge(lot, warningDays, criticalDays)}</TableCell>
                    <TableCell>{lot.received_date}</TableCell>
                    <TableCell className="text-right space-x-1">
                      {token && (
                        <>
                          <EditExpiryDialog
                            rid={rid}
                            lot={lot}
                            productName={productName}
                            token={token}
                          />
                          <DiscardDialog
                            rid={rid}
                            lot={lot}
                            productName={productName}
                            token={token}
                          />
                        </>
                      )}
                    </TableCell>
                  </TableRow>
                );
              })}
            </TableBody>
          </Table>
        </div>
      )}
    </div>
  );
}
