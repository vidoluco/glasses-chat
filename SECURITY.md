# Security

## What is exposed

The relay (`relay/worker.js`) is the only public endpoint.

- `POST /webhook` accepts a request only if its `X-Hub-Signature-256` is a valid
  HMAC-SHA256 of the body with your Meta app secret, and keeps only messages
  whose sender equals `ALLOWED_FROM`. Everything else is dropped.
- `GET /webhook` answers Meta's verification challenge only with `VERIFY_TOKEN`.
- `GET /pull` and `POST /ack` need `PULL_TOKEN` as a bearer token.

The Mac accepts no inbound connection: the bridge polls the relay over HTTPS.

## Secrets

| Secret | Where it lives |
|---|---|
| Meta app secret, verify token, pull token, allowed number | Worker secrets (`wrangler secret put`) |
| WhatsApp access token, pull token | `~/.config/glasses-chat/whatsapp.json`, mode 600 |
| ChatGPT login | the Codex CLI's own store |

None of them belongs in the repository.

## Where your data goes

Photo and question pass through WhatsApp, Meta's Cloud API and the relay's
Durable Object (deleted on ack), then to OpenAI through `codex exec`. If that is
not acceptable for what you look at, do not point the glasses at it.

## Reporting

Open a private security advisory on this repository.
