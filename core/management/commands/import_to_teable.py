import json
import mimetypes
import os
from concurrent.futures import ThreadPoolExecutor, as_completed
from collections import defaultdict
from pathlib import Path
from urllib.parse import urlparse

from django.conf import settings
from django.core.management.base import BaseCommand, CommandError

from blog.models import Article, ArticleTag
from core.teable import TeableClient, TeableError
from core.teable_schema import (
    CHOICE_FIELD_TYPES,
    link_field_options,
    normalize_agreements,
    normalize_language_codes,
    therapist_choice_options,
)
from naturapeute.models import (
    Office,
    OfficePicture,
    Patient,
    Practice,
    Symptom,
    Synonym,
    Therapist,
    TherapistPatient,
)


TABLE_DEFINITIONS = [
    (
        "Practices",
        "practices",
        [
            ("singleLineText", "Name", "name"),
            ("singleLineText", "Slug", "slug"),
            ("number", "Source ID", "source_id"),
            ("longText", "Data", "data"),
        ],
    ),
    (
        "Symptoms",
        "symptoms",
        [
            ("singleLineText", "Name", "name"),
            ("number", "Source ID", "source_id"),
            ("link", "Parent Source ID", "parent_source_id"),
            ("longText", "Synonyms", "synonyms"),
            ("longText", "Keywords", "keywords"),
            ("singleLineText", "Airtable ID", "airtable_id"),
        ],
    ),
    (
        "Synonyms",
        "synonyms",
        [
            ("singleLineText", "Name", "name"),
            ("number", "Source ID", "source_id"),
            ("longText", "Words", "words"),
            ("longText", "Data", "data"),
        ],
    ),
    (
        "Therapists",
        "therapists",
        [
            ("singleLineText", "Name", "name"),
            ("number", "Source ID", "source_id"),
            ("singleLineText", "Slug", "slug"),
            ("singleLineText", "Firstname", "firstname"),
            ("singleLineText", "Lastname", "lastname"),
            ("singleLineText", "Gender", "gender"),
            ("singleLineText", "Email", "email"),
            ("singleLineText", "Phone", "phone"),
            ("checkbox", "Certified", "is_certified"),
            ("longText", "Description", "description"),
            ("longText", "Price", "price"),
            ("longText", "Timetable", "timetable"),
            ("multipleSelect", "Languages", "languages"),
            ("multipleSelect", "Agreements", "agreements"),
            ("multipleSelect", "Payment Types", "payment_types"),
            ("longText", "Socials", "socials"),
            ("singleSelect", "Membership", "membership"),
            ("link", "Primary Practice Source ID", "practice_source_id"),
            ("link", "Practice Source IDs", "practice_source_ids"),
            ("longText", "Symptom Source IDs", "symptom_source_ids"),
            ("longText", "Offices", "offices"),
            ("longText", "Patient Source IDs", "patient_source_ids"),
            ("longText", "Invoice Data", "invoice_data"),
            ("longText", "Services", "services"),
            ("singleLineText", "Calendly URL", "calendly_url"),
            ("date", "Creation Date", "creation_date"),
            ("date", "Modification Date", "modification_date"),
            ("singleLineText", "Photo Source", "photo_source"),
            ("attachment", "Photo", "photo"),
            ("attachment", "Office Pictures", "office_pictures"),
        ],
    ),
    (
        "Offices",
        "offices",
        [
            ("singleLineText", "Name", "name"),
            ("number", "Source ID", "source_id"),
            ("number", "Therapist Source ID", "therapist_source_id"),
            ("singleLineText", "Street", "street"),
            ("singleLineText", "Zipcode", "zipcode"),
            ("singleLineText", "City", "city"),
            ("singleLineText", "Country", "country"),
            ("number", "Latitude", "latitude"),
            ("number", "Longitude", "longitude"),
            ("longText", "Coordinates", "coordinates"),
            ("longText", "Picture Source IDs", "picture_source_ids"),
            ("longText", "Data", "data"),
            ("attachment", "Pictures", "pictures"),
        ],
    ),
    (
        "Office Pictures",
        "office_pictures",
        [
            ("singleLineText", "Name", "name"),
            ("number", "Source ID", "source_id"),
            ("number", "Office Source ID", "office_source_id"),
            ("singleLineText", "File", "file"),
            ("longText", "Data", "data"),
            ("attachment", "Picture", "picture"),
        ],
    ),
    (
        "Patients",
        "patients",
        [
            ("singleLineText", "Name", "name"),
            ("number", "Source ID", "source_id"),
            ("singleLineText", "Firstname", "firstname"),
            ("singleLineText", "Lastname", "lastname"),
            ("singleLineText", "Gender", "gender"),
            ("date", "Birthdate", "birthdate"),
            ("singleLineText", "Email", "email"),
            ("singleLineText", "Phone", "phone"),
            ("singleLineText", "Mobile", "mobile"),
            ("singleLineText", "Street", "street"),
            ("singleLineText", "Street 2", "street2"),
            ("singleLineText", "Canton", "canton"),
            ("number", "Zipcode", "zipcode"),
            ("singleLineText", "City", "city"),
            ("longText", "Therapist Source IDs", "therapist_source_ids"),
            ("longText", "Data", "data"),
        ],
    ),
    (
        "Therapist Patients",
        "therapist_patients",
        [
            ("singleLineText", "Name", "name"),
            ("number", "Source ID", "source_id"),
            ("number", "Therapist Source ID", "therapist_source_id"),
            ("number", "Patient Source ID", "patient_source_id"),
            ("date", "Creation Date", "creation_date"),
            ("longText", "Data", "data"),
        ],
    ),
    (
        "Article Tags",
        "article_tags",
        [
            ("singleLineText", "Name", "name"),
            ("number", "Source ID", "source_id"),
            ("singleLineText", "Slug", "slug"),
            ("longText", "Data", "data"),
        ],
    ),
    (
        "Articles",
        "articles",
        [
            ("singleLineText", "Title", "title"),
            ("number", "Source ID", "source_id"),
            ("singleLineText", "Slug", "slug"),
            ("longText", "Body", "body"),
            ("longText", "Tag Source IDs", "tag_source_ids"),
            ("longText", "Tag Names", "tag_names"),
            ("date", "Creation Date", "creation_date"),
            ("date", "Update Date", "update_date"),
            ("singleLineText", "Image Source", "image_source"),
            ("attachment", "Image", "image"),
        ],
    ),
    (
        "Assets",
        "assets",
        [
            ("singleLineText", "Path", "path"),
            ("singleLineText", "Category", "category"),
            ("singleLineText", "Content Type", "content_type"),
            ("number", "Size", "size"),
            ("longText", "Manifest", "manifest"),
            ("attachment", "Asset", "asset"),
        ],
    ),
]


def _json_value(value):
    if value is None:
        return None
    return json.dumps(value, ensure_ascii=False, default=str)


def _iso_value(value):
    return value.isoformat() if value is not None else None


def _string_value(value):
    if value is None:
        return None
    value = str(value)
    return value or None


def _unique_tags(tags):
    result = []
    seen = set()
    for tag in tags:
        key = (tag.pk, tag.name, tag.slug)
        if key in seen:
            continue
        seen.add(key)
        result.append(tag)
    return result


def _office_data(office):
    coordinates = office.coordinates or []
    return {
        "source_id": office.pk,
        "therapist_source_id": office.therapist_id,
        "street": office.street,
        "zipcode": office.zipcode,
        "city": office.city,
        "country": office.country,
        "coordinates": coordinates,
        "picture_source_ids": [picture.pk for picture in office.pictures.all()],
        "pictures": [_string_value(picture.file) for picture in office.pictures.all()],
    }


class AssetIndex:
    def __init__(self, roots):
        self.entries = []
        self.by_key = {}
        self.by_basename = {}
        for root_value in roots:
            root = Path(root_value).expanduser().resolve()
            if not root.is_dir():
                raise CommandError(f"Asset root does not exist or is not a directory: {root}")
            for path in sorted(path for path in root.rglob("*") if path.is_file()):
                relative = path.relative_to(root).as_posix()
                display_path = f"{root.name}/{relative}"
                entry = {
                    "display_path": display_path,
                    "path": path,
                    "content_type": mimetypes.guess_type(path.name)[0] or "application/octet-stream",
                    "size": path.stat().st_size,
                    "root": root,
                }
                self.entries.append(entry)
                for key in {display_path, relative, path.name}:
                    self.by_key.setdefault(key.lower(), []).append(entry)
                self.by_basename.setdefault(path.name.lower(), []).append(entry)

    def resolve(self, value):
        if not value:
            return None
        text = str(value)
        parsed = urlparse(text)
        candidates = [text, parsed.path.lstrip("/")]
        if parsed.path:
            candidates.append(Path(parsed.path).name)
        if text.startswith("/uploads/"):
            candidates.append(text.removeprefix("/uploads/"))
        if text.startswith("uploads/"):
            candidates.append(text.removeprefix("uploads/"))

        for candidate in candidates:
            matches = self.by_key.get(candidate.lower(), [])
            if len(matches) == 1:
                return matches[0]
        matches = self.by_basename.get(Path(parsed.path or text).name.lower(), [])
        if len(matches) == 1:
            return matches[0]
        return text if parsed.scheme in {"http", "https"} else None


class TeableImporter:
    batch_size = 100

    def __init__(self, client, asset_index, clear_existing=True, output=None):
        self.client = client
        self.asset_index = asset_index
        self.clear_existing = clear_existing
        self.output = output
        self.tables = {}
        self.attachments = []

    def log(self, message):
        if self.output:
            self.output.write(message)

    def ensure_schema(self):
        existing = {table["name"]: table for table in self.client.list_tables()}
        choice_options = therapist_choice_options()
        for name, db_table_name, fields in TABLE_DEFINITIONS:
            table = existing.get(name)
            initial_fields = [
                definition for definition in fields if definition[0] != "link"
            ]
            if table is None:
                table = self.client.create_table(
                    name,
                    db_table_name,
                    initial_fields,
                    description=f"Imported from the Naturapeute Django {db_table_name} data.",
                    field_options=choice_options,
                )
            table_id = table["id"]
            field_map = {field["name"]: field for field in self.client.list_fields(table_id)}
            for field_type, field_name, db_field_name in fields:
                field = field_map.get(field_name)
                options = choice_options.get(field_name)
                if field_type == "link":
                    foreign_table_id = (
                        self.tables["Practices"]["id"]
                        if name == "Therapists"
                        else table_id
                    )
                    options = link_field_options(
                        name, field_name, table_id, foreign_table_id=foreign_table_id
                    )
                if field is None:
                    field = self.client.create_field(
                        table_id,
                        field_type,
                        field_name,
                        db_field_name,
                        options=options,
                    )
                else:
                    needs_choice_reset = False
                    if field_name in CHOICE_FIELD_TYPES:
                        current_choices = {
                            choice.get("name")
                            for choice in field.get("options", {}).get("choices", [])
                        }
                        expected_choices = {
                            choice.get("name")
                            for choice in options["choices"]
                        }
                        needs_choice_reset = current_choices != expected_choices
                    needs_link_reset = False
                    if field_type == "link":
                        current_options = field.get("options", {})
                        needs_link_reset = any(
                            current_options.get(key) != value
                            for key, value in options.items()
                        )
                    if (
                        field.get("type") != field_type
                        or needs_choice_reset
                        or needs_link_reset
                    ):
                        if field_name not in CHOICE_FIELD_TYPES and field_type != "link":
                            raise TeableError(
                                f"Table {name} field {field_name} has type {field.get('type')}, "
                                f"expected {field_type}"
                            )
                        self.client.delete_field(table_id, field["id"])
                        field = self.client.create_field(
                            table_id,
                            field_type,
                            field_name,
                            db_field_name,
                            options=options,
                        )
                field_map[field_name] = field
            self.tables[name] = {"id": table_id, "fields": field_map}

    def clear_table(self, table_name):
        if not self.clear_existing:
            return
        table_id = self.tables[table_name]["id"]
        while True:
            records = self.client.list_records(table_id, take=1000, skip=0)
            if not records:
                return
            for start in range(0, len(records), 100):
                record_ids = [record["id"] for record in records[start : start + 100]]
                self.client.delete_records(table_id, record_ids)

    def clear_all_tables(self):
        for table_name in self.tables:
            self.clear_table(table_name)

    def add_attachment(self, table_name, record_id, field_name, source):
        if not source:
            return
        if isinstance(source, dict):
            resolved = source
        elif self.asset_index:
            resolved = self.asset_index.resolve(source)
        else:
            resolved = source
        if not resolved:
            self.log(
                f"skipping unresolved attachment in {table_name}.{field_name}: "
                f"{Path(str(source)).name}\n"
            )
            return
        self.attachments.append(
            {
                "table_name": table_name,
                "record_id": record_id,
                "field_name": field_name,
                "source": resolved,
            }
        )

    def write_rows(self, table_name, rows):
        self.clear_table(table_name)
        table_id = self.tables[table_name]["id"]
        created_records = []
        for start in range(0, len(rows), self.batch_size):
            batch = rows[start : start + self.batch_size]
            records = self.client.create_records(table_id, [row["fields"] for row in batch])
            if len(records) != len(batch):
                raise TeableError(
                    f"Teable returned {len(records)} records for a batch of {len(batch)} in {table_name}"
                )
            created_records.extend(records)
            for row, record in zip(batch, records):
                for field_name, source in row.get("attachments", []):
                    self.add_attachment(table_name, record["id"], field_name, source)
        self.log(f"{table_name}: {len(rows)} records\n")
        return created_records

    def upload_attachment(self, attachment):
        table = self.tables[attachment["table_name"]]
        field = table["fields"].get(attachment["field_name"])
        if not field:
            raise TeableError(
                f"Attachment field {attachment['field_name']} not found in {attachment['table_name']}"
            )
        source = attachment["source"]
        if isinstance(source, dict):
            return self.client.upload_attachment(
                table["id"],
                attachment["record_id"],
                field["id"],
                file_path=source["path"],
            )
        return self.client.upload_attachment(
            table["id"],
            attachment["record_id"],
            field["id"],
            file_url=source,
        )

    def upload_attachments(self):
        if not self.attachments:
            return
        try:
            workers = int(os.environ.get("TEABLE_UPLOAD_WORKERS", "6"))
        except ValueError:
            workers = 6
        workers = max(1, min(workers, len(self.attachments)))
        skipped = 0
        with ThreadPoolExecutor(max_workers=workers) as executor:
            futures = {
                executor.submit(self.upload_attachment, attachment): attachment
                for attachment in self.attachments
            }
            for index, future in enumerate(as_completed(futures), start=1):
                attachment = futures[future]
                try:
                    future.result()
                except Exception as error:
                    source = attachment["source"]
                    label = source.get("display_path") if isinstance(source, dict) else source
                    if isinstance(source, str) and source.startswith(("http://", "https://")):
                        skipped += 1
                        self.log(
                            f"skipping unavailable remote attachment in "
                            f"{attachment['table_name']}.{attachment['field_name']}: "
                            f"{Path(str(label)).name}\n"
                        )
                    else:
                        raise TeableError(
                            f"Attachment upload failed for {attachment['table_name']}."
                            f"{attachment['field_name']}: {Path(str(label)).name}"
                        ) from error
                if index == 1 or index % 25 == 0 or index == len(self.attachments):
                    self.log(f"attachments: {index}/{len(self.attachments)}\n")
        if skipped:
            self.log(f"attachments skipped: {skipped}\n")

    def import_data(self):
        practices = list(Practice.objects.all().order_by("pk"))
        symptoms = list(Symptom.objects.all().order_by("pk"))
        synonyms = list(Synonym.objects.all().order_by("pk"))
        therapists = list(
            Therapist.mixed.all()
            .select_related("practice")
            .prefetch_related("practices", "symptoms", "offices__pictures")
            .order_by("pk")
        )
        linkable_practices = practices
        offices = list(Office.objects.select_related("therapist").prefetch_related("pictures").order_by("pk"))
        office_pictures = list(OfficePicture.objects.select_related("office").order_by("pk"))
        patients = list(Patient.objects.all().order_by("pk"))
        therapist_patients = list(
            TherapistPatient.objects.select_related("therapist", "patient").order_by("pk")
        )
        article_tags = _unique_tags(ArticleTag.objects.all().order_by("pk"))
        articles = list(Article.objects.prefetch_related("tags").all().order_by("pk"))

        offices_by_therapist = defaultdict(list)
        for office in offices:
            offices_by_therapist[office.therapist_id].append(_office_data(office))

        office_pictures_by_therapist = defaultdict(list)
        for picture in office_pictures:
            office_pictures_by_therapist[picture.office.therapist_id].append(_string_value(picture.file))

        patients_by_therapist = defaultdict(list)
        therapists_by_patient = defaultdict(list)
        relation_data = []
        for relation in therapist_patients:
            patients_by_therapist[relation.therapist_id].append(relation.patient_id)
            therapists_by_patient[relation.patient_id].append(relation.therapist_id)
            relation_data.append(
                {
                    "source_id": relation.pk,
                    "therapist_source_id": relation.therapist_id,
                    "patient_source_id": relation.patient_id,
                    "creation_date": _iso_value(relation.creation_date),
                }
            )

        self.clear_all_tables()

        practice_rows = [
            {
                "fields": {
                    "Name": "All practices",
                    "Data": _json_value(
                        [
                            {"source_id": p.pk, "name": p.name, "slug": p.slug}
                            for p in practices
                        ]
                    ),
                }
            }
        ] + [
            {
                "fields": {
                    "Name": practice.name,
                    "Slug": practice.slug,
                    "Source ID": practice.pk,
                }
            }
            for practice in linkable_practices
        ]
        practice_records = self.write_rows("Practices", practice_rows)
        practice_record_ids = {
            practice.pk: record["id"]
            for practice, record in zip(linkable_practices, practice_records[1:])
        }
        symptom_rows = [
            {
                "fields": {
                    "Name": s.name,
                    "Source ID": s.pk,
                    "Synonyms": _json_value(s.synonyms),
                    "Keywords": s.keywords,
                }
            }
            for s in symptoms
        ]
        symptom_records = self.write_rows("Symptoms", symptom_rows)
        symptom_record_ids = {
            symptom.pk: record["id"]
            for symptom, record in zip(symptoms, symptom_records)
        }
        symptom_table_id = self.tables["Symptoms"]["id"]
        for symptom, record in zip(symptoms, symptom_records):
            parent_record_id = symptom_record_ids.get(symptom.parent_id)
            if parent_record_id:
                self.client.update_record(
                    symptom_table_id,
                    record["id"],
                    {"Parent Source ID": {"id": parent_record_id}},
                )
        self.write_rows(
            "Synonyms",
            [
                {
                    "fields": {
                        "Name": "All synonyms",
                        "Words": _json_value(
                            [{"source_id": s.pk, "name": s.name, "words": s.words} for s in synonyms]
                        ),
                        "Data": _json_value(
                            [{"source_id": s.pk, "name": s.name, "words": s.words} for s in synonyms]
                        ),
                    }
                }
            ],
        )

        therapist_rows = []
        for therapist in therapists:
            therapist_rows.append(
                {
                    "fields": {
                        "Name": therapist.name,
                        "Source ID": therapist.pk,
                        "Slug": therapist.slug,
                        "Firstname": therapist.firstname,
                        "Lastname": therapist.lastname,
                        "Gender": therapist.gender,
                        "Email": therapist.email,
                        "Phone": therapist.phone,
                        "Certified": therapist.is_certified,
                        "Description": therapist.description,
                        "Price": therapist.price,
                        "Timetable": therapist.timetable,
                        "Languages": normalize_language_codes(therapist.languages),
                        "Agreements": normalize_agreements(therapist.agreements),
                        "Payment Types": list(therapist.payment_types or []),
                        "Socials": _json_value(therapist.socials),
                        "Membership": therapist.membership,

                        "Symptom Source IDs": _json_value([s.pk for s in therapist.symptoms.all()]),
                        "Offices": _json_value(offices_by_therapist[therapist.pk]),
                        "Patient Source IDs": _json_value(patients_by_therapist[therapist.pk]),
                        "Invoice Data": _json_value(therapist.invoice_data),
                        "Services": _json_value(therapist.services),
                        "Calendly URL": therapist.calendly_url,
                        "Creation Date": _iso_value(therapist.creation_date),
                        "Modification Date": _iso_value(therapist.modification_date),
                        "Photo Source": _string_value(therapist.photo),
                    },
                    "attachments": [
                        ("Photo", _string_value(therapist.photo)),
                        *[
                            ("Office Pictures", picture)
                            for picture in office_pictures_by_therapist[therapist.pk]
                        ],
                    ],
                }
            )
        therapist_records = self.write_rows("Therapists", therapist_rows)
        therapist_table_id = self.tables["Therapists"]["id"]
        for therapist, record in zip(therapists, therapist_records):
            practice_record_id = practice_record_ids.get(therapist.practice_id)
            practice_ids = [
                practice.pk
                for practice in therapist.practices.all()
                if practice.pk != therapist.practice_id
            ]
            practice_records = [
                {"id": practice_record_ids[practice_id]}
                for practice_id in practice_ids
                if practice_id in practice_record_ids
            ]
            relation_fields = {"Practice Source IDs": practice_records}
            if practice_record_id:
                relation_fields["Primary Practice Source ID"] = {"id": practice_record_id}
            self.client.update_record(therapist_table_id, record["id"], relation_fields)

        self.write_rows(
            "Offices",
            [
                {
                    "fields": {
                        "Name": "All offices",
                        "Data": _json_value([_office_data(office) for office in offices]),
                    },
                    "attachments": [
                        ("Pictures", _string_value(picture.file)) for picture in office_pictures
                    ],
                }
            ],
        )
        self.write_rows(
            "Office Pictures",
            [
                {
                    "fields": {
                        "Name": "All office pictures",
                        "Data": _json_value(
                            [
                                {
                                    "source_id": picture.pk,
                                    "office_source_id": picture.office_id,
                                    "file": _string_value(picture.file),
                                }
                                for picture in office_pictures
                            ]
                        ),
                    },
                    "attachments": [
                        ("Picture", _string_value(picture.file)) for picture in office_pictures
                    ],
                }
            ],
        )
        self.write_rows(
            "Patients",
            [
                {
                    "fields": {
                        "Name": "All patients",
                        "Data": _json_value(
                            [
                                {
                                    "source_id": patient.pk,
                                    "firstname": patient.firstname,
                                    "lastname": patient.lastname,
                                    "gender": patient.gender,
                                    "birthdate": _iso_value(patient.birthdate),
                                    "email": patient.email,
                                    "phone": patient.phone,
                                    "mobile": patient.mobile,
                                    "street": patient.street,
                                    "street2": patient.street2,
                                    "canton": patient.canton,
                                    "zipcode": patient.zipcode,
                                    "city": patient.city,
                                    "therapist_source_ids": therapists_by_patient[patient.pk],
                                }
                                for patient in patients
                            ]
                        ),
                    }
                }
            ],
        )
        self.write_rows(
            "Therapist Patients",
            [
                {
                    "fields": {
                        "Name": "All therapist-patient relations",
                        "Data": _json_value(relation_data),
                    }
                }
            ],
        )
        self.write_rows(
            "Article Tags",
            [
                {
                    "fields": {
                        "Name": "All article tags",
                        "Data": _json_value(
                            [
                                {"source_id": tag.pk, "name": tag.name, "slug": tag.slug}
                                for tag in article_tags
                            ]
                        ),
                    }
                }
            ],
        )
        self.write_rows(
            "Articles",
            [
                {
                    "fields": {
                        "Title": article.title,
                        "Source ID": article.pk,
                        "Slug": article.slug,
                        "Body": article.body,
                        "Tag Source IDs": _json_value([tag.pk for tag in tags]),
                        "Tag Names": _json_value([tag.name for tag in tags]),
                        "Creation Date": _iso_value(article.creation_date),
                        "Update Date": _iso_value(article.update_date),
                        "Image Source": _string_value(article.image),
                    },
                    "attachments": [("Image", _string_value(article.image))],
                }
                for article in articles
                for tags in [_unique_tags(article.tags.all())]
            ],
        )

        asset_rows = []
        if self.asset_index:
            manifest = [
                {
                    "path": entry["display_path"],
                    "content_type": entry["content_type"],
                    "size": entry["size"],
                }
                for entry in self.asset_index.entries
            ]
            asset_rows = [
                {
                    "fields": {
                        "Path": "All server assets",
                        "Category": "server",
                        "Content Type": "mixed",
                        "Size": sum(entry["size"] for entry in self.asset_index.entries),
                        "Manifest": _json_value(manifest),
                    },
                    "attachments": [("Asset", entry) for entry in self.asset_index.entries],
                }
            ]
        else:
            asset_rows = [
                {
                    "fields": {
                        "Path": "All server assets",
                        "Category": "server",
                        "Content Type": "mixed",
                        "Manifest": "[]",
                    }
                }
            ]
        self.write_rows("Assets", asset_rows)
        self.upload_attachments()


class Command(BaseCommand):
    help = "Create/update the Naturapeute Teable base and import Django data and media."

    def add_arguments(self, parser):
        parser.add_argument(
            "--asset-root",
            action="append",
            dest="asset_roots",
            help="Directory containing assets; may be supplied multiple times.",
        )
        parser.add_argument(
            "--no-clear",
            action="store_true",
            help="Keep existing records in managed Teable tables.",
        )

    def handle(self, *args, **options):
        roots = options.get("asset_roots")
        if roots is None:
            roots = [
                root
                for root in os.environ.get("TEABLE_ASSET_ROOTS", "").split(os.pathsep)
                if root
            ]
        asset_index = AssetIndex(roots) if roots else None
        try:
            client = TeableClient(
                base_url=getattr(settings, "TEABLE_API_URL", "https://app.teable.ai"),
                base_id=getattr(settings, "TEABLE_BASE_ID", ""),
                token=getattr(settings, "TEABLE_API_TOKEN", ""),
            )
            client.get_base()
            importer = TeableImporter(
                client,
                asset_index,
                clear_existing=not options["no_clear"],
                output=self.stdout,
            )
            importer.ensure_schema()
            importer.import_data()
        except TeableError as error:
            raise CommandError(str(error)) from error
