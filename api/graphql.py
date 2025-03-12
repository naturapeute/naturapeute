"""GraphQL API schema and types for the naturapeute application."""

from graphene_django import DjangoObjectType
import graphene

from naturapeute.models import Patient, Therapist


class TherapistNode(DjangoObjectType):
    """GraphQL Node representing a Therapist."""
    class Meta:
        """Meta configuration for TherapistNode."""
        model = Therapist


class PatientNode(DjangoObjectType):
    """GraphQL Node representing a Patient."""
    therapists = graphene.List(TherapistNode)

    class Meta:
        """Meta configuration for PatientNode."""
        model = Patient

    @graphene.resolve_only_args
    def resolve_therapists(self):
        """Resolve the therapists field for a patient."""
        return self.therapists.all()


class Query(graphene.ObjectType):
    """Root Query object for the GraphQL API."""
    patients = graphene.List(PatientNode, therapist=graphene.Int())
    patient = graphene.Field(PatientNode, patient_id=graphene.Int())
    therapists = graphene.List(TherapistNode)
    therapist = graphene.Field(TherapistNode, email=graphene.String())

    def resolve_patients(self, _info, therapist):
        """Resolve patients, optionally filtered by therapist ID."""
        if therapist:
            patients = Patient.objects.filter(therapists__in=[therapist])
        else:
            patients = Patient.objects.all()
        return patients

    def resolve_patient(self, _info, patient_id):
        """Resolve a single patient by ID."""
        return Patient.objects.get(pk=patient_id)

    def resolve_therapists(self, _info):
        """Resolve all therapist members."""
        return Therapist.members.all()

    def resolve_therapist(self, _info, email):
        """Resolve a single therapist by email."""
        return Therapist.members.get(email=email)


schema = graphene.Schema(query=Query)
