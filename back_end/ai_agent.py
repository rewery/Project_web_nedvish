from flask import Flask, render_template, request, jsonify

app = Flask(
    __name__,
    template_folder="frontend/templates",
    static_folder="assets",
    static_url_path="/assets"
)

@app.route("/")
def index():
    return render_template("ai_agent_html.html")


@app.route("/chat", methods=["POST"])
def chat():
    data = request.get_json()

    message = data.get("message", "").strip()

    if not message:
        return jsonify({"error": "Пустое сообщение"}), 400

    # Здесь происходит обработка сообщения
    response = process_message(message)

    return jsonify({
        "response": response
    })


def process_message(message):
    """
    Здесь будет логика твоего AI-агента.
    Пока возвращаем тестовый ответ.
    """
    return f"Python получил твоё сообщение: {message}"


if __name__ == "__main__":
    app.run(debug=True)