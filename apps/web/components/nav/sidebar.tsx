"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { useAuth } from "@/hooks/use-auth";
import { useRestaurant } from "@/hooks/use-restaurant";
import { RestaurantSelector } from "@/components/restaurant-selector";
import { Button } from "@/components/ui/button";

export function Sidebar({
  variant = "desktop",
  onNavigate,
}: {
  /**
   * `desktop` (default): fixed-width, always-visible at md+ via `hidden md:flex`.
   * `drawer`: full-height, no border, no breakpoint hiding — rendered inside
   *   the mobile drawer Dialog. Caller is responsible for visibility.
   */
  variant?: "desktop" | "drawer";
  /** Called after a nav link is clicked. Used by the drawer to close itself. */
  onNavigate?: () => void;
} = {}) {
  const pathname = usePathname();
  const { signOut } = useAuth();
  const { restaurants, active, selectRestaurant } = useRestaurant();

  const navItems = active
    ? [
        { href: `/app/${active.id}/dashboard`, label: "Dashboard" },
        { href: `/app/${active.id}/products`, label: "Products" },
        { href: `/app/${active.id}/suppliers`, label: "Suppliers" },
        { href: `/app/${active.id}/stock`, label: "Stock" },
        { href: `/app/${active.id}/recipes`, label: "Recipes" },
        { href: `/app/${active.id}/invoices`, label: "Invoices" },
        { href: `/app/${active.id}/purchase-lists`, label: "Purchase Lists" },
        { href: `/app/${active.id}/equipment`, label: "Equipment" },
        { href: `/app/${active.id}/haccp`, label: "HACCP" },
      ]
    : [];

  const containerClass =
    variant === "drawer"
      ? "flex h-full w-full flex-col bg-background p-4"
      : "hidden h-screen w-60 flex-col border-r bg-background p-4 md:flex";

  return (
    <aside className={containerClass}>
      <div className="mb-6">
        <p className="text-lg font-semibold">ChefTrace</p>
      </div>
      <div className="mb-6">
        <RestaurantSelector
          restaurants={restaurants}
          active={active}
          onSelect={(r) => {
            selectRestaurant(r);
            onNavigate?.();
          }}
        />
      </div>
      <nav className="flex flex-1 flex-col gap-1">
        {navItems.map((item) => (
          <Link
            key={item.href}
            href={item.href}
            onClick={() => onNavigate?.()}
            className={`rounded-md px-3 py-2 text-sm transition-colors hover:bg-accent ${
              pathname.startsWith(item.href)
                ? "bg-accent font-medium"
                : "text-muted-foreground"
            }`}
          >
            {item.label}
          </Link>
        ))}
      </nav>
      <Button
        variant="ghost"
        className="justify-start text-muted-foreground"
        onClick={() => {
          onNavigate?.();
          void signOut();
        }}
      >
        Sign out
      </Button>
    </aside>
  );
}
