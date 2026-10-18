# Наполнение демо-данными — план 4: интеграция и документация (5.1–5.3)

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Прогнать полный цикл на восстановленной базе, получить `PASS` от проверки, зафиксировать результат в документации и убедиться, что формы не пострадали.

**Architecture:** Никакого нового кода — только прогон готовых инструментов в правильном порядке и фиксация результата. Восстановление базы из копии задачи 1.1 доказывает, что цикл воспроизводим с нуля, а не только «докатился» на текущем состоянии.

**Tech Stack:** PowerShell, `epf/run-fill.ps1`, `epf/run-check.ps1`, `tests/vanessa/run-xdd-smoke.ps1`, 1С:Предприятие 8.3.27.1786.

**Spec:** `openspec/changes/seed-test-data/tasks.md`, `specs/demo-dataset/spec.md`, `specs/dataset-verification/spec.md`

## Global Constraints

- Перед любым запуском 1С закрыть процессы `1cv8`, `1cv8c`, `1cv8s`.
- Восстановление базы — только при закрытых сеансах, иначе файл заблокирован.
- `*.log` в `.gitignore`: итог проверки сохраняется как `.md`, иначе не попадёт в коммит.
- Успех = `ВЕРДИКТ: PASS` и код возврата 0 от `run-check.ps1`.

## Review Focus

- **Откат к копии.** Пользователь восстанавливает базу и ждёт, что наполнение соберётся заново — задача 4.1.
- **Пустая база после отката.** Конфигурация в копии старше исходников, поэтому загрузка XML обязательна до наполнения — задача 4.1.
- **Лог проверки в репозитории.** `.log` игнорируется git, поэтому результат пишется в `.md` — задача 4.1 и 4.2.
- **Сломанные формы.** Загрузка конфигурации могла что-то задеть — задача 4.3.

---

<!-- openspec-task: 5.1 -->
### Task 1: Полный цикл на восстановленной базе

**Files:**
- Modify: `db/КурсоваяРабота/1Cv8.1CD` (восстановление из копии)
- Create: `docs/Проверка-данных-2026-10-18.md`

**Interfaces:**
- Consumes: копию `db/backup/1Cv8-2026-10-18.1CD`, `epf/run-fill.ps1`, `epf/run-check.ps1`
- Produces: подтверждённый `PASS` и файл-отчёт в `docs/`

- [ ] **Step 1: Закрыть сеансы**

Run: `Get-Process 1cv8,1cv8c,1cv8s -ErrorAction SilentlyContinue`
Expected: пусто.

- [ ] **Step 2: Восстановить базу из копии**

Run:
```powershell
Copy-Item "db\backup\1Cv8-2026-10-18.1CD" "db\КурсоваяРабота\1Cv8.1CD" -Force
```
Expected: копия восстановлена, размер совпадает с копией.

- [ ] **Step 3: Загрузить актуальную конфигурацию**

Run: скиллы `db-load-xml` и `db-update` для `src\КурсоваяРабота`
Expected: конфигурация в базе соответствует исходникам (включая `SLAЧасов` Число(4,2)).

- [ ] **Step 4: Прогнать наполнение**

Run: `powershell -ExecutionPolicy Bypass -File epf/run-fill.ps1`
Expected: код 0, `Блоков выполнено: 17 из 17, ошибок: 0`, двадцать документов.

- [ ] **Step 5: Прогнать проверку**

Run: `powershell -ExecutionPolicy Bypass -File epf/run-check.ps1; "EXIT=$LASTEXITCODE"`
Expected: `ВЕРДИКТ: PASS`, `EXIT=0`.

- [ ] **Step 6: Сохранить отчёт**

Создать `docs/Проверка-данных-2026-10-18.md`: дата, версия конфигурации (коммит), таблица фактических количеств из лога, строка вердикта, размер базы.

- [ ] **Step 7: Закоммитить отчёт**

```bash
git add docs/Проверка-данных-2026-10-18.md
git commit -m "docs: record verified demo dataset snapshot"
```

---

<!-- openspec-task: 5.2 -->
### Task 2: Обновить статус проекта

**Files:**
- Modify: `docs/Оставшиеся-задачи.md`

**Interfaces:**
- Consumes: отчёт из задачи 1
- Produces: снятый пункт «наполнение не подтверждено» и фактические числа

- [ ] **Step 1: Зафиксировать падающую проверку**

Run: `Select-String -Path "docs\Оставшиеся-задачи.md" -Pattern "не подтверждено" -Encoding UTF8`
Expected: строка найдена — документация устарела.

- [ ] **Step 2: Заменить пункт про наполнение**

В разделе «Состояние проекта» заменить абзац про `ЗаполнениеНСИ` на подтверждённый: дата прогона, фактические количества справочников и документов, ссылка на `docs/Проверка-данных-2026-10-18.md`.

- [ ] **Step 3: Убрать пункт из хвостов**

В разделе «Текущие хвосты» удалить строку «Проверить/при необходимости повторить наполнение базы обработкой `ЗаполнениеНСИ`».

- [ ] **Step 4: Проверить, что старого текста не осталось**

Run: `Select-String -Path "docs\Оставшиеся-задачи.md" -Pattern "не подтверждено" -Encoding UTF8`
Expected: пусто.

- [ ] **Step 5: Закоммитить**

```bash
git add docs/Оставшиеся-задачи.md
git commit -m "docs: mark demo data seeding as verified"
```

---

<!-- openspec-task: 5.3 -->
### Task 3: Дымовой набор форм

**Files:**
- Modify: ничего (только прогон)

**Interfaces:**
- Consumes: загруженную в задаче 1 конфигурацию
- Produces: подтверждение, что 82 формы открываются после изменения метаданных

- [ ] **Step 1: Закрыть сеансы**

Run: `Get-Process 1cv8,1cv8c,1cv8s -ErrorAction SilentlyContinue`
Expected: пусто.

- [ ] **Step 2: Прогнать смоук**

Run: `powershell -ExecutionPolicy Bypass -File tests/vanessa/run-xdd-smoke.ps1`
Expected: `82/82 passed`.

- [ ] **Step 3: Разобрать падения, если есть**

Если тест красный — открыть `build/vanessa/results/*-result.xml`, найти упавшую форму, сверить с `docs/superpowers/specs/2026-10-05-формы-справочников-и-документов-design.md`. Правка форм — **вне** этого изменения: зафиксировать дефект отдельной задачей и не чинить здесь.

- [ ] **Step 4: Зафиксировать результат**

Дописать в `docs/Проверка-данных-2026-10-18.md` строку `Смоук форм: 82/82 passed` (или фактический результат) и закоммитить:

```bash
git add docs/Проверка-данных-2026-10-18.md
git commit -m "docs: record smoke test result for seeded base"
```
