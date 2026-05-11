"use client";

import { useCallback, useEffect, useState } from "react";
import { createClient } from "@/lib/supabase/client";
import { api } from "@/lib/api/client";

export interface Restaurant {
  id: string;
  name: string;
  city: string | null;
  country: string;
  timezone: string;
  currency: string;
  expiry_warning_days: number;
  critical_expiry_days: number;
  role?: string | null;
}

const STORAGE_KEY = "cheftrace_active_restaurant";

export function useRestaurant() {
  const [restaurants, setRestaurants] = useState<Restaurant[]>([]);
  const [active, setActive] = useState<Restaurant | null>(null);
  const [loading, setLoading] = useState(true);

  const loadRestaurants = useCallback(async () => {
    const supabase = createClient();
    const { data: { session } } = await supabase.auth.getSession();
    if (!session) {
      setLoading(false);
      return;
    }
    try {
      const data = await api.get<Restaurant[]>(
        "/restaurants",
        session.access_token
      );
      setRestaurants(data);
      const savedId =
        typeof window !== "undefined"
          ? localStorage.getItem(STORAGE_KEY)
          : null;
      const saved = data.find((r) => r.id === savedId);
      setActive(saved ?? data[0] ?? null);
    } catch {
      setRestaurants([]);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    // eslint-disable-next-line react-hooks/set-state-in-effect
    void loadRestaurants();
  }, [loadRestaurants]);

  function selectRestaurant(restaurant: Restaurant) {
    setActive(restaurant);
    if (typeof window !== "undefined") {
      localStorage.setItem(STORAGE_KEY, restaurant.id);
    }
  }

  return {
    restaurants,
    active,
    loading,
    selectRestaurant,
    reload: loadRestaurants,
  };
}
