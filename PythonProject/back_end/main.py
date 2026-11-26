from flask import Flask, jsonify, request, send_from_directory

from recommendations import rank_properties
from listing_preparation import prepare_search_listings
from property_scoring import filter_by_budget, score_listing_features, estimate_market_price
from demo_dataset import parse_apartment_text_content
from real_listing_import import fetch_listing_url

from pathlib import Path
from assistant_service import process_message
from database import db, init_database

from apartment_model import Apartment
from sqlalchemy.exc import SQLAlchemyError
from uuid import uuid4


FRONTEND_DIR = Path(__file__).resolve().parent.parent / 'front_end'
app = Flask(
    __name__,
    static_folder=str(FRONTEND_DIR / 'assets'),
    static_url_path='/assets'
)
init_database(app)


@app.route('/api/database/check')
def database_check():
    from sqlalchemy import text

    try:
        with db.engine.connect() as connection:
            connection.execute(text("SELECT 1"))

        return jsonify({
            "status": "success",
            "message": "Подключение к PostgreSQL работает!"
        })

    except Exception:
        app.logger.exception("Ошибка подключения к PostgreSQL")
        return jsonify({
            "status": "error",
            "message": "Не удалось подключиться к базе данных."
        }), 500


@app.route('/')
def home():
    return send_from_directory(FRONTEND_DIR, 'index.html')


@app.route('/templates/<path:filename>')
def page_templates(filename):
    """Отдаёт страницы для iframe (ассистент и карта)."""
    return send_from_directory(FRONTEND_DIR / 'templates', filename)


@app.route('/api/assistant/chat', methods=['POST'])
def assistant_chat():
    """Принимает сообщение и возвращает ответ ассистента."""

    payload = request.get_json(silent=True)

    if not isinstance(payload, dict):
        return jsonify({"error": "Ожидается JSON-объект."}), 400

    message = payload.get("message")
    filters = payload.get("filters", {})

    if not isinstance(message, str) or not message.strip():
        return jsonify({"error": "Введите сообщение."}), 400

    if len(message) > 2000:
        return jsonify({"error": "Сообщение слишком длинное."}), 400

    if not isinstance(filters, dict):
        return jsonify({"error": "Некорректные параметры поиска."}), 400

    try:
        result = process_message(message, filters)
        return jsonify(result)

    except (TypeError, ValueError) as exc:
        app.logger.exception("Ошибка обработки сообщения")
        return jsonify({
            "error": "Не удалось обработать сообщение."
        }), 500



@app.route('/api/recommendations/import-url', methods=['POST'])
def recommendations_import_url():
    """Fetch one user-supplied listing URL, extract and normalize its fields."""
    payload = request.get_json(silent=True)
    if not isinstance(payload, dict):
        return jsonify({"error": "Ожидается JSON-объект."}), 400
    url = payload.get("url")
    city = payload.get("city")
    if not isinstance(url, str) or not url.strip():
        return jsonify({"error": "Передайте ссылку в поле url."}), 400
    try:
        raw = fetch_listing_url(url.strip(), city)
        prepared = prepare_search_listings([raw], city or raw.get("city") or "Не указан")
        item = prepared[0] if prepared else raw
        return jsonify({
            "status": "success",
            "source": item.get("source_domain"),
            "raw_listing": raw,
            "listing": item,
            "quality": item.get("data_quality"),
            "note": "Неизвлечённые характеристики остаются пустыми; данные требуют проверки по оригиналу."
        }), 200
    except PermissionError as exc:
        return jsonify({"error": str(exc), "code": "robots_disallowed"}), 403
    except ValueError as exc:
        return jsonify({"error": str(exc)}), 422


@app.route('/api/recommendations/import-urls', methods=['POST'])
def recommendations_import_urls():
    """Batch import up to 10 user-provided listing URLs (sequential, respectful)."""
    payload = request.get_json(silent=True)
    urls = payload.get("urls") if isinstance(payload, dict) else None
    city = payload.get("city") if isinstance(payload, dict) else None
    if not isinstance(urls, list) or not urls or len(urls) > 10:
        return jsonify({"error": "Передайте от 1 до 10 ссылок в поле urls."}), 400
    if not all(isinstance(url, str) and url.strip() for url in urls):
        return jsonify({"error": "Каждая ссылка должна быть непустой строкой."}), 400
    results, errors = [], []
    for url in urls:
        try:
            raw = fetch_listing_url(url.strip(), city)
            prepared = prepare_search_listings([raw], city or raw.get("city") or "Не указан")
            results.extend(prepared or [raw])
        except (PermissionError, ValueError) as exc:
            errors.append({"url": url, "error": str(exc)})
    return jsonify({
        "results": results,
        "count": len(results),
        "errors": errors,
        "attempted": len(urls),
        "note": "Импорт последовательный; доступ проверяется по robots.txt, блокировки не обходятся."
    }), 200


@app.route('/api/recommendations/rank', methods=['POST'])
def recommendations_rank():
    """Принимает профиль приоритетов и нормализованные оценки объявлений."""
    payload = request.get_json(silent=True)
    if not isinstance(payload, dict):
        return jsonify({"error": "Ожидается JSON-объект."}), 400

    profile = payload.get('profile')
    properties = payload.get('properties')
    if not isinstance(profile, dict) or not isinstance(profile.get('priorities'), dict):
        return jsonify({"error": "В profile должен быть объект priorities."}), 400
    if not isinstance(properties, list):
        return jsonify({"error": "В properties должен быть список объявлений."}), 400

    try:
        ranked = rank_properties(profile, properties)
    except (AttributeError, TypeError, ValueError) as exc:
        return jsonify({"error": "Не удалось обработать входные данные.", "details": str(exc)}), 400

    return jsonify({"results": ranked, "count": len(ranked)})


@app.route('/api/recommendations/prepare', methods=['POST'])
def recommendations_prepare():
    """Нормализует исходные объявления одного города перед оценкой."""
    payload = request.get_json(silent=True)
    if not isinstance(payload, dict):
        return jsonify({"error": "Ожидается JSON-объект."}), 400
    city = payload.get('city')
    listings = payload.get('listings')
    if not isinstance(city, str) or not city.strip():
        return jsonify({"error": "Укажите город в поле city."}), 400
    if not isinstance(listings, list):
        return jsonify({"error": "В listings должен быть список объявлений."}), 400
    if not all(isinstance(item, dict) for item in listings):
        return jsonify({"error": "Каждое объявление должно быть JSON-объектом."}), 400
    prepared = prepare_search_listings(listings, city)
    return jsonify({
        "city": city,
        "results": prepared,
        "count": len(prepared),
        "rejected_other_city": len(listings) - len(prepared),
        "note": "Текстовые признаки извлечены эвристически; неизвестные значения не заменяются нулями."
    })


@app.route('/api/recommendations/evaluate', methods=['POST'])
def recommendations_evaluate():
    """Полный MVP-конвейер: бюджет -> признаки -> рынок -> взвешенный рейтинг."""
    payload = request.get_json(silent=True)
    if not isinstance(payload, dict):
        return jsonify({"error": "Ожидается JSON-объект."}), 400
    profile = payload.get('profile')
    properties = payload.get('properties')
    if not isinstance(profile, dict) or not isinstance(profile.get('priorities'), dict):
        return jsonify({"error": "В profile должен быть объект priorities."}), 400
    if not isinstance(properties, list) or not all(isinstance(row, dict) for row in properties):
        return jsonify({"error": "В properties должен быть список объектов."}), 400
    try:
        filtered, rejected = filter_by_budget(properties, payload.get('budget') or profile.get('budget'))
        enriched = []
        for item in filtered:
            row = dict(item)
            row['criterion_scores'] = score_listing_features(row, profile)
            row['market_analysis'] = estimate_market_price(row, filtered)
            price_score = row['market_analysis'].get('price_score')
            if price_score is not None:
                row['criterion_scores']['price'] = price_score
            enriched.append(row)
        ranked = rank_properties(profile, enriched)
        by_id = {row.get('id'): row for row in enriched}
        for result in ranked:
            source = by_id.get(result.get('id'), {})
            result['market_analysis'] = source.get('market_analysis')
            result['price'] = source.get('price')
            result['area'] = source.get('area')
            result['rooms'] = source.get('rooms')
        return jsonify({
            "results": ranked,
            "count": len(ranked),
            "rejected_by_budget": rejected,
            "price_scoring_status": "market_relative_when_comparable_data_exists",
            "note": "Ценовой балл рассчитывается только при наличии минимум трёх сопоставимых квартир того же района; иначе критерий не учитывается."
        })
    except (AttributeError, TypeError, ValueError) as exc:
        return jsonify({"error": "Не удалось обработать входные данные.", "details": str(exc)}), 400



@app.route('/api/recommendations/evaluate-demo', methods=['POST'])
def recommendations_evaluate_demo():
    """Запускает подбор по демонстрационной базе квартир из PostgreSQL."""

    payload = request.get_json(silent=True)

    if not isinstance(payload, dict) or not isinstance(payload.get('profile'), dict):
        return jsonify({
            "error": "Передайте профиль пользователя в поле profile."
        }), 400

    if not isinstance(payload['profile'].get('priorities'), dict):
        return jsonify({
            "error": "В profile должен быть объект priorities."
        }), 400

    try:
        # Получаем квартиры из PostgreSQL.
        apartments = Apartment.query.order_by(Apartment.id.asc()).all()

        # Преобразуем записи базы в обычные словари.
        properties = [
            apartment.to_dict()
            for apartment in apartments
        ]

        profile = payload['profile']

        # Фильтрация по бюджету.
        filtered, rejected = filter_by_budget(
            properties,
            profile.get('budget')
        )

        # Расчёт оценок критериев.
        enriched = []

        for item in filtered:
            row = dict(item)

            row['criterion_scores'] = score_listing_features(
                row,
                profile
            )

            row['market_analysis'] = estimate_market_price(
                row,
                filtered
            )

            price_score = row['market_analysis'].get('price_score')

            if price_score is not None:
                row['criterion_scores']['price'] = price_score

            enriched.append(row)

        # Сортировка квартир по приоритетам пользователя.
        ranked = rank_properties(profile, enriched)

        by_id = {
            row.get('id'): row
            for row in enriched
        }

        # Добавляем характеристики в результаты.
        for result in ranked:
            source = by_id.get(result.get('id'), {})

            for field in (
                'price',
                'area',
                'rooms',
                'market_analysis'
            ):
                result[field] = source.get(field)

        return jsonify({
            "results": ranked,
            "count": len(ranked),
            "rejected_by_budget": rejected,
            "price_scoring_status": "market_relative_when_comparable_data_exists"
        })

    except SQLAlchemyError:
        db.session.rollback()
        app.logger.exception(
            "Ошибка получения квартир из PostgreSQL"
        )

        return jsonify({
            "error": "Не удалось загрузить квартиры из PostgreSQL."
        }), 500

    except (ValueError, TypeError) as exc:
        app.logger.exception(
            "Ошибка обработки рекомендаций"
        )

        return jsonify({
            "error": "Не удалось обработать рекомендации.",
            "details": str(exc)
        }), 400


@app.route('/api/recommendations/import-text', methods=['POST'])
def recommendations_import_text():
    """Принимает содержимое TXT и возвращает распознанные объявления для предпросмотра."""
    payload = request.get_json(silent=True)
    if not isinstance(payload, dict) or not isinstance(payload.get('text'), str):
        return jsonify({"error": "Передайте текстовый файл в поле text."}), 400
    if len(payload['text'].encode('utf-8')) > 2 * 1024 * 1024:
        return jsonify({"error": "Файл слишком большой. Максимальный размер — 2 МБ."}), 413
    city = payload.get('city') or 'Не указан'
    listings, errors = parse_apartment_text_content(payload['text'], city)
    if not listings:
        return jsonify({"error": "Не удалось распознать объявления. Проверьте формат файла: для каждой квартиры нужны как минимум цена и площадь.", "errors": errors}), 422
    return jsonify({"results": listings, "count": len(listings), "errors": errors,
                    "note": "Распознаются структурированные TXT-объявления; отсутствующие характеристики остаются пустыми."})


@app.route("/api/apartments", methods=["GET", "POST"])
def add_apartment():
    if request.method == "GET":
        try:
            apartments = Apartment.query.order_by(Apartment.id).all()

            return jsonify({
                "total": len(apartments),
                "apartments": [
                    apartment.to_dict()
                    for apartment in apartments
                ]
            }), 200

        except SQLAlchemyError:
            return jsonify({
                "status": "error",
                "message": "Ошибка загрузки квартир из базы данных."
            }), 500

    data = request.get_json(silent=True)

    if not isinstance(data, dict):
        return jsonify({
            "status": "error",
            "message": "Ожидается JSON с данными квартиры."
        }), 400

    required_fields = ["city", "rooms", "price", "area"]

    missing_fields = [
        field for field in required_fields
        if field not in data or data[field] is None
    ]

    if missing_fields:
        return jsonify({
            "status": "error",
            "message": "Не заполнены обязательные поля.",
            "fields": missing_fields
        }), 400

    try:
        city = str(data["city"]).strip()
        rooms = int(data["rooms"])
        price = int(data["price"])
        area = float(data["area"])

        if not city:
            raise ValueError("Город не может быть пустым.")

        if rooms < 0 or price <= 0 or area <= 0:
            raise ValueError(
                "Проверь количество комнат, цену и площадь."
            )

        apartment_id = str(data.get("id") or uuid4())

        if Apartment.query.filter_by(id=apartment_id).first():
            return jsonify({
                "status": "error",
                "message": "Квартира с таким ID уже существует."
            }), 409

        apartment = Apartment(
            id=apartment_id,
            city=city,
            rooms=rooms,
            price=price,
            area=area,
            building_condition=data.get("building_condition"),
            metro_note=data.get("metro_note"),
            kindergarten_minutes=data.get("kindergarten_minutes"),
            school_minutes=data.get("school_minutes"),
            center_km=data.get("center_km"),
            metro_minutes=data.get("metro_minutes"),
            source="manual"
        )

        db.session.add(apartment)
        db.session.commit()

        return jsonify({
            "status": "success",
            "message": "Квартира успешно добавлена.",
            "apartment": apartment.to_dict()
        }), 201

    except (ValueError, TypeError) as error:
        return jsonify({
            "status": "error",
            "message": str(error)
        }), 400

    except SQLAlchemyError:
        db.session.rollback()
        return jsonify({
            "status": "error",
            "message": "Ошибка при сохранении квартиры в базе данных."
        }), 500


@app.route("/api/apartments/<string:apartment_id>", methods=["PUT"])
def update_apartment(apartment_id):
    data = request.get_json(silent=True)

    if not isinstance(data, dict) or not data:
        return jsonify({
            "status": "error",
            "message": "Передай JSON с данными для изменения."
        }), 400

    try:
        apartment = db.session.get(Apartment, apartment_id)

        if apartment is None:
            return jsonify({
                "status": "error",
                "message": "Квартира не найдена."
            }), 404

        # Разрешённые поля и типы данных
        field_types = {
            "city": str,
            "rooms": int,
            "price": int,
            "area": float,
            "building_condition": str,
            "metro_note": str,
            "kindergarten_minutes": int,
            "school_minutes": int,
            "center_km": float,
            "metro_minutes": int
        }

        nullable_fields = {
            "building_condition",
            "metro_note",
            "kindergarten_minutes",
            "school_minutes",
            "center_km",
            "metro_minutes"
        }

        # Проверяем неизвестные поля
        unknown_fields = set(data.keys()) - set(field_types.keys())

        if unknown_fields:
            return jsonify({
                "status": "error",
                "message": "Переданы неизвестные поля.",
                "fields": list(unknown_fields)
            }), 400

        for field, value in data.items():
            if value is None:
                if field not in nullable_fields:
                    raise ValueError(
                        f"Поле {field} не может быть пустым."
                    )

                setattr(apartment, field, None)
                continue

            expected_type = field_types[field]

            if expected_type == str:
                if not isinstance(value, str):
                    raise ValueError(
                        f"Поле {field} должно быть строкой."
                    )

                value = value.strip()

                if not value and field == "city":
                    raise ValueError("Город не может быть пустым.")

            elif expected_type == int:
                if isinstance(value, bool):
                    raise ValueError(
                        f"Поле {field} должно быть целым числом."
                    )

                if isinstance(value, float) and not value.is_integer():
                    raise ValueError(
                        f"Поле {field} должно быть целым числом."
                    )

                value = int(value)

            elif expected_type == float:
                if isinstance(value, bool):
                    raise ValueError(
                        f"Поле {field} должно быть числом."
                    )

                value = float(value)

            if field == "rooms" and value < 0:
                raise ValueError("Количество комнат не может быть отрицательным.")

            if field == "price" and value <= 0:
                raise ValueError("Цена должна быть больше нуля.")

            if field == "area" and value <= 0:
                raise ValueError("Площадь должна быть больше нуля.")

            if field in {
                "kindergarten_minutes",
                "school_minutes",
                "metro_minutes",
                "center_km"
            } and value < 0:
                raise ValueError(
                    f"Поле {field} не может быть отрицательным."
                )

            setattr(apartment, field, value)

        db.session.commit()

        return jsonify({
            "status": "success",
            "message": "Квартира успешно обновлена.",
            "apartment": apartment.to_dict()
        }), 200

    except (ValueError, TypeError, OverflowError) as error:
        db.session.rollback()

        return jsonify({
            "status": "error",
            "message": str(error)
        }), 400

    except SQLAlchemyError:
        db.session.rollback()

        return jsonify({
            "status": "error",
            "message": "Ошибка при обновлении квартиры в базе данных."
        }), 500


@app.route("/api/apartments/<string:apartment_id>", methods=["GET"])
def get_apartment(apartment_id):
    try:
        apartment = db.session.get(Apartment, apartment_id)

        if apartment is None:
            return jsonify({
                "status": "error",
                "message": "Квартира не найдена."
            }), 404

        return jsonify({
            "status": "success",
            "apartment": apartment.to_dict()
        }), 200

    except SQLAlchemyError:
        db.session.rollback()

        return jsonify({
            "status": "error",
            "message": "Не удалось получить квартиру из базы данных."
        }), 500


@app.route("/api/apartments/<string:apartment_id>", methods=["DELETE"])
def delete_apartment(apartment_id):
    try:
        apartment = db.session.get(Apartment, apartment_id)

        if apartment is None:
            return jsonify({
                "status": "error",
                "message": "Квартира не найдена."
            }), 404

        db.session.delete(apartment)
        db.session.commit()

        return jsonify({
            "status": "success",
            "message": "Квартира успешно удалена.",
            "deleted_id": apartment_id
        }), 200

    except SQLAlchemyError:
        db.session.rollback()

        return jsonify({
            "status": "error",
            "message": "Ошибка при удалении квартиры из базы данных."
        }), 500


if __name__ == '__main__':
    app.run(debug=True)
