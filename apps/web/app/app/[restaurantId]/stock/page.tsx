"use client";

import { useQuery } from "@tanstack/react-query";
import { useToken } from "@/hooks/use-token";
import { stockLotsApi, productsApi } from "@/lib/api/resources";
import { useRestaurant } from "@/hooks/use-restaurant";
import Link from "next/link";
import { Button } from "@/components/ui/button";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";
import { Badge } from "@/components/ui/badge";
import type { StockLot } from "@/lib/api/types";

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

export default function StockPage({
  params,
}: {
  params: { restaurantId: string };
}) {
  const rid = params.restaurantId;
  const token = useToken();
  const { active } = useRestaurant();

  const { data: lots = [], isLoading } = useQuery({
    queryKey: ["stock-lots", rid],
    queryFn: () => stockLotsApi.list(rid, token!),
    enabled: !!token,
  });

  const { data: products = [] } = useQuery({
    queryKey: ["products", rid],
    queryFn: () => productsApi.list(rid, token!),
    enabled: !!token,
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
        <Table>
          <TableHeader>
            <TableRow>
              <TableHead>Product</TableHead>
              <TableHead>Remaining</TableHead>
              <TableHead>Unit</TableHead>
              <TableHead>Expiry</TableHead>
              <TableHead>Received</TableHead>
            </TableRow>
          </TableHeader>
          <TableBody>
            {activeLots.map((lot) => (
              <TableRow key={lot.id}>
                <TableCell className="font-medium">
                  {productMap[lot.product_id] ?? lot.product_id}
                </TableCell>
                <TableCell>{lot.quantity_remaining}</TableCell>
                <TableCell>{lot.unit}</TableCell>
                <TableCell>{expiryBadge(lot, warningDays, criticalDays)}</TableCell>
                <TableCell>{lot.received_date}</TableCell>
              </TableRow>
            ))}
          </TableBody>
        </Table>
      )}
    </div>
  );
}
