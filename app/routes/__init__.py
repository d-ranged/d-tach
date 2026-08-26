"""Shared helpers for the route blueprints."""


def build_detection_summary(settings, include_file_names: bool = False) -> str:
    """Return a one-line description of what the saved settings will detect.

    Mode pages no longer carry their own detection controls — those live in
    Settings and apply to every mode — so each page shows this read-only line
    instead. It exists to answer "what is about to happen to my file" without
    making the answer editable in two places.
    """
    parts = ["names and emails"]
    if settings.anonymize_dates:
        parts.append("dates")
    if settings.anonymize_locations:
        parts.append("locations")
    if settings.anonymize_urls:
        parts.append("URLs")

    config = settings.pattern_config
    if config.numeric_id_enabled:
        parts.append(f"{config.digit_count}-digit IDs")
    if include_file_names and config.check_file_names:
        parts.append("file and folder names")

    known_count = len(settings.known_values)
    if known_count:
        parts.append(f"{known_count:,} known value{'s' if known_count != 1 else ''}")

    summary = ", ".join(parts[:-1]) + " and " + parts[-1] if len(parts) > 1 else parts[0]
    if settings.hashing_enabled:
        summary += " — as hashed placeholders"
    return summary
