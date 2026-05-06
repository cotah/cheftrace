"use client";

import { useQuery } from "@tanstack/react-query";
import { useToken } from "@/hooks/use-token";
import { stockMovementsApi, productsApi } from "@/lib/api/resources";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";

const kindColor: Record<string, string> = {
  receive: "bg-green-100 text-green-800",
  manual_in: "bg-blue-100 text-blue-800",
  manual_out: "bg-orange-100 text-orange-800",
  adjustment: "bg-purple-100 text-purple-800",
  discard: "bg-red-100 text-red-800",
  consume: "bg-gray-100 text-gray-800",
};

export default function MovementsPage({
  params,
}: {
  params: { restaurantId: string };
}) {
  const rid = params.restaurantId;
  const token = useToken();

  const { data: movements = [], isLoading } = useQuery({
    queryKey: ["stock-movements", rid],
    queryFn: () => stockMovementsApi.list(rid, token!),
    enabled: !!token,
  });

  const { data: products = [] } = useQuery({
    queryKey: ["products", rid],
    queryFn: () => productsApi.list(rid, token!),
    enabled: !!token,
  });

  const productMap = Object.fromEntries(products.map((p) => [p.id, p.name]));

  return (
    <div className="space-y-6">
      <h1 className="text-2xl font-semibold">Movement log</h1>
      <p className="text-sm text-muted-foreground">
        All movements are immutable. Corrections are new movements.
      </p>

      {isLoading ? (
        <p className="text-muted-foreground">Loading...</p>
      ) : movements.length === 0 ? (
        <p className="text-muted-foreground">No movements yet.</p>
      ) : (
        <Table>
          <TableHeader>
            <TableRow>
              <TableHead>Date</TableHead>
              <TableHead>Product</TableHead>
              <TableHead>Type</TableHead>
              <TableHead className="text-right">Qty</TableHead>
              <TableHead>Unit</TableHead>
              <TableHead>Reason</TableHead>
            </TableRow>
          </TableHeader>
          <TableBody>
            {movements.map((m) => (
              <TableRow key={m.id}>
                <TableCell className="text-sm text-muted-foreground">
                  {new Date(m.created_at).toLocaleDateString("en-IE")}
                </TableCell>
                <TableCell className="font-medium">
                  {productMap[m.product_id] ?? m.product_id.slice(0, 8)}
                </TableCell>
                <TableCell>
                  <span
                    className={`rounded px-2 py-0.5 text-xs font-medium ${
                      kindColor[m.kind] ?? "bg-gray-100 text-gray-800"
                    }`}
                  >
                    {m.kind.replace("_", " ")}
                  </span>
                </TableCell>
                <TableCell className="text-right font-mono">
                  {m.quantity > 0 ? `+${m.quantity}` : m.quantity}
                </TableCell>
                <TableCell>{m.unit}</TableCell>
                <TableCell className="text-sm text-muted-foreground">
                  {m.reason ?? "-"}
                </TableCell>
              </TableRow>
            ))}
          </TableBody>
        </Table>
      )}
    </div>
  );
}
