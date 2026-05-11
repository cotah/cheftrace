"use client";

import { use } from "react";
import { useQuery } from "@tanstack/react-query";
import Link from "next/link";
import { useToken } from "@/hooks/use-token";
import { purchaseListsApi } from "@/lib/api/resources";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";

function statusBadge(status: string) {
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

export default function PurchaseListsPage({
  params,
}: {
  params: Promise<{ restaurantId: string }>;
}) {
  const { restaurantId: rid } = use(params);
  const token = useToken();

  const { data: lists = [], isLoading } = useQuery({
    queryKey: ["purchase-lists", rid],
    queryFn: () => purchaseListsApi.list(rid, token!),
    enabled: !!rid && !!token,
  });

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <h1 className="text-2xl font-semibold">Purchase Lists</h1>
        <Link href={`/app/${rid}/purchase-lists/new`}>
          <Button>New list</Button>
        </Link>
      </div>

      {isLoading ? (
        <p className="text-muted-foreground">Loading...</p>
      ) : lists.length === 0 ? (
        <p className="text-muted-foreground">
          No purchase lists yet. Click &quot;New list&quot; to create one.
        </p>
      ) : (
        <div className="overflow-x-auto">
          <Table>
            <TableHeader>
              <TableRow>
                <TableHead>Type</TableHead>
                <TableHead>Status</TableHead>
                <TableHead>Created</TableHead>
                <TableHead>Sent</TableHead>
                <TableHead></TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {lists.map((l) => (
                <TableRow key={l.id}>
                  <TableCell className="font-medium capitalize">
                    {l.type.replace("_", " ")}
                  </TableCell>
                  <TableCell>{statusBadge(l.status)}</TableCell>
                  <TableCell className="text-sm text-muted-foreground">
                    {new Date(l.created_at).toLocaleDateString("en-IE")}
                  </TableCell>
                  <TableCell className="text-sm text-muted-foreground">
                    {l.sent_at ? new Date(l.sent_at).toLocaleDateString("en-IE") : "—"}
                  </TableCell>
                  <TableCell>
                    <Link href={`/app/${rid}/purchase-lists/${l.id}`}>
                      <Button variant="outline" size="sm">
                        Open
                      </Button>
                    </Link>
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
