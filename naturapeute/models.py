import json
import time

from django.db import models
from django.contrib.postgres.search import SearchVector
from django.utils.text import slugify
from django_better_admin_arrayfield.models.fields import ArrayField
from django.db.models.signals import post_save
from django.dispatch import receiver

from core.utils import normalize_text, unique, crypt


invoice_data = {
    "hourly_price": 0,
    "services": [],
    "author": {
        "name": "",
        "email": "",
        "phone": "",
        "street": "",
        "zipcode": "",
        "city": "",
        "rcc": "",
        "iban": "",
    },
    "therapist": {
        "firstname": "",
        "lastname": "",
        "email": "",
        "phone": "",
        "street": "",
        "zipcode": "",
        "city": "",
        "rcc": "",
    },
}


class Practice(models.Model):
    name = models.CharField(max_length=50, unique=True, blank=False)
    slug = models.SlugField(max_length=50, unique=True, blank=False)

    def __str__(self):
        return str(self.name)

    class Meta:
        """Meta options for Practice model."""
        ordering = ["slug"]


class SymptomManager(models.Manager):

    def search(self, terms):
        terms = normalize_text(terms).split(' ')
        replaced = []
        for t in terms:
            synonym = Synonym.objects.annotate(
                search=SearchVector("name", "words", config="french"),
            ).filter(search=t)
            replaced.append(synonym.first().name if synonym.first() else t)
        return Symptom.objects.annotate(
            search=SearchVector("name", "keywords", config="french"),
        ).filter(search=' '.join(replaced))


class Symptom(models.Model):
    name = models.CharField(max_length=100, unique=True)
    parent = models.ForeignKey("self", null=True, blank=True, on_delete=models.SET_NULL)
    synonyms = ArrayField(models.CharField(max_length=50))
    keywords = models.TextField()

    objects = SymptomManager()

    def __str__(self):
        return str(self.name)

    class Meta:
        """Meta options for Symptom model."""
        ordering = ["name"]


class SynonymManager(models.Manager):

    def replace(self, term):
        synonym = Synonym.objects.annotate(
            search=SearchVector("name", "words", config="french"),
        ).filter(search=term)
        return synonym.first().name if synonym.first() else term


class Synonym(models.Model):
    name = models.CharField(max_length=50, unique=True)
    words = models.TextField()

    objects = SynonymManager()

    def __str__(self):
        return self.name

    class Meta:
        """Meta options for Synonym model."""
        ordering = ["name"]


class Office(models.Model):
    therapist = models.ForeignKey(
        "Therapist", related_name="offices", on_delete=models.CASCADE, null=False
    )
    street = models.CharField(max_length=100, null=True)
    zipcode = models.CharField(max_length=5, null=True)
    city = models.CharField(max_length=50, null=True)
    country = models.CharField(max_length=2, default="ch")
    latlng = ArrayField(models.DecimalField(decimal_places=15, max_digits=17), size=2)

    def __str__(self):
        return f"{str(self.therapist)} in {str(self.city)}"

    @property
    def coordinates(self):
        if not len(self.latlng) == 2:
            return
        return [float(ll) for ll in self.latlng]


class OfficePicture(models.Model):
    """Represents pictures associated with a therapist's office."""
    def upload_to(self, *args, **kwargs):
        return f"offices/{self.uuid}"

    office = models.ForeignKey(Office, related_name="pictures", on_delete=models.CASCADE)
    file = models.ImageField(upload_to=upload_to)
    uuid = models.CharField(default=unique, max_length=12)

    def __str__(self):
        return self.file.url


MEMBERSHIPS = (
    ("pending", "En attente / suspendu"),
    ("invitee", "Invité"),
    ("member", "Membre"),
    ("premium", "Payant"),
)

GENDERS = (
    ("man", "Homme"),
    ("woman", "Femme"),
)

LANGUAGES = (
    ("en", "anglais"),
    ("fr", "français"),
    ("de", "allemand"),
    ("ru", "russe"),
    ("it", "italien"),
    ("es", "espagnol"),
    ("nl", "néerlandais"),
    ("pl", "polonais"),
    ("pt", "portugais"),
    ("ro", "roumain"),
    ("hu", "hongrois"),
)


class TherapistMembersManager(models.Manager):
    """Custom manager that filters therapists with 'member' status."""
    def get_queryset(self):
        return super().get_queryset().filter(membership="member")


class TherapistInviteesManager(models.Manager):
    """Custom manager that filters therapists with 'invitee' status."""
    def get_queryset(self):
        """
        Return queryset filtered for invitee therapists.
        
        Returns:
            QuerySet: Filtered queryset containing only invitee therapists
        """
        return super().get_queryset().filter(membership="invitee")


class Therapist(models.Model):
    """
    Represents a therapist in the system.
    
    This model stores comprehensive information about therapists including their
    personal details, professional information, office locations, and credentials.
    """
    def upload_to(self, *args, **kwargs):
        """
        Determine the upload path for therapist photos.
        
        Returns:
            str: Path where the photo should be stored
        """
        return f"therapists/{slugify(self.slug)}"

    slug = models.SlugField(max_length=100, unique=True, null=True)
    firstname = models.CharField(max_length=100, null=True, blank=True)
    lastname = models.CharField(max_length=100)
    gender = models.CharField(max_length=6, default="woman", choices=GENDERS)
    email = models.EmailField(null=True, blank=True)
    phone = models.CharField(max_length=15, null=True, blank=True)
    is_certified = models.BooleanField(default=False)
    description = models.TextField(null=True, blank=True)
    price = models.TextField(null=True, blank=True)
    timetable = models.TextField(null=True, blank=True)
    languages = ArrayField(models.CharField(max_length=2, choices=LANGUAGES), null=True, blank=True)
    photo = models.ImageField(upload_to=upload_to, max_length=255, null=True, blank=True)
    socials = ArrayField(models.TextField(), null=True, blank=True)
    practice = models.ForeignKey(
        Practice,
        verbose_name="Pratique principale",
        related_name="experts",
        on_delete=models.RESTRICT
    )
    practices = models.ManyToManyField(
        Practice,
        verbose_name="Autres pratiques",
        related_name="therapists",
        blank=True
    )
    agreements = ArrayField(models.CharField(max_length=50), null=True, blank=True)
    payment_types = ArrayField(models.CharField(max_length=20), null=True, blank=True)
    symptoms = models.ManyToManyField(Symptom, related_name="therapists", blank=True)
    membership = models.CharField(max_length=20, choices=MEMBERSHIPS)
    patients = models.ManyToManyField(
        "Patient",
        through="TherapistPatient",
        related_name="therapists"
    )
    invoice_data = models.JSONField(default=invoice_data, null=True, blank=True)
    services = ArrayField(
        models.IntegerField(),
        null=True,
        blank=True
    )
    creation_date = models.DateTimeField(auto_now_add=True)
    modification_date = models.DateTimeField(auto_now=True)

    # Not called "objects" to prevent from mistakenly using it and
    # displaying all therapists.
    mixed = models.Manager()
    members = TherapistMembersManager()
    invitees = TherapistInviteesManager()
    class Meta:
        ordering = ["-creation_date"]

    def __str__(self):
        return self.name

    @property
    def slug0(self):
        """Get the first part of the slug."""
        return self.slug.split("/")[0]

    @property
    def slug1(self):
        """Get the second part of the slug."""
        return self.slug.split("/")[1]

    @property
    def name(self):
        """Get the full name of the therapist."""
        if self.firstname:
            return f"{self.firstname} {self.lastname}"
        else:
            return self.lastname

    @property
    def office(self):
        """Get the primary office of the therapist."""
        return self.offices.first()

    @property
    def city(self):
        if self.office:
            return self.office.city

    def get_social(self, name):
        """
        Get the URL for a specific social media profile.
        
        Args:
            name (str): Name of the social media platform
            
        Returns:
            str: URL of the social media profile if found, None otherwise
        """
        if not self.socials:
            return
        matches = [eval(s) for s in self.socials if eval(s)["name"] == name]
        if matches:
            return matches[0]["url"]

    @property
    def website(self):
        """Get the therapist's website URL."""
        return self.get_social("website")

    @property
    def facebook(self):
        """Get the therapist's Facebook profile URL."""
        return self.get_social("facebook")

    @property
    def photo_url(self):
        """
        Get the URL for the therapist's photo.
        
        Returns a default avatar if no photo is set.
        """
        url = self.photo
        if not self.photo.name and self.gender:
            return f"/static/img/avatar-{self.gender}.png"
        if url and not str(url).startswith("http"):
            url = self.photo.url
        return url

    @property
    def languages_verbose(self):
        """Get list of languages in verbose form."""
        if not self.languages:
            return []
        languages = dict(LANGUAGES)
        return [languages[l] for l in self.languages if l in languages]


@receiver(post_save, sender=Therapist)
def therapist_create_slug(sender, instance, **kwargs):
    """
    Signal handler to automatically create slugs for therapist instances.
    
    Creates a slug combining practice name, city (if available), and therapist name.
    """
    post_save.disconnect(therapist_create_slug, sender=sender)
    part1 = instance.practice.slug
    if instance.offices.count():
        part1 += "-" + slugify(instance.offices.first().city)
    part2 = slugify(instance.name)
    instance.slug = f"{part1}/{part2}"
    instance.save()
    post_save.connect(therapist_create_slug, sender=sender)


class Patient(models.Model):
    """
    Represents a patient in the system.
    
    This model stores patient information including personal details
    and contact information.
    """
    firstname = models.CharField(max_length=100, null=True, blank=True)
    lastname = models.CharField(max_length=100)
    gender = models.CharField(max_length=6, choices=GENDERS, null=True, blank=True)
    birthdate = models.DateField(null=True, blank=True)
    email = models.EmailField(null=True, blank=True)
    phone = models.CharField(max_length=12, null=True, blank=True)
    mobile = models.CharField(max_length=12, null=True, blank=True)
    street = models.CharField(max_length=100, null=True, blank=True)
    street2 = models.CharField(max_length=100, null=True, blank=True)
    canton = models.CharField(max_length=2, null=True, blank=True)
    zipcode = models.IntegerField(null=True, blank=True)
    city = models.CharField(max_length=50, null=True, blank=True)

    def __str__(self):
        """Get string representation of the patient."""
        if(self.firstname):
            return f"{self.firstname} {self.lastname}"
        return self.lastname

    def to_json(self):
        """
        Convert patient data to JSON format.
        
        Returns:
            dict: Patient data in dictionary format
        """
        data = self.__dict__
        del data["_state"]
        data["birthdate"] = time.mktime(self.birthdate.timetuple()) * 1000
        return data


class TherapistPatient(models.Model):
    """
    Represents the relationship between therapists and their patients.
    
    This is a through model for the many-to-many relationship between
    Therapist and Patient models.
    """
    therapist = models.ForeignKey(Therapist, on_delete=models.CASCADE)
    patient = models.ForeignKey(Patient, on_delete=models.CASCADE)
    creation_date = models.DateTimeField(auto_now_add=True)
