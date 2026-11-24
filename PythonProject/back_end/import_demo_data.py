import json
from pathlib import Path

from main import app
from database import db
from apartment_model import Apartment


def import_apartments():
    file_path = Path(__file__).with_name(
        "demo_apartments_yoshkar_ola.json"
    )

    with file_path.open("r", encoding="utf-8") as file:
        dataset = json.load(file)

    listings = dataset.get("listings", [])

    if not isinstance(listings, list) or len(listings) != 50:
        raise ValueError(
            "Ожидалось 50 демонстрационных объявлений."
        )

    with app.app_context():
        # Создаёт отсутствующие таблицы, не удаляя существующие.
        db.create_all()

        imported = 0
        updated = 0

        for item in listings:
            apartment = db.session.get(
                Apartment,
                item["id"]
            )

            if apartment is None:
                apartment = Apartment(id=item["id"])
                db.session.add(apartment)
                imported += 1
            else:
                updated += 1

            apartment.city = item["city"]
            apartment.rooms = item["rooms"]
            apartment.price = item["price"]
            apartment.area = item["area"]
            apartment.building_condition = item.get(
                "building_condition"
            )
            apartment.metro_note = item.get("metro_note")
            apartment.kindergarten_minutes = item.get(
                "kindergarten_minutes"
            )
            apartment.school_minutes = item.get(
                "school_minutes"
            )
            apartment.center_km = item.get("center_km")
            apartment.metro_minutes = item.get("metro_minutes")
            apartment.source = "demo"

        db.session.commit()

        total = db.session.query(Apartment).count()

        print("Импорт завершён!")
        print(f"Добавлено: {imported}")
        print(f"Обновлено: {updated}")
        print(f"Всего квартир в базе: {total}")


if __name__ == "__main__":
    # try:
    #     import_apartments()
    # except Exception:
    #     db.session.rollback()
    #     raise
    import_apartments()