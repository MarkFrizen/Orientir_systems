# Обработки, запросы и приёмка — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Дать пользователю четыре массовые операции над учётными данными, запросы показателей и автоматическое доказательство, что учёт выдерживает полный прогон, отмену и регрессию по формам и обмену.

**Architecture:** Обработки — встроенные `DataProcessors`, работу выполняет модуль объекта, форма только собирает параметры. Каждый объект обрабатывается в своей транзакции, ошибки собираются в таблицу результата. Поведение проверяется тем же драйвером `ТестПроведения`: сценарии `proc-*` вызывают обработку напрямую и проверяют результат.

**Tech Stack:** 1С:Предприятие 8.3.27, файловая ИБ, `epf/ЗаполнениеНСИ` + `epf/run-fill.ps1` для демо-данных, `epf/run-check.ps1`, `tests/posting/run-posting-tests.ps1`, `tests/vanessa/run-xdd-smoke.ps1`, `tests/exchange/run-exchange-tests.ps1`.

**Spec:** `openspec/changes/implement-posting-and-data-processors/specs/data-processors/spec.md`, `design.md` (D6, D7, D8, D10).

## Global Constraints

- Перед пакетным запуском закрыть окна 1С: лицензия на одно место.
- Массовые операции не откатываются целиком: результат по каждому объекту отдельно.
- Аналитические операции — только чтение, без записи документов и движений.
- Запросы принимают период и отбор параметрами; никаких зашитых дат и ссылок.
- Порог согласования в демо — 10 000.
- Формат отчёта драйвера и коды возврата — как в плане 1: `ПРОВЕРКА: … — OK|FAIL`, `ВЕРДИКТ: PASS|FAIL`, exit 0/1/2.

## Review Focus

- Повторный запуск массового формирования создаёт дубли заказов.
- Пересчёт таймингов молча меняет проведённые документы.
- Обработка падает целиком из-за одной битой заявки.
- Сводка считает по реквизитам документов вместо движений и расходится с регистрами.
- Запуск обработки пользователем без прав создаёт документы.

---

<!-- openspec-task: 3.1 -->
### Task 1: Обработка формирования запросов поставщикам

**Files:**
- Create: `src/КурсоваяРабота/DataProcessors/ФормированиеЗапросовПоставщикам.xml`
- Create: `src/КурсоваяРабота/DataProcessors/ФормированиеЗапросовПоставщикам/Forms/Форма/...`
- Create: `src/КурсоваяРабота/DataProcessors/ФормированиеЗапросовПоставщикам/Ext/ObjectModule.bsl`
- Modify: `epf/ТестПроведения/Forms/Форма/Ext/Form/Module.bsl` (сценарий `proc-requests`)
- Modify: `tests/posting/run-posting-tests.ps1`

**Interfaces:**
- Produces: `Функция Выполнить(ПараметрыВыполнения) Экспорт` → `Структура` с `Результат` (ТаблицаЗначений: Заявка, Состояние, Причина) и `Итоги` (Создано, Пропущено, Ошибок).

- [ ] **Step 1: Добавить сценарий `proc-requests` и убедиться, что он падает**

Сценарий запускает обработку дважды: первый раз ожидает создание заказов по заявкам без заказов, второй — ноль новых и пометку «пропущено» с причиной. В конце помечает созданные заказы на удаление.
Run: `tests\posting\run-posting-tests.ps1 -Scenario proc-requests`
Expected: FAIL — обработки не существует.

- [ ] **Step 2: Создать обработку и форму**

Реквизиты формы: период, список заявок, флаг «Только без заказов», таблица результата, кнопка «Выполнить».

- [ ] **Step 3: Реализовать `Выполнить`**

Запросом отобрать заявки `ВРаботе` с услугами без заказа. По каждой заявке в своей транзакции создать заказ (через `Документы.ЗаказПоставщику.СоздатьДокумент`), заполнить услуги, записать. Успех и ошибка — отдельные строки результата.

- [ ] **Step 4: Прогнать сценарий**

Run: `db-load-xml`, затем `tests\posting\run-posting-tests.ps1 -Scenario proc-requests`
Expected: `ВЕРДИКТ: PASS` — пять заказов, повторный запуск даёт ноль новых.

- [ ] **Step 5: Commit**

```bash
git add src/КурсоваяРабота/DataProcessors/ФормированиеЗапросовПоставщикам* epf/ТестПроведения tests/posting
git commit -m "feat(учёт): обработка формирования запросов + тест"
```

<!-- openspec-task: 3.2 -->
### Task 2: Обработка пересчёта таймингов маршрутов

**Files:**
- Create: `src/КурсоваяРабота/DataProcessors/ПересчётТайминговМаршрутов.xml`
- Create: `src/КурсоваяРабота/DataProcessors/ПересчётТайминговМаршрутов/Forms/Форма/...`
- Create: `src/КурсоваяРабота/DataProcessors/ПересчётТайминговМаршрутов/Ext/ObjectModule.bsl`
- Modify: `epf/ТестПроведения/Forms/Форма/Ext/Form/Module.bsl` (сценарий `proc-timings`)
- Modify: `tests/posting/run-posting-tests.ps1`

**Interfaces:**
- Consumes: `РаботаСДатамиИЧасовымиЗонами`.
- Produces: `Функция Выполнить(ПараметрыВыполнения) Экспорт` → `Структура` с `Пересчитано`, `Пропущено`, `Накладки`.

- [ ] **Step 1: Добавить сценарий `proc-timings`**

Проверяет: непроведённые листы пересчитаны, проведённые без флага пропущены, проведённые с флагом пересчитаны, накладка попадает в результат с величиной перекрытия.
Run: `tests\posting\run-posting-tests.ps1 -Scenario proc-timings`
Expected: FAIL.

- [ ] **Step 2: Создать обработку и реализовать пересчёт**

Форма: список листов, флаг «Изменять проведённые», таблицы результата и накладок.

- [ ] **Step 3: Прогнать**

Run: `db-load-xml`, затем `tests\posting\run-posting-tests.ps1 -Scenario proc-timings`
Expected: PASS.

- [ ] **Step 4: Commit**

```bash
git add src/КурсоваяРабота/DataProcessors/ПересчётТайминговМаршрутов* epf/ТестПроведения tests/posting
git commit -m "feat(учёт): обработка пересчёта таймингов + тест"
```

<!-- openspec-task: 3.3 -->
### Task 3: Обработка выявления просроченных сроков и SLA

**Files:**
- Create: `src/КурсоваяРабота/DataProcessors/ПросроченныеСрокиИSLA.xml`
- Create: `src/КурсоваяРабота/DataProcessors/ПросроченныеСрокиИSLA/Forms/Форма/...`
- Create: `src/КурсоваяРабота/DataProcessors/ПросроченныеСрокиИSLA/Ext/ObjectModule.bsl`
- Modify: `epf/ТестПроведения/Forms/Форма/Ext/Form/Module.bsl` (сценарий `proc-overdue`)
- Modify: `tests/posting/run-posting-tests.ps1`

**Interfaces:**
- Consumes: `КонтрольСроков`, `ЗадачиИсполнителям.СоздатьЗадачу`.
- Produces: `Функция Выполнить(ПараметрыВыполнения) Экспорт` → `Структура` с `Просрочки`.

- [ ] **Step 1: Добавить сценарий `proc-overdue`**

Проверяет: при наличии просрочек — строки в результате и задачи при включённом флаге; при их отсутствии — пустой результат без ошибки. Созданные задачи помечаются на удаление.
Run: `tests\posting\run-posting-tests.ps1 -Scenario proc-overdue`
Expected: FAIL.

- [ ] **Step 2: Создать обработку и реализовать отбор**

- [ ] **Step 3: Прогнать**

Run: `db-load-xml`, затем `tests\posting\run-posting-tests.ps1 -Scenario proc-overdue`
Expected: PASS.

- [ ] **Step 4: Commit**

```bash
git add src/КурсоваяРабота/DataProcessors/ПросроченныеСрокиИSLA* epf/ТестПроведения tests/posting
git commit -m "feat(учёт): обработка выявления просрочек + тест"
```

<!-- openspec-task: 3.4 -->
### Task 4: Обработка сводки статусов

**Files:**
- Create: `src/КурсоваяРабота/DataProcessors/СводкаСтатусов.xml`
- Create: `src/КурсоваяРабота/DataProcessors/СводкаСтатусов/Forms/Форма/...`
- Create: `src/КурсоваяРабота/DataProcessors/СводкаСтатусов/Ext/ObjectModule.bsl`
- Modify: `epf/ТестПроведения/Forms/Форма/Ext/Form/Module.bsl` (сценарий `proc-summary`)
- Modify: `tests/posting/run-posting-tests.ps1`

**Interfaces:**
- Produces: `Функция Выполнить(Период, Отбор) Экспорт` → `ТаблицаЗначений` (Сущность, Статус, Количество); `Процедура ВыгрузитьВФайл(Таблица, ПутьФайла) Экспорт`.

- [ ] **Step 1: Добавить сценарий `proc-summary`**

Проверяет: количества по статусам совпадают с ручным подсчётом по регистрам и документам, пустой период даёт пустую таблицу без ошибки, выгрузка повторяет значения, число записей регистров до и после запуска одинаково.
Run: `tests\posting\run-posting-tests.ps1 -Scenario proc-summary`
Expected: FAIL.

- [ ] **Step 2: Создать обработку и реализовать четыре запроса**

Только чтение, без записи документов и движений.

- [ ] **Step 3: Прогнать**

Run: `db-load-xml`, затем `tests\posting\run-posting-tests.ps1 -Scenario proc-summary`
Expected: PASS, число записей регистров не изменилось.

- [ ] **Step 4: Commit**

```bash
git add src/КурсоваяРабота/DataProcessors/СводкаСтатусов* epf/ТестПроведения tests/posting
git commit -m "feat(учёт): обработка сводки статусов + тест"
```

<!-- openspec-task: 4.1 -->
### Task 5: Запрос сальдо по претензии

**Files:**
- Modify: `src/КурсоваяРабота/DataProcessors/СводкаСтатусов/Ext/ObjectModule.bsl`
- Modify: `epf/ТестПроведения/Forms/Форма/Ext/Form/Module.bsl` (сценарий `query-saldo`)
- Modify: `tests/posting/run-posting-tests.ps1`

**Interfaces:**
- Produces: `Функция СальдоПоПретензии(ПретензияСсылка) Экспорт` → `Число`.

- [ ] **Step 1: Добавить сценарий `query-saldo`**

Проверяет: требование 100 000 и удовлетворение 60 000 дают 40 000; после отмены акта — 100 000; претензия без акта — сумма требования. Считается по движениям, не по реквизитам.
Run: `tests\posting\run-posting-tests.ps1 -Scenario query-saldo`
Expected: FAIL.

- [ ] **Step 2: Реализовать запрос по оборотам регистра**

- [ ] **Step 3: Прогнать**

Run: `db-load-xml`, затем `tests\posting\run-posting-tests.ps1 -Scenario query-saldo`
Expected: PASS.

- [ ] **Step 4: Commit**

```bash
git add src/КурсоваяРабота/DataProcessors/СводкаСтатусов/Ext/ObjectModule.bsl epf/ТестПроведения tests/posting
git commit -m "feat(учёт): сальдо по движениям + тест"
```

<!-- openspec-task: 4.2 -->
### Task 6: Запрос KPI сотрудника

**Files:**
- Modify: `src/КурсоваяРабота/DataProcessors/СводкаСтатусов/Ext/ObjectModule.bsl`
- Modify: `epf/ТестПроведения/Forms/Форма/Ext/Form/Module.bsl` (сценарий `query-kpi`)
- Modify: `tests/posting/run-posting-tests.ps1`

**Interfaces:**
- Produces: `Функция KPIСотрудников(Период, Сотрудник = Неопределено) Экспорт` → `ТаблицаЗначений` (Сотрудник, ВидОперации, Количество, ВремяОбработкиМинут).

- [ ] **Step 1: Добавить сценарий `query-kpi`**

Проверяет: три проведённых подтверждения дают `ОбработанаЗаявка` с количеством 3 и временем, равным сумме регистра; сотрудник без операций даёт нули и пометку «нет операций».
Run: `tests\posting\run-posting-tests.ps1 -Scenario query-kpi`
Expected: FAIL.

- [ ] **Step 2: Реализовать запрос**

Группировка оборотов `KPIОператоров` по сотруднику и виду операции.

- [ ] **Step 3: Прогнать**

Run: `db-load-xml`, затем `tests\posting\run-posting-tests.ps1 -Scenario query-kpi`
Expected: PASS.

- [ ] **Step 4: Commit**

```bash
git add src/КурсоваяРабота/DataProcessors/СводкаСтатусов/Ext/ObjectModule.bsl epf/ТестПроведения tests/posting
git commit -m "feat(учёт): KPI по движениям + тест"
```

<!-- openspec-task: 4.3 -->
### Task 7: Команды обработок в подсистемах и проверка прав

**Files:**
- Modify: `src/КурсоваяРабота/Subsystems/ОператорСопровождения.xml`
- Modify: `src/КурсоваяРабота/Subsystems/КоординаторЛогистики.xml`
- Modify: `src/КурсоваяРабота/Subsystems/РуководительНаправления.xml`
- Modify: `src/КурсоваяРабота/DataProcessors/*/Ext/ObjectModule.bsl`

**Interfaces:**
- Consumes: `ПравоДоступа("Изменение", Метаданные.Документы.ЗаказПоставщику)` и аналогичные проверки в начале `Выполнить`.

- [ ] **Step 1: Включить обработки в подсистемы**

Через `subsystem-edit`: формирование запросов — «Оператор сопровождения»; пересчёт и просрочки — «Координатор логистики» и «Руководитель направления»; сводка — «Руководитель направления».

- [ ] **Step 2: Добавить проверку прав в начало `Выполнить`**

При отсутствии права — исключение с текстом об отсутствии прав, без состава данных.

- [ ] **Step 3: Проверить видимость команд**

Run: `subsystem-validate`, `db-load-xml`, открыть три раздела.
Expected: каждая обработка видна только в своих разделах, лишних команд нет.

- [ ] **Step 4: Проверить отказ без прав**

Run: на копии базы с ролью без прав на заказы запустить формирование запросов.
Expected: отказ с сообщением, документы не созданы. Если в базе только полноправный пользователь — зафиксировать ограничение проверки в `docs/Чек-лист-проверки-расчётов.md` и не считать пункт пройденным.

- [ ] **Step 5: Commit**

```bash
git add src/КурсоваяРабота/Subsystems src/КурсоваяРабота/DataProcessors docs/Чек-лист-проверки-расчётов.md
git commit -m "feat(учёт): команды обработок и проверка прав"
```

<!-- openspec-task: 5.1 -->
### Task 8: Полный прогон набора проведения

**Files:**
- Modify: `docs/Проверка-данных-2026-10-18.md` (или новый отчёт о приёмке)

**Interfaces:**
- Consumes: сценарии `post-*` из плана 2.

- [ ] **Step 1: Подготовить базу**

Run: `epf/run-fill.ps1` (окна 1С закрыты).
Expected: демо-набор наполнен.

- [ ] **Step 2: Прогнать набор проведения**

Run: `powershell -ExecutionPolicy Bypass -File tests\posting\run-posting-tests.ps1`
Expected: `ИТОГО: 9/9`, exit 0; после прогона регистры пусты.

- [ ] **Step 3: Проверить демо-набор**

Run: `epf/run-check.ps1`
Expected: `ВЕРДИКТ: PASS`.

- [ ] **Step 4: Записать результат и Commit**

```bash
git add docs
git commit -m "test: приёмка набора проведения"
```

<!-- openspec-task: 5.2 -->
### Task 9: Сценарий целостности

**Files:**
- Modify: `epf/ТестПроведения/Forms/Форма/Ext/Form/Module.bsl` (сценарий `integrity`)
- Modify: `tests/posting/run-posting-tests.ps1`

**Interfaces:**
- Consumes: обработчики проведения задач 1–9 плана 2.

- [ ] **Step 1: Добавить сценарий `integrity`**

Проверяет три свойства: при исключении в середине проведения регистры не содержат ни одной записи документа; повторное проведение не меняет количество записей; встречное проведение претензии и акта завершается без потери движений.
Run: `tests\posting\run-posting-tests.ps1 -Scenario integrity`
Expected: PASS на реализованном коде; FAIL, если найдено частичное проведение.

- [ ] **Step 2: Прогнать полный набор**

Run: `powershell -ExecutionPolicy Bypass -File tests\posting\run-posting-tests.ps1`
Expected: `ИТОГО: 10/10`.

- [ ] **Step 3: Commit**

```bash
git add epf/ТестПроведения tests/posting
git commit -m "test(учёт): сценарий целостности проведения"
```

<!-- openspec-task: 5.3 -->
### Task 10: Синтаксический контроль, валидация и регрессия

**Files:**
- Modify: исправления по результатам проверок (если будут)

- [ ] **Step 1: Диагностика изменённых модулей**

Run: `1c-lsp-diagnostics` по каждому изменённому `.bsl`.
Expected: 0 ошибок; предупреждения разобраны.

- [ ] **Step 2: Валидация конфигурации и объектов**

Run: `cf-validate`, `meta-validate`, `subsystem-validate` для новых объектов.
Expected: ошибок нет.

- [ ] **Step 3: Загрузить и обновить базу**

Run: `db-load-xml`, `db-update`.
Expected: конфигурация базы обновлена без ошибок.

- [ ] **Step 4: Регрессия**

Run: `tests\vanessa\run-xdd-smoke.ps1` → `83/83`; `tests\exchange\run-exchange-tests.ps1` → `8/8`; `epf/run-check.ps1` → `PASS`; `tests\posting\run-posting-tests.ps1` → `10/10`.
Expected: все четыре прогона зелёные.

- [ ] **Step 5: Commit**

```bash
git add -A
git commit -m "chore: контроль конфигурации и регрессия после реализации учёта"
```
