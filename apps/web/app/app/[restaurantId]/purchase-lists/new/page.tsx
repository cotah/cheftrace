"use client";

import { use, useState } from "react";
import { useMutation } from "@tanstack/react-query";
import { useRouter } from "next/navigation";
import { useToken } from "@/hooks/use-token";
import { purchaseListsApi } from "@/lib/api/resources";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";

const TYPES = [
  { value: "food", label: "Food" },
  { value: "beverage", label: "Beverage" },
  { value: "non_food", label: "Non-food" },
  { value: "mixed", label: "Mixed" },
];

export default function NewPurchaseListPage({
  params,
}: {
  params: Promise<{ restaurantId: string }>;
}) {
  const { restaurantId: rid } = use(params);
  const token = useToken();
  const router = useRouter();
  const [type, setType] = useState("food");
  const [notes, setNotes] = useState("");

  const createMutation = useMutation({
    mutationFn: () =>
      purchaseListsApi.create(rid, { type, notes: notes || null }, token!),
    onSuccess: (list) => {
      router.push(`/app/${rid}/purchase-lists/${list.id}`);
    },
  });

  return (
    <div className="max-w-lg space-y-6">
      <h1 className="text-2xl font-semibold">New purchase list</h1>
      <Card>
        <CardHeader>
          <CardTitle className="text-base">Details</CardTitle>
        </CardHeader>
        <CardContent className="space-y-4">
          <div className="space-y-2">
            <Label>Type</Label>
            <Select value={type} onValueChange={setType}>
              <SelectTrigger>
                <SelectValue />
              </SelectTrigger>
              <SelectContent>
                {TYPES.map((t) => (
                  <SelectItem key={t.value} value={t.value}>
                    {t.label}
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>
          </div>
          <div className="space-y-2">
            <Label>Notes (optional)</Label>
            <Input
              value={notes}
              onChange={(e) => setNotes(e.target.value)}
              placeholder="Weekly order, supplier preference, etc."
            />
          </div>
          <Button
            className="w-full"
            disabled={createMutation.isPending || !rid || !token}
            onClick={() => createMutation.mutate()}
          >
            {createMutation.isPending ? "Creating..." : "Create draft"}
          </Button>
          {createMutation.isError && (
            <p className="text-sm text-destructive">
              {createMutation.error.message}
            </p>
          )}
        </CardContent>
      </Card>
    </div>
  );
}
