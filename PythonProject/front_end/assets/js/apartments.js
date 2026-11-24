
(() => {
    const API_URL = "/api/apartments";

    const catalogList = document.getElementById("catalog-list");
    const catalogStatus = document.getElementById("catalog-status");

    if (!catalogList || !catalogStatus) {
        console.error("Не найдены элементы каталога квартир.");
        return;
    }

    // Загрузка всех квартир из базы данных
    async function loadApartments() {
        catalogStatus.textContent = "Загружаем квартиры...";
        catalogList.innerHTML = "";

        try {
            const response = await fetch(API_URL);
            const data = await response.json();

            if (!response.ok) {
                throw new Error(data.message || "Ошибка загрузки квартир.");
            }

            const apartments = data.apartments || [];

            catalogStatus.textContent =
                `Всего квартир в каталоге: ${apartments.length}`;

            if (apartments.length === 0) {
                catalogList.innerHTML =
                    '<p class="catalog-empty">В каталоге пока нет квартир.</p>';
                return;
            }

            apartments.forEach(apartment => {
                catalogList.appendChild(createApartmentCard(apartment));
            });

        } catch (error) {
            console.error("Ошибка загрузки каталога:", error);
            catalogStatus.textContent =
                "Не удалось загрузить квартиры. Проверь подключение к серверу.";
        }
    }

    // Создание карточки квартиры
    function createApartmentCard(apartment) {
        const card = document.createElement("div");
        card.className = "catalog-card";

        const sourceLabel = apartment.source === "demo"
            ? "Демо-данные"
            : "Добавлена вручную";

        card.innerHTML = `
            <div class="catalog-card-header">
                <h3>${escapeHTML(apartment.city)}</h3>
                <span class="catalog-source">${sourceLabel}</span>
            </div>

            <div class="catalog-card-info">
                <p><strong>Комнат:</strong> ${apartment.rooms}</p>
                <p><strong>Площадь:</strong> ${apartment.area} м²</p>
                <p><strong>Цена:</strong> ${formatPrice(apartment.price)}</p>
                <p><strong>Состояние:</strong>
                    ${escapeHTML(apartment.building_condition || "Не указано")}
                </p>
                <p><strong>До детского сада:</strong>
                    ${formatMinutes(apartment.kindergarten_minutes)}
                </p>
                <p><strong>До школы:</strong>
                    ${formatMinutes(apartment.school_minutes)}
                </p>
                <p><strong>До центра:</strong>
                    ${apartment.center_km == null
                        ? "Не указано"
                        : apartment.center_km + " км"}
                </p>
                <p><strong>Транспорт:</strong>
                    ${escapeHTML(apartment.metro_note || "Не указано")}
                </p>
            </div>

            <div class="catalog-card-actions">
                <button type="button" class="catalog-edit-button" disabled>
                    Редактировать
                </button>
                <button type="button" class="catalog-delete-button" disabled>
                    Удалить
                </button>
            </div>
        `;

        return card;
    }

    // Безопасный вывод текстовых значений
    function escapeHTML(value) {
        return String(value).replace(/[&<>"']/g, character => ({
            "&": "&amp;",
            "<": "&lt;",
            ">": "&gt;",
            '"': "&quot;",
            "'": "&#039;"
        })[character]);
    }

    function formatPrice(price) {
        return Number(price).toLocaleString("ru-RU") + " ₽";
    }

    function formatMinutes(minutes) {
        return minutes == null ? "Не указано" : minutes + " мин.";
    }

    // Первоначальная загрузка
    loadApartments();

})();