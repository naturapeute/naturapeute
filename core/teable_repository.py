import ast
import contextvars
import json
import tempfile
import threading
import time
from datetime import datetime, timezone as datetime_timezone
from pathlib import Path

from django.conf import settings
from django.core.signals import request_finished, request_started

from core.teable import TeableClient, TeableError
from core.teable_schema import normalize_agreements, normalize_language_codes
from core.utils import normalize_text


_request_context = contextvars.ContextVar("teable_request_context", default=None)


def _request_started(sender, **kwargs):
    _request_context.set(object())


def _request_finished(sender, **kwargs):
    _request_context.set(None)


request_started.connect(_request_started, dispatch_uid="teable_request_started")
request_finished.connect(_request_finished, dispatch_uid="teable_request_finished")


class TeableCollection(list):
    def all(self):
        return self

    def first(self):
        return self[0] if self else None

    def count(self, value=None):
        if value is None:
            return len(self)
        return super().count(value)

    def __getitem__(self, index):
        value = super().__getitem__(index)
        return TeableCollection(value) if isinstance(index, slice) else value


class TeablePractice:
    def __init__(self, source_id, name, slug):
        self.pk = source_id
        self.id = source_id
        self.name = name or ""
        self.slug = slug or ""

    def __str__(self):
        return self.name


class TeableSymptom:
    def __init__(self, source_id, fields, source_ids_by_record_id=None):
        self.pk = source_id
        self.id = source_id
        self.name = fields.get("Name") or ""
        self.parent_id = _linked_source_id(
            fields.get("Parent Source ID"), source_ids_by_record_id or {}
        )
        self.parent = None
        self.synonyms = _json(fields.get("Synonyms"), [])
        self.keywords = fields.get("Keywords") or ""

    def __str__(self):
        return self.name


class TeableTag:
    def __init__(self, source_id, name, slug):
        self.pk = source_id
        self.id = source_id
        self.name = name or ""
        self.slug = slug or ""

    def __str__(self):
        return self.name


class TeableOfficePicture:
    def __init__(self, source_id, file, url=None):
        self.pk = source_id
        self.id = source_id
        self.file = file or ""
        self.url = url or self.file

    def __str__(self):
        return self.url


class TeableOffice:
    def __init__(self, data, pictures=None):
        self.pk = _integer(data.get("source_id"))
        self.id = self.pk
        self.street = data.get("street")
        self.zipcode = data.get("zipcode")
        self.city = data.get("city")
        self.country = data.get("country") or "ch"
        self.latlng = data.get("coordinates") or []
        self.pictures = TeableCollection(pictures or [])

    @property
    def coordinates(self):
        if not isinstance(self.latlng, (list, tuple)) or len(self.latlng) != 2:
            return None
        return [float(value) for value in self.latlng]

    def __str__(self):
        return f"{self.city or ''}".strip()


class TeablePatient:
    def __init__(self, record, data=None):
        if data is None:
            fields = record.get("fields", {})
            self._record_id = record.get("id")
        else:
            fields = {
                "Source ID": data.get("source_id"),
                "Firstname": data.get("firstname"),
                "Lastname": data.get("lastname"),
                "Gender": data.get("gender"),
                "Birthdate": data.get("birthdate"),
                "Email": data.get("email"),
                "Phone": data.get("phone"),
                "Mobile": data.get("mobile"),
                "Street": data.get("street"),
                "Street 2": data.get("street2"),
                "Canton": data.get("canton"),
                "Zipcode": data.get("zipcode"),
                "City": data.get("city"),
                "Therapist Source IDs": data.get("therapist_source_ids"),
            }
            self._record_id = None
        self._fields = fields
        self.pk = _integer(fields.get("Source ID"))
        self.id = self.pk
        self.firstname = fields.get("Firstname")
        self.lastname = fields.get("Lastname") or ""
        self.gender = fields.get("Gender")
        self.birthdate = _date(fields.get("Birthdate"))
        self.email = fields.get("Email")
        self.phone = fields.get("Phone")
        self.mobile = fields.get("Mobile")
        self.street = fields.get("Street")
        self.street2 = fields.get("Street 2")
        self.canton = fields.get("Canton")
        self.zipcode = fields.get("Zipcode")
        self.city = fields.get("City")
        self.therapist_source_ids = _integer_list(fields.get("Therapist Source IDs"))
        self.therapists = TeableCollection()

    def __str__(self):
        if self.firstname:
            return f"{self.firstname} {self.lastname}"
        return self.lastname

    def to_json(self):
        birthdate = None
        if self.birthdate:
            birthdate = int(
                datetime.combine(self.birthdate, datetime.min.time(), tzinfo=datetime_timezone.utc).timestamp()
                * 1000
            )
        return {
            "id": self.pk,
            "firstname": self.firstname,
            "lastname": self.lastname,
            "gender": self.gender,
            "birthdate": birthdate,
            "email": self.email,
            "phone": self.phone,
            "mobile": self.mobile,
            "street": self.street,
            "street2": self.street2,
            "canton": self.canton,
            "zipcode": self.zipcode,
            "city": self.city,
        }


class TeableTherapist:
    def __init__(
        self,
        record,
        practice_map,
        symptom_map,
        patient_map,
        practice_record_sources=None,
        symptom_record_sources=None,
    ):
        fields = record.get("fields", {})
        self._record_id = record.get("id")
        self._fields = fields
        self.pk = _integer(fields.get("Source ID"))
        self.id = self.pk
        self.slug = fields.get("Slug") or ""
        self.display_name = fields.get("Name") or ""
        self.firstname = fields.get("Firstname")
        self.lastname = fields.get("Lastname") or ""
        self.gender = fields.get("Gender")
        self.email = fields.get("Email")
        self.phone = fields.get("Phone")
        self.is_certified = bool(fields.get("Certified"))
        self.description = fields.get("Description")
        self.price = fields.get("Price")
        self.timetable = fields.get("Timetable")
        self.languages = normalize_language_codes(_string_list(fields.get("Languages")))
        self.agreements = normalize_agreements(_string_list(fields.get("Agreements")))
        self.payment_types = _string_list(fields.get("Payment Types"))
        self.membership = fields.get("Membership") or "pending"
        self.invoice_data = _json(fields.get("Invoice Data"), {})
        self.services = _json(fields.get("Services"), [])
        self.calendly_url = fields.get("Calendly URL")
        self.creation_date = _date_time(fields.get("Creation Date"))
        self.modification_date = _date_time(fields.get("Modification Date"))

        practice_id = _linked_source_id(
            fields.get("Primary Practice Source ID"), practice_record_sources or {}
        )
        self.practice_id = practice_id
        practice_ids = _linked_source_ids(
            fields.get("Practice Source IDs"), practice_record_sources or {}
        )
        self.practice = practice_map.get(practice_id)
        self.practices = TeableCollection(
            practice_map[source_id]
            for source_id in practice_ids
            if source_id in practice_map
        )
        if self.practice and self.practice not in self.practices:
            self.practices.insert(0, self.practice)

        symptom_ids = _linked_source_ids(
            fields.get("Symptom Source IDs"), symptom_record_sources or {}
        )
        self.symptoms = TeableCollection(
            symptom_map[source_id]
            for source_id in symptom_ids
            if source_id in symptom_map
        )
        self.patients = TeableCollection(
            patient_map[source_id]
            for source_id in _integer_list(fields.get("Patient Source IDs"))
            if source_id in patient_map
        )

        office_picture_items = _attachments(fields.get("Office Pictures"))
        office_picture_by_name = {
            item.get("name", "").lower(): item
            for item in office_picture_items
            if isinstance(item, dict)
        }
        self.offices = TeableCollection()
        for office_data in _json(fields.get("Offices"), []):
            pictures = []
            for picture_index, picture_path in enumerate(office_data.get("pictures", []), start=1):
                picture = office_picture_by_name.get(str(picture_path).lower())
                if not picture and picture_path:
                    picture = office_picture_by_name.get(str(picture_path).rsplit("/", 1)[-1].lower())
                if not picture and picture_index <= len(office_picture_items):
                    picture = office_picture_items[picture_index - 1]
                pictures.append(
                    TeableOfficePicture(
                        picture_index,
                        picture_path,
                        _attachment_url([picture]) if isinstance(picture, dict) else None,
                    )
                )
            self.offices.append(TeableOffice(office_data, pictures))

        photo_items = _attachments(fields.get("Photo"))
        self.photo_url = _attachment_url(photo_items)
        if not self.photo_url:
            photo_source = fields.get("Photo Source")
            if isinstance(photo_source, str) and photo_source.startswith(("http://", "https://")):
                self.photo_url = photo_source
            elif self.gender:
                self.photo_url = f"/static/img/avatar-{self.gender}.png"
        self.socials = _parse_socials(_json(fields.get("Socials"), []))

    @property
    def name(self):
        if self.display_name:
            return self.display_name
        if self.firstname:
            return f"{self.firstname} {self.lastname}"
        return self.lastname

    @property
    def office(self):
        return self.offices.first()

    @property
    def city(self):
        office = self.office
        return office.city if office else None

    def get_social(self, name):
        for social in self.socials:
            if social.get("name") == name:
                return social.get("url")
        return None

    @property
    def website(self):
        return self.get_social("website")

    @property
    def facebook(self):
        return self.get_social("facebook")

    @property
    def slug0(self):
        return self.slug.split("/", 1)[0]

    @property
    def slug1(self):
        return self.slug.split("/", 1)[1] if "/" in self.slug else ""

    @property
    def languages_verbose(self):
        language_names = {
            "en": "anglais",
            "fr": "français",
            "de": "allemand",
            "ru": "russe",
            "it": "italien",
            "es": "espagnol",
            "nl": "néerlandais",
            "pl": "polonais",
            "pt": "portugais",
            "ro": "roumain",
            "hu": "hongrois",
        }
        return [language_names[language] for language in self.languages if language in language_names]

    def __str__(self):
        return self.name


class TeableArticle:
    def __init__(self, record, tag_map):
        fields = record.get("fields", {})
        self._record_id = record.get("id")
        self._fields = fields
        self.pk = _integer(fields.get("Source ID"))
        self.id = self.pk
        self.title = fields.get("Title") or ""
        self.slug = fields.get("Slug") or ""
        self.body = fields.get("Body") or ""
        tag_names = _string_list(fields.get("Tag Names"))
        tag_ids = _integer_list(fields.get("Tag Source IDs"))
        self.tags = TeableCollection()
        seen_tag_names = set()
        for source_id, name in zip(tag_ids, tag_names):
            tag_name = name.strip()
            tag_key = tag_name.casefold()
            if not tag_name or tag_key in seen_tag_names:
                continue
            seen_tag_names.add(tag_key)
            source_tag = tag_map.get(source_id)
            tag_slug = source_tag.slug if source_tag and source_tag.name == tag_name else ""
            self.tags.append(TeableTag(source_id, tag_name, tag_slug))
        if not self.tags and tag_names:
            for name in tag_names:
                tag_name = name.strip()
                tag_key = tag_name.casefold()
                if tag_name and tag_key not in seen_tag_names:
                    seen_tag_names.add(tag_key)
                    self.tags.append(TeableTag(None, tag_name, ""))
        self.creation_date = _date_time(fields.get("Creation Date"))
        self.update_date = _date_time(fields.get("Update Date"))
        self.image_url = _attachment_url(_attachments(fields.get("Image"))) or fields.get("Image Source")

    @property
    def summary(self):
        return self.body[:300]

    @property
    def reading_time(self):
        return max(1, round(len(self.body.split()) / 225))

    def __str__(self):
        return self.title


def _integer(value):
    try:
        return int(value) if value is not None else None
    except (TypeError, ValueError):
        return None


def _linked_source_id(value, source_ids_by_record_id):
    if isinstance(value, dict):
        record_id = value.get("id")
        return source_ids_by_record_id.get(record_id) or _integer(record_id)
    if isinstance(value, list):
        return _linked_source_id(value[0], source_ids_by_record_id) if value else None
    return _integer(value)


def _linked_source_ids(value, source_ids_by_record_id):
    if isinstance(value, str):
        value = _json(value, [])
    if isinstance(value, dict):
        value = [value]
    if not isinstance(value, (list, tuple)):
        return []
    result = []
    for item in value:
        source_id = _linked_source_id(item, source_ids_by_record_id)
        if source_id is not None and source_id not in result:
            result.append(source_id)
    return result


def _integer_list(value):
    value = _json(value, [])
    if not isinstance(value, list):
        return []
    return [parsed for parsed in (_integer(item) for item in value) if parsed is not None]


def _string_list(value):
    if isinstance(value, str):
        parsed = _json(value, None)
        value = parsed if isinstance(parsed, list) else [value]
    if not isinstance(value, (list, tuple)):
        return []

    result = []
    for item in value:
        if isinstance(item, (list, tuple)):
            result.extend(_string_list(item))
            continue
        if isinstance(item, dict):
            item = item.get("name")
        if not isinstance(item, str):
            continue
        parsed = _json(item, None)
        if isinstance(parsed, list):
            result.extend(_string_list(parsed))
        elif item:
            result.append(item)
    return result


def _json(value, default):
    if value is None or value == "":
        return default
    if isinstance(value, (list, dict)):
        return value
    try:
        return json.loads(value)
    except (TypeError, ValueError, json.JSONDecodeError):
        return default


def _iso_value(value):
    return value.isoformat() if value is not None else None


def _date(value):
    if not value:
        return None
    if hasattr(value, "year") and hasattr(value, "month") and hasattr(value, "day"):
        return value
    try:
        if isinstance(value, (int, float)):
            return datetime.fromtimestamp(value / 1000, tz=datetime_timezone.utc).date()
        return datetime.fromisoformat(str(value).replace("Z", "+00:00")).date()
    except (TypeError, ValueError, OSError, OverflowError):
        return None


def _date_time(value):
    if not value:
        return None
    if hasattr(value, "isoformat"):
        return value
    try:
        return datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    except (TypeError, ValueError):
        return None


def _attachments(value):
    if isinstance(value, list):
        return value
    if isinstance(value, dict):
        return [value]
    return []


def _attachment_url(items):
    for item in items:
        if isinstance(item, dict):
            for key in ("url", "lgThumbnailUrl", "presignedUrl", "smThumbnailUrl"):
                if item.get(key):
                    return item[key]
        if isinstance(item, str) and item:
            return item
    return None


def _parse_socials(value):
    result = []
    for item in value if isinstance(value, list) else []:
        if isinstance(item, dict):
            result.append(item)
            continue
        if not isinstance(item, str):
            continue
        try:
            parsed = ast.literal_eval(item)
        except (SyntaxError, ValueError):
            continue
        if isinstance(parsed, dict):
            result.append(parsed)
    return result


def teable_enabled():
    return bool(
        getattr(settings, "TEABLE_ENABLED", False)
        and getattr(settings, "TEABLE_BASE_ID", "")
        and getattr(settings, "TEABLE_API_TOKEN", "")
    )


class TeableRepository:
    cache_seconds = 60

    def __init__(self):
        self.client = TeableClient(
            base_url=settings.TEABLE_API_URL,
            base_id=settings.TEABLE_BASE_ID,
            token=settings.TEABLE_API_TOKEN,
        )
        self.cache_seconds = settings.TEABLE_CACHE_SECONDS
        self._loaded_at = 0
        self._request_key = None
        self._lock = threading.RLock()

    def _table_records(self, table_id):
        records = []
        skip = 0
        while True:
            page = self.client.list_records(table_id, take=1000, skip=skip)
            records.extend(page)
            if len(page) < 1000:
                return records
            skip += len(page)

    def refresh(self):
        with self._lock:
            table_list = self.client.list_tables()
            table_ids = {table["name"]: table["id"] for table in table_list}
            self._table_ids = table_ids
            required = {"Practices", "Symptoms", "Therapists", "Patients", "Articles"}
            missing = required - table_ids.keys()
            if missing:
                raise TeableError(f"Teable base is missing tables: {', '.join(sorted(missing))}")
            records = {
                name: self._table_records(table_id)
                for name, table_id in table_ids.items()
                if name in {
                    "Practices",
                    "Symptoms",
                    "Synonyms",
                    "Therapists",
                    "Offices",
                    "Office Pictures",
                    "Patients",
                    "Therapist Patients",
                    "Article Tags",
                    "Articles",
                }
            }

            practice_records = records.get("Practices", [])
            self._practice_record_ids = {}
            practice_map = {}
            for record in practice_records:
                fields = record.get("fields", {})
                data = _json(fields.get("Data"), None)
                if isinstance(data, list):
                    for item in data:
                        source_id = _integer(item.get("source_id"))
                        if source_id is not None:
                            practice_map[source_id] = TeablePractice(
                                source_id, item.get("name"), item.get("slug")
                            )
                else:
                    source_id = _integer(fields.get("Source ID"))
                    if source_id is not None:
                        practice_map[source_id] = TeablePractice(
                            source_id, fields.get("Name"), fields.get("Slug")
                        )
                        if record.get("id"):
                            self._practice_record_ids[source_id] = record["id"]
            self._practices_by_source_id = practice_map
            self._practice_record_sources = {
                record_id: source_id
                for source_id, record_id in self._practice_record_ids.items()
            }

            symptom_records = records.get("Symptoms", [])
            symptom_record_sources = {
                record["id"]: _integer(record.get("fields", {}).get("Source ID"))
                for record in symptom_records
                if record.get("id")
                and _integer(record.get("fields", {}).get("Source ID")) is not None
            }
            symptom_map = {}
            for record in symptom_records:
                fields = record.get("fields", {})
                data = _json(fields.get("Data"), None)
                if isinstance(data, list):
                    for item in data:
                        source_id = _integer(item.get("source_id"))
                        if source_id is not None:
                            symptom_map[source_id] = TeableSymptom(
                                source_id, item, symptom_record_sources
                            )
                else:
                    source_id = _integer(fields.get("Source ID"))
                    if source_id is not None:
                        symptom_map[source_id] = TeableSymptom(
                            source_id, fields, symptom_record_sources
                        )
            for symptom in symptom_map.values():
                symptom.parent = symptom_map.get(symptom.parent_id)

            patient_map = {}
            for record in records.get("Patients", []):
                fields = record.get("fields", {})
                data = _json(fields.get("Data"), None)
                values = data if isinstance(data, list) else [None]
                for item in values:
                    patient = TeablePatient(record, item) if isinstance(item, dict) else TeablePatient(record)
                    if patient.pk is not None:
                        patient_map[patient.pk] = patient
            tag_map = {}
            for record in records.get("Article Tags", []):
                fields = record.get("fields", {})
                data = _json(fields.get("Data"), None)
                values = data if isinstance(data, list) else [fields]
                for item in values:
                    source_id = _integer(item.get("source_id"))
                    if source_id is not None:
                        tag_map[source_id] = TeableTag(
                            source_id, item.get("name"), item.get("slug")
                        )

            self._practices = TeableCollection(practice_map.values())
            self._symptoms = TeableCollection(
                sorted(symptom_map.values(), key=lambda symptom: symptom.name.lower())
            )
            self._patients = TeableCollection(patient_map.values())
            all_therapists = [
                TeableTherapist(
                    record,
                    practice_map,
                    symptom_map,
                    patient_map,
                    self._practice_record_sources,
                    symptom_record_sources,
                )
                for record in records.get("Therapists", [])
                if _integer(record.get("fields", {}).get("Source ID")) is not None
                or record.get("fields", {}).get("Email")
            ]
            self._all_therapists = TeableCollection(all_therapists)
            self._therapists = TeableCollection(
                therapist for therapist in all_therapists if therapist.pk is not None
            )
            for therapist in self._all_therapists:
                for patient in therapist.patients:
                    patient.therapists.append(therapist)
            self._articles = TeableCollection(
                sorted(
                    (TeableArticle(record, tag_map) for record in records.get("Articles", [])),
                    key=lambda article: article.creation_date or datetime.min.replace(tzinfo=datetime_timezone.utc),
                    reverse=True,
                )
            )
            self._loaded_at = time.monotonic()

    def _ensure_loaded(self):
        request_key = _request_context.get()
        if self.cache_seconds <= 0 and request_key is not None:
            if self._request_key is not request_key:
                self.refresh()
                self._request_key = request_key
            return
        if time.monotonic() - self._loaded_at > self.cache_seconds:
            self.refresh()

    def practices(self):
        self._ensure_loaded()
        return self._practices

    def symptoms(self):
        self._ensure_loaded()
        return self._symptoms

    def search_symptoms(self, query):
        self._ensure_loaded()
        normalized_query = normalize_text(query).lower()
        terms = [term for term in normalized_query.split() if term]
        return TeableCollection(
            symptom
            for symptom in self._symptoms
            if all(
                term in " ".join(
                    [symptom.name, symptom.keywords, *[str(item) for item in symptom.synonyms]]
                ).lower()
                for term in terms
            )
        )

    def therapists(self, members_only=True):
        self._ensure_loaded()
        if not members_only:
            return self._therapists
        return TeableCollection(
            therapist for therapist in self._therapists if therapist.membership == "member"
        )

    def patients(self):
        self._ensure_loaded()
        return self._patients

    def articles(self):
        self._ensure_loaded()
        return self._articles

    def practice_by_name(self, name):
        return next((practice for practice in self.practices() if practice.name == name), None)

    def practice_by_slug(self, slug):
        return next((practice for practice in self.practices() if practice.slug == slug), None)

    def therapist_by_slug(self, slug):
        return next((therapist for therapist in self.therapists(False) if therapist.slug == slug), None)

    def therapist_by_email_or_id(self, value, members_only=True):
        therapists = self.therapists(members_only)
        if not members_only:
            therapists = self._all_therapists
        normalized_value = str(value).strip().casefold()
        for therapist in therapists:
            if (
                therapist.email
                and therapist.email.strip().casefold() == normalized_value
            ) or str(therapist.pk) == str(value) or therapist._record_id == str(value):
                return therapist
        return None

    def therapist_profile_choices(self, therapist):
        self._ensure_loaded()
        table_id = self._table_ids.get("Therapists")
        if not table_id:
            raise TeableError("The Teable Therapists table cannot be found")
        fields = {field["name"]: field for field in self.client.list_fields(table_id)}

        def choices(field_name, selected):
            configured = [
                choice.get("name")
                for choice in fields.get(field_name, {}).get("options", {}).get("choices", [])
                if choice.get("name")
            ]
            return list(dict.fromkeys([*configured, *(selected or [])]))

        primary_practices = [
            (str(source_id), practice_map.name)
            for source_id, practice_map in self._practices_by_source_id.items()
            if source_id in self._practice_record_ids
        ]
        all_practices = [
            (str(practice.pk), practice.name)
            for practice in sorted(self._practices, key=lambda item: item.name.casefold())
        ]
        return {
            "agreements": choices("Agreements", therapist.agreements),
            "payment_types": choices("Payment Types", therapist.payment_types),
            "primary_practices": primary_practices,
            "practices": all_practices,
        }

    def update_therapist_profile(self, therapist, fields, photo=None):
        self._ensure_loaded()
        table_id = self._table_ids.get("Therapists")
        if not table_id or not therapist._record_id:
            raise TeableError("The Teable therapist record cannot be updated")

        allowed_fields = {
            "Name",
            "Firstname",
            "Lastname",
            "Gender",
            "Email",
            "Phone",
            "Description",
            "Price",
            "Timetable",
            "Languages",
            "Agreements",
            "Payment Types",
            "Socials",
            "Calendly URL",
            "Primary Practice Source ID",
            "Practice Source IDs",
        }
        updates = {
            field_name: value
            for field_name, value in fields.items()
            if field_name in allowed_fields
        }
        if "Primary Practice Source ID" in updates:
            source_id = _integer(updates["Primary Practice Source ID"])
            record_id = self._practice_record_ids.get(source_id)
            updates["Primary Practice Source ID"] = {"id": record_id} if record_id else None
        if "Practice Source IDs" in updates:
            source_ids = _integer_list(updates["Practice Source IDs"])
            updates["Practice Source IDs"] = [
                {"id": self._practice_record_ids[source_id]}
                for source_id in source_ids
                if source_id in self._practice_record_ids
            ]
        if updates:
            self.client.update_record(table_id, therapist._record_id, updates)

        if photo:
            photo_field = next(
                (
                    field
                    for field in self.client.list_fields(table_id)
                    if field["name"] == "Photo"
                ),
                None,
            )
            if photo_field is None:
                raise TeableError("The Teable Therapists table is missing the Photo field")
            self.client.update_record(
                table_id,
                therapist._record_id,
                {"Photo": None, "Photo Source": None},
            )
            suffix = Path(photo.name).suffix or ".jpg"
            with tempfile.NamedTemporaryFile(suffix=suffix) as temporary:
                for chunk in photo.chunks():
                    temporary.write(chunk)
                temporary.flush()
                self.client.upload_attachment(
                    table_id,
                    therapist._record_id,
                    photo_field["id"],
                    file_path=temporary.name,
                    filename=Path(photo.name).name,
                )

        self._loaded_at = 0
        self._request_key = None

    def article_by_slug(self, slug):
        return next((article for article in self.articles() if article.slug == slug), None)

    def update_therapist_data(self, therapist, data):
        self._ensure_loaded()
        table_id = self._table_ids.get("Therapists")
        if not table_id or not therapist._record_id:
            raise TeableError("The Teable therapist record cannot be updated")
        self.client.update_record(
            table_id,
            therapist._record_id,
            {"Invoice Data": json.dumps(data, ensure_ascii=False, default=str)},
        )

        for patient_data in data.get("patients", []):
            patient_id = _integer(patient_data.get("id"))
            patient = next(
                (item for item in self._patients if item.pk == patient_id),
                None,
            )
            if not patient or not patient._record_id:
                continue
            fields = {
                "Firstname": patient_data.get("firstname"),
                "Lastname": patient_data.get("lastname"),
                "Gender": patient_data.get("gender"),
                "Birthdate": _iso_value(_date(patient_data.get("birthdate"))),
                "Email": patient_data.get("email"),
                "Phone": patient_data.get("phone"),
                "Mobile": patient_data.get("mobile"),
                "Street": patient_data.get("street"),
                "Street 2": patient_data.get("street2"),
                "Canton": patient_data.get("canton"),
                "Zipcode": patient_data.get("zipcode"),
                "City": patient_data.get("city"),
            }
            self.client.update_record(
                self._table_ids.get("Patients"),
                patient._record_id,
                fields,
            )
        self._loaded_at = 0


_repository = None
_repository_lock = threading.Lock()


def get_teable_repository():
    global _repository
    if not teable_enabled():
        raise TeableError("Teable is not enabled or is missing credentials")
    with _repository_lock:
        if _repository is None:
            _repository = TeableRepository()
        return _repository
