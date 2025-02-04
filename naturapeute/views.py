"""Views for the naturapeute application."""
from django.views.generic import TemplateView, ListView, View
from django.views.generic.base import RedirectView, reverse
from django.shortcuts import redirect
from django.http import HttpResponse, Http404, HttpResponseRedirect
from django.db.models import Q

import vobject

from .models import Therapist, Symptom, Practice


class HomeView(TemplateView):
    """View for the home page."""

    template_name = "index.html"

    def get_context_data(self, **kwargs):
        """Get context data for the home page template.
        
        Returns:
            dict: Context containing therapists count, latest therapists and practices
        """
        context = super().get_context_data(**kwargs)
        therapists = Therapist.members.all()
        context["therapistsCount"] = therapists.count()
        context["therapists"] = therapists[:5]
        context["practices"] = Practice.objects.all()
        return context


class TherapistByPractice(ListView):
    """View for listing therapists filtered by practice."""
    template_name = "therapists.html"
    model = Therapist
    context_object_name = "therapists"
    queryset = Therapist.members.all()

    def get_queryset(self, *args, **kwargs):
        """Filter queryset by practice slug.
        
        Returns:
            QuerySet: Filtered therapists queryset
        """
        qs = super().get_queryset(*args, **kwargs)
        qs = qs.filter(practice__slug__in=self.kwargs.practice)


class TherapistsView(ListView):
    """View for listing all therapists with optional filtering."""
    template_name = "therapists.html"
    model = Therapist
    context_object_name = "therapists"
    queryset = Therapist.members.all()

    def get(self, request, *args, **kwargs):
        """Handle GET requests with practice name filtering.
        
        Returns:
            HttpResponse: Redirect to practice-specific view or default list view
        """
        practice_name = self.request.GET.get("practice")
        if practice_name:
            try:
                practice = Practice.objects.get(name=practice_name)
            except Practice.DoesNotExist:
                pass
            else:
                return redirect("therapists_practice", practice.slug)
        return super().get(request, *args, **kwargs)

    def get_queryset(self, *args, **kwargs):
        """Filter queryset by practice and/or symptoms.
        
        Returns:
            QuerySet: Filtered therapists queryset
        """
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
    """View for displaying detailed therapist information."""
    template_name = "therapist.html"

    def get_context_data(self, **kwargs):
        """Get context data for the therapist detail template.
        
        Returns:
            dict: Context containing therapist object
        """
        slug = f"{self.kwargs['slug0']}/{self.kwargs['slug1']}"
        try:
            therapist = Therapist.mixed.get(slug=slug)
        except Therapist.DoesNotExist as exc:
            raise Http404(f"Therapist not found with slug {slug}") from exc
        return {"therapist": therapist}

    def get(self, request, *args, **kwargs):
        """Handle GET requests with membership verification.
        
        Returns:
            HttpResponse: Redirect to therapists list for pending members,
                        or render detail template
        """
        therapist = self.get_context_data()["therapist"]
        if therapist.membership == "pending":
            return HttpResponseRedirect(reverse("therapists"))
        return super().get(request, *args, **kwargs)


class TherapistVcardView(View):
    """View for generating vCard downloads for therapists."""
    def get(self, *args, **kwargs):
        """Generate and return vCard response for therapist.
        
        Returns:
            HttpResponse: vCard file download response
        """
        card = vobject.vCard()
        therapist = Therapist.mixed.get(
            slug=f"{self.kwargs['slug0']}/{self.kwargs['slug1']}"
        )
        office = therapist.offices.first()
        card.add("n")
        card.n.value = vobject.vcard.Name(
            family=therapist.lastname, given=therapist.firstname
        )
        card.add("email")
        card.email.value = therapist.email
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
    """Legacy view for handling old therapist URLs."""
    def get_redirect_url(self, *args, **kwargs):
        """Return URL for redirecting old therapist URLs to new format."""
        return f"/therapists/{kwargs['slug0']}/{kwargs['slug1']}/"
