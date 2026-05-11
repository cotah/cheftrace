import { afterEach, beforeEach, expect, test, vi } from "vitest";
import { recipesApi } from "@/lib/api/resources";

const originalFetch = globalThis.fetch;

beforeEach(() => {
  globalThis.fetch = vi.fn().mockResolvedValue({
    ok: true,
    status: 200,
    json: async () => [],
  }) as unknown as typeof fetch;
});

afterEach(() => {
  globalThis.fetch = originalFetch;
  vi.restoreAllMocks();
});

test("list without isActive omits the query param", async () => {
  await recipesApi.list("rid-1", "tok");
  const call = (globalThis.fetch as unknown as ReturnType<typeof vi.fn>).mock
    .calls[0];
  expect(String(call[0])).toMatch(/\/restaurants\/rid-1\/recipes$/);
});

test("list with isActive=true appends ?is_active=true", async () => {
  await recipesApi.list("rid-1", "tok", true);
  const call = (globalThis.fetch as unknown as ReturnType<typeof vi.fn>).mock
    .calls[0];
  expect(String(call[0])).toMatch(/\?is_active=true$/);
});

test("list with isActive=false appends ?is_active=false", async () => {
  await recipesApi.list("rid-1", "tok", false);
  const call = (globalThis.fetch as unknown as ReturnType<typeof vi.fn>).mock
    .calls[0];
  expect(String(call[0])).toMatch(/\?is_active=false$/);
});

test("producePreview POSTs the batches body", async () => {
  await recipesApi.producePreview("rid-1", "rec-1", 2.5, "tok");
  const call = (globalThis.fetch as unknown as ReturnType<typeof vi.fn>).mock
    .calls[0];
  expect(String(call[0])).toMatch(
    /\/restaurants\/rid-1\/recipes\/rec-1\/produce\/preview$/,
  );
  expect(call[1]?.method).toBe("POST");
  expect(call[1]?.body).toBe(JSON.stringify({ batches: 2.5 }));
});
