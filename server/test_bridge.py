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
        self.assertEqual(p.text(ME, "che pianta e'?", now=8), [(ME, "che pianta e'?", b"img")])
        self.assertEqual(p.due(now=100), [])

    def test_photo_alone_gets_default_question_after_wait(self):
        p = Pairer(photo_wait=20, pair_window=90)
        p.photo(ME, b"img", "", now=0)
        self.assertEqual(p.due(now=19), [])
        self.assertEqual(p.due(now=20), [(ME, DEFAULT_QUESTION, b"img")])
        self.assertEqual(p.due(now=40), [])

    def test_text_without_photo_has_no_image(self):
        self.assertEqual(Pairer().text(ME, "che ore sono a Tokyo?", now=0), [(ME, "che ore sono a Tokyo?", None)])

    def test_stale_photo_is_not_attached(self):
        p = Pairer(photo_wait=1000, pair_window=90)
        p.photo(ME, b"old", "", now=0)
        self.assertEqual(p.text(ME, "domanda nuova", now=91), [(ME, "domanda nuova", None)])

    def test_caption_answers_at_once(self):
        p = Pairer()
        self.assertEqual(p.photo(ME, b"img", "quanto costa?", now=0), [(ME, "quanto costa?", b"img")])
        self.assertEqual(p.due(now=10_000), [])

    def test_newer_photo_replaces_older(self):
        p = Pairer(photo_wait=20, pair_window=90)
        p.photo(ME, b"first", "", now=0)
        p.photo(ME, b"second", "", now=5)
        self.assertEqual(p.text(ME, "e questo?", now=6), [(ME, "e questo?", b"second")])


class HandleTest(unittest.TestCase):
    def test_image_is_downloaded_and_held(self):
        wa, p = FakeWhatsApp(), Pairer()
        msg = {"id": "m:1", "from": ME, "type": "image", "image": {"id": "MEDIA1"}}
        self.assertEqual(handle(msg, p, wa, now=0), [])
        self.assertEqual(p.text(ME, "cos'e'?", now=1), [(ME, "cos'e'?", b"jpeg:MEDIA1")])

    def test_text_becomes_a_job(self):
        msg = {"id": "m:2", "from": ME, "type": "text", "text": {"body": "  ciao  "}}
        self.assertEqual(handle(msg, Pairer(), FakeWhatsApp(), now=0), [(ME, "ciao", None)])

    def test_voice_note_gets_a_hint_and_no_job(self):
        wa = FakeWhatsApp()
        msg = {"id": "m:3", "from": ME, "type": "audio", "audio": {"id": "A"}}
        self.assertEqual(handle(msg, Pairer(), wa, now=0), [])
        self.assertEqual(wa.sent, [(ME, UNSUPPORTED)])


class AnswerTest(unittest.TestCase):
    def test_reply_goes_back_to_sender(self):
        wa = FakeWhatsApp()
        answer((ME, "cos'e'?", b"img"), wa, ask=lambda q, img: f"risposta a {q} con {img!r}")
        self.assertEqual(wa.sent, [(ME, "risposta a cos'e'? con b'img'")])

    def test_backend_failure_still_replies(self):
        def broken(q, img):
            raise RuntimeError("codex down")

        wa = FakeWhatsApp()
        answer((ME, "ciao", None), wa, ask=broken)
        self.assertEqual(len(wa.sent), 1)
        self.assertIn("problema", wa.sent[0][1])


if __name__ == "__main__":
    unittest.main()
