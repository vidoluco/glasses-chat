// node --test relay/worker.test.mjs
import assert from "node:assert/strict";
import { createHmac } from "node:crypto";
import { test } from "node:test";
import worker, { Inbox, extractMessages } from "./worker.js";

const ME = "15550001111";
const env = () => {
  const map = new Map();
  const storage = {
    get: async (k) => map.get(k),
    put: async (k, v) => void map.set(k, structuredClone(v)),
    delete: async (keys) => keys.forEach((k) => map.delete(k)),
    list: async ({ prefix, limit }) =>
      new Map([...map].filter(([k]) => k.startsWith(prefix)).sort(([a], [b]) => (a < b ? -1 : 1)).slice(0, limit)),
  };
  const inbox = new Inbox({ storage });
  return {
    APP_SECRET: "app-secret",
    VERIFY_TOKEN: "verify-me",
    PULL_TOKEN: "pull-me",
    ALLOWED_FROM: ME,
    INBOX: { idFromName: () => "id", get: () => ({ fetch: (u, init) => inbox.fetch(new Request(u, init)) }) },
  };
};

const payload = (...msgs) => ({ entry: [{ changes: [{ value: { messages: msgs } }] }] });
const signed = (body, secret = "app-secret") =>
  new Request("https://relay/webhook", {
    method: "POST",
    body,
    headers: { "X-Hub-Signature-256": "sha256=" + createHmac("sha256", secret).update(body).digest("hex") },
  });
const pull = (e, token = "pull-me") =>
  worker.fetch(new Request("https://relay/pull", { headers: { Authorization: `Bearer ${token}` } }), e);

test("webhook verification echoes the challenge only with the right token", async () => {
  const e = env();
  const ok = await worker.fetch(new Request("https://relay/webhook?hub.mode=subscribe&hub.verify_token=verify-me&hub.challenge=42"), e);
  assert.equal(await ok.text(), "42");
  const bad = await worker.fetch(new Request("https://relay/webhook?hub.mode=subscribe&hub.verify_token=nope&hub.challenge=42"), e);
  assert.equal(bad.status, 403);
});

test("a signed message from the owner is stored, pulled, then acked away", async () => {
  const e = env();
  const res = await worker.fetch(signed(JSON.stringify(payload({ id: "wamid.1", from: ME, type: "text", text: { body: "ciao" } }))), e);
  assert.equal(res.status, 200);
  const { messages } = await (await pull(e)).json();
  assert.equal(messages.length, 1);
  assert.equal(messages[0].text.body, "ciao");
  assert.match(messages[0].id, /^m:/);
  await worker.fetch(new Request("https://relay/ack", { method: "POST", headers: { Authorization: "Bearer pull-me" }, body: JSON.stringify({ ids: [messages[0].id] }) }), e);
  assert.deepEqual((await (await pull(e)).json()).messages, []);
});

test("a bad signature is rejected and nothing is stored", async () => {
  const e = env();
  const res = await worker.fetch(signed(JSON.stringify(payload({ id: "wamid.2", from: ME, type: "text", text: { body: "x" } })), "wrong"), e);
  assert.equal(res.status, 401);
  assert.deepEqual((await (await pull(e)).json()).messages, []);
});

test("Meta retries do not duplicate a message", async () => {
  const e = env();
  const body = JSON.stringify(payload({ id: "wamid.3", from: ME, type: "text", text: { body: "una volta" } }));
  await worker.fetch(signed(body), e);
  await worker.fetch(signed(body), e);
  assert.equal((await (await pull(e)).json()).messages.length, 1);
});

test("pull needs the pull token", async () => {
  assert.equal((await pull(env(), "nope")).status, 401);
});

test("other senders and status updates are dropped", () => {
  const p = payload({ id: "a", from: "39000", type: "text" }, { id: "b", from: ME, type: "image" });
  p.entry[0].changes.push({ value: { statuses: [{ id: "s" }] } });
  assert.deepEqual(extractMessages(p, ME).map((m) => m.id), ["b"]);
});
