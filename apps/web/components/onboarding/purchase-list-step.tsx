"use client";

import { useState } from "react";
import { purchaseListsApi } from "@/lib/api/resources";
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

const TYPES = [
  { value: "food", label: "Food" },
  { value: "beverage", label: "Beverage" },
  { value: "non_food", label: "Non-food" },
  { value: "mixed", label: "Mixed" },
];

interface Props {
  restaurantId: string;
  token: string;
  onComplete: () => void;
  onSkip: () => void;
}

export function PurchaseListStep({
  restaurantId,
  token,
  onComplete,
  onSkip,
}: Props) {
  const [type, setType] = useState("food");
  const [notes, setNotes] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);

  async function handleCreate() {
    setError(null);
    setLoading(true);
    try {
      await purchaseListsApi.create(
        restaurantId,
        { type, notes: notes || null },
        token,
      );
      onComplete();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Something went wrong");
    } finally {
      setLoading(false);
    }
  }

  return (
    <div className="space-y-4">
      <div>
        <h2 className="text-lg font-semibold">Create your first purchase list</h2>
        <p className="text-sm text-muted-foreground mt-1">
          Optional — start a draft order now, or skip and create later.
        </p>
      </div>
      {error && <p className="text-sm text-destructive">{error}</p>}
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
          placeholder="Weekly order, supplier preference, etc."
          value={notes}
          onChange={(e) => setNotes(e.target.value)}
        />
      </div>
      <div className="flex gap-2 pt-2">
        <Button variant="outline" className="flex-1" onClick={onSkip} disabled={loading}>
          Skip
        </Button>
        <Button className="flex-1" disabled={loading} onClick={() => void handleCreate()}>
          {loading ? "Creating..." : "Create draft list"}
        </Button>
      </div>
    </div>
  );
}
