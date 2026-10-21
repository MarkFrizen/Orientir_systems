# Обмен данными через CSV — подготовка и метаданные — План реализации

> **For agentic workers:** REQUIRED SUB-SKILL: используйте `/opsx-executing-plans add-csv-data-exchange` для реализации плана по задачам. Шаги отмечены чекбоксами (`- [ ]`).

**Goal:** Подготовить базу и создать в конфигурации носители будущего обмена — общий модуль `ОбменCSV` и обработку `ОбменСФайлами` — так, чтобы всё валидировалось и загружалось в ИБ.

**Architecture:** Сначала фиксируется исходное состояние (LSP, бэкап, базовая линия проверок). Затем через `meta-compile` и `form-add` создаются два объекта метаданных, они регистрируются в `Configuration.xml` и в подсистеме «Администратор ИС». Кода логики на этом этапе нет — только пустые модули и проверяемая структура.

**Tech Stack:** 1С:Предприятие 8.3.27.1786, файловая ИБ, XML-выгрузка конфигурации, bsl-language-server, PowerShell.

**Spec:** `openspec/changes/add-csv-data-exchange/specs/data-exchange/spec.md`, `openspec/changes/add-csv-data-exchange/design.md`

## Global Constraints

- Платформа `8.3.27.1786`, файловая ИБ `db/КурсоваяРабота`, тонкий клиент.
- Все новые модули — серверные: `Сервер = Истина`, `ВызовСервера = Ложь`, `Клиент = Ложь`, `ВнешнееСоединение = Истина`, `Привилегированный = Ложь`.
- Исходники и любые файлы для 1С — UTF-8; JSON и PS1 — UTF-8 с BOM. Ровно один BOM: двойной ломает XML.
- Строки длиннее 1024 символов в файловую ИБ записать нельзя.
- Команды к базе выполняются с `-UserName "Администратор"`, пароль пустой.
- `ОбменДанными.Загрузка` в коде обмена не выставляется нигде.
- Лицензия на одно место: перед любым прогоном закрыть все сеансы 1С.
- Коммиты — английские conventional-сообщения, в код и коммиты мат не попадает.

## Review Focus

- **LSP сбит на каталог установки** — после старта `root_path` может указывать на `C:\Users\vladi\AppData\Local\...\bsl-language-server`, и индексация висит на 0%. Ожидаемое поведение: `ready` и `100`; иначе все проверки дальше врут.
- **Двойной BOM в новом XML** — `meta-compile` и `form-add` пишут файлы сами, но любая ручная правка PowerShell может добавить второй BOM. Ожидаемое поведение: XML открывается платформой, а не «повреждён».
- **Обработка не попала в подсистему** — объект создан и валиден, но команды в разделе «Администратор ИС» нет. Ожидаемое поведение: команда открытия видна в панели навигации раздела.
- **Порядок `<ChildObjects>` в `Configuration.xml`** — вставка `Processing` не в своё место даёт ошибку разбора конфигурации при загрузке. Ожидаемое поведение: `cf-validate` зелёный, `db-load-xml` проходит.
- **Бэкап сделан после изменений** — если `.dt` снять не до правок, откат вернёт уже испорченное состояние. Ожидаемое поведение: файл бэкапа датирован раньше первого изменения.

---

<!-- openspec-task: 1.1 -->
### Task 1: Проверить готовность LSP

**Files:**
- Modify: нет (только диагностика)

**Interfaces:**
- Consumes: ничего
- Produces: подтверждение, что проект проиндексирован; без этого задачи 4–7 нечем валидировать

- [x] **Step 1: Запросить состояние проектов**

```powershell
[Console]::OutputEncoding = [System.Text.Encoding]::UTF8
(Invoke-WebRequest http://127.0.0.1:4000/api/projects -UseBasicParsing).Content
```

- [x] **Step 2: Сверить ответ**

Ожидается `"root_path": "D:\\Projects\\1C_prj\\7 семестр\\Kursovaya"`, `"status": "ready"`, `"percentage": 100`.

- [x] **Step 3: Починить, если путь сбит**

Открыть `http://127.0.0.1:4000`, открыть карточку проекта, выставить «Корневой путь BSL» = `D:\Projects\1C_prj\7 семестр\Kursovaya` (не трогая «Корневой путь всего проекта»), сохранить, затем Stop → Start. Повторить Step 1.

- [x] **Step 4: Проверить, что диагностика отвечает**

Прогнать инструмент `1c-lsp-diagnostics` для `src/КурсоваяРабота/CommonModules/КонтрольСроков/Ext/Module.bsl`. Ожидается список диагностик, а не сообщение «Проект еще не готов».

- [x] **Step 5: Зафиксировать**

Коммит не нужен: репозиторий не менялся. Результат шага — зелёный LSP, на который опираются все последующие проверки.

---

<!-- openspec-task: 1.2 -->
### Task 2: Сделать бэкап информационной базы

**Files:**
- Create: `db/backup-2026-10-21-before-exchange.dt` (вне git)

**Interfaces:**
- Consumes: ничего
- Produces: точку отката для всей ветки работ

- [x] **Step 1: Убедиться, что сеансов 1С нет**

```powershell
Get-Process | Where-Object { $_.ProcessName -like '1cv8*' } | Select-Object Id, ProcessName
```

Ожидается пустой вывод. Если процессы есть — закрыть их и повторить.

- [x] **Step 2: Выгрузить ИБ**

Прогнать skill `db-dump-dt` для базы `dev` (`db/КурсоваяРабота`), файл — `db/backup-2026-10-21-before-exchange.dt`.

- [x] **Step 3: Проверить артефакт**

```powershell
Get-Item "db\backup-2026-10-21-before-exchange.dt" | Select-Object Length, LastWriteTime
```

Ожидается `Length` больше нуля.

- [x] **Step 4: Зафиксировать**

Коммит не нужен: `db/` не входит в поставку исходников. Дата файла должна быть раньше первого изменения конфигурации.

---

<!-- openspec-task: 1.3 -->
### Task 3: Зафиксировать базовую линию проверок

**Files:**
- Modify: нет (только прогоны)

**Interfaces:**
- Consumes: Task 1 (работающий LSP), Task 2 (бэкап на случай сюрпризов)
- Produces: эталонные числа `PASS` и `82/82`, с которыми сравниваются результаты в плане 6

- [x] **Step 1: Прогнать проверку демо-набора**

```powershell
powershell -ExecutionPolicy Bypass -File epf\run-check.ps1
```

Ожидается вердикт `PASS` в логе.

- [x] **Step 2: Прогнать дымовые тесты**

```powershell
powershell -ExecutionPolicy Bypass -File tests\vanessa\run-xdd-smoke.ps1
```

Ожидается 82 пройденных теста, 0 упавших.

- [x] **Step 3: Записать базовую линию**

Создать `docs/Обмен-данными.md` с разделом `## Базовая линия` и двумя строками: `run-check.ps1` → `PASS`, `run-xdd-smoke.ps1` → `82/82`, с датой `2026-10-21`. Файл дальше дополняется в планах 2–4.

- [x] **Step 4: Коммит**

```bash
git add docs/Обмен-данными.md
git commit -m "docs: record baseline check results before exchange work"
```

---

<!-- openspec-task: 2.1 -->
### Task 4: Создать общий модуль `ОбменCSV`

**Files:**
- Create: `src/КурсоваяРабота/CommonModules/ОбменCSV.xml`
- Create: `src/КурсоваяРабота/CommonModules/ОбменCSV/Ext/Module.bsl`

**Interfaces:**
- Consumes: Task 1 (LSP)
- Produces: метаданные модуля и пустой файл `Module.bsl`, в который план 2 добавляет `РазобратьСтроку`, `СобратьСтроку`, `ПрочитатьФайл`, `ЗаписатьФайл`, `ПривестиКЧислу`, `ПривестиКДате`, `ПривестиКБулеву`

- [x] **Step 1: Проверить, что объекта ещё нет**

Прогнать `meta-info` для `CommonModule.ОбменCSV`. Ожидается сообщение, что объект не найден. Это красная часть проверки.

- [x] **Step 2: Создать модуль**

Прогнать skill `meta-compile` с описанием: вид объекта `CommonModule`, имя `ОбменCSV`, синоним «Обмен CSV», комментарий «Разбор и сборка CSV-файлов обмена», свойства `Сервер = Истина`, `ВызовСервера = Ложь`, `Клиент = Ложь`, `ВнешнееСоединение = Истина`, `Привилегированный = Ложь`.

- [x] **Step 3: Убедиться, что оба файла созданы**

```powershell
Get-ChildItem "src\КурсоваяРабота\CommonModules\ОбменCSV*" -Recurse | Select-Object FullName, Length
```

Ожидается два пути: `CommonModules\ОбменCSV.xml` и `CommonModules\ОбменCSV\Ext\Module.bsl`.

- [x] **Step 4: Проверить конфигурацию**

Прогнать skill `cf-validate` для `src/КурсоваяРабота`. Ожидается отсутствие ошибок.

- [x] **Step 5: Проверить модуль диагностикой**

Прогнать `1c-lsp-diagnostics` для `src/КурсоваяРабота/CommonModules/ОбменCSV/Ext/Module.bsl`. Ожидается пустой список или только информационные замечания — синтаксических ошибок быть не должно.

- [x] **Step 6: Коммит**

```bash
git add src/КурсоваяРабота/CommonModules/ОбменCSV.xml src/КурсоваяРабота/CommonModules/ОбменCSV/Ext/Module.bsl
git commit -m "feat: add ОбменCSV common module metadata"
```

---

<!-- openspec-task: 2.2 -->
### Task 5: Создать обработку `ОбменСФайлами` с пустой формой

**Files:**
- Create: `src/КурсоваяРабота/DataProcessors/ОбменСФайлами.xml`
- Create: `src/КурсоваяРабота/DataProcessors/ОбменСФайлами/Ext/ObjectModule.bsl`
- Create: `src/КурсоваяРабота/DataProcessors/ОбменСФайлами/Forms/Форма.xml`
- Create: `src/КурсоваяРабота/DataProcessors/ОбменСФайлами/Forms/Форма/Ext/Form.xml`
- Create: `src/КурсоваяРабота/DataProcessors/ОбменСФайлами/Forms/Форма/Ext/Form/Module.bsl`

**Interfaces:**
- Consumes: Task 4 (модуль `ОбменCSV` существует — обработка будет его вызывать)
- Produces: `Обработки.ОбменСФайлами.Создать()` как точку входа; экспортные методы `НовыйОтчёт`, `ВыгрузитьНоменклатуру`, `ЗагрузитьНоменклатуру`, `ВыгрузитьЗаказы`, `ЗагрузитьЗаказы`, `ЗаписатьОтчёт` добавляются в планах 2–4

- [x] **Step 1: Проверить, что обработки ещё нет**

Прогнать `meta-info` для `DataProcessor.ОбменСФайлами`. Ожидается «объект не найден».

- [x] **Step 2: Создать обработку**

Прогнать `meta-compile`: вид `DataProcessor`, имя `ОбменСФайлами`, синоним «Обмен данными с файлами», комментарий «Выгрузка и загрузка номенклатуры и заказов через CSV».

- [x] **Step 3: Добавить управляемую форму**

Прогнать skill `form-add` для объекта `DataProcessor.ОбменСФайлами`, имя формы `Форма`, тип `Managed`, назначение — форма объекта по умолчанию.

- [x] **Step 4: Убедиться, что пять файлов на месте**

```powershell
Get-ChildItem "src\КурсоваяРабота\DataProcessors\ОбменСФайлами" -Recurse -File | Select-Object FullName
```

Ожидается пять файлов: корневой `ОбменСФайлами.xml`, `Ext\ObjectModule.bsl`, `Forms\Форма.xml`, `Forms\Форма\Ext\Form.xml`, `Forms\Форма\Ext\Form\Module.bsl`.

- [x] **Step 5: Проверить метаданные и форму**

Прогнать `meta-validate` для `DataProcessor.ОбменСФайлами` и `form-validate` для формы `Форма`. Ожидается: ошибок нет, форма проходит 1 из 1.

- [x] **Step 6: Проверить статическим валидатором структуры форм**

```powershell
python tests\forms\validate_form_structure.py "src\КурсоваяРабота\DataProcessors\ОбменСФайлами\Forms\Форма\Ext\Form.xml"
```

Ожидается отсутствие ошибок.

- [x] **Step 7: Коммит**

```bash
git add src/КурсоваяРабота/DataProcessors/ОбменСФайлами.xml src/КурсоваяРабота/DataProcessors/ОбменСФайлами/Ext/ObjectModule.bsl src/КурсоваяРабота/DataProcessors/ОбменСФайлами/Forms
git commit -m "feat: add ОбменСФайлами data processor with empty form"
```

---

<!-- openspec-task: 2.3 -->
### Task 6: Зарегистрировать обработку в конфигурации и подсистеме

**Files:**
- Modify: `src/КурсоваяРабота/Configuration.xml` — блок `<ChildObjects>`, после элементов `<Document>`
- Modify: `src/КурсоваяРабота/Subsystems/АдминистраторИС.xml` — блок `<Content>`

**Interfaces:**
- Consumes: Task 5 (`DataProcessors/ОбменСФайлами.xml` существует)
- Produces: `Processing.ОбменСФайлами` доступен в глобальном контексте и в панели навигации раздела «Администратор ИС»

- [x] **Step 1: Проверить, что регистрации нет**

```powershell
Select-String -Path "src\КурсоваяРабота\Configuration.xml" -Pattern "Processing\."
Select-String -Path "src\КурсоваяРабота\Subsystems\АдминистраторИС.xml" -Pattern "Processing\."
```

Ожидается пустой вывод по обоим файлам.

- [x] **Step 2: Добавить в `Configuration.xml`**

Вставить `<Processing>ОбменСФайлами</Processing>` в `<ChildObjects>` между последним `<Document>` и первым `<Enum>`. Порядок видов объектов в выгрузке 1С фиксирован — `Document` идёт до `Processing`, `Processing` до `Enum`.

- [x] **Step 3: Добавить в подсистему**

В `<Content>` файла `src/КурсоваяРабота/Subsystems/АдминистраторИС.xml` добавить строку:

```xml
<xr:Item xsi:type="xr:MDObjectRef">Processing.ОбменСФайлами</xr:Item>
```

- [x] **Step 4: Проверить, что регистрация появилась**

```powershell
Select-String -Path "src\КурсоваяРабота\Configuration.xml" -Pattern "Processing\.ОбменСФайлами"
Select-String -Path "src\КурсоваяРабота\Subsystems\АдминистраторИС.xml" -Pattern "Processing\.ОбменСФайлами"
```

Ожидается по одной строке в каждом файле.

- [x] **Step 5: Проверить конфигурацию**

Прогнать `cf-validate` для `src/КурсоваяРабота`. Ожидается отсутствие ошибок. Если появилась ошибка разбора — вернуться к Step 2 и сверить позицию вставки.

- [x] **Step 6: Коммит**

```bash
git add src/КурсоваяРабота/Configuration.xml src/КурсоваяРабота/Subsystems/АдминистраторИС.xml
git commit -m "feat: register ОбменСФайлами in configuration and admin subsystem"
```

---

<!-- openspec-task: 2.4 -->
### Task 7: Обновить состав конфигурации в документации

**Files:**
- Modify: `docs/Оставшиеся-задачи.md` — раздел о составе объектов

**Interfaces:**
- Consumes: Task 6 (объекты зарегистрированы)
- Produces: актуальное число прикладных объектов (61 вместо 59) для плана 6

- [x] **Step 1: Сосчитать фактическое число объектов**

```powershell
$root = "src\КурсоваяРабота"
$kinds = @('Catalogs','Documents','DataProcessors','InformationRegisters','AccumulationRegisters','CommonModules','Enums','BusinessProcesses','Tasks','Constants','ChartsOfCharacteristicTypes','Reports')
$total = 0
foreach ($k in $kinds) { if (Test-Path "$root\$k") { $n = (Get-ChildItem "$root\$k" -Filter *.xml -File).Count; $total += $n; "$k = $n" } }
"TOTAL = $total"
```

Ожидается `TOTAL = 61`.

- [x] **Step 2: Найти устаревшее число в документе**

```powershell
Select-String -Path "docs\Оставшиеся-задачи.md" -Pattern "59"
```

Ожидается строка с числом 59.

- [x] **Step 3: Исправить число и дописать объекты**

Заменить 59 на 61 и добавить в перечень новый общий модуль `ОбменCSV` и обработку `ОбменСФайлами`.

- [x] **Step 4: Проверить, что старого числа не осталось**

```powershell
Select-String -Path "docs\Оставшиеся-задачи.md" -Pattern "59 прикладн"
```

Ожидается пустой вывод.

- [x] **Step 5: Коммит**

```bash
git add docs/Оставшиеся-задачи.md
git commit -m "docs: update configuration object count after adding exchange module"
```
