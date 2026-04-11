import re

from flask import Blueprint, current_app, jsonify, render_template, request

from app.services.anonymizer import ENTITIES, STUDENT_NUMBER_ENTITY, build_student_number_recognizer
from app.services.hash_encoder import HashEncoder
from app.services.pattern_config import PatternConfig

bp = Blueprint("text", __name__)

_SUPPORTED_LANGUAGES = ("en", "nl")


def _build_entity_list(anonymize_dates: bool, student_number_enabled: bool = False) -> list[str]:
    """Return entity list with DATE_TIME and STUDENT_NUMBER included only when opted in."""
    result = list(ENTITIES) if anonymize_dates else [e for e in ENTITIES if e != "DATE_TIME"]
    if student_number_enabled:
        result.append(STUDENT_NUMBER_ENTITY)
    return result


@bp.route("/")
def index():
    """Redirect root to text mode."""
    return _render_text_mode()


@bp.route("/text")
def text_mode():
    """Render the Text Mode page."""
    return _render_text_mode()


@bp.route("/text/anonymize", methods=["POST"])
def anonymize():
    """Anonymize submitted text and return the result as JSON.

    Expects JSON body:
        text                     (str)  — the text to anonymize
        language                 (str)  — 'en' or 'nl', user-selected
        hashing_enabled          (bool)
        secret                   (str)  — required when hashing_enabled is true
        key_reference_enabled    (bool)
        anonymize_dates          (bool) — include DATE_TIME entities; default false
        student_number_enabled   (bool) — detect student numbers; default false
        digit_count              (int)  — exact digit count for student numbers

    Returns JSON:
        anonymized_text   (str)
        entities          (list) — [{type, original, placeholder}, …]
        key_reference     (list) — deduplicated list when key_reference_enabled
        error             (str)  — present only on validation error
    """
    data = request.get_json(force=True, silent=True) or {}
    text: str = data.get("text", "")
    language: str = data.get("language", "en")
    hashing_enabled: bool = bool(data.get("hashing_enabled", False))
    secret: str = data.get("secret", "")
    key_reference_enabled: bool = bool(data.get("key_reference_enabled", False))
    anonymize_dates: bool = bool(data.get("anonymize_dates", False))
    student_number_enabled: bool = bool(data.get("student_number_enabled", False))
    try:
        digit_count = int(data.get("digit_count", 7))
    except (ValueError, TypeError):
        digit_count = 7

    if not text.strip():
        return jsonify({"anonymized_text": "", "entities": [], "key_reference": []})

    if language not in _SUPPORTED_LANGUAGES:
        language = "en"

    if hashing_enabled and not secret.strip():
        return jsonify({"error": "Enter a secret phrase to use hashing."}), 400

    entities_to_detect = _build_entity_list(anonymize_dates, student_number_enabled)

    ad_hoc = []
    if student_number_enabled:
        config = PatternConfig(digit_count=digit_count)
        ad_hoc = [build_student_number_recognizer(config, language)]

    result = current_app.anonymizer.anonymize(
        text, language, entities=entities_to_detect, ad_hoc_recognizers=ad_hoc
    )

    anonymized = result.anonymized_text

    hash_replacements: dict[str, str] = {}
    if hashing_enabled:
        encoder = HashEncoder(secret)
        for entity in result.entities:
            if entity.entity_type == "PERSON" and entity.placeholder not in hash_replacements:
                hash_replacements[entity.placeholder] = encoder.encode_full_name(
                    entity.original_text
                )
        if hash_replacements:
            pattern = re.compile(
                "|".join(
                    re.escape(k)
                    for k in sorted(hash_replacements, key=len, reverse=True)
                )
            )
            anonymized = pattern.sub(lambda m: hash_replacements[m.group()], anonymized)

    entities_out = []
    for entity in result.entities:
        placeholder = hash_replacements.get(entity.placeholder, entity.placeholder)
        entities_out.append({
            "type": entity.entity_type,
            "original": entity.original_text,
            "placeholder": placeholder,
        })

    # Persist settings
    settings = current_app.user_settings
    settings.language = language
    settings.hashing_enabled = hashing_enabled
    settings.anonymize_dates = anonymize_dates
    if hashing_enabled and secret.strip():
        settings.hashing_secret = secret
    settings.pattern_config = PatternConfig(
        digit_count=digit_count,
        student_number_enabled=student_number_enabled,
    )
    settings.save()

    key_reference = []
    if key_reference_enabled:
        seen: set[tuple[str, str]] = set()
        for entry in entities_out:
            key = (entry["placeholder"], entry["original"])
            if key not in seen and entry["placeholder"] in anonymized:
                key_reference.append(entry)
                seen.add(key)

    return jsonify({
        "anonymized_text": anonymized,
        "entities": entities_out,
        "key_reference": key_reference,
    })


def _render_text_mode():
    """Render text_mode.html with current UserSettings restored from disk."""
    settings = current_app.user_settings
    return render_template(
        "text_mode.html",
        active_mode="text",
        language=settings.language,
        hashing_enabled=settings.hashing_enabled,
        hashing_secret=settings.hashing_secret,
        anonymize_dates=settings.anonymize_dates,
        pattern_config=settings.pattern_config,
    )
