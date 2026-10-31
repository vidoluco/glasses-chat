#!/usr/bin/env python3
"""WhatsApp bridge: the glasses send a photo and a question to the bot's contact,
this answers on WhatsApp and the glasses read the reply aloud.

The Mac never accepts inbound connections: Meta calls the relay (relay/worker.js),
and this process pulls from it over HTTPS.

    python3 bridge.py        # config in ~/.config/glasses-chat/whatsapp.json
"""
import json
import os
import sys
import time
import urllib.request
from pathlib import Path

from server import ask_codex

CONFIG_FILE = Path(os.environ.get("GLASSES_WA_CONFIG", Path.home() / ".config/glasses-chat/whatsapp.json"))
GRAPH = os.environ.get("GLASSES_GRAPH", "https://graph.facebook.com")  # overridden by the e2e test
POLL_SECONDS = float(os.environ.get("GLASSES_POLL", "2"))
# "Hey Meta, take a photo and send it to Tony" and the spoken question arrive as
# two messages: a photo waits this long for its question, then gets a default one.
PHOTO_WAIT = float(os.environ.get("GLASSES_PHOTO_WAIT", "20"))
# a question this soon after a photo is about that photo
PAIR_WINDOW = float(os.environ.get("GLASSES_PAIR_WINDOW", "90"))
DEFAULT_QUESTION = "What am I looking at?"
UNSUPPORTED = "Send me a photo or a text message. I cannot listen to voice notes yet."


class Pairer:
    """Turns the incoming stream of photos and texts into (question, image) jobs."""

    def __init__(self, photo_wait=PHOTO_WAIT, pair_window=PAIR_WINDOW):
        self.photo_wait = photo_wait
        self.pair_window = pair_window
        self.photos = {}  # sender -> (arrived_at, image_bytes)

    def photo(self, sender, image, caption, now):
        if caption:
            self.photos.pop(sender, None)
            return [(sender, caption, image)]
        self.photos[sender] = (now, image)
        return []

    def text(self, sender, question, now):
        held = self.photos.pop(sender, None)
        if held and now - held[0] <= self.pair_window:
            return [(sender, question, held[1])]
        return [(sender, question, None)]

    def due(self, now):
        """Photos whose question never came."""
        jobs = []
        for sender, (at, image) in list(self.photos.items()):
            if now - at >= self.photo_wait:
                del self.photos[sender]
                jobs.append((sender, DEFAULT_QUESTION, image))
        return jobs


class WhatsApp:
    def __init__(self, token, phone_number_id, version):
        self.token = token
        self.phone_number_id = phone_number_id
        self.version = version

    def _call(self, url, data=None):
        req = urllib.request.Request(url, data=data, headers={"Authorization": f"Bearer {self.token}"})
        if data is not None:
            req.add_header("Content-Type", "application/json")
        with urllib.request.urlopen(req, timeout=30) as r:
            return r.read()

    def media(self, media_id):
        meta = json.loads(self._call(f"{GRAPH}/{self.version}/{media_id}"))
        return self._call(meta["url"])

    def send(self, to, text):
        body = {"messaging_product": "whatsapp", "to": to, "type": "text", "text": {"body": text}}
        self._call(f"{GRAPH}/{self.version}/{self.phone_number_id}/messages", json.dumps(body).encode())


class Relay:
    def __init__(self, url, token):
        self.url = url.rstrip("/")
        self.token = token

    def _call(self, path, data=None):
        # Cloudflare answers 403 to the default Python-urllib user agent
        req = urllib.request.Request(f"{self.url}{path}", data=data,
                                     headers={"Authorization": f"Bearer {self.token}",
                                              "User-Agent": "glasses-chat-bridge/1"})
        with urllib.request.urlopen(req, timeout=30) as r:
            return json.loads(r.read())

    def pull(self):
        return self._call("/pull")["messages"]

    def ack(self, ids):
        if ids:
            self._call("/ack", json.dumps({"ids": ids}).encode())


def handle(msg, pairer, wa, now):
    """One stored webhook message in, zero or more jobs out."""
    sender, kind = msg["from"], msg.get("type")
    if kind == "text":
        return pairer.text(sender, msg["text"]["body"].strip(), now)
    if kind == "image":
        image = wa.media(msg["image"]["id"])
        return pairer.photo(sender, image, msg["image"].get("caption", "").strip(), now)
    wa.send(sender, UNSUPPORTED)
    return []


def answer(job, wa, ask=ask_codex):
    sender, question, image = job
    t0 = time.monotonic()
    try:
        reply = ask(question, image)
    except Exception as e:
        print(f"error {e}", file=sys.stderr, flush=True)
        reply = "Something went wrong with the model, try again."
    wa.send(sender, reply)
    print(f"ok {time.monotonic() - t0:.1f}s photo={image is not None} q={question[:60]!r}",
          file=sys.stderr, flush=True)


def main():
    cfg = json.loads(CONFIG_FILE.read_text())
    relay = Relay(cfg["relay_url"], cfg["pull_token"])
    wa = WhatsApp(cfg["whatsapp_token"], cfg["phone_number_id"], cfg.get("graph_version", "v25.0"))
    pairer = Pairer()
    print(f"bridge polling {relay.url} every {POLL_SECONDS}s", file=sys.stderr, flush=True)
    while True:
        try:
            msgs = relay.pull()
            jobs = []
            for msg in msgs:
                try:
                    jobs += handle(msg, pairer, wa, time.monotonic())
                except Exception as e:  # one bad media download must not block the queue
                    print(f"message {msg.get('id')} skipped: {e}", file=sys.stderr, flush=True)
            # ack before answering: a crash mid-answer must not replay the question forever
            relay.ack([m["id"] for m in msgs])
            for job in jobs + pairer.due(time.monotonic()):
                answer(job, wa)
        except Exception as e:  # network blips: keep polling
            print(f"poll error {e}", file=sys.stderr, flush=True)
        time.sleep(POLL_SECONDS)


if __name__ == "__main__":
    main()
