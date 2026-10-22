# Проведение девяти документов — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Документы операционного сопровождения при проведении формируют движения регистров и меняют статусы, при отмене — убирают за собой; всё это проверяется автоматическим драйвером.

**Architecture:** `ОбработкаПроведения` и `ОбработкаУдаленияПроведения` живут в модуле объекта каждого документа. Повторяемые операции берутся из `ПроведениеДокументов` и `ЗадачиИсполнителям` (план 1). На каждый документ добавляется сценарий драйвера `ТестПроведения`, выполняющий полный цикл «провести → сверить → провести повторно → сверить → отменить → сверить».

**Tech Stack:** 1С:Предприятие 8.3.27, файловая ИБ, XML-выгрузка, внешняя обработка `epf/ТестПроведения`, раннер `tests/posting/run-posting-tests.ps1`.

**Spec:** `openspec/changes/implement-posting-and-data-processors/specs/document-posting/spec.md`, раздел 5.1 «Дополнения к ТЗ», `design.md` (D2, D3, D4, D5, D8).

## Global Constraints

- Платформа 8.3.27, файловая ИБ; перед пакетным запуском закрыть окна 1С.
- Порядок блокировок — из `ПроведениеДокументов.ЗаблокироватьРегистры`: сначала накопления, затем сведения.
- Отмена проведения = удаление движений по регистратору, без сторно-записей. Платформа удаляет только строки с `Регистратор = этот документ`; строки других документов не затрагиваются.
- `СобытиеМаршрута` движений не формирует (решение D3).
- Правила записи в `ПередЗаписью` не трогаем.
- Порог `ПорогСогласованияРуководителем` в демо — 10 000.
- Каждый сценарий драйвера обязан оставлять базу в исходном состоянии: в конце — отмена проведения, созданные задачи помечены на удаление.

## Review Focus

- Повторное проведение не дублирует записи регистров.
- Отмена одного документа не удаляет движения других.
- Ошибка в середине проведения не оставляет частичных записей.
- Проведение при пустой табличной части или нулевой сумме отклоняется с понятным сообщением.
- Статус связанного объекта не «залипает» после отмены документа, который его выставил.

---

<!-- openspec-task: 2.1 -->
### Task 1: `ЗаказПоставщику` — статусы отправки

**Files:**
- Modify: `src/КурсоваяРабота/Documents/ЗаказПоставщику/Ext/ObjectModule.bsl`
- Modify: `epf/ТестПроведения/Forms/Форма/Ext/Form/Module.bsl` (сценарий `post-order`)
- Modify: `tests/posting/run-posting-tests.ps1` (добавить `post-order`)

**Interfaces:**
- Consumes: `ПроведениеДокументов.ЗаблокироватьРегистры`, `ЗаписатьСтатус`, `УдалитьДвиженияРегистратора`.

- [ ] **Step 1: Добавить сценарий `post-order` и убедиться, что он падает**

Сценарий берёт первый непроведённый заказ, проводит, проверяет по записи `СтатусыПодтверждений` на каждую строку услуг со статусом `Отправлен`, проводит повторно и проверяет отсутствие дублей, отменяет проведение и проверяет пустоту.
Run: `tests\posting\run-posting-tests.ps1 -Scenario post-order`
Expected: FAIL — записей в регистре нет.

- [ ] **Step 2: Реализовать `ОбработкаПроведения`**

Заблокировать `РегистрСведений.СтатусыПодтверждений`, очистить движения регистратора, записать по строке на каждую услугу.

- [ ] **Step 3: Реализовать `ОбработкаУдаленияПроведения`**

`УдалитьДвиженияРегистратора(ЭтотОбъект.Ссылка)`.

- [ ] **Step 4: Прогнать сценарий**

Run: `db-load-xml`, затем `tests\posting\run-posting-tests.ps1 -Scenario post-order`
Expected: `ВЕРДИКТ: PASS`.

- [ ] **Step 5: Commit**

```bash
git add src/КурсоваяРабота/Documents/ЗаказПоставщику/Ext/ObjectModule.bsl epf/ТестПроведения tests/posting
git commit -m "feat(учёт): проведение заказа поставщику + тест"
```

<!-- openspec-task: 2.2 -->
### Task 2: `ПодтверждениеУслуги` — статус, параметры, статус заявки

**Files:**
- Modify: `src/КурсоваяРабота/Documents/ПодтверждениеУслуги/Ext/ObjectModule.bsl`
- Modify: `epf/ТестПроведения/Forms/Форма/Ext/Form/Module.bsl` (сценарий `post-confirmation`)
- Modify: `tests/posting/run-posting-tests.ps1`

**Interfaces:**
- Consumes: `ПроведениеДокументов`.

- [ ] **Step 1: Добавить сценарий `post-confirmation`**

Проверяет: записи `СтатусыПодтверждений` со статусом `Подтверждён`, записи `ПараметрыУслуг` с фактическими параметрами, перевод заявки в `Подтверждена` при полном подтверждении, возврат в `ВРаботе` после отмены.
Run: `tests\posting\run-posting-tests.ps1 -Scenario post-confirmation`
Expected: FAIL.

- [ ] **Step 2: Реализовать проведение**

Записи статуса и параметров по строкам, затем проверка полноты подтверждения заявки.

- [ ] **Step 3: Реализовать отмену проведения**

Удалить движения; вернуть заявку в `ВРаботе`, если она была переведена этим документом.

- [ ] **Step 4: Прогнать**

Run: `db-load-xml`, затем `tests\posting\run-posting-tests.ps1`
Expected: `ИТОГО: 2/2`.

- [ ] **Step 5: Commit**

```bash
git add src/КурсоваяРабота/Documents/ПодтверждениеУслуги/Ext/ObjectModule.bsl epf/ТестПроведения tests/posting
git commit -m "feat(учёт): проведение подтверждения услуги + тест"
```

<!-- openspec-task: 2.3 -->
### Task 3: `МаршрутныйЛист` — график перемещений

**Files:**
- Modify: `src/КурсоваяРабота/Documents/МаршрутныйЛист/Ext/ObjectModule.bsl`
- Modify: `epf/ТестПроведения/Forms/Форма/Ext/Form/Module.bsl` (сценарий `post-route`)
- Modify: `tests/posting/run-posting-tests.ps1`

**Interfaces:**
- Consumes: `ПроведениеДокументов`.

- [ ] **Step 1: Добавить сценарий `post-route`**

Проверяет: число записей `ГрафикПеремещений` равно числу событий, повторное проведение не увеличивает число, отмена очищает записи.
Run: `tests\posting\run-posting-tests.ps1 -Scenario post-route`
Expected: FAIL.

- [ ] **Step 2: Реализовать проведение**

Заблокировать регистр, удалить прежние записи документа, записать измерения (маршрутный лист, событие, турист, объект, тип события) и реквизиты времени.

- [ ] **Step 3: Реализовать отмену проведения**

Удалить записи регистратора.

- [ ] **Step 4: Прогнать**

Run: `db-load-xml`, затем `tests\posting\run-posting-tests.ps1`
Expected: `ИТОГО: 3/3`.

- [ ] **Step 5: Commit**

```bash
git add src/КурсоваяРабота/Documents/МаршрутныйЛист/Ext/ObjectModule.bsl epf/ТестПроведения tests/posting
git commit -m "feat(учёт): проведение маршрутного листа + тест"
```

<!-- openspec-task: 2.4 -->
### Task 4: `КорректировкаМаршрута` — замена времён и пересчёт буферов

**Files:**
- Modify: `src/КурсоваяРабота/Documents/КорректировкаМаршрута/Ext/ObjectModule.bsl`
- Modify: `epf/ТестПроведения/Forms/Форма/Ext/Form/Module.bsl` (сценарий `post-route-correction`)
- Modify: `tests/posting/run-posting-tests.ps1`

**Interfaces:**
- Consumes: `РаботаСДатамиИЧасовымиЗонами`, `ПроведениеДокументов`.

- [ ] **Step 1: Добавить сценарий `post-route-correction`**

Проверяет: после проведения время события в графике изменилось, буферы соседних событий пересчитаны, после отмены прежние времена восстановлены.
Run: `tests\posting\run-posting-tests.ps1 -Scenario post-route-correction`
Expected: FAIL.

- [ ] **Step 2: Реализовать проведение**

Обновить реквизиты времени записей по исходным событиям, пересчитать локальное время и буферы маршрутного листа.

- [ ] **Step 3: Реализовать отмену проведения**

Восстановить прежние времена и пересчитать буферы.

- [ ] **Step 4: Прогнать**

Run: `db-load-xml`, затем `tests\posting\run-posting-tests.ps1`
Expected: `ИТОГО: 4/4`.

- [ ] **Step 5: Commit**

```bash
git add src/КурсоваяРабота/Documents/КорректировкаМаршрута/Ext/ObjectModule.bsl epf/ТестПроведения tests/posting
git commit -m "feat(учёт): проведение корректировки маршрута + тест"
```

<!-- openspec-task: 2.5 -->
### Task 5: `СобытиеМаршрута` — проведение без движений

**Files:**
- Modify: `src/КурсоваяРабота/Documents/СобытиеМаршрута/Ext/ObjectModule.bsl`
- Modify: `epf/ТестПроведения/Forms/Форма/Ext/Form/Module.bsl` (сценарий `post-event`)
- Modify: `tests/posting/run-posting-tests.ps1`

**Interfaces:**
- Consumes: ничего.

- [ ] **Step 1: Добавить сценарий `post-event`**

Проверяет: количество записей `ГрафикПеремещений` до и после проведения события не изменилось.
Run: `tests\posting\run-posting-tests.ps1 -Scenario post-event`
Expected: FAIL — если у документа появилась логика, тест поймает расхождение.

- [ ] **Step 2: Реализовать пустую `ОбработкаПроведения`**

Тело без движений, комментарий со ссылкой на решение D3.

- [ ] **Step 3: Прогнать**

Run: `db-load-xml`, затем `tests\posting\run-posting-tests.ps1`
Expected: `ИТОГО: 5/5`.

- [ ] **Step 4: Commit**

```bash
git add src/КурсоваяРабота/Documents/СобытиеМаршрута/Ext/ObjectModule.bsl epf/ТестПроведения tests/posting
git commit -m "fix(учёт): событие маршрута не формирует движений + тест"
```

<!-- openspec-task: 2.6 -->
### Task 6: `ЗаявкаТуристаНаМаршруте` — история и эскалация

**Files:**
- Modify: `src/КурсоваяРабота/Documents/ЗаявкаТуристаНаМаршруте/Ext/ObjectModule.bsl`
- Modify: `epf/ТестПроведения/Forms/Форма/Ext/Form/Module.bsl` (сценарий `post-tourist-request`)
- Modify: `tests/posting/run-posting-tests.ps1`

**Interfaces:**
- Consumes: `ПроведениеДокументов.ЗаписатьСтатус`, `ЗадачиИсполнителям.СоздатьЗадачу`.

- [ ] **Step 1: Добавить сценарий `post-tourist-request`**

Проверяет: запись `ИсторияОбработокЗапросов` с действием `Регистрация`; при критическом уровне критичности — созданную задачу руководителю; после отмены записи и задачи нет.
Run: `tests\posting\run-posting-tests.ps1 -Scenario post-tourist-request`
Expected: FAIL.

- [ ] **Step 2: Реализовать проведение и отмену**

- [ ] **Step 3: Прогнать**

Run: `db-load-xml`, затем `tests\posting\run-posting-tests.ps1`
Expected: `ИТОГО: 6/6`.

- [ ] **Step 4: Commit**

```bash
git add src/КурсоваяРабота/Documents/ЗаявкаТуристаНаМаршруте/Ext/ObjectModule.bsl epf/ТестПроведения tests/posting
git commit -m "feat(учёт): проведение заявки туриста + тест"
```

<!-- openspec-task: 2.7 -->
### Task 7: `Инцидент` — открытие статуса

**Files:**
- Modify: `src/КурсоваяРабота/Documents/Инцидент/Ext/ObjectModule.bsl`
- Modify: `epf/ТестПроведения/Forms/Форма/Ext/Form/Module.bsl` (сценарий `post-incident`)
- Modify: `tests/posting/run-posting-tests.ps1`

**Interfaces:**
- Consumes: `ПроведениеДокументов.ЗаписатьСтатус`.

- [ ] **Step 1: Добавить сценарий `post-incident`**

Проверяет: одна запись `СтатусыИнцидентов` со статусом `Открыт` и ответственным из документа; после отмены — ноль записей.
Run: `tests\posting\run-posting-tests.ps1 -Scenario post-incident`
Expected: FAIL.

- [ ] **Step 2: Реализовать проведение и отмену**

- [ ] **Step 3: Прогнать**

Run: `db-load-xml`, затем `tests\posting\run-posting-tests.ps1`
Expected: `ИТОГО: 7/7`.

- [ ] **Step 4: Commit**

```bash
git add src/КурсоваяРабота/Documents/Инцидент/Ext/ObjectModule.bsl epf/ТестПроведения tests/posting
git commit -m "feat(учёт): проведение инцидента + тест"
```

<!-- openspec-task: 2.8 -->
### Task 8: `ПретензияПоставщику` — оборот требования

**Files:**
- Modify: `src/КурсоваяРабота/Documents/ПретензияПоставщику/Ext/ObjectModule.bsl`
- Modify: `epf/ТестПроведения/Forms/Форма/Ext/Form/Module.bsl` (сценарий `post-claim`)
- Modify: `tests/posting/run-posting-tests.ps1`

**Interfaces:**
- Consumes: `ПроведениеДокументов`.

- [ ] **Step 1: Добавить сценарий `post-claim`**

Проверяет: оборот с суммой требования по измерениям; попытка провести претензию с нулевой суммой отклоняется с сообщением; после отмены движений нет.
Run: `tests\posting\run-posting-tests.ps1 -Scenario post-claim`
Expected: FAIL.

- [ ] **Step 2: Реализовать проведение и отмену**

- [ ] **Step 3: Прогнать**

Run: `db-load-xml`, затем `tests\posting\run-posting-tests.ps1`
Expected: `ИТОГО: 8/8`.

- [ ] **Step 4: Commit**

```bash
git add src/КурсоваяРабота/Documents/ПретензияПоставщику/Ext/ObjectModule.bsl epf/ТестПроведения tests/posting
git commit -m "feat(учёт): проведение претензии поставщику + тест"
```

<!-- openspec-task: 2.9 -->
### Task 9: `АктОКомпенсации` — удовлетворение, компенсации, KPI, статус инцидента

**Files:**
- Modify: `src/КурсоваяРабота/Documents/АктОКомпенсации/Ext/ObjectModule.bsl`
- Modify: `epf/ТестПроведения/Forms/Форма/Ext/Form/Module.bsl` (сценарий `post-compensation-act`)
- Modify: `tests/posting/run-posting-tests.ps1`

**Interfaces:**
- Consumes: `ПроведениеДокументов` (включая `ЗарегистрироватьKPI`).

- [ ] **Step 1: Добавить сценарий `post-compensation-act`**

Проверяет: оборот удовлетворения, записи по видам компенсаций, KPI `УрегулированИнцидент`, статус инцидента `Урегулирован`; отказ при расхождении суммы строк с итогом; после отмены — движения удалены, инцидент `ВРаботе`, KPI удалён.
Run: `tests\posting\run-posting-tests.ps1 -Scenario post-compensation-act`
Expected: FAIL.

- [ ] **Step 2: Реализовать проведение**

- [ ] **Step 3: Реализовать отмену проведения**

- [ ] **Step 4: Прогнать полный набор**

Run: `db-load-xml`, затем `tests\posting\run-posting-tests.ps1`
Expected: `ИТОГО: 9/9`.

- [ ] **Step 5: Commit**

```bash
git add src/КурсоваяРабота/Documents/АктОКомпенсации/Ext/ObjectModule.bsl epf/ТестПроведения tests/posting
git commit -m "feat(учёт): проведение акта компенсации + тест"
```

<!-- openspec-task: 2.10 -->
### Task 10: Чек-лист для того, что не проверяется автоматически

**Files:**
- Modify: `docs/Чек-лист-проверки-расчётов.md`

**Interfaces:**
- Consumes: набор `tests/posting/run-posting-tests.ps1`.

- [ ] **Step 1: Переписать раздел проверки расчётов**

Указать, что движения и статусы покрыты автоматическим набором (команда запуска и ожидаемое `ИТОГО: 9/9`), а в чек-листе оставить только то, что требует человека: читаемость сообщений об ошибках, видимые статусы в формах, подсветка просрочек.

- [ ] **Step 2: Пройти ручные пункты и зафиксировать результат**

Run: `powershell -ExecutionPolicy Bypass -File tests\posting\run-posting-tests.ps1`, затем открыть документы по чек-листу.
Expected: набор зелёный; ручные пункты отмечены фактическим результатом.

- [ ] **Step 3: Commit**

```bash
git add docs/Чек-лист-проверки-расчётов.md
git commit -m "docs: чек-лист ручных проверок после автоматизации проведения"
```
