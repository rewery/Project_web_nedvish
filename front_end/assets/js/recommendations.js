/*
 * MVP настройки приоритетов пользователя.
 * После подтверждения:
 * 1) формирует JSON-профиль;
 * 2) сохраняет его в sessionStorage для текущей вкладки;
 * 3) отправляет событие recommendation:priorities-ready.
 * Позже обработчик события можно связать с API/модулем ранжирования.
 */
(() => {
  'use strict';

  const form = document.getElementById('priority-form');
  if (!form) return;
  const continueButton = document.getElementById('priority-continue');
  if (continueButton) continueButton.addEventListener('click', () => { if (form.requestSubmit) form.requestSubmit(); else form.dispatchEvent(new Event('submit', { bubbles: true, cancelable: true })); });

  const labels = {
    not_important: 'Не важно',
    low: 'Низкий',
    medium: 'Средний',
    high: 'Высокий'
  };
  const result = document.getElementById('priority-result');
  const output = document.getElementById('priority-json');
  const scoreMap = { unspecified: 0, not_important: 0, low: 1, medium: 2, high: 3 };
  const status = document.getElementById('priority-status');
  const recommendationsOutput = document.getElementById('recommendation-results');
  const priceInputs = ['min_price', 'max_price'].map(name => form.querySelector(`[name="${name}"]`)).filter(Boolean);
  const digitsOnly = value => String(value || '').replace(/\D/g, '');
  const formatThousands = value => { const digits = digitsOnly(value); return digits ? Number(digits).toLocaleString('ru-RU').replace(/\u00a0/g, ' ') : ''; };
  priceInputs.forEach(input => {
    input.addEventListener('input', () => { const start = input.selectionStart; const before = input.value.slice(0, start); const formattedBefore = formatThousands(before); input.value = formatThousands(input.value); const pos = Math.min(formattedBefore.length, input.value.length); try { input.setSelectionRange(pos, pos); } catch (_) {} });
    input.addEventListener('blur', () => { input.value = formatThousands(input.value); });
  });
  const summaryBody = document.getElementById('priority-summary-body');
  const categoryLabels = {
    price: 'Стоимость квартиры', area: 'Площадь квартиры', building_condition: 'Состояние дома', metro: 'Близость к метро', kindergarten: 'Детские сады', school: 'Школы', city_center: 'Близость к центру'
  };
  const displayLabels = { unspecified: 'Пока не решил(а)', not_important: 'Не важно', low: 'Низкий', medium: 'Средний', high: 'Высокий' };
  const barWidths = { unspecified: 0, not_important: 0, low: 33, medium: 66, high: 100 };

  const initialProfile = {
    price: 'unspecified', area: 'unspecified', building_condition: 'unspecified', metro: 'unspecified', kindergarten: 'unspecified', school: 'unspecified', city_center: 'unspecified'
  };

  // Подставляем уже согласованный с пользователем профиль при первом открытии.
  Object.entries(initialProfile).forEach(([name, value]) => {
    const input = form.querySelector(`input[name="${name}"][value="${value}"]`);
    if (input) input.checked = true;
  });

  function renderPrioritySummary() {
    if (!summaryBody) return;
    summaryBody.innerHTML = Object.entries(categoryLabels).map(([key, label]) => {
      const level = readGroup(key);
      const width = barWidths[level] || 0;
      const stateClass = `is-${level.replace('_', '-')}`;
      const bar = level === 'unspecified'
        ? '<span class="priority-summary__empty">—</span>'
        : `<span class="priority-summary__track"><span class="priority-summary__fill ${stateClass}" style="width:${width}%"></span></span>`;
      return `<tr><th scope="row">${label}</th><td><span class="priority-summary__level ${stateClass}">${displayLabels[level]}</span></td><td>${bar}</td></tr>`;
    }).join('');
  }
  form.addEventListener('change', renderPrioritySummary);
  renderPrioritySummary();

  function readGroup(name) {
    const selected = form.querySelector(`input[name="${name}"]:checked`);
    return selected ? selected.value : 'unspecified';
  }

  function buildProfile() {
    const categories = ['price', 'area', 'building_condition', 'metro', 'kindergarten', 'school', 'city_center'];
    const priorities = {};
    categories.forEach((key) => {
      const level = readGroup(key);
      priorities[key] = { level, weight: scoreMap[level] };
    });

    const maxRaw = form.querySelector('[name="max_price"]')?.value.trim();
    const minRaw = form.querySelector('[name="min_price"]')?.value.trim();
    const maxPrice = maxRaw ? Number(digitsOnly(maxRaw)) : null;
    const minPrice = minRaw ? Number(digitsOnly(minRaw)) : null;
    const budget = { mode: minPrice !== null && maxPrice !== null ? 'price_range' : minPrice !== null ? 'min_price' : maxPrice !== null ? 'max_price' : 'none' };
    if (maxPrice !== null) budget.max_price = maxPrice;
    if (minPrice !== null) budget.min_price = minPrice;
    const targetAreaValue = Number(form.querySelector('[name="target_area"]')?.value);
    return { schema_version: 2, priorities, budget, target_area: targetAreaValue > 0 ? targetAreaValue : null };
  }

  form.addEventListener('submit', async (event) => {
    event.preventDefault();
    const profile = buildProfile();
    if (profile.budget.mode !== 'none' && Object.entries(profile.budget).some(([key, value]) => key !== 'mode' && !(value > 0))) { alert('Цена должна быть больше нуля.'); return; }
    if (profile.budget.mode === 'price_range' && profile.budget.max_price < profile.budget.min_price) { alert('Значение «До» должно быть не меньше значения «От».'); return; }
    const activePriorities = Object.values(profile.priorities).some(item => item.weight > 0);
    if (!activePriorities) { alert('Выберите хотя бы один приоритет: сейчас все критерии имеют нулевой вес.'); return; }
    const json = JSON.stringify(profile, null, 2);
    try { sessionStorage.setItem('recommendation_priorities', json); } catch (_) {}
    output.textContent = json;
    result.classList.add('is-visible');
    if (status) status.textContent = 'Рассчитываем подбор по демонстрационной базе…';
    if (recommendationsOutput) recommendationsOutput.innerHTML = '';
    result.scrollIntoView({ behavior: 'smooth', block: 'nearest' });
    window.dispatchEvent(new CustomEvent('recommendation:priorities-ready', { detail: { profile } }));
    try {
      const response = await fetch('/api/recommendations/evaluate-demo', {
        method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ profile })
      });
      const data = await response.json();
      if (!response.ok) throw new Error(data.error || 'Не удалось рассчитать рекомендации.');
      renderRecommendationResults(data);
      if (status) status.textContent = `Подбор завершён. Найдено квартир: ${data.count}; исключено по бюджету: ${data.rejected_by_budget}.`;
    } catch (error) {
      if (status) status.textContent = `Профиль сохранён, но расчёт не выполнен: ${error.message}`;
    }
  });

  function renderRecommendationResults(data) {
    if (!recommendationsOutput) return;
    const rows = data.results || [];
    if (!rows.length) { recommendationsOutput.innerHTML = '<p>По заданным условиям квартир не найдено. Попробуйте изменить бюджет или приоритеты.</p>'; return; }
    recommendationsOutput.innerHTML = `<h3>Результаты подбора</h3><ol>${rows.slice(0, 30).map(row => `<li><strong>${escapeHtml(row.title || row.id || 'Квартира')}</strong> — ${Number(row.price || 0).toLocaleString('ru-RU')} ₽, ${row.area ?? '—'} м²; оценка: ${row.rating ?? 'нет оценки'}/100${row.market_analysis?.warning ? `; ${escapeHtml(row.market_analysis.warning.label)}` : ''}</li>`).join('')}</ol>`;
  }
  function escapeHtml(value) { return String(value).replace(/[&<>"']/g, char => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[char])); }

  form.addEventListener('reset', () => {
    window.setTimeout(() => { result.classList.remove('is-visible'); renderPrioritySummary(); }, 0);
  });

  // Публичный метод для интеграции с другими frontend-модулями.


  // Пользовательский импорт TXT: загрузка, предпросмотр и запуск того же рейтинга.
  const uploadButton = document.getElementById('custom-data-upload');
  const fileInput = document.getElementById('custom-data-file');
  const importStatus = document.getElementById('custom-data-status');
  const importPreview = document.getElementById('custom-data-preview');
  let importedListings = null;
  if (uploadButton && fileInput) {
    uploadButton.addEventListener('click', async () => {
      const file = fileInput.files && fileInput.files[0];
      if (!file) { importStatus.textContent = 'Сначала выберите TXT-файл.'; return; }
      if (file.size > 2 * 1024 * 1024) { importStatus.textContent = 'Файл больше 2 МБ.'; return; }
      uploadButton.disabled = true;
      importStatus.textContent = 'Читаем и проверяем файл…';
      try {
        const text = await file.text();
        const response = await fetch('/api/recommendations/import-text', {
          method: 'POST', headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ text, city: document.getElementById('custom-data-city')?.value || '' })
        });
        const data = await response.json();
        if (!response.ok) throw new Error(data.error || 'Не удалось обработать файл.');
        importedListings = data.results;
        const errors = data.errors || [];
        importStatus.textContent = `Распознано объявлений: ${data.count}. Пропущено блоков: ${errors.length}.`;
        importPreview.hidden = false;
        importPreview.innerHTML = `<p><strong>Предпросмотр:</strong> ${data.results.slice(0, 5).map(row => `${row.id || 'Без номера'} — ${Number(row.price).toLocaleString('ru-RU')} ₽, ${row.area} м²`).join('; ')}</p>` +
          (errors.length ? `<p>Не распознаны: ${errors.map(row => `блок ${row.block}: ${row.reason}`).join('; ')}</p>` : '') +
          '<button type="button" id="custom-data-run" class="priority-setup__continue">Подобрать квартиры из этого файла</button>';
        document.getElementById('custom-data-run').addEventListener('click', runImportedRecommendations);
      } catch (error) {
        importedListings = null;
        importPreview.hidden = true;
        importStatus.textContent = error.message;
      } finally { uploadButton.disabled = false; }
    });
  }

  async function runImportedRecommendations() {
    if (!importedListings || !importedListings.length) return;
    const profile = buildProfile();
    if (profile.budget.mode !== 'none' && Object.entries(profile.budget).some(([key, value]) => key !== 'mode' && !(value > 0))) { importStatus.textContent = 'Цена должна быть больше нуля.'; return; }
    if (profile.budget.mode === 'price_range' && profile.budget.max_price < profile.budget.min_price) { importStatus.textContent = 'Значение «До» должно быть не меньше значения «От».'; return; }
    importStatus.textContent = 'Рассчитываем рекомендации…';
    try {
      const response = await fetch('/api/recommendations/evaluate', {
        method: 'POST', headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ profile, properties: importedListings })
      });
      const data = await response.json();
      if (!response.ok) throw new Error(data.error || 'Ошибка расчёта рекомендаций.');
      importStatus.textContent = `Готово: найдено ${data.count} подходящих квартир; исключено по бюджету: ${data.rejected_by_budget}.`;
      const rows = data.results || [];
      importPreview.insertAdjacentHTML('beforeend', `<h4>Результаты подбора</h4><ol>${rows.slice(0, 20).map(row => `<li><strong>${row.id || 'Квартира'}</strong> — ${Number(row.price || 0).toLocaleString('ru-RU')} ₽, ${row.area || '—'} м²; итоговая оценка: ${row.rating ?? '—'}/100${row.market_analysis?.warning ? `; ${row.market_analysis.warning.label}` : ''}</li>`).join('')}</ol>`);
    } catch (error) { importStatus.textContent = error.message; }
  }

  window.RecommendationPriorities = {
    getCurrent() {
      try {
        const saved = sessionStorage.getItem('recommendation_priorities');
        return saved ? JSON.parse(saved) : null;
      } catch (_) { return null; }
    }
  };
})();
