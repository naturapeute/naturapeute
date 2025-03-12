"""Admin configuration for naturapeute application."""
from django.contrib import admin
from django.utils.html import format_html
from django_better_admin_arrayfield.admin.mixins import DynamicArrayMixin

from .models import (
    Office, OfficePicture, Patient, Practice,
    Symptom, Synonym, Therapist
)


class OfficePictureInline(admin.TabularInline):
    """Admin inline for OfficePicture model."""
    model = OfficePicture
    exclude = ["uuid"]


@admin.register(Office)
class OfficeAdmin(admin.ModelAdmin):
    """Admin configuration for Office model."""
    inlines = [OfficePictureInline]
    search_fields = ["therapist__firstname", "therapist__lastname", "city"]


class OfficeInline(admin.StackedInline):
    """Admin inline for Office model."""
    model = Office
    readonly_fields = ["country"]
    extra = 1


@admin.register(Therapist)
class TherapistAdmin(admin.ModelAdmin, DynamicArrayMixin):
    """Admin configuration for Therapist model."""
    list_display = ["__str__", "image_tag", "agreements", "slug"]
    list_filter = ["is_certified", "membership"]
    search_fields = ["firstname", "lastname", "slug"]
    exclude = ["slug", "services", "invoice_data"]
    inlines = [OfficeInline]

    def image_tag(self, obj):
        """Generate HTML for displaying therapist photo in admin."""
        return format_html(
            f'<img src="{obj.photo_url}" style="width: 45px; height:45px;" />'
        )
    image_tag.short_description = 'Photo'


@admin.register(Practice)
class PracticeAdmin(admin.ModelAdmin, DynamicArrayMixin):
    """Admin configuration for Practice model."""


@admin.register(Symptom)
class SymptomAdmin(admin.ModelAdmin, DynamicArrayMixin):
    """Admin configuration for Symptom model."""
    list_display = ["parent", "__str__"]
    list_display_links = ["__str__"]
    search_fields = ["name", "keywords"]


@admin.register(Synonym)
class SynonymAdmin(admin.ModelAdmin, DynamicArrayMixin):
    """Admin configuration for Synonym model."""
    list_display = ["__str__", "words"]


@admin.register(Patient)
class PatientAdmin(admin.ModelAdmin, DynamicArrayMixin):
    """Admin configuration for Patient model."""