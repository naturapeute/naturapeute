import unicodedata

from naturapeute.models import LANGUAGES, Therapist


CHOICE_FIELD_TYPES = {
    "Languages": "multipleSelect",
    "Agreements": "multipleSelect",
    "Payment Types": "multipleSelect",
    "Membership": "singleSelect",
}

LINK_FIELD_DEFINITIONS = {
    "Symptoms": {
        "Parent Source ID": {
            "relationship": "manyOne",
            "isOneWay": True,
        },
    },
    "Therapists": {
        "Primary Practice Source ID": {
            "relationship": "manyOne",
            "isOneWay": True,
        },
        "Practice Source IDs": {
            "relationship": "manyMany",
            "isOneWay": True,
        },
    },
}

LANGUAGE_CODES = tuple(code for code, _label in LANGUAGES)

CHOICE_COLORS = [
    "blue",
    "cyan",
    "green",
    "orange",
    "purple",
    "red",
    "teal",
    "yellow",
]


def link_field_options(table_name, field_name, table_id, foreign_table_id=None):
    try:
        options = LINK_FIELD_DEFINITIONS[table_name][field_name]
    except KeyError as error:
        raise ValueError(f"No Teable link definition for {table_name}.{field_name}") from error
    return {**options, "foreignTableId": foreign_table_id or table_id}


def normalize_language_codes(values):
    valid_codes = set(LANGUAGE_CODES)
    result = []
    for value in values or []:
        code = str(value).strip().lower()
        if code in valid_codes and code not in result:
            result.append(code)
    return result


def normalize_agreement(value):
    if value is None:
        return None
    normalized = unicodedata.normalize("NFKD", str(value).strip())
    normalized = normalized.encode("ascii", "ignore").decode("ascii")
    letters = "".join(character for character in normalized if character.isascii() and character.isalpha())
    return letters.upper() or None


def normalize_agreements(values):
    result = []
    for value in values or []:
        agreement = normalize_agreement(value)
        if agreement and agreement not in result:
            result.append(agreement)
    return result


def therapist_choice_options():
    values = {
        "Languages": set(LANGUAGE_CODES),
        "Agreements": {
            agreement
            for row in Therapist.mixed.values_list("agreements", flat=True)
            for agreement in normalize_agreements(row)
            if agreement
        },
        "Payment Types": {
            value
            for row in Therapist.mixed.values_list("payment_types", flat=True)
            for value in (row or [])
            if value
        },
        "Membership": {"pending", "invitee", "member", "premium"},
    }
    options = {}
    for field_name, field_values in values.items():
        options[field_name] = {
            "choices": [
                {
                    "name": value,
                    "color": CHOICE_COLORS[index % len(CHOICE_COLORS)],
                }
                for index, value in enumerate(sorted(field_values))
            ]
        }
    return options
