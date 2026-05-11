import { afterEach, beforeEach, expect, test, vi } from "vitest";
import { posApi } from "@/lib/api/resources";

const originalFetch = globalThis.fetch;

beforeEach(() => {
  globalThis.fetch = vi.fn().mockResolvedValue({
    ok: true,
    status: 200,
    json: async () => ({}),
  }) as unknown as typeof fetch;
});

afterEach(() => {
  globalThis.fetch = originalFetch;
  vi.restoreAllMocks();
});

function lastCall(): [string, RequestInit | undefined] {
  const mock = globalThis.fetch as unknown as ReturnType<typeof vi.fn>;
  const call = mock.mock.calls[0];
  return [String(call[0]), call[1]];
}

// --- integrations --- //

test("listIntegrations hits the right URL", async () => {
  await posApi.listIntegrations("rid-1", "tok");
  const [url] = lastCall();
  expect(url).toMatch(/\/restaurants\/rid-1\/pos\/integrations$/);
});

test("createIntegration posts the body", async () => {
  await posApi.createIntegration(
    "rid-1",
    { provider: "square", name: "Main", external_location_id: "L_1" },
    "tok",
  );
  const [url, init] = lastCall();
  expect(url).toMatch(/\/restaurants\/rid-1\/pos\/integrations$/);
  expect(init?.method).toBe("POST");
  expect(init?.body).toBe(
    JSON.stringify({ provider: "square", name: "Main", external_location_id: "L_1" }),
  );
});

test("setCredentials uses PUT on the /credentials sub-path", async () => {
  await posApi.setCredentials(
    "rid-1",
    "int-1",
    { access_token: "tok-x", webhook_signing_key: "sig-y" },
    "tok",
  );
  const [url, init] = lastCall();
  expect(url).toMatch(/\/restaurants\/rid-1\/pos\/integrations\/int-1\/credentials$/);
  expect(init?.method).toBe("PUT");
  expect(init?.body).toBe(
    JSON.stringify({ access_token: "tok-x", webhook_signing_key: "sig-y" }),
  );
});

// --- mappings --- //

test("createMapping supports recipe_id=null (ignore state)", async () => {
  await posApi.createMapping(
    "rid-1",
    "int-1",
    {
      external_item_id: "gift_card",
      external_item_name_snapshot: "Gift Card",
      recipe_id: null,
      units_per_sale: 1,
    },
    "tok",
  );
  const [url, init] = lastCall();
  expect(url).toMatch(
    /\/restaurants\/rid-1\/pos\/integrations\/int-1\/mappings$/,
  );
  expect(init?.body).toContain('"recipe_id":null');
});

// --- events --- //

test("listEvents without status filter has no querystring", async () => {
  await posApi.listEvents("rid-1", undefined, "tok");
  const [url] = lastCall();
  expect(url).toMatch(/\/restaurants\/rid-1\/pos\/events$/);
});

test("listEvents with status filter encodes the param", async () => {
  await posApi.listEvents("rid-1", "needs_mapping", "tok");
  const [url] = lastCall();
  expect(url).toContain("?status=needs_mapping");
});

test("processEvent without force has no querystring", async () => {
  await posApi.processEvent("rid-1", "evt-1", false, "tok");
  const [url, init] = lastCall();
  expect(url).toMatch(
    /\/restaurants\/rid-1\/pos\/events\/evt-1\/process$/,
  );
  expect(init?.method).toBe("POST");
});

test("processEvent with force=true appends ?force=true", async () => {
  await posApi.processEvent("rid-1", "evt-1", true, "tok");
  const [url] = lastCall();
  expect(url).toContain("?force=true");
});
