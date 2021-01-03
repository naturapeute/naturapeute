from graphene_django import DjangoObjectType
import graphene

from naturapeute.models import Patient, Therapist


class TherapistNode(DjangoObjectType):
    class Meta:
        model = Therapist


class PatientNode(DjangoObjectType):
    therapists = graphene.List(TherapistNode)
    class Meta:
        model = Patient

    @graphene.resolve_only_args
    def resolve_therapists(self):
        return self.therapists.all()


class Query(graphene.ObjectType):
    patients = graphene.List(PatientNode, therapist=graphene.Int())
    patient = graphene.Field(PatientNode, id=graphene.Int())
    therapists = graphene.List(TherapistNode)
    therapist = graphene.Field(TherapistNode, email=graphene.String())

    def resolve_patients(self, info, therapist):
        if therapist:
            patients = Patient.objects.filter(therapists__in=[therapist])
        else:
            patients = Patient.objects.all()
        return patients

    def resolve_patient(self, info, id):
        return Patient.objects.get(pk=id)

    def resolve_therapists(self, info):
        return Therapist.members.all()

    def resolve_therapist(self, info, email):
        return Therapist.members.get(email=email)

schema = graphene.Schema(query=Query)
