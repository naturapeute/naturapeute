import json
from datetime import date

from django.core.serializers.json import DjangoJSONEncoder
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.views.generic import View
from django.utils.decorators import method_decorator

from core.teable_repository import get_teable_repository, teable_enabled

from naturapeute.models import Patient, Therapist


class LazyEncoder(DjangoJSONEncoder):
    pass


def therapist_payload(therapist):
    offices = [
        {
            "street": office.street,
            "city": office.city,
            "country": office.country,
            "zipcode": office.zipcode,
        }
        for office in therapist.offices.all()
    ]
    return {
        "id": therapist.pk,
        "email": therapist.email,
        "firstname": therapist.firstname,
        "lastname": therapist.lastname,
        "phone": therapist.phone,
        "offices": offices,
        "patients": [patient.to_json() for patient in therapist.patients.all()],
        "invoice_data": therapist.invoice_data,
    }


@method_decorator(csrf_exempt, name="dispatch")
class TherapistView(View):
    model = Therapist

    def get(self, *args, **kwargs):
        value = kwargs["email_or_pk"]
        if teable_enabled():
            therapist = get_teable_repository().therapist_by_email_or_id(value)
            if not therapist:
                return JsonResponse({"detail": "Therapist not found"}, status=404)
            return JsonResponse(therapist_payload(therapist))

        try:
            therapist = Therapist.members.get(email=value)
        except Therapist.DoesNotExist:
            return JsonResponse({"detail": "Therapist not found"}, status=404)
        return JsonResponse(therapist_payload(therapist))

    def patch(self, *args, **kwargs):
        value = kwargs["email_or_pk"]
        data = json.loads(self.request.body or "{}")
        if teable_enabled():
            repository = get_teable_repository()
            therapist = repository.therapist_by_email_or_id(value)
            if not therapist:
                return JsonResponse({"detail": "Therapist not found"}, status=404)
            repository.update_therapist_data(therapist, data)
            return JsonResponse(data)

        try:
            therapist = Therapist.members.get(pk=value)
        except Therapist.DoesNotExist:
            return JsonResponse({"detail": "Therapist not found"}, status=404)
        therapist.invoice_data = data
        therapist.save()
        for patient_data in data.get("patients", []):
            if patient_data.get("birthdate") is not None:
                patient_data["birthdate"] = date.fromtimestamp(patient_data["birthdate"] / 1000)
            patient_id = patient_data.get("id")
            if patient_id:
                Patient.objects.filter(pk=patient_id).update(**patient_data)
            else:
                patient = Patient.objects.create(**patient_data)
                therapist.patients.add(patient)
        return JsonResponse(therapist.invoice_data)


class PatientView(View):
    def post(self, *args, **kwargs):
        return JsonResponse({"detail": "Not implemented"}, status=501)
