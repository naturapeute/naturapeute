from django.test import TestCase

from .teable_repository import (
    TeableArticle,
    TeableSymptom,
    TeableTag,
    _attachment_url,
    _string_list,
)
from .teable_schema import normalize_agreements, normalize_language_codes
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

    def test_teable_choice_values(self):
        self.assertEqual(
            normalize_language_codes(["FR", "en", "xx", "fr"]),
            ["fr", "en"],
        )
        self.assertEqual(
            normalize_agreements(
                ["ASCA", "Visana", "Diplôme Fédéral", "Euro Nature", None, "ASCA"]
            ),
            ["ASCA", "VISANA", "DIPLOMEFEDERAL", "EURONATURE"],
        )
        self.assertEqual(_string_list(['["RME", "EGK"]']), ["RME", "EGK"])
        self.assertEqual(
            _attachment_url([{"lgThumbnailUrl": "https://teable.example/photo.jpg"}]),
            "https://teable.example/photo.jpg",
        )

    def test_teable_article_tags_are_unique(self):
        article = TeableArticle(
            {
                "fields": {
                    "Source ID": 269,
                    "Title": "Article",
                    "Slug": "article",
                    "Tag Source IDs": "[32, 32, 32, 32]",
                    "Tag Names": '["Infos", "Symptomatologie", "Infos", "Symptomatologie"]',
                }
            },
            {32: TeableTag(32, "Symptomatologie", "symptomatologie")},
        )
        self.assertEqual([tag.name for tag in article.tags], ["Infos", "Symptomatologie"])

    def test_teable_symptom_parent_link(self):
        symptom = TeableSymptom(
            2,
            {"Name": "Child", "Parent Source ID": {"id": "rec-parent"}},
            {"rec-parent": 1},
        )
        self.assertEqual(symptom.parent_id, 1)
