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
    fontFace: "Calibri", fontSize: opts.size || 28, bold: true,
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
    x, y, w, h: opts.vh || 0.7, fontFace: "Calibri", fontSize: opts.vSize || 32, bold: true,
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
      "Заголовок раскрывает главный вывод не сразу — сначала вопрос и дизайн, потом находка на слайде 6. " +
      "Если попросят резюме в одном предложении: связь между ставкой и курсом реальна, но только в кризис."
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
        items: ["VAR в первых разностях (лаг по BIC/AIC/HQIC/FPE: p=3)", "Тест на коинтеграцию: ранг неустойчив к лагу (1 при kd=1, 0 при kd=2/3) — берём VAR-в-разностях, VECM как альтернатива", "Тест Грейнджера, импульсные отклики (IRF)"],
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
    s.addNotes("Если спросят про VECM: мы его не выбросили, а прогнали параллельно (слайд с Грейнджером) — результат тот же качественно.");
    pageNum(s, 4);
  }

  // ---------- 5. Р1 три ряда ----------
  {
    const s = lightSlide(pres);
    title(s, "Три ряда во времени");
    s.addImage({ path: FIG_DIR + "R1_three_series.png", x: 3.46, y: 1.4, w: 6.41, h: 5.7 });
    pageNum(s, 5);
  }

  // ---------- 6. ГЛАВНАЯ НАХОДКА ----------
  {
    const s = darkSlide(pres);
    s.addShape("roundRect", { x: 0.5, y: 0.4, w: 3.4, h: 0.4, fill: { color: ACCENT }, line: { type: "none" }, rectRadius: 0.06 });
    s.addText("ГЛАВНАЯ НАХОДКА", { x: 0.5, y: 0.4, w: 3.4, h: 0.4, fontFace: "Calibri", fontSize: 13, bold: true, color: PRIMARY, align: "center", valign: "middle", isTextBox: true, margin: 0 });
    s.addText("Связь видна только тогда, когда в выборке есть кризис", {
      x: 0.6, y: 0.95, w: 12.0, h: 0.8, fontFace: "Cambria", fontSize: 24, bold: true, color: WHITE, isTextBox: true, margin: 0,
    });

    s.addImage({ path: FIG_DIR + "R4_rolling_granger.png", x: 0.5, y: 1.75, w: 7.6, h: 3.8 });

    const rows = [
      [{ text: "Подвыборка", options: { bold: true, color: WHITE, fill: { color: PRIMARY } } }, { text: "ставка→курс, p", options: { bold: true, color: WHITE, fill: { color: PRIMARY } } }, { text: "курс→ставка, p", options: { bold: true, color: WHITE, fill: { color: PRIMARY } } }],
      ["Вся выборка", { text: "<0,0001", options: { color: GREEN, bold: true } }, { text: "0,005", options: { color: GREEN } }],
      ["Спокойный период 2015-06–2021-12", { text: "0,54", options: { color: RED } }, { text: "0,37", options: { color: RED } }],
      ["После острой фазы 2022-09…", { text: "0,74", options: { color: RED } }, { text: "0,37", options: { color: RED } }],
    ];
    s.addTable(rows, {
      x: 8.3, y: 1.75, w: 4.5, h: 2.6, fontFace: "Calibri", fontSize: 11, color: INK,
      fill: { color: WHITE }, border: { type: "solid", color: "E3E7ED", pt: 1 }, autoPage: false,
      colW: [2.1, 1.2, 1.2], align: "center",
    });
    s.addText("Скользящее окно (60 мес.): p-значение падает с ~0,1 до ~10⁻³⁰ ровно в момент, когда в окно входит кризис 2022 года — и остаётся астрономически значимым все последующие годы, пока кризис в окне.", {
      x: 8.3, y: 4.55, w: 4.5, h: 2.0, fontFace: "Calibri", fontSize: 11.5, color: "CADCFC", isTextBox: true, margin: 0,
    });

    s.addText([
      { text: "Вне кризисов предсказуемости нет ни в одну сторону. ", options: { bold: true, color: ACCENT } },
      { text: "Полновыборочный результат — эффект нескольких кризисных месяцев, а не устойчивая закономерность.", options: { color: "CADCFC" } },
    ], { x: 0.5, y: 6.55, w: 11.9, h: 0.5, fontFace: "Calibri", fontSize: 12.5, isTextBox: true, margin: 0 });
    s.addNotes(
      "Это переработанная версия находки после внешнего ревью: в первой версии мы утверждали 'разворот' Грейнджера по подпериодам до/после 2022. " +
      "Ревью показало, что оба подпериода всё ещё содержат кризисные месяцы. Спокойные периоды по отдельности не значимы ни в одну сторону — " +
      "значит, дело не в направлении причинности, а в самом присутствии кризиса в выборке. Экзогенная дамми на кризисные месяцы эффект не убирает — " +
      "связь размазана по кризисному режиму, а не сосредоточена в паре месяцев."
    );
    pageNum(s, 6, "8592A8");
  }

  // ---------- 7. IRF ----------
  {
    const s = lightSlide(pres);
    title(s, "Импульсный отклик: исправленный масштаб и накопленный эффект");
    s.addImage({ path: FIG_DIR + "R2_irf_rate_to_fx.png", x: 4.7, y: 1.3, w: 4.3, h: 4.0 });
    const bullets = [
      { text: "Шок — ровно 1 п.п. (в первой версии график был подписан «1 п.п.», но фактически показывал шок в 1 стандартное отклонение ≈ 1,33 п.п.)", options: { bullet: true, breakLine: true } },
      { text: "Пик +2,3% на 1-м месяце, разворот в минус на 2–4 месяце, гаснет к 6–7 месяцу", options: { bullet: true, breakLine: true } },
      { text: "Накопленный эффект перестаёт значимо отличаться от нуля уже с 3-го месяца (95% бутстрап-CI, 500 реплик, включает ноль)", options: { bullet: true, breakLine: true } },
      { text: "Ортогонализация по Холецкому: ставка первая в порядке — доп. допущение, устойчивое к перестановке (Т7b)", options: { bullet: true, breakLine: false } },
    ];
    s.addText(bullets, { x: 0.5, y: 1.5, w: 4.0, h: 4.5, fontFace: "Calibri", fontSize: 12, color: INK, isTextBox: true, margin: 0, paraSpaceAfter: 12 });
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
      ["Normal, const-mean (исходная)", "8544", "8568"],
    ];
    s.addTable(rows, {
      x: 0.6, y: 1.5, w: 6.0, h: 2.2, fontFace: "Calibri", fontSize: 12, color: INK,
      border: { type: "solid", color: "E3E7ED", pt: 1 }, autoPage: false, colW: [3.6, 1.2, 1.2],
    });
    s.addText("Исходная спецификация не проходила диагностику остатков (Ljung-Box p<0,001). Выбранная по BIC — проходит (p=0,18 на всём периоде, p=0,45 в квадратах остатков).", {
      x: 0.6, y: 3.9, w: 6.0, h: 1.1, fontFace: "Calibri", fontSize: 12, italic: true, color: MUTED, isTextBox: true, margin: 0,
    });
    statCallout(s, 7.1, 1.5, 5.4, "α+β ≈ 0,99", "персистентность волатильности, весь период", { vSize: 28 });
    statCallout(s, 7.1, 3.0, 5.4, "0,029→0,061", "ω (не безусловная дисперсия!) до → после 28.02.2022", { vSize: 24, vColor: SECONDARY });
    s.addText("На подвыборке «после 2022» персистентность выходит на 1,0 (интегрированный GARCH) — известный артефакт кластера экстремальной волатильности в малой подвыборке; безусловная дисперсия там не идентифицируется, репортим как NaN, а не как число.", {
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
      { text: "Плацебо стратифицировано по году + аномальная |доходность| (минус база за 30 дней): все события — p=0,009.", options: { bullet: true, breakLine: true } },
      { text: "Без 2014/2015/2022: p=0,457 — эффекта нет.", options: { bullet: true, breakLine: true, bold: true } },
      { text: "После решения доходность выше (1,07%), чем до (0,84%, = базовый уровень 0,84%) — реакция идёт после, не до.", options: { bullet: true, breakLine: false } },
    ], { x: 0.8, y: 2.25, w: 5.4, h: 3.8, fontFace: "Calibri", fontSize: 12, color: INK, isTextBox: true, margin: 0, paraSpaceAfter: 10 });

    s.addShape("roundRect", { x: 6.85, y: 1.5, w: 5.9, h: 4.7, fill: { color: PRIMARY }, line: { type: "none" }, rectRadius: 0.08 });
    s.addText("Прогноз вне выборки (rolling origin)", { x: 7.15, y: 1.7, w: 5.3, h: 0.4, fontFace: "Calibri", fontSize: 15, bold: true, color: ACCENT, isTextBox: true, margin: 0 });
    s.addText([
      { text: "Наивный прогноз («без изменений») конкурентен с VAR-моделями на горизонтах 1–3 месяца.", options: { bullet: true, breakLine: true } },
      { text: "RMSE (h=1, спокойные годы): наивный 0,033, VAR без ставки 0,035, VAR со ставкой 0,037 — ставка прогноз не улучшает.", options: { bullet: true, breakLine: true } },
      { text: "Значимость по Грейнджеру внутри выборки ≠ польза для прогноза вне неё — разные вопросы.", options: { bullet: true, breakLine: false, bold: true } },
    ], { x: 7.15, y: 2.25, w: 5.3, h: 3.8, fontFace: "Calibri", fontSize: 12.5, color: WHITE, isTextBox: true, margin: 0, paraSpaceAfter: 12 });
    pageNum(s, 9);
  }

  // ---------- 10. Ответ + ограничения ----------
  {
    const s = lightSlide(pres);
    title(s, "Ответ на вопрос и ограничения");
    s.addShape("roundRect", { x: 0.6, y: 1.5, w: 5.7, h: 4.7, fill: { color: CARD }, line: { type: "none" }, rectRadius: 0.08 });
    s.addText("Ответ", { x: 0.9, y: 1.75, w: 5.1, h: 0.4, fontFace: "Calibri", fontSize: 16, bold: true, color: PRIMARY, isTextBox: true, margin: 0 });
    s.addText([
      { text: "Факт: ставка и курс совместно движутся сильнее в кризис; вне кризиса предсказуемости нет ни в одну сторону.", options: { bullet: true, breakLine: true } },
      { text: "Чего данные не позволяют утверждать: направление причинности, роль инфляции и ожиданий (их нет в модели).", options: { bullet: true, breakLine: true } },
      { text: "Что нужно для следующего шага: данные по инфляции, календарь заседаний без изменения ставки, дизайн с «сюрпризом» решения.", options: { bullet: true, breakLine: false } },
    ], { x: 0.9, y: 2.3, w: 5.1, h: 3.7, fontFace: "Calibri", fontSize: 12.5, color: INK, isTextBox: true, margin: 0, paraSpaceAfter: 10 });

    s.addShape("roundRect", { x: 6.65, y: 1.5, w: 5.9, h: 4.7, fill: { color: PRIMARY }, line: { type: "none" }, rectRadius: 0.08 });
    s.addText("Ограничения", { x: 6.95, y: 1.75, w: 5.3, h: 0.4, fontFace: "Calibri", fontSize: 16, bold: true, color: ACCENT, isTextBox: true, margin: 0 });
    s.addText([
      { text: "Контрольная группа «заседания без изменения ставки» не построена — тест остаётся ослабленным.", options: { bullet: true, breakLine: true } },
      { text: "Множественные проверки (лаги, подпериоды, спецификации) не скорректированы на множественное тестирование.", options: { bullet: true, breakLine: true } },
      { text: "Короткие кризисные подвыборки (n=12–55) — низкая мощность, отсутствие значимости может быть нехваткой данных.", options: { bullet: true, breakLine: true } },
      { text: "Три переменные — упрощение: нет ставки ФРС, инфляции, санкционного индекса.", options: { bullet: true, breakLine: false } },
    ], { x: 6.95, y: 2.3, w: 5.3, h: 3.7, fontFace: "Calibri", fontSize: 12.5, color: WHITE, isTextBox: true, margin: 0, paraSpaceAfter: 10 });
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
    s.addText("Код, данные (загружаются автоматически) и инструкция — в репозитории проекта, README.md.\nПолный прогон с нуля: ~19 секунд (лимит задания — 30 минут).\nПроект прошёл внешнее ревью — см. feedback_1.md в репозитории.", {
      x: 0.8, y: 4.1, w: 10.5, h: 1.3, fontFace: "Calibri", fontSize: 13, color: "8592A8", isTextBox: true, margin: 0,
    });
    pageNum(s, 11, "8592A8");
  }

  await pres.writeFile({ fileName: "presentation.pptx" });
  console.log("OK: presentation.pptx");
}

build().catch((e) => { console.error(e); process.exit(1); });
