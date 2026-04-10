import re

from flask import Blueprint, current_app, jsonify, render_template, request

from app.services.hash_encoder import HashEncoder

bp = Blueprint("text", __name__)


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
        text                 (str)  — the text to anonymize
        hashing_enabled      (bool) — whether to apply hash encoding to names
        secret               (str)  — required when hashing_enabled is true
        key_reference_enabled (bool) — whether to include a key reference in the response

    Returns JSON:
        anonymized_text   (str)
        detected_language (str)  — 'en' or 'nl'
        entities          (list) — [{type, original, placeholder}, …]
        key_reference     (list) — deduplicated entity list when key_reference_enabled
        error             (str)  — present only when a validation error occurs
    """
    data = request.get_json(force=True, silent=True) or {}
    text: str = data.get("text", "")
    hashing_enabled: bool = bool(data.get("hashing_enabled", False))
    secret: str = data.get("secret", "")
    key_reference_enabled: bool = bool(data.get("key_reference_enabled", False))

    if not text.strip():
        return jsonify({"anonymized_text": "", "entities": [], "key_reference": [],
                        "detected_language": "en"})

    if hashing_enabled and not secret.strip():
        return jsonify({"error": "Enter a secret phrase to use hashing."}), 400

    language: str = current_app.language_detector.detect(text)
    result = current_app.anonymizer.anonymize(text, language)

    anonymized = result.anonymized_text

    # Build placeholder → hashed-name map for PERSON entities when hashing is on
    hash_replacements: dict[str, str] = {}
    if hashing_enabled:
        encoder = HashEncoder(secret)
        for entity in result.entities:
            if entity.entity_type == "PERSON" and entity.placeholder not in hash_replacements:
                hash_replacements[entity.placeholder] = encoder.encode_full_name(
                    entity.original_text
                )
        if hash_replacements:
            # Replace all at once; sort by length descending to avoid partial matches
            pattern = re.compile(
                "|".join(
                    re.escape(k)
                    for k in sorted(hash_replacements, key=len, reverse=True)
                )
            )
            anonymized = pattern.sub(lambda m: hash_replacements[m.group()], anonymized)

    # Build entities output list with final placeholders
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
    settings.hashing_enabled = hashing_enabled
    if hashing_enabled and secret.strip():
        settings.hashing_secret = secret
    settings.save()

    # Deduplicate key reference; only include placeholders present in the final text
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
        "detected_language": language,
        "entities": entities_out,
        "key_reference": key_reference,
    })


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

def _render_text_mode():
    """Render text_mode.html with current UserSettings restored from disk."""
    settings = current_app.user_settings
    return render_template(
        "text_mode.html",
        active_mode="text",
        hashing_enabled=settings.hashing_enabled,
        hashing_secret=settings.hashing_secret,
    )
