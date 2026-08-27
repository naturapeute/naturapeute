from django.db.models import Q
from django.http import Http404, HttpResponse, HttpResponseRedirect
from django.shortcuts import redirect, reverse
from django.views.generic import ListView, TemplateView, View
from django.views.generic.base import RedirectView

import vobject

from core.teable_repository import TeableCollection, get_teable_repository, teable_enabled

from .models import Practice, Symptom, Therapist


def teable_repository():
    return get_teable_repository() if teable_enabled() else None


class HomeView(TemplateView):
    template_name = "index.html"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        repository = teable_repository()
        if repository:
            therapists = repository.therapists()
            context["therapistsCount"] = therapists.count()
            context["therapists"] = therapists[:5]
            context["practices"] = repository.practices()
            return context

        therapists = Therapist.members.all()
        context["therapistsCount"] = therapists.count()
        context["therapists"] = therapists[:5]
        context["practices"] = Practice.objects.all()
        return context


class TherapistByPractice(ListView):
    template_name = "therapists.html"
    model = Therapist
    context_object_name = "therapists"
    queryset = Therapist.members.all()

    def get_queryset(self, *args, **kwargs):
        qs = super().get_queryset(*args, **kwargs)
        return qs.filter(practice__slug__in=self.kwargs["practice"])


class TherapistsView(ListView):
    template_name = "therapists.html"
    model = Therapist
    context_object_name = "therapists"
    queryset = Therapist.members.all()

    def get(self, request, *args, **kwargs):
        practice_name = self.request.GET.get("practice")
        if practice_name:
            repository = teable_repository()
            if repository:
                practice = repository.practice_by_name(practice_name)
                if practice:
                    return redirect("therapists_practice", practice.slug)
            else:
                try:
                    practice = Practice.objects.get(name=practice_name)
                except Practice.DoesNotExist:
                    pass
                else:
                    return redirect("therapists_practice", practice.slug)
        return super().get(request, *args, **kwargs)

    def get_queryset(self, *args, **kwargs):
        repository = teable_repository()
        if repository:
            therapists = repository.therapists()
            practice_slug = self.kwargs.get("practice_slug")
            if practice_slug:
                practice = repository.practice_by_slug(practice_slug)
                if not practice:
                    raise Http404(f"Practice not found with slug {practice_slug}")
                therapists = TeableCollection(
                    therapist
                    for therapist in therapists
                    if any(item.slug == practice_slug for item in therapist.practices.all())
                )

            symptom_name = self.request.GET.get("symptom")
            if symptom_name:
                symptom_ids = {symptom.pk for symptom in repository.search_symptoms(symptom_name)}
                therapists = TeableCollection(
                    therapist
                    for therapist in therapists
                    if any(symptom.pk in symptom_ids for symptom in therapist.symptoms.all())
                )
            return therapists

        qs = super().get_queryset(*args, **kwargs)
        params = self.request.GET
        symptom_name = params.get("symptom")
        practice_slug = self.kwargs.get("practice_slug")
        if practice_slug:
            practice = Practice.objects.get(slug=practice_slug)
            qs = qs.filter(Q(practices__in=[practice]) | Q(practice=practice)).distinct()
        if symptom_name:
            symptoms = Symptom.objects.search(symptom_name)
            qs = qs.filter(symptoms__in=symptoms).distinct()
        return qs


class TherapistView(TemplateView):
    template_name = "therapist.html"

    def get_context_data(self, **kwargs):
        slug = f"{self.kwargs['slug0']}/{self.kwargs['slug1']}"
        repository = teable_repository()
        if repository:
            therapist = repository.therapist_by_slug(slug)
            if not therapist:
                raise Http404(f"Therapist not found with slug {slug}")
            return {"therapist": therapist}

        try:
            therapist = Therapist.mixed.get(slug=slug)
        except Therapist.DoesNotExist:
            raise Http404(f"Therapist not found with slug {slug}")
        return {"therapist": therapist}

    def get(self, request, *args, **kwargs):
        therapist = self.get_context_data()["therapist"]
        if therapist.membership == "pending":
            return HttpResponseRedirect(reverse("therapists"))
        return super().get(request, *args, **kwargs)


class TherapistVcardView(View):
    def get(self, *args, **kwargs):
        slug = f"{self.kwargs['slug0']}/{self.kwargs['slug1']}"
        repository = teable_repository()
        if repository:
            therapist = repository.therapist_by_slug(slug)
            if not therapist:
                raise Http404(f"Therapist not found with slug {slug}")
        else:
            try:
                therapist = Therapist.mixed.get(slug=slug)
            except Therapist.DoesNotExist:
                raise Http404(f"Therapist not found with slug {slug}")

        office = therapist.offices.first()
        card = vobject.vCard()
        card.add("n")
        card.n.value = vobject.vcard.Name(
            family=therapist.lastname, given=therapist.firstname
        )
        card.add("email")
        card.email.value = therapist.email
        if office:
            card.add("adr")
            card.adr.value = vobject.vcard.Address(
                street=office.street,
                city=office.city,
                code=office.zipcode,
                country=office.country,
            )
        response = HttpResponse(str(card), content_type="text/vcard")
        response["Content-Disposition"] = f'attachment; filename="{therapist}.vcf"'
        return response


class TherapistOldView(RedirectView):
    def get_redirect_url(self, *args, **kwargs):
        return f"/therapeutes/{kwargs['slug0']}/{kwargs['slug1']}/"
