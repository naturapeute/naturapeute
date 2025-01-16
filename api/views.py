"""Views for the API application."""

import json
from datetime import date

from django.core.serializers.json import DjangoJSONEncoder
from django.http import JsonResponse
from django.utils.decorators import method_decorator
from django.views.decorators.csrf import csrf_exempt
from django.views.generic import View

from naturapeute.models import Patient, Therapist


class LazyEncoder(DjangoJSONEncoder):
    """Custom JSON encoder for lazy-loaded Django objects."""
    def default(self, obj):
        """Convert object to JSON serializable format."""
        if hasattr(obj, 'to_json'):
            return obj.to_json()
        return super().default(obj)


@method_decorator(csrf_exempt, name='dispatch')
class TherapistView(View):
    """View for handling Therapist-related requests."""
    model = Therapist

    def get(self, *args, **kwargs):
        """Get therapist details by email."""
        therapist = Therapist.members.get(email=kwargs["email_or_pk"])
        office = therapist.offices.first()
        data = {
            "id": therapist.pk,
            "email": therapist.email,
            "firstname": therapist.firstname,
            "lastname": therapist.lastname,
            "phone": therapist.phone,
            "offices": [{
                "street": office.street,
                "city": office.city,
                "country": office.country,
                "zipcode": office.zipcode,
            }],
            "patients": [p.to_json() for p in therapist.patients.all()],
            "invoice_data": therapist.invoice_data,
        }
        return JsonResponse(data)

    def patch(self, *args, **kwargs):
        """Update therapist and associated patients."""
        therapist = Therapist.members.get(pk=kwargs["email_or_pk"])
        data = json.loads(self.request.body)
        therapist.invoice_data = data
        therapist.save()
        for p in data["patients"]:
            p["birthdate"] = date.fromtimestamp(p["birthdate"] / 1000)
            if "id" in p:
                Patient.objects.filter(pk=p["id"]).update(**p)
            else:
                patient = Patient.objects.create(**p)
                therapist.patients.add(patient)
        return JsonResponse(therapist.invoice_data)


class PatientView(View):
    """View for handling Patient-related requests."""
    def post(self, request, *args, **kwargs):
        """Create a new patient associated with a therapist."""
        therapist_id = kwargs.get('therapist_id')
        therapist = Therapist.members.get(pk=therapist_id)
        return JsonResponse(
            Patient.objects.create(
                therapist=therapist,
                **json.loads(request.body)
            ).to_json()
        )
