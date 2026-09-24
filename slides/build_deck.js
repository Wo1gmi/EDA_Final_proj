const pptxgen = require("pptxgenjs");

const PRIMARY = "13294B";   // тёмно-синий, ЦБ/официальный тон
const SECONDARY = "5B7FA6"; // стальной синий
const ACCENT = "C9A227";    // золотой — только для ключевых находок
const INK = "1C2733";       // почти чёрный текст
const MUTED = "6B7688";     // серый текст
const CARD = "F3F5F8";      // светлая подложка карточки
const WHITE = "FFFFFF";

const FIG_DIR = "../output/figures/";

function newPres() {
  const pres = new pptxgen();
  pres.layout = "LAYOUT_WIDE"; // 13.33 x 7.5"
  return pres;
}

function darkSlide(pres) {
  const s = pres.addSlide();
  s.background = { color: PRIMARY };
  return s;
}

function lightSlide(pres) {
  const s = pres.addSlide();
  s.background = { color: WHITE };
  return s;
}

function title(s, text, opts = {}) {
  s.addText(text, {
    x: 0.6, y: 0.45, w: 12.1, h: opts.h || 0.9,
    fontFace: "Calibri", fontSize: opts.size || 30, bold: true,
    color: opts.color || INK, isTextBox: true, margin: 0,
  });
}

function pageNum(s, n, color = MUTED) {
  s.addText(String(n), {
    x: 12.6, y: 7.05, w: 0.5, h: 0.3, fontFace: "Calibri", fontSize: 10,
    color, align: "right", isTextBox: true, margin: 0,
  });
}

function statCallout(s, x, y, w, value, label, opts = {}) {
  s.addText(value, {
    x, y, w, h: opts.vh || 0.85, fontFace: "Calibri", fontSize: opts.vSize || 40, bold: true,
    color: opts.vColor || PRIMARY, align: "left", isTextBox: true, margin: 0,
  });
  s.addText(label, {
    x, y: y + (opts.vh || 0.85), w, h: opts.lh || 0.6, fontFace: "Calibri", fontSize: opts.lSize || 12,
    color: opts.lColor || MUTED, align: "left", isTextBox: true, margin: 0,
  });
}

async function build() {
  const pres = newPres();

  // ---------- 1. Титул ----------
  {
    const s = darkSlide(pres);
    s.addText("Ставка ЦБ, курс рубля\nи его волатильность", {
      x: 0.8, y: 2.1, w: 10.5, h: 2.2, fontFace: "Cambria", fontSize: 42, bold: true,
      color: WHITE, isTextBox: true, margin: 0, lineSpacingMultiple: 1.05,
    });
    s.addText("Финальный проект · Анализ экономических данных · 2026", {
      x: 0.8, y: 4.2, w: 10, h: 0.5, fontFace: "Calibri", fontSize: 16,
      color: "AEB9CC", isTextBox: true, margin: 0,
    });
    s.addText("Команда: ФИО будут указаны перед сдачей", {
      x: 0.8, y: 6.55, w: 8, h: 0.4, fontFace: "Calibri", fontSize: 12,
      color: "8592A8", isTextBox: true, margin: 0,
    });
    s.addText("2013 – 2026  ·  65 решений ЦБ  ·  3 источника данных", {
      x: 0.8, y: 6.95, w: 10, h: 0.35, fontFace: "Calibri", fontSize: 11,
      color: "8592A8", isTextBox: true, margin: 0,
    });
  }

  // ---------- 2. Вопрос ----------
  {
    const s = lightSlide(pres);
    title(s, "Вопрос");
    s.addText("Как ключевая ставка ЦБ РФ влияет на курс рубля и его волатильность,\nи с каким лагом это происходит?", {
      x: 0.6, y: 1.5, w: 11.5, h: 1.5, fontFace: "Cambria", fontSize: 24, italic: true,
      color: PRIMARY, isTextBox: true, margin: 0,
    });
    const bullets = [
      { text: "Денежный, макроэкономический вопрос: ставка — инструмент политики, курс — цена, напрямую влияющая на импорт, инфляцию, сбережения.", options: { bullet: true, breakLine: true } },
      { text: "Не причинный quasi-эксперимент (нет рандомизации ставки) — приведённая форма: VAR, тест Грейнджера, импульсные отклики.", options: { bullet: true, breakLine: true } },
      { text: "Дополнительно: меняется ли волатильность курса вокруг решений ЦБ (GARCH + событийное исследование).", options: { bullet: true, breakLine: false } },
    ];
    s.addText(bullets, { x: 0.6, y: 3.3, w: 7.6, h: 3.2, fontFace: "Calibri", fontSize: 15, color: INK, isTextBox: true, margin: 0, paraSpaceAfter: 12 });

    statCallout(s, 8.7, 3.3, 3.8, "4,25 – 21%", "диапазон ключевой ставки, 2013–2026");
    statCallout(s, 8.7, 5.1, 3.8, "65", "решений ЦБ по ставке за 13 лет");
    pageNum(s, 2);
  }

  // ---------- 3. Данные ----------
  {
    const s = lightSlide(pres);
    title(s, "Данные: три открытых источника");
    const cols = [
      { x: 0.6, h: "Ключевая ставка", src: "cbr.ru, HTML-таблица", n: "3264", rng: "17.09.2013 – 23.09.2026" },
      { x: 4.7, h: "Курс USD/RUB", src: "cbr.ru, XML (официальный фиксинг)", n: "3385", rng: "10.01.2013 – 23.09.2026" },
      { x: 8.8, h: "Нефть Brent", src: "FRED, DCOILBRENTEU", n: "3581", rng: "01.01.2013 – 22.09.2026" },
    ];
    cols.forEach((c) => {
      s.addShape("roundRect", { x: c.x, y: 1.55, w: 3.7, h: 2.7, fill: { color: CARD }, line: { type: "none" }, rectRadius: 0.08 });
      s.addText(c.h, { x: c.x + 0.25, y: 1.75, w: 3.2, h: 0.5, fontFace: "Calibri", fontSize: 16, bold: true, color: PRIMARY, isTextBox: true, margin: 0 });
      s.addText(c.src, { x: c.x + 0.25, y: 2.25, w: 3.2, h: 0.5, fontFace: "Calibri", fontSize: 11, color: MUTED, isTextBox: true, margin: 0 });
      s.addText(c.n, { x: c.x + 0.25, y: 2.85, w: 3.2, h: 0.7, fontFace: "Calibri", fontSize: 30, bold: true, color: SECONDARY, isTextBox: true, margin: 0 });
      s.addText("наблюдений · " + c.rng, { x: c.x + 0.25, y: 3.55, w: 3.2, h: 0.6, fontFace: "Calibri", fontSize: 10, color: MUTED, isTextBox: true, margin: 0 });
    });
    s.addText([
      { text: "Ставка — ступенчатая функция: 3264 дневных значения, но всего ", options: {} },
      { text: "65 фактических изменений", options: { bold: true, color: PRIMARY } },
      { text: " (~5 в год).", options: {} },
    ], { x: 0.6, y: 4.55, w: 12.0, h: 0.5, fontFace: "Calibri", fontSize: 14, color: INK, isTextBox: true, margin: 0 });
    s.addText([
      { text: "Курс и ставка обязательно моделируются вместе с нефтью: без контроля на неё эффект ставки на курс путается с сырьевым циклом (корреляция курс–нефть −0,14 по уровням).", options: {} },
    ], { x: 0.6, y: 5.15, w: 12.0, h: 0.6, fontFace: "Calibri", fontSize: 14, color: INK, isTextBox: true, margin: 0 });
    s.addText("Два структурных слома видны прямо в данных: экстренное повышение ставки до 20% 28.02.2022 (пик курса 120,4 ₽/$ 11.03.2022) и цикл ужесточения 2023–2024 до исторического максимума 21%.", {
      x: 0.6, y: 5.95, w: 12.0, h: 0.8, fontFace: "Calibri", fontSize: 13, italic: true, color: MUTED, isTextBox: true, margin: 0,
    });
    pageNum(s, 3);
  }

  // ---------- 4. Скрытая ловушка в датах ----------
  {
    const s = lightSlide(pres);
    title(s, "Проверка вместо доверия: даты решений не совпадали");
    s.addText("Дата в выгрузке курса — дата действия официального фиксинга (T+1 от торговой сессии).\nДата в выгрузке ставки — дата вступления решения в силу. Разные конвенции — разные даты.", {
      x: 0.6, y: 1.55, w: 12.0, h: 1.0, fontFace: "Calibri", fontSize: 15, color: INK, isTextBox: true, margin: 0,
    });

    const before = { x: 1.3, label: "До проверки", value: "5 / 65", note: "дат совпало напрямую" };
    const after = { x: 7.3, label: "После сдвига на +1 день", value: "65 / 65", note: "дат совпало точно" };
    [before, after].forEach((b, i) => {
      s.addShape("roundRect", { x: b.x, y: 2.9, w: 4.3, h: 2.5, fill: { color: i === 0 ? CARD : PRIMARY }, line: { type: "none" }, rectRadius: 0.08 });
      s.addText(b.label, { x: b.x + 0.3, y: 3.1, w: 3.7, h: 0.5, fontFace: "Calibri", fontSize: 14, bold: true, color: i === 0 ? MUTED : "AEB9CC", isTextBox: true, margin: 0 });
      s.addText(b.value, { x: b.x + 0.3, y: 3.6, w: 3.7, h: 1.0, fontFace: "Calibri", fontSize: 44, bold: true, color: i === 0 ? "B23B3B" : ACCENT, isTextBox: true, margin: 0 });
      s.addText(b.note, { x: b.x + 0.3, y: 4.65, w: 3.7, h: 0.5, fontFace: "Calibri", fontSize: 12, color: i === 0 ? MUTED : "CADCFC", isTextBox: true, margin: 0 });
    });
    s.addText("Проверка встроена в код: скрипт останавливается с ошибкой, если совпадений не 65 — не полагаемся на то, что «выглядит похоже».", {
      x: 0.6, y: 5.75, w: 11.5, h: 0.8, fontFace: "Calibri", fontSize: 13, italic: true, color: MUTED, isTextBox: true, margin: 0,
    });
    pageNum(s, 4);
  }

  // ---------- 5. Дизайн: два слоя ----------
  {
    const s = lightSlide(pres);
    title(s, "Дизайн: два слоя, две частоты");
    const layers = [
      {
        x: 0.6, color: PRIMARY, h: "Слой 1 · месячные данные",
        items: ["VAR в первых разностях", "Тест Грейнджера (обе стороны, с нефтью и без)", "Импульсные отклики (IRF)"],
      },
      {
        x: 6.8, color: SECONDARY, h: "Слой 2 · дневные данные",
        items: ["GARCH(1,1) на доходностях курса", "Диагностика остатков (Ljung-Box)", "Событийное исследование вокруг 65 решений + плацебо"],
      },
    ];
    layers.forEach((l) => {
      s.addShape("roundRect", { x: l.x, y: 1.6, w: 5.9, h: 4.6, fill: { color: CARD }, line: { type: "none" }, rectRadius: 0.08 });
      s.addShape("roundRect", { x: l.x + 0.35, y: 1.95, w: 0.25, h: 0.25, fill: { color: l.color }, line: { type: "none" } });
      s.addText(l.h, { x: l.x + 0.8, y: 1.85, w: 4.7, h: 0.5, fontFace: "Calibri", fontSize: 17, bold: true, color: l.color, isTextBox: true, margin: 0 });
      const items = l.items.map((t, i) => ({ text: t, options: { bullet: true, breakLine: i < l.items.length - 1 } }));
      s.addText(items, { x: l.x + 0.4, y: 2.6, w: 5.1, h: 3.3, fontFace: "Calibri", fontSize: 15, color: INK, isTextBox: true, margin: 0, paraSpaceAfter: 14 });
    });
    s.addText("Почему раздельно: ставка меняется реже раза в два месяца — дневной шум испортит VAR. Волатильность, наоборот, нельзя оценить на 157 месячных точках.", {
      x: 0.6, y: 6.35, w: 12.0, h: 0.7, fontFace: "Calibri", fontSize: 13, italic: true, color: MUTED, isTextBox: true, margin: 0,
    });
    pageNum(s, 5);
  }

  // ---------- 6. Спецификация: коинтеграция ----------
  {
    const s = lightSlide(pres);
    title(s, "Спецификация выбрана тестом, а не наугад");
    s.addText("Лаг для теста Йохансена подобран по данным (BIC/AIC/HQIC/FPE → p=3 → k_ar_diff=2), не взят произвольно.", {
      x: 0.6, y: 1.5, w: 12.0, h: 0.6, fontFace: "Calibri", fontSize: 15, color: INK, isTextBox: true, margin: 0,
    });

    const rows = [
      [{ text: "k_ar_diff", options: { bold: true, fill: { color: PRIMARY }, color: WHITE } }, { text: "Ранг коинтеграции", options: { bold: true, fill: { color: PRIMARY }, color: WHITE } }, { text: "Решение", options: { bold: true, fill: { color: PRIMARY }, color: WHITE } }],
      ["1 (произвольный)", "1 (на границе: 14,96 vs 15,49)", "VECM — альтернатива"],
      ["2 (по данным, основной)", "0", "VAR в разностях — основная модель"],
      ["3", "0", "подтверждает k=2"],
    ];
    s.addTable(rows, {
      x: 0.6, y: 2.3, w: 12.0, h: 2.0, fontFace: "Calibri", fontSize: 14, color: INK,
      border: { type: "solid", color: "E3E7ED", pt: 1 }, autoPage: false,
      colW: [3.5, 4.5, 4.0],
    });

    s.addText([
      { text: "Ранг неустойчив к выбору лага ", options: { bold: true, color: PRIMARY } },
      { text: "— это не техническая деталь, а содержательный вывод: свидетельство долгосрочной связи слабое, поэтому в основу модели его не кладём. Обе спецификации считаются и сравниваются на всех дальнейших шагах.", options: {} },
    ], { x: 0.6, y: 4.55, w: 12.0, h: 1.2, fontFace: "Calibri", fontSize: 14, color: INK, isTextBox: true, margin: 0 });
    pageNum(s, 6);
  }

  // ---------- 7. Р1 три ряда ----------
  {
    const s = lightSlide(pres);
    title(s, "Три ряда во времени");
    // исходное изображение 1350x1200 px (w:h = 1.125); h=5.7 -> w=6.41
    s.addImage({ path: FIG_DIR + "R1_three_series.png", x: 3.46, y: 1.4, w: 6.41, h: 5.7 });
    pageNum(s, 7);
  }

  // ---------- 8. Грейнджер, полная выборка ----------
  {
    const s = lightSlide(pres);
    title(s, "Тест Грейнджера: асимметрия на полной выборке");
    statCallout(s, 0.8, 1.8, 5.5, "F = 50,2\np < 0,0001", "ставка → курс\n(с нефтью в системе и без — не меняется)", { vSize: 34, vColor: PRIMARY, lSize: 13, vh: 1.5, lh: 1.0 });
    statCallout(s, 7.0, 1.8, 5.5, "F = 5,4\np = 0,005", "курс → ставка\n(значимо, но на порядок слабее)", { vSize: 34, vColor: SECONDARY, lSize: 13, vh: 1.5, lh: 1.0 });
    s.addShape("line", { x: 6.55, y: 1.9, w: 0, h: 3.0, line: { color: "E3E7ED", width: 1.5 } });
    s.addText("Результат совпадает в двух спецификациях (VAR-в-разностях и VECM) и с контролем на нефть, и без — но, как покажет следующий слайд, не совпадает по подпериодам.", {
      x: 0.8, y: 5.5, w: 11.7, h: 1.0, fontFace: "Calibri", fontSize: 14, italic: true, color: MUTED, isTextBox: true, margin: 0,
    });
    pageNum(s, 8);
  }

  // ---------- 9. ГЛАВНАЯ находка ----------
  {
    const s = darkSlide(pres);
    s.addShape("roundRect", { x: 0.5, y: 0.45, w: 3.0, h: 0.4, fill: { color: ACCENT }, line: { type: "none" }, rectRadius: 0.06 });
    s.addText("ГЛАВНАЯ НАХОДКА", { x: 0.5, y: 0.45, w: 3.0, h: 0.4, fontFace: "Calibri", fontSize: 13, bold: true, color: PRIMARY, align: "center", valign: "middle", isTextBox: true, margin: 0 });
    s.addText("Результат переворачивается внутри подпериодов", {
      x: 0.6, y: 1.05, w: 12.0, h: 0.9, fontFace: "Cambria", fontSize: 27, bold: true, color: WHITE, isTextBox: true, margin: 0,
    });

    const rows = [
      [{ text: "", options: { fill: { color: PRIMARY } } }, { text: "ставка → курс", options: { bold: true, color: WHITE, fill: { color: PRIMARY } } }, { text: "курс → ставка", options: { bold: true, color: WHITE, fill: { color: PRIMARY } } }],
      [{ text: "Вся выборка", options: { bold: true } }, { text: "p < 0,0001", options: { color: "1C7C3E", bold: true } }, { text: "p = 0,005", options: { color: "1C7C3E" } }],
      [{ text: "До 28.02.2022", options: { bold: true } }, { text: "p = 0,062", options: { color: "B23B3B" } }, { text: "p = 0,040", options: { color: "1C7C3E", bold: true } }],
      [{ text: "После 28.02.2022", options: { bold: true } }, { text: "p = 0,779", options: { color: "B23B3B" } }, { text: "p < 0,0001", options: { color: "1C7C3E", bold: true } }],
    ];
    s.addTable(rows, {
      x: 0.6, y: 2.15, w: 12.0, h: 2.3, fontFace: "Calibri", fontSize: 15, color: INK,
      fill: { color: WHITE }, border: { type: "solid", color: "E3E7ED", pt: 1 }, autoPage: false,
      colW: [4.0, 4.0, 4.0], align: "center",
    });

    s.addText([
      { text: "Внутри каждого режима курс предсказывает ставку, а не наоборот. ", options: { bold: true, color: ACCENT } },
      { text: "Полновыборочный результат, скорее всего, порождён самим фактом одновременного слома обоих рядов в 2022 году — не устойчивой внутрирежимной динамикой.", options: { color: "CADCFC" } },
    ], { x: 0.6, y: 4.75, w: 12.0, h: 1.3, fontFace: "Calibri", fontSize: 16, isTextBox: true, margin: 0 });
    pageNum(s, 9, "8592A8");
  }

  // ---------- 10. IRF ----------
  {
    const s = lightSlide(pres);
    title(s, "Импульсный отклик курса на шок ставки");
    // исходное изображение 1125x750 px (w:h = 1.5); h=3.9 -> w=5.85
    s.addImage({ path: FIG_DIR + "R2_irf_rate_to_fx.png", x: 3.74, y: 1.35, w: 5.85, h: 3.9 });
    s.addText([
      { text: "Пик на 1-м месяце (+3–4%), разворот в минус на 2–3 месяце, гаснет к 9–10 месяцу.", options: { bullet: true, breakLine: true } },
      { text: "Знак и масштаб пика устойчивы к порядку переменных в ортогонализации (3 варианта, разброс 0,026–0,031).", options: { bullet: true, breakLine: true } },
      { text: "Контринтуитивно относительно паритета ставок — согласуется с обратной причинностью (слайд 9).", options: { bullet: true, breakLine: false } },
    ], { x: 0.6, y: 5.3, w: 12.0, h: 1.8, fontFace: "Calibri", fontSize: 13, color: INK, isTextBox: true, margin: 0, paraSpaceAfter: 6 });
    pageNum(s, 10);
  }

  // ---------- 11. GARCH ----------
  {
    const s = lightSlide(pres);
    title(s, "GARCH(1,1): волатильность курса кластеризована");
    statCallout(s, 0.6, 1.6, 3.7, "p ≈ 0", "ARCH-LM тест: волатильность точно кластеризована", { vSize: 34 });
    statCallout(s, 4.6, 1.6, 3.7, "α+β ≈ 0,98", "персистентность шоков волатильности, весь период", { vSize: 34, vColor: SECONDARY });
    statCallout(s, 8.6, 1.6, 3.7, "0,029→0,061", "базовая дисперсия (ω): до → после 28.02.2022", { vSize: 26, vColor: ACCENT });
    // исходное изображение 1350x675 px (w:h = 2.0); h=3.2 -> w=6.4
    s.addImage({ path: FIG_DIR + "R3_conditional_volatility.png", x: 3.47, y: 3.85, w: 6.4, h: 3.2 });
    pageNum(s, 11);
  }

  // ---------- 12. Событийное исследование ----------
  {
    const s = lightSlide(pres);
    title(s, "Волатильность вокруг решений ЦБ выше случайной");
    s.addText("Окно ±5 торговых дней вокруг каждого из 65 решений, сравнение с 1000 случайных плацебо-наборов той же длины.", {
      x: 0.6, y: 1.5, w: 12.0, h: 0.6, fontFace: "Calibri", fontSize: 14, color: INK, isTextBox: true, margin: 0,
    });
    const rows = [
      [{ text: "", options: { fill: { color: PRIMARY } } }, { text: "Наблюдаемое", options: { bold: true, color: WHITE, fill: { color: PRIMARY } } }, { text: "Плацебо (среднее)", options: { bold: true, color: WHITE, fill: { color: PRIMARY } } }, { text: "p-значение", options: { bold: true, color: WHITE, fill: { color: PRIMARY } } }],
      ["|доходность|, %", "0,92", "0,68", { text: "0,000", options: { bold: true, color: "1C7C3E" } }],
      ["Условная волатильность", "1,16", "0,95", { text: "0,002", options: { bold: true, color: "1C7C3E" } }],
    ];
    s.addTable(rows, {
      x: 0.6, y: 2.35, w: 12.0, h: 1.6, fontFace: "Calibri", fontSize: 15, color: INK,
      border: { type: "solid", color: "E3E7ED", pt: 1 }, autoPage: false,
      colW: [4.0, 2.7, 2.7, 2.6], align: "center",
    });
    s.addText("Наблюдаемое значение выше всех 1000 плацебо-перестановок по |доходности| — результат не объясняется случайным совпадением дат.", {
      x: 0.6, y: 4.3, w: 12.0, h: 0.8, fontFace: "Calibri", fontSize: 13, italic: true, color: MUTED, isTextBox: true, margin: 0,
    });
    pageNum(s, 12);
  }

  // ---------- 13. Ответ + ограничения ----------
  {
    const s = lightSlide(pres);
    title(s, "Ответ на вопрос и ограничения");
    s.addShape("roundRect", { x: 0.6, y: 1.5, w: 5.7, h: 4.7, fill: { color: CARD }, line: { type: "none" }, rectRadius: 0.08 });
    s.addText("Ответ", { x: 0.9, y: 1.75, w: 5.1, h: 0.4, fontFace: "Calibri", fontSize: 16, bold: true, color: PRIMARY, isTextBox: true, margin: 0 });
    s.addText([
      { text: "Устойчивой поддержки идее «ставка предсказывает курс» в данных нет.", options: { bullet: true, breakLine: true } },
      { text: "Устойчиво обратное: курс предсказывает решения по ставке — ЦБ реагирует на курс/инфляцию, а не наоборот.", options: { bullet: true, breakLine: true } },
      { text: "Волатильность курса вокруг решений выше случайной — это надёжно.", options: { bullet: true, breakLine: false } },
    ], { x: 0.9, y: 2.3, w: 5.1, h: 3.7, fontFace: "Calibri", fontSize: 13, color: INK, isTextBox: true, margin: 0, paraSpaceAfter: 10 });

    s.addShape("roundRect", { x: 6.65, y: 1.5, w: 5.9, h: 4.7, fill: { color: PRIMARY }, line: { type: "none" }, rectRadius: 0.08 });
    s.addText("Ограничения", { x: 6.95, y: 1.75, w: 5.3, h: 0.4, fontFace: "Calibri", fontSize: 16, bold: true, color: ACCENT, isTextBox: true, margin: 0 });
    s.addText([
      { text: "Официальный фиксинг ≠ рыночная сделка, особенно после 2022.", options: { bullet: true, breakLine: true } },
      { text: "Три переменные — упрощение (нет ставки ФРС, санкционного индекса).", options: { bullet: true, breakLine: true } },
      { text: "IRF зависит от порядка ортогонализации (проверено, но не единственно).", options: { bullet: true, breakLine: true } },
      { text: "GARCH не до конца объясняет автокорреляцию в уровне доходностей.", options: { bullet: true, breakLine: true } },
      { text: "Грейнджер — про предсказуемость, не про причинность.", options: { bullet: true, breakLine: false } },
    ], { x: 6.95, y: 2.3, w: 5.3, h: 3.7, fontFace: "Calibri", fontSize: 13, color: WHITE, isTextBox: true, margin: 0, paraSpaceAfter: 10 });
    pageNum(s, 13);
  }

  // ---------- 14. Авторы / репозиторий ----------
  {
    const s = darkSlide(pres);
    s.addText("Спасибо. Вопросы?", {
      x: 0.8, y: 2.3, w: 10, h: 1.0, fontFace: "Cambria", fontSize: 36, bold: true, color: WHITE, isTextBox: true, margin: 0,
    });
    s.addText("Команда: ФИО будут указаны перед сдачей", {
      x: 0.8, y: 3.5, w: 10, h: 0.5, fontFace: "Calibri", fontSize: 15, color: "CADCFC", isTextBox: true, margin: 0,
    });
    s.addText("Код, данные (загружаются автоматически) и инструкция — в репозитории проекта, README.md.\nПолный прогон с нуля (проверено дважды, включая чистое окружение): 12 секунд (лимит задания — 30 минут).", {
      x: 0.8, y: 4.1, w: 10.5, h: 1.0, fontFace: "Calibri", fontSize: 13, color: "8592A8", isTextBox: true, margin: 0,
    });
    pageNum(s, 14, "8592A8");
  }

  await pres.writeFile({ fileName: "presentation.pptx" });
  console.log("OK: presentation.pptx");
}

build().catch((e) => { console.error(e); process.exit(1); });
