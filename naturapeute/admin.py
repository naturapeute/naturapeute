from django.contrib import admin
from django_better_admin_arrayfield.admin.mixins import DynamicArrayMixin
from django.utils.html import format_html

from .models import Therapist, Symptom, Practice, Office, Synonym, models


@admin.register(Therapist)
class TherapistAdmin(admin.ModelAdmin, DynamicArrayMixin):
    list_display = ["__str__", "image_tag", "agreements", "slug"]
    list_filter = ["is_certified"]
    search_fields = ["firstname", "lastname", "slug"]

    def image_tag(self, obj):
        return format_html(f'<img src="{obj.photo}" style="width: 45px; height:45px;" />')
    image_tag.short_description = 'Photo'

    formfield_overrides = {
        models.ManyToManyField: {'widget': models.fields.forms.widgets.CheckboxSelectMultiple }
    }

@admin.register(Office)
class OfficeAdmin(admin.ModelAdmin, DynamicArrayMixin):
    pass


@admin.register(Practice)
class PracticeAdmin(admin.ModelAdmin, DynamicArrayMixin):
    pass


@admin.register(Symptom)
class SymptomAdmin(admin.ModelAdmin, DynamicArrayMixin):
    list_display = ["parent", "__str__"]
    list_display_links = ["__str__"]
    search_fields = ["name", "keywords"]


@admin.register(Synonym)
class SynonymAdmin(admin.ModelAdmin, DynamicArrayMixin):
    list_display = ["__str__", "words"]
