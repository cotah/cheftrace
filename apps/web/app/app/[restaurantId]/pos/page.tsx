"use client";

import { use } from "react";
import { useQuery } from "@tanstack/react-query";
import Link from "next/link";
import { useToken } from "@/hooks/use-token";
import { posApi } from "@/lib/api/resources";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";

export default function POSIntegrationsPage({
  params,
}: {
  params: Promise<{ restaurantId: string }>;
}) {
  const { restaurantId: rid } = use(params);
  const token = useToken();

  const { data: integrations = [], isLoading } = useQuery({
    queryKey: ["pos-integrations", rid],
    queryFn: () => posApi.listIntegrations(rid, token!),
    enabled: !!rid && !!token,
  });

  return (
    <div className="space-y-6">
      <div className="flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
        <div>
          <h1 className="text-2xl font-semibold">POS Integrations</h1>
          <p className="text-sm text-muted-foreground mt-1">
            Connect your point-of-sale so sales deduct stock automatically.
          </p>
        </div>
        <div className="flex flex-wrap gap-2">
          <Link href={`/app/${rid}/pos/events`}>
            <Button variant="outline">Event queue</Button>
          </Link>
          {integrations.length === 0 && (
            <Link href={`/app/${rid}/pos/new`}>
              <Button>Connect POS</Button>
            </Link>
          )}
        </div>
      </div>

      {isLoading ? (
        <p className="text-muted-foreground">Loading...</p>
      ) : integrations.length === 0 ? (
        <Card>
          <CardContent className="py-8 text-center">
            <p className="text-muted-foreground">
              No POS connected yet. Click{" "}
              <span className="font-medium">Connect POS</span> to set up Square.
            </p>
          </CardContent>
        </Card>
      ) : (
        <div className="grid gap-3 sm:grid-cols-2">
          {integrations.map((integration) => {
            const ready =
              integration.has_access_token && integration.has_webhook_signing_key;
            return (
              <Card key={integration.id}>
                <CardHeader className="pb-2">
                  <div className="flex items-start justify-between gap-2">
                    <CardTitle className="text-base capitalize">
                      {integration.name}
                    </CardTitle>
                    <Badge variant={integration.is_active ? "secondary" : "outline"}>
                      {integration.is_active ? "Active" : "Inactive"}
                    </Badge>
                  </div>
                  <p className="text-xs uppercase tracking-wide text-muted-foreground mt-1">
                    {integration.provider}
                  </p>
                </CardHeader>
                <CardContent className="space-y-3">
                  <div className="space-y-1 text-sm">
                    <p className="text-muted-foreground">
                      Location:{" "}
                      <span className="text-foreground font-mono text-xs">
                        {integration.external_location_id ?? "—"}
                      </span>
                    </p>
                    <p className="text-muted-foreground">
                      Mode:{" "}
                      <span className="text-foreground font-medium capitalize">
                        {integration.confirmation_mode}
                      </span>
                    </p>
                    <p className="text-muted-foreground">
                      Credentials:{" "}
                      {ready ? (
                        <Badge className="bg-green-100 text-green-800 hover:bg-green-100">
                          Configured
                        </Badge>
                      ) : (
                        <Badge variant="destructive">Needs setup</Badge>
                      )}
                    </p>
                  </div>
                  <Link href={`/app/${rid}/pos/${integration.id}`}>
                    <Button variant="outline" size="sm" className="w-full">
                      Open
                    </Button>
                  </Link>
                </CardContent>
              </Card>
            );
          })}
        </div>
      )}
    </div>
  );
}
