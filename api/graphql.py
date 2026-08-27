import graphene
from graphene.types.generic import GenericScalar

from core.teable_repository import get_teable_repository, teable_enabled
from naturapeute.models import Patient as DjangoPatient
from naturapeute.models import Therapist as DjangoTherapist


class PracticeNode(graphene.ObjectType):
    id = graphene.Int()
    name = graphene.String()
    slug = graphene.String()


class SymptomNode(graphene.ObjectType):
    id = graphene.Int()
    name = graphene.String()
    synonyms = graphene.List(graphene.String)
    keywords = graphene.String()


class OfficeNode(graphene.ObjectType):
    id = graphene.Int()
    street = graphene.String()
    zipcode = graphene.String()
    city = graphene.String()
    country = graphene.String()
    coordinates = graphene.List(graphene.Float)

    def resolve_coordinates(self, info):
        return self.coordinates


class PatientNode(graphene.ObjectType):
    id = graphene.Int()
    firstname = graphene.String()
    lastname = graphene.String()
    gender = graphene.String()
    birthdate = graphene.Date()
    email = graphene.String()
    phone = graphene.String()
    mobile = graphene.String()
    street = graphene.String()
    street2 = graphene.String()
    canton = graphene.String()
    zipcode = graphene.Int()
    city = graphene.String()
    therapists = graphene.List(lambda: TherapistNode)

    def resolve_therapists(self, info):
        if teable_enabled():
            return self.therapists.all()
        return self.therapists.all()


class TherapistNode(graphene.ObjectType):
    id = graphene.Int()
    firstname = graphene.String()
    lastname = graphene.String()
    gender = graphene.String()
    email = graphene.String()
    phone = graphene.String()
    is_certified = graphene.Boolean()
    description = graphene.String()
    price = graphene.String()
    timetable = graphene.String()
    languages = graphene.List(graphene.String)
    agreements = graphene.List(graphene.String)
    payment_types = graphene.List(graphene.String)
    membership = graphene.String()
    slug = graphene.String()
    calendly_url = graphene.String()
    invoice_data = GenericScalar()
    services = graphene.List(GenericScalar)
    practice = graphene.Field(PracticeNode)
    practices = graphene.List(PracticeNode)
    symptoms = graphene.List(SymptomNode)
    offices = graphene.List(OfficeNode)
    patients = graphene.List(PatientNode)

    def resolve_practices(self, info):
        return self.practices.all()

    def resolve_symptoms(self, info):
        return self.symptoms.all()

    def resolve_offices(self, info):
        return self.offices.all()

    def resolve_patients(self, info):
        return self.patients.all()


class Query(graphene.ObjectType):
    patients = graphene.List(PatientNode, therapist=graphene.Int())
    patient = graphene.Field(PatientNode, id=graphene.Int())
    therapists = graphene.List(TherapistNode)
    therapist = graphene.Field(TherapistNode, email=graphene.String())

    def resolve_patients(self, info, therapist=None):
        if teable_enabled():
            patients = get_teable_repository().patients()
            if therapist is not None:
                patients = [patient for patient in patients if therapist in patient.therapist_source_ids]
            return patients
        if therapist:
            return DjangoPatient.objects.filter(therapists__in=[therapist])
        return DjangoPatient.objects.all()

    def resolve_patient(self, info, id=None):
        if teable_enabled():
            return next(
                (patient for patient in get_teable_repository().patients() if patient.pk == id),
                None,
            )
        try:
            return DjangoPatient.objects.get(pk=id)
        except DjangoPatient.DoesNotExist:
            return None

    def resolve_therapists(self, info):
        if teable_enabled():
            return get_teable_repository().therapists()
        return DjangoTherapist.members.all()

    def resolve_therapist(self, info, email=None):
        if teable_enabled():
            return get_teable_repository().therapist_by_email_or_id(email)
        try:
            return DjangoTherapist.members.get(email=email)
        except DjangoTherapist.DoesNotExist:
            return None


schema = graphene.Schema(query=Query)
