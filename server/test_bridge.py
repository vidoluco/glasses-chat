import unittest

from bridge import DEFAULT_QUESTION, UNSUPPORTED, Pairer, answer, handle

ME = "15550001111"


class FakeWhatsApp:
    def __init__(self):
        self.sent = []

    def media(self, media_id):
        return f"jpeg:{media_id}".encode()

    def send(self, to, text):
        self.sent.append((to, text))


class PairerTest(unittest.TestCase):
    def test_question_after_photo_uses_the_photo(self):
        p = Pairer(photo_wait=20, pair_window=90)
        self.assertEqual(p.photo(ME, b"img", "", now=0), [])
        self.assertEqual(p.text(ME, "what plant is this?", now=8), [(ME, "what plant is this?", b"img")])
        self.assertEqual(p.due(now=100), [])

    def test_photo_alone_gets_default_question_after_wait(self):
        p = Pairer(photo_wait=20, pair_window=90)
        p.photo(ME, b"img", "", now=0)
        self.assertEqual(p.due(now=19), [])
        self.assertEqual(p.due(now=20), [(ME, DEFAULT_QUESTION, b"img")])
        self.assertEqual(p.due(now=40), [])

    def test_text_without_photo_has_no_image(self):
        self.assertEqual(Pairer().text(ME, "what time is it in Tokyo?", now=0), [(ME, "what time is it in Tokyo?", None)])

    def test_stale_photo_is_not_attached(self):
        p = Pairer(photo_wait=1000, pair_window=90)
        p.photo(ME, b"old", "", now=0)
        self.assertEqual(p.text(ME, "a new question", now=91), [(ME, "a new question", None)])

    def test_caption_answers_at_once(self):
        p = Pairer()
        self.assertEqual(p.photo(ME, b"img", "how much is it?", now=0), [(ME, "how much is it?", b"img")])
        self.assertEqual(p.due(now=10_000), [])

    def test_newer_photo_replaces_older(self):
        p = Pairer(photo_wait=20, pair_window=90)
        p.photo(ME, b"first", "", now=0)
        p.photo(ME, b"second", "", now=5)
        self.assertEqual(p.text(ME, "and this one?", now=6), [(ME, "and this one?", b"second")])


class HandleTest(unittest.TestCase):
    def test_image_is_downloaded_and_held(self):
        wa, p = FakeWhatsApp(), Pairer()
        msg = {"id": "m:1", "from": ME, "type": "image", "image": {"id": "MEDIA1"}}
        self.assertEqual(handle(msg, p, wa, now=0), [])
        self.assertEqual(p.text(ME, "what is it?", now=1), [(ME, "what is it?", b"jpeg:MEDIA1")])

    def test_text_becomes_a_job(self):
        msg = {"id": "m:2", "from": ME, "type": "text", "text": {"body": "  hello  "}}
        self.assertEqual(handle(msg, Pairer(), FakeWhatsApp(), now=0), [(ME, "hello", None)])

    def test_voice_note_gets_a_hint_and_no_job(self):
        wa = FakeWhatsApp()
        msg = {"id": "m:3", "from": ME, "type": "audio", "audio": {"id": "A"}}
        self.assertEqual(handle(msg, Pairer(), wa, now=0), [])
        self.assertEqual(wa.sent, [(ME, UNSUPPORTED)])


class AnswerTest(unittest.TestCase):
    def test_reply_goes_back_to_sender(self):
        wa = FakeWhatsApp()
        answer((ME, "what is it?", b"img"), wa, ask=lambda q, img: f"answer to {q} con {img!r}")
        self.assertEqual(wa.sent, [(ME, "answer to what is it? con b'img'")])

    def test_backend_failure_still_replies(self):
        def broken(q, img):
            raise RuntimeError("codex down")

        wa = FakeWhatsApp()
        answer((ME, "hello", None), wa, ask=broken)
        self.assertEqual(len(wa.sent), 1)
        self.assertIn("wrong", wa.sent[0][1])


if __name__ == "__main__":
    unittest.main()
