from typing import Any

from app.core.exceptions import AppError
from app.models import ServiceCustomField
from app.models.enums import CustomFieldType


def validate_custom_field_responses(
    fields: list[ServiceCustomField], responses: dict[str, Any]
) -> dict[str, Any]:
    errors: list[dict[str, str]] = []
    by_label = {field.field_label: field for field in fields}

    for unknown in sorted(set(responses) - set(by_label)):
        errors.append({"field": unknown, "message": "Unexpected custom field"})

    for label, field in by_label.items():
        present = label in responses
        if field.is_required and not present:
            errors.append({"field": label, "message": "This field is required"})
            continue
        if not present:
            continue

        value = responses[label]
        if field.field_type == CustomFieldType.TEXT:
            if not isinstance(value, str) or (field.is_required and not value.strip()):
                errors.append({"field": label, "message": "Enter a text value"})
        elif field.field_type == CustomFieldType.DROPDOWN:
            if not isinstance(value, str) or value not in (field.options or []):
                errors.append({"field": label, "message": "Select one of the allowed options"})
        elif field.field_type == CustomFieldType.BOOLEAN:
            if type(value) is not bool:
                errors.append({"field": label, "message": "Enter true or false"})
        elif field.field_type == CustomFieldType.FILE_UPLOAD:
            errors.append({"field": label, "message": "File upload is unavailable in Phase 1"})

    if errors:
        raise AppError("INVALID_CUSTOM_FIELDS", "Custom field responses are invalid", 422, errors)
    return responses

