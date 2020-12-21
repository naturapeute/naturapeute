import json
from datetime import date

from django.http.response import HttpResponse, JsonResponse
from django.views.generic import View
from django.http import JsonResponse
from django.core import serializers
from django.utils.decorators import method_decorator
from django.views.decorators.csrf import csrf_exempt

from naturapeute.models import Therapist, Patient
from django.core.serializers.json import DjangoJSONEncoder


class LazyEncoder(DjangoJSONEncoder):
    def default(self, obj):
        if isinstance(obj, YourCustomType):
            return str(obj)
        return super().default(obj)


@method_decorator(csrf_exempt, name='dispatch')
class TherapistView(View):
    model = Therapist

    def get(self, *args, **kwargs):
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
        therapist = Therapist.members.get(pk=kwargs["email_or_pk"])
        data = json.loads(self.request.body)
        therapist.invoice_data = data
        therapist.save()
        for p in data["patients"]:
            p["birthdate"] = date.fromtimestamp(p["birthdate"] / 1000)
            if "id" in p:
                patient = Patient.objects.filter(pk=p["id"]).update(**p)
            else:
                patient = Patient.objects.create(**p)
                therapist.patients.add(patient)
        return JsonResponse(therapist.invoice_data)


class PatientView(View):
    def post(self, *args, **kwargs):
        Patient.objects.create(therapist=therapist, **json.loads(self.request.body))


#   app.patch(`${prefix}/therapist/:id`, async (req, res) => {
#     const content = req.body.extraData
#     if(!content) return res.status(403, 'No data to patch')

#     const therapist = await Therapist.findById(req.params.id)
#     if(!therapist) return res.status(404).send('Therapist not found')
#     let data = await TherapistData.findOne({ therapistAirtableId: therapist.airtableId })
#     if(!data) data = new TherapistData({ therapistAirtableId: therapist.airtableId })
#     data.data = content
#     await data.save()
#     res.setHeader('Content-Type', 'application/json')
#     const inst = await therapist.asObject()
#     res.send(inst)
#   })
# }
