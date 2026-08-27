from django import forms

from .models import GENDERS, LANGUAGES


class AccountEmailForm(forms.Form):
    email = forms.EmailField(
        label="Adresse email",
        widget=forms.EmailInput(
            attrs={"autocomplete": "email", "placeholder": "vous@exemple.ch"}
        ),
    )

    def clean_email(self):
        return self.cleaned_data["email"].strip().lower()


class TherapistProfileForm(forms.Form):
    display_name = forms.CharField(label="Nom affiché", max_length=200)
    firstname = forms.CharField(label="Prénom", max_length=100, required=False)
    lastname = forms.CharField(label="Nom", max_length=100)
    gender = forms.ChoiceField(label="Civilité", choices=GENDERS)
    email = forms.EmailField(label="Adresse email")
    phone = forms.CharField(label="Téléphone", max_length=50, required=False)
    website = forms.URLField(label="Site internet", required=False)
    facebook = forms.URLField(label="Facebook", required=False)
    calendly_url = forms.URLField(label="Lien Calendly", required=False)
    primary_practice = forms.ChoiceField(
        label="Pratique principale", required=False
    )
    practices = forms.MultipleChoiceField(
        label="Pratiques", required=False, widget=forms.CheckboxSelectMultiple
    )
    description = forms.CharField(
        label="Présentation", required=False, widget=forms.Textarea(attrs={"rows": 8})
    )
    price = forms.CharField(
        label="Tarifs", required=False, widget=forms.Textarea(attrs={"rows": 3})
    )
    timetable = forms.CharField(
        label="Horaires", required=False, widget=forms.Textarea(attrs={"rows": 3})
    )
    languages = forms.MultipleChoiceField(
        label="Langues parlées",
        choices=LANGUAGES,
        required=False,
        widget=forms.CheckboxSelectMultiple,
    )
    agreements = forms.MultipleChoiceField(
        label="Agréments",
        required=False,
        widget=forms.CheckboxSelectMultiple,
    )
    payment_types = forms.MultipleChoiceField(
        label="Moyens de paiement",
        required=False,
        widget=forms.CheckboxSelectMultiple,
    )
    photo = forms.ImageField(label="Photo", required=False)

    def __init__(
        self,
        *args,
        therapist,
        agreement_choices,
        payment_type_choices,
        primary_practice_choices,
        practice_choices,
        **kwargs,
    ):
        super().__init__(*args, **kwargs)
        self.fields["agreements"].choices = [(choice, choice) for choice in agreement_choices]
        self.fields["payment_types"].choices = [
            (choice, choice) for choice in payment_type_choices
        ]
        self.fields["primary_practice"].choices = primary_practice_choices
        self.fields["practices"].choices = practice_choices
        self.initial.update(
            {
                "display_name": therapist.name,
                "firstname": therapist.firstname,
                "lastname": therapist.lastname,
                "gender": therapist.gender,
                "email": therapist.email,
                "phone": therapist.phone,
                "website": therapist.website,
                "facebook": therapist.facebook,
                "calendly_url": therapist.calendly_url,
                "primary_practice": str(therapist.practice_id or ""),
                "practices": [str(practice.pk) for practice in therapist.practices],
                "description": therapist.description,
                "price": therapist.price,
                "timetable": therapist.timetable,
                "languages": therapist.languages,
                "agreements": therapist.agreements,
                "payment_types": therapist.payment_types,
            }
        )

    def clean_email(self):
        return self.cleaned_data["email"].strip().lower()

    def clean_photo(self):
        photo = self.cleaned_data.get("photo")
        if photo and photo.size > 10 * 1024 * 1024:
            raise forms.ValidationError("La photo ne peut pas dépasser 10 Mo.")
        return photo
