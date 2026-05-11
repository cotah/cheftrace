"use client";

import { use, useRef, useState, type ChangeEvent, type DragEvent } from "react";
import { useRouter } from "next/navigation";
import Link from "next/link";
import { Camera } from "lucide-react";
import { useToken } from "@/hooks/use-token";
import { invoicesApi } from "@/lib/api/resources";
import { Button } from "@/components/ui/button";
import { Label } from "@/components/ui/label";

const MAX_BYTES = 10 * 1024 * 1024;
const ACCEPTED_MIME = new Set([
  "application/pdf",
  "image/jpeg",
  "image/png",
  "image/webp",
  // iPhone camera output (HEIC) and some Android cameras (HEIF). Gemini
  // 2.5 Flash supports both; backend `_MIME_EXT` maps them to .heic/.heif.
  "image/heic",
  "image/heif",
]);

export default function InvoiceUploadPage({
  params,
}: {
  params: Promise<{ restaurantId: string }>;
}) {
  const { restaurantId: rid } = use(params);
  const token = useToken();
  const router = useRouter();

  const [file, setFile] = useState<File | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const [dragOver, setDragOver] = useState(false);
  // Drives the camera input — clicking the "Take photo" button forwards to
  // this hidden <input> so the browser opens the device camera directly on
  // mobile. On desktop the `capture` attribute is silently ignored and the
  // file picker opens as a harmless fallback.
  const cameraInputRef = useRef<HTMLInputElement>(null);

  function pick(f: File | null) {
    setError(null);
    if (!f) {
      setFile(null);
      return;
    }
    if (!ACCEPTED_MIME.has(f.type)) {
      setError(`Unsupported file type: ${f.type || "unknown"}. Use PDF, JPG, PNG or WEBP.`);
      setFile(null);
      return;
    }
    if (f.size > MAX_BYTES) {
      setError(`File is ${(f.size / 1024 / 1024).toFixed(1)} MB — limit is 10 MB.`);
      setFile(null);
      return;
    }
    setFile(f);
  }

  function onInputChange(e: ChangeEvent<HTMLInputElement>) {
    pick(e.target.files?.[0] ?? null);
  }

  function onDrop(e: DragEvent<HTMLLabelElement>) {
    e.preventDefault();
    setDragOver(false);
    pick(e.dataTransfer.files?.[0] ?? null);
  }

  async function upload() {
    if (!file || !token) return;
    setBusy(true);
    setError(null);
    try {
      const { invoice_id, upload_url } = await invoicesApi.requestUploadUrl(
        rid,
        { filename: file.name, mime_type: file.type },
        token,
      );
      const res = await fetch(upload_url, {
        method: "PUT",
        headers: { "Content-Type": file.type },
        body: file,
      });
      if (!res.ok) {
        throw new Error(`Upload to storage failed (${res.status}). Check bucket CORS rules.`);
      }
      router.push(`/app/${rid}/invoices/${invoice_id}`);
    } catch (e) {
      setError(e instanceof Error ? e.message : "Upload failed");
      setBusy(false);
    }
  }

  return (
    <div className="mx-auto max-w-2xl space-y-6">
      <div>
        <Link
          href={`/app/${rid}/invoices`}
          className="text-sm text-muted-foreground hover:underline"
        >
          ← Invoices
        </Link>
        <h1 className="mt-2 text-2xl font-semibold">Upload invoice</h1>
        <p className="text-sm text-muted-foreground">
          PDF or image (JPG / PNG / WEBP / HEIC), up to 10 MB.
        </p>
      </div>

      <Label
        onDrop={onDrop}
        onDragOver={(e) => {
          e.preventDefault();
          setDragOver(true);
        }}
        onDragLeave={() => setDragOver(false)}
        className={`flex h-48 cursor-pointer flex-col items-center justify-center rounded-md border-2 border-dashed text-center transition-colors ${
          dragOver ? "border-primary bg-accent" : "border-muted-foreground/30"
        }`}
      >
        <p className="font-medium">
          {file ? file.name : "Drop a file here, or click to choose"}
        </p>
        {file && (
          <p className="mt-1 text-xs text-muted-foreground">
            {(file.size / 1024).toFixed(0)} KB · {file.type}
          </p>
        )}
        <input
          type="file"
          className="sr-only"
          accept=".pdf,image/jpeg,image/png,image/webp,.heic,.heif,image/heic,image/heif"
          onChange={onInputChange}
        />
      </Label>

      <div className="flex items-center gap-3">
        <div className="h-px flex-1 bg-border" />
        <p className="text-xs text-muted-foreground">or</p>
        <div className="h-px flex-1 bg-border" />
      </div>

      <input
        ref={cameraInputRef}
        type="file"
        className="sr-only"
        accept="image/*"
        capture="environment"
        onChange={onInputChange}
      />
      <Button
        type="button"
        variant="outline"
        className="w-full"
        onClick={() => cameraInputRef.current?.click()}
      >
        <Camera />
        Take photo
      </Button>

      {error && (
        <p className="rounded-md bg-destructive/10 p-3 text-sm text-destructive">{error}</p>
      )}

      <div className="flex items-center justify-end gap-2">
        <Link href={`/app/${rid}/invoices`}>
          <Button variant="ghost">Cancel</Button>
        </Link>
        <Button onClick={() => void upload()} disabled={!file || busy || !token}>
          {busy ? "Uploading..." : "Upload"}
        </Button>
      </div>
    </div>
  );
}
