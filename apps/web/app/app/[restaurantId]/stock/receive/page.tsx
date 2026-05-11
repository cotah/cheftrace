"use client";

import { use, useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useRouter } from "next/navigation";
import { useToken } from "@/hooks/use-token";
import { productsApi, suppliersApi, stockLotsApi } from "@/lib/api/resources";
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
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";

export default function ReceivePage({
  params,
}: {
  params: Promise<{ restaurantId: string }>;
}) {
  const { restaurantId: rid } = use(params);
  const token = useToken();
  const router = useRouter();
  const qc = useQueryClient();

  const [productId, setProductId] = useState("");
  const [supplierId, setSupplierId] = useState("");
  const [quantity, setQuantity] = useState("");
  const [unit, setUnit] = useState("unit");
  const [expiryDate, setExpiryDate] = useState("");
  const [notes, setNotes] = useState("");

  const { data: products = [] } = useQuery({
    queryKey: ["products", rid],
    queryFn: () => productsApi.list(rid, token!),
    enabled: !!rid && !!token,
  });

  const { data: suppliers = [] } = useQuery({
    queryKey: ["suppliers", rid],
    queryFn: () => suppliersApi.list(rid, token!),
    enabled: !!rid && !!token,
  });

  const selectedProduct = products.find((p) => p.id === productId);

  const receiveMutation = useMutation({
    mutationFn: () =>
      stockLotsApi.receive(
        rid,
        {
          product_id: productId,
          supplier_id: supplierId || null,
          quantity_received: parseFloat(quantity),
          unit,
          expiry_date: expiryDate || null,
          notes: notes || null,
        },
        token!,
      ),
    onSuccess: () => {
      void qc.invalidateQueries({ queryKey: ["stock-lots", rid] });
      router.push(`/app/${rid}/stock`);
    },
  });

  return (
    <div className="max-w-lg space-y-6">
      <h1 className="text-2xl font-semibold">Receive delivery</h1>
      <Card>
        <CardHeader>
          <CardTitle className="text-base">Lot details</CardTitle>
        </CardHeader>
        <CardContent className="space-y-4">
          <div className="space-y-2">
            <Label>Product</Label>
            <Select
              value={productId}
              onValueChange={(v) => {
                setProductId(v);
                const p = products.find((x) => x.id === v);
                if (p) setUnit(p.unit);
              }}
            >
              <SelectTrigger>
                <SelectValue placeholder="Select product" />
              </SelectTrigger>
              <SelectContent>
                {products.map((p) => (
                  <SelectItem key={p.id} value={p.id}>
                    {p.name}
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>
          </div>

          <div className="grid grid-cols-1 gap-3 sm:grid-cols-2">
            <div className="space-y-2">
              <Label>Quantity</Label>
              <Input
                type="number"
                min="0"
                step="0.001"
                value={quantity}
                onChange={(e) => setQuantity(e.target.value)}
                placeholder="0"
              />
            </div>
            <div className="space-y-2">
              <Label>Unit</Label>
              <Input value={unit} readOnly className="bg-muted" />
            </div>
          </div>

          <div className="space-y-2">
            <Label>
              Expiry date
              {selectedProduct?.expiry_required && (
                <span className="text-destructive ml-1">*</span>
              )}
            </Label>
            <Input
              type="date"
              value={expiryDate}
              onChange={(e) => setExpiryDate(e.target.value)}
            />
          </div>

          {suppliers.length > 0 && (
            <div className="space-y-2">
              <Label>Supplier</Label>
              <Select value={supplierId} onValueChange={setSupplierId}>
                <SelectTrigger>
                  <SelectValue placeholder="Optional" />
                </SelectTrigger>
                <SelectContent>
                  {suppliers.map((s) => (
                    <SelectItem key={s.id} value={s.id}>
                      {s.name}
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
            </div>
          )}

          <div className="space-y-2">
            <Label>Notes</Label>
            <Input
              value={notes}
              onChange={(e) => setNotes(e.target.value)}
              placeholder="Optional"
            />
          </div>

          <Button
            className="w-full"
            disabled={
              !productId ||
              !quantity ||
              (selectedProduct?.expiry_required === true && !expiryDate) ||
              receiveMutation.isPending
            }
            onClick={() => receiveMutation.mutate()}
          >
            {receiveMutation.isPending ? "Saving..." : "Confirm receipt"}
          </Button>

          {receiveMutation.isError && (
            <p className="text-sm text-destructive">{receiveMutation.error.message}</p>
          )}
        </CardContent>
      </Card>
    </div>
  );
}
