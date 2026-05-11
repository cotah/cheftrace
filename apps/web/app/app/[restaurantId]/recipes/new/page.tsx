"use client";

import { use, useState } from "react";
import { useMutation } from "@tanstack/react-query";
import { useRouter } from "next/navigation";
import { useToken } from "@/hooks/use-token";
import { recipesApi } from "@/lib/api/resources";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";

export default function NewRecipePage({
  params,
}: {
  params: Promise<{ restaurantId: string }>;
}) {
  const { restaurantId: rid } = use(params);
  const token = useToken();
  const router = useRouter();

  const [name, setName] = useState("");
  const [yieldQuantity, setYieldQuantity] = useState("");
  const [yieldUnit, setYieldUnit] = useState("portion");
  const [prepMinutes, setPrepMinutes] = useState("");
  const [cookMinutes, setCookMinutes] = useState("");
  const [instructions, setInstructions] = useState("");

  const createMutation = useMutation({
    mutationFn: () =>
      recipesApi.create(
        rid,
        {
          name,
          yield_quantity: parseFloat(yieldQuantity),
          yield_unit: yieldUnit,
          prep_time_minutes: prepMinutes ? parseInt(prepMinutes, 10) : null,
          cook_time_minutes: cookMinutes ? parseInt(cookMinutes, 10) : null,
          instructions: instructions || null,
        },
        token!,
      ),
    onSuccess: (recipe) => {
      router.push(`/app/${rid}/recipes/${recipe.id}`);
    },
  });

  const canSubmit =
    name.trim().length > 0 &&
    yieldQuantity.length > 0 &&
    parseFloat(yieldQuantity) > 0 &&
    yieldUnit.trim().length > 0 &&
    !!rid &&
    !!token;

  return (
    <div className="max-w-xl space-y-6">
      <h1 className="text-2xl font-semibold">New recipe</h1>
      <Card>
        <CardHeader>
          <CardTitle className="text-base">Details</CardTitle>
        </CardHeader>
        <CardContent className="space-y-4">
          <div className="space-y-2">
            <Label>Name</Label>
            <Input
              value={name}
              onChange={(e) => setName(e.target.value)}
              placeholder="e.g. Tomato sauce"
              maxLength={200}
            />
          </div>
          <div className="grid grid-cols-1 gap-3 sm:grid-cols-2">
            <div className="space-y-2">
              <Label>Yield quantity</Label>
              <Input
                type="number"
                min="0"
                step="0.001"
                value={yieldQuantity}
                onChange={(e) => setYieldQuantity(e.target.value)}
                placeholder="0"
              />
            </div>
            <div className="space-y-2">
              <Label>Yield unit</Label>
              <Input
                value={yieldUnit}
                onChange={(e) => setYieldUnit(e.target.value)}
                placeholder="portion, L, batch..."
                maxLength={50}
              />
            </div>
          </div>
          <div className="grid grid-cols-1 gap-3 sm:grid-cols-2">
            <div className="space-y-2">
              <Label>Prep time (min)</Label>
              <Input
                type="number"
                min="0"
                step="1"
                value={prepMinutes}
                onChange={(e) => setPrepMinutes(e.target.value)}
                placeholder="optional"
              />
            </div>
            <div className="space-y-2">
              <Label>Cook time (min)</Label>
              <Input
                type="number"
                min="0"
                step="1"
                value={cookMinutes}
                onChange={(e) => setCookMinutes(e.target.value)}
                placeholder="optional"
              />
            </div>
          </div>
          <div className="space-y-2">
            <Label>Instructions (optional)</Label>
            <textarea
              className="flex min-h-[100px] w-full rounded-md border border-input bg-background px-3 py-2 text-sm shadow-sm placeholder:text-muted-foreground focus-visible:outline-none focus-visible:ring-1 focus-visible:ring-ring disabled:cursor-not-allowed disabled:opacity-50"
              value={instructions}
              onChange={(e) => setInstructions(e.target.value)}
              placeholder="Cooking steps, plating notes..."
            />
          </div>
          <Button
            className="w-full"
            disabled={!canSubmit || createMutation.isPending}
            onClick={() => createMutation.mutate()}
          >
            {createMutation.isPending ? "Creating..." : "Create recipe"}
          </Button>
          {createMutation.isError && (
            <p className="text-sm text-destructive">
              {createMutation.error.message}
            </p>
          )}
          <p className="text-xs text-muted-foreground">
            You&apos;ll add ingredients on the next screen.
          </p>
        </CardContent>
      </Card>
    </div>
  );
}
