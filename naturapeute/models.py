from django.db import models
from django.contrib.postgres.fields import HStoreField, JSONField
from django.contrib.postgres.search import SearchVector
from django.utils.text import slugify
from django_better_admin_arrayfield.models.fields import ArrayField

from core.utils import normalize_text, unique, crypt


class Practice(models.Model):
    name = models.CharField(max_length=50, unique=True, blank=False)
    slug = models.SlugField(max_length=50, unique=True, blank=False)

    def __str__(self):
        return str(self.name)

    class Meta:
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
        ordering = ["name"]


class Office(models.Model):
    therapist = models.ForeignKey(
        "Therapist", related_name="offices", on_delete=models.CASCADE, null=False
    )
    street = models.CharField(max_length=100, null=True)
    zipcode = models.CharField(max_length=5, null=True)
    city = models.CharField(max_length=50, null=True)
    country = models.CharField(max_length=2, default="ch")
    latlng = ArrayField(models.DecimalField(decimal_places=2, max_digits=10), size=2)

    def __str__(self):
        return f"{str(self.therapist)} in {str(self.city)}"


class OfficePicture(models.Model):
    def upload_to(self, *args, **kwargs):
        return f"offices/{self.uuid}"

    office = models.ForeignKey(Office, related_name="pictures", on_delete=models.CASCADE)
    file = models.ImageField(upload_to=upload_to)
    uuid = models.CharField(default=unique, max_length=12)

    def __str__(self):
        return self.file.url


MEMBERSHIPS = (
    ("invitee", "Invité"),
    ("member", "Membre"),
    ("premium", "Payant"),
)

GENDERS = (
    ("man", "Homme"),
    ("woman", "Femme"),
)


class TherapistMembersManager(models.Manager):
    def get_queryset(self):
        return super().get_queryset().filter(membership="member")


class TherapistInviteesManager(models.Manager):
    def get_queryset(self):
        return super().get_queryset().filter(membership="invitee")


class Therapist(models.Model):
    def upload_to(self, *args, **kwargs):
        return f"therapists/{self.uuid}"

    slug = models.SlugField(max_length=100, unique=True)
    firstname = models.CharField(max_length=100, null=True, blank=True)
    lastname = models.CharField(max_length=100)
    gender = models.CharField(max_length=6, default="woman", choices=GENDERS)
    email = models.EmailField(null=True, blank=True)
    phone = models.CharField(max_length=15, null=True, blank=True)
    is_certified = models.BooleanField(default=False)
    description = models.TextField(null=True, blank=True)
    price = models.TextField(null=True, blank=True)
    timetable = models.TextField(null=True, blank=True)
    languages = ArrayField(models.CharField(max_length=2), null=True, blank=True)
    photo = models.ImageField(max_length=255, null=True, blank=True)
    socials = ArrayField(models.TextField(), null=True, blank=True)
    practices = models.ManyToManyField(Practice, related_name="therapists")
    agreements = ArrayField(models.CharField(max_length=50), null=True, blank=True)
    payment_types = ArrayField(models.CharField(max_length=20), null=True, blank=True)
    symptoms = models.ManyToManyField(Symptom, related_name="therapists", null=True, blank=True)
    creation_date = models.DateTimeField(auto_now_add=True)
    modification_date = models.DateTimeField(auto_now=True)
    membership = models.CharField(max_length=20, choices=MEMBERSHIPS)

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
        return self.slug.split("/")[0]

    @property
    def slug1(self):
        return self.slug.split("/")[1]

    @property
    def name(self):
        return f"{self.firstname} {self.lastname}"

    @property
    def languages_verbose(self):
        trans = {
            "en": "anglais",
            "fr": "français",
            "de": "allemand",
            "ru": "russe",
            "it": "italien",
            "es": "espagnol",
        }
        if self.languages:
            return [trans[l] for l in self.languages]

    def save(self, *args, **kwargs):
        if not self.slug:
            self.slug = slugify(f"{self.practices.first().name}-{self.offices.first().city}") + "/" + slugify(f"{self.name}")
        return super().save(*args, **kwargs)


# const TherapistPendingSchema = new mongoose.Schema({
#   slug: { type: String, unique: true },
#   name: String,
#   email: String,
#   phone: String,
#   isCertified: Boolean,
#   description: String,
#   price: String,
#   timetable: String,
#   languages: [String],
#   photo: String,
#   socials: [Object],
#   therapies: [String],
#   agreements: [String],
#   paymentTypes: [String],
#   // symptoms: [{ type: mongoose.ObjectId, ref: Symptom }],
#   offices: [Office],
#   creationDate: { type: Date, default: Date.now },
#   expirationDate: Date,
#   confirmed: Boolean,
# })

# TherapistPendingSchema.virtual('photoUrl').get(function() {
#   if(this.photo.startsWith('http')) return this.photo
#   return `/uploads/therapists/holistia/${this.slug}.jpg`
# })
