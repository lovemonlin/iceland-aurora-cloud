import assert from "node:assert/strict";
import { afterEach, mock, test } from "node:test";
import worker from "../src/index.ts";

const dispatchUrl =
  "https://api.github.com/repos/lovemonlin/iceland-aurora-cloud/actions/workflows/update-road-info.yml/dispatches";
const token = "fake-token-for-tests";
const missingTokenMessage = "IRCA road scheduler: GITHUB_TOKEN is not configured.";
const dispatchFailureMessage = "IRCA road scheduler: GitHub dispatch did not return 204.";
const networkFailureMessage = "IRCA road scheduler: GitHub dispatch request failed.";

function fakeFetch(response: Response | Error) {
  return mock.method(globalThis, "fetch", async () => {
    if (response instanceof Error) throw response;
    return response;
  });
}

function fakeErrorLog() {
  return mock.method(console, "error", () => undefined);
}

afterEach(() => {
  mock.restoreAll();
});

test("scheduled dispatches the fixed workflow URL once", async () => {
  const fetch = fakeFetch(new Response(null, { status: 204 }));

  await worker.scheduled({}, { GITHUB_TOKEN: token }, {});

  assert.equal(fetch.mock.callCount(), 1);
  assert.equal(fetch.mock.calls[0]?.arguments[0], dispatchUrl);
});

test("scheduled uses POST with manual redirects", async () => {
  const fetch = fakeFetch(new Response(null, { status: 204 }));

  await worker.scheduled({}, { GITHUB_TOKEN: token }, {});

  const options = fetch.mock.calls[0]?.arguments[1] as RequestInit;
  assert.equal(options.method, "POST");
  assert.equal(options.redirect, "manual");
});

test("scheduled dispatches the main ref only", async () => {
  const fetch = fakeFetch(new Response(null, { status: 204 }));

  await worker.scheduled({}, { GITHUB_TOKEN: token }, {});

  const options = fetch.mock.calls[0]?.arguments[1] as RequestInit;
  assert.equal(options.body, JSON.stringify({ ref: "main" }));
});

test("scheduled uses the fixed workflow dispatch headers", async () => {
  const fetch = fakeFetch(new Response(null, { status: 204 }));

  await worker.scheduled({}, { GITHUB_TOKEN: token }, {});

  const headers = new Headers((fetch.mock.calls[0]?.arguments[1] as RequestInit).headers);
  assert.equal(headers.get("accept"), "application/vnd.github+json");
  assert.equal(headers.get("authorization"), `Bearer ${token}`);
  assert.equal(headers.get("user-agent"), "iceland-aurora-road-scheduler");
  assert.equal(headers.get("x-github-api-version"), "2022-11-28");
});

test("a 204 dispatch resolves without logging", async () => {
  fakeFetch(new Response(null, { status: 204 }));
  const error = fakeErrorLog();

  await worker.scheduled({}, { GITHUB_TOKEN: token }, {});

  assert.equal(error.mock.callCount(), 0);
});

test("a non-204 response logs and rejects with a fixed diagnostic", async () => {
  const fetch = fakeFetch(new Response("response-body-must-not-leak", { status: 500 }));
  const error = fakeErrorLog();

  await assert.rejects(worker.scheduled({}, { GITHUB_TOKEN: token }, {}), { message: dispatchFailureMessage });

  assert.equal(fetch.mock.callCount(), 1);
  assert.deepEqual(error.mock.calls[0]?.arguments, [dispatchFailureMessage]);
});

test("a redirect logs and rejects without following it", async () => {
  const fetch = fakeFetch(new Response(null, { status: 302 }));
  const error = fakeErrorLog();

  await assert.rejects(worker.scheduled({}, { GITHUB_TOKEN: token }, {}), { message: dispatchFailureMessage });

  assert.equal(fetch.mock.callCount(), 1);
  assert.deepEqual(error.mock.calls[0]?.arguments, [dispatchFailureMessage]);
});

test("missing tokens do not fetch and reject without leaking supplied values", async () => {
  const fetch = fakeFetch(new Response(null, { status: 204 }));
  const error = fakeErrorLog();

  await assert.rejects(worker.scheduled({}, { GITHUB_TOKEN: "" }, {}), { message: missingTokenMessage });

  assert.equal(fetch.mock.callCount(), 0);
  assert.deepEqual(error.mock.calls[0]?.arguments, [missingTokenMessage]);
});

test("network errors log and reject without exception text", async () => {
  const fetch = fakeFetch(new Error("network details must not leak"));
  const error = fakeErrorLog();

  await assert.rejects(worker.scheduled({}, { GITHUB_TOKEN: token }, {}), { message: networkFailureMessage });

  assert.equal(fetch.mock.callCount(), 1);
  assert.deepEqual(error.mock.calls[0]?.arguments, [networkFailureMessage]);
});

test("health fetch returns JSON and never dispatches", async () => {
  const fetch = fakeFetch(new Response(null, { status: 204 }));

  const response = await worker.fetch();

  assert.deepEqual(await response.json(), { ok: true, service: "irca-road-scheduler" });
  assert.equal(fetch.mock.callCount(), 0);
});
