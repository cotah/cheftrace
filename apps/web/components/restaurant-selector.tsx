"use client";

import { type Restaurant } from "@/hooks/use-restaurant";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";

interface Props {
  restaurants: Restaurant[];
  active: Restaurant | null;
  onSelect: (restaurant: Restaurant) => void;
}

export function RestaurantSelector({ restaurants, active, onSelect }: Props) {
  return (
    <Select
      value={active?.id ?? ""}
      onValueChange={(id) => {
        const r = restaurants.find((r) => r.id === id);
        if (r) onSelect(r);
      }}
    >
      <SelectTrigger className="w-[200px]">
        <SelectValue placeholder="Select restaurant" />
      </SelectTrigger>
      <SelectContent>
        {restaurants.map((r) => (
          <SelectItem key={r.id} value={r.id}>
            {r.name}
          </SelectItem>
        ))}
      </SelectContent>
    </Select>
  );
}
