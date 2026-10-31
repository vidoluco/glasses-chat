# Changelog

## 0.1.0 - 2026-10-31

- WhatsApp transport: the glasses send a photo and a question to a contact, the
  bridge replies, the glasses read the answer aloud.
- Relay on Cloudflare Workers with signature check, single-sender allow-list,
  retry dedup and pull/ack queue in a Durable Object.
- Bridge on the Mac: photo and question pairing, default question for a photo
  alone, answers through `codex exec` on a ChatGPT plan.
