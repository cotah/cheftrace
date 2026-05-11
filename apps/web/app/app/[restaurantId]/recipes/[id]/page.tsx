"use client";

import { use, useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { useToken } from "@/hooks/use-token";
import { productsApi, recipesApi } from "@/lib/api/resources";
import type { IngredientUnit, RecipeIngredient } from "@/lib/api/types";
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
import { ProduceDialog } from "./produce-dialog";

const INGREDIENT_UNITS: IngredientUnit[] = ["kg", "g", "l", "ml", "unit"];

function IngredientDialog({
  rid,
  recipeId,
  token,
  trigger,
  existing,
  products,
}: {
  rid: string;
  recipeId: string;
  token: string;
  trigger: React.ReactNode;
  existing?: RecipeIngredient;
  products: { id: string; name: string; unit: string }[];
}) {
  const qc = useQueryClient();
  const [open, setOpen] = useState(false);
  const [productId, setProductId] = useState(existing?.product_id ?? "");
  const [quantity, setQuantity] = useState(
    existing ? String(existing.quantity) : "",
  );
  const [unit, setUnit] = useState<IngredientUnit>(
    (existing?.unit as IngredientUnit) ?? "kg",
  );
  const [notes, setNotes] = useState(existing?.notes ?? "");

  function handleOpenChange(next: boolean) {
    setOpen(next);
    // Reset form whenever the Add variant re-opens, otherwise the previous
    // selection sticks across opens. Edit variants prefill from `existing`
    // and shouldn't be wiped.
    if (next && !existing) {
      setProductId("");
      setQuantity("");
      setUnit("kg");
      setNotes("");
    }
  }

  const addMutation = useMutation({
    mutationFn: () =>
      recipesApi.addIngredient(
        rid,
        recipeId,
        {
          product_id: productId,
          quantity: parseFloat(quantity),
          unit,
          notes: notes || null,
        },
        token,
      ),
    onSuccess: () => {
      void qc.invalidateQueries({ queryKey: ["recipe", rid, recipeId] });
      setOpen(false);
    },
  });

  const updateMutation = useMutation({
    mutationFn: () =>
      recipesApi.updateIngredient(
        rid,
        recipeId,
        existing!.id,
        {
          quantity: parseFloat(quantity),
          unit,
          notes: notes || null,
        },
        token,
      ),
    onSuccess: () => {
      void qc.invalidateQueries({ queryKey: ["recipe", rid, recipeId] });
      setOpen(false);
    },
  });

  const isEditing = !!existing;
  const mutation = isEditing ? updateMutation : addMutation;
  const canSubmit =
    (isEditing || productId.length > 0) &&
    quantity.length > 0 &&
    parseFloat(quantity) > 0;

  return (
    <Dialog open={open} onOpenChange={handleOpenChange}>
      <DialogTrigger asChild>{trigger}</DialogTrigger>
      <DialogContent>
        <DialogHeader>
          <DialogTitle>
            {isEditing ? "Edit ingredient" : "Add ingredient"}
          </DialogTitle>
        </DialogHeader>
        <div className="space-y-4 pt-2">
          {!isEditing && (
            <div className="space-y-2">
              <Label>Product</Label>
              <Select value={productId} onValueChange={setProductId}>
                <SelectTrigger>
                  <SelectValue placeholder="Select product" />
                </SelectTrigger>
                <SelectContent>
                  {products.map((p) => (
                    <SelectItem key={p.id} value={p.id}>
                      {p.name} ({p.unit})
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
            </div>
          )}
          <div className="grid grid-cols-1 gap-3 sm:grid-cols-2">
            <div className="space-y-2">
              <Label>Quantity</Label>
              <Input
                type="number"
                min="0"
                step="0.001"
                value={quantity}
                onChange={(e) => setQuantity(e.target.value)}
                placeholder="0"
              />
            </div>
            <div className="space-y-2">
              <Label>Unit</Label>
              <Select
                value={unit}
                onValueChange={(v) => setUnit(v as IngredientUnit)}
              >
                <SelectTrigger>
                  <SelectValue />
                </SelectTrigger>
                <SelectContent>
                  {INGREDIENT_UNITS.map((u) => (
                    <SelectItem key={u} value={u}>
                      {u}
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
            </div>
          </div>
          <div className="space-y-2">
            <Label>Notes (optional)</Label>
            <Input
              value={notes}
              onChange={(e) => setNotes(e.target.value)}
              placeholder="e.g. diced, room temperature"
            />
          </div>
          <Button
            className="w-full"
            disabled={!canSubmit || mutation.isPending}
            onClick={() => mutation.mutate()}
          >
            {mutation.isPending
              ? "Saving..."
              : isEditing
                ? "Save"
                : "Add ingredient"}
          </Button>
          {mutation.isError && (
            <p className="text-sm text-destructive">{mutation.error.message}</p>
          )}
        </div>
      </DialogContent>
    </Dialog>
  );
}

export default function RecipeDetailPage({
  params,
}: {
  params: Promise<{ restaurantId: string; id: string }>;
}) {
  const { restaurantId: rid, id: recipeId } = use(params);
  const token = useToken();
  const qc = useQueryClient();
  const router = useRouter();

  const { data: recipe, isLoading } = useQuery({
    queryKey: ["recipe", rid, recipeId],
    queryFn: () => recipesApi.get(rid, recipeId, token!),
    enabled: !!rid && !!recipeId && !!token,
  });

  const { data: products = [] } = useQuery({
    queryKey: ["products", rid],
    queryFn: () => productsApi.list(rid, token!),
    enabled: !!rid && !!token,
  });

  const [isEditing, setIsEditing] = useState(false);
  const [name, setName] = useState("");
  const [yieldQuantity, setYieldQuantity] = useState("");
  const [yieldUnit, setYieldUnit] = useState("");
  const [prepMinutes, setPrepMinutes] = useState("");
  const [cookMinutes, setCookMinutes] = useState("");
  const [instructions, setInstructions] = useState("");
  const [pendingDelete, setPendingDelete] = useState(false);

  // Hydrate the edit form once when the user opens it, so external refetches
  // don't clobber in-progress edits.
  function startEdit() {
    if (!recipe) return;
    setName(recipe.name);
    setYieldQuantity(String(recipe.yield_quantity));
    setYieldUnit(recipe.yield_unit);
    setPrepMinutes(
      recipe.prep_time_minutes !== null ? String(recipe.prep_time_minutes) : "",
    );
    setCookMinutes(
      recipe.cook_time_minutes !== null ? String(recipe.cook_time_minutes) : "",
    );
    setInstructions(recipe.instructions ?? "");
    setIsEditing(true);
  }

  const updateMutation = useMutation({
    mutationFn: () =>
      recipesApi.update(
        rid,
        recipeId,
        {
          name,
          yield_quantity: parseFloat(yieldQuantity),
          yield_unit: yieldUnit,
          prep_time_minutes: prepMinutes ? parseInt(prepMinutes, 10) : null,
          cook_time_minutes: cookMinutes ? parseInt(cookMinutes, 10) : null,
          instructions: instructions || null,
        },
        token!,
      ),
    onSuccess: () => {
      void qc.invalidateQueries({ queryKey: ["recipe", rid, recipeId] });
      void qc.invalidateQueries({ queryKey: ["recipes", rid] });
      setIsEditing(false);
    },
  });

  const reactivateMutation = useMutation({
    mutationFn: () =>
      recipesApi.update(rid, recipeId, { is_active: true }, token!),
    onSuccess: () => {
      void qc.invalidateQueries({ queryKey: ["recipe", rid, recipeId] });
      void qc.invalidateQueries({ queryKey: ["recipes", rid] });
    },
  });

  const deleteMutation = useMutation({
    mutationFn: () => recipesApi.delete(rid, recipeId, token!),
    onSuccess: () => {
      void qc.invalidateQueries({ queryKey: ["recipes", rid] });
      router.push(`/app/${rid}/recipes`);
    },
  });

  const removeIngredientMutation = useMutation({
    mutationFn: (ingredientId: string) =>
      recipesApi.removeIngredient(rid, recipeId, ingredientId, token!),
    onSuccess: () => {
      void qc.invalidateQueries({ queryKey: ["recipe", rid, recipeId] });
    },
  });

  if (isLoading) {
    return <p className="text-muted-foreground">Loading...</p>;
  }
  if (!recipe) {
    return <p className="text-sm text-destructive">Recipe not found.</p>;
  }

  const productMap = Object.fromEntries(products.map((p) => [p.id, p]));
  const canSaveEdit =
    name.trim().length > 0 &&
    yieldQuantity.length > 0 &&
    parseFloat(yieldQuantity) > 0 &&
    yieldUnit.trim().length > 0;

  return (
    <div className="space-y-6">
      <div className="flex items-start justify-between gap-4">
        <div className="min-w-0">
          <Link
            href={`/app/${rid}/recipes`}
            className="text-sm text-muted-foreground hover:underline"
          >
            ← All recipes
          </Link>
          <h1 className="text-2xl font-semibold mt-2 truncate">{recipe.name}</h1>
          <div className="flex items-center gap-2 mt-1">
            {recipe.is_active ? (
              <Badge variant="secondary">Active</Badge>
            ) : (
              <Badge variant="outline">Inactive</Badge>
            )}
            <span className="text-xs text-muted-foreground">
              Yield: {recipe.yield_quantity} {recipe.yield_unit}
            </span>
          </div>
        </div>
        <div className="flex items-center gap-2 shrink-0">
          {recipe.is_active ? (
            <ProduceDialog
              rid={rid}
              recipeId={recipeId}
              recipeName={recipe.name}
              token={token}
              disabled={recipe.ingredients.length === 0}
              disabledReason={
                recipe.ingredients.length === 0
                  ? "Add at least one ingredient before producing."
                  : undefined
              }
            />
          ) : (
            <Button
              variant="outline"
              disabled={reactivateMutation.isPending}
              onClick={() => reactivateMutation.mutate()}
            >
              {reactivateMutation.isPending ? "Reactivating..." : "Reactivate"}
            </Button>
          )}
        </div>
      </div>

      <Card>
        <CardHeader className="flex flex-row items-center justify-between pb-2">
          <CardTitle className="text-base">Details</CardTitle>
          {recipe.is_active && !isEditing && (
            <Button variant="outline" size="sm" onClick={startEdit}>
              Edit
            </Button>
          )}
        </CardHeader>
        <CardContent className="space-y-4">
          {isEditing ? (
            <>
              <div className="space-y-2">
                <Label>Name</Label>
                <Input
                  value={name}
                  onChange={(e) => setName(e.target.value)}
                  maxLength={200}
                />
              </div>
              <div className="grid grid-cols-1 gap-3 sm:grid-cols-2">
                <div className="space-y-2">
                  <Label>Yield quantity</Label>
                  <Input
                    type="number"
                    min="0"
                    step="0.001"
                    value={yieldQuantity}
                    onChange={(e) => setYieldQuantity(e.target.value)}
                  />
                </div>
                <div className="space-y-2">
                  <Label>Yield unit</Label>
                  <Input
                    value={yieldUnit}
                    onChange={(e) => setYieldUnit(e.target.value)}
                    maxLength={50}
                  />
                </div>
              </div>
              <div className="grid grid-cols-1 gap-3 sm:grid-cols-2">
                <div className="space-y-2">
                  <Label>Prep time (min)</Label>
                  <Input
                    type="number"
                    min="0"
                    step="1"
                    value={prepMinutes}
                    onChange={(e) => setPrepMinutes(e.target.value)}
                  />
                </div>
                <div className="space-y-2">
                  <Label>Cook time (min)</Label>
                  <Input
                    type="number"
                    min="0"
                    step="1"
                    value={cookMinutes}
                    onChange={(e) => setCookMinutes(e.target.value)}
                  />
                </div>
              </div>
              <div className="space-y-2">
                <Label>Instructions</Label>
                <textarea
                  className="flex min-h-[100px] w-full rounded-md border border-input bg-background px-3 py-2 text-sm shadow-sm placeholder:text-muted-foreground focus-visible:outline-none focus-visible:ring-1 focus-visible:ring-ring disabled:cursor-not-allowed disabled:opacity-50"
                  value={instructions}
                  onChange={(e) => setInstructions(e.target.value)}
                />
              </div>
              <div className="flex gap-2">
                <Button
                  disabled={!canSaveEdit || updateMutation.isPending}
                  onClick={() => updateMutation.mutate()}
                >
                  {updateMutation.isPending ? "Saving..." : "Save"}
                </Button>
                <Button
                  variant="ghost"
                  disabled={updateMutation.isPending}
                  onClick={() => setIsEditing(false)}
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
            <dl className="grid grid-cols-2 gap-x-4 gap-y-2 text-sm">
              <dt className="text-muted-foreground">Prep time</dt>
              <dd>
                {recipe.prep_time_minutes !== null
                  ? `${recipe.prep_time_minutes} min`
                  : "—"}
              </dd>
              <dt className="text-muted-foreground">Cook time</dt>
              <dd>
                {recipe.cook_time_minutes !== null
                  ? `${recipe.cook_time_minutes} min`
                  : "—"}
              </dd>
              <dt className="text-muted-foreground">Instructions</dt>
              <dd className="whitespace-pre-wrap">
                {recipe.instructions ?? "—"}
              </dd>
            </dl>
          )}
        </CardContent>
      </Card>

      <Card>
        <CardHeader className="flex flex-row items-center justify-between pb-2">
          <CardTitle className="text-base">Ingredients</CardTitle>
          {recipe.is_active && token && (
            <IngredientDialog
              rid={rid}
              recipeId={recipeId}
              token={token}
              products={products}
              trigger={<Button size="sm">Add ingredient</Button>}
            />
          )}
        </CardHeader>
        <CardContent>
          {recipe.ingredients.length === 0 ? (
            <p className="text-sm text-muted-foreground py-4">
              No ingredients yet. Add at least one before producing.
            </p>
          ) : (
            <div className="overflow-x-auto">
              <Table>
                <TableHeader>
                  <TableRow>
                    <TableHead>Product</TableHead>
                    <TableHead className="text-right">Quantity</TableHead>
                    <TableHead>Unit</TableHead>
                    <TableHead>Notes</TableHead>
                    <TableHead></TableHead>
                  </TableRow>
                </TableHeader>
                <TableBody>
                  {recipe.ingredients.map((ing) => {
                    const product = productMap[ing.product_id];
                    const productName = product?.name ?? ing.product_id.slice(0, 8);
                    const productUnit = product?.unit;
                    const unitMismatch =
                      productUnit !== undefined && productUnit !== ing.unit;
                    return (
                      <TableRow key={ing.id}>
                        <TableCell>
                          <div className="font-medium">{productName}</div>
                          {unitMismatch && (
                            <div className="text-xs text-amber-800">
                              Product unit is {productUnit} — fix before
                              producing.
                            </div>
                          )}
                        </TableCell>
                        <TableCell className="text-right font-mono">
                          {ing.quantity}
                        </TableCell>
                        <TableCell>{ing.unit}</TableCell>
                        <TableCell className="text-sm text-muted-foreground">
                          {ing.notes ?? "—"}
                        </TableCell>
                        <TableCell className="text-right space-x-1">
                          {recipe.is_active && token && (
                            <IngredientDialog
                              rid={rid}
                              recipeId={recipeId}
                              token={token}
                              existing={ing}
                              products={products}
                              trigger={
                                <Button variant="ghost" size="sm">
                                  Edit
                                </Button>
                              }
                            />
                          )}
                          {recipe.is_active && (
                            <Button
                              variant="ghost"
                              size="sm"
                              disabled={removeIngredientMutation.isPending}
                              onClick={() =>
                                removeIngredientMutation.mutate(ing.id)
                              }
                            >
                              Remove
                            </Button>
                          )}
                        </TableCell>
                      </TableRow>
                    );
                  })}
                </TableBody>
              </Table>
            </div>
          )}
          {removeIngredientMutation.isError && (
            <p className="text-sm text-destructive mt-2">
              {removeIngredientMutation.error.message}
            </p>
          )}
        </CardContent>
      </Card>

      {recipe.is_active && (
        <Card>
          <CardContent className="flex items-center justify-between pt-6">
            <div>
              <p className="text-sm font-medium">Delete recipe</p>
              <p className="text-xs text-muted-foreground">
                Soft delete — the recipe is hidden from active lists but past
                productions keep their reference.
              </p>
            </div>
            <Button
              variant="ghost"
              className="text-destructive hover:text-destructive"
              onClick={() => setPendingDelete(true)}
            >
              Delete
            </Button>
          </CardContent>
        </Card>
      )}

      <Dialog
        open={pendingDelete}
        onOpenChange={(o) => {
          if (!deleteMutation.isPending) setPendingDelete(o);
        }}
      >
        <DialogContent>
          <DialogHeader>
            <DialogTitle>Delete recipe?</DialogTitle>
            <DialogDescription>
              This soft-deletes the recipe. You can reactivate it later from
              the inactive filter. Past productions keep their reference.
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
              {deleteMutation.isPending ? "Deleting..." : "Delete"}
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </div>
  );
}
