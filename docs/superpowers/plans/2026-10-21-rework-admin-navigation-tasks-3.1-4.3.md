# Настройки администратора вместо раздела «Сервис» — план 2: командный интерфейс, права, документация

> **For agentic workers:** REQUIRED SUB-SKILL: Use `/opsx-executing-plans rework-admin-navigation` to implement this plan task-by-task and sync progress back to OpenSpec. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Сделать константу видимой и редактируемой в «Администратор ИС», скрыть оттуда технические объекты, выдать роли право изменения и привести документацию в соответствие с новым составом подсистем.

**Architecture:** Командный интерфейс `АдминистраторИС` создаётся с нуля — файла `Ext/CommandInterface.xml` у неё нет. Прятать команды нужно явно, потому что по умолчанию всё, что попало в состав подсистемы, показывается в навигации. Права добавляются точечно: роль сейчас пустая, и любая выдача прав должна оставаться минимальной.

**Tech Stack:** 1С:Предприятие 8.3.27, XML-выгрузка `src/КурсоваяРабота`, скиллы `interface-edit`, `role-edit`, `role-validate`, `cf-validate`, `meta-validate`, `subsystem-info`.

**Spec:**
- `openspec/changes/rework-admin-navigation/specs/navigation-and-commands/spec.md` — оба новых требования
- `openspec/changes/rework-admin-navigation/design.md` — решения 4, 5
- `openspec/changes/rework-admin-navigation/tasks.md` — задачи 3.1–4.3

## Global Constraints

- Платформа 8.3.27, режим совместимости `Version8_3_27`, управляемое приложение.
- Метаданные правятся только скиллами проекта; ручное редактирование XML запрещено.
- XML выгрузки — UTF-8 с BOM.
- UUID роли `Администратор` и подсистемы `АдминистраторИС` не меняются.
- У константы команда называется `StandardCommand.Open`, а не `OpenList`: платформа отвергает `OpenList` для константы с ошибкой «Неизвестная команда».
- Подсистема `НастройкиИнтеграций` и её файлы не изменяются.

## Review Focus

- **Команды, которых не существует.** `Enum` не имеет `StandardCommand.OpenList`; попытка скрыть её валит загрузку конфигурации — ожидается, что ни одно перечисление не упоминается в командном интерфейсе.
- **Файл командного интерфейса отсутствует.** `АдминистраторИС/Ext/CommandInterface.xml` не существует; если скилл не создаст его, скрытие молча не применится — ожидается созданный файл с явными записями.
- **Права роли.** Роль пустая; добавление права только на константу не должно затереть флаги `setForNewObjects` и `setForAttributesByDefault` — ожидается одна запись объекта и сохранённые флаги.
- **Документация расходится с фактом.** Числа «25 подсистем» и «19 листовых» после удаления «Сервиса» станут неверными — ожидается пересчёт по фактическим файлам, а не вычитание единицы на глаз.
- **`ЗадачаИсполнителя` была видимой по решению D8.** Теперь она скрывается; в документации это должно быть названо явно, иначе следующий читатель решит, что решение потеряли.

---

<!-- openspec-task: 3.1 -->
### Task 8: Создать командный интерфейс «Администратор ИС»

**Files:**
- Create: `src/КурсоваяРабота/Subsystems/АдминистраторИС/Ext/CommandInterface.xml`

**Interfaces:**
- Consumes: состав `АдминистраторИС` из задачи 4 (пять объектов)
- Produces: файл командного интерфейса; на него опирается задача 9

- [ ] **Step 1: Зафиксировать отсутствие файла**

Run:
```powershell
Test-Path "src/КурсоваяРабота/Subsystems/АдминистраторИС/Ext/CommandInterface.xml"
```
Expected: `False`.

- [ ] **Step 2: Создать командный интерфейс**

Использовать скилл `interface-edit` для подсистемы `АдминистраторИС`. Файл создаётся пустым по скрытиям: константу не скрывать.

- [ ] **Step 3: Проверить, что файл создан и константа не скрыта**

Run:
```powershell
Test-Path "src/КурсоваяРабота/Subsystems/АдминистраторИС/Ext/CommandInterface.xml"; Select-String -Path "src/КурсоваяРабота/Subsystems/АдминистраторИС/Ext/CommandInterface.xml" -Pattern "Constant\."
```
Expected: `True` и ни одного совпадения — константа остаётся видимой по умолчанию.

- [ ] **Step 4: Провалидировать подсистему**

Использовать скилл `meta-validate` для `Subsystems/АдминистраторИС.xml`.
Expected: 0 ошибок.

- [ ] **Step 5: Коммит**

```bash
git add "src/КурсоваяРабота/Subsystems/АдминистраторИС"
git commit -m "feat(subsystems): add command interface to admin section"
```

---

<!-- openspec-task: 3.2 -->
### Task 9: Скрыть технические команды в «Администратор ИС»

**Files:**
- Modify: `src/КурсоваяРабота/Subsystems/АдминистраторИС/Ext/CommandInterface.xml`

**Interfaces:**
- Consumes: файл из задачи 8
- Produces: навигацию раздела, в которой видна только константа

- [ ] **Step 1: Скрыть четыре команды**

Использовать скилл `interface-edit`, добавив в `<CommandsVisibility>` записи с `Visibility = false` ровно для:

- `ChartOfCharacteristicTypes.ДополнительныеРеквизитыТуриста.StandardCommand.OpenList`
- `ChartOfCharacteristicTypes.ДополнительныеРеквизитыУслуг.StandardCommand.OpenList`
- `Task.ЗадачаИсполнителя.StandardCommand.OpenList`
- `InformationRegister.АдресацияЗадач.StandardCommand.OpenList`

- [ ] **Step 2: Проверить, что скрыто ровно четыре**

Run:
```powershell
(Select-String -Path "src/КурсоваяРабота/Subsystems/АдминистраторИС/Ext/CommandInterface.xml" -Pattern "Visibility").Count
```
Expected: 4.

- [ ] **Step 3: Проверить, что ни одно перечисление не упомянуто**

Run:
```powershell
Select-String -Path "src/КурсоваяРабота/Subsystems/АдминистраторИС/Ext/CommandInterface.xml" -Pattern "Enum\."
```
Expected: ни одного совпадения. У перечислений нет команды `OpenList`, платформа такую запись отвергает.

- [ ] **Step 4: Провалидировать**

Использовать скиллы `meta-validate` (подсистема) и `cf-validate` (конфигурация).
Expected: 0 ошибок.

- [ ] **Step 5: Коммит**

```bash
git add "src/КурсоваяРабота/Subsystems/АдминистраторИС/Ext/CommandInterface.xml"
git commit -m "feat(subsystems): hide technical commands in admin section"
```

---

<!-- openspec-task: 3.3 -->
### Task 10: Выдать роли права на константу

**Files:**
- Modify: `src/КурсоваяРабота/Roles/Администратор/Ext/Rights.xml`

**Interfaces:**
- Consumes: существующую роль с флагами `setForNewObjects` и `setForAttributesByDefault`
- Produces: право `Read` и `Update` на `Constant.ПорогСогласованияРуководителем`

- [ ] **Step 1: Зафиксировать исходное состояние**

Run:
```powershell
Select-String -Path "src/КурсоваяРабота/Roles/Администратор/Ext/Rights.xml" -Pattern "Constant|setForNewObjects"
```
Expected: только флаги, ни одного объекта.

- [ ] **Step 2: Добавить права**

Использовать скилл `role-edit` для `Roles/Администратор`: объект `Constant.ПорогСогласованияРуководителем`, права `Read` и `Update`.

- [ ] **Step 3: Проверить результат**

Run:
```powershell
Select-String -Path "src/КурсоваяРабота/Roles/Администратор/Ext/Rights.xml" -Pattern "ПорогСогласованияРуководителем|Read|Update|setForNewObjects"
```
Expected: одна запись объекта с `Read` и `Update`; флаги `setForNewObjects` и `setForAttributesByDefault` сохранились.

- [ ] **Step 4: Провалидировать роль**

Использовать скилл `role-validate`.
Expected: 0 ошибок.

- [ ] **Step 5: Коммит**

```bash
git add "src/КурсоваяРабота/Roles/Администратор/Ext/Rights.xml"
git commit -m "feat(roles): let administrator change approval threshold"
```

---

<!-- openspec-task: 3.4 -->
### Task 11: Провалидировать метаданные целиком

**Files:**
- Modify: только если валидация нашла ошибки

**Interfaces:**
- Consumes: результаты задач 4–10
- Produces: конфигурацию без ошибок, готовую к загрузке

- [ ] **Step 1: Проверить конфигурацию**

Использовать скилл `cf-validate`.
Expected: 0 ошибок, включая отсутствие ссылок на удалённую подсистему.

- [ ] **Step 2: Проверить изменённые объекты**

Использовать скиллы `meta-validate` (подсистема `АдминистраторИС`) и `role-validate` (роль `Администратор`).
Expected: 0 ошибок в обоих.

- [ ] **Step 3: Проверить, что ссылок на «Сервис» не осталось**

Run:
```powershell
Select-String -Path "src/КурсоваяРабота/Configuration.xml" -Pattern "Сервис"
```
Expected: ни одного совпадения.

- [ ] **Step 4: Исправить и повторить**

Если валидация нашла ошибки — устранить и прогнать шаги 1–3 заново.
Expected: 0 ошибок.

- [ ] **Step 5: Коммит (если были правки)**

```bash
git add "src/КурсоваяРабота"
git commit -m "fix(metadata): resolve validation errors after subsystem move"
```

---

<!-- openspec-task: 4.1 -->
### Task 12: Обновить чек-лист форм

**Files:**
- Modify: `docs/Чек-лист-форм.md` — раздел «Навигация подсистем»

**Interfaces:**
- Consumes: фактический состав подсистем после задач 4–5
- Produces: документ, в котором нет строки `Сервис`

- [ ] **Step 1: Найти устаревшие места**

Run:
```powershell
Select-String -Path "docs/Чек-лист-форм.md" -Pattern "Сервис"
```
Expected: не меньше четырёх совпадений — таблица навигации, примечание про `ЗадачаИсполнителя`, пояснение про `Enum` и `Constant`.

- [ ] **Step 2: Переписать таблицу навигации**

Убрать строку `Сервис`. Добавить в строку `Администратор ИС` команду `ПорогСогласованияРуководителем` как видимую.

- [ ] **Step 3: Обновить примечание про задачу**

Заменить текст про решение D8: `ЗадачаИсполнителя` больше не остаётся видимой — она переехала в «Администратор ИС» и скрыта, потому что относится к техническим объектам.

- [ ] **Step 4: Обновить пояснение про `Enum` и `Constant`**

Оставить факт: у `Enum` нет `StandardCommand.OpenList`. Дописать, что константа использует `StandardCommand.Open` и потому скрывается/показывается именно этой командой.

- [ ] **Step 5: Проверить**

Run:
```powershell
Select-String -Path "docs/Чек-лист-форм.md" -Pattern "Сервис"
```
Expected: ни одного совпадения.

- [ ] **Step 6: Коммит**

```bash
git add "docs/Чек-лист-форм.md"
git commit -m "docs: update subsystem navigation after service section removal"
```

---

<!-- openspec-task: 4.2 -->
### Task 13: Обновить отчёт по подсистемам

**Files:**
- Modify: `docs/Отчёт-по-подсистемам.md`

**Interfaces:**
- Consumes: фактическое число подсистем
- Produces: отчёт, совпадающий с выгрузкой

- [ ] **Step 1: Сосчитать фактические числа**

Run:
```powershell
(Get-ChildItem "src/КурсоваяРабота/Subsystems" -Filter *.xml).Count
(Select-String -Path "src/КурсоваяРабота/Configuration.xml" -Pattern "<Subsystem>" -SimpleMatch).Count
```
Expected: 6 файлов верхнего уровня и 6 записей `<Subsystem>` в корне конфигурации. Общее число подсистем — по фактическому дереву, а не «25 минус один».

- [ ] **Step 2: Исправить вводный абзац**

Строка «Создано 25 подсистем: 6 верхнего уровня, 18 вложенных и служебная «Сервис»» переписывается под фактические числа; упоминание «Сервиса» убирается.

- [ ] **Step 3: Убрать раздел «Сервис»**

Удалить строку «Сервис (22 объектов)» и строку таблицы состава подсистемы `Сервис`.

- [ ] **Step 4: Перенести состав**

В таблицу состава добавить в строку `Администратор ИС` пять объектов: константу, два плана видов характеристик, задачу и регистр адресации.

- [ ] **Step 5: Обновить принятые решения**

В разделе «Принятые решения и отклонения» заменить пункт про вынос служебных объектов в «Сервис» на: служебные объекты входят в «Администратор ИС», раздел «Сервис» упразднён.

- [ ] **Step 6: Проверить**

Run:
```powershell
Select-String -Path "docs/Отчёт-по-подсистемам.md" -Pattern "Сервис"
```
Expected: ни одного совпадения.

- [ ] **Step 7: Коммит**

```bash
git add "docs/Отчёт-по-подсистемам.md"
git commit -m "docs: refresh subsystem report after section removal"
```

---

<!-- openspec-task: 4.3 -->
### Task 14: Обновить документ оставшихся задач

**Files:**
- Modify: `docs/Оставшиеся-задачи.md`

**Interfaces:**
- Consumes: результаты задач 4–13
- Produces: документ, который не обещает уже сделанное

- [ ] **Step 1: Найти устаревшие числа**

Run:
```powershell
Select-String -Path "docs/Оставшиеся-задачи.md" -Pattern "Сервис|25 подсистем|19 листовых"
```
Expected: три совпадения — состояние проекта и два места про навигацию.

- [ ] **Step 2: Обновить состояние проекта**

Заменить «25 подсистем по рабочим местам + «Сервис»» на фактическое число без «Сервиса».

- [ ] **Step 3: Обновить навигацию**

Заменить «19 листовых подсистем» на фактическое число после удаления раздела. Добавить фразу: константа `ПорогСогласованияРуководителем` доступна администратору из раздела «Администратор ИС».

- [ ] **Step 4: Оставить профили в остатке**

Проверить, что раздел про семь профилей групп доступа не тронут и по-прежнему числится в остатке — именно они дают настоящее разделение «администратор ИС / администратор 1С».

- [ ] **Step 5: Проверить**

Run:
```powershell
Select-String -Path "docs/Оставшиеся-задачи.md" -Pattern "Сервис"
```
Expected: ни одного совпадения.

- [ ] **Step 6: Коммит**

```bash
git add "docs/Оставшиеся-задачи.md"
git commit -m "docs: reflect admin navigation changes in remaining tasks"
```

---

## Проверка плана

- [ ] `АдминистраторИС/Ext/CommandInterface.xml` существует, в нём ровно 4 записи `Visibility = false`
- [ ] Ни одно перечисление не упомянуто в командном интерфейсе
- [ ] В `Rights.xml` одна запись объекта с `Read` и `Update`, флаги на месте
- [ ] `cf-validate`, `meta-validate`, `role-validate` — 0 ошибок
- [ ] В трёх документах нет слова «Сервис»
- [ ] `git log --oneline -7` показывает коммиты задач плана
