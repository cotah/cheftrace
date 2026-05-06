"use client";

import { use, useState } from "react";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { useToken } from "@/hooks/use-token";
import { equipmentApi } from "@/lib/api/resources";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
  DialogTrigger,
} from "@/components/ui/dialog";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import type { Equipment, TemperatureLog } from "@/lib/api/types";

const EQUIPMENT_TYPES = [
  { value: "fridge", label: "Fridge (0–5°C)" },
  { value: "freezer", label: "Freezer (-25 to -18°C)" },
  { value: "hot_hold", label: "Hot Hold (63–90°C)" },
  { value: "dry_store", label: "Dry Store" },
  { value: "display", label: "Display Fridge (0–8°C)" },
  { value: "prep_table", label: "Prep Table (0–5°C)" },
  { value: "blast_chiller", label: "Blast Chiller" },
  { value: "other", label: "Other" },
];

const DEFAULT_RANGES: Record<string, { min: number; max: number } | null> = {
  fridge: { min: 0, max: 5 },
  freezer: { min: -25, max: -18 },
  hot_hold: { min: 63, max: 90 },
  display: { min: 0, max: 8 },
  prep_table: { min: 0, max: 5 },
  blast_chiller: { min: -18, max: 5 },
  dry_store: null,
  other: null,
};

function EquipmentTypeBadge({ type }: { type: string }) {
  const colors: Record<string, string> = {
    fridge: "bg-blue-100 text-blue-800",
    freezer: "bg-indigo-100 text-indigo-800",
    hot_hold: "bg-red-100 text-red-800",
    display: "bg-cyan-100 text-cyan-800",
    prep_table: "bg-teal-100 text-teal-800",
    blast_chiller: "bg-violet-100 text-violet-800",
    dry_store: "bg-amber-100 text-amber-800",
    other: "bg-gray-100 text-gray-800",
  };
  return (
    <span
      className={`rounded px-2 py-0.5 text-xs font-medium ${colors[type] ?? colors.other}`}
    >
      {type.replace("_", " ")}
    </span>
  );
}

function TempLogDialog({
  equipment,
  restaurantId,
  token,
}: {
  equipment: Equipment;
  restaurantId: string;
  token: string;
}) {
  const qc = useQueryClient();
  const [open, setOpen] = useState(false);
  const [temp, setTemp] = useState("");
  const [notes, setNotes] = useState("");

  const { data: logs = [] } = useQuery({
    queryKey: ["temp-logs", restaurantId, equipment.id],
    queryFn: () => equipmentApi.listTemperatureLogs(restaurantId, equipment.id, token),
    enabled: open && !!restaurantId && !!token,
  });

  const logMutation = useMutation({
    mutationFn: () =>
      equipmentApi.logTemperature(
        restaurantId,
        {
          equipment_id: equipment.id,
          temperature: parseFloat(temp),
          notes: notes || undefined,
        },
        token,
      ),
    onSuccess: () => {
      void qc.invalidateQueries({
        queryKey: ["temp-logs", restaurantId, equipment.id],
      });
      void qc.invalidateQueries({ queryKey: ["dashboard", restaurantId] });
      setTemp("");
      setNotes("");
    },
  });

  const isOutOfRange = (t: number) => {
    if (equipment.min_temp !== null && t < equipment.min_temp) return true;
    if (equipment.max_temp !== null && t > equipment.max_temp) return true;
    return false;
  };

  return (
    <Dialog open={open} onOpenChange={setOpen}>
      <DialogTrigger asChild>
        <Button variant="outline" size="sm">
          Log temp
        </Button>
      </DialogTrigger>
      <DialogContent className="max-w-md">
        <DialogHeader>
          <DialogTitle>{equipment.name} — Temperature Log</DialogTitle>
        </DialogHeader>
        <div className="space-y-4">
          {equipment.min_temp !== null && equipment.max_temp !== null && (
            <p className="text-sm text-muted-foreground">
              Safe range: {equipment.min_temp}°C to {equipment.max_temp}°C
            </p>
          )}
          <div className="flex gap-2">
            <div className="flex-1 space-y-1">
              <Label>Temperature (°C)</Label>
              <Input
                type="number"
                step="0.1"
                value={temp}
                onChange={(e) => setTemp(e.target.value)}
                placeholder="e.g. 4.5"
              />
            </div>
            <div className="flex-1 space-y-1">
              <Label>Notes (optional)</Label>
              <Input
                value={notes}
                onChange={(e) => setNotes(e.target.value)}
                placeholder="optional"
              />
            </div>
          </div>
          {temp && !isNaN(parseFloat(temp)) && isOutOfRange(parseFloat(temp)) && (
            <p className="text-sm text-destructive font-medium">
              ⚠ Temperature out of safe range
            </p>
          )}
          <Button
            className="w-full"
            disabled={!temp || logMutation.isPending}
            onClick={() => logMutation.mutate()}
          >
            {logMutation.isPending ? "Saving..." : "Record reading"}
          </Button>

          {logs.length > 0 && (
            <div className="border-t pt-3 space-y-1 max-h-48 overflow-y-auto">
              <p className="text-xs text-muted-foreground font-medium mb-2">
                Recent readings
              </p>
              {logs.slice(0, 20).map((log: TemperatureLog) => (
                <div key={log.id} className="flex items-center justify-between text-sm">
                  <span className="text-muted-foreground text-xs">
                    {new Date(log.recorded_at).toLocaleString("en-IE")}
                  </span>
                  <span
                    className={`font-mono ${
                      log.is_out_of_range ? "text-destructive font-semibold" : ""
                    }`}
                  >
                    {log.temperature}°C
                    {log.is_out_of_range && " ⚠"}
                  </span>
                </div>
              ))}
            </div>
          )}
        </div>
      </DialogContent>
    </Dialog>
  );
}

function AddEquipmentDialog({
  restaurantId,
  token,
}: {
  restaurantId: string;
  token: string;
}) {
  const qc = useQueryClient();
  const [open, setOpen] = useState(false);
  const [name, setName] = useState("");
  const [type, setType] = useState("");
  const [location, setLocation] = useState("");
  const [minTemp, setMinTemp] = useState("");
  const [maxTemp, setMaxTemp] = useState("");

  const handleTypeChange = (val: string) => {
    setType(val);
    const defaults = DEFAULT_RANGES[val];
    if (defaults) {
      setMinTemp(String(defaults.min));
      setMaxTemp(String(defaults.max));
    } else {
      setMinTemp("");
      setMaxTemp("");
    }
  };

  const createMutation = useMutation({
    mutationFn: () =>
      equipmentApi.create(
        restaurantId,
        {
          name,
          equipment_type: type,
          location: location || null,
          min_temp: minTemp ? parseFloat(minTemp) : null,
          max_temp: maxTemp ? parseFloat(maxTemp) : null,
        },
        token,
      ),
    onSuccess: () => {
      void qc.invalidateQueries({ queryKey: ["equipment", restaurantId] });
      setOpen(false);
      setName("");
      setType("");
      setLocation("");
      setMinTemp("");
      setMaxTemp("");
    },
  });

  return (
    <Dialog open={open} onOpenChange={setOpen}>
      <DialogTrigger asChild>
        <Button>Add equipment</Button>
      </DialogTrigger>
      <DialogContent>
        <DialogHeader>
          <DialogTitle>New equipment</DialogTitle>
        </DialogHeader>
        <div className="space-y-4 pt-2">
          <div className="space-y-2">
            <Label>Name</Label>
            <Input
              value={name}
              onChange={(e) => setName(e.target.value)}
              placeholder="e.g. Main Fridge"
            />
          </div>
          <div className="space-y-2">
            <Label>Type</Label>
            <Select value={type} onValueChange={handleTypeChange}>
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
          <div className="grid grid-cols-2 gap-3">
            <div className="space-y-2">
              <Label>Min temp (°C)</Label>
              <Input
                type="number"
                step="0.1"
                value={minTemp}
                onChange={(e) => setMinTemp(e.target.value)}
                placeholder="optional"
              />
            </div>
            <div className="space-y-2">
              <Label>Max temp (°C)</Label>
              <Input
                type="number"
                step="0.1"
                value={maxTemp}
                onChange={(e) => setMaxTemp(e.target.value)}
                placeholder="optional"
              />
            </div>
          </div>
          <div className="space-y-2">
            <Label>Location (optional)</Label>
            <Input
              value={location}
              onChange={(e) => setLocation(e.target.value)}
              placeholder="e.g. Main Kitchen"
            />
          </div>
          <Button
            className="w-full"
            disabled={!name || !type || createMutation.isPending}
            onClick={() => createMutation.mutate()}
          >
            {createMutation.isPending ? "Creating..." : "Create equipment"}
          </Button>
          {createMutation.isError && (
            <p className="text-sm text-destructive">{createMutation.error.message}</p>
          )}
        </div>
      </DialogContent>
    </Dialog>
  );
}

export default function EquipmentPage({
  params,
}: {
  params: Promise<{ restaurantId: string }>;
}) {
  const { restaurantId: rid } = use(params);
  const token = useToken();

  const { data: equipment = [], isLoading } = useQuery({
    queryKey: ["equipment", rid],
    queryFn: () => equipmentApi.list(rid, token!),
    enabled: !!rid && !!token,
  });

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <h1 className="text-2xl font-semibold">Equipment</h1>
        {token && <AddEquipmentDialog restaurantId={rid} token={token} />}
      </div>

      {isLoading ? (
        <p className="text-muted-foreground">Loading...</p>
      ) : equipment.length === 0 ? (
        <Card>
          <CardContent className="py-8 text-center">
            <p className="text-muted-foreground">
              No equipment added yet. Add your fridges, freezers, and other
              temperature-controlled units to start logging.
            </p>
          </CardContent>
        </Card>
      ) : (
        <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-3">
          {equipment.map((eq: Equipment) => (
            <Card key={eq.id}>
              <CardHeader className="pb-2">
                <div className="flex items-start justify-between gap-2">
                  <CardTitle className="text-base">{eq.name}</CardTitle>
                  <EquipmentTypeBadge type={eq.equipment_type} />
                </div>
                {eq.location && (
                  <p className="text-xs text-muted-foreground">{eq.location}</p>
                )}
              </CardHeader>
              <CardContent className="space-y-3">
                {eq.min_temp !== null && eq.max_temp !== null ? (
                  <p className="text-sm text-muted-foreground">
                    Range: {eq.min_temp}°C to {eq.max_temp}°C
                  </p>
                ) : (
                  <p className="text-sm text-muted-foreground">
                    No temperature range set
                  </p>
                )}
                {token && (
                  <TempLogDialog equipment={eq} restaurantId={rid} token={token} />
                )}
              </CardContent>
            </Card>
          ))}
        </div>
      )}
    </div>
  );
}
