from django.db import models
from django.utils.text import slugify
from django.contrib.postgres.fields import HStoreField, JSONField
from django.contrib.postgres.search import SearchVector
from django_better_admin_arrayfield.models.fields import ArrayField


BLACKLIST_WORDS = ['alors', 'aucun', 'aussi', 'autre', 'avant', 'avec', 'avoir', 'bas', 'haut', 'bon', 'car', 'cela', 'ces', 'ceux', 'chaque', 'comme', 'comment', 'dans', 'des', 'dedans', 'dehors', 'depuis', 'devrait', 'doit', 'donc', 'debut', 'elle', 'elles', 'encore', 'essai', 'est', 'fait', 'faites', 'fois', 'font', 'hors', 'ici', 'ils', 'juste', 'les', 'leur', 'maintenant', 'mais', 'mes', 'mien', 'moins', 'mon', 'mot', 'meme', 'ni', 'notre', 'nous', 'par', 'parce', 'pas', 'peut', 'peu', 'plupart', 'pour', 'pourquoi', 'quand', 'que', 'quel', 'qui', 'sans', 'ses', 'seulement', 'sien', 'son', 'sont', 'sous', 'soyez', 'sujet', 'sur', 'tandis', 'tellement', 'tels', 'tes', 'ton', 'tous', 'tout', 'trop', 'tres', 'voient', 'vont', 'votre', 'vous', 'etaient', 'etat', 'etions', 'ete', 'les', 'des', 'aux', 'dans', 'pour', 'lie', 'liee',
"accident", "baisse", "bobo", "brulure", "chronique", "chute", "crise", "diminution", "douleur", "douloureuse", "douloureux", "dysfonctionnement", "etat", "fievre", "hypersensibilite", "infection", "lesion", "mal", "maladie", "malaise", "manque", "organe", "perte", "probleme", "reaction", "rouge", "rythme", "sensation", "syndrome", "trouble", "trou", "dessus", "dessous", "fais"]


class Practice(models.Model):
    name = models.CharField(max_length=50, unique=True, blank=False)
    slug = models.SlugField(max_length=50, unique=True, blank=False)

    def __str__(self):
        return str(self.name)


class SymptomManager(models.Manager):

    def search(self, terms):
        cleaned = []
        for t in terms.split(" "):
            t = slugify(t.strip())
            if not t in BLACKLIST_WORDS:
                cleaned.append(t)

        return Symptom.objects.annotate(
            search=SearchVector("name", "keywords", config="french"),
        ).filter(search=' '.join(cleaned))


class Symptom(models.Model):
    name = models.CharField(max_length=100, unique=True)
    parent = models.ForeignKey("self", null=True, blank=True, on_delete=models.SET_NULL)
    synonyms = ArrayField(models.CharField(max_length=50))
    keywords = models.TextField()

    objects = SymptomManager()

    def __str__(self):
        return str(self.name)


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
