"""Universo de mercados de la Microsoft Store (243, segun el campo Markets de la API).

`MARKETS` es la lista canonica. `locale_for` devuelve un locale valido para el
parametro `languages` de displaycatalog; el precio depende del MERCADO, no del
idioma, asi que 'en-US' es un fallback seguro para cualquier mercado.
"""

# 243 mercados (se descarta el centinela 'NEUTRAL').
MARKETS = [
    "US", "DZ", "AR", "AU", "AT", "BH", "BD", "BE", "BR", "BG", "CA", "CL", "CN", "CO", "CR", "HR",
    "CY", "CZ", "DK", "EG", "EE", "FI", "FR", "DE", "GR", "GT", "HK", "HU", "IS", "IN", "ID", "IQ",
    "IE", "IL", "IT", "JP", "JO", "KZ", "KE", "KW", "LV", "LB", "LI", "LT", "LU", "MY", "MT", "MR",
    "MX", "MA", "NL", "NZ", "NG", "NO", "OM", "PK", "PE", "PH", "PL", "PT", "QA", "RO", "RU", "SA",
    "RS", "SG", "SK", "SI", "ZA", "KR", "ES", "SE", "CH", "TW", "TH", "TT", "TN", "TR", "UA", "AE",
    "GB", "VN", "YE", "LY", "LK", "UY", "VE", "AF", "AX", "AL", "AS", "AO", "AI", "AQ", "AG", "AM",
    "AW", "BO", "BQ", "BA", "BW", "BV", "IO", "BN", "BF", "BI", "KH", "CM", "CV", "KY", "CF", "TD",
    "TL", "DJ", "DM", "DO", "EC", "SV", "GQ", "ER", "ET", "FK", "FO", "FJ", "GF", "PF", "TF", "GA",
    "GM", "GE", "GH", "GI", "GL", "GD", "GP", "GU", "GG", "GN", "GW", "GY", "HT", "HM", "HN", "AZ",
    "BS", "BB", "BY", "BZ", "BJ", "BM", "BT", "KM", "CG", "CD", "CK", "CX", "CC", "CI", "CW", "JM",
    "SJ", "JE", "KI", "KG", "LA", "LS", "LR", "MO", "MK", "MG", "MW", "IM", "MH", "MQ", "MU", "YT",
    "FM", "MD", "MN", "MS", "MZ", "MM", "NA", "NR", "NP", "MV", "ML", "NC", "NI", "NE", "NU", "NF",
    "PW", "PS", "PA", "PG", "PY", "RE", "RW", "BL", "MF", "WS", "ST", "SN", "MP", "PN", "SX", "SB",
    "SO", "SC", "SL", "GS", "SH", "KN", "LC", "PM", "VC", "TJ", "TZ", "TG", "TK", "TO", "TM", "TC",
    "TV", "UM", "UG", "VI", "VG", "WF", "EH", "ZM", "ZW", "UZ", "VU", "SR", "SZ", "AD", "MC", "SM",
    "ME", "VA",
]

# Locale principal por mercado (solo los mas relevantes; el resto usa el fallback).
_LOCALE = {
    "US": "en-US", "GB": "en-GB", "CA": "en-CA", "AU": "en-AU", "NZ": "en-NZ", "IE": "en-IE",
    "AR": "es-AR", "MX": "es-MX", "ES": "es-ES", "CL": "es-CL", "CO": "es-CO", "PE": "es-PE",
    "BR": "pt-BR", "PT": "pt-PT", "FR": "fr-FR", "DE": "de-DE", "IT": "it-IT", "NL": "nl-NL",
    "PL": "pl-PL", "RU": "ru-RU", "TR": "tr-TR", "JP": "ja-JP", "KR": "ko-KR", "CN": "zh-CN",
    "TW": "zh-TW", "HK": "zh-HK", "TH": "th-TH", "VN": "vi-VN", "ID": "id-ID", "IN": "en-IN",
    "ZA": "en-ZA", "NG": "en-NG", "SA": "ar-SA", "AE": "en-AE", "EG": "ar-EG", "IL": "he-IL",
    "UA": "uk-UA", "SE": "sv-SE", "NO": "nb-NO", "DK": "da-DK", "FI": "fi-FI", "CZ": "cs-CZ",
}

DEFAULT_LOCALE = "en-US"


def locale_for(market: str) -> str:
    return _LOCALE.get((market or "").upper(), DEFAULT_LOCALE)
