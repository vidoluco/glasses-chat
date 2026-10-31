// Relay between the WhatsApp Cloud API and the Mac: Meta calls the webhook here,
// the Mac pulls over HTTPS, so the Mac never accepts inbound connections.
//
// Secrets (wrangler secret put): APP_SECRET, VERIFY_TOKEN, PULL_TOKEN, ALLOWED_FROM.

const enc = new TextEncoder();

async function validSignature(secret, body, header) {
  if (!header || !header.startsWith("sha256=")) return false;
  const key = await crypto.subtle.importKey("raw", enc.encode(secret), { name: "HMAC", hash: "SHA-256" }, false, ["sign"]);
  const mac = new Uint8Array(await crypto.subtle.sign("HMAC", key, enc.encode(body)));
  const expected = "sha256=" + [...mac].map((b) => b.toString(16).padStart(2, "0")).join("");
  return timingSafeEqual(expected, header);
}

function timingSafeEqual(a, b) {
  if (a.length !== b.length) return false;
  let diff = 0;
  for (let i = 0; i < a.length; i++) diff |= a.charCodeAt(i) ^ b.charCodeAt(i);
  return diff === 0;
}

// only messages from the owner's number; statuses and other senders are dropped
export function extractMessages(payload, allowedFrom) {
  const out = [];
  for (const entry of payload.entry || []) {
    for (const change of entry.changes || []) {
      for (const msg of change.value?.messages || []) {
        if (msg.from === allowedFrom) out.push(msg);
      }
    }
  }
  return out;
}

const json = (data, status = 200) =>
  new Response(JSON.stringify(data), { status, headers: { "Content-Type": "application/json" } });

export class Inbox {
  constructor(state) {
    this.storage = state.storage;
  }

  async fetch(request) {
    const { pathname } = new URL(request.url);
    if (pathname === "/store") {
      for (const msg of await request.json()) {
        // Meta retries deliveries: store each message id once
        if (await this.storage.get(`seen:${msg.id}`)) continue;
        await this.storage.put(`seen:${msg.id}`, Date.now());
        const key = `m:${String(Date.now()).padStart(15, "0")}:${msg.id}`;
        await this.storage.put(key, msg);
      }
      return json({ ok: true });
    }
    if (pathname === "/pull") {
      const stored = await this.storage.list({ prefix: "m:", limit: 50 });
      return json({ messages: [...stored].map(([key, msg]) => ({ ...msg, id: key })) });
    }
    if (pathname === "/ack") {
      const { ids } = await request.json();
      await this.storage.delete(ids.filter((id) => id.startsWith("m:")));
      return json({ ok: true });
    }
    return json({ error: "not found" }, 404);
  }
}

export default {
  async fetch(request, env) {
    const url = new URL(request.url);
    const inbox = env.INBOX.get(env.INBOX.idFromName("inbox"));

    if (url.pathname === "/webhook" && request.method === "GET") {
      const p = url.searchParams;
      if (p.get("hub.mode") === "subscribe" && p.get("hub.verify_token") === env.VERIFY_TOKEN) {
        return new Response(p.get("hub.challenge"));
      }
      return new Response("forbidden", { status: 403 });
    }

    if (url.pathname === "/webhook" && request.method === "POST") {
      const body = await request.text();
      if (!(await validSignature(env.APP_SECRET, body, request.headers.get("X-Hub-Signature-256")))) {
        return new Response("bad signature", { status: 401 });
      }
      const msgs = extractMessages(JSON.parse(body), env.ALLOWED_FROM);
      if (msgs.length) {
        await inbox.fetch("https://inbox/store", { method: "POST", body: JSON.stringify(msgs) });
      }
      return new Response("ok");
    }

    if (url.pathname === "/pull" || url.pathname === "/ack") {
      if (!timingSafeEqual(request.headers.get("Authorization") || "", `Bearer ${env.PULL_TOKEN}`)) {
        return json({ error: "token" }, 401);
      }
      const body = request.method === "POST" ? await request.text() : undefined;
      return inbox.fetch(`https://inbox${url.pathname}`, { method: request.method, body });
    }

    return new Response("not found", { status: 404 });
  },
};
