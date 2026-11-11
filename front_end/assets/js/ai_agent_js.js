
const textarea = document.getElementById("message");
const messages = document.querySelector(".messages");
const sendButton = document.querySelector(".send");

let currentFilters = {};
let isSending = false;

// Добавление сообщения в чат
function addMessage(text, sender) {
    const messageElement = document.createElement("div");
    messageElement.className = `message ${sender}`;
    messageElement.textContent = text;

    messages.appendChild(messageElement);
    messages.scrollTop = messages.scrollHeight;

    return messageElement;
}

// Карточки найденных квартир
function addApartmentCards(apartments) {
    apartments.forEach(apartment => {
        const card = document.createElement("div");
        card.className = "apartment-card";

        const title = document.createElement("h3");
        title.textContent =
            `${apartment.rooms ?? "?"}-комнатная квартира`;

        const price = document.createElement("p");
        price.textContent = apartment.price != null
            ? `Цена: ${Number(apartment.price).toLocaleString("ru-RU")} ₽`
            : "Цена не указана";

        const area = document.createElement("p");
        area.textContent = apartment.area != null
            ? `Площадь: ${apartment.area} м²`
            : "Площадь не указана";

        const id = document.createElement("p");
        id.textContent = `Номер объявления: ${apartment.id ?? "не указан"}`;

        card.append(title, price, area, id);
        messages.appendChild(card);
    });

    messages.scrollTop = messages.scrollHeight;
}

// Отправка сообщения
async function sendMessage() {
    const message = textarea.value.trim();

    if (!message || isSending) return;

    addMessage(message, "user");

    textarea.value = "";
    textarea.style.height = "auto";

    isSending = true;
    sendButton.disabled = true;

    const loadingMessage = addMessage(
        "Подбираю подходящие квартиры...",
        "bot"
    );

    try {
        const response = await fetch("/api/assistant/chat", {
            method: "POST",
            headers: {
                "Content-Type": "application/json"
            },
            body: JSON.stringify({
                message: message,
                filters: currentFilters
            })
        });

        const data = await response.json();

        if (!response.ok) {
            throw new Error(data.error || "Ошибка сервера.");
        }

        currentFilters = data.filters || {};

        loadingMessage.textContent =
            data.reply || "Ответ получен.";

        if (Array.isArray(data.listings) && data.listings.length > 0) {
            addApartmentCards(data.listings);
        }

    } catch (error) {
        loadingMessage.textContent =
            "Не удалось получить ответ: " + error.message;
    } finally {
        isSending = false;
        sendButton.disabled = false;
        textarea.focus();
    }
}

// Изменение высоты поля ввода
textarea.addEventListener("input", () => {
    textarea.style.height = "auto";
    textarea.style.height =
        Math.min(textarea.scrollHeight, 200) + "px";
});

// Enter — отправка, Shift + Enter — новая строка
textarea.addEventListener("keydown", event => {
    if (event.key === "Enter" && !event.shiftKey) {
        event.preventDefault();
        sendMessage();
    }
});

// Приветствие при открытии чата
addMessage(
    "Привет! Я Homer — помощник по подбору квартир. " +
    "Расскажи, какую квартиру ты ищешь.",
    "bot"
);

// Переключение светлой и тёмной темы

const themeToggle = document.getElementById("themeToggle");

function setTheme(theme) {
    document.documentElement.setAttribute("data-theme", theme);

    themeToggle.textContent =
        theme === "dark" ? "☀️" : "🌙";

    localStorage.setItem("homer-theme", theme);
}

const savedTheme = localStorage.getItem("homer-theme") || "light";

setTheme(savedTheme);

themeToggle.addEventListener("click", () => {
    const currentTheme =
        document.documentElement.getAttribute("data-theme");

    setTheme(currentTheme === "dark" ? "light" : "dark");
});