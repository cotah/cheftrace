"use client";

import { use, useMemo, useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { useToken } from "@/hooks/use-token";
import { invoicesApi, productsApi } from "@/lib/api/resources";
import type {
  InvoiceConfirmDecision,
  InvoiceLineItem,
  InvoiceWithItems,
  Product,
} from "@/lib/api/types";
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

type Decision = {
  action: "confirm" | "reject";
  productId: string;
  quantity: string;
  unit: string;
  unitCost: string;
  expiryDate: string;
  batchCode: string;
  notes: string;
};

function emptyDecision(line: InvoiceLineItem): Decision {
  return {
    action: "confirm",
    productId: line.confirmed_product_id ?? line.suggested_product_id ?? "",
    quantity: line.quantity != null ? String(line.quantity) : "",
    unit: line.unit ?? "",
    unitCost: line.unit_cost != null ? String(line.unit_cost) : "",
    expiryDate: line.expiry_date ?? "",
    batchCode: line.batch_code ?? "",
    notes: line.notes ?? "",
  };
}

function statusBadge(status: string) {
  if (status === "confirmed")
    return <Badge className="bg-green-100 text-green-800">Confirmed</Badge>;
  if (status === "needs_review")
    return <Badge className="bg-amber-100 text-amber-800">Needs review</Badge>;
  if (status === "processing") return <Badge variant="secondary">Processing</Badge>;
  if (status === "rejected") return <Badge variant="destructive">Rejected</Badge>;
  return <Badge variant="outline">Uploaded</Badge>;
}

function isImageMime(path: string): boolean {
  const lower = path.toLowerCase();
  return [".jpg", ".jpeg", ".png", ".webp"].some((ext) => lower.endsWith(ext));
}

export default function InvoiceDetailPage({
  params,
}: {
  params: Promise<{ restaurantId: string; invoiceId: string }>;
}) {
  const { restaurantId: rid, invoiceId } = use(params);
  const token = useToken();
  const router = useRouter();
  const qc = useQueryClient();

  const { data: invoice, isLoading } = useQuery({
    queryKey: ["invoice", rid, invoiceId],
    queryFn: () => invoicesApi.get(rid, invoiceId, token!),
    enabled: !!rid && !!invoiceId && !!token,
  });

  const { data: products = [] } = useQuery({
    queryKey: ["products", rid],
    queryFn: () => productsApi.list(rid, token!),
    enabled: !!rid && !!token,
  });

  // Only user edits are stored. Defaults come from the invoice line items
  // each render — avoids a setState-in-effect cascade.
  const [edits, setEdits] = useState<Record<string, Partial<Decision>>>({});
  const [submitError, setSubmitError] = useState<string | null>(null);

  const decisions = useMemo<Record<string, Decision>>(() => {
    if (!invoice) return {};
    const out: Record<string, Decision> = {};
    for (const line of invoice.items) {
      out[line.id] = { ...emptyDecision(line), ...(edits[line.id] ?? {}) };
    }
    return out;
  }, [invoice, edits]);

  const productsById = useMemo(
    () => Object.fromEntries(products.map((p) => [p.id, p])) as Record<string, Product>,
    [products],
  );

  const processMut = useMutation({
    mutationFn: () => invoicesApi.process(rid, invoiceId, token!),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["invoice", rid, invoiceId] }),
  });

  const confirmMut = useMutation({
    mutationFn: (body: { items: InvoiceConfirmDecision[] }) =>
      invoicesApi.confirm(rid, invoiceId, body, token!),
    onSuccess: () => {
      void qc.invalidateQueries({ queryKey: ["invoice", rid, invoiceId] });
      router.push(`/app/${rid}/invoices`);
    },
  });

  if (isLoading || !invoice) {
    return <p className="text-muted-foreground">Loading...</p>;
  }

  const isReview = invoice.status === "needs_review";
  const isUploaded = invoice.status === "uploaded";

  function setField(lineId: string, field: keyof Decision, value: string) {
    setEdits((e) => ({ ...e, [lineId]: { ...(e[lineId] ?? {}), [field]: value } }));
  }

  function handleConfirmAll() {
    setSubmitError(null);
    if (!invoice) return;
    const items: InvoiceConfirmDecision[] = [];
    for (const line of invoice.items) {
      const dec = decisions[line.id];
      if (!dec) continue;
      if (dec.action === "reject") {
        items.push({
          line_item_id: line.id,
          action: "reject",
          notes: dec.notes || undefined,
        });
        continue;
      }
      const qty = Number(dec.quantity);
      if (!dec.productId || !dec.unit || !Number.isFinite(qty) || qty <= 0) {
        setSubmitError(
          `Line ${line.line_number}: pick a product and enter a quantity > 0 with unit, ` +
            "or change the action to Reject.",
        );
        return;
      }
      items.push({
        line_item_id: line.id,
        action: "confirm",
        confirmed_product_id: dec.productId,
        quantity: qty,
        unit: dec.unit,
        unit_cost: dec.unitCost === "" ? null : Number(dec.unitCost),
        expiry_date: dec.expiryDate || null,
        batch_code: dec.batchCode || null,
        notes: dec.notes || null,
      });
    }
    confirmMut.mutate({ items });
  }

  return (
    <div className="space-y-4">
      <div className="flex items-center justify-between">
        <div>
          <Link
            href={`/app/${rid}/invoices`}
            className="text-sm text-muted-foreground hover:underline"
          >
            ← Invoices
          </Link>
          <h1 className="mt-2 text-2xl font-semibold">
            {invoice.supplier_name_raw ?? "Invoice"}
          </h1>
          <p className="text-sm text-muted-foreground">
            {invoice.invoice_number ?? "—"} · {invoice.invoice_date ?? "—"}
          </p>
        </div>
        <div className="flex items-center gap-3">
          {statusBadge(invoice.status)}
          {isUploaded && (
            <Button
              onClick={() => processMut.mutate()}
              disabled={processMut.isPending || !token}
            >
              {processMut.isPending ? "Processing..." : "Process with OCR"}
            </Button>
          )}
        </div>
      </div>

      {processMut.isError && (
        <p className="rounded-md bg-destructive/10 p-3 text-sm text-destructive">
          OCR failed: {(processMut.error as Error).message}
        </p>
      )}

      <div className="grid grid-cols-1 gap-4 lg:grid-cols-2">
        <FilePane invoice={invoice} />

        <div className="space-y-4">
          {isUploaded && (
            <p className="rounded-md border p-3 text-sm text-muted-foreground">
              File uploaded. Click <span className="font-medium">Process with OCR</span> to
              extract line items.
            </p>
          )}

          {invoice.status === "processing" && (
            <p className="rounded-md border p-3 text-sm text-muted-foreground">
              Processing... refresh in a few seconds.
            </p>
          )}

          {(isReview || invoice.status === "confirmed" || invoice.status === "rejected") &&
            invoice.items.length === 0 && (
              <p className="rounded-md border p-3 text-sm text-muted-foreground">
                No line items were extracted from this invoice.
              </p>
            )}

          {(isReview || invoice.status === "confirmed" || invoice.status === "rejected") &&
            invoice.items.map((line) => (
              <LineCard
                key={line.id}
                line={line}
                products={products}
                productsById={productsById}
                decision={decisions[line.id]}
                editable={isReview}
                onChange={(field, value) => setField(line.id, field, value)}
              />
            ))}

          {isReview && (
            <div className="space-y-2">
              {submitError && (
                <p className="rounded-md bg-destructive/10 p-3 text-sm text-destructive">
                  {submitError}
                </p>
              )}
              {confirmMut.isError && (
                <p className="rounded-md bg-destructive/10 p-3 text-sm text-destructive">
                  Confirm failed: {(confirmMut.error as Error).message}
                </p>
              )}
              <div className="flex justify-end">
                <Button
                  onClick={handleConfirmAll}
                  disabled={confirmMut.isPending || !token}
                >
                  {confirmMut.isPending ? "Confirming..." : "Confirm all"}
                </Button>
              </div>
            </div>
          )}
        </div>
      </div>
    </div>
  );
}

function FilePane({ invoice }: { invoice: InvoiceWithItems }) {
  if (!invoice.download_url) {
    return (
      <div className="flex h-96 items-center justify-center rounded-md border text-sm text-muted-foreground">
        File preview unavailable.
      </div>
    );
  }
  if (isImageMime(invoice.file_path)) {
    return (
      <a
        href={invoice.download_url}
        target="_blank"
        rel="noopener noreferrer"
        className="block"
      >
        {/* eslint-disable-next-line @next/next/no-img-element */}
        <img
          src={invoice.download_url}
          alt={`Invoice ${invoice.invoice_number ?? ""}`}
          className="max-h-[80vh] w-full rounded-md border object-contain"
        />
      </a>
    );
  }
  return (
    <iframe
      src={invoice.download_url}
      title="Invoice preview"
      className="h-[80vh] w-full rounded-md border"
    />
  );
}

function LineCard({
  line,
  products,
  productsById,
  decision,
  editable,
  onChange,
}: {
  line: InvoiceLineItem;
  products: Product[];
  productsById: Record<string, Product>;
  decision: Decision | undefined;
  editable: boolean;
  onChange: (field: keyof Decision, value: string) => void;
}) {
  const finalStatusBadge =
    line.status === "confirmed" ? (
      <Badge className="bg-green-100 text-green-800">Confirmed</Badge>
    ) : line.status === "rejected" ? (
      <Badge variant="destructive">Rejected</Badge>
    ) : null;

  if (!editable) {
    const product =
      line.confirmed_product_id != null
        ? productsById[line.confirmed_product_id]
        : line.suggested_product_id != null
          ? productsById[line.suggested_product_id]
          : null;
    return (
      <div className="rounded-md border p-3">
        <div className="flex items-start justify-between">
          <div>
            <p className="text-xs text-muted-foreground">Line {line.line_number}</p>
            <p className="font-medium">{line.raw_text ?? "—"}</p>
            <p className="text-xs text-muted-foreground">
              {product ? product.name : "No product matched"} · {line.quantity ?? "—"}{" "}
              {line.unit ?? ""}
            </p>
          </div>
          {finalStatusBadge}
        </div>
      </div>
    );
  }

  const dec = decision;
  if (!dec) return null;

  return (
    <div className="space-y-3 rounded-md border p-3">
      <div className="flex items-start justify-between">
        <div>
          <p className="text-xs text-muted-foreground">Line {line.line_number}</p>
          <p className="font-medium">{line.raw_text ?? "—"}</p>
        </div>
        <Select
          value={dec.action}
          onValueChange={(v) => onChange("action", v)}
        >
          <SelectTrigger className="w-32">
            <SelectValue />
          </SelectTrigger>
          <SelectContent>
            <SelectItem value="confirm">Confirm</SelectItem>
            <SelectItem value="reject">Reject</SelectItem>
          </SelectContent>
        </Select>
      </div>

      {dec.action === "confirm" && (
        <div className="grid grid-cols-1 gap-3 sm:grid-cols-2">
          <div className="col-span-2 space-y-1">
            <Label className="text-xs">Product</Label>
            <Select value={dec.productId} onValueChange={(v) => onChange("productId", v)}>
              <SelectTrigger>
                <SelectValue placeholder="Pick a product..." />
              </SelectTrigger>
              <SelectContent>
                {products.map((p) => (
                  <SelectItem key={p.id} value={p.id}>
                    {p.name} ({p.unit})
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>
          </div>
          <div className="space-y-1">
            <Label className="text-xs">Quantity</Label>
            <Input
              type="number"
              step="0.001"
              min="0"
              value={dec.quantity}
              onChange={(e) => onChange("quantity", e.target.value)}
            />
          </div>
          <div className="space-y-1">
            <Label className="text-xs">Unit</Label>
            <Input value={dec.unit} onChange={(e) => onChange("unit", e.target.value)} />
          </div>
          <div className="space-y-1">
            <Label className="text-xs">Unit cost</Label>
            <Input
              type="number"
              step="0.0001"
              min="0"
              value={dec.unitCost}
              onChange={(e) => onChange("unitCost", e.target.value)}
            />
          </div>
          <div className="space-y-1">
            <Label className="text-xs">Expiry date</Label>
            <Input
              type="date"
              value={dec.expiryDate}
              onChange={(e) => onChange("expiryDate", e.target.value)}
            />
          </div>
          <div className="col-span-2 space-y-1">
            <Label className="text-xs">Batch code</Label>
            <Input
              value={dec.batchCode}
              onChange={(e) => onChange("batchCode", e.target.value)}
            />
          </div>
        </div>
      )}

      <div className="space-y-1">
        <Label className="text-xs">Notes</Label>
        <Input value={dec.notes} onChange={(e) => onChange("notes", e.target.value)} />
      </div>
    </div>
  );
}
