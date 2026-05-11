"use client";

import { use, useState } from "react";
import { useMutation } from "@tanstack/react-query";
import { useRouter } from "next/navigation";
import Link from "next/link";
import { useToken } from "@/hooks/use-token";
import { posApi } from "@/lib/api/resources";
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

export default function NewPOSIntegrationPage({
  params,
}: {
  params: Promise<{ restaurantId: string }>;
}) {
  const { restaurantId: rid } = use(params);
  const token = useToken();
  const router = useRouter();

  const [provider] = useState<"square">("square");
  const [name, setName] = useState("Main POS");
  const [locationId, setLocationId] = useState("");

  const createMutation = useMutation({
    mutationFn: () =>
      posApi.createIntegration(
        rid,
        {
          provider,
          name,
          external_location_id: locationId || null,
        },
        token!,
      ),
    onSuccess: (integration) => {
      router.push(`/app/${rid}/pos/${integration.id}`);
    },
  });

  const canSubmit = name.trim().length > 0 && !!rid && !!token;

  return (
    <div className="max-w-xl space-y-6">
      <div>
        <Link
          href={`/app/${rid}/pos`}
          className="text-sm text-muted-foreground hover:underline"
        >
          ← POS integrations
        </Link>
        <h1 className="text-2xl font-semibold mt-2">Connect POS</h1>
        <p className="text-sm text-muted-foreground mt-1">
          After creating the integration you&apos;ll add the Square sandbox
          access token + webhook signing key. Stock won&apos;t move until
          credentials are configured.
        </p>
      </div>
      <Card>
        <CardHeader>
          <CardTitle className="text-base">Details</CardTitle>
        </CardHeader>
        <CardContent className="space-y-4">
          <div className="space-y-2">
            <Label>Provider</Label>
            <Select value={provider} disabled>
              <SelectTrigger>
                <SelectValue />
              </SelectTrigger>
              <SelectContent>
                <SelectItem value="square">Square</SelectItem>
              </SelectContent>
            </Select>
            <p className="text-xs text-muted-foreground">
              More providers land in future releases.
            </p>
          </div>
          <div className="space-y-2">
            <Label>Name</Label>
            <Input
              value={name}
              onChange={(e) => setName(e.target.value)}
              placeholder="Main POS"
              maxLength={200}
            />
          </div>
          <div className="space-y-2">
            <Label>Location ID (optional now, required to receive events)</Label>
            <Input
              value={locationId}
              onChange={(e) => setLocationId(e.target.value)}
              placeholder="e.g. L7QXZ8M2K9JN1"
              maxLength={200}
            />
            <p className="text-xs text-muted-foreground">
              Square Dashboard → Locations → copy the Location ID. Used to
              route incoming webhooks back to this restaurant.
            </p>
          </div>
          <Button
            className="w-full"
            disabled={!canSubmit || createMutation.isPending}
            onClick={() => createMutation.mutate()}
          >
            {createMutation.isPending ? "Creating..." : "Create integration"}
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
