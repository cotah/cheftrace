"use client";

import { use, useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import Link from "next/link";
import { useToken } from "@/hooks/use-token";
import { productsApi, purchaseListsApi, suppliersApi } from "@/lib/api/resources";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
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
import type { Product, PurchaseListItem } from "@/lib/api/types";

function listStatusBadge(status: string) {
  if (status === "draft") return <Badge variant="outline">Draft</Badge>;
  if (status === "sent") return <Badge variant="secondary">Sent</Badge>;
  if (status === "partially_received")
    return (
      <Badge className="bg-amber-100 text-amber-800 hover:bg-amber-100">
        Partially received
      </Badge>
    );
  if (status === "received")
    return <Badge className="bg-green-100 text-green-800 hover:bg-green-100">Received</Badge>;
  return <Badge variant="outline">{status}</Badge>;
}

function itemStatusBadge(status: string) {
  if (status === "pending") return <Badge variant="outline">Pending</Badge>;
  if (status === "partial")
    return <Badge className="bg-amber-100 text-amber-800 hover:bg-amber-100">Partial</Badge>;
  if (status === "received")
    return <Badge className="bg-green-100 text-green-800 hover:bg-green-100">Received</Badge>;
  if (status === "not_received") return <Badge variant="destructive">Not received</Badge>;
  return <Badge variant="outline">{status}</Badge>;
}

function AddItemDialog({
  rid,
  listId,
  token,
  products,
}: {
  rid: string;
  listId: string;
  token: string;
  products: Product[];
}) {
  const qc = useQueryClient();
  const [open, setOpen] = useState(false);
  const [productId, setProductId] = useState("");
  const [quantity, setQuantity] = useState("");
  const [unitCost, setUnitCost] = useState("");

  const selected = products.find((p) => p.id === productId);

  const addMutation = useMutation({
    mutationFn: () =>
      purchaseListsApi.addItem(
        rid,
        listId,
        {
          product_id: productId,
          quantity_ordered: parseFloat(quantity),
          unit: selected!.unit,
          unit_cost_estimate: unitCost ? parseFloat(unitCost) : null,
        },
        token,
      ),
    onSuccess: () => {
      void qc.invalidateQueries({ queryKey: ["purchase-list", rid, listId] });
      setOpen(false);
      setProductId("");
      setQuantity("");
      setUnitCost("");
    },
  });

  return (
    <Dialog open={open} onOpenChange={setOpen}>
      <DialogTrigger asChild>
        <Button size="sm">Add item</Button>
      </DialogTrigger>
      <DialogContent>
        <DialogHeader>
          <DialogTitle>Add item</DialogTitle>
        </DialogHeader>
        <div className="space-y-4 pt-2">
          <div className="space-y-2">
            <Label>Product</Label>
            <Select value={productId} onValueChange={setProductId}>
              <SelectTrigger>
                <SelectValue placeholder="Select product" />
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
              <Label>Estimated cost / unit</Label>
              <Input
                type="number"
                step="0.0001"
                value={unitCost}
                onChange={(e) => setUnitCost(e.target.value)}
                placeholder="optional"
              />
            </div>
          </div>
          <Button
            className="w-full"
            disabled={!productId || !quantity || addMutation.isPending}
            onClick={() => addMutation.mutate()}
          >
            {addMutation.isPending ? "Adding..." : "Add item"}
          </Button>
          {addMutation.isError && (
            <p className="text-sm text-destructive">{addMutation.error.message}</p>
          )}
        </div>
      </DialogContent>
    </Dialog>
  );
}

function ReceiveItemDialog({
  rid,
  listId,
  item,
  productName,
  expiryRequired,
  token,
}: {
  rid: string;
  listId: string;
  item: PurchaseListItem;
  productName: string;
  expiryRequired: boolean;
  token: string;
}) {
  const qc = useQueryClient();
  const [open, setOpen] = useState(false);
  const remainingToReceive =
    item.quantity_ordered - (item.quantity_received ?? 0);
  const [quantity, setQuantity] = useState(String(remainingToReceive));
  const [expiryDate, setExpiryDate] = useState("");
  const [unitCost, setUnitCost] = useState(
    item.unit_cost_estimate ? String(item.unit_cost_estimate) : "",
  );

  const receiveMutation = useMutation({
    mutationFn: () =>
      purchaseListsApi.receiveItem(
        rid,
        listId,
        item.id,
        {
          quantity_received: parseFloat(quantity),
          expiry_date: expiryDate || null,
          unit_cost: unitCost ? parseFloat(unitCost) : null,
        },
        token,
      ),
    onSuccess: () => {
      void qc.invalidateQueries({ queryKey: ["purchase-list", rid, listId] });
      void qc.invalidateQueries({ queryKey: ["stock-lots", rid] });
      void qc.invalidateQueries({ queryKey: ["dashboard", rid] });
      setOpen(false);
    },
  });

  return (
    <Dialog open={open} onOpenChange={setOpen}>
      <DialogTrigger asChild>
        <Button variant="outline" size="sm">
          Receive
        </Button>
      </DialogTrigger>
      <DialogContent>
        <DialogHeader>
          <DialogTitle>Receive — {productName}</DialogTitle>
        </DialogHeader>
        <div className="space-y-4 pt-2">
          <p className="text-sm text-muted-foreground">
            Ordered: {item.quantity_ordered} {item.unit}
            {item.quantity_received !== null && (
              <> · Already received: {item.quantity_received} {item.unit}</>
            )}
          </p>
          <div className="grid grid-cols-1 gap-3 sm:grid-cols-2">
            <div className="space-y-2">
              <Label>Quantity received</Label>
              <Input
                type="number"
                min="0"
                step="0.001"
                value={quantity}
                onChange={(e) => setQuantity(e.target.value)}
              />
            </div>
            <div className="space-y-2">
              <Label>
                Expiry date
                {expiryRequired && <span className="text-destructive ml-1">*</span>}
              </Label>
              <Input
                type="date"
                value={expiryDate}
                onChange={(e) => setExpiryDate(e.target.value)}
              />
            </div>
          </div>
          <div className="space-y-2">
            <Label>Actual cost / unit (optional)</Label>
            <Input
              type="number"
              step="0.0001"
              value={unitCost}
              onChange={(e) => setUnitCost(e.target.value)}
              placeholder="Leave blank to use estimate"
            />
          </div>
          <Button
            className="w-full"
            disabled={
              !quantity ||
              parseFloat(quantity) <= 0 ||
              (expiryRequired && !expiryDate) ||
              receiveMutation.isPending
            }
            onClick={() => receiveMutation.mutate()}
          >
            {receiveMutation.isPending ? "Saving..." : "Confirm receipt"}
          </Button>
          {receiveMutation.isError && (
            <p className="text-sm text-destructive">{receiveMutation.error.message}</p>
          )}
        </div>
      </DialogContent>
    </Dialog>
  );
}

export default function PurchaseListDetailPage({
  params,
}: {
  params: Promise<{ restaurantId: string; id: string }>;
}) {
  const { restaurantId: rid, id: listId } = use(params);
  const token = useToken();
  const qc = useQueryClient();

  const { data: list, isLoading } = useQuery({
    queryKey: ["purchase-list", rid, listId],
    queryFn: () => purchaseListsApi.get(rid, listId, token!),
    enabled: !!rid && !!listId && !!token,
  });

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

  const sendMutation = useMutation({
    mutationFn: () => purchaseListsApi.send(rid, listId, token!),
    onSuccess: () => {
      void qc.invalidateQueries({ queryKey: ["purchase-list", rid, listId] });
      void qc.invalidateQueries({ queryKey: ["purchase-lists", rid] });
    },
  });

  const deleteItemMutation = useMutation({
    mutationFn: (itemId: string) =>
      purchaseListsApi.deleteItem(rid, listId, itemId, token!),
    onSuccess: () => {
      void qc.invalidateQueries({ queryKey: ["purchase-list", rid, listId] });
    },
  });

  if (isLoading) {
    return <p className="text-muted-foreground">Loading...</p>;
  }
  if (!list) {
    return <p className="text-sm text-destructive">List not found.</p>;
  }

  const productMap = Object.fromEntries(products.map((p) => [p.id, p]));
  const supplierMap = Object.fromEntries(suppliers.map((s) => [s.id, s.name]));
  const isDraft = list.status === "draft";
  const canReceive = list.status === "sent" || list.status === "partially_received";

  return (
    <div className="space-y-6">
      <div className="flex items-start justify-between">
        <div>
          <Link
            href={`/app/${rid}/purchase-lists`}
            className="text-sm text-muted-foreground hover:underline"
          >
            ← All lists
          </Link>
          <h1 className="text-2xl font-semibold mt-2 capitalize">
            {list.type.replace("_", " ")} order
          </h1>
          <div className="flex items-center gap-2 mt-1">
            {listStatusBadge(list.status)}
            {list.sent_at && (
              <span className="text-xs text-muted-foreground">
                Sent {new Date(list.sent_at).toLocaleDateString("en-IE")}
              </span>
            )}
          </div>
        </div>
        {isDraft && (
          <Button
            disabled={list.items.length === 0 || sendMutation.isPending}
            onClick={() => sendMutation.mutate()}
          >
            {sendMutation.isPending ? "Sending..." : "Mark as sent"}
          </Button>
        )}
      </div>

      {sendMutation.isError && (
        <p className="text-sm text-destructive">{sendMutation.error.message}</p>
      )}

      {list.notes && (
        <Card>
          <CardHeader className="pb-2">
            <CardTitle className="text-sm">Notes</CardTitle>
          </CardHeader>
          <CardContent>
            <p className="text-sm">{list.notes}</p>
          </CardContent>
        </Card>
      )}

      <Card>
        <CardHeader className="flex flex-row items-center justify-between pb-2">
          <CardTitle className="text-base">Items</CardTitle>
          {isDraft && token && (
            <AddItemDialog
              rid={rid}
              listId={listId}
              token={token}
              products={products}
            />
          )}
        </CardHeader>
        <CardContent>
          {list.items.length === 0 ? (
            <p className="text-sm text-muted-foreground py-4">No items yet.</p>
          ) : (
            <div className="overflow-x-auto">
              <Table>
                <TableHeader>
                  <TableRow>
                    <TableHead>Product</TableHead>
                    <TableHead className="text-right">Ordered</TableHead>
                    <TableHead className="text-right">Received</TableHead>
                    <TableHead>Unit</TableHead>
                    <TableHead>Status</TableHead>
                    <TableHead></TableHead>
                  </TableRow>
                </TableHeader>
                <TableBody>
                  {list.items.map((item) => {
                    const product = productMap[item.product_id];
                    const productName = product?.name ?? item.product_id.slice(0, 8);
                    const supplierName = item.supplier_id
                      ? supplierMap[item.supplier_id]
                      : null;
                    return (
                      <TableRow key={item.id}>
                        <TableCell>
                          <div className="font-medium">{productName}</div>
                          {supplierName && (
                            <div className="text-xs text-muted-foreground">
                              from {supplierName}
                            </div>
                          )}
                        </TableCell>
                        <TableCell className="text-right font-mono">
                          {item.quantity_ordered}
                        </TableCell>
                        <TableCell className="text-right font-mono">
                          {item.quantity_received ?? "—"}
                        </TableCell>
                        <TableCell>{item.unit}</TableCell>
                        <TableCell>{itemStatusBadge(item.status)}</TableCell>
                        <TableCell className="text-right space-x-2">
                          {isDraft && (
                            <Button
                              variant="ghost"
                              size="sm"
                              disabled={deleteItemMutation.isPending}
                              onClick={() => deleteItemMutation.mutate(item.id)}
                            >
                              Remove
                            </Button>
                          )}
                          {canReceive && item.status !== "received" && token && (
                            <ReceiveItemDialog
                              rid={rid}
                              listId={listId}
                              item={item}
                              productName={productName}
                              expiryRequired={product?.expiry_required ?? false}
                              token={token}
                            />
                          )}
                        </TableCell>
                      </TableRow>
                    );
                  })}
                </TableBody>
              </Table>
            </div>
          )}
        </CardContent>
      </Card>
    </div>
  );
}
