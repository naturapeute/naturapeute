"""
Import data from the legacy MongoDB application into PostgreSQL.

The importer expects the legacy collections used by the old Naturapeute
application: therapies, symptoms, synonyms, therapists, therapistpendings,
therapistdatas, and articles.
"""
import os
from datetime import date, datetime, timezone as datetime_timezone

from django.utils import timezone
from django.utils.text import slugify
from pymongo import MongoClient

from blog.models import Article, ArticleTag
from naturapeute.models import (
    Office,
    OfficePicture,
    Patient,
    Practice,
    Symptom,
    Synonym,
    Therapist,
)


MONGO_URI = os.environ.get("MONGO_URI", "mongodb://localhost:27017/terrapeute")
MONGO_DATABASE = os.environ.get("MONGO_DATABASE", "terrapeute")

client = MongoClient(MONGO_URI, serverSelectionTimeoutMS=5000)
db = client[MONGO_DATABASE]

airtable_registry = {}
id_registry = {}


def _as_list(value):
    if value is None:
        return []
    if isinstance(value, (list, tuple)):
        return list(value)
    return [value]


def _phone(value):
    if not value:
        return None
    return str(value).replace(" ", "")


def _socials(values):
    result = []
    for value in _as_list(values):
        if isinstance(value, dict):
            result.append(repr(value))
        elif value:
            result.append(str(value))
    return result


def _resolve_practices(values):
    practices = []
    seen = set()
    for value in _as_list(values):
        practice = id_registry.get(str(value))
        if not isinstance(practice, Practice):
            practice = airtable_registry.get(str(value))
        if not isinstance(practice, Practice) and isinstance(value, str):
            practice = Practice.objects.filter(name=value).first()
            if not practice:
                practice = Practice.objects.filter(slug=slugify(value)).first()
        if isinstance(practice, Practice) and practice.pk not in seen:
            practices.append(practice)
            seen.add(practice.pk)
    return practices


def _resolve_symptoms(values):
    symptoms = []
    seen = set()
    for value in _as_list(values):
        symptom = id_registry.get(str(value))
        if not isinstance(symptom, Symptom):
            symptom = airtable_registry.get(str(value))
        if isinstance(symptom, Symptom) and symptom.pk not in seen:
            symptoms.append(symptom)
            seen.add(symptom.pk)
    return symptoms


def _coordinates(source):
    location = source.get("location") or {}
    coordinates = location.get("coordinates") if isinstance(location, dict) else None
    if not coordinates:
        coordinates = source.get("latlng")
    if not isinstance(coordinates, (list, tuple)) or len(coordinates) != 2:
        return None
    return coordinates


def _import_offices(therapist, sources):
    therapist.offices.all().delete()
    for source in _as_list(sources):
        coordinates = _coordinates(source)
        if not coordinates:
            print(f"Skipping office without coordinates for {therapist}")
            continue

        office = Office.objects.create(
            street=source.get("street"),
            zipcode=source.get("zipCode") or source.get("zipcode"),
            city=source.get("city"),
            country=source.get("country") or "ch",
            latlng=coordinates,
            therapist=therapist,
        )

        for picture in _as_list(source.get("pictures")):
            if isinstance(picture, dict):
                picture = picture.get("url") or picture.get("path") or picture.get("filename")
            if picture:
                OfficePicture.objects.create(office=office, file=str(picture))


def _find_therapist(source):
    source_slug = source.get("slug")
    if source_slug:
        therapist = Therapist.mixed.filter(slug=source_slug).first()
        if therapist:
            return therapist

    email = source.get("email")
    if email:
        return Therapist.mixed.filter(
            email=email,
            firstname=source.get("firstname"),
            lastname=source.get("lastname"),
        ).first()
    return None


def _save_therapist(source, membership):
    practices = _resolve_practices(source.get("therapies"))
    if not practices:
        print(f"Skipping therapist without a known practice: {source.get('name') or source.get('lastname')}")
        return None

    firstname = source.get("firstname")
    lastname = source.get("lastname")
    if membership == "invitee" and (not firstname or not lastname):
        name = str(source.get("name") or "").strip().split()
        firstname = firstname or (name[0] if name else None)
        lastname = lastname or " ".join(name[1:])

    fields = {
        "slug": source.get("slug"),
        "firstname": firstname,
        "lastname": lastname or "",
        "email": source.get("email"),
        "phone": _phone(source.get("phone")),
        "is_certified": bool(source.get("isCertified")),
        "description": source.get("description"),
        "price": source.get("price"),
        "timetable": source.get("timetable"),
        "languages": _as_list(source.get("languages")),
        "photo": source.get("photo"),
        "socials": _socials(source.get("socials")),
        "agreements": _as_list(source.get("agreements")),
        "payment_types": _as_list(source.get("paymentTypes")),
        "membership": membership,
        "practice": practices[0],
    }

    therapist = _find_therapist(source)
    if therapist:
        for field, value in fields.items():
            setattr(therapist, field, value)
    else:
        therapist = Therapist(**fields)
    therapist.save()

    creation_date = _creation_date(source.get("creationDate"))
    if creation_date is not None:
        therapist.creation_date = creation_date

    therapist.practices.set(practices)
    therapist.symptoms.set(_resolve_symptoms(source.get("symptoms")))
    _import_offices(therapist, source.get("offices"))
    therapist.save()
    return therapist


def import_practices():
    count = 0
    for therapy in db["therapies"].find():
        name = str(therapy.get("name") or "").strip()
        if not name:
            continue
        slug = str(therapy.get("slug") or slugify(name))
        practice, _ = Practice.objects.get_or_create(name=name, defaults={"slug": slug})
        if practice.slug != slug and not Practice.objects.filter(slug=slug).exclude(pk=practice.pk).exists():
            practice.slug = slug
            practice.save(update_fields=["slug"])

        if therapy.get("airtableId"):
            airtable_registry[str(therapy["airtableId"])] = practice
        if therapy.get("_id") is not None:
            id_registry[str(therapy["_id"])] = practice
        count += 1
    print(f"{count} practices imported")


def import_synonyms():
    count = 0
    for source in db["synonyms"].find():
        name = str(source.get("name") or "").strip()
        if not name:
            continue
        words = " ".join(str(word) for word in _as_list(source.get("words")) if word)
        Synonym.objects.update_or_create(name=name, defaults={"words": words})
        count += 1
    print(f"{count} synonyms imported")


def import_symptoms():
    count = 0
    for source in db["symptoms"].find():
        name = str(source.get("name") or "").strip()
        if not name:
            continue

        synonyms = _as_list(source.get("synonyms"))
        if len(synonyms) == 1 and isinstance(synonyms[0], str):
            synonyms = synonyms[0].split()

        instance, _ = Symptom.objects.update_or_create(
            name=name,
            defaults={
                "synonyms": [str(value).strip() for value in synonyms if value],
                "keywords": source.get("keywords") or "",
            },
        )
        if source.get("_id") is not None:
            id_registry[str(source["_id"])] = instance
        if source.get("airtableId"):
            airtable_registry[str(source["airtableId"])] = instance
        count += 1

    for source in db["symptoms"].find({"airtableParentId": {"$exists": True}}):
        instance = airtable_registry.get(str(source.get("airtableId")))
        parent = airtable_registry.get(str(source.get("airtableParentId")))
        if isinstance(instance, Symptom) and isinstance(parent, Symptom):
            instance.parent = parent
            instance.save(update_fields=["parent"])
    print(f"{count} symptoms imported")


def import_therapists():
    count = 0
    for source in db["therapists"].find():
        if _save_therapist(source, "member"):
            count += 1
    print(f"{count} therapists imported")


def import_therapists_pending():
    count = 0
    for source in db["therapistpendings"].find():
        if _save_therapist(source, "invitee"):
            count += 1
    print(f"{count} pending therapists imported")


def _creation_date(value):
    if isinstance(value, datetime) and timezone.is_naive(value):
        return timezone.make_aware(value, datetime_timezone.utc)
    return value


def _birthdate(value):
    if value is None:
        return None
    if isinstance(value, date):
        return value
    try:
        return date.fromtimestamp(float(value) / 1000)
    except (TypeError, ValueError, OSError, OverflowError):
        return None


def import_patients():
    Patient.objects.all().delete()
    count = 0
    for extra in db["therapistdatas"].find():
        source_therapist = db["therapists"].find_one(
            {"airtableId": extra.get("therapistAirtableId")}
        )
        if not source_therapist:
            continue

        therapist = Therapist.mixed.filter(
            lastname=source_therapist.get("lastname"),
            firstname=source_therapist.get("firstname"),
        ).first()
        if not therapist:
            continue

        data = extra.get("data") or {}
        author = data.get("author") or {}
        therapist_data = data.get("therapist") or {}
        therapist.invoice_data = {
            "hourly_price": data.get("servicePrice", 0),
            "services": data.get("preferredServices", []),
            "author": {
                "name": author.get("name", ""),
                "email": author.get("email", ""),
                "phone": author.get("phone", ""),
                "zipcode": author.get("ZIP", ""),
                "city": author.get("city", ""),
                "street": author.get("street", ""),
                "rcc": author.get("RCC", ""),
                "iban": author.get("IBAN", ""),
            },
            "therapist": {
                "firstname": therapist_data.get("firstName", ""),
                "lastname": therapist_data.get("lastName", ""),
                "street": therapist_data.get("street", ""),
                "zipcode": therapist_data.get("ZIP", ""),
                "city": therapist_data.get("city", ""),
                "phone": therapist_data.get("phone", ""),
                "rcc": therapist_data.get("RCC", ""),
            },
        }
        therapist.save()

        for source in _as_list(data.get("patients")):
            lastname = str(source.get("lastName") or "").strip()
            if not lastname:
                continue
            try:
                zipcode = int(source["ZIP"])
            except (KeyError, TypeError, ValueError):
                zipcode = None

            patient = Patient.objects.create(
                firstname=source.get("firstName"),
                lastname=lastname,
                street=source.get("street"),
                zipcode=zipcode,
                city=source.get("city"),
                canton=source.get("canton"),
                gender="man" if source.get("gender") == "male" else "woman",
                birthdate=_birthdate(source.get("birthday")),
                email=source.get("email"),
            )
            therapist.patients.add(patient)
            count += 1
    print(f"{count} patients imported")


def import_articles():
    count = 0
    for source in db["articles"].find():
        title = str(source.get("title") or "").strip()
        if not title:
            continue
        slug = str(source.get("slug") or slugify(title))
        article, _ = Article.objects.update_or_create(
            slug=slug,
            defaults={
                "title": title,
                "body": source.get("body") or "",
                "image": source.get("image"),
            },
        )
        creation_date = _creation_date(source.get("creationDate"))
        if creation_date is not None:
            article.creation_date = creation_date
        article.save()

        tags = []
        for source_tag in _as_list(source.get("tags")):
            if isinstance(source_tag, dict):
                source_tag = source_tag.get("name")
            tag_name = str(source_tag or "").strip()
            tag_slug = slugify(tag_name)
            if not tag_slug:
                continue
            tag, _ = ArticleTag.objects.get_or_create(
                slug=tag_slug,
                defaults={"name": tag_name},
            )
            tags.append(tag)
        article.tags.set(tags)
        count += 1
    print(f"{count} articles imported")


def import_all():
    client.admin.command("ping")
    collections = set(db.list_collection_names())
    supported = {
        "therapies",
        "symptoms",
        "synonyms",
        "therapists",
        "therapistpendings",
        "therapistdatas",
        "articles",
    }
    available = collections & supported
    if not available:
        raise RuntimeError(
            f"Mongo database '{MONGO_DATABASE}' has no supported Naturapeute collections"
        )

    id_registry.clear()
    airtable_registry.clear()

    if "therapies" in collections:
        import_practices()
    if "synonyms" in collections:
        import_synonyms()
    if "symptoms" in collections:
        import_symptoms()
    if "therapists" in collections:
        import_therapists()
    if "therapistpendings" in collections:
        import_therapists_pending()
    if "therapistdatas" in collections and "therapists" in collections:
        import_patients()
    if "articles" in collections:
        import_articles()

    print(f"Imported Mongo collections: {', '.join(sorted(available))}")
