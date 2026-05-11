"use client";

import { use, useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { useToken } from "@/hooks/use-token";
import { posApi, recipesApi } from "@/lib/api/resources";
import type {
  POSConfirmationMode,
  POSItemMapping,
  Recipe,
} from "@/lib/api/types";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
  DialogTrigger,
} from "@/components/ui/dialog";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";

const IGNORE_VALUE = "__ignore__";

function CredentialsDialog({
  rid,
  integrationId,
  token,
  trigger,
}: {
  rid: string;
  integrationId: string;
  token: string;
  trigger: React.ReactNode;
}) {
  const qc = useQueryClient();
  const [open, setOpen] = useState(false);
  const [accessToken, setAccessToken] = useState("");
  const [signingKey, setSigningKey] = useState("");

  const mutation = useMutation({
    mutationFn: () =>
      posApi.setCredentials(
        rid,
        integrationId,
        {
          access_token: accessToken,
          webhook_signing_key: signingKey,
        },
        token,
      ),
    onSuccess: () => {
      void qc.invalidateQueries({
        queryKey: ["pos-integration", rid, integrationId],
      });
      void qc.invalidateQueries({ queryKey: ["pos-integrations", rid] });
      setAccessToken("");
      setSigningKey("");
      setOpen(false);
    },
  });

  return (
    <Dialog
      open={open}
      onOpenChange={(o) => {
        if (mutation.isPending) return;
        setOpen(o);
        if (!o) {
          setAccessToken("");
          setSigningKey("");
        }
      }}
    >
      <DialogTrigger asChild>{trigger}</DialogTrigger>
      <DialogContent>
        <DialogHeader>
          <DialogTitle>Set Square credentials</DialogTitle>
          <DialogDescription>
            Both values are required together. They&apos;re encrypted at rest;
            we never display them back. Re-submitting replaces both.
          </DialogDescription>
        </DialogHeader>
        <div className="space-y-4 pt-2">
          <div className="space-y-2">
            <Label>Access token</Label>
            <Input
              type="password"
              value={accessToken}
              onChange={(e) => setAccessToken(e.target.value)}
              placeholder="EAAAEx..."
              autoComplete="off"
            />
          </div>
          <div className="space-y-2">
            <Label>Webhook signing key</Label>
            <Input
              type="password"
              value={signingKey}
              onChange={(e) => setSigningKey(e.target.value)}
              placeholder="From Square Developer dashboard → Webhooks"
              autoComplete="off"
            />
          </div>
          {mutation.isError && (
            <p className="text-sm text-destructive">{mutation.error.message}</p>
          )}
        </div>
        <DialogFooter>
          <Button
            variant="ghost"
            onClick={() => setOpen(false)}
            disabled={mutation.isPending}
          >
            Cancel
          </Button>
          <Button
            onClick={() => mutation.mutate()}
            disabled={
              !accessToken.trim() || !signingKey.trim() || mutation.isPending
            }
          >
            {mutation.isPending ? "Saving..." : "Save credentials"}
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}

function AutoModeWarningDialog({
  open,
  onCancel,
  onConfirm,
  pending,
}: {
  open: boolean;
  onCancel: () => void;
  onConfirm: () => void;
  pending: boolean;
}) {
  return (
    <Dialog open={open} onOpenChange={(o) => !o && !pending && onCancel()}>
      <DialogContent>
        <DialogHeader>
          <DialogTitle>Enable automatic stock deduction?</DialogTitle>
          <DialogDescription>
            In <span className="font-medium">Auto</span> mode, every POS sale
            deducts stock via FEFO without human approval. The IA never decides
            unilaterally — you&apos;re explicitly authorising this now.
          </DialogDescription>
        </DialogHeader>
        <p className="text-sm">
          Switch back to <span className="font-medium">Manual</span> any time
          to require approval per sale again.
        </p>
        <DialogFooter>
          <Button variant="ghost" onClick={onCancel} disabled={pending}>
            Cancel
          </Button>
          <Button onClick={onConfirm} disabled={pending}>
            {pending ? "Switching..." : "Enable auto"}
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}

function MappingDialog({
  rid,
  integrationId,
  token,
  recipes,
  trigger,
  existing,
}: {
  rid: string;
  integrationId: string;
  token: string;
  recipes: Recipe[];
  trigger: React.ReactNode;
  existing?: POSItemMapping;
}) {
  const qc = useQueryClient();
  const [open, setOpen] = useState(false);
  const [externalId, setExternalId] = useState(existing?.external_item_id ?? "");
  const [name, setName] = useState(existing?.external_item_name_snapshot ?? "");
  const [recipeId, setRecipeId] = useState<string>(
    existing?.recipe_id ?? IGNORE_VALUE,
  );
  const [unitsPerSale, setUnitsPerSale] = useState(
    existing ? String(existing.units_per_sale) : "1.000",
  );

  function handleOpenChange(next: boolean) {
    setOpen(next);
    if (next && !existing) {
      setExternalId("");
      setName("");
      setRecipeId(IGNORE_VALUE);
      setUnitsPerSale("1.000");
    }
  }

  const createMutation = useMutation({
    mutationFn: () =>
      posApi.createMapping(
        rid,
        integrationId,
        {
          external_item_id: externalId,
          external_item_name_snapshot: name,
          recipe_id: recipeId === IGNORE_VALUE ? null : recipeId,
          units_per_sale: parseFloat(unitsPerSale),
        },
        token,
      ),
    onSuccess: () => {
      void qc.invalidateQueries({
        queryKey: ["pos-mappings", rid, integrationId],
      });
      setOpen(false);
    },
  });

  const updateMutation = useMutation({
    mutationFn: () =>
      posApi.updateMapping(
        rid,
        integrationId,
        existing!.id,
        {
          external_item_name_snapshot: name,
          recipe_id: recipeId === IGNORE_VALUE ? null : recipeId,
          units_per_sale: parseFloat(unitsPerSale),
        },
        token,
      ),
    onSuccess: () => {
      void qc.invalidateQueries({
        queryKey: ["pos-mappings", rid, integrationId],
      });
      setOpen(false);
    },
  });

  const isEdit = !!existing;
  const mutation = isEdit ? updateMutation : createMutation;
  const canSubmit =
    (isEdit || externalId.trim().length > 0) &&
    name.trim().length > 0 &&
    parseFloat(unitsPerSale) > 0;

  return (
    <Dialog open={open} onOpenChange={handleOpenChange}>
      <DialogTrigger asChild>{trigger}</DialogTrigger>
      <DialogContent>
        <DialogHeader>
          <DialogTitle>{isEdit ? "Edit mapping" : "Add mapping"}</DialogTitle>
          <DialogDescription>
            Link a POS item (Square catalog object id) to a recipe.
            &quot;Don&apos;t deduct&quot; preserves the audit trail for items
            like gift cards or service charges.
          </DialogDescription>
        </DialogHeader>
        <div className="space-y-4 pt-2">
          {!isEdit && (
            <div className="space-y-2">
              <Label>External item ID</Label>
              <Input
                value={externalId}
                onChange={(e) => setExternalId(e.target.value)}
                placeholder="Square catalog_object_id"
                maxLength={200}
              />
              <p className="text-xs text-muted-foreground">
                Find this in Square Dashboard → Items → variation ID.
              </p>
            </div>
          )}
          <div className="space-y-2">
            <Label>Display name</Label>
            <Input
              value={name}
              onChange={(e) => setName(e.target.value)}
              placeholder="e.g. Tomato Pasta"
              maxLength={200}
            />
          </div>
          <div className="space-y-2">
            <Label>Recipe</Label>
            <Select value={recipeId} onValueChange={setRecipeId}>
              <SelectTrigger>
                <SelectValue />
              </SelectTrigger>
              <SelectContent>
                <SelectItem value={IGNORE_VALUE}>
                  Don&apos;t deduct (ignore this item)
                </SelectItem>
                {recipes
                  .filter((r) => r.is_active)
                  .map((r) => (
                    <SelectItem key={r.id} value={r.id}>
                      {r.name}
                    </SelectItem>
                  ))}
              </SelectContent>
            </Select>
          </div>
          <div className="space-y-2">
            <Label>Units per sale</Label>
            <Input
              type="number"
              min="0"
              step="0.001"
              value={unitsPerSale}
              onChange={(e) => setUnitsPerSale(e.target.value)}
            />
            <p className="text-xs text-muted-foreground">
              How many recipe portions one POS sale equals. Default 1.000.
            </p>
          </div>
          {mutation.isError && (
            <p className="text-sm text-destructive">{mutation.error.message}</p>
          )}
        </div>
        <DialogFooter>
          <Button
            variant="ghost"
            onClick={() => setOpen(false)}
            disabled={mutation.isPending}
          >
            Cancel
          </Button>
          <Button
            onClick={() => mutation.mutate()}
            disabled={!canSubmit || mutation.isPending}
          >
            {mutation.isPending ? "Saving..." : isEdit ? "Save" : "Add mapping"}
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}

export default function POSIntegrationDetailPage({
  params,
}: {
  params: Promise<{ restaurantId: string; integrationId: string }>;
}) {
  const { restaurantId: rid, integrationId } = use(params);
  const token = useToken();
  const qc = useQueryClient();
  const router = useRouter();

  const { data: integration, isLoading } = useQuery({
    queryKey: ["pos-integration", rid, integrationId],
    queryFn: () => posApi.getIntegration(rid, integrationId, token!),
    enabled: !!rid && !!integrationId && !!token,
  });

  const { data: mappings = [] } = useQuery({
    queryKey: ["pos-mappings", rid, integrationId],
    queryFn: () => posApi.listMappings(rid, integrationId, token!),
    enabled: !!rid && !!integrationId && !!token,
  });

  const { data: recipes = [] } = useQuery({
    queryKey: ["recipes", rid, "active"],
    queryFn: () => recipesApi.list(rid, token!, true),
    enabled: !!rid && !!token,
  });

  const [pendingMode, setPendingMode] = useState<POSConfirmationMode | null>(
    null,
  );
  const [pendingDelete, setPendingDelete] = useState(false);
  const [editName, setEditName] = useState(false);
  const [name, setName] = useState("");
  const [locationId, setLocationId] = useState("");

  const updateMutation = useMutation({
    mutationFn: (data: Parameters<typeof posApi.updateIntegration>[2]) =>
      posApi.updateIntegration(rid, integrationId, data, token!),
    onSuccess: () => {
      void qc.invalidateQueries({
        queryKey: ["pos-integration", rid, integrationId],
      });
      void qc.invalidateQueries({ queryKey: ["pos-integrations", rid] });
      setPendingMode(null);
      setEditName(false);
    },
  });

  const deleteMutation = useMutation({
    mutationFn: () => posApi.deleteIntegration(rid, integrationId, token!),
    onSuccess: () => {
      void qc.invalidateQueries({ queryKey: ["pos-integrations", rid] });
      router.push(`/app/${rid}/pos`);
    },
  });

  const deleteMappingMutation = useMutation({
    mutationFn: (mappingId: string) =>
      posApi.deleteMapping(rid, integrationId, mappingId, token!),
    onSuccess: () => {
      void qc.invalidateQueries({
        queryKey: ["pos-mappings", rid, integrationId],
      });
    },
  });

  if (isLoading) {
    return <p className="text-muted-foreground">Loading...</p>;
  }
  if (!integration) {
    return <p className="text-sm text-destructive">Integration not found.</p>;
  }

  function startNameEdit() {
    if (!integration) return;
    setName(integration.name);
    setLocationId(integration.external_location_id ?? "");
    setEditName(true);
  }

  const recipeNameById = new Map(recipes.map((r) => [r.id, r.name]));
  const ready =
    integration.has_access_token && integration.has_webhook_signing_key;

  return (
    <div className="space-y-6">
      <div className="flex flex-col gap-3 sm:flex-row sm:items-start sm:justify-between">
        <div>
          <Link
            href={`/app/${rid}/pos`}
            className="text-sm text-muted-foreground hover:underline"
          >
            ← POS integrations
          </Link>
          <h1 className="text-2xl font-semibold mt-2">{integration.name}</h1>
          <div className="flex flex-wrap items-center gap-2 mt-1">
            <Badge variant={integration.is_active ? "secondary" : "outline"}>
              {integration.is_active ? "Active" : "Inactive"}
            </Badge>
            <span className="text-xs uppercase tracking-wide text-muted-foreground">
              {integration.provider}
            </span>
            <Badge
              variant={
                integration.confirmation_mode === "auto"
                  ? "destructive"
                  : "outline"
              }
            >
              {integration.confirmation_mode === "auto"
                ? "Auto deduct"
                : "Manual approval"}
            </Badge>
          </div>
        </div>
        <Link href={`/app/${rid}/pos/events`}>
          <Button variant="outline">View event queue</Button>
        </Link>
      </div>

      {/* Settings */}
      <Card>
        <CardHeader className="flex flex-row items-center justify-between pb-2">
          <CardTitle className="text-base">Settings</CardTitle>
          {!editName && (
            <Button variant="outline" size="sm" onClick={startNameEdit}>
              Edit
            </Button>
          )}
        </CardHeader>
        <CardContent className="space-y-4">
          {editName ? (
            <>
              <div className="space-y-2">
                <Label>Name</Label>
                <Input
                  value={name}
                  onChange={(e) => setName(e.target.value)}
                  maxLength={200}
                />
              </div>
              <div className="space-y-2">
                <Label>Location ID</Label>
                <Input
                  value={locationId}
                  onChange={(e) => setLocationId(e.target.value)}
                  placeholder="Square Location ID"
                  maxLength={200}
                />
              </div>
              <div className="flex gap-2">
                <Button
                  disabled={!name.trim() || updateMutation.isPending}
                  onClick={() =>
                    updateMutation.mutate({
                      name,
                      external_location_id: locationId || null,
                    })
                  }
                >
                  {updateMutation.isPending ? "Saving..." : "Save"}
                </Button>
                <Button
                  variant="ghost"
                  onClick={() => setEditName(false)}
                  disabled={updateMutation.isPending}
                >
                  Cancel
                </Button>
              </div>
              {updateMutation.isError && (
                <p className="text-sm text-destructive">
                  {updateMutation.error.message}
                </p>
              )}
            </>
          ) : (
            <dl className="grid grid-cols-1 gap-y-2 text-sm sm:grid-cols-2 sm:gap-x-4">
              <dt className="text-muted-foreground">Location ID</dt>
              <dd className="font-mono text-xs">
                {integration.external_location_id ?? "—"}
              </dd>
              <dt className="text-muted-foreground">Last sync</dt>
              <dd>
                {integration.last_sync_at
                  ? new Date(integration.last_sync_at).toLocaleString("en-IE")
                  : "—"}
              </dd>
            </dl>
          )}
        </CardContent>
      </Card>

      {/* Credentials */}
      <Card>
        <CardHeader className="pb-2">
          <CardTitle className="text-base">Credentials</CardTitle>
        </CardHeader>
        <CardContent className="space-y-4">
          <div className="space-y-2 text-sm">
            <div className="flex items-center justify-between">
              <span className="text-muted-foreground">Access token</span>
              {integration.has_access_token ? (
                <Badge className="bg-green-100 text-green-800 hover:bg-green-100">
                  Configured
                </Badge>
              ) : (
                <Badge variant="destructive">Missing</Badge>
              )}
            </div>
            <div className="flex items-center justify-between">
              <span className="text-muted-foreground">Webhook signing key</span>
              {integration.has_webhook_signing_key ? (
                <Badge className="bg-green-100 text-green-800 hover:bg-green-100">
                  Configured
                </Badge>
              ) : (
                <Badge variant="destructive">Missing</Badge>
              )}
            </div>
          </div>
          {token && (
            <CredentialsDialog
              rid={rid}
              integrationId={integrationId}
              token={token}
              trigger={
                <Button variant="outline" className="w-full sm:w-auto">
                  {ready ? "Replace credentials" : "Set credentials"}
                </Button>
              }
            />
          )}
        </CardContent>
      </Card>

      {/* Confirmation mode */}
      <Card>
        <CardHeader className="pb-2">
          <CardTitle className="text-base">Confirmation mode</CardTitle>
        </CardHeader>
        <CardContent className="space-y-3">
          <p className="text-sm text-muted-foreground">
            <span className="font-medium text-foreground">Manual</span>: every
            sale waits for human approval before stock moves.{" "}
            <span className="font-medium text-foreground">Auto</span>: stock
            deducts immediately on every sale.
          </p>
          <div className="flex flex-wrap gap-2">
            <Button
              variant={
                integration.confirmation_mode === "manual" ? "default" : "outline"
              }
              onClick={() =>
                integration.confirmation_mode !== "manual" &&
                updateMutation.mutate({ confirmation_mode: "manual" })
              }
              disabled={updateMutation.isPending}
            >
              Manual approval
            </Button>
            <Button
              variant={
                integration.confirmation_mode === "auto" ? "default" : "outline"
              }
              onClick={() =>
                integration.confirmation_mode !== "auto" && setPendingMode("auto")
              }
              disabled={updateMutation.isPending}
            >
              Auto deduct
            </Button>
          </div>
        </CardContent>
      </Card>

      <AutoModeWarningDialog
        open={pendingMode === "auto"}
        onCancel={() => setPendingMode(null)}
        onConfirm={() =>
          updateMutation.mutate({ confirmation_mode: "auto" })
        }
        pending={updateMutation.isPending}
      />

      {/* Mappings */}
      <Card>
        <CardHeader className="flex flex-row items-center justify-between pb-2">
          <CardTitle className="text-base">Item mappings</CardTitle>
          {token && (
            <MappingDialog
              rid={rid}
              integrationId={integrationId}
              token={token}
              recipes={recipes}
              trigger={<Button size="sm">Add mapping</Button>}
            />
          )}
        </CardHeader>
        <CardContent>
          {mappings.length === 0 ? (
            <p className="text-sm text-muted-foreground py-4">
              No mappings yet. Without mappings, every incoming POS sale parks
              in <span className="font-medium">needs_mapping</span>.
            </p>
          ) : (
            <div className="overflow-x-auto">
              <Table>
                <TableHeader>
                  <TableRow>
                    <TableHead>External ID</TableHead>
                    <TableHead>Display name</TableHead>
                    <TableHead>Recipe</TableHead>
                    <TableHead className="text-right">Units/sale</TableHead>
                    <TableHead>Active</TableHead>
                    <TableHead></TableHead>
                  </TableRow>
                </TableHeader>
                <TableBody>
                  {mappings.map((m) => (
                    <TableRow key={m.id}>
                      <TableCell className="font-mono text-xs">
                        {m.external_item_id}
                      </TableCell>
                      <TableCell>{m.external_item_name_snapshot}</TableCell>
                      <TableCell>
                        {m.recipe_id ? (
                          recipeNameById.get(m.recipe_id) ?? (
                            <span className="text-muted-foreground">
                              {m.recipe_id.slice(0, 8)}
                            </span>
                          )
                        ) : (
                          <span className="text-amber-800">
                            Ignored (no deduction)
                          </span>
                        )}
                      </TableCell>
                      <TableCell className="text-right font-mono">
                        {m.units_per_sale}
                      </TableCell>
                      <TableCell>
                        {m.is_active ? (
                          <Badge variant="secondary">Active</Badge>
                        ) : (
                          <Badge variant="outline">Inactive</Badge>
                        )}
                      </TableCell>
                      <TableCell className="text-right space-x-1">
                        {token && (
                          <MappingDialog
                            rid={rid}
                            integrationId={integrationId}
                            token={token}
                            recipes={recipes}
                            existing={m}
                            trigger={
                              <Button variant="ghost" size="sm">
                                Edit
                              </Button>
                            }
                          />
                        )}
                        {m.is_active && (
                          <Button
                            variant="ghost"
                            size="sm"
                            disabled={deleteMappingMutation.isPending}
                            onClick={() => deleteMappingMutation.mutate(m.id)}
                          >
                            Remove
                          </Button>
                        )}
                      </TableCell>
                    </TableRow>
                  ))}
                </TableBody>
              </Table>
            </div>
          )}
        </CardContent>
      </Card>

      {/* Soft delete */}
      <Card>
        <CardContent className="flex flex-col gap-3 pt-6 sm:flex-row sm:items-center sm:justify-between">
          <div>
            <p className="text-sm font-medium">Disconnect POS</p>
            <p className="text-xs text-muted-foreground">
              Soft delete — incoming webhooks for this integration are
              ignored, past events stay in the queue.
            </p>
          </div>
          <Button
            variant="ghost"
            className="text-destructive hover:text-destructive"
            onClick={() => setPendingDelete(true)}
          >
            Disconnect
          </Button>
        </CardContent>
      </Card>

      <Dialog
        open={pendingDelete}
        onOpenChange={(o) => {
          if (!deleteMutation.isPending) setPendingDelete(o);
        }}
      >
        <DialogContent>
          <DialogHeader>
            <DialogTitle>Disconnect POS integration?</DialogTitle>
            <DialogDescription>
              Future webhooks for this location will be ignored. Past events
              and audit log entries remain intact. You can re-enable later.
            </DialogDescription>
          </DialogHeader>
          {deleteMutation.isError && (
            <p className="rounded-md bg-destructive/10 p-3 text-sm text-destructive">
              {deleteMutation.error.message}
            </p>
          )}
          <DialogFooter>
            <Button
              variant="ghost"
              onClick={() => setPendingDelete(false)}
              disabled={deleteMutation.isPending}
            >
              Cancel
            </Button>
            <Button
              variant="destructive"
              onClick={() => deleteMutation.mutate()}
              disabled={deleteMutation.isPending}
            >
              {deleteMutation.isPending ? "Disconnecting..." : "Disconnect"}
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </div>
  );
}
