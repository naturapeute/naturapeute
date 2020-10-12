from django.contrib import admin
from django_better_admin_arrayfield.admin.mixins import DynamicArrayMixin

from .models import Therapist, Symptom, Practice, Office


@admin.register(Therapist)
class TherapistAdmin(admin.ModelAdmin, DynamicArrayMixin):
    pass


@admin.register(Office)
class OfficeAdmin(admin.ModelAdmin, DynamicArrayMixin):
    pass


@admin.register(Practice)
class PracticeAdmin(admin.ModelAdmin, DynamicArrayMixin):
    pass


@admin.register(Symptom)
class SymptomAdmin(admin.ModelAdmin, DynamicArrayMixin):
    pass
