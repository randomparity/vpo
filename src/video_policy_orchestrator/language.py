"""Language code normalization and comparison utilities.

This module provides standardized handling of ISO 639 language codes throughout VPO.
It supports conversion between:
- ISO 639-1 (2-letter codes like "en", "de", "ja")
- ISO 639-2/B (3-letter bibliographic codes like "eng", "ger", "jpn")
- ISO 639-2/T (3-letter terminological codes like "eng", "deu", "jpn")

The default standard is ISO 639-2/B, which is used by MKV containers and FFmpeg.
"""

import logging
from typing import Literal

logger = logging.getLogger(__name__)

# Type alias for supported ISO standards
ISOStandard = Literal["639-1", "639-2/B", "639-2/T"]

# Default standard used throughout VPO
DEFAULT_STANDARD: ISOStandard = "639-2/B"

# ISO 639-1 (2-letter) to ISO 639-2/B (3-letter bibliographic) mapping
# This covers the most common languages in video files
_ISO_639_1_TO_639_2B: dict[str, str] = {
    "aa": "aar",  # Afar
    "ab": "abk",  # Abkhazian
    "af": "afr",  # Afrikaans
    "am": "amh",  # Amharic
    "ar": "ara",  # Arabic
    "as": "asm",  # Assamese
    "ay": "aym",  # Aymara
    "az": "aze",  # Azerbaijani
    "ba": "bak",  # Bashkir
    "be": "bel",  # Belarusian
    "bg": "bul",  # Bulgarian
    "bh": "bih",  # Bihari
    "bi": "bis",  # Bislama
    "bn": "ben",  # Bengali
    "bo": "tib",  # Tibetan (bibliographic)
    "br": "bre",  # Breton
    "ca": "cat",  # Catalan
    "co": "cos",  # Corsican
    "cs": "cze",  # Czech (bibliographic)
    "cy": "wel",  # Welsh (bibliographic)
    "da": "dan",  # Danish
    "de": "ger",  # German (bibliographic)
    "dz": "dzo",  # Dzongkha
    "el": "gre",  # Greek (bibliographic)
    "en": "eng",  # English
    "eo": "epo",  # Esperanto
    "es": "spa",  # Spanish
    "et": "est",  # Estonian
    "eu": "baq",  # Basque (bibliographic)
    "fa": "per",  # Persian (bibliographic)
    "fi": "fin",  # Finnish
    "fj": "fij",  # Fijian
    "fo": "fao",  # Faroese
    "fr": "fre",  # French (bibliographic)
    "fy": "fry",  # Western Frisian
    "ga": "gle",  # Irish
    "gd": "gla",  # Scottish Gaelic
    "gl": "glg",  # Galician
    "gn": "grn",  # Guarani
    "gu": "guj",  # Gujarati
    "ha": "hau",  # Hausa
    "he": "heb",  # Hebrew
    "hi": "hin",  # Hindi
    "hr": "hrv",  # Croatian
    "hu": "hun",  # Hungarian
    "hy": "arm",  # Armenian (bibliographic)
    "ia": "ina",  # Interlingua
    "id": "ind",  # Indonesian
    "ie": "ile",  # Interlingue
    "ik": "ipk",  # Inupiaq
    "is": "ice",  # Icelandic (bibliographic)
    "it": "ita",  # Italian
    "iu": "iku",  # Inuktitut
    "ja": "jpn",  # Japanese
    "jv": "jav",  # Javanese
    "ka": "geo",  # Georgian (bibliographic)
    "kk": "kaz",  # Kazakh
    "kl": "kal",  # Kalaallisut
    "km": "khm",  # Khmer
    "kn": "kan",  # Kannada
    "ko": "kor",  # Korean
    "ks": "kas",  # Kashmiri
    "ku": "kur",  # Kurdish
    "ky": "kir",  # Kyrgyz
    "la": "lat",  # Latin
    "ln": "lin",  # Lingala
    "lo": "lao",  # Lao
    "lt": "lit",  # Lithuanian
    "lv": "lav",  # Latvian
    "mg": "mlg",  # Malagasy
    "mi": "mao",  # Maori (bibliographic)
    "mk": "mac",  # Macedonian (bibliographic)
    "ml": "mal",  # Malayalam
    "mn": "mon",  # Mongolian
    "mr": "mar",  # Marathi
    "ms": "may",  # Malay (bibliographic)
    "mt": "mlt",  # Maltese
    "my": "bur",  # Burmese (bibliographic)
    "na": "nau",  # Nauru
    "ne": "nep",  # Nepali
    "nl": "dut",  # Dutch (bibliographic)
    "no": "nor",  # Norwegian
    "oc": "oci",  # Occitan
    "om": "orm",  # Oromo
    "or": "ori",  # Oriya
    "pa": "pan",  # Punjabi
    "pl": "pol",  # Polish
    "ps": "pus",  # Pashto
    "pt": "por",  # Portuguese
    "qu": "que",  # Quechua
    "rm": "roh",  # Romansh
    "rn": "run",  # Rundi
    "ro": "rum",  # Romanian (bibliographic)
    "ru": "rus",  # Russian
    "rw": "kin",  # Kinyarwanda
    "sa": "san",  # Sanskrit
    "sd": "snd",  # Sindhi
    "se": "sme",  # Northern Sami
    "sg": "sag",  # Sango
    "si": "sin",  # Sinhala
    "sk": "slo",  # Slovak (bibliographic)
    "sl": "slv",  # Slovenian
    "sm": "smo",  # Samoan
    "sn": "sna",  # Shona
    "so": "som",  # Somali
    "sq": "alb",  # Albanian (bibliographic)
    "sr": "srp",  # Serbian
    "ss": "ssw",  # Swati
    "st": "sot",  # Southern Sotho
    "su": "sun",  # Sundanese
    "sv": "swe",  # Swedish
    "sw": "swa",  # Swahili
    "ta": "tam",  # Tamil
    "te": "tel",  # Telugu
    "tg": "tgk",  # Tajik
    "th": "tha",  # Thai
    "ti": "tir",  # Tigrinya
    "tk": "tuk",  # Turkmen
    "tl": "tgl",  # Tagalog
    "tn": "tsn",  # Tswana
    "to": "ton",  # Tonga
    "tr": "tur",  # Turkish
    "ts": "tso",  # Tsonga
    "tt": "tat",  # Tatar
    "tw": "twi",  # Twi
    "ug": "uig",  # Uyghur
    "uk": "ukr",  # Ukrainian
    "ur": "urd",  # Urdu
    "uz": "uzb",  # Uzbek
    "vi": "vie",  # Vietnamese
    "vo": "vol",  # Volapük
    "wo": "wol",  # Wolof
    "xh": "xho",  # Xhosa
    "yi": "yid",  # Yiddish
    "yo": "yor",  # Yoruba
    "za": "zha",  # Zhuang
    "zh": "chi",  # Chinese (bibliographic)
    "zu": "zul",  # Zulu
}

# ISO 639-2/T (terminological) to ISO 639-2/B (bibliographic) mapping
# These are the languages where the codes differ
_ISO_639_2T_TO_639_2B: dict[str, str] = {
    "bod": "tib",  # Tibetan
    "ces": "cze",  # Czech
    "cym": "wel",  # Welsh
    "deu": "ger",  # German
    "ell": "gre",  # Greek
    "eus": "baq",  # Basque
    "fas": "per",  # Persian
    "fra": "fre",  # French
    "hye": "arm",  # Armenian
    "isl": "ice",  # Icelandic
    "kat": "geo",  # Georgian
    "mkd": "mac",  # Macedonian
    "mri": "mao",  # Maori
    "msa": "may",  # Malay
    "mya": "bur",  # Burmese
    "nld": "dut",  # Dutch
    "ron": "rum",  # Romanian
    "slk": "slo",  # Slovak
    "sqi": "alb",  # Albanian
    "zho": "chi",  # Chinese
}

# Reverse mappings (generated from forward mappings)
_ISO_639_2B_TO_639_1: dict[str, str] = {v: k for k, v in _ISO_639_1_TO_639_2B.items()}
_ISO_639_2B_TO_639_2T: dict[str, str] = {v: k for k, v in _ISO_639_2T_TO_639_2B.items()}

# Language names (lowercase) to ISO 639-2/B codes
# Used for converting full language names from external APIs (Radarr/Sonarr)
_LANGUAGE_NAME_TO_639_2B: dict[str, str] = {
    "afar": "aar",
    "abkhazian": "abk",
    "afrikaans": "afr",
    "albanian": "alb",
    "amharic": "amh",
    "arabic": "ara",
    "armenian": "arm",
    "assamese": "asm",
    "aymara": "aym",
    "azerbaijani": "aze",
    "bashkir": "bak",
    "basque": "baq",
    "belarusian": "bel",
    "bengali": "ben",
    "bihari": "bih",
    "bislama": "bis",
    "breton": "bre",
    "bulgarian": "bul",
    "burmese": "bur",
    "catalan": "cat",
    "chinese": "chi",
    "corsican": "cos",
    "czech": "cze",
    "danish": "dan",
    "dutch": "dut",
    "dzongkha": "dzo",
    "english": "eng",
    "esperanto": "epo",
    "estonian": "est",
    "faroese": "fao",
    "fijian": "fij",
    "finnish": "fin",
    "french": "fre",
    "western frisian": "fry",
    "galician": "glg",
    "georgian": "geo",
    "german": "ger",
    "greek": "gre",
    "guarani": "grn",
    "gujarati": "guj",
    "hausa": "hau",
    "hebrew": "heb",
    "hindi": "hin",
    "hungarian": "hun",
    "icelandic": "ice",
    "indonesian": "ind",
    "interlingua": "ina",
    "interlingue": "ile",
    "inuktitut": "iku",
    "inupiaq": "ipk",
    "irish": "gle",
    "italian": "ita",
    "japanese": "jpn",
    "javanese": "jav",
    "kalaallisut": "kal",
    "kannada": "kan",
    "kashmiri": "kas",
    "kazakh": "kaz",
    "khmer": "khm",
    "kinyarwanda": "kin",
    "kyrgyz": "kir",
    "korean": "kor",
    "kurdish": "kur",
    "lao": "lao",
    "latin": "lat",
    "latvian": "lav",
    "lingala": "lin",
    "lithuanian": "lit",
    "macedonian": "mac",
    "malagasy": "mlg",
    "malay": "may",
    "malayalam": "mal",
    "maltese": "mlt",
    "maori": "mao",
    "marathi": "mar",
    "mongolian": "mon",
    "nauru": "nau",
    "nepali": "nep",
    "norwegian": "nor",
    "occitan": "oci",
    "oriya": "ori",
    "oromo": "orm",
    "pashto": "pus",
    "persian": "per",
    "polish": "pol",
    "portuguese": "por",
    "punjabi": "pan",
    "quechua": "que",
    "romansh": "roh",
    "romanian": "rum",
    "rundi": "run",
    "russian": "rus",
    "samoan": "smo",
    "sango": "sag",
    "sanskrit": "san",
    "scottish gaelic": "gla",
    "serbian": "srp",
    "shona": "sna",
    "sindhi": "snd",
    "sinhala": "sin",
    "slovak": "slo",
    "slovenian": "slv",
    "somali": "som",
    "southern sotho": "sot",
    "spanish": "spa",
    "sundanese": "sun",
    "swahili": "swa",
    "swati": "ssw",
    "swedish": "swe",
    "tagalog": "tgl",
    "tajik": "tgk",
    "tamil": "tam",
    "tatar": "tat",
    "telugu": "tel",
    "thai": "tha",
    "tibetan": "tib",
    "tigrinya": "tir",
    "tonga": "ton",
    "tsonga": "tso",
    "tswana": "tsn",
    "turkish": "tur",
    "turkmen": "tuk",
    "twi": "twi",
    "uyghur": "uig",
    "ukrainian": "ukr",
    "urdu": "urd",
    "uzbek": "uzb",
    "vietnamese": "vie",
    "volapük": "vol",
    "welsh": "wel",
    "wolof": "wol",
    "xhosa": "xho",
    "yiddish": "yid",
    "yoruba": "yor",
    "zhuang": "zha",
    "zulu": "zul",
}

# All valid ISO 639-2/B codes (3-letter)
_VALID_639_2B: set[str] = set(_ISO_639_2B_TO_639_1.keys()) | {
    "und",
    "mis",
    "mul",
    "zxx",
}


def language_name_to_code(name: str | None) -> str | None:
    """Convert a language name to ISO 639-2/B code.

    This function is useful for converting full language names from external
    APIs (like Radarr/Sonarr) to ISO 639-2/B codes used by VPO.

    Args:
        name: Full language name (e.g., "English", "Japanese").
              Case-insensitive.

    Returns:
        ISO 639-2/B code if recognized, None otherwise.

    Examples:
        >>> language_name_to_code("English")
        'eng'
        >>> language_name_to_code("Japanese")
        'jpn'
        >>> language_name_to_code("Unknown Language")
        None
    """
    if not name:
        return None
    return _LANGUAGE_NAME_TO_639_2B.get(name.lower().strip())


def normalize_language(
    code: str | None,
    target: ISOStandard = DEFAULT_STANDARD,
    warn_on_conversion: bool = True,
) -> str:
    """Normalize a language code to the target ISO standard.

    Args:
        code: Language code to normalize (ISO 639-1, 639-2/B, or 639-2/T).
              Also accepts full language names (e.g., "English", "Japanese").
              If None or empty, returns "und" (undefined).
        target: Target ISO standard ("639-1", "639-2/B", or "639-2/T").
        warn_on_conversion: Log a warning when converting between standards.

    Returns:
        Normalized language code in the target standard.
        Returns "und" for undefined/empty input or unrecognized codes.

    Examples:
        >>> normalize_language("de")  # ISO 639-1 to 639-2/B
        'ger'
        >>> normalize_language("deu")  # ISO 639-2/T to 639-2/B
        'ger'
        >>> normalize_language("ger")  # Already 639-2/B
        'ger'
        >>> normalize_language("eng", target="639-1")
        'en'
        >>> normalize_language("English")  # Full language name
        'eng'
    """
    # Handle None/empty
    if not code:
        return "und"

    code = code.lower().strip()

    # Handle special codes that are the same across standards
    if code in ("und", "mis", "mul", "zxx"):
        if target == "639-1":
            # These don't have 639-1 equivalents, return as-is
            return code
        return code

    # Determine input format based on length
    if len(code) == 2:
        # ISO 639-1 input
        return _convert_from_639_1(code, target, warn_on_conversion)
    elif len(code) == 3:
        # ISO 639-2 input (B or T)
        return _convert_from_639_2(code, target, warn_on_conversion)
    else:
        # Might be a full language name (e.g., "English" from Radarr/Sonarr APIs)
        converted = _LANGUAGE_NAME_TO_639_2B.get(code)
        if converted:
            if warn_on_conversion:
                logger.debug(
                    "Converted language name '%s' to '%s' (ISO 639-2/B)",
                    code,
                    converted,
                )
            # Now convert to target standard if needed
            if target == "639-2/B":
                return converted
            elif target == "639-2/T":
                return _ISO_639_2B_TO_639_2T.get(converted, converted)
            elif target == "639-1":
                return _ISO_639_2B_TO_639_1.get(converted, converted)
            return converted

        # Unrecognized format
        if warn_on_conversion:
            logger.warning(
                "Unrecognized language code format '%s', using 'und'",
                code,
            )
        return "und"


def _convert_from_639_1(
    code: str,
    target: ISOStandard,
    warn: bool,
) -> str:
    """Convert from ISO 639-1 to target standard."""
    if target == "639-1":
        # Validate it's a known 639-1 code
        if code in _ISO_639_1_TO_639_2B:
            return code
        if warn:
            logger.warning(
                "Unknown ISO 639-1 code '%s', using 'und'",
                code,
            )
        return "und"

    # Convert to 639-2/B first
    if code not in _ISO_639_1_TO_639_2B:
        if warn:
            logger.warning(
                "Unknown ISO 639-1 code '%s', using 'und'",
                code,
            )
        return "und"

    code_2b = _ISO_639_1_TO_639_2B[code]

    if warn:
        logger.debug(
            "Converted language code '%s' (ISO 639-1) to '%s' (ISO 639-2/B)",
            code,
            code_2b,
        )

    if target == "639-2/B":
        return code_2b
    elif target == "639-2/T":
        return _ISO_639_2B_TO_639_2T.get(code_2b, code_2b)

    return code_2b


def _convert_from_639_2(
    code: str,
    target: ISOStandard,
    warn: bool,
) -> str:
    """Convert from ISO 639-2 (B or T) to target standard."""
    # First, normalize to 639-2/B
    if code in _ISO_639_2T_TO_639_2B:
        # Input is 639-2/T, convert to 639-2/B
        code_2b = _ISO_639_2T_TO_639_2B[code]
        if warn:
            logger.debug(
                "Converted language code '%s' (ISO 639-2/T) to '%s' (ISO 639-2/B)",
                code,
                code_2b,
            )
    elif code in _VALID_639_2B or code in _ISO_639_2B_TO_639_1:
        # Input is already 639-2/B
        code_2b = code
    else:
        # Unknown 3-letter code - might be valid but not in our mapping
        # Keep it but warn
        if warn:
            logger.warning(
                "Unknown ISO 639-2 code '%s', keeping as-is",
                code,
            )
        code_2b = code

    # Convert to target standard
    if target == "639-2/B":
        return code_2b
    elif target == "639-2/T":
        return _ISO_639_2B_TO_639_2T.get(code_2b, code_2b)
    elif target == "639-1":
        if code_2b in _ISO_639_2B_TO_639_1:
            return _ISO_639_2B_TO_639_1[code_2b]
        # No 639-1 equivalent
        if warn:
            logger.warning(
                "No ISO 639-1 equivalent for '%s', keeping as '%s'",
                code_2b,
                code_2b,
            )
        return code_2b

    return code_2b


def languages_match(code1: str | None, code2: str | None) -> bool:
    """Check if two language codes represent the same language.

    This comparison is standard-agnostic: "de", "ger", and "deu" all match.

    Args:
        code1: First language code (any ISO 639 format).
        code2: Second language code (any ISO 639 format).

    Returns:
        True if both codes represent the same language.

    Examples:
        >>> languages_match("de", "ger")
        True
        >>> languages_match("deu", "ger")
        True
        >>> languages_match("en", "eng")
        True
        >>> languages_match("en", "de")
        False
    """
    # Normalize both to 639-2/B for comparison
    norm1 = normalize_language(code1, "639-2/B", warn_on_conversion=False)
    norm2 = normalize_language(code2, "639-2/B", warn_on_conversion=False)
    return norm1 == norm2


def get_language_name(code: str | None) -> str:
    """Get the English name for a language code.

    Args:
        code: Language code (any ISO 639 format).

    Returns:
        English name of the language, or the code itself if unknown.
    """
    if not code:
        return "Undefined"

    # Normalize to 639-2/B
    code_2b = normalize_language(code, "639-2/B", warn_on_conversion=False)

    # Map of 639-2/B codes to English names
    names: dict[str, str] = {
        "eng": "English",
        "ger": "German",
        "fre": "French",
        "spa": "Spanish",
        "ita": "Italian",
        "por": "Portuguese",
        "rus": "Russian",
        "jpn": "Japanese",
        "chi": "Chinese",
        "kor": "Korean",
        "ara": "Arabic",
        "hin": "Hindi",
        "ben": "Bengali",
        "vie": "Vietnamese",
        "tha": "Thai",
        "dut": "Dutch",
        "pol": "Polish",
        "tur": "Turkish",
        "ukr": "Ukrainian",
        "swe": "Swedish",
        "nor": "Norwegian",
        "dan": "Danish",
        "fin": "Finnish",
        "cze": "Czech",
        "hun": "Hungarian",
        "rum": "Romanian",
        "gre": "Greek",
        "heb": "Hebrew",
        "ind": "Indonesian",
        "may": "Malay",
        "tgl": "Tagalog",
        "und": "Undefined",
        "mis": "Miscellaneous",
        "mul": "Multiple",
        "zxx": "No linguistic content",
    }

    return names.get(code_2b, code_2b.upper())


def is_valid_language_code(code: str | None) -> bool:
    """Check if a code is a valid ISO 639 language code.

    Args:
        code: Language code to validate.

    Returns:
        True if the code is recognized as valid.
    """
    if not code:
        return False

    code = code.lower().strip()

    # Check 639-1
    if len(code) == 2 and code in _ISO_639_1_TO_639_2B:
        return True

    # Check 639-2/B
    if len(code) == 3 and (code in _VALID_639_2B or code in _ISO_639_2B_TO_639_1):
        return True

    # Check 639-2/T
    if len(code) == 3 and code in _ISO_639_2T_TO_639_2B:
        return True

    return False
