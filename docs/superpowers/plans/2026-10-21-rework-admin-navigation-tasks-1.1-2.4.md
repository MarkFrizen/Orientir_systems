# Настройки администратора вместо раздела «Сервис» — план 1: подготовка и перенос подсистем

> **For agentic workers:** REQUIRED SUB-SKILL: Use `/opsx-executing-plans rework-admin-navigation` to implement this plan task-by-task and sync progress back to OpenSpec. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Переложить содержимое подсистемы «Сервис» в «Администратор ИС» и удалить «Сервис», не потеряв ни одного объекта и не тронув рабочие «Настройки интеграций».

**Architecture:** Работа идёт по метаданным выгрузки. Порядок жёсткий: сначала состав `АдминистраторИС` получает пять объектов, только потом удаляется `Сервис` — иначе удаление оставит объекты без подсистемы и следующий шаг придётся откатывать. Каждый шаг проверяется `subsystem-info` и `cf-validate`, а не глазами.

**Tech Stack:** 1С:Предприятие 8.3.27, управляемое приложение, XML-выгрузка `src/КурсоваяРабота`, файловая ИБ `db/КурсоваяРабота`, скиллы `db-dump-dt`, `subsystem-info`, `subsystem-edit`, `meta-remove`, `cf-validate`, `meta-validate`.

**Spec:**
- `openspec/changes/rework-admin-navigation/proposal.md`
- `openspec/changes/rework-admin-navigation/design.md` — решения 1–4, 6
- `openspec/changes/rework-admin-navigation/specs/navigation-and-commands/spec.md` — требование «Технические объекты не образуют отдельного раздела»
- `openspec/changes/rework-admin-navigation/tasks.md` — задачи 1.1–2.4

## Global Constraints

- Платформа 8.3.27, режим совместимости `Version8_3_27`, управляемое приложение, вариант скрипта — русский.
- ИБ файловая, `db/КурсоваяРабота`.
- Метаданные правятся только скиллами проекта; ручное редактирование XML запрещено.
- XML выгрузки — UTF-8 с BOM; двойной BOM ломает загрузку.
- UUID существующих объектов (`Subsystem.АдминистраторИС`, `Role.Администратор`) не меняются.
- Подсистема `НастройкиИнтеграций` и её состав не изменяются ни на одном шаге.
- Команды Конфигуратора запускаются с `-UserName "Администратор"`.
- Имена объектов и файлов — русские, как в существующей выгрузке.

## Review Focus

- **Повторное добавление объекта в `<Content>`.** Если объект уже там, `subsystem-edit` может создать дубль, и `cf-validate` пропустит его молча — ожидается ровно пять записей, каждая по одному разу.
- **Удаление подсистемы вместе с объектами.** `meta-remove` на `Subsystem.Сервис` не должен каскадно удалить константу, планы характеристик, задачу и регистр — ожидается, что после удаления все 22 объекта остаются в `Configuration.xml`.
- **Расхождение файла и каталога.** Удаление только `Subsystems/Сервис.xml` без каталога (или наоборот) оставляет мусор в выгрузке, который ломает следующую загрузку — ожидается отсутствие обоих.
- **Порядок `<ChildObjects>` в `Configuration.xml`.** Удаление записи не должно сдвигать остальные — ожидается `cf-validate` без ошибок.
- **`НастройкиИнтеграций` под горячую руку.** Массовая правка подсистем легко задевает соседний файл — ожидается пустой `git diff` по нему.

---

<!-- openspec-task: 1.1 -->
### Task 1: Сделать бэкап информационной базы

**Files:**
- Create: `db/backup/КурсоваяРабота-2026-10-21.dt`

**Interfaces:**
- Consumes: работающую ИБ `db/КурсоваяРабота`
- Produces: файл отката для плана 3

- [ ] **Step 1: Убедиться, что база свободна**

Run:
```powershell
Get-Process -Name 1cv8,1cv8c -ErrorAction SilentlyContinue
```
Expected: пусто. Если процессы есть — закрыть клиентские сеансы, иначе выгрузка упадёт.

- [ ] **Step 2: Выгрузить ИБ**

Использовать скилл `db-dump-dt` для базы `КурсоваяРабота`, файл назначения `db/backup/КурсоваяРабота-2026-10-21.dt`.

- [ ] **Step 3: Проверить артефакт**

Run:
```powershell
Get-Item db/backup/КурсоваяРабота-2026-10-21.dt | Select-Object Length
```
Expected: `Length` больше нуля.

---

<!-- openspec-task: 1.2 -->
### Task 2: Зафиксировать текущий состав подсистем

**Files:**
- Create: `C:\Users\vladi\AppData\Local\Temp\opencode\subsystems-before.txt` (вне репозитория)

**Interfaces:**
- Consumes: ничего
- Produces: эталонный список объектов `Сервис` (22) и `АдминистраторИС`, с которым сверяются задачи 4–6

- [ ] **Step 1: Снять состав `Сервис`**

Использовать скилл `subsystem-info` для `src/КурсоваяРабота/Subsystems/Сервис` и сохранить вывод в `subsystems-before.txt`.

- [ ] **Step 2: Снять состав `АдминистраторИС`**

Тем же скиллом для `src/КурсоваяРабота/Subsystems/АдминистраторИС`, дописать в тот же файл.

- [ ] **Step 3: Проверить, что эталон полон**

Run:
```powershell
Select-String -Path "C:\Users\vladi\AppData\Local\Temp\opencode\subsystems-before.txt" -Pattern "Состав:"
```
Expected: строка «Состав: 22 объектов (Constant: 1, ChartOfCharacteristicTypes: 2, Task: 1, InformationRegister: 1, Enum: 17)». Пустой `Content` у `АдминистраторИС` и две дочерние подсистемы: `НастройкиИнтеграций`, `СправочникиНСИ`.

---

<!-- openspec-task: 1.3 -->
### Task 3: Зафиксировать неприкосновенность «Настроек интеграций»

**Files:**
- Read: `src/КурсоваяРабота/Subsystems/АдминистраторИС/Subsystems/НастройкиИнтеграций.xml`

**Interfaces:**
- Consumes: ничего
- Produces: контрольную сумму файла для задачи 7

- [ ] **Step 1: Проверить состав**

Run:
```powershell
Select-String -Path "src/КурсоваяРабота/Subsystems/АдминистраторИС/Subsystems/НастройкиИнтеграций.xml" -Pattern "InformationRegister\."
```
Expected: ровно одна строка — `InformationRegister.НастройкиИнтеграций`.

- [ ] **Step 2: Запомнить хеш файла**

Run:
```powershell
Get-FileHash "src/КурсоваяРабота/Subsystems/АдминистраторИС/Subsystems/НастройкиИнтеграций.xml" -Algorithm SHA256
```
Expected: хеш записан в отчёт задачи; в задаче 7 он должен совпасть.

---

<!-- openspec-task: 2.1 -->
### Task 4: Перенести пять объектов в «Администратор ИС»

**Files:**
- Modify: `src/КурсоваяРабота/Subsystems/АдминистраторИС.xml` — блок `<Content>`
- Read: `src/КурсоваяРабота/Subsystems/Сервис.xml` — источник списка

**Interfaces:**
- Consumes: список объектов из задачи 2
- Produces: `АдминистраторИС` с пятью объектами в составе; на него опираются задачи 5, 8 и 9

- [ ] **Step 1: Зафиксировать исходное состояние**

Run:
```powershell
Select-String -Path "src/КурсоваяРабота/Subsystems/АдминистраторИС.xml" -Pattern "<Content/>|<Content>"
```
Expected: пустой `<Content/>` — ни одного объекта.

- [ ] **Step 2: Добавить пять объектов**

Использовать скилл `subsystem-edit` для `Subsystems/АдминистраторИС.xml`, добавив в состав ровно:

- `Constant.ПорогСогласованияРуководителем`
- `ChartOfCharacteristicTypes.ДополнительныеРеквизитыТуриста`
- `ChartOfCharacteristicTypes.ДополнительныеРеквизитыУслуг`
- `Task.ЗадачаИсполнителя`
- `InformationRegister.АдресацияЗадач`

- [ ] **Step 3: Проверить состав**

Использовать скилл `subsystem-info` для `Subsystems/АдминистраторИС`.
Expected: ровно 5 объектов, каждый по одному разу; дочерние подсистемы `НастройкиИнтеграций` и `СправочникиНСИ` на месте.

- [ ] **Step 4: Провалидировать**

Использовать скилл `meta-validate` для `Subsystems/АдминистраторИС.xml`.
Expected: 0 ошибок.

- [ ] **Step 5: Коммит**

```bash
git add "src/КурсоваяРабота/Subsystems/АдминистраторИС.xml"
git commit -m "feat(subsystems): move service objects into admin section"
```

---

<!-- openspec-task: 2.2 -->
### Task 5: Удалить подсистему «Сервис»

**Files:**
- Delete: `src/КурсоваяРабота/Subsystems/Сервис.xml`
- Delete: `src/КурсоваяРабота/Subsystems/Сервис/`
- Modify: `src/КурсоваяРабота/Configuration.xml` — блок `<ChildObjects>`

**Interfaces:**
- Consumes: результат задачи 4 — объекты уже принадлежат `АдминистраторИС`
- Produces: конфигурацию без подсистемы `Сервис`

- [ ] **Step 1: Проверить, что объекты уже в другом месте**

Использовать скилл `subsystem-info` для `Subsystems/АдминистраторИС`.
Expected: 5 объектов на месте (из задачи 4). Если нет — остановиться и вернуться к задаче 4.

- [ ] **Step 2: Удалить подсистему**

Использовать скилл `meta-remove` для `Subsystem.Сервис`.
Expected: из `Configuration.xml` исчезла строка `<Subsystem>Сервис</Subsystem>`, файл и каталог подсистемы удалены.

- [ ] **Step 3: Проверить, что каталог не остался**

Run:
```powershell
Test-Path "src/КурсоваяРабота/Subsystems/Сервис.xml"; Test-Path "src/КурсоваяРабота/Subsystems/Сервис"
```
Expected: `False` и `False`.

- [ ] **Step 4: Проверить, что объекты не удалились каскадом**

Run:
```powershell
(Select-String -Path "src/КурсоваяРабота/Configuration.xml" -Pattern "<Enum>").Count
```
Expected: 17. Если меньше — `meta-remove` утянул перечисления: восстановить выгрузку командой `git checkout -- "src/КурсоваяРабота"`, остановиться и выбрать другой способ удаления подсистемы (сначала убрать её объекты из состава через `subsystem-edit`, затем повторить `meta-remove`). Молча продолжать нельзя: 17 перечислений — часть конфигурации.

- [ ] **Step 5: Провалидировать конфигурацию**

Использовать скилл `cf-validate`.
Expected: 0 ошибок.

- [ ] **Step 6: Коммит**

```bash
git add "src/КурсоваяРабота/Configuration.xml" "src/КурсоваяРабота/Subsystems"
git commit -m "feat(subsystems): remove service section"
```

---

<!-- openspec-task: 2.3 -->
### Task 6: Проверить, что перечисления остались в конфигурации

**Files:**
- Read: `src/КурсоваяРабота/Configuration.xml`
- Read: `src/КурсоваяРабота/Subsystems/*.xml`

**Interfaces:**
- Consumes: результат задачи 5
- Produces: подтверждение, что 17 перечислений на месте и не входят ни в одну подсистему

- [ ] **Step 1: Сосчитать перечисления**

Run:
```powershell
(Select-String -Path "src/КурсоваяРабота/Configuration.xml" -Pattern "<Enum>").Count
```
Expected: 17.

- [ ] **Step 2: Проверить, что перечисления не попали в другие подсистемы**

Run:
```powershell
Select-String -Path "src/КурсоваяРабота/Subsystems/*.xml" -Pattern "Enum\."
```
Expected: ни одного совпадения.

- [ ] **Step 3: Проверить, что состав `АдминистраторИС` не разросся**

Использовать скилл `subsystem-info` для `Subsystems/АдминистраторИС`.
Expected: те же 5 объектов, перечислений среди них нет.

- [ ] **Step 4: Записать результат**

Коммит не требуется, файлы не менялись. Числа из шагов 1–3 привести в отчёте задачи.

---

<!-- openspec-task: 2.4 -->
### Task 7: Убедиться, что «Настройки интеграций» не тронуты

**Files:**
- Read: `src/КурсоваяРабота/Subsystems/АдминистраторИС/Subsystems/НастройкиИнтеграций.xml`

**Interfaces:**
- Consumes: хеш из задачи 3
- Produces: подтверждение неприкосновенности подсистемы

- [ ] **Step 1: Проверить diff**

Run:
```powershell
git diff --stat -- "src/КурсоваяРабота/Subsystems/АдминистраторИС/Subsystems/НастройкиИнтеграций.xml"
```
Expected: пустой вывод — файл не менялся.

- [ ] **Step 2: Проверить хеш**

Run:
```powershell
Get-FileHash "src/КурсоваяРабота/Subsystems/АдминистраторИС/Subsystems/НастройкиИнтеграций.xml" -Algorithm SHA256
```
Expected: совпадает с хешем из задачи 3.

- [ ] **Step 3: Проверить состав**

Run:
```powershell
(Select-String -Path "src/КурсоваяРабота/Subsystems/АдминистраторИС/Subsystems/НастройкиИнтеграций.xml" -Pattern "InformationRegister\.").Count
```
Expected: 1.

---

## Проверка плана

- [ ] `cf-validate` — 0 ошибок
- [ ] `Test-Path` для `Subsystems/Сервис.xml` и `Subsystems/Сервис` — оба `False`
- [ ] `<Enum>` в `Configuration.xml` — ровно 17
- [ ] `subsystem-info` по `АдминистраторИС` — 5 объектов и 2 дочерние подсистемы
- [ ] `git diff` по `НастройкиИнтеграций.xml` пуст
- [ ] `git log --oneline -2` показывает два коммита плана
