"use client";

import { useState } from "react";
import { useMutation, useQueryClient } from "@tanstack/react-query";
import { recipesApi } from "@/lib/api/resources";
import type { RecipeProductionPreviewResponse } from "@/lib/api/types";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
  DialogTrigger,
} from "@/components/ui/dialog";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";

// Exported so a Vitest test can render the table state in isolation without
// having to spin up the dialog + mutation lifecycle.
export function ProducePreviewTable({
  preview,
}: {
  preview: RecipeProductionPreviewResponse;
}) {
  return (
    <Table>
      <TableHeader>
        <TableRow>
          <TableHead>Ingredient</TableHead>
          <TableHead className="text-right">Needed</TableHead>
          <TableHead className="text-right">Available</TableHead>
          <TableHead>Status</TableHead>
        </TableRow>
      </TableHeader>
      <TableBody>
        {preview.lines.map((line) => (
          <TableRow key={line.ingredient_id}>
            <TableCell>
              <div className="font-medium">{line.product_name}</div>
              {line.allocations.length > 0 && (
                <ul className="mt-1 space-y-0.5 text-xs text-muted-foreground">
                  {line.allocations.map((a) => (
                    <li key={a.lot_id}>
                      {a.quantity_from_lot} {a.unit} · expiry{" "}
                      {a.expiry_date ?? "—"}
                      {a.unit_cost !== null && (
                        <> · €{a.unit_cost}/{a.unit}</>
                      )}
                    </li>
                  ))}
                </ul>
              )}
            </TableCell>
            <TableCell className="text-right font-mono text-sm">
              {line.quantity_needed} {line.ingredient_unit}
            </TableCell>
            <TableCell className="text-right font-mono text-sm">
              {line.unit_mismatch ? (
                <span className="text-muted-foreground">—</span>
              ) : (
                <>
                  {line.available} {line.product_unit}
                </>
              )}
            </TableCell>
            <TableCell>
              {line.unit_mismatch ? (
                <Badge variant="destructive">
                  Unit mismatch ({line.ingredient_unit} vs {line.product_unit})
                </Badge>
              ) : line.shortage ? (
                <Badge className="bg-amber-100 text-amber-800 hover:bg-amber-100">
                  Shortage
                </Badge>
              ) : (
                <Badge className="bg-green-100 text-green-800 hover:bg-green-100">
                  OK
                </Badge>
              )}
            </TableCell>
          </TableRow>
        ))}
      </TableBody>
    </Table>
  );
}

export function ProduceDialog({
  rid,
  recipeId,
  recipeName,
  token,
  disabled,
  disabledReason,
}: {
  rid: string;
  recipeId: string;
  recipeName: string;
  token: string | null;
  disabled?: boolean;
  disabledReason?: string;
}) {
  const qc = useQueryClient();
  const [open, setOpen] = useState(false);
  const [batches, setBatches] = useState("1");
  const [notes, setNotes] = useState("");
  const [preview, setPreview] = useState<RecipeProductionPreviewResponse | null>(
    null,
  );

  const previewMutation = useMutation({
    mutationFn: () =>
      recipesApi.producePreview(rid, recipeId, parseFloat(batches), token!),
    onSuccess: (data) => setPreview(data),
  });

  const confirmMutation = useMutation({
    mutationFn: () =>
      recipesApi.produceConfirm(
        rid,
        recipeId,
        { batches: parseFloat(batches), notes: notes || null },
        token!,
      ),
    onSuccess: () => {
      // Production consumes stock, so anything that surfaces stock state
      // needs to refetch.
      void qc.invalidateQueries({ queryKey: ["stock-lots", rid] });
      void qc.invalidateQueries({ queryKey: ["stock-movements", rid] });
      void qc.invalidateQueries({ queryKey: ["dashboard", rid] });
      void qc.invalidateQueries({ queryKey: ["recipe", rid, recipeId] });
      reset();
      setOpen(false);
    },
  });

  function reset() {
    setBatches("1");
    setNotes("");
    setPreview(null);
    previewMutation.reset();
    confirmMutation.reset();
  }

  const batchesNumber = parseFloat(batches);
  const validBatches = !isNaN(batchesNumber) && batchesNumber > 0;
  const previewMatchesInput =
    preview !== null && Number(preview.batches) === batchesNumber;

  return (
    <Dialog
      open={open}
      onOpenChange={(o) => {
        if (confirmMutation.isPending) return;
        setOpen(o);
        if (!o) reset();
      }}
    >
      <DialogTrigger asChild>
        <Button
          disabled={disabled}
          title={disabled ? disabledReason : undefined}
        >
          Produce
        </Button>
      </DialogTrigger>
      <DialogContent className="max-w-2xl">
        <DialogHeader>
          <DialogTitle>Produce — {recipeName}</DialogTitle>
          <DialogDescription>
            Preview FEFO consumption, then confirm to deduct stock and record
            the production.
          </DialogDescription>
        </DialogHeader>

        <div className="space-y-4">
          <div className="grid grid-cols-[1fr_auto] gap-3 items-end">
            <div className="space-y-2">
              <Label>Batches</Label>
              <Input
                type="number"
                min="0"
                step="0.001"
                value={batches}
                onChange={(e) => {
                  setBatches(e.target.value);
                  setPreview(null);
                }}
              />
            </div>
            <Button
              variant="outline"
              disabled={!validBatches || previewMutation.isPending}
              onClick={() => previewMutation.mutate()}
            >
              {previewMutation.isPending ? "Loading..." : "Preview"}
            </Button>
          </div>

          {previewMutation.isError && (
            <p className="text-sm text-destructive">
              {previewMutation.error.message}
            </p>
          )}

          {preview && previewMatchesInput && (
            <div className="space-y-3">
              <ProducePreviewTable preview={preview} />
              <div className="space-y-2">
                <Label>Notes (optional)</Label>
                <Input
                  value={notes}
                  onChange={(e) => setNotes(e.target.value)}
                  placeholder="e.g. lunch service"
                />
              </div>
              {!preview.can_confirm && (
                <p className="text-sm text-amber-800">
                  Fix the issues above before confirming. Either receive more
                  stock or correct the ingredient unit.
                </p>
              )}
            </div>
          )}

          {confirmMutation.isError && (
            <p className="text-sm text-destructive">
              {confirmMutation.error.message}
            </p>
          )}
        </div>

        <DialogFooter>
          <Button
            variant="ghost"
            onClick={() => {
              if (!confirmMutation.isPending) {
                setOpen(false);
                reset();
              }
            }}
            disabled={confirmMutation.isPending}
          >
            Cancel
          </Button>
          <Button
            onClick={() => confirmMutation.mutate()}
            disabled={
              !preview ||
              !previewMatchesInput ||
              !preview.can_confirm ||
              confirmMutation.isPending
            }
            title={
              !preview
                ? "Preview first"
                : !previewMatchesInput
                  ? "Re-run preview after changing batches"
                  : !preview.can_confirm
                    ? "Fix shortages or unit mismatches"
                    : undefined
            }
          >
            {confirmMutation.isPending ? "Confirming..." : "Confirm"}
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}
