from django.contrib import admin

from .models import Therapist, Symptom, Practice, Office


@admin.register(Therapist)
class TherapistAdmin(admin.ModelAdmin):
    pass


@admin.register(Office)
class OfficeAdmin(admin.ModelAdmin):
    pass


@admin.register(Practice)
class PracticeAdmin(admin.ModelAdmin):
    pass


@admin.register(Symptom)
class SymptomAdmin(admin.ModelAdmin):
    pass
