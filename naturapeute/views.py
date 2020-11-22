from django.views.generic import TemplateView, ListView, View

from naturapeute.models import Therapist


class HomeView(TemplateView):

    template_name = "index.html"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        therapists = Therapist.objects.all()
        context["therapistsCount"] = therapists.count()
        context["therapists"] = therapists[:5]
        return context


class TherapistView(TemplateView):
    template_name = "therapist.html"

    def get_context_data(self, **kwargs):
        slug = f"{self.kwargs['slug0']}/{self.kwargs['slug1']}"
        return {
            "therapist": Therapist.objects.get(slug=slug)
        }


class TherapistsView(ListView):
    template_name = "therapists.html"
    model = Therapist
    context_object_name = "therapists"
