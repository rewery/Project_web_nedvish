import json
import re
from pathlib import Path


DATA_PATH = Path(__file__).with_name("demo_apartments_yoshkar_ola.json")


def parse_message(message):
    """Извлекает параметры поиска из обычного русского текста."""

    text = message.lower().replace("ё", "е")
    filters = {}

    # Бюджет: до 5 млн, не дороже 5 000 000 рублей
    budget_pattern = (
        r"(?:до|не дороже|максимум|не более)\s*"
        r"(\d[\d\s.,]*)\s*"
        r"(млн|миллион(?:а|ов)?|тыс(?:яч)?|руб(?:лей)?|₽)?"
    )
    budget_match = re.search(budget_pattern, text)

    if budget_match:
        number = float(
            budget_match.group(1).replace(" ", "").replace(",", ".")
        )
        unit = budget_match.group(2) or ""

        if unit in ("млн", "миллион", "миллиона", "миллионов"):
            number *= 1_000_000
        elif unit in ("тыс", "тысяч"):
            number *= 1_000

        if number > 0:
            filters["max_price"] = int(number)

    # Количество комнат
    room_words = {
        "однокомнат": 1,
        "однушк": 1,
        "двухкомнат": 2,
        "двушк": 2,
        "трехкомнат": 3,
        "трёхкомнат": 3,
        "трешк": 3,
        "трёшк": 3,
        "четырехкомнат": 4,
        "четырёхкомнат": 4,
    }

    for word, count in room_words.items():
        if word in text:
            filters["rooms"] = count
            break

    if "rooms" not in filters:
        room_match = re.search(
            r"\b([1-5])\s*[- ]?(?:комнатн\w*|комнат\w*)",
            text
        )
        if room_match:
            filters["rooms"] = int(room_match.group(1))

    # Минимальная площадь: от 50 м², площадью от 50 кв. м
    area_match = re.search(
        r"(?:от|площадью|площадь|не меньше)\s*"
        r"(\d+(?:[.,]\d+)?)\s*"
        r"(?:м²|м2|кв\.?\s*м)?",
        text
    )

    if area_match:
        filters["min_area"] = float(
            area_match.group(1).replace(",", ".")
        )

    if "йошкар" in text:
        filters["city"] = "Йошкар-Ола"

    return filters


def search_apartments(filters):
    """Ищет квартиры в демонстрационном JSON-наборе."""

    data = json.loads(DATA_PATH.read_text(encoding="utf-8"))

    apartments = (
        data.get("listings", [])
        if isinstance(data, dict)
        else data
    )

    if not isinstance(apartments, list):
        raise ValueError("Некорректный формат базы квартир.")

    results = []

    for apartment in apartments:
        if not isinstance(apartment, dict):
            continue

        price = apartment.get("price")
        rooms = apartment.get("rooms")
        area = apartment.get("area")

        if filters.get("max_price") is not None:
            if not isinstance(price, (int, float)):
                continue
            if price > filters["max_price"]:
                continue

        if filters.get("rooms") is not None:
            if rooms != filters["rooms"]:
                continue

        if filters.get("min_area") is not None:
            if not isinstance(area, (int, float)):
                continue
            if area < filters["min_area"]:
                continue

        results.append(apartment)

    return results[:10]


def process_message(message, previous_filters=None):
    """Обрабатывает сообщение и возвращает ответ с найденными квартирами."""

    filters = dict(previous_filters or {})
    new_filters = parse_message(message)
    filters.update(new_filters)

    if not filters:
        return {
            "reply": (
                "Привет! Я помогу подобрать квартиру. "
                "Напиши, например: «Двухкомнатная квартира "
                "в Йошкар-Оле до 5 млн рублей, площадью от 40 м²»."
            ),
            "filters": {},
            "listings": []
        }

    try:
        apartments = search_apartments(filters)
    except (OSError, ValueError, json.JSONDecodeError):
        return {
            "reply": "Не получилось загрузить базу квартир. Попробуй позже.",
            "filters": filters,
            "listings": []
        }

    if apartments:
        reply = f"Нашёл подходящие варианты: {len(apartments)}. Посмотри их ниже."
    else:
        reply = (
            "По этим параметрам квартир пока не нашлось. "
            "Попробуй увеличить бюджет или изменить площадь."
        )

    return {
        "reply": reply,
        "filters": filters,
        "listings": apartments
    }