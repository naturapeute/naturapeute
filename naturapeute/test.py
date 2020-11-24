from django.test import TestCase

from .utils import normalize_text


class TestUtils(TestCase):

    def test_replace_words(self):
        self.assertEqual(normalize_text("café Thé"), "cafe the")
        self.assertEqual(normalize_text("maux de dos"), "dos")
        self.assertEqual(normalize_text("douleurs aux os"), "os")
        self.assertEqual(normalize_text("problème d'articulations"), "articuler")
