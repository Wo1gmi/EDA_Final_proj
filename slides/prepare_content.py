import json
import csv
import hashlib
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
AUTHORS = ['Анастасия Казакова', 'Степан Селезнев', 'Светлана Калошкина']
entries = []
def add(slide, name, text, size=18, color='#1C2733', bold=False, font='Calibri', position=None, italic=False):
    item = dict(slide=slide, name=name, text=text, style=dict(typeface=font, fontSize=size, color=color, bold=bold, italic=italic))
    if position:
        item['position'] = dict(zip(['left','top','width','height'], position))
    entries.append(item)

def title(slide, text):
    add(slide, 'Text 0', text, 36, bold=True)

add(1, 'Text 0', 'Ставка ЦБ, курс рубля\nи его волатильность', 53.33, '#FFFFFF', True, 'Cambria')
add(1, 'Text 1', 'Финальный проект по анализу экономических данных\n2026', 22, '#AEB9CC', position=[76.8,400,1008,74])
add(1, 'Text 2', '\n'.join(AUTHORS), 20, '#CADCFC', position=[76.8,534,1100,92])
add(1, 'Text 3', 'Данные Банка России и FRED', 17, '#AEB9CC', position=[76.8,654,1100,30])
title(2, 'Исследовательский вопрос')
add(2, 'Text 1', 'Помогают ли прошлые изменения ключевой ставки\nпрогнозировать изменения курса рубля?', 29.33, '#13294B', font='Cambria', italic=True)
add(2, 'Text 2', [
    'Как меняется волатильность курса вокруг дат вступления новой ставки в силу?',
    'Курс определяет стоимость валюты для импортёров и владельцев валютных сбережений.',
    'Исследуем прогнозную связь при учёте цены нефти Brent. Причинная трактовка требует отдельного дизайна.'
], 20, position=[57.6,315,729.6,312])
add(2, 'Text 3', '4,25-21%', 40, '#13294B', True)
add(2, 'Text 4', 'диапазон ключевой ставки в исходных данных', 16, '#6B7688')
add(2, 'Text 5', '65', 40, '#13294B', True)
add(2, 'Text 6', 'изменений уровня ставки', 16, '#6B7688')
title(3, 'Данные и календарь наблюдений')
add(3, 'Text 3', 'Банк России, ключевая ставка', 15, '#6B7688')
add(3, 'Text 8', 'Банк России, официальный курс', 15, '#6B7688')
add(3, 'Text 13', 'FRED, DCOILBRENTEU', 15, '#6B7688')
for name, text in [('Text 5', '17.09.2013-23.09.2026'), ('Text 10','10.01.2013-23.09.2026'), ('Text 15','01.01.2013-22.09.2026')]:
    add(3, name, text, 15, '#6B7688')
add(3, 'Text 16', 'Дневная ставка отражает действующий уровень. События определяем по датам изменения этого уровня.', 20, position=[57.6,395,1152,72])
add(3, 'Text 17', 'Официальный курс датирован днём действия. Для каждого события берём первую запись курса после даты вступления ставки в силу.', 20, position=[57.6,485,1152,86])
add(3, 'Text 18', 'Месячная модель использует общую выборку полных месяцев. После июня 2024 года методика официального курса опирается на внебиржевой рынок.', 17, '#6B7688', position=[57.6,594,1152,67])
title(4, 'Методы и проверка устойчивости')
add(4, 'Text 4', ['Изменения ставки и логарифмов курса и Brent.', 'VAR с лагом, выбранным по BIC. Проверка Грейнджера и импульсные отклики.', 'Чувствительность к лагу, кризисным эпизодам и порядку переменных.'], 19)
add(4, 'Text 8', ['GJR-GARCH с AR(1) и t-распределением для волатильности.', 'Сравнение четырёх спецификаций по BIC и диагностика остатков.', 'Событийные окна с плацебо внутри каждого года.'], 19)
add(4, 'Text 9', 'Модели описывают условные связи. Множественные проверки и нарушения предпосылок учитываем при интерпретации p-значений.', 18, '#6B7688')
title(5, 'Ставка, официальный курс и нефть во времени')
add(6, 'Text 1', 'УСТОЙЧИВОСТЬ РЕЗУЛЬТАТА', 17, '#13294B', True)
add(6, 'Text 2', 'Связь чувствительна к кризисным эпизодам', 34, '#FFFFFF', True, 'Cambria')
add(6, 'Text 3', 'Кризисные месяцы выделены индикаторами. Сравнение показывает чувствительность результата к выбору модели.', 18, '#CADCFC')
add(6, 'Text 4', 'Скользящие окна дают меняющуюся оценку связи. Результаты тестов рассматриваем вместе с диагностикой остатков и проверками чувствительности.', 18, '#CADCFC')
title(7, 'Отклик курса на модельный импульс ставки')
add(7, 'Text 1', ['Размер импульса: 1 процентный пункт ставки.', 'Отклик измеряется изменением логарифма официального курса.', 'Интервалы показывают неопределённость оценки при выбранной модели.', 'Порядок переменных задаёт допущения об одновременной связи.'], 19, position=[57.6,167,480,455])
title(8, 'Модель волатильности и её ограничения')
add(8, 'Text 1', 'Диагностика стандартных и квадратов стандартизированных остатков оценивает, насколько модель учитывает зависимость во времени.', 18, '#6B7688', position=[57.6,375,576,185])
add(8, 'Text 2', '0,99 и 1,00', 36, '#13294B', True)
add(8, 'Text 3', 'персистентность до и после 28.02.2022', 17, '#6B7688')
add(8, 'Text 4', '1,06 и н/д', 34, '#5B7FA6', True)
add(8, 'Text 5', 'безусловная дисперсия до и после, %²', 17, '#6B7688')
add(8, 'Text 6', 'Оценка на границе стационарности и остаточная зависимость ограничивают выводы по подвыборке после 2022 года.', 18, '#6B7688')
title(9, 'Волатильность вокруг событий и точность прогноза')
add(9, 'Text 2', 'Даты изменения действующей ставки', 20, '#13294B', True, position=[76.8,164,518.4,62])
add(9, 'Text 3', ['Сравниваем модуль изменения курса в событийном окне с базовым периодом.', 'Плацебо сохраняет годовой состав событий.', 'Интерпретация относится к окнам вокруг вступления ставки в силу.'], 19, position=[76.8,245,518.4,330])
add(9, 'Text 5', 'Прогноз на следующий месяц', 20, '#C9A227', True, position=[686.4,164,508.8,62])
add(9, 'Text 6', ['Модели обучаются только на прошлых наблюдениях.', 'Сравниваем нулевое изменение, VAR без ставки и VAR со ставкой.', 'Оцениваем RMSE отдельно для кризисных и остальных лет.'], 19, '#FFFFFF', position=[686.4,245,508.8,330])
title(10, 'Ответ на вопрос и ограничения')
add(10, 'Text 3', ['Оценка прогнозной связи зависит от кризисных эпизодов и спецификации.', 'Результаты событийного анализа зависят от состава периодов.', 'Практическую полезность ставки оцениваем по ошибкам прогноза на будущих месяцах.'], 19, position=[86.4,238,489.6,345])
add(10, 'Text 6', ['Ставка реагирует на состояние экономики. Инфляция и ожидания остаются за пределами модели.', 'Короткие кризисные подвыборки ограничивают точность сравнения.', 'Многочисленные проверки имеют исследовательский характер.', 'Официальный курс и даты действия ставки ограничивают событийную трактовку.'], 18.5, '#FFFFFF', position=[667.2,238,508.8,345])
add(11, 'Text 0', 'Спасибо за внимание', 48, '#FFFFFF', True, 'Cambria')
add(11, 'Text 1', ', '.join(AUTHORS), 21, '#CADCFC', position=[76.8,338,1120,66])
add(11, 'Text 2', 'Код, исходные данные и инструкция запуска доступны в репозитории проекта.\nСсылки на источники и ограничения приведены в README.', 21, '#AEB9CC', position=[76.8,429,1120,118])

notes = [
 'Авторы: '+', '.join(AUTHORS)+'. Исследуем прогнозную связь ставки, курса и волатильности на российских данных.',
 'Основной вопрос относится к предсказанию. Дополнительный вопрос касается модуля изменения официального курса вокруг дат изменения действующей ставки.',
 'Источники: https://www.cbr.ru/hd_base/KeyRate/ , https://www.cbr.ru/scripts/XML_dynamic.asp , https://fred.stlouisfed.org/series/DCOILBRENTEU . Таблица T1_sample.csv. Даты действия ставки отличаются от дат объявления решений. Даты официального курса также имеют собственную конвенцию.',
 'Спецификация и диагностика: T2_stationarity.csv, T3_lag_selection.csv, T3_diagnostics.txt, T4_granger.csv, T5b_garch_spec_selection.csv. При интерпретации учитываем исследовательский выбор нескольких спецификаций.',
 'Источник графика: output/figures/R1_three_series.png. Исходные данные Банка России и FRED. Официальный курс отражает действующую на дату котировку.',
 'Источники: T7_robustness.csv, T7c_rolling_granger.csv и R4_rolling_granger.png. Выделение кризисных периодов является проверкой чувствительности. Индикаторы имеют смысл при конкретном построении регрессии.',
 'Источники: T3c_irf_bootstrap.csv, T7b_irf_ordering.csv, R2_irf_rate_to_fx.png. Интервалы условны относительно модели и выбранной процедуры бутстрапа. Импульс задаётся в процентных пунктах ставки.',
 'Источники: T5_garch.csv, T5b_garch_spec_selection.csv. Высокая персистентность и плохая диагностика на отдельном периоде ограничивают применение выбранной модели в этом периоде.',
 'Источники: T6b_event_study_stratified.csv, T6c_before_after.csv, T8_outofsample_summary.csv, T8_outofsample_forecasts.csv. Событийный анализ описывает ассоциации вокруг вступления ставки в силу. Числа относятся к официальному курсу.',
 'Итог относится к использованным данным, датам, периодам и моделям. Статистически слабый результат сохраняет содержательный смысл при корректной интерпретации.',
 'Авторы: '+', '.join(AUTHORS)+'. Репозиторий: https://github.com/Wo1gmi/EDA_Final_proj .'
]

content = dict(authors=AUTHORS, text=entries, tables=[], images=[
 dict(slide=5,name='Image 0',file='output/figures/R1_three_series.png',alt='Динамика ключевой ставки, курса USD/RUB и Brent'),
 dict(slide=6,name='Image 0',file='output/figures/R4_rolling_granger.png',alt='Проверка Грейнджера в скользящих окнах'),
 dict(slide=7,name='Image 0',file='output/figures/R2_irf_rate_to_fx.png',alt='Импульсный отклик курса и накопленный отклик',position=dict(left=575,top=135,width=630,height=530))
],notes=notes)

values = json.loads((ROOT/'output/tables/slide_values.json').read_text())
audit = values['source_audit']
def number(x, digits=3):
    return f'{float(x):.{digits}f}'.replace('.', ',')
def pvalue(x):
    x = float(x)
    if x < 0.001:
        mantissa, exp = f'{x:.1e}'.split('e')
        return mantissa.replace('.', ',') + ' × 10' + str(int(exp)).translate(str.maketrans('-0123456789','⁻⁰¹²³⁴⁵⁶⁷⁸⁹'))
    return number(x)
def pick(items, **fields):
    found = [r for r in items if all(r[k] == v for k,v in fields.items())]
    if len(found) != 1:
        raise ValueError(f'Expected one result: {fields}')
    return found[0]
def update(slide, name, text, **kwargs):
    found = [i for i in entries if i['slide'] == slide and i['name'] == name]
    if found:
        found[0]['text'] = text
        if kwargs.get('size'):
            found[0]['style']['fontSize'] = kwargs['size']
        if kwargs.get('position'):
            found[0]['position'] = dict(zip(['left','top','width','height'], kwargs['position']))
    else:
        add(slide,name,text,**kwargs)

event_all, event_other = values['event']
base = pick(values['robustness'], variant='VAR(2) (основной)')
rob22 = pick(values['robustness'], variant='2022 (фев-апр), дамми@t..t+2')
rob14 = pick(values['robustness'], variant='2014-15 (ноя-фев), дамми@t..t+2')
rob_both = pick(values['robustness'], variant='оба кризиса, дамми@t..t+2')
update(2,'Text 5',str(event_all['n_events']))
sample = list(csv.DictReader((ROOT/'output/tables/T1_sample.csv').open()))
for r, names in zip(sample, [('Text 4','Text 5'),('Text 9','Text 10'),('Text 14','Text 15')]):
    update(3, names[0], str(r['n_obs']), size=34.66, color='#5B7FA6', bold=True)
    date = lambda x: '.'.join(x.split('-')[::-1])
    update(3, names[1], date(r['date_min'])+'-'+date(r['date_max']))
update(3,'Text 16',f"Месячная модель: {audit['monthly_n']} полных месяцев с 10.2013 по 08.2026. После разностей и двух лагов остаётся {base['n_obs']} наблюдения.")
update(3,'Text 17',f"События: {audit['rate_change_proxy_n']} дат изменения действующей ставки. Опорная дата курса: следующий календарный день. Это приближение по официальным датам действия.")
update(3,'Text 18','В месячной модели ставка берётся на конец месяца, курс и Brent усредняются. С июня 2024 года меняется методика официального курса.',size=18)
update(4,'Text 4',[
    f"Основная VAR({values['baseline_var_lag']}) в изменениях ставки и логарифмов курса и Brent.",
    'BIC на разностях поддерживает два лага. Проверяем также один и три лага.',
    'Тест Грейнджера, отклики и чувствительность к кризисным эпизодам.'
])
update(4,'Text 9','Коинтеграция чувствительна к лагу. VAR в разностях используем как рабочую модель. p-значения и интервалы трактуем с учётом диагностики.',size=18)
content['tables'] = [dict(slide=6,name='Table 0',fontSize=16,values=[
    ['Индикаторы кризисных месяцев','p теста ставки'],
    ['Без индикаторов',pvalue(base['rate_to_fx_p'])],
    ['Фев-апр 2022 + 2 месяца',pvalue(rob22['rate_to_fx_p'])],
    ['Ноя 2014-фев 2015 + 2 месяца',pvalue(rob14['rate_to_fx_p'])],
    ['Оба эпизода + 2 месяца',pvalue(rob_both['rate_to_fx_p'])]
])]
update(6,'Text 3','Индикаторы выделяют кризисные месяцы и следующие два месяца, на которые распространяются лаги. Рост p-значения показывает чувствительность теста.',size=18)
rolling = values['rolling_summary']
a=100*rolling['rate_to_fx_p']['fraction_below_005']
b=100*rolling['rate_to_fx_p_neutralized']['fraction_below_005']
update(6,'Text 4',f"В {rolling['n_windows']} скользящих окнах доля p<0,05 меняется с {number(a,1)}% до {number(b,1)}% при контроле кризисных наблюдений и лагов. Кризисная неоднородность ограничивает модельные тесты.",size=18)
irf = values['irf']
peak = max(irf, key=lambda r:r['response_per_pp'])
first_zero = min(r['horizon'] for r in irf if r['cum_ci_lo'] <= 0 <= r['cum_ci_hi'])
update(7,'Text 1',[
    'Импульс ставки: 1 процентный пункт.',
    f"Пик отклика месячного изменения курса: около {number(100*peak['response_per_pp'],1)} п.п. на {peak['horizon']}-м месяце.",
    f"С {first_zero}-го месяца точечный 95% интервал накопленного отклика включает ноль.",
    '500 реплик бутстрапа. Отклик условен относительно модели и порядка переменных.'
])
garch = values['garch']
gall=pick(garch,period='весь период')
gbefore=pick(garch,period='до 28.02.2022')
gafter=pick(garch,period='после 28.02.2022')
rows=[['Спецификация','AIC','BIC']]
labels=['t, AR(1), GJR','t, AR(1)','t, постоянное среднее','Normal, постоянное среднее']
for row,label in zip(values['garch_selection'],labels):
    rows.append([label,number(row['aic'],0),number(row['bic'],0)])
content['tables'].append(dict(slide=8,name='Table 0',fontSize=16,values=rows))
update(8,'Text 1',f"Общая выборка: {gall['n_obs']} наблюдений. Ljung-Box, 12 лагов: p={number(gall['ljung_box_resid_p'],2)} для остатков и {number(gall['ljung_box_resid_sq_p'],2)} для их квадратов.\n\nВ периоде с 28.02.2022 квадраты остатков сохраняют зависимость: p={pvalue(gafter['ljung_box_resid_sq_p'])}.",size=18)
update(8,'Text 2',number(gbefore['persistence'])+' и '+number(gafter['persistence']))
update(8,'Text 4',number(gbefore['unconditional_var_pct2'],2)+' и н/д')
update(8,'Text 6','В периоде с 28.02.2022 оценка персистентности достигает границы стационарности. Безусловная дисперсия в этой спецификации не определена.',size=18)
update(9,'Text 3',[
    f"{event_all['n_events']} событий: превышение обычного модуля изменения курса на {number(event_all['observed_abnormal_abs_return_pct'])} п.п. Monte Carlo p={number(event_all['p_value'])}.",
    f"Без 2014, 2015 и 2022: {event_other['n_events']} событий, превышение около {number(event_other['observed_abnormal_abs_return_pct'],4)} п.п. p={number(event_other['p_value'])}.",
    f"Окно {event_all['event_window_obs']} наблюдений, база {event_all['baseline_obs']}. Плацебо внутри года, {event_all['n_permutations']} повторов."
],size=18.5,position=[76.8,235,518.4,345])
oos=pick(values['forecast_summary'],regime='вся OOS-выборка',h=1)
oos22=pick(values['forecast_summary'],regime='кризисные цели, доступный год: 2022',h=1)
oosother=pick(values['forecast_summary'],regime='остальные годы OOS-выборки',h=1)
cw0=pick(values['forecast_comparison'],restricted_model='naive')
cw2=pick(values['forecast_comparison'],restricted_model='var2_no_rate')
update(9,'Text 6',[
    f"{oos['n']} прогнозов. RMSE VAR: {number(oos['rmse_var3_with_rate'],4)}, нулевого: {number(oos['rmse_naive'],4)}. MAE: {number(oos['mae_var3_with_rate'],4)} и {number(oos['mae_naive'],4)} соответственно.",
    f"У VAR ниже RMSE в 2022 (n={oos22['n']}) и выше в остальные годы (n={oosother['n']}).",
    f"Clark-West, приближённо: p={number(cw0['p_one_sided'])} против нулевого прогноза и {number(cw2['p_one_sided'])} при добавлении ставки к VAR курса и Brent."
],size=18.5,position=[686.4,235,508.8,345])
update(10,'Text 3',[
    'Прогнозная связь ставки и курса чувствительна к кризисным эпизодам и спецификации.',
    'VAR со ставкой немного снижает RMSE полной выборки. По MAE нулевой прогноз точнее.',
    'Добавочная польза ставки по сравнению с VAR курса и Brent остаётся неопределённой.',
    'Событийный результат зависит от включения кризисных лет.'
],size=18.5)
update(10,'Text 6',[
    'Ставка реагирует на экономику. Инфляция и ожидания остаются за пределами модели.',
    'Малые кризисные выборки и многочисленные проверки ограничивают уверенность выводов.',
    'Кризисная неоднородность ограничивает модельные интервалы и тесты.',
    'Используем даты действия ставки и официальный курс со сменой методики в 2024 году.'
],size=18)
content['notes'][2] += f" Общее число полных месяцев: {audit['monthly_n']}, в основной VAR после разностей и лагов {base['n_obs']}. Месячное усреднение курса и нефти исключает их механическое приравнивание к значениям на конец месяца."
content['notes'][5] += f" В основной модели p для прошлого курса в уравнении ставки равно {pvalue(pick(values['granger'],spec='VAR-в-разностях (осн.)',control='с нефтью в системе',causing='usdrub',caused='key_rate')['p_value'])}. После контроля обоих эпизодов и следующих двух месяцев p для обратного направления равно {pvalue(rob_both['fx_to_rate_p'])}. Высокие p-значения совместимы с недостаточной точностью."
content['notes'][8] += f" RMSE в 2022: нулевой {number(oos22['rmse_naive'],4)}, VAR со ставкой {number(oos22['rmse_var3_with_rate'],4)}. Остальные годы: {number(oosother['rmse_naive'],4)} и {number(oosother['rmse_var3_with_rate'],4)}. Ошибки прогнозов измерены в логарифмическом изменении курса. Все приведённые ошибки относятся к горизонту один месяц. Тест Clark-West использует всю непрерывную последовательность из {oos['n']} прогнозов и HAC с {cw0['hac_lags']} лагами. p-значения односторонние, приближённые. База сравнения имеет значение: нулевой прогноз p={number(cw0['p_one_sided'])}, VAR без ставки p={number(cw2['p_one_sided'])}. Режимные RMSE описательные."
manifest_path=ROOT/'output/run_manifest.json'
manifest=json.loads(manifest_path.read_text())
time_description='менее минуты' if manifest['elapsed_seconds'] < 60 else number(manifest['elapsed_seconds'],1)+' с'
update(11,'Text 2',f"Код, данные и инструкция: README.md.\nПолный расчёт: {time_description} в тестовом окружении.\nТестовый Mac: {manifest['runtime']['logical_cpus']} логических ядер, лимит численных потоков {manifest['runtime']['numerical_thread_limit']}.",size=21)
content['notes'][6] += ' Использован остаточный iid-бутстрап с фиксированной исходной нормировкой. Интервалы точечные. iid-бутстрап предполагает одинаковое распределение остатков. Возможная изменчивость дисперсии и выбросы ограничивают это допущение.'
content['notes'][10] += ' Замер включает весь расчёт на локально сохранённых исходных данных. Конфигурация ровно 8 CPU и 16 ГБ отдельно не испытывалась. Подробности доступны в output/run_manifest.json.'
content['inputs_sha256']={}
inputs=[ROOT/'output/tables/slide_values.json',ROOT/'output/tables/T1_sample.csv',manifest_path]+[ROOT/x['file'] for x in content['images']]
for f in inputs:
    content['inputs_sha256'][str(f.relative_to(ROOT))]=hashlib.sha256(f.read_bytes()).hexdigest()
serialized=json.dumps(content,ensure_ascii=False,indent=2)+'\n'
if any(x in serialized for x in ['\u2014','\u2013']):
    raise ValueError('Long dashes remain in slide copy.')
(ROOT/'slides/slide_content.json').write_text(serialized)
