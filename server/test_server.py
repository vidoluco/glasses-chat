import unittest

from server import speakable


class SpeakableTest(unittest.TestCase):
    def test_source_link_in_brackets_is_dropped(self):
        raw = ("Clear skies today, between 1 and 11 degrees. "
               "([Tempo Italia](https://meteo.tempoitalia.it/previsioni/borca-di-cadore?d=3))")
        self.assertEqual(speakable(raw), "Clear skies today, between 1 and 11 degrees.")

    def test_inline_link_keeps_its_text(self):
        self.assertEqual(speakable("It is the [Duomo](https://example.com/duomo) of Milan."),
                         "It is the Duomo of Milan.")

    def test_bare_url_is_dropped(self):
        self.assertEqual(speakable("Opening hours are on https://example.com/hours today."),
                         "Opening hours are on today.")

    def test_emphasis_marks_are_removed(self):
        self.assertEqual(speakable("It is **very** cold."), "It is very cold.")

    def test_plain_answer_is_unchanged(self):
        self.assertEqual(speakable("Seven times eight is fifty-six."), "Seven times eight is fifty-six.")


if __name__ == "__main__":
    unittest.main()
