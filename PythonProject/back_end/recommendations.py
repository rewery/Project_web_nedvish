"""Прозрачное ранжирование объявлений по приоритетам пользователя.

Модуль не обращается к AI и не извлекает признаки из объявлений.
На вход он получает уже нормализованные оценки критериев от 0 до 100.
Отсутствующая оценка или приоритет уровня unspecified не дают штрафа.
Уровень not_important исключает критерий из расчёта.
"""

from __future__ import annotations

from typing import Any

PRIORITY_WEIGHTS = {
    "not_important": 0,
    "low": 1,
    "medium": 2,
    "high": 3,
}

CRITERIA = (
    "price",
    "area",
    "building_condition",
    "metro",
    "kindergarten",
    "school",
    "city_center",
)

CRITERION_LABELS = {
    "price": "Стоимость",
    "area": "Площадь квартиры",
    "building_condition": "Состояние дома",
    "metro": "Близость к метро",
    "kindergarten": "Детские сады",
    "school": "Школы",
    "city_center": "Близость к центру",
}


def _priority_weight(priority: dict[str, Any] | None) -> float:
    """Читает вес из профиля; неизвестный/неуказанный приоритет пропускается."""
    if not isinstance(priority, dict):
        return 0.0
    level = priority.get("level")
    if level == "unspecified":
        return 0.0
    if level in PRIORITY_WEIGHTS:
        return float(PRIORITY_WEIGHTS[level])
    weight = priority.get("weight")
    try:
        value = float(weight)
    except (TypeError, ValueError):
        return 0.0
    return max(0.0, min(3.0, value))


def _valid_score(value: Any) -> float | None:
    try:
        score = float(value)
    except (TypeError, ValueError):
        return None
    if not 0 <= score <= 100:
        return None
    return score


def rank_properties(profile: dict[str, Any], properties: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Возвращает объявления по убыванию взвешенного рейтинга (0–100).

    Ожидаемый формат property:
      {"id": "flat-1", "title": "...", "criterion_scores": {"apartment_condition": 90, ...}}
    """
    priorities = profile.get("priorities", {})
    ranked = []

    for original_index, item in enumerate(properties):
        scores = item.get("criterion_scores") or {}
        weighted_sum = 0.0
        weight_sum = 0.0
        contributions = []
        missing = []

        for criterion in CRITERIA:
            weight = _priority_weight(priorities.get(criterion))
            if weight <= 0:
                continue

            score = _valid_score(scores.get(criterion))
            source = "основная оценка"

            if score is None:
                missing.append(CRITERION_LABELS[criterion])
                continue

            weighted_sum += score * weight
            weight_sum += weight
            contributions.append({
                "criterion": criterion,
                "label": CRITERION_LABELS[criterion],
                "score": round(score, 1),
                "weight": weight,
                "source": source,
            })

        rating = round(weighted_sum / weight_sum, 1) if weight_sum else None
        contributions.sort(key=lambda row: row["score"] * row["weight"], reverse=True)
        ranked.append({
            "id": item.get("id"),
            "title": item.get("title") or f"Объявление {original_index + 1}",
            "rating": rating,
            "rating_scale": "0–100",
            "evaluated_criteria": len(contributions),
            "explanation": _make_explanation(contributions, missing, rating),
            "criterion_details": contributions,
            "missing_criteria": missing,
            "_original_index": original_index,
        })

    # Объекты без единой применимой оценки идут в конец, не получая фиктивный ноль.
    ranked.sort(key=lambda row: (row["rating"] is not None, row["rating"] or 0, -row["_original_index"]), reverse=True)
    for row in ranked:
        row.pop("_original_index", None)
    return ranked


def _make_explanation(contributions: list[dict[str, Any]], missing: list[str], rating: float | None) -> str:
    if rating is None:
        return "Недостаточно данных по критериям, которые важны пользователю: рейтинг пока не рассчитан."
    if not contributions:
        return "Нет критериев с заданным приоритетом и доступными оценками."
    best = sorted(contributions, key=lambda row: row["score"], reverse=True)[:2]
    weak = sorted(contributions, key=lambda row: row["score"])[:1]
    text = "Сильные стороны: " + " и ".join(row["label"].lower() for row in best) + "."
    if weak and weak[0]["score"] < 60:
        text += f" Слабое место: {weak[0]['label'].lower()}."
    if missing:
        text += " Не удалось учесть: " + ", ".join(missing) + "."
    return text
