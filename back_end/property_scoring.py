"""Преобразование характеристик объявлений в оценки и ценовую аналитику.

Ценовой балл намеренно не рассчитывается, пока не откалибрована формула.
Рыночная стоимость оценивается только по объектам того же района.
"""
from __future__ import annotations

from statistics import median
from typing import Any

PRICE_WARNING_THRESHOLD = 40.0
AREA_FULL_SCORE_TOLERANCE = 5.0
AREA_POINTS_PER_EXTRA_SQM = 5.0


def filter_by_budget(properties: list[dict[str, Any]], budget: dict[str, Any] | None) -> tuple[list[dict[str, Any]], int]:
    """Режим max_price ИЛИ price_range; пустой режим не фильтрует."""
    budget = budget or {}
    mode = budget.get("mode", "none")
    minimum = _positive_number(budget.get("min_price"))
    maximum = _positive_number(budget.get("max_price"))
    if mode == "max_price":
        if maximum is None:
            raise ValueError("Для режима max_price укажите max_price.")
        lower, upper = None, maximum
    elif mode == "price_range":
        if minimum is None or maximum is None or minimum > maximum:
            raise ValueError("Для price_range укажите корректные min_price и max_price.")
        lower, upper = minimum, maximum
    elif mode == "min_price":
        if minimum is None:
            raise ValueError("Для режима min_price укажите min_price.")
        lower, upper = minimum, None
    elif mode == "none":
        lower, upper = None, None
    else:
        raise ValueError("budget.mode должен быть none, min_price, max_price или price_range.")

    kept = []
    for item in properties:
        price = _positive_number(item.get("price"))
        if price is None:
            # Неизвестную цену нельзя достоверно проверить по бюджету.
            continue
        if lower is not None and price < lower:
            continue
        if upper is not None and price > upper:
            continue
        kept.append(item)
    return kept, len(properties) - len(kept)


def area_score(actual_area: Any, target_area: Any) -> float | None:
    actual, target = _positive_number(actual_area), _positive_number(target_area)
    if actual is None or target is None:
        return None
    deviation_outside_band = max(0.0, abs(actual - target) - AREA_FULL_SCORE_TOLERANCE)
    return round(max(0.0, 100.0 - deviation_outside_band * AREA_POINTS_PER_EXTRA_SQM), 1)


def proximity_score(minutes_or_km: Any, *, unit: str) -> float | None:
    """Временная стартовая шкала, вынесенная отдельно для последующей калибровки."""
    value = _positive_number(minutes_or_km)
    if value is None:
        return None
    # Линейная шкала MVP: 0 = 100, 30 минут / 10 км = 0.
    limit = 30.0 if unit == "minutes" else 10.0 if unit == "km" else None
    if limit is None:
        raise ValueError("unit должен быть minutes или km.")
    return round(max(0.0, min(100.0, 100.0 * (1.0 - value / limit))), 1)


def building_condition_score(value: Any) -> float | None:
    if not isinstance(value, str):
        return None
    normalized = value.strip().casefold()
    scores = {
        "отличное": 100.0,
        "после капитального ремонта": 95.0,
        "хорошее": 80.0,
        "удовлетворительное": 55.0,
        "требует косметического ремонта": 35.0,
        "требует ремонта": 15.0,
    }
    return scores.get(normalized)


def estimate_market_price(property_item: dict[str, Any], all_properties: list[dict[str, Any]]) -> dict[str, Any]:
    """Оценивает цену по медиане цены/м² аналогов того же района.

    Аналоги: тот же район, то же число комнат (если задано), площадь в пределах
    +/-20%. Сам объект исключается. При отсутствии района или достаточных аналогов
    возвращается status=insufficient_data, без выдуманной оценки.
    """
    district = property_item.get("district")
    area = _positive_number(property_item.get("area"))
    rooms = _positive_number(property_item.get("rooms"))
    price = _positive_number(property_item.get("price"))
    if not district or area is None or price is None:
        return _market_unavailable("Не хватает района, площади или цены.")

    peers = []
    for candidate in all_properties:
        if candidate is property_item or candidate.get("id") == property_item.get("id"):
            continue
        if str(candidate.get("district", "")).strip().casefold() != str(district).strip().casefold():
            continue
        candidate_area = _positive_number(candidate.get("area"))
        candidate_price = _positive_number(candidate.get("price"))
        candidate_rooms = _positive_number(candidate.get("rooms"))
        if candidate_area is None or candidate_price is None:
            continue
        if abs(candidate_area - area) / area > 0.20:
            continue
        if rooms is not None and candidate_rooms is not None and abs(candidate_rooms - rooms) > 1:
            continue
        peers.append(candidate_price / candidate_area)

    if len(peers) < 3:
        return _market_unavailable("В этом районе недостаточно сопоставимых квартир (нужно минимум 3 аналога).", len(peers))

    market_price = median(peers) * area
    deviation = (price - market_price) / market_price * 100.0
    warning = None
    if deviation > PRICE_WARNING_THRESHOLD:
        warning = {"code": "possibly_overpriced", "label": "Возможно завышенная цена"}
    elif deviation < -PRICE_WARNING_THRESHOLD:
        warning = {"code": "possibly_underpriced", "label": "Возможно заниженная стоимость"}
    return {
        "status": "estimated",
        "market_price": round(market_price),
        "deviation_percent": round(deviation, 1),
        "warning": warning,
        "comparable_count": len(peers),
        "price_score": None,  # Формулу баллов согласуем после тестов на данных.
    }


def score_listing_features(item: dict[str, Any], profile: dict[str, Any]) -> dict[str, float]:
    """Считает доступные оценки критериев, не подменяя отсутствующие данные нулями."""
    scores: dict[str, float] = {}
    target_area = profile.get("target_area")
    calculated_area = area_score(item.get("area"), target_area)
    if calculated_area is not None:
        scores["area"] = calculated_area
    condition = building_condition_score(item.get("building_condition"))
    if condition is not None:
        scores["building_condition"] = condition
    metro = item.get("metro_minutes")
    if metro is not None:
        score = proximity_score(metro, unit="minutes")
        if score is not None:
            scores["metro"] = score
    kindergarten = proximity_score(item.get("kindergarten_minutes"), unit="minutes")
    if kindergarten is not None:
        scores["kindergarten"] = kindergarten
    school = proximity_score(item.get("school_minutes"), unit="minutes")
    if school is not None:
        scores["school"] = school
    center = proximity_score(item.get("center_km"), unit="km")
    if center is not None:
        scores["city_center"] = center
    return scores


def _positive_number(value: Any) -> float | None:
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    return number if number > 0 else None


def _market_unavailable(reason: str, comparable_count: int = 0) -> dict[str, Any]:
    return {"status": "insufficient_data", "market_price": None, "deviation_percent": None,
            "warning": None, "comparable_count": comparable_count, "price_score": None, "reason": reason}
