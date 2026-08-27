import json

from django.conf import settings
from django.core.management.base import BaseCommand, CommandError

from core.teable import TeableClient, TeableError
from core.teable_schema import (
    CHOICE_FIELD_TYPES,
    link_field_options,
    normalize_agreements,
    normalize_language_codes,
    therapist_choice_options,
)
from naturapeute.models import Patient, Practice, Therapist, TherapistPatient


def _source_id_list(value):
    if isinstance(value, str):
        try:
            value = json.loads(value)
        except (TypeError, ValueError, json.JSONDecodeError):
            return []
    if not isinstance(value, list):
        return []
    result = []
    for item in value:
        try:
            source_id = int(item)
        except (TypeError, ValueError):
            continue
        if source_id not in result:
            result.append(source_id)
    return result


class Command(BaseCommand):
    help = "Configure Teable choice fields and migrate their existing therapist values."

    def handle(self, *args, **options):
        try:
            client = TeableClient(
                base_url=settings.TEABLE_API_URL,
                base_id=settings.TEABLE_BASE_ID,
                token=settings.TEABLE_API_TOKEN,
            )
            tables = {table["name"]: table for table in client.list_tables()}
            therapist_table = tables.get("Therapists")
            symptom_table = tables.get("Symptoms")
            if therapist_table is None:
                raise CommandError("Teable base is missing the Therapists table")
            if symptom_table is None:
                raise CommandError("Teable base is missing the Symptoms table")

            symptom_table_id = symptom_table["id"]
            symptom_records = client.list_records(symptom_table_id, take=1000)
            symptom_record_ids = {}
            for record in symptom_records:
                try:
                    source_id = int(record.get("fields", {}).get("Source ID"))
                except (TypeError, ValueError):
                    continue
                symptom_record_ids[source_id] = record["id"]

            symptom_fields = {
                field["name"]: field for field in client.list_fields(symptom_table_id)
            }
            parent_field = symptom_fields.get("Parent Source ID")
            parent_options = link_field_options(
                "Symptoms", "Parent Source ID", symptom_table_id
            )
            if parent_field is None:
                parent_field = client.create_field(
                    symptom_table_id,
                    "link",
                    "Parent Source ID",
                    "parent_source_id",
                    options=parent_options,
                )
            elif parent_field.get("type") != "link" or any(
                parent_field.get("options", {}).get(key) != value
                for key, value in parent_options.items()
            ):
                client.delete_field(symptom_table_id, parent_field["id"])
                parent_field = client.create_field(
                    symptom_table_id,
                    "link",
                    "Parent Source ID",
                    parent_field["dbFieldName"],
                    options=parent_options,
                )

            migrated_parents = 0
            for record in symptom_records:
                parent_value = record.get("fields", {}).get("Parent Source ID")
                if isinstance(parent_value, dict):
                    parent_record_id = parent_value.get("id")
                else:
                    try:
                        parent_source_id = int(parent_value)
                    except (TypeError, ValueError):
                        parent_source_id = None
                    parent_record_id = symptom_record_ids.get(parent_source_id)
                client.update_record(
                    symptom_table_id,
                    record["id"],
                    {
                        "Parent Source ID": (
                            {"id": parent_record_id} if parent_record_id else None
                        )
                    },
                )
                migrated_parents += 1

            table_id = therapist_table["id"]
            patient_table = tables.get("Patients")
            if patient_table is None:
                raise CommandError("Teable base is missing the Patients table")
            patient_table_id = patient_table["id"]
            patient_records = client.list_records(patient_table_id, take=1000)
            patient_fields = {
                field["name"]: field for field in client.list_fields(patient_table_id)
            }
            if "Data" not in patient_fields:
                client.create_field(patient_table_id, "longText", "Data", "data")
                patient_fields["Data"] = True

            compacted_patients = 0
            if len(patient_records) != 1 or not patient_records[0].get("fields", {}).get("Data"):
                patient_therapists = {}
                for relation in TherapistPatient.objects.all().order_by("pk"):
                    patient_therapists.setdefault(relation.patient_id, []).append(
                        relation.therapist_id
                    )
                for start in range(0, len(patient_records), 100):
                    client.delete_records(
                        patient_table_id,
                        [
                            record["id"]
                            for record in patient_records[start : start + 100]
                        ],
                    )
                client.create_records(
                    patient_table_id,
                    [
                        {
                            "Name": "All patients",
                            "Data": json.dumps(
                                [
                                    {
                                        "source_id": patient.pk,
                                        "firstname": patient.firstname,
                                        "lastname": patient.lastname,
                                        "gender": patient.gender,
                                        "birthdate": patient.birthdate.isoformat()
                                        if patient.birthdate
                                        else None,
                                        "email": patient.email,
                                        "phone": patient.phone,
                                        "mobile": patient.mobile,
                                        "street": patient.street,
                                        "street2": patient.street2,
                                        "canton": patient.canton,
                                        "zipcode": patient.zipcode,
                                        "city": patient.city,
                                        "therapist_source_ids": patient_therapists.get(
                                            patient.pk, []
                                        ),
                                    }
                                    for patient in Patient.objects.all().order_by("pk")
                                ],
                                ensure_ascii=False,
                            ),
                        }
                    ],
                )
                compacted_patients = len(patient_records)

            practice_table = tables.get("Practices")
            if practice_table is None:
                raise CommandError("Teable base is missing the Practices table")
            practice_table_id = practice_table["id"]
            source_therapists = {
                therapist.pk: therapist
                for therapist in Therapist.mixed.prefetch_related("practices").all()
            }
            therapist_records = client.list_records(table_id, take=1000)
            practice_records = client.list_records(practice_table_id, take=1000)
            practice_record_ids = {}
            for record in practice_records:
                try:
                    source_id = int(record.get("fields", {}).get("Source ID"))
                except (TypeError, ValueError):
                    continue
                practice_record_ids[source_id] = record["id"]

            practices = {
                practice.pk: practice
                for practice in Practice.objects.all()
            }
            missing_practices = [
                practice
                for practice in practices.values()
                if practice.pk not in practice_record_ids
            ]
            if missing_practices:
                created = client.create_records(
                    practice_table_id,
                    [
                        {
                            "Name": practice.name,
                            "Slug": practice.slug,
                            "Source ID": practice.pk,
                        }
                        for practice in sorted(missing_practices, key=lambda item: item.pk)
                    ],
                )
                for practice, record in zip(
                    sorted(missing_practices, key=lambda item: item.pk), created
                ):
                    practice_record_ids[practice.pk] = record["id"]

            practice_field_options = link_field_options(
                "Therapists",
                "Primary Practice Source ID",
                table_id,
                foreign_table_id=practice_table_id,
            )
            fields = {field["name"]: field for field in client.list_fields(table_id)}
            primary_field = fields.get("Primary Practice Source ID")
            if primary_field is None:
                primary_field = client.create_field(
                    table_id,
                    "link",
                    "Primary Practice Source ID",
                    "practice_source_id",
                    options=practice_field_options,
                )
            elif primary_field.get("type") != "link" or any(
                primary_field.get("options", {}).get(key) != value
                for key, value in practice_field_options.items()
            ):
                client.delete_field(table_id, primary_field["id"])
                primary_field = client.create_field(
                    table_id,
                    "link",
                    "Primary Practice Source ID",
                    primary_field["dbFieldName"],
                    options=practice_field_options,
                )

            migrated_practices = 0
            for record in therapist_records:
                try:
                    source_id = int(record.get("fields", {}).get("Source ID"))
                except (TypeError, ValueError):
                    source_id = None
                source_therapist = source_therapists.get(source_id)
                if source_therapist:
                    practice_record_id = practice_record_ids.get(source_therapist.practice_id)
                else:
                    value = record.get("fields", {}).get("Primary Practice Source ID")
                    practice_record_id = (
                        value.get("id") if isinstance(value, dict) else None
                    )
                    if not practice_record_id:
                        practice_record_id = practice_record_ids.get(_source_id_list(value)[0]) if _source_id_list(value) else None
                client.update_record(
                    table_id,
                    record["id"],
                    {
                        "Primary Practice Source ID": (
                            {"id": practice_record_id} if practice_record_id else None
                        )
                    },
                )
                migrated_practices += 1

            practice_sources_options = link_field_options(
                "Therapists",
                "Practice Source IDs",
                table_id,
                foreign_table_id=practice_table_id,
            )
            practice_sources_field = fields.get("Practice Source IDs")
            if practice_sources_field is None:
                practice_sources_field = client.create_field(
                    table_id,
                    "link",
                    "Practice Source IDs",
                    "practice_source_ids",
                    options=practice_sources_options,
                )
            elif practice_sources_field.get("type") != "link" or any(
                practice_sources_field.get("options", {}).get(key) != value
                for key, value in practice_sources_options.items()
            ):
                client.delete_field(table_id, practice_sources_field["id"])
                practice_sources_field = client.create_field(
                    table_id,
                    "link",
                    "Practice Source IDs",
                    practice_sources_field["dbFieldName"],
                    options=practice_sources_options,
                )

            migrated_practice_lists = 0
            for record in therapist_records:
                try:
                    source_id = int(record.get("fields", {}).get("Source ID"))
                except (TypeError, ValueError):
                    source_id = None
                source_therapist = source_therapists.get(source_id)
                if source_therapist:
                    source_ids = [
                        practice_record_ids.get(practice_id)
                        for practice_id in source_therapist.practices.values_list(
                            "pk", flat=True
                        )
                    ]
                else:
                    value = record.get("fields", {}).get("Practice Source IDs")
                    source_ids = [
                        practice_record_ids.get(item.get("id"))
                        for item in value
                        if isinstance(item, dict)
                    ] if isinstance(value, list) else [
                        practice_record_ids.get(practice_id)
                        for practice_id in _source_id_list(value)
                    ]
                links = [{"id": record_id} for record_id in source_ids if record_id]
                client.update_record(
                    table_id,
                    record["id"],
                    {"Practice Source IDs": links},
                )
                migrated_practice_lists += 1

            choices = therapist_choice_options()
            fields = {field["name"]: field for field in client.list_fields(table_id)}

            for field_name, field_type in CHOICE_FIELD_TYPES.items():
                field = fields.get(field_name)
                if field is None:
                    raise CommandError(f"Teable Therapists table is missing {field_name}")
                expected = {choice["name"] for choice in choices[field_name]["choices"]}
                actual = {
                    choice.get("name")
                    for choice in field.get("options", {}).get("choices", [])
                }
                if field.get("type") != field_type or actual != expected:
                    client.delete_field(table_id, field["id"])
                    field = client.create_field(
                        table_id,
                        field_type,
                        field_name,
                        field["dbFieldName"],
                        options=choices[field_name],
                    )
                    fields[field_name] = field

            source_values = {
                therapist.pk: therapist
                for therapist in Therapist.mixed.only(
                    "pk", "languages", "agreements", "payment_types", "membership"
                )
            }
            updated = 0
            for record in client.list_records(table_id, take=1000):
                source_id = record.get("fields", {}).get("Source ID")
                try:
                    source_id = int(source_id)
                except (TypeError, ValueError):
                    continue
                therapist = source_values.get(source_id)
                if not therapist:
                    continue
                client.update_record(
                    table_id,
                    record["id"],
                    {
                        "Languages": normalize_language_codes(therapist.languages),
                        "Agreements": normalize_agreements(therapist.agreements),
                        "Payment Types": list(therapist.payment_types or []),
                        "Membership": therapist.membership,
                    },
                )
                updated += 1
            self.stdout.write(
                f"configured Symptoms.Parent Source ID as a relation; "
                f"migrated {migrated_parents} symptom records; "
                f"configured Therapists.Primary Practice Source ID as a relation; "
                f"migrated {migrated_practices} therapist primary-practice references; "
                f"migrated {migrated_practice_lists} additional-practice references; "
                f"compacted {compacted_patients} patient records; "
                f"configured Languages, Agreements, Payment Types, and Membership; "
                f"updated {updated} therapist records"
            )
        except (StopIteration, TeableError) as error:
            raise CommandError(str(error)) from error
