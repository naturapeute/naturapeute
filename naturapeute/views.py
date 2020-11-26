from django.views.generic import TemplateView, ListView, View
from django.views.generic.base import RedirectView
from django.shortcuts import redirect, reverse
from django.http import HttpResponse
import vobject

from .models import Therapist, Symptom, Practice


class HomeView(TemplateView):

    template_name = "index.html"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        therapists = Therapist.members.all()
        context["therapistsCount"] = therapists.count()
        context["therapists"] = therapists[:5]
        context["practices"] = Practice.objects.all()
        return context


class TherapistsView(ListView):
    template_name = "therapists.html"
    model = Therapist
    context_object_name = "therapists"
    queryset = Therapist.members

    def get_queryset(self, *args, **kwargs):
        qs = super().get_queryset(*args, **kwargs)
        params = self.request.GET
        symptom_name = params.get("symptom")
        if symptom_name:
            symptoms = Symptom.objects.search(symptom_name)
            qs = qs.filter(symptoms__in=symptoms).distinct()
        practice_name = params.get("practice")
        if practice_name:
            practice = Practice.objects.get(name=practice_name)
            if practice:
                qs = qs.filter(practices=practice).distinct()
        return qs


class TherapistView(TemplateView):
    template_name = "therapist.html"

    def get_context_data(self, **kwargs):
        slug = f"{self.kwargs['slug0']}/{self.kwargs['slug1']}"
        return {"therapist": Therapist.objects.get(slug=slug)}


class TherapistVcardView(View):
    def get(self, *args, **kwargs):
        card = vobject.vCard()
        therapist = Therapist.objects.get(
            slug=f"{self.kwargs['slug0']}/{self.kwargs['slug1']}"
        )
        office = therapist.offices.first()
        card.add("n")
        card.n.value = vobject.vcard.Name(family=therapist.lastname, given=therapist.firstname)
        card.add("email")
        card.email.value = therapist.email
        card.add("adr")
        card.adr.value = vobject.vcard.Address(street=office.street, city=office.city, code=office.zipcode, country=office.country)
        response = HttpResponse(str(card), content_type="text/vcard")
        response["Content-Disposition"] = f'attachment; filename="{therapist}.vcf"'
        return response
        raise Error("WIP Implementing fields and returning response")


class TherapistOldView(RedirectView):
    def get_redirect_url(self, *args, **kwargs):
        return f"/therapeutes/{kwargs['slug0']}/{kwargs['slug1']}/"
