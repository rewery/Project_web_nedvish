"""Импорт учебного текстового набора квартир Йошкар-Олы."""
from __future__ import annotations
import re
from pathlib import Path

FIELD_PATTERNS = {
    "id": (r"Квартира №(\d+)", lambda x: f"yola-{int(x):02d}"),
    "rooms": (r"Количество комнат:\s*(\d+)", int),
    "price": (r"Цена квартиры:\s*([\d\s]+)\s*руб", lambda x: int(x.replace(" ", ""))),
    "area": (r"Площадь:\s*([\d.,]+)\s*м²", lambda x: float(x.replace(",", "."))),
    "building_condition": (r"Состояние дома:\s*(.+)", str.strip),
    "metro_note": (r"Близость к метро:\s*(.+)", str.strip),
    "kindergarten_minutes": (r"Близость к детским садам:\s*(\d+)\s*мин", int),
    "school_minutes": (r"Близость к школам:\s*(\d+)\s*мин", int),
    "center_km": (r"Близость к центру:\s*([\d.,]+)\s*км", lambda x: float(x.replace(",", "."))),
}

def parse_apartment_text_content(text: str, city: str = "Йошкар-Ола") -> tuple[list[dict], list[dict]]:
    """Разбирает пользовательский TXT: один блок объявления на квартиру.

    Поддерживает исходный учебный формат и близкие варианты названий полей.
    Нераспознанные блоки возвращаются отдельно, чтобы пользователь видел потери.
    """
    if not isinstance(text, str) or not text.strip():
        return [], [{"block": 0, "reason": "Файл пустой."}]
    blocks = re.split(r"(?=Квартира\s*(?:№|#)\s*\d+)|(?=Объявление\s*№?\s*\d+)", text, flags=re.I)
    if len(blocks) <= 1:
        blocks = re.split(r"\n\s*\n(?=.{0,80}(?:Цена|Стоимость|Площадь|комнат))", text, flags=re.I)
    results = []
    errors = []
    for block in blocks:
        if not re.search(r"(?:Цена|Стоимость).*?(?:руб|₽)|Площадь.*?м", block, re.I | re.S):
            continue
        item = {"city": city.strip() or "Не указан"}
        patterns = dict(FIELD_PATTERNS)
        patterns["id"] = (r"(?:Квартира|Объявление)\s*(?:№|#)?\s*(\d+)", lambda x: f"upload-{int(x):03d}")
        patterns["rooms"] = (r"(?:Количество комнат|Комнат(?:ы)?):\s*(\d+)", int)
        patterns["price"] = (r"(?:Цена квартиры|Цена|Стоимость):\s*([\d\s]+)\s*(?:руб(?:лей)?|₽)", lambda x: int(x.replace(" ", "")))
        patterns["area"] = (r"(?:Общая площадь|Площадь):\s*([\d.,]+)\s*м²", lambda x: float(x.replace(",", ".")))
        patterns["building_condition"] = (r"Состояние дома:\s*(.+)", str.strip)
        patterns["kindergarten_minutes"] = (r"(?:Близость к детским садам|Детский сад):\s*(\d+)\s*мин", int)
        patterns["school_minutes"] = (r"(?:Близость к школам|Школа):\s*(\d+)\s*мин", int)
        patterns["center_km"] = (r"(?:Близость к центру|До центра):\s*([\d.,]+)\s*км", lambda x: float(x.replace(",", ".")))
        for field, (pattern, converter) in patterns.items():
            match = re.search(pattern, block, re.I)
            if match:
                try:
                    item[field] = converter(match.group(1))
                except (TypeError, ValueError):
                    pass
        metro_match = re.search(r"(?:До метро|Метро):\s*(\d+)\s*мин", block, re.I)
        item["metro_minutes"] = int(metro_match.group(1)) if metro_match else None
        item["district"] = (re.search(r"Район:\s*(.+)", block, re.I).group(1).strip()
                            if re.search(r"Район:\s*(.+)", block, re.I) else None)
        if item.get("price") and item.get("area"):
            results.append(item)
        else:
            errors.append({"block": len(results) + len(errors) + 1,
                           "reason": "Не удалось распознать цену и/или площадь."})
    return results, errors


def parse_apartment_text(path: str | Path) -> list[dict]:
    text = Path(path).read_text(encoding="utf-8-sig")
    results, _ = parse_apartment_text_content(text)
    return results
