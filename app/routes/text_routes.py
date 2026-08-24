import re

from flask import Blueprint, current_app, jsonify, render_template, request

from app.services.anonymizer import (
    ENTITIES,
    LOCATION_ENTITY,
    NUMERIC_ID_ENTITY,
    URL_ENTITY,
    build_known_value_recognizers,
    build_numeric_id_recognizer,
)
from app.services.hash_encoder import HashEncoder, UNHASHABLE_ENTITIES
from app.services.language_detector import LanguageNotLoadedError
from app.services.pattern_config import PatternConfig

bp = Blueprint("text", __name__)

_SUPPORTED_LANGUAGES = ("en", "nl")


def _build_entity_list(
    anonymize_dates: bool,
    numeric_id_enabled: bool = False,
    anonymize_urls: bool = False,
    anonymize_locations: bool = False,
) -> list[str]:
    """Return entity list with opt-in entities included only when requested.

    DATE_TIME: excluded by default — ubiquitous in academic documents.
    LOCATION: excluded by default — city/country names often carry meaningful context.
    URL: excluded by default — overlaps with EMAIL_ADDRESS, causing garbled output.
    NUMERIC_ID: included only when numeric ID detection is enabled.
    """
    result = list(ENTITIES) if anonymize_dates else [e for e in ENTITIES if e != "DATE_TIME"]
    if anonymize_locations:
        result.append(LOCATION_ENTITY)
    if numeric_id_enabled:
        result.append(NUMERIC_ID_ENTITY)
    if anonymize_urls:
        result.append(URL_ENTITY)
    return result


@bp.route("/")
def index():
    """Redirect root to text mode."""
    return _render_text_mode()


@bp.route("/text")
def text_mode():
    """Render the Text Mode page.

    Accepts an optional ?q= query parameter to pre-fill the input textarea,
    so external tools (e.g. an OS keyboard shortcut sending clipboard text)
    can open d-tach with text already in place.
    """
    return _render_text_mode(prefill_text=request.args.get("q", ""))


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
        numeric_id_enabled   (bool) — detect student numbers; default false
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
    anonymize_locations: bool = bool(data.get("anonymize_locations", False))
    anonymize_urls: bool = bool(data.get("anonymize_urls", False))
    numeric_id_enabled: bool = bool(data.get("numeric_id_enabled", False))
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

    entities_to_detect = _build_entity_list(anonymize_dates, numeric_id_enabled, anonymize_urls, anonymize_locations)

    ad_hoc: list = []
    known_values = current_app.user_settings.known_values
    if known_values:
        ad_hoc.extend(build_known_value_recognizers(known_values, language))
    if numeric_id_enabled:
        config = PatternConfig(digit_count=digit_count)
        ad_hoc.append(build_numeric_id_recognizer(config, language))

    settings = current_app.user_settings
    try:
        current_app.language_detector.ensure_loaded(language, settings.loading_strategy)
    except LanguageNotLoadedError as exc:
        return jsonify({"error": str(exc)}), 400

    result = current_app.anonymizer.anonymize(
        text, language, entities=entities_to_detect, ad_hoc_recognizers=ad_hoc
    )

    anonymized = result.anonymized_text

    hash_replacements: dict[str, str] = {}
    if hashing_enabled:
        encoder = HashEncoder(secret)
        for entity in result.entities:
            if entity.placeholder in hash_replacements:
                continue
            if entity.entity_type == "PERSON":
                hash_replacements[entity.placeholder] = f"[{encoder.encode_full_name(entity.original_text)}]"
            elif entity.entity_type not in UNHASHABLE_ENTITIES:
                hashed = encoder.encode_entity(entity.entity_type, entity.original_text)
                if hashed:
                    hash_replacements[entity.placeholder] = hashed
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
    settings.anonymize_locations = anonymize_locations
    settings.anonymize_urls = anonymize_urls
    if hashing_enabled and secret.strip():
        settings.hashing_secret = secret
    settings.pattern_config = PatternConfig(
        digit_count=digit_count,
        numeric_id_enabled=numeric_id_enabled,
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


def _render_text_mode(prefill_text: str = ""):
    """Render text_mode.html with current UserSettings restored from disk."""
    settings = current_app.user_settings
    return render_template(
        "text_mode.html",
        active_mode="text",
        language=settings.language,
        hashing_enabled=settings.hashing_enabled,
        hashing_secret=settings.hashing_secret,
        anonymize_dates=settings.anonymize_dates,
        anonymize_locations=settings.anonymize_locations,
        anonymize_urls=settings.anonymize_urls,
        pattern_config=settings.pattern_config,
        prefill_text=prefill_text,
    )
