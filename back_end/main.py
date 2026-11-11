from flask import Flask, jsonify, request, send_from_directory

from recommendations import rank_properties
from listing_preparation import prepare_search_listings
from property_scoring import filter_by_budget, score_listing_features, estimate_market_price
from demo_dataset import parse_apartment_text_content

from pathlib import Path

from assistant_service import process_message

FRONTEND_DIR = Path(__file__).resolve().parent.parent / 'front_end'
app = Flask(
    __name__,
    static_folder=str(FRONTEND_DIR / 'assets'),
    static_url_path='/assets'
)


@app.route('/')
def home():
    return send_from_directory(FRONTEND_DIR / 'templates', 'index.html')


@app.route('/templates/<path:filename>')
def page_templates(filename):
    """Отдаёт страницы для iframe (ассистент и карта)."""
    return send_from_directory(FRONTEND_DIR / 'templates', filename)


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
            # Рыночная оценка и предупреждения доступны, но ценовой балл пока
            # намеренно не включён до калибровки на реальных данных.
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
            "price_scoring_status": "pending_calibration",
            "note": "Ценовой балл пока не влияет на рейтинг; для рыночной оценки нужны аналоги с указанным районом."
        })
    except (AttributeError, TypeError, ValueError) as exc:
        return jsonify({"error": "Не удалось обработать входные данные.", "details": str(exc)}), 400


@app.route('/api/recommendations/evaluate-demo', methods=['POST'])
def recommendations_evaluate_demo():
    """Запускает подбор по встроенной демонстрационной базе квартир."""
    payload = request.get_json(silent=True)
    if not isinstance(payload, dict) or not isinstance(payload.get('profile'), dict):
        return jsonify({"error": "Передайте профиль пользователя в поле profile."}), 400
    if not isinstance(payload['profile'].get('priorities'), dict):
        return jsonify({"error": "В profile должен быть объект priorities."}), 400
    from pathlib import Path
    import json
    dataset_path = Path(__file__).with_name('demo_apartments_yoshkar_ola.json')
    try:
        dataset = json.loads(dataset_path.read_text(encoding='utf-8'))
        properties = dataset.get('listings', []) if isinstance(dataset, dict) else dataset
        if not isinstance(properties, list):
            raise ValueError('В демонстрационной базе отсутствует список listings.')
        profile = payload['profile']
        filtered, rejected = filter_by_budget(properties, profile.get('budget'))
        enriched = []
        for item in filtered:
            row = dict(item)
            row['criterion_scores'] = score_listing_features(row, profile)
            row['market_analysis'] = estimate_market_price(row, filtered)
            enriched.append(row)
        ranked = rank_properties(profile, enriched)
        by_id = {row.get('id'): row for row in enriched}
        for result in ranked:
            source = by_id.get(result.get('id'), {})
            for field in ('price', 'area', 'rooms', 'market_analysis'):
                result[field] = source.get(field)
        return jsonify({"results": ranked, "count": len(ranked), "rejected_by_budget": rejected,
                        "price_scoring_status": "pending_calibration"})
    except (OSError, ValueError, TypeError) as exc:
        return jsonify({"error": "Не удалось загрузить демонстрационную базу.", "details": str(exc)}), 500


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


@app.route('/api/assistant/chat', methods=['POST'])
def assistant_chat():
    """Обрабатывает сообщения пользователя в ИИ-ассистенте."""

    payload = request.get_json(silent=True)

    if not isinstance(payload, dict):
        return jsonify({"error": "Ожидается JSON-объект."}), 400

    message = payload.get('message')

    if not isinstance(message, str) or not message.strip():
        return jsonify({"error": "Введите сообщение."}), 400

    if len(message) > 2000:
        return jsonify({"error": "Сообщение слишком длинное."}), 413

    try:
        result = process_message(message.strip())
        return jsonify(result)

    except (ValueError, OSError) as exc:
        return jsonify({
            "error": "Не удалось обработать сообщение.",
            "details": str(exc)
        }), 400


if __name__ == '__main__':
    app.run(debug=True)
