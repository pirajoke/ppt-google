"""Lightweight language detection and deck copy helpers."""

from __future__ import annotations

import re

SUPPORTED_LANGUAGES = ("ru", "en", "fr")

STOPWORDS = {
    "ru": {
        "и", "в", "на", "что", "это", "как", "мы", "я", "ты", "они", "для", "у", "не", "но", "с", "по",
        "уже", "то", "когда", "есть", "будет", "или", "нужно", "сейчас",
    },
    "en": {
        "the", "and", "for", "with", "that", "this", "from", "have", "will", "next", "need", "project",
        "client", "meeting", "summary", "call", "is", "are", "we", "you", "they",
    },
    "fr": {
        "le", "la", "les", "des", "une", "pour", "avec", "dans", "sur", "que", "qui", "est", "nous",
        "vous", "ils", "elles", "projet", "appel", "résumé", "client", "suivi", "de", "du", "et",
    },
}

DECK_COPY = {
    "en": {
        "brand": "INSTANT PRESENTATION",
        "audience": "audience",
        "source_summary": "source summary",
        "date": "Date",
        "conversation_context": "Conversation Context",
        "key_direction": "Key Direction",
        "constraints": "Constraints",
        "follow_up": "Follow-up",
        "none_identified": "None identified.",
        "quote_fallback": "No quotes available.",
    },
    "ru": {
        "brand": "INSTANT PRESENTATION",
        "audience": "аудитория",
        "source_summary": "источник summary",
        "date": "Дата",
        "conversation_context": "Контекст разговора",
        "key_direction": "Ключевое направление",
        "constraints": "Ограничения",
        "follow_up": "Что делать дальше",
        "none_identified": "Ничего не выделено.",
        "quote_fallback": "Цитаты не выделены.",
    },
    "fr": {
        "brand": "INSTANT PRESENTATION",
        "audience": "audience",
        "source_summary": "source du résumé",
        "date": "Date",
        "conversation_context": "Contexte de l'échange",
        "key_direction": "Direction clé",
        "constraints": "Contraintes",
        "follow_up": "Suite",
        "none_identified": "Aucun élément identifié.",
        "quote_fallback": "Aucune citation disponible.",
    },
}

MEETING_TYPE_LABELS = {
    "en": {"research": "research", "business": "business", "trading": "trading", "lecture": "lecture", "ideas": "ideas", "social": "social"},
    "ru": {"research": "исследование", "business": "бизнес", "trading": "трейдинг", "lecture": "лекция", "ideas": "идеи", "social": "разговор"},
    "fr": {"research": "recherche", "business": "business", "trading": "trading", "lecture": "conférence", "ideas": "idées", "social": "conversation"},
}

DECK_MODE_LABELS = {
    "en": {
        "client-followup": "client-followup",
        "sales-recap": "sales recap",
        "research-insights": "research insights",
        "internal-decision": "internal decision",
    },
    "ru": {
        "client-followup": "follow-up",
        "sales-recap": "итоги для клиента",
        "research-insights": "research insights",
        "internal-decision": "внутреннее решение",
    },
    "fr": {
        "client-followup": "suivi client",
        "sales-recap": "récap commercial",
        "research-insights": "insights recherche",
        "internal-decision": "décision interne",
    },
}

AUDIENCE_LABELS = {
    "en": {
        "relationship_follow_up": "relationship follow-up",
        "client_stakeholder": "client stakeholder",
        "client_or_prospect": "client or prospect",
        "internal_product_or_strategy_team": "internal product or strategy team",
        "internal_decision_makers": "internal decision makers",
        "mixed_stakeholders": "mixed stakeholders",
    },
    "ru": {
        "relationship_follow_up": "отношенческий follow-up",
        "client_stakeholder": "клиентский стейкхолдер",
        "client_or_prospect": "клиент или потенциальный клиент",
        "internal_product_or_strategy_team": "внутренняя product/strategy команда",
        "internal_decision_makers": "внутренние decision makers",
        "mixed_stakeholders": "смешанная аудитория",
    },
    "fr": {
        "relationship_follow_up": "suivi relationnel",
        "client_stakeholder": "partie prenante côté client",
        "client_or_prospect": "client ou prospect",
        "internal_product_or_strategy_team": "équipe produit/stratégie interne",
        "internal_decision_makers": "décideurs internes",
        "mixed_stakeholders": "parties prenantes mixtes",
    },
}


def normalize_language(language: str | None) -> str:
    """Clamp the language to one of the supported deck languages."""
    lowered = (language or "").strip().lower()
    if lowered in SUPPORTED_LANGUAGES:
        return lowered
    return "en"


def detect_language(text: str) -> str:
    """Detect the dominant language among Russian, English, and French."""
    lowered = text.lower()
    cyrillic_hits = len(re.findall(r"[а-яё]", lowered))
    if cyrillic_hits >= 12:
        return "ru"

    words = re.findall(r"[a-zàâçéèêëîïôûùüÿñæœ]+", lowered)
    scores = {lang: 0 for lang in SUPPORTED_LANGUAGES}
    for word in words:
        for lang, stopwords in STOPWORDS.items():
            if word in stopwords:
                scores[lang] += 2
    scores["fr"] += len(re.findall(r"[àâçéèêëîïôûùüÿæœ]", lowered)) * 2
    scores["en"] += len(re.findall(r"\b(?:the|and|with|from|will|next|client|project)\b", lowered))
    scores["fr"] += len(re.findall(r"\b(?:le|la|les|des|avec|pour|client|projet|suivi)\b", lowered))

    best_lang = max(scores, key=scores.get)
    if scores[best_lang] > 0:
        return best_lang
    if re.search(r"[a-z]", lowered):
        return "en"
    return "ru" if cyrillic_hits else "en"


def detect_language_from_parts(*parts: str) -> str:
    """Detect language from multiple text sources."""
    return detect_language("\n".join(part for part in parts if part))


def deck_copy(language: str) -> dict[str, str]:
    """Return localized UI copy for deck rendering."""
    return DECK_COPY[normalize_language(language)]


def localize_meeting_type(meeting_type: str, language: str) -> str:
    """Translate the meeting type for deck UI."""
    lang = normalize_language(language)
    return MEETING_TYPE_LABELS[lang].get(meeting_type, meeting_type)


def localize_deck_mode(deck_mode: str, language: str) -> str:
    """Translate the deck mode for deck UI."""
    lang = normalize_language(language)
    return DECK_MODE_LABELS[lang].get(deck_mode, deck_mode)


def localize_audience(audience_key: str, language: str) -> str:
    """Translate the audience label for deck UI."""
    lang = normalize_language(language)
    return AUDIENCE_LABELS[lang].get(audience_key, audience_key.replace("_", " "))
