"use client";

import { use } from "react";
import { useQuery } from "@tanstack/react-query";
import { useToken } from "@/hooks/use-token";
import { dashboardApi } from "@/lib/api/resources";
import { Badge } from "@/components/ui/badge";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import type {
  ExpiryAlert,
  HACCPPendingAlert,
  LowStockAlert,
  TemperatureAlert,
} from "@/lib/api/types";

function ExpiryCard({
  alerts,
  title,
  variant,
}: {
  alerts: ExpiryAlert[];
  title: string;
  variant: "warning" | "critical";
}) {
  if (alerts.length === 0) return null;
  return (
    <Card>
      <CardHeader className="pb-2">
        <CardTitle className="text-base flex items-center gap-2">
          {title}
          <Badge variant={variant === "critical" ? "destructive" : "secondary"}>
            {alerts.length}
          </Badge>
        </CardTitle>
      </CardHeader>
      <CardContent className="space-y-2">
        {alerts.map((a) => (
          <div key={a.lot_id} className="flex items-center justify-between text-sm">
            <span className="font-medium">{a.product_name}</span>
            <div className="flex items-center gap-2 text-muted-foreground">
              <span>
                {a.quantity_remaining} {a.unit}
              </span>
              <Badge
                variant={a.days_left <= 0 ? "destructive" : "outline"}
                className="text-xs"
              >
                {a.days_left <= 0
                  ? "Expired"
                  : a.days_left === 1
                    ? "1 day"
                    : `${a.days_left} days`}
              </Badge>
            </div>
          </div>
        ))}
      </CardContent>
    </Card>
  );
}

function LowStockCard({ alerts }: { alerts: LowStockAlert[] }) {
  if (alerts.length === 0) return null;
  return (
    <Card>
      <CardHeader className="pb-2">
        <CardTitle className="text-base flex items-center gap-2">
          Low Stock
          <Badge variant="secondary">{alerts.length}</Badge>
        </CardTitle>
      </CardHeader>
      <CardContent className="space-y-2">
        {alerts.map((a) => (
          <div key={a.product_id} className="flex items-center justify-between text-sm">
            <span className="font-medium">{a.product_name}</span>
            <span className="text-muted-foreground text-xs">
              {a.quantity_remaining}/{a.minimum_stock_quantity} {a.unit}
            </span>
          </div>
        ))}
      </CardContent>
    </Card>
  );
}

function HACCPPendingCard({ alerts }: { alerts: HACCPPendingAlert[] }) {
  if (alerts.length === 0) return null;
  return (
    <Card>
      <CardHeader className="pb-2">
        <CardTitle className="text-base flex items-center gap-2">
          HACCP Pending
          <Badge variant="secondary">{alerts.length}</Badge>
        </CardTitle>
      </CardHeader>
      <CardContent className="space-y-2">
        {alerts.map((a, i) => (
          <div key={`${a.template_id}-${i}`} className="text-sm">
            <span className="font-medium">{a.template_name}</span>
            {a.shift_number && (
              <span className="text-muted-foreground ml-2">— Shift {a.shift_number}</span>
            )}
          </div>
        ))}
      </CardContent>
    </Card>
  );
}

function TemperatureCard({ alerts }: { alerts: TemperatureAlert[] }) {
  if (alerts.length === 0) return null;
  return (
    <Card className="border-destructive">
      <CardHeader className="pb-2">
        <CardTitle className="text-base flex items-center gap-2 text-destructive">
          Temperature Out of Range
          <Badge variant="destructive">{alerts.length}</Badge>
        </CardTitle>
      </CardHeader>
      <CardContent className="space-y-2">
        {alerts.map((a) => (
          <div key={a.log_id} className="flex items-center justify-between text-sm">
            <span className="font-medium">{a.equipment_name}</span>
            <span className="text-destructive font-mono">
              {a.temperature}°C
              {a.min_temp !== null && a.max_temp !== null && (
                <span className="text-muted-foreground font-normal ml-1">
                  (range {a.min_temp}–{a.max_temp})
                </span>
              )}
            </span>
          </div>
        ))}
      </CardContent>
    </Card>
  );
}

export default function DashboardPage({
  params,
}: {
  params: Promise<{ restaurantId: string }>;
}) {
  const { restaurantId: rid } = use(params);
  const token = useToken();

  const { data, isLoading, error } = useQuery({
    queryKey: ["dashboard", rid],
    queryFn: () => dashboardApi.get(rid, token!),
    enabled: !!rid && !!token,
    refetchInterval: 60_000,
  });

  if (isLoading) {
    return (
      <div className="space-y-6">
        <h1 className="text-2xl font-semibold">Dashboard</h1>
        <p className="text-muted-foreground">Loading...</p>
      </div>
    );
  }

  if (error || !data) {
    return (
      <div className="space-y-6">
        <h1 className="text-2xl font-semibold">Dashboard</h1>
        <p className="text-sm text-destructive">Failed to load dashboard data.</p>
      </div>
    );
  }

  const hasAlerts =
    data.critical_expiry.length > 0 ||
    data.temperature_out_of_range.length > 0 ||
    data.expiry_alerts.length > 0 ||
    data.low_stock.length > 0 ||
    data.haccp_pending.length > 0;

  return (
    <div className="space-y-6">
      <div className="flex flex-col gap-3 sm:flex-row sm:items-start sm:justify-between">
        <div>
          <h1 className="text-2xl font-semibold">Dashboard</h1>
          <p className="text-sm text-muted-foreground mt-1">
            {data.total_active_lots} active stock lot
            {data.total_active_lots !== 1 ? "s" : ""}
          </p>
        </div>
        {data.stock_value_eur !== undefined && (
          <div className="sm:text-right">
            <p className="text-2xl font-semibold">
              €{data.stock_value_eur?.toFixed(2) ?? "—"}
            </p>
            {data.stock_value_partial && (
              <p className="text-xs text-muted-foreground">
                {data.lots_without_cost} lot
                {data.lots_without_cost !== 1 ? "s" : ""} without cost — partial estimate
              </p>
            )}
          </div>
        )}
      </div>

      {!hasAlerts ? (
        <Card>
          <CardContent className="py-8 text-center">
            <p className="text-muted-foreground">All clear — no alerts today.</p>
          </CardContent>
        </Card>
      ) : (
        <div className="grid gap-4 md:grid-cols-2">
          {data.temperature_out_of_range.length > 0 && (
            <div className="md:col-span-2">
              <TemperatureCard alerts={data.temperature_out_of_range} />
            </div>
          )}
          <ExpiryCard
            alerts={data.critical_expiry}
            title="Expiring Soon — Critical"
            variant="critical"
          />
          <ExpiryCard
            alerts={data.expiry_alerts}
            title="Expiring Soon"
            variant="warning"
          />
          <LowStockCard alerts={data.low_stock} />
          <HACCPPendingCard alerts={data.haccp_pending} />
        </div>
      )}
    </div>
  );
}
