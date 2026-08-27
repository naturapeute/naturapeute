from types import SimpleNamespace
from unittest.mock import patch

from django.core import mail
from django.test import TestCase, override_settings
from django.urls import reverse


@override_settings(
    EMAIL_BACKEND="django.core.mail.backends.locmem.EmailBackend",
    ACCOUNT_MAGIC_LINK_COOLDOWN_SECONDS=0,
)
class AccountViewTests(TestCase):
    def setUp(self):
        self.therapist = SimpleNamespace(
            pk=2596,
            email="therapist@example.ch",
        )

    @patch("naturapeute.account_views.get_teable_repository")
    @patch("naturapeute.account_views.teable_enabled", return_value=True)
    def test_known_therapist_receives_a_signed_login_link(self, _teable_enabled, repository):
        repository.return_value.therapist_by_email_or_id.return_value = self.therapist

        response = self.client.post(reverse("account"), {"email": self.therapist.email})

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "lien de connexion vient d'être envoyé")
        self.assertEqual(len(mail.outbox), 1)
        self.assertIn("/account/verify/", mail.outbox[0].body)

    @patch("naturapeute.account_views.get_teable_repository")
    @patch("naturapeute.account_views.teable_enabled", return_value=True)
    def test_unknown_email_shows_an_error(self, _teable_enabled, repository):
        repository.return_value.therapist_by_email_or_id.return_value = None

        response = self.client.post(reverse("account"), {"email": "unknown@example.ch"})

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Aucun profil thérapeute n")
        self.assertEqual(len(mail.outbox), 0)

    @patch("naturapeute.account_views.get_teable_repository")
    @patch("naturapeute.account_views.teable_enabled", return_value=True)
    def test_valid_login_link_creates_a_therapist_session(self, _teable_enabled, repository):
        repository.return_value.therapist_by_email_or_id.return_value = self.therapist
        self.client.post(reverse("account"), {"email": self.therapist.email})
        link = mail.outbox[0].body.splitlines()[3]

        response = self.client.get(link)

        self.assertRedirects(
            response,
            reverse("account_profile"),
            fetch_redirect_response=False,
        )
        self.assertEqual(self.client.session["account_therapist_id"], self.therapist.pk)
