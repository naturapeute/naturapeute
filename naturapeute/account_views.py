import json
import logging
import time

from django.conf import settings
from django.core import signing
from django.core.mail import send_mail

from django.shortcuts import redirect, render
from django.urls import reverse
from django.views import View

from core.teable_repository import get_teable_repository, teable_enabled
from core.teable_schema import normalize_agreements

from .forms import AccountEmailForm, TherapistProfileForm


logger = logging.getLogger(__name__)
SESSION_THERAPIST_ID = "account_therapist_id"
SESSION_LAST_LINK_SENT = "account_last_link_sent"
MAGIC_LINK_SALT = "naturapeute.account.magic-link"


def _repository_or_unavailable(request):
    if not teable_enabled():
        return None, render(
            request,
            "account/unavailable.html",
            status=503,
        )
    return get_teable_repository(), None


def _therapist_session_id(therapist):
    return therapist.pk if therapist.pk is not None else therapist._record_id


def _session_therapist(request, repository):
    therapist_id = request.session.get(SESSION_THERAPIST_ID)
    if therapist_id is None:
        return None
    therapist = repository.therapist_by_email_or_id(therapist_id, members_only=False)
    if therapist is None:
        request.session.pop(SESSION_THERAPIST_ID, None)
    return therapist


def _profile_fields(therapist, cleaned_data):
    socials = [
        social
        for social in therapist.socials
        if isinstance(social, dict) and social.get("name") not in {"website", "facebook"}
    ]
    for name in ("website", "facebook"):
        if url := cleaned_data[name]:
            socials.append({"name": name, "url": url})

    primary_practice = cleaned_data["primary_practice"] or None
    selected_practices = list(dict.fromkeys(cleaned_data["practices"]))
    if primary_practice and primary_practice not in selected_practices:
        selected_practices.insert(0, primary_practice)
    other_practices = [
        int(practice_id)
        for practice_id in selected_practices
        if practice_id != primary_practice
    ]

    return {
        "Name": cleaned_data["display_name"],
        "Firstname": cleaned_data["firstname"],
        "Lastname": cleaned_data["lastname"],
        "Gender": cleaned_data["gender"],
        "Email": cleaned_data["email"],
        "Phone": cleaned_data["phone"],
        "Description": cleaned_data["description"],
        "Price": cleaned_data["price"],
        "Timetable": cleaned_data["timetable"],
        "Languages": cleaned_data["languages"],
        "Agreements": normalize_agreements(cleaned_data["agreements"]),
        "Payment Types": cleaned_data["payment_types"],
        "Socials": json.dumps(socials, ensure_ascii=False),
        "Calendly URL": cleaned_data["calendly_url"],
        "Primary Practice Source ID": primary_practice,
        "Practice Source IDs": json.dumps(other_practices),
    }


class AccountView(View):
    template_name = "account/login.html"

    def get(self, request):
        repository, unavailable = _repository_or_unavailable(request)
        if unavailable:
            return unavailable
        if _session_therapist(request, repository):
            return redirect("account_profile")
        return render(request, self.template_name, {"form": AccountEmailForm()})

    def post(self, request):
        repository, unavailable = _repository_or_unavailable(request)
        if unavailable:
            return unavailable

        form = AccountEmailForm(request.POST)
        if form.is_valid():
            email = form.cleaned_data["email"]
            now = time.time()
            cooldown = getattr(settings, "ACCOUNT_MAGIC_LINK_COOLDOWN_SECONDS", 60)
            last_sent = request.session.get(SESSION_LAST_LINK_SENT, 0)
            therapist = repository.therapist_by_email_or_id(email, members_only=False)
            if therapist is None:
                return render(
                    request,
                    self.template_name,
                    {
                        "form": form,
                        "error": "Aucun profil thérapeute n'est associé à cette adresse email.",
                    },
                )
            login_url = None
            if now - last_sent >= cooldown:
                token = signing.dumps({"email": therapist.email}, salt=MAGIC_LINK_SALT)
                url = request.build_absolute_uri(
                    reverse("account_verify", kwargs={"token": token})
                )
                local_host = request.get_host().split(":", 1)[0] in {
                    "localhost",
                    "127.0.0.1",
                }
                if (
                    (settings.DEBUG or local_host)
                    and settings.EMAIL_BACKEND.endswith("console.EmailBackend")
                ):
                    login_url = url
                try:
                    send_mail(
                        "Votre lien de connexion Naturapeute",
                        "Bonjour,\n\n"
                        "Utilisez ce lien pour accéder à votre profil Naturapeute :\n"
                        f"{url}\n\n"
                        "Ce lien expire dans 15 minutes. Si vous ne l'avez pas demandé, "
                        "vous pouvez ignorer cet email.",
                        settings.DEFAULT_FROM_EMAIL,
                        [therapist.email],
                        fail_silently=False,
                    )
                except Exception:
                    logger.exception("Could not send an account login link")
                    return render(
                        request,
                        self.template_name,
                        {
                            "form": form,
                            "error": "Le lien de connexion n'a pas pu être envoyé. Réessayez plus tard.",
                        },
                    )
                else:
                    request.session[SESSION_LAST_LINK_SENT] = now
            return render(
                request,
                self.template_name,
                {"form": AccountEmailForm(), "sent": True, "login_url": login_url},
            )
        return render(request, self.template_name, {"form": form})


class AccountVerifyView(View):
    def get(self, request, token):
        try:
            payload = signing.loads(
                token,
                salt=MAGIC_LINK_SALT,
                max_age=getattr(settings, "ACCOUNT_MAGIC_LINK_MAX_AGE", 900),
            )
            email = payload["email"]
        except (signing.BadSignature, KeyError, TypeError):
            return render(request, "account/link_invalid.html", status=400)

        repository, unavailable = _repository_or_unavailable(request)
        if unavailable:
            return unavailable
        therapist = repository.therapist_by_email_or_id(email, members_only=False)
        if therapist is None:
            return render(request, "account/link_invalid.html", status=400)

        request.session.cycle_key()
        request.session[SESSION_THERAPIST_ID] = _therapist_session_id(therapist)
        return redirect("account_profile")


class AccountProfileView(View):
    template_name = "account/profile.html"

    def _profile_context(self, repository, therapist, form, saved=False):
        profile_url = None
        if therapist.slug0 and therapist.slug1:
            profile_url = reverse(
                "therapist",
                kwargs={"slug0": therapist.slug0, "slug1": therapist.slug1},
            )
        return {
            "therapist": therapist,
            "form": form,
            "saved": saved,
            "profile_url": profile_url,
        }

    def get(self, request):
        repository, unavailable = _repository_or_unavailable(request)
        if unavailable:
            return unavailable
        therapist = _session_therapist(request, repository)
        if therapist is None:
            return redirect("account")
        choices = repository.therapist_profile_choices(therapist)
        form = TherapistProfileForm(
            therapist=therapist,
            agreement_choices=choices["agreements"],
            payment_type_choices=choices["payment_types"],
            primary_practice_choices=choices["primary_practices"],
            practice_choices=choices["practices"],
        )
        return render(
            request,
            self.template_name,
            self._profile_context(repository, therapist, form, request.GET.get("saved") == "1"),
        )

    def post(self, request):
        repository, unavailable = _repository_or_unavailable(request)
        if unavailable:
            return unavailable
        therapist = _session_therapist(request, repository)
        if therapist is None:
            return redirect("account")
        choices = repository.therapist_profile_choices(therapist)
        form = TherapistProfileForm(
            request.POST,
            request.FILES,
            therapist=therapist,
            agreement_choices=choices["agreements"],
            payment_type_choices=choices["payment_types"],
            primary_practice_choices=choices["primary_practices"],
            practice_choices=choices["practices"],
        )
        if form.is_valid():
            existing = repository.therapist_by_email_or_id(
                form.cleaned_data["email"], members_only=False
            )
            if existing and existing._record_id != therapist._record_id:
                form.add_error(
                    "email",
                    "Cette adresse email est déjà associée à un autre profil.",
                )
            else:
                repository.update_therapist_profile(
                    therapist,
                    _profile_fields(therapist, form.cleaned_data),
                    photo=form.cleaned_data.get("photo"),
                )
                return redirect(f"{reverse('account_profile')}?saved=1")
        return render(request, self.template_name, self._profile_context(repository, therapist, form))


class AccountLogoutView(View):
    def post(self, request):
        request.session.pop(SESSION_THERAPIST_ID, None)
        request.session.pop(SESSION_LAST_LINK_SENT, None)
        return redirect("account")
