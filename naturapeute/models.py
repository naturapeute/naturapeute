from django.db import models
from django.contrib.postgres.fields import HStoreField, JSONField
from django.contrib.postgres.search import SearchVector
from django_better_admin_arrayfield.models.fields import ArrayField

from .utils import normalize_text

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
    pictures = ArrayField(models.ImageField())
    latlng = ArrayField(models.DecimalField(decimal_places=2, max_digits=10), size=2)

    def __str__(self):
        return f"{str(self.therapist)} in {str(self.city)}"


MEMBERSHIPS = (
    ("invitee", "Invité"),
    ("member", "Membre"),
    ("premium", "Payant"),
)


class TherapistMembersManager(models.Manager):
    def get_queryset(self):
        return super().get_queryset().filter(membership="member")


class TherapistInviteesManager(models.Manager):
    def get_queryset(self):
        return super().get_queryset().filter(membership="invitee")


class Therapist(models.Model):
    slug = models.SlugField(max_length=100, unique=True)
    firstname = models.CharField(max_length=100, null=True)
    lastname = models.CharField(max_length=100, null=True)
    email = models.EmailField(null=True)
    phone = models.CharField(max_length=15, null=True)
    is_certified = models.BooleanField(default=True)
    description = models.TextField(null=True)
    price = models.TextField(null=True)
    timetable = models.TextField(null=True)
    languages = ArrayField(models.CharField(max_length=2), null=True)
    photo = models.ImageField(max_length=255, null=True)
    socials = ArrayField(models.TextField())
    practices = models.ManyToManyField(Practice, related_name="therapists")
    agreements = ArrayField(models.CharField(max_length=50), null=True)
    payment_types = ArrayField(models.CharField(max_length=20), null=True)
    symptoms = models.ManyToManyField(Symptom, related_name="therapists")
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
        return [trans[l] for l in self.languages]


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
