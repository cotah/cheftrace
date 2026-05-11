"use client";

import { use, useState } from "react";
import { useQuery } from "@tanstack/react-query";
import Link from "next/link";
import { useToken } from "@/hooks/use-token";
import { recipesApi } from "@/lib/api/resources";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
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

type ActiveFilter = "active" | "inactive" | "any";

const FILTER_TO_PARAM: Record<ActiveFilter, boolean | undefined> = {
  active: true,
  inactive: false,
  any: undefined,
};

export default function RecipesListPage({
  params,
}: {
  params: Promise<{ restaurantId: string }>;
}) {
  const { restaurantId: rid } = use(params);
  const token = useToken();
  const [filter, setFilter] = useState<ActiveFilter>("active");

  const { data: recipes = [], isLoading } = useQuery({
    queryKey: ["recipes", rid, filter],
    queryFn: () => recipesApi.list(rid, token!, FILTER_TO_PARAM[filter]),
    enabled: !!rid && !!token,
  });

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <h1 className="text-2xl font-semibold">Recipes</h1>
        <Link href={`/app/${rid}/recipes/new`}>
          <Button>New recipe</Button>
        </Link>
      </div>

      <div className="grid grid-cols-1 gap-3 sm:max-w-xs">
        <div className="space-y-1">
          <Label className="text-xs">Status</Label>
          <Select value={filter} onValueChange={(v) => setFilter(v as ActiveFilter)}>
            <SelectTrigger>
              <SelectValue />
            </SelectTrigger>
            <SelectContent>
              <SelectItem value="active">Active only</SelectItem>
              <SelectItem value="inactive">Inactive only</SelectItem>
              <SelectItem value="any">Any status</SelectItem>
            </SelectContent>
          </Select>
        </div>
      </div>

      {isLoading ? (
        <p className="text-muted-foreground">Loading...</p>
      ) : recipes.length === 0 ? (
        <p className="text-muted-foreground">
          No recipes match this filter. Click{" "}
          <span className="font-medium">New recipe</span> to create one.
        </p>
      ) : (
        <div className="overflow-x-auto">
          <Table>
            <TableHeader>
              <TableRow>
                <TableHead>Name</TableHead>
                <TableHead className="text-right">Yield</TableHead>
                <TableHead>Prep / cook</TableHead>
                <TableHead>Status</TableHead>
                <TableHead></TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {recipes.map((r) => (
                <TableRow key={r.id}>
                  <TableCell className="font-medium">{r.name}</TableCell>
                  <TableCell className="text-right font-mono text-sm">
                    {r.yield_quantity} {r.yield_unit}
                  </TableCell>
                  <TableCell className="text-sm text-muted-foreground">
                    {r.prep_time_minutes !== null || r.cook_time_minutes !== null
                      ? `${r.prep_time_minutes ?? 0} / ${r.cook_time_minutes ?? 0} min`
                      : "—"}
                  </TableCell>
                  <TableCell>
                    {r.is_active ? (
                      <Badge variant="secondary">Active</Badge>
                    ) : (
                      <Badge variant="outline">Inactive</Badge>
                    )}
                  </TableCell>
                  <TableCell>
                    <Link href={`/app/${rid}/recipes/${r.id}`}>
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
