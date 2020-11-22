from django.views.generic import TemplateView, ListView, View
from django.shortcuts import redirect, reverse
from django.views.generic.base import RedirectView
import vobject

from .models import Therapist, Symptom


class HomeView(TemplateView):

    template_name = "index.html"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        therapists = Therapist.objects.all()
        context["therapistsCount"] = therapists.count()
        context["therapists"] = therapists[:5]
        return context


class TherapistsView(ListView):
    template_name = "therapists.html"
    model = Therapist
    context_object_name = "therapists"

    def get_queryset(self, *args, **kwargs):
        qs = super().get_queryset(*args, **kwargs)
        params = dict(self.request.GET)
        symptom = self.request.GET.get("symptom")
        if symptom:
            symptoms = Symptom.objects.search(symptom)
            qs = qs.filter(symptoms__in=symptoms).distinct()
        return qs




class TherapistView(TemplateView):
    template_name = "therapist.html"

    def get_context_data(self, **kwargs):
        slug = f"{self.kwargs['slug0']}/{self.kwargs['slug1']}"
        return {"therapist": Therapist.objects.get(slug=slug)}


class TherapistVcardView(View):
    def get(self, **kwargs):
        card = vobject.vCard()
        therapist = Therapist.objects.get(
            slug=f"{self.kwargs['slug0']}/{self.kwargs['slug1']}"
        )
        office = therapist.offices[0]
        card.add("n")
        card.n.value = vobject.vcard.Name(family="Harris", given="Jeffrey")
        card.add("email")
        card.email.value = therapist.email
        card.add("adr")
        card.ard.value = vobject.vcard.Address(street=office.street, city=office.city, code=office.zipcode, country=office.country)
        raise Error("WIP Implementing fields and returning response")


class TherapistOldView(RedirectView):
    def get_redirect_url(self, *args, **kwargs):
        return f"/therapeutes/{kwargs['slug0']}/{kwargs['slug1']}/"
