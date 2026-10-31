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

    def test_long_answer_keeps_the_first_sentence(self):
        raw = ("Today in Borca di Cadore, expect sunshine with some clouds and a high around 11 degrees. "
               "It'll be cold this evening, with temperatures dropping close to freezing.")
        self.assertEqual(speakable(raw), "Today in Borca di Cadore, expect sunshine with some clouds "
                                         "and a high around 11 degrees.")

    def test_long_single_sentence_is_cut_at_a_word(self):
        out = speakable("word " * 40, max_chars=30)
        self.assertLessEqual(len(out), 31)
        self.assertTrue(out.endswith("word."))

    def test_plain_answer_is_unchanged(self):
        self.assertEqual(speakable("Seven times eight is fifty-six."), "Seven times eight is fifty-six.")


if __name__ == "__main__":
    unittest.main()
