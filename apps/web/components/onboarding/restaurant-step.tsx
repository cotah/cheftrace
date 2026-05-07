"use client";

import { useState } from "react";
import { api } from "@/lib/api/client";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";

interface Props {
  token: string;
  onComplete: (restaurantId: string) => void;
}

export function RestaurantStep({ token, onComplete }: Props) {
  const [name, setName] = useState("");
  const [city, setCity] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    setError(null);
    setLoading(true);
    try {
      const restaurant = await api.post<{ id: string }>(
        "/restaurants",
        { name, city, country: "IE" },
        token,
      );
      onComplete(restaurant.id);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Something went wrong");
    } finally {
      setLoading(false);
    }
  }

  return (
    <form onSubmit={handleSubmit} className="space-y-4">
      <div>
        <h2 className="text-lg font-semibold">Set up your restaurant</h2>
        <p className="text-sm text-muted-foreground mt-1">
          We need a few details to get started.
        </p>
      </div>
      {error && <p className="text-sm text-destructive">{error}</p>}
      <div className="space-y-2">
        <Label htmlFor="name">Restaurant name</Label>
        <Input
          id="name"
          type="text"
          placeholder="The Grand Café"
          value={name}
          onChange={(e) => setName(e.target.value)}
          required
        />
      </div>
      <div className="space-y-2">
        <Label htmlFor="city">City</Label>
        <Input
          id="city"
          type="text"
          placeholder="Dublin"
          value={city}
          onChange={(e) => setCity(e.target.value)}
        />
      </div>
      <Button type="submit" className="w-full" disabled={loading || !name}>
        {loading ? "Creating..." : "Continue"}
      </Button>
    </form>
  );
}
