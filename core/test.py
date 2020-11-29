from django.test import TestCase

from .utils import normalize_text, crypt, unique


class TestUtils(TestCase):

    def test_replace_words(self):
        self.assertEqual(normalize_text("café Thé"), "cafe the")
        self.assertEqual(normalize_text("maux de dos"), "dos")
        self.assertEqual(normalize_text("douleurs aux os"), "os")
        self.assertEqual(normalize_text("problème d'articulations"), "articuler")

    def test_hash_string(self):
        self.assertEqual(crypt("hi"), "49f68a5c8493ec2c0bf489821c21fc3b")
        self.assertEqual(len(crypt()), 32)
        self.assertNotEqual(crypt(), crypt())

    def test_unique_string(self):
        self.assertEqual(len(unique()), 12)
        self.assertEqual(len(unique(3)), 3)
