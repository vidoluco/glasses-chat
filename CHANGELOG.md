# Changelog

## 0.2.0 - 2026-10-31

- One sentence of at most 20 words, capped at `GLASSES_MAX_CHARS` (130). Measured on the glasses: 130 characters are read aloud, 160 are only announced as "a long message".
- Live web search through `codex --search` for questions about current facts, off with `GLASSES_WEB_SEARCH=0`.
- Answers are cleaned for speech: markdown links, bare URLs and emphasis marks are removed.
- The prompt carries today's date.

## 0.1.0 - 2026-10-31

- WhatsApp transport: the glasses send a photo and a question to a contact, the
  bridge replies, the glasses read the answer aloud.
- Relay on Cloudflare Workers with signature check, single-sender allow-list,
  retry dedup and pull/ack queue in a Durable Object.
- Bridge on the Mac: photo and question pairing, default question for a photo
  alone, answers through `codex exec` on a ChatGPT plan.
