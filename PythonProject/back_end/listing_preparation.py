"""Подготовка объявлений недвижимости к последующему ранжированию.

Учебный MVP: числовые поля нормализуются детерминированно, признаки из текста
извлекаются осторожными правилами. Это не LLM и не заменяет проверку источника.
Неизвестное значение остаётся None, а не превращается в отрицательную оценку.
"""
from __future__ import annotations

import re
from typing import Any


def _number(value: Any) -> float | None:
    if value is None:
        return None
    if isinstance(value, (int, float)):
        return float(value)
    cleaned = str(value).replace("\xa0", " ").replace("₽", "").replace("м²", "")
    cleaned = cleaned.replace("руб.", "").replace("руб", "").replace(",", ".")
    match = re.search(r"\d+(?:\.\d+)?", cleaned.replace(" ", ""))
    return float(match.group()) if match else None


def _extract_floor(text: str) -> tuple[int | None, int | None]:
    match = re.search(r"(?:^|\D)(\d{1,2})\s*/\s*(\d{1,2})(?:\s*эт\.?|\D|$)", text, re.I)
    if not match:
        match = re.search(r"(\d{1,2})\s*/\s*(\d{1,2})\s*эт", text, re.I)
    return (int(match.group(1)), int(match.group(2))) if match else (None, None)


def analyze_description(description: str | None) -> dict[str, Any]:
    """Извлекает только явные текстовые свидетельства о состоянии и планировке."""
    text = (description or "").lower()
    condition = None
    condition_evidence = None
    condition_confidence = 0.0
    patterns = [
        (r"без ремонта|требует ремонта|под ремонт", "needs_renovation", "явно указано, что требуется ремонт", 0.90),
        (r"евроремонт|дизайнерский ремонт|свежий ремонт|после ремонта", "renovated", "в описании прямо упомянут ремонт", 0.85),
        (r"косметическ\w* ремонт", "cosmetic_renovation", "упомянут косметический ремонт", 0.85),
        (r"под ключ", "turnkey_option_mentioned", "упомянута возможность покупки/отделки под ключ; готовое состояние не подтверждено", 0.55),
    ]
    for pattern, value, evidence, confidence in patterns:
        if re.search(pattern, text):
            condition, condition_evidence, condition_confidence = value, evidence, confidence
            break

    layout = None
    layout_evidence = None
    layout_confidence = 0.0
    if re.search(r"эргономичн\w* планировк|современн\w* планировк", text):
        layout, layout_evidence, layout_confidence = "described_as_modern", "объявление называет планировку современной/эргономичной", 0.65
    elif re.search(r"свободн\w* планировк", text):
        layout, layout_evidence, layout_confidence = "free_layout", "упомянута свободная планировка", 0.85

    return {
        "apartment_condition": {"value": condition, "confidence": condition_confidence, "evidence": condition_evidence},
        "layout": {"value": layout, "confidence": layout_confidence, "evidence": layout_evidence},
    }


def prepare_listing(raw: dict[str, Any], default_city: str | None = None) -> dict[str, Any]:
    """Приводит одно объявление к общей схеме; исходный текст сохраняется."""
    title = str(raw.get("title") or "").strip()
    description = str(raw.get("description") or "").strip()
    combined = " ".join((title, description, str(raw.get("details") or "")))

    price = _number(raw.get("price"))
    area = _number(raw.get("area"))
    price_per_sqm = _number(raw.get("price_per_sqm"))
    if price_per_sqm is None and price and area and area > 0:
        price_per_sqm = round(price / area, 2)

    rooms = raw.get("rooms")
    if rooms is None:
        m = re.search(r"(\d+)\s*[-– ]?к(?:омн)?\.?\s*квартир", combined, re.I)
        rooms = int(m.group(1)) if m else None

    floor, total_floors = _extract_floor(combined)
    floor = raw.get("floor", floor)
    total_floors = raw.get("total_floors", total_floors)

    text_features = analyze_description(description)
    # Явно переданные структурированные данные имеют приоритет над эвристикой.
    for key in ("apartment_condition", "layout"):
        if raw.get(key) is not None:
            text_features[key] = {"value": raw[key], "confidence": 1.0, "evidence": "поле передано источником"}

    city = raw.get("city") or default_city
    conflicts = []
    if floor is not None and re.search(r"на первом этаже|1[- ]м этаже", description, re.I) and int(floor) != 1:
        conflicts.append("Этаж в характеристиках не совпадает с текстом описания")
    return {
        "id": raw.get("id"),
        "title": title or "Объявление без заголовка",
        "city": city,
        "price": price,
        "area": area,
        "price_per_sqm": price_per_sqm,
        "rooms": int(rooms) if rooms is not None else None,
        "floor": int(floor) if floor is not None else None,
        "total_floors": int(total_floors) if total_floors is not None else None,
        "address": raw.get("address"),
        "description": description,
        "features": text_features,
        "source_url": raw.get("source_url"),
        "data_quality": {
            "has_price": price is not None,
            "has_area": area is not None,
            "has_address": bool(raw.get("address")),
            "has_description": bool(description),
            "conflicts": conflicts,
        },
    }


def prepare_search_listings(raw_listings: list[dict[str, Any]], city: str) -> list[dict[str, Any]]:
    """Готовит объявления в рамках одного населённого пункта.

    Если у объявления явно указан другой город, оно отклоняется: нельзя смешивать
    цены и локации разных населённых пунктов в одном рейтинге.
    """
    prepared = []
    target = city.strip().casefold()
    for raw in raw_listings:
        item_city = str(raw.get("city") or city).strip()
        if item_city.casefold() != target:
            continue
        prepared.append(prepare_listing(raw, default_city=city))
    return prepared
