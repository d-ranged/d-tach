import re

from flask import Blueprint, current_app, jsonify, render_template, request

from app.routes import build_detection_summary
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

    Every detection setting is stored in Settings and shared by all modes, so a
    request only needs to carry the text and the per-run choices. Each field is
    still accepted per-request for API callers, but omitting one now inherits
    the saved value rather than silently disabling that detection.

    Expects JSON body:
        text                     (str)  — the text to anonymize
        language                 (str)  — 'en' or 'nl'; defaults to the saved language
        key_reference_enabled    (bool) — per-run; not saved
        hashing_enabled          (bool) — optional override of the saved setting
        secret                   (str)  — optional override of the saved secret
        anonymize_dates          (bool) — optional override
        anonymize_locations      (bool) — optional override
        anonymize_urls           (bool) — optional override
        numeric_id_enabled       (bool) — optional override
        digit_count              (int)  — optional override

    Returns JSON:
        anonymized_text   (str)
        entities          (list) — [{type, original, placeholder}, …]
        key_reference     (list) — deduplicated list when key_reference_enabled
        error             (str)  — present only on validation error
    """
    data = request.get_json(force=True, silent=True) or {}
    settings = current_app.user_settings
    saved_config = settings.pattern_config

    text: str = data.get("text", "")
    language: str = data.get("language", settings.language)
    hashing_enabled: bool = bool(data.get("hashing_enabled", settings.hashing_enabled))
    secret: str = data.get("secret", settings.hashing_secret)
    key_reference_enabled: bool = bool(data.get("key_reference_enabled", False))
    anonymize_dates: bool = bool(data.get("anonymize_dates", settings.anonymize_dates))
    anonymize_locations: bool = bool(
        data.get("anonymize_locations", settings.anonymize_locations)
    )
    anonymize_urls: bool = bool(data.get("anonymize_urls", settings.anonymize_urls))
    numeric_id_enabled: bool = bool(
        data.get("numeric_id_enabled", saved_config.numeric_id_enabled)
    )
    try:
        digit_count = int(data.get("digit_count", saved_config.digit_count))
    except (ValueError, TypeError):
        digit_count = saved_config.digit_count

    if not text.strip():
        return jsonify({"anonymized_text": "", "entities": [], "key_reference": []})

    if language not in _SUPPORTED_LANGUAGES:
        language = "en"

    if hashing_enabled and not secret.strip():
        return jsonify({"error": "Enter a secret phrase to use hashing."}), 400

    entities_to_detect = _build_entity_list(anonymize_dates, numeric_id_enabled, anonymize_urls, anonymize_locations)

    ad_hoc: list = []
    known_values = settings.known_values
    if known_values:
        ad_hoc.extend(build_known_value_recognizers(known_values, language))
    if numeric_id_enabled:
        config = PatternConfig(digit_count=digit_count)
        ad_hoc.append(build_numeric_id_recognizer(config, language))

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

    # Nothing is persisted here. Settings is the only writer: a run reads the
    # saved configuration and leaves it exactly as it found it, so one request
    # can never change what a later run in another mode does.
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
        detection_summary=build_detection_summary(settings),
        prefill_text=prefill_text,
    )
