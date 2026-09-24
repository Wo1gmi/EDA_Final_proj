const pptxgen = require("pptxgenjs");

const PRIMARY = "13294B";   // тёмно-синий, ЦБ/официальный тон
const SECONDARY = "5B7FA6"; // стальной синий
const ACCENT = "C9A227";    // золотой — только для ключевых находок
const RED = "B23B3B";
const GREEN = "1C7C3E";
const INK = "1C2733";
const MUTED = "6B7688";
const CARD = "F3F5F8";
const WHITE = "FFFFFF";

const FIG_DIR = "../output/figures/";

function newPres() {
  const pres = new pptxgen();
  pres.layout = "LAYOUT_WIDE";
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
    fontFace: "Calibri", fontSize: opts.size || 27, bold: true,
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
    x, y, w, h: opts.vh || 0.7, fontFace: "Calibri", fontSize: opts.vSize || 30, bold: true,
    color: opts.vColor || PRIMARY, align: "left", isTextBox: true, margin: 0,
  });
  s.addText(label, {
    x, y: y + (opts.vh || 0.7), w, h: opts.lh || 0.6, fontFace: "Calibri", fontSize: opts.lSize || 11,
    color: opts.lColor || MUTED, align: "left", isTextBox: true, margin: 0,
  });
}

async function build() {
  const pres = newPres();

  // ---------- 1. Титул ----------
  {
    const s = darkSlide(pres);
    s.addText("Ставка ЦБ, курс рубля\nи его волатильность", {
      x: 0.8, y: 2.0, w: 10.5, h: 2.0, fontFace: "Cambria", fontSize: 40, bold: true,
      color: WHITE, isTextBox: true, margin: 0, lineSpacingMultiple: 1.05,
    });
    s.addText("Финальный проект · Анализ экономических данных · 2026", {
      x: 0.8, y: 4.0, w: 10, h: 0.5, fontFace: "Calibri", fontSize: 16,
      color: "AEB9CC", isTextBox: true, margin: 0,
    });
    s.addText("Команда: ФИО будут указаны перед сдачей", {
      x: 0.8, y: 6.45, w: 8, h: 0.4, fontFace: "Calibri", fontSize: 12,
      color: "8592A8", isTextBox: true, margin: 0,
    });
    s.addText("2013 – 2026  ·  65 решений ЦБ  ·  связь видна только в кризис", {
      x: 0.8, y: 6.85, w: 11, h: 0.35, fontFace: "Calibri", fontSize: 11,
      color: "8592A8", isTextBox: true, margin: 0,
    });
    s.addNotes(
      "Резюме в одном предложении: связь между ставкой и курсом статистически значима на полной выборке, " +
      "но целиком объясняется семью кризисными месяцами из 156 — при их нейтрализации значимость исчезает."
    );
  }

  // ---------- 2. Вопрос ----------
  {
    const s = lightSlide(pres);
    title(s, "Вопрос");
    s.addText(
      "Есть ли связь по времени между решениями ЦБ по ставке, курсом рубля\nи его волатильностью, и в каком направлении идёт предсказуемость?",
      { x: 0.6, y: 1.5, w: 11.8, h: 1.5, fontFace: "Cambria", fontSize: 22, italic: true, color: PRIMARY, isTextBox: true, margin: 0 }
    );
    const bullets = [
      { text: "Денежный, макроэкономический вопрос: ставка — инструмент политики, курс — цена, напрямую влияющая на импорт, инфляцию, сбережения.", options: { bullet: true, breakLine: true } },
      { text: "Дизайн предсказательный (VAR, Грейнджер, IRF, GARCH), не причинный — намеренно: нет рандомизации ставки, вопрос про предсказуемость, а не про эффект.", options: { bullet: true, breakLine: true } },
      { text: "«Влияет» и «предсказывает» — разные слова, и мы различаем их до конца презентации, не только на этом слайде.", options: { bullet: true, breakLine: false } },
    ];
    s.addText(bullets, { x: 0.6, y: 3.3, w: 7.6, h: 3.2, fontFace: "Calibri", fontSize: 15, color: INK, isTextBox: true, margin: 0, paraSpaceAfter: 12 });
    statCallout(s, 8.7, 3.3, 3.8, "4,25 – 21%", "диапазон ключевой ставки, 2013–2026");
    statCallout(s, 8.7, 5.0, 3.8, "65", "решений ЦБ по ставке за 13 лет");
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
      s.addShape("roundRect", { x: c.x, y: 1.5, w: 3.7, h: 2.3, fill: { color: CARD }, line: { type: "none" }, rectRadius: 0.08 });
      s.addText(c.h, { x: c.x + 0.25, y: 1.68, w: 3.2, h: 0.5, fontFace: "Calibri", fontSize: 15, bold: true, color: PRIMARY, isTextBox: true, margin: 0 });
      s.addText(c.src, { x: c.x + 0.25, y: 2.14, w: 3.2, h: 0.5, fontFace: "Calibri", fontSize: 10, color: MUTED, isTextBox: true, margin: 0 });
      s.addText(c.n, { x: c.x + 0.25, y: 2.65, w: 3.2, h: 0.6, fontFace: "Calibri", fontSize: 26, bold: true, color: SECONDARY, isTextBox: true, margin: 0 });
      s.addText("наблюдений · " + c.rng, { x: c.x + 0.25, y: 3.25, w: 3.2, h: 0.55, fontFace: "Calibri", fontSize: 9.5, color: MUTED, isTextBox: true, margin: 0 });
    });
    s.addText([
      { text: "Ставка — ступенчатая функция: 3264 дневных значения, но всего ", options: {} },
      { text: "65 фактических изменений", options: { bold: true, color: PRIMARY } },
      { text: " (~5 в год). Курс и ставка обязательно моделируются вместе с нефтью — иначе эффект ставки путается с сырьевым циклом.", options: {} },
    ], { x: 0.6, y: 4.15, w: 12.0, h: 0.7, fontFace: "Calibri", fontSize: 13, color: INK, isTextBox: true, margin: 0 });
    s.addText([
      { text: "Проверка данных: ", options: { bold: true } },
      { text: "даты решений и даты курса в выгрузках ЦБ используют разные конвенции (курс датирован T+1 от торговой сессии). Прямое сравнение совпадало в 5 случаях из 65; после сдвига на 1 день — в 65 из 65. Проверка встроена в код: скрипт падает, если совпадений не 65.", options: {} },
    ], { x: 0.6, y: 4.95, w: 12.0, h: 1.0, fontFace: "Calibri", fontSize: 12.5, color: INK, isTextBox: true, margin: 0 });
    s.addText("Два структурных слома видны прямо в данных: экстренное повышение ставки до 20% 28.02.2022 (пик курса 120,4 ₽/$ 11.03.2022) и цикл ужесточения 2023–2024 до исторического максимума 21%.", {
      x: 0.6, y: 6.1, w: 12.0, h: 0.7, fontFace: "Calibri", fontSize: 12, italic: true, color: MUTED, isTextBox: true, margin: 0,
    });
    pageNum(s, 3);
  }

  // ---------- 4. Методы и спецификация ----------
  {
    const s = lightSlide(pres);
    title(s, "Методы: два слоя, спецификация выбрана данными");
    const layers = [
      {
        x: 0.6, color: PRIMARY, h: "Месячные данные",
        items: ["VAR в первых разностях (лаг по BIC/AIC/HQIC/FPE: p=3)", "Тест на коинтеграцию: ранг неустойчив к лагу (1 при kd=1, 0 при kd=2/3) — берём VAR-в-разностях, VECM как помеченная альтернатива", "Тест Грейнджера, импульсные отклики (IRF)"],
      },
      {
        x: 6.8, color: SECONDARY, h: "Дневные данные",
        items: ["GARCH: спецификация выбрана по AIC/BIC среди 4 кандидатов (Normal/t × const/AR(1) × GJR)", "Выбрана: t-распределение, AR(1)-среднее, GJR-асимметрия", "Событийное исследование вокруг 65 решений, плацебо стратифицировано по году"],
      },
    ];
    layers.forEach((l) => {
      s.addShape("roundRect", { x: l.x, y: 1.55, w: 5.9, h: 4.3, fill: { color: CARD }, line: { type: "none" }, rectRadius: 0.08 });
      s.addShape("roundRect", { x: l.x + 0.35, y: 1.9, w: 0.25, h: 0.25, fill: { color: l.color }, line: { type: "none" } });
      s.addText(l.h, { x: l.x + 0.8, y: 1.8, w: 4.7, h: 0.5, fontFace: "Calibri", fontSize: 16, bold: true, color: l.color, isTextBox: true, margin: 0 });
      const items = l.items.map((t, i) => ({ text: t, options: { bullet: true, breakLine: i < l.items.length - 1 } }));
      s.addText(items, { x: l.x + 0.4, y: 2.5, w: 5.1, h: 3.1, fontFace: "Calibri", fontSize: 13, color: INK, isTextBox: true, margin: 0, paraSpaceAfter: 10 });
    });
    s.addText("Почему так: произвольный выбор лага (kd=1) давал коинтеграцию на границе критического значения — при лаге, выбранном по данным, она исчезает. Исходная GARCH-спецификация (const-mean, Normal) не проходила диагностику остатков — выбранная по BIC проходит.", {
      x: 0.6, y: 6.0, w: 12.0, h: 0.9, fontFace: "Calibri", fontSize: 12, italic: true, color: MUTED, isTextBox: true, margin: 0,
    });
    s.addNotes("Если спросят про VECM: мы его не выбросили, а прогнали параллельно (T4) — результат тот же качественно.");
    pageNum(s, 4);
  }

  // ---------- 5. Р1 три ряда ----------
  {
    const s = lightSlide(pres);
    title(s, "Три ряда во времени");
    s.addImage({ path: FIG_DIR + "R1_three_series.png", x: 3.46, y: 1.4, w: 6.41, h: 5.7 });
    s.addNotes(
      "Обратить внимание на два эпизода, которые видны на всех трёх графиках одновременно: конец 2014 — начало 2015 " +
      "(нефть падает, ставка и курс резко растут) и февраль-март 2022 (экстренное повышение ставки, пик курса). " +
      "Это и есть те самые 7 месяцев, которые определяют весь результат — см. слайд 6."
    );
    pageNum(s, 5);
  }

  // ---------- 6. ГЛАВНАЯ НАХОДКА ----------
  {
    const s = darkSlide(pres);
    s.addShape("roundRect", { x: 0.5, y: 0.4, w: 3.4, h: 0.4, fill: { color: ACCENT }, line: { type: "none" }, rectRadius: 0.06 });
    s.addText("ГЛАВНАЯ НАХОДКА", { x: 0.5, y: 0.4, w: 3.4, h: 0.4, fontFace: "Calibri", fontSize: 13, bold: true, color: PRIMARY, align: "center", valign: "middle", isTextBox: true, margin: 0 });
    s.addText("Значимость держится на семи месяцах из 156", {
      x: 0.6, y: 0.95, w: 12.0, h: 0.8, fontFace: "Cambria", fontSize: 24, bold: true, color: WHITE, isTextBox: true, margin: 0,
    });

    s.addImage({ path: FIG_DIR + "R4_rolling_granger.png", x: 0.5, y: 1.75, w: 7.6, h: 3.8 });

    const rows = [
      [{ text: "Нейтрализация (дамми по наблюдению)", options: { bold: true, color: WHITE, fill: { color: PRIMARY } } }, { text: "ставка→курс, p", options: { bold: true, color: WHITE, fill: { color: PRIMARY } } }],
      ["Ничего (основной результат)", { text: "<10⁻¹⁹", options: { color: GREEN, bold: true } }],
      ["Только 2022 (фев–апр)", { text: "0,10", options: { color: RED } }],
      ["Только 2014-15 (ноя–фев)", { text: "<10⁻¹⁹", options: { color: GREEN } }],
      ["Оба кризиса", { text: "0,74", options: { color: RED, bold: true } }],
    ];
    s.addTable(rows, {
      x: 8.3, y: 1.75, w: 4.5, h: 2.6, fontFace: "Calibri", fontSize: 11, color: INK,
      fill: { color: WHITE }, border: { type: "solid", color: "E3E7ED", pt: 1 }, autoPage: false,
      colW: [3.0, 1.5], align: "center",
    });
    s.addText("Дамми ставится по одному наблюдению на каждый кризисный месяц (общая дамми на весь период эффект выброса не гасит — он ещё входит в VAR как лаг). Нужны оба кризиса: один эпизод в одиночку значимость не убирает.", {
      x: 8.3, y: 4.55, w: 4.5, h: 2.0, fontFace: "Calibri", fontSize: 11.5, color: "CADCFC", isTextBox: true, margin: 0,
    });

    s.addText([
      { text: "Скользящее окно: доля значимых окон падает с 60% до 2% ", options: { bold: true, color: ACCENT } },
      { text: "при нейтрализации кризисных месяцев в каждом окне. Провал до p≈10⁻³⁰ — эффект одного экстремального наблюдения (ставка +10,5 п.п., курс +29% в тот же месяц), не сила связи; F-тест при таком выбросе не проходит проверку на нормальность остатков.", options: { color: "CADCFC" } },
    ], { x: 0.5, y: 6.5, w: 11.9, h: 0.8, fontFace: "Calibri", fontSize: 11.5, isTextBox: true, margin: 0 });
    s.addNotes(
      "Ключевая методическая правка: одна общая дамми на весь кризисный период не гасит эффект выброса, потому что тот же " +
      "выброс входит в VAR ещё и как лаг на t+1, t+2. Дамми нужно ставить по одному наблюдению. После этого исправления " +
      "значимость на полной выборке действительно исчезает при нейтрализации обоих кризисов (p=0.74), что и есть " +
      "прямое, а не косвенное доказательство главного тезиса."
    );
    pageNum(s, 6, "8592A8");
  }

  // ---------- 7. IRF ----------
  {
    const s = lightSlide(pres);
    title(s, "Импульсный отклик: 1 п.п., накопленный эффект, бутстрап-CI");
    s.addImage({ path: FIG_DIR + "R2_irf_rate_to_fx.png", x: 4.7, y: 1.3, w: 4.3, h: 4.0 });
    const bullets = [
      { text: "Шок — ровно 1 п.п. ставки (не 1 стандартное отклонение ≈ 1,33 п.п.)", options: { bullet: true, breakLine: true } },
      { text: "Пик +2,3% на 1-м месяце, разворот в минус на 2–4 месяце, гаснет к 6–7 месяцу", options: { bullet: true, breakLine: true } },
      { text: "Накопленный эффект перестаёт значимо отличаться от нуля уже с 3-го месяца (95% бутстрап-CI, 500 реплик, включает ноль)", options: { bullet: true, breakLine: true } },
      { text: "Устойчиво к порядку ортогонализации: при пересчёте в тех же единицах (1 п.п.) для всех трёх порядков пик 0,019–0,023, накопленный эффект на 3-м месяце близок к нулю (0,001–0,014)", options: { bullet: true, breakLine: false } },
    ];
    s.addText(bullets, { x: 0.5, y: 1.5, w: 4.0, h: 4.5, fontFace: "Calibri", fontSize: 12, color: INK, isTextBox: true, margin: 0, paraSpaceAfter: 12 });
    s.addNotes("Размер эффекта отдельно от значимости: сумма коэффициентов при двух лагах ставки в уравнении курса — 0.0005, 95% ДИ от -0.008 до 0.009, включает ноль.");
    pageNum(s, 7);
  }

  // ---------- 8. GARCH ----------
  {
    const s = lightSlide(pres);
    title(s, "GARCH: спецификация выбрана, не угадана");
    const rows = [
      [{ text: "Спецификация", options: { bold: true, fill: { color: PRIMARY }, color: WHITE } }, { text: "AIC", options: { bold: true, fill: { color: PRIMARY }, color: WHITE } }, { text: "BIC", options: { bold: true, fill: { color: PRIMARY }, color: WHITE } }],
      ["t, AR(1)-mean, GJR (выбрана)", "8201", { text: "8244", options: { bold: true, color: GREEN } }],
      ["t, AR(1)-mean", "8227", "8263"],
      ["t, const-mean", "8257", "8287"],
      ["Normal, const-mean", "8544", "8568"],
    ];
    s.addTable(rows, {
      x: 0.6, y: 1.5, w: 6.0, h: 2.0, fontFace: "Calibri", fontSize: 12, color: INK,
      border: { type: "solid", color: "E3E7ED", pt: 1 }, autoPage: false, colW: [3.6, 1.2, 1.2],
    });
    s.addText("Диагностика остатков (Ljung-Box), весь период: p=0,18 (уровень), p=0,45 (квадраты) — проходит. Подвыборка «после 2022»: персистентность выходит на 1,0 (интегрированный GARCH), квадраты остатков p=6·10⁻⁸ — НЕ проходит; артефакт кластера экстремальной волатильности в малой подвыборке.", {
      x: 0.6, y: 3.75, w: 6.0, h: 1.7, fontFace: "Calibri", fontSize: 11.5, italic: true, color: MUTED, isTextBox: true, margin: 0,
    });
    statCallout(s, 7.1, 1.5, 5.4, "0,98 → 1,00", "персистентность (α+β+γ/2): до → после 28.02.2022", { vSize: 26 });
    statCallout(s, 7.1, 3.0, 5.4, "1,06 → н/д", "безусловная дисперсия, %²: до 2022 — идентифицируется; после — нет", { vSize: 24, vColor: SECONDARY });
    s.addText("Персистентность ~1 в малой подвыборке с выбросами — не находка про «долгую память», а известный артефакт оценивания GARCH; безусловная дисперсия там математически не определена и не репортится как число.", {
      x: 7.1, y: 4.55, w: 5.4, h: 1.4, fontFace: "Calibri", fontSize: 11.5, italic: true, color: MUTED, isTextBox: true, margin: 0,
    });
    pageNum(s, 8);
  }

  // ---------- 9. Событийное исследование + прогноз вне выборки ----------
  {
    const s = lightSlide(pres);
    title(s, "Волатильность вокруг решений и прогноз вне выборки");

    s.addShape("roundRect", { x: 0.5, y: 1.5, w: 6.0, h: 4.7, fill: { color: CARD }, line: { type: "none" }, rectRadius: 0.08 });
    s.addText("Событийное исследование", { x: 0.8, y: 1.7, w: 5.4, h: 0.4, fontFace: "Calibri", fontSize: 15, bold: true, color: PRIMARY, isTextBox: true, margin: 0 });
    s.addText([
      { text: "Наивный тест (плацебо по всей выборке): p=0,000 — но 19 из 65 решений физически лежат в кризисных годах.", options: { bullet: true, breakLine: true } },
      { text: "Плацебо стратифицировано по году + аномальная |доходность|: все события — p=0,009; без 2014/2015/2022 — p=0,457.", options: { bullet: true, breakLine: true } },
      { text: "Вне кризисных лет: доходность до решения 0,568%, после — 0,570%, база — 0,569% — никакой реакции нет.", options: { bullet: true, breakLine: false, bold: true } },
    ], { x: 0.8, y: 2.25, w: 5.4, h: 3.8, fontFace: "Calibri", fontSize: 12, color: INK, isTextBox: true, margin: 0, paraSpaceAfter: 10 });

    s.addShape("roundRect", { x: 6.85, y: 1.5, w: 5.9, h: 4.7, fill: { color: PRIMARY }, line: { type: "none" }, rectRadius: 0.08 });
    s.addText("Прогноз вне выборки (rolling origin)", { x: 7.15, y: 1.7, w: 5.3, h: 0.4, fontFace: "Calibri", fontSize: 15, bold: true, color: ACCENT, isTextBox: true, margin: 0 });
    s.addText([
      { text: "Спокойные годы: наивный прогноз не хуже VAR-моделей (VAR без ставки значимо точнее VAR со ставкой, DM p=0,025).", options: { bullet: true, breakLine: true } },
      { text: "Кризисные годы (n=12): VAR со ставкой точнее наивного (RMSE 0,127 vs 0,138) и VAR без ставки (0,191) — но по упрощённому тесту Диболда-Мариано разница не значима (p=0,09–0,73).", options: { bullet: true, breakLine: true } },
      { text: "Честно по обоим режимам, не выбираем удобную половину результата.", options: { bullet: true, breakLine: false, bold: true } },
    ], { x: 7.15, y: 2.25, w: 5.3, h: 3.8, fontFace: "Calibri", fontSize: 12, color: WHITE, isTextBox: true, margin: 0, paraSpaceAfter: 10 });
    s.addNotes(
      "Для вложенной пары VAR-без-ставки/VAR-со-ставкой классический тест Диболда-Мариано формально смещён " +
      "(лишние параметры добавляют шум оценивания) — корректнее тест Кларка-Уэста, мы его не реализовывали, это отмечено как ограничение."
    );
    pageNum(s, 9);
  }

  // ---------- 10. Ответ + ограничения ----------
  {
    const s = lightSlide(pres);
    title(s, "Ответ на вопрос и ограничения");
    s.addShape("roundRect", { x: 0.6, y: 1.5, w: 5.7, h: 4.7, fill: { color: CARD }, line: { type: "none" }, rectRadius: 0.08 });
    s.addText("Ответ", { x: 0.9, y: 1.75, w: 5.1, h: 0.4, fontFace: "Calibri", fontSize: 16, bold: true, color: PRIMARY, isTextBox: true, margin: 0 });
    s.addText([
      { text: "Факт: значимость связи целиком объясняется двумя кризисными эпизодами (7 месяцев из 156); при их нейтрализации она исчезает.", options: { bullet: true, breakLine: true } },
      { text: "Вне кризисных лет — ни предсказуемости, ни повышенной волатильности вокруг решений. В кризис ставка помогает прогнозу курса, но на 12 наблюдениях это не доказано формально.", options: { bullet: true, breakLine: true } },
      { text: "Чего данные не позволяют утверждать: направление причинности, роль инфляции и ожиданий (их нет в модели).", options: { bullet: true, breakLine: false } },
    ], { x: 0.9, y: 2.3, w: 5.1, h: 3.7, fontFace: "Calibri", fontSize: 12, color: INK, isTextBox: true, margin: 0, paraSpaceAfter: 10 });

    s.addShape("roundRect", { x: 6.65, y: 1.5, w: 5.9, h: 4.7, fill: { color: PRIMARY }, line: { type: "none" }, rectRadius: 0.08 });
    s.addText("Ограничения", { x: 6.95, y: 1.75, w: 5.3, h: 0.4, fontFace: "Calibri", fontSize: 16, bold: true, color: ACCENT, isTextBox: true, margin: 0 });
    s.addText([
      { text: "Контрольная группа «заседания без изменения ставки» не построена — тест остаётся ослабленным.", options: { bullet: true, breakLine: true } },
      { text: "Множественные проверки (лаги, подпериоды, дамми-варианты) не скорректированы на множественное тестирование.", options: { bullet: true, breakLine: true } },
      { text: "Короткие кризисные подвыборки (n=12–55) — низкая мощность.", options: { bullet: true, breakLine: true } },
      { text: "DM-тест для вложенных моделей формально смещён (нужен тест Кларка-Уэста); три переменные — упрощение.", options: { bullet: true, breakLine: false } },
    ], { x: 6.95, y: 2.3, w: 5.3, h: 3.7, fontFace: "Calibri", fontSize: 12, color: WHITE, isTextBox: true, margin: 0, paraSpaceAfter: 10 });
    pageNum(s, 10);
  }

  // ---------- 11. Спасибо ----------
  {
    const s = darkSlide(pres);
    s.addText("Спасибо. Вопросы?", {
      x: 0.8, y: 2.3, w: 10, h: 1.0, fontFace: "Cambria", fontSize: 36, bold: true, color: WHITE, isTextBox: true, margin: 0,
    });
    s.addText("Команда: ФИО будут указаны перед сдачей", {
      x: 0.8, y: 3.5, w: 10, h: 0.5, fontFace: "Calibri", fontSize: 15, color: "CADCFC", isTextBox: true, margin: 0,
    });
    s.addText("Код, данные (загружаются автоматически) и инструкция — в репозитории проекта, README.md.\nПолный прогон с нуля: ~16 секунд (лимит задания — 30 минут).", {
      x: 0.8, y: 4.1, w: 10.5, h: 1.0, fontFace: "Calibri", fontSize: 13, color: "8592A8", isTextBox: true, margin: 0,
    });
    pageNum(s, 11, "8592A8");
  }

  await pres.writeFile({ fileName: "presentation.pptx" });
  console.log("OK: presentation.pptx");
}

build().catch((e) => { console.error(e); process.exit(1); });
