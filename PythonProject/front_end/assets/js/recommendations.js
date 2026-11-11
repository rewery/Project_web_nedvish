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

  // Восстанавливаем весь профиль, включая бюджет и площадь, после возврата со страницы сравнения.
  let savedProfile = null;
  try {
    const rawProfile = sessionStorage.getItem('recommendation_priorities');
    savedProfile = rawProfile ? JSON.parse(rawProfile) : null;
  } catch (_) { savedProfile = null; }

  Object.entries(initialProfile).forEach(([name, defaultValue]) => {
    const savedLevel = savedProfile?.priorities?.[name]?.level || defaultValue;
    const input = form.querySelector(`input[name="${name}"][value="${savedLevel}"]`)
      || form.querySelector(`input[name="${name}"][value="${defaultValue}"]`);
    if (input) input.checked = true;
  });
  const savedMinPrice = savedProfile?.budget?.min_price;
  const savedMaxPrice = savedProfile?.budget?.max_price;
  const minPriceInput = form.querySelector('[name="min_price"]');
  const maxPriceInput = form.querySelector('[name="max_price"]');
  const areaInput = form.querySelector('[name="target_area"]');
  if (minPriceInput && savedMinPrice != null) minPriceInput.value = formatThousands(savedMinPrice);
  if (maxPriceInput && savedMaxPrice != null) maxPriceInput.value = formatThousands(savedMaxPrice);
  if (areaInput && savedProfile?.target_area != null) areaInput.value = savedProfile.target_area;

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
    result.classList.add('is-visible');
    if (status) status.textContent = importedListings ? 'Рассчитываем подбор по загруженному TXT-файлу…' : 'Рассчитываем подбор по демонстрационной базе…';
    if (recommendationsOutput) recommendationsOutput.innerHTML = '';
    result.scrollIntoView({ behavior: 'smooth', block: 'nearest' });
    window.dispatchEvent(new CustomEvent('recommendation:priorities-ready', { detail: { profile } }));
    try {
      const response = await fetch(importedListings ? '/api/recommendations/evaluate' : '/api/recommendations/evaluate-demo', {
        method: 'POST', headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(importedListings ? { profile, properties: importedListings } : { profile })
      });
      const data = await response.json();
      if (!response.ok) throw new Error(data.error || 'Не удалось рассчитать рекомендации.');
      renderRecommendationResults(data);
      // Результаты тоже сохраняются: при повторном открытии страницы не нужно запускать подбор заново.
      try { sessionStorage.setItem('recommendation_results', JSON.stringify(data)); } catch (_) {}
      if (status) status.textContent = `Подбор завершён. Найдено квартир: ${data.count}; исключено по бюджету: ${data.rejected_by_budget ?? 0}.`;
    } catch (error) {
      if (status) status.textContent = `Профиль сохранён, но расчёт не выполнен: ${error.message}`;
    }
  });

  function renderRecommendationResults(data, target = recommendationsOutput) {
    if (!target) return;
    // Убираем повторно пришедшие объявления до построения карточек.
    const sourceRows = Array.isArray(data.results) ? data.results : [];
    const seenListings = new Set();
    const uniqueRows = sourceRows.filter(row => {
      const identity = row.id != null && String(row.id).trim()
        ? 'id:' + String(row.id).trim()
        : [row.title, row.price, row.area, row.rooms, row.apartment_floor ?? row.floor]
            .map(value => String(value ?? '').trim().toLocaleLowerCase('ru-RU')).join('|');
      if (seenListings.has(identity)) return false;
      seenListings.add(identity);
      return true;
    });
    const shortlist = uniqueRows.slice(0, 6);
    if (!shortlist.length) {
      target.innerHTML = '<p class="recommendation-empty">По заданным условиям квартир не найдено. Попробуйте изменить бюджет или приоритеты.</p>';
      return;
    }

    const labels = { price: 'Стоимость', area: 'Площадь квартиры', building_condition: 'Состояние дома',
      metro: 'Близость к метро', kindergarten: 'Детские сады', school: 'Школы', city_center: 'Близость к центру' };
    const sortLabels = { relevance: 'По соответствию', price_asc: 'Сначала дешевле', price_desc: 'Сначала дороже',
      area_asc: 'По возрастанию площади', area_desc: 'По убыванию площади', floor_asc: 'По этажу' };
    const number = value => value == null || value === '' || !Number.isFinite(Number(value)) ? '—' : Number(value).toLocaleString('ru-RU');
    const safe = value => escapeHtml(value == null ? '' : String(value));
    const floor = row => row.apartment_floor ?? row.floor;
    const selected = new Set();
    const keyOf = (row, index) => String(row.id ?? row.title ?? index);

    const sorted = mode => {
      const rows = shortlist.map((row,index) => ({ row,index }));
      const val = (row,key) => Number.isFinite(Number(row[key])) && row[key] !== null && row[key] !== '' ? Number(row[key]) : null;
      if (mode === 'price_asc' || mode === 'price_desc') rows.sort((a,b) => {
        const x=val(a.row,'price'), y=val(b.row,'price');
        return x===null ? 1 : y===null ? -1 : (mode==='price_asc' ? x-y : y-x);
      });
      else if (mode === 'area_asc' || mode === 'area_desc') rows.sort((a,b) => {
        const x=val(a.row,'area'), y=val(b.row,'area');
        return x===null ? 1 : y===null ? -1 : (mode==='area_asc' ? x-y : y-x);
      });
      else if (mode === 'floor_asc') rows.sort((a,b) => (Number(floor(a.row))||Infinity)-(Number(floor(b.row))||Infinity));
      else rows.sort((a,b) => (b.row.rating ?? -1)-(a.row.rating ?? -1));
      return rows;
    };

    const details = row => {
      const scores = Array.isArray(row.criterion_details) ? row.criterion_details : [];
      const missing = Array.isArray(row.missing_criteria) ? row.missing_criteria : [];
      if (!scores.length && !missing.length) return '<div class="recommendation-analysis"><h4>Почему квартира в подборке</h4><p class="recommendation-note">Недостаточно характеристик объявления, чтобы подробно объяснить оценку. Квартира оставлена в подборке по общему результату расчёта.</p></div>';
      const scoreRows = scores.map(item => '<tr><th>'+safe(item.label || labels[item.criterion] || item.criterion)+'</th><td>'+number(item.score)+'/100</td><td>Учтено</td></tr>').join('');
      const missingRows = missing.map(label => '<tr><th>'+safe(label)+'</th><td>—</td><td>Нет данных</td></tr>').join('');
      return '<div class="recommendation-analysis"><h4>Почему квартира в подборке</h4><p>'+safe(row.explanation || 'Оценка рассчитана по доступным приоритетам.')+'</p><div class="recommendation-table-wrap"><table class="recommendation-analysis-table"><thead><tr><th>Критерий</th><th>Оценка</th><th>Статус</th></tr></thead><tbody>'+scoreRows+missingRows+'</tbody></table></div></div>';
    };

    const render = mode => {
      const rows = sorted(mode);
      target.innerHTML = '<div class="recommendation-toolbar"><div><h3>Результаты подбора</h3><p>6 лучших вариантов. Сортировка меняет порядок, но не пересчитывает рейтинг.</p></div><label class="recommendation-sort">Сортировать <select id="recommendation-sort">'+Object.entries(sortLabels).map(([v,l])=>'<option value="'+v+'" '+(v===mode?'selected':'')+'>'+l+'</option>').join('')+'</select></label></div>'+
        '<div class="recommendation-compare-bar"><span>Для сравнения: <strong id="recommendation-compare-count">'+selected.size+'</strong> / 3</span><button type="button" id="recommendation-compare-open" '+(selected.size<2?'disabled':'')+'>Сравнить</button></div>'+
        '<div class="recommendation-grid">'+rows.map(({row,index})=>{
          const score=row.rating==null?'Нет оценки':number(row.rating)+' / 100';
          const scoreClass=row.rating==null?'is-unrated':row.rating>=80?'is-high':row.rating>=60?'is-medium':'is-low';
          const warning=row.market_analysis?.warning?.label;
          return '<article class="recommendation-card"><div class="recommendation-card__visual"><span class="recommendation-card__number">Вариант '+(index+1)+'</span><span class="recommendation-card__score '+scoreClass+'">'+score+'</span><div class="recommendation-card__visual-caption">Подбор недвижимости</div></div><div class="recommendation-card__body"><h4>'+safe(row.title || row.id || 'Квартира')+'</h4><div class="recommendation-card__price">'+number(row.price)+' ₽</div><div class="recommendation-card__facts"><span>'+safe(row.rooms ?? '—')+' комн.</span><span>'+number(row.area)+' м²</span><span>Этаж '+safe(floor(row) ?? '—')+(row.building_floors?' / '+safe(row.building_floors):'')+'</span></div>'+(warning?'<p class="recommendation-warning">'+safe(warning)+'</p>':'')+'<label class="recommendation-compare-check"><input type="checkbox" data-compare="'+safe(keyOf(row,index))+'" '+(selected.has(keyOf(row,index))?'checked':'')+'> Добавить к сравнению</label>' +details(row)+'</div></article>';
        }).join('')+'</div><div id="recommendation-comparison"></div>';
      target.querySelector('#recommendation-sort')?.addEventListener('change',event=>render(event.target.value));
      target.querySelectorAll('[data-compare]').forEach(input=>input.addEventListener('change',()=>{
        const id=input.dataset.compare;
        if(input.checked && selected.size>=3){input.checked=false;return;}
        if(input.checked) selected.add(id); else selected.delete(id);
        render(mode);
      }));
      target.querySelector('#recommendation-compare-open')?.addEventListener('click',()=>{
        const chosen=rows.filter(({row,index})=>selected.has(keyOf(row,index))).map(x=>x.row);
        if (chosen.length < 2) return;
        try {
          sessionStorage.setItem('recommendation_comparison_items', JSON.stringify(chosen));
          window.location.href = 'compare.html';
        } catch (_) {
          if (status) status.textContent = 'Не удалось открыть сравнение. Попробуйте ещё раз.';
        }
      });
    };
    render('relevance');
  }
  function escapeHtml(value) { return String(value).replace(/[&<>"']/g, char => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[char])); }

  form.addEventListener('reset', () => {
    window.setTimeout(() => {
      result.classList.remove('is-visible');
      renderPrioritySummary();
      try {
        sessionStorage.removeItem('recommendation_priorities');
        sessionStorage.removeItem('recommendation_results');
      } catch (_) {}
    }, 0);
  });

  // Публичный метод для интеграции с другими frontend-модулями.


  // Пользовательский импорт TXT: загрузка, предпросмотр и запуск того же рейтинга.
  const uploadButton = document.getElementById('custom-data-upload');
  const fileInput = document.getElementById('custom-data-file');
  const importStatus = document.getElementById('custom-data-status');
  const importPreview = document.getElementById('custom-data-preview');
  let importedListings = null;
  try {
    const savedListings = sessionStorage.getItem('recommendation_imported_listings');
    importedListings = savedListings ? JSON.parse(savedListings) : null;
  } catch (_) { importedListings = null; }
  // Восстанавливаем результаты подбора и показываем сводную таблицу при повторной загрузке страницы.
  if (savedProfile) renderPrioritySummary();
  try {
    const savedResults = sessionStorage.getItem('recommendation_results');
    if (savedResults) {
      const parsedResults = JSON.parse(savedResults);
      if (parsedResults && Array.isArray(parsedResults.results)) {
        result.classList.add('is-visible');
        renderRecommendationResults(parsedResults);
        if (status) status.textContent = `Подбор завершён. Найдено квартир: ${parsedResults.count ?? parsedResults.results.length}; исключено по бюджету: ${parsedResults.rejected_by_budget ?? 0}.`;
      }
    }
  } catch (_) {}

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
        try { sessionStorage.setItem('recommendation_imported_listings', JSON.stringify(importedListings)); } catch (_) {}
        const errors = data.errors || [];
        importStatus.textContent = `Файл загружен и сохранён для подбора. Распознано объявлений: ${data.count}; пропущено блоков: ${errors.length}. Теперь нажмите «Продолжаем», чтобы увидеть результаты.`;
        if (importPreview) { importPreview.hidden = true; importPreview.innerHTML = ''; }
      } catch (error) {
        importedListings = null;
        try { sessionStorage.removeItem('recommendation_imported_listings'); } catch (_) {}
        importPreview.hidden = true;
        importStatus.textContent = error.message;
      } finally { uploadButton.disabled = false; }
    });
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
