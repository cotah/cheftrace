/**
 * Trigger browser download of a PDF endpoint with Bearer auth.
 *
 * Why blob+anchor instead of window.open: PDF endpoints require an
 * Authorization header, which window.open cannot send. We fetch with the
 * header, build a Blob URL, and click a synthetic <a download> to save.
 */

const API_URL = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";

export async function downloadPdf(
  path: string,
  token: string,
  filename: string,
): Promise<void> {
  const res = await fetch(`${API_URL}/api/v1${path}`, {
    headers: { Authorization: `Bearer ${token}` },
  });
  if (!res.ok) {
    const detail = await res.text().catch(() => res.statusText);
    throw new Error(`Failed to download PDF: ${res.status} ${detail}`);
  }
  const blob = await res.blob();
  const url = URL.createObjectURL(blob);
  const anchor = document.createElement("a");
  anchor.href = url;
  anchor.download = filename;
  document.body.appendChild(anchor);
  anchor.click();
  document.body.removeChild(anchor);
  URL.revokeObjectURL(url);
}
