import assert from "node:assert/strict";
import test from "node:test";
import { createMlServiceClient, MlServiceClientError } from "../src/clients/mlService.client.js";

test("ML client applies strict timeout and maps only supported parameters", async () => {
  let configuration;
  let request;
  const axiosInstance = {
    get: async (path, options) => {
      request = { path, options };
      return { data: { ok: true } };
    },
  };
  const client = createMlServiceClient({
    baseURL: "http://localhost:8000", timeout: 5000, internalKey: "service-key", axiosInstance,
  });
  const value = await client.recommendations("user/id", {
    mediaType: "movie", limit: 20, context: "home", excludeSeen: true,
  });
  assert.deepEqual(value, { ok: true });
  assert.equal(request.path, "/recommendations/user%2Fid");
  assert.equal(request.options.params.media_type, "movie");
  assert.equal(request.options.params.debug, undefined);
  assert.equal(request.options.headers["X-Internal-Key"], "service-key");
});

test("ML client converts transport and timeout details to safe errors", async () => {
  const client = createMlServiceClient({
    baseURL: "http://localhost:8000", timeout: 5000,
    axiosInstance: { get: async () => { const error = new Error("secret URL"); error.code = "ECONNABORTED"; throw error; } },
  });
  await assert.rejects(() => client.recommendations("user", {}), (error) => {
    assert.ok(error instanceof MlServiceClientError);
    assert.equal(error.message, "ML service timed out");
    assert.ok(!error.message.includes("secret"));
    return true;
  });
});

test("ML client rejects unsafe timeout configuration", () => {
  assert.throws(
    () => createMlServiceClient({ baseURL: "not-a-url", timeout: 999999 }),
    MlServiceClientError
  );
});
