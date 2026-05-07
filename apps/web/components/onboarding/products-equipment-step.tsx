"use client";

import { useState } from "react";
import { equipmentApi, productsApi } from "@/lib/api/resources";
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

const UNITS = ["kg", "g", "l", "ml", "unit"] as const;

const EQUIPMENT_TYPES = [
  { value: "fridge", label: "Fridge (0–5°C)", min: 0, max: 5 },
  { value: "freezer", label: "Freezer (-25 to -18°C)", min: -25, max: -18 },
  { value: "hot_hold", label: "Hot Hold (63–90°C)", min: 63, max: 90 },
  { value: "dry_store", label: "Dry Store", min: null, max: null },
  { value: "display", label: "Display (0–8°C)", min: 0, max: 8 },
  { value: "prep_table", label: "Prep Table (0–5°C)", min: 0, max: 5 },
  { value: "blast_chiller", label: "Blast Chiller", min: -18, max: 5 },
  { value: "other", label: "Other", min: null, max: null },
];

interface Props {
  restaurantId: string;
  token: string;
  onComplete: () => void;
  onSkip: () => void;
}

export function ProductsEquipmentStep({
  restaurantId,
  token,
  onComplete,
  onSkip,
}: Props) {
  const [productName, setProductName] = useState("");
  const [productUnit, setProductUnit] = useState<string>("unit");
  const [productExpiry, setProductExpiry] = useState(true);

  const [equipmentName, setEquipmentName] = useState("");
  const [equipmentType, setEquipmentType] = useState("");

  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);

  const hasProduct = productName.trim().length > 0;
  const hasEquipment = equipmentName.trim().length > 0 && equipmentType !== "";

  async function handleContinue() {
    if (!hasProduct && !hasEquipment) return;
    setError(null);
    setLoading(true);
    try {
      const tasks: Promise<unknown>[] = [];
      if (hasProduct) {
        tasks.push(
          productsApi.create(
            restaurantId,
            {
              name: productName,
              unit: productUnit,
              expiry_required: productExpiry,
            },
            token,
          ),
        );
      }
      if (hasEquipment) {
        const typeMeta = EQUIPMENT_TYPES.find((t) => t.value === equipmentType);
        tasks.push(
          equipmentApi.create(
            restaurantId,
            {
              name: equipmentName,
              equipment_type: equipmentType,
              min_temp: typeMeta?.min ?? null,
              max_temp: typeMeta?.max ?? null,
            },
            token,
          ),
        );
      }
      await Promise.all(tasks);
      onComplete();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Something went wrong");
    } finally {
      setLoading(false);
    }
  }

  return (
    <div className="space-y-5">
      <div>
        <h2 className="text-lg font-semibold">Add your first items</h2>
        <p className="text-sm text-muted-foreground mt-1">
          Optional — you can fill in one, both, or skip and add later.
        </p>
      </div>
      {error && <p className="text-sm text-destructive">{error}</p>}

      <div className="space-y-3">
        <h3 className="text-sm font-medium">First product</h3>
        <div className="space-y-2">
          <Label htmlFor="prod-name">Name</Label>
          <Input
            id="prod-name"
            placeholder="e.g. Chicken Breast"
            value={productName}
            onChange={(e) => setProductName(e.target.value)}
          />
        </div>
        <div className="grid grid-cols-2 gap-3">
          <div className="space-y-2">
            <Label>Unit</Label>
            <Select value={productUnit} onValueChange={setProductUnit}>
              <SelectTrigger>
                <SelectValue />
              </SelectTrigger>
              <SelectContent>
                {UNITS.map((u) => (
                  <SelectItem key={u} value={u}>
                    {u}
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>
          </div>
          <div className="flex items-end pb-2 gap-2">
            <input
              type="checkbox"
              id="prod-expiry"
              checked={productExpiry}
              onChange={(e) => setProductExpiry(e.target.checked)}
            />
            <Label htmlFor="prod-expiry" className="text-sm">
              Expiry required
            </Label>
          </div>
        </div>
      </div>

      <div className="space-y-3 border-t pt-4">
        <h3 className="text-sm font-medium">First equipment</h3>
        <div className="space-y-2">
          <Label htmlFor="eq-name">Name</Label>
          <Input
            id="eq-name"
            placeholder="e.g. Main Fridge"
            value={equipmentName}
            onChange={(e) => setEquipmentName(e.target.value)}
          />
        </div>
        <div className="space-y-2">
          <Label>Type</Label>
          <Select value={equipmentType} onValueChange={setEquipmentType}>
            <SelectTrigger>
              <SelectValue placeholder="Select type" />
            </SelectTrigger>
            <SelectContent>
              {EQUIPMENT_TYPES.map((t) => (
                <SelectItem key={t.value} value={t.value}>
                  {t.label}
                </SelectItem>
              ))}
            </SelectContent>
          </Select>
        </div>
      </div>

      <div className="flex gap-2 pt-2">
        <Button variant="outline" className="flex-1" onClick={onSkip} disabled={loading}>
          Skip
        </Button>
        <Button
          className="flex-1"
          disabled={loading || (!hasProduct && !hasEquipment)}
          onClick={() => void handleContinue()}
        >
          {loading ? "Saving..." : "Continue"}
        </Button>
      </div>
    </div>
  );
}
