# Add Access Roles (Part 2: IB Load, Scenario Verification, Docs) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Load the 6 generated profile roles into the file infobase, verify the spec scenarios with real users, and close the documentation of stage 3.

**Architecture:** Load pipeline via project skills: `db-dump-dt` backup → `db-load-xml` → `db-update`; 1C crash dumps (`Ошибка_*.zip`) are the primary failure signal (AGENTS.md rule 7 — inspect before any retry). Verification is behavioral: 7 test users (6 profiles + Administrator) run through the spec scenarios in enterprise client (`db-run`) or web client (`web-test`). Fixes go back to `roles-matrix.json` → regenerate (Part 1 Tasks 4–6) → reload; never edit `Rights.xml` by hand.

**Tech Stack:** 1C:Enterprise 8.3 file infobase, project skills `.opencode/skills/db-*`, `web-test` (Playwright), PowerShell, Python for dump inspection.

**Spec:** `openspec/changes/add-access-roles/specs/access-roles/spec.md` — every scenario listed below cites this file; `design.md` D5/D6. Prerequisite: Part 1 (`docs/superpowers/plans/2026-10-23-add-access-roles-tasks-1.1-2.4.md`) committed and Tasks 1–7 complete.

## Global Constraints

- Before EVERY 1C command: kill leftover processes (`Get-Process 1cv8* -ErrorAction SilentlyContinue | Stop-Process` pattern from `db-*` skills) and check for a fresh `Ошибка_*.zip` in the project root; a dump newer than the last run is conclusive evidence — read `report.json` → `errorInfo.applicationErrorInfo.errors` before retrying anything.
- `db-repo` (store) is not used; `Администратор` role and `DefaultRoles` remain untouched (Part 1 Task 7 invariant must still hold — re-check before step 3.2).
- Test users are infobase DATA: created in the running ИБ, not committed to git.
- Scenario failures are matrix defects: fix `roles-matrix.json`, regenerate, reload — do not patch `Rights.xml`.
- Commits clean, conventional, no profanity.

## Review Focus

1. Silent load failure: `db-update` exits «успешно» but a crash dump exists → roles half-applied (pinned in Task 9).
2. Wrong profile section visible (subsystem View leak, e.g. Оператор sees `КоординаторЛогистики`) (pinned in Task 12).
3. Гид gains `Пров`/posting or deletion rights beyond the closure `Edit`+`Update` (matrix leak) (pinned in Task 12); Аудитор gains any `Edit`/`Insert` (it has none — rights honestly block editing) (pinned in Task 12).
4. Оператор's posting of `ПодтверждениеУслуги` fails due to missing Update/Пров (pinned in Task 12).
5. Regression: `Администратор` loses a previously working command because a profile changed shared metadata expectations (pinned in Task 13).

---

<!-- openspec-task: 3.1 -->
### Task 8: Infobase backup

**Files:**
- Create: `<project root or backups dir per db-dump-dt skill>/*.dt`

**Interfaces:**
- Produces: fresh `.dt` dump file path (rollback point for Tasks 9–12).

- [x] **Step 1: Run skill `db-dump-dt`** per its SKILL.md. Expected: dump completes without error.
- [x] **Step 2: Verify freshness** — `Get-ChildItem *.dt | Sort-Object LastWriteTime | Select-Object -Last 1`; expected: `LastWriteTime` within the last 15 minutes, non-zero size. Record the path as the rollback point.
- [x] **Step 3: Commit nothing** (data file stays out of git); if `.dt` lands inside the repo and `git status` shows it, add the file name to `.gitignore` locally ONLY if the repo already ignores dumps; otherwise move the dump to the skill's default backup location.

<!-- openspec-task: 3.2 -->
### Task 9: Load XML + update DB

**Files:**
- Read: `src/КурсоваяРабота/**` (Part 1 output), `Ошибка_*.zip` (failure signal)

**Interfaces:**
- Consumes: validated roles (Part 1). Produces: live ИБ with 7 roles.

- [x] **Step 1: Preflight** — no `1cv8*` processes running; no `Ошибка_*.zip` newer than Part 1's last 1C action; re-run Part 1 Task 7 checks (git diff `Администратор` empty, `<DefaultRoles/>` present).
- [x] **Step 2: Run skill `db-load-xml`** then skill `db-update` per their SKILL.md. Expected: both complete without syntax errors.
- [x] **Step 3: Dump check** — `Get-ChildItem Ошибка_*.zip` newest timestamp newer than step 2 start? Expected: NO. If YES: unzip, read `report.json` → `errorInfo.applicationErrorInfo.errors`, fix the root cause in matrix → regenerate (Part 1 Task 4) → retry from step 1. Do not blind-retry.
- [x] **Step 4: Verify in ИБ** (Configurator tree via `db-run` in designer mode or the load output): 7 roles present. Expected: list matches `Профиль_*`×6 + `Администратор`.

<!-- openspec-task: 3.3 -->
### Task 10: Spot-check rights inside the loaded ИБ

**Files:**
- Read-only.

**Interfaces:**
- Consumes: Task 9 live ИБ; `/role-info` skill. Produces: confidence to proceed to user scenarios.

- [x] **Step 1: `/role-info` on the loaded `Профиль_Гид`** (from `src/КурсоваяРабота/Roles/Профиль_Гид/Ext/Rights.xml`, same file the ИБ now uses). Expected rows: `Document.Инцидент` = чтение/просмотр/интерактивное добавление/ввод по строке and NO редактирование/проведение; `Document.ПретензияПоставщику` — absent entirely; `Subsystem.ГидНаМаршруте` — visible; `DataProcessor.ПересчётТайминговМаршрутов` — absent.
- [x] **Step 2: `/role-info` on `Профиль_Оператор`**: `Document.ПодтверждениеУслуги` includes проведение (Пров/Update). Expected: PASS. Any mismatch → matrix defect: fix in `roles-matrix.json`, regenerate (Part 1 Task 4), reload (Task 9), re-check.

<!-- openspec-task: 4.1 -->
### Task 11: Test users

**Files:**
- Read-only (ИБ data).

**Interfaces:**
- Consumes: Task 10. Produces: 6 users `test_operator`, `test_koordinator`, `test_gid`, `test_menuver`, `test_rukovoditel`, `test_auditor` with their single profile role + the EXISTING `Администратор` user reused for admin runs (user decision 25.10 — no test_admin); `test_operator`/`test_gid` bound to existing demo `Сотрудники`.

- [x] **Step 1: Users exist** — created by the user via Configurator («Пользователи информационной базы») per `docs/Инструкция-пользователи-ИБ.md`: 6 `test_*` with one profile role each; admin runs reuse the existing `Администратор`. Controller verifies, does not create. `DefaultRoles` stays empty.
- [x] **Step 2: Bind «свой» subjects** — via code (external run under `Администратор`, data layer): fill/extend `Catalogs.Пользователи` records with `ИмяПользователяИБ` = `test_operator`/`test_gid` linked to demo `Сотрудники` (forms logic resolves «свой» through this binding).
- [x] **Step 3: Verify** — the 6 test users are listed in ИБ, each shows exactly one role; launch each via `/U test_*` and confirm session starts. Expected: PASS. No git commit (data, not sources).

<!-- openspec-task: 4.2 -->
### Task 12: Spec scenario battery

**Files:**
- Read: scenario table below (from spec `access-roles`).

**Interfaces:**
- Consumes: Task 11 users; `roles-matrix.json` (fix target). Produces: recorded PASS per scenario; committed matrix fixes if any failed.

- [x] **Step 1: Run the scenario battery** and record PASS/FAIL per line:
  1. `test_koordinator`: командный интерфейс shows `КоординаторЛогистики`, does NOT show `ОператорСопровождения` (spec «Рабочее место…»).
  2. `test_gid`: creates `Инцидент`, saves (closure `Edit`+`Update` makes save possible; no independent `Изм`, no `Пров` — posting command unavailable); `ДоговорыСПоставщиками` not openable (spec «Гид создаёт, редактирование идёт платформенным замыканием», «Нет прав — нет доступа»).
  3. `test_operator`: posts `ПодтверждениеУслуги` successfully (spec «Оператор проводит…»).
  4. `test_operator`: `ПретензияПоставщику` and `InformationRegister.НастройкиИнтеграций` inaccessible (spec matrices + «Настройки интеграций закрыты…»).
  5. `test_auditor`: reads `Catalog.СтраныМира`, cannot add/change; reads `ШтрафыИКомпенсации`; `ПересчётТайминговМаршрутов` unavailable for `test_gid` but available for `test_koordinator` (spec off-matrix scenarios).
  6. `test_operator` on the KPI summary (`СводкаСтатусов`/KPI form of subsystem `ОператорСопровождения`): list filtered to the bound `Сотрудник` («Чтение (своих)» requirement).
  7. `test_menuver` reads `ВзаиморасчётыПоПретензиям`; `test_operator` — access denied (spec «Менеджер видит взаиморасчёты…»).
- [x] **Step 2: On any FAIL** — diagnose as matrix defect, fix `roles-matrix.json` + role JSONs, regenerate (Part 1 Task 4), validate (Task 6), reload (Task 9), re-run the failed scenario only, then full battery once. Expected: battery all-PASS.
- [x] **Step 3: Commit** fixes if produced: `git commit -am "fix(roles): matrix corrections from scenario verification"`.

<!-- openspec-task: 4.3 -->
### Task 13: Regression of neighboring specs

**Files:**
- Read-only.

**Interfaces:**
- Consumes: Task 12 PASS battery. Produces: evidence that `navigation-and-commands`, `data-processors`, `data-exchange` behavior and admin workflows are intact.

- [x] **Step 1: Rights-hidden commands** (`navigation-and-commands` spec): as `test_auditor`, verify commands absent for objects it cannot edit; as `test_operator`, verify its allowed commands work. Expected: matches existing `ПравоДоступа`-driven form logic.
- [x] **Step 2: Processors** (`data-processors` spec): `test_koordinator` runs `ПересчётТайминговМаршрутов`; `test_rukovoditel` opens `ПросроченныеСрокиИSLA`; `test_auditor` opens `СводкаСтатусов`. Expected: all succeed; `test_gid` cannot open any of the five.
- [x] **Step 3: CSV exchange** (`data-exchange` spec): existing `Администратор` runs `ОбменСФайлами` import/export as before; `test_operator` does not see the command. Expected: admin workflow unchanged from archived `add-csv-data-exchange` behavior.
- [x] **Step 4: Admin full-path smoke**: existing `Администратор` user repeats one full posting chain from `document-posting` spec scenarios and demo data browsing. Expected: no new errors, no fresh `Ошибка_*.zip`.

<!-- openspec-task: 5.1 -->
### Task 14: Close stage-3 docs

**Files:**
- Modify: `docs/Оставшиеся-задачи.md` (stage 3 «роли и профили» section, lines ~63–65 and ~11)

**Interfaces:**
- Consumes: all previous tasks. Produces: documentation matching delivered state.

- [ ] **Step 1: Update `docs/Оставшиеся-задачи.md`**: mark этап 3 «роли и профили» done with capability pointer `access-roles` (openspec spec) and plan file names; append the 7 accepted ТЗ deviations from `proposal.md` («Расхождения с Дополнением к ТЗ») as a short list; remove the stale planned-roles list (`Профиль_Администратор` note: not created, `Администратор` used).
- [ ] **Step 2: Verify** — `Select-String docs\Оставшиеся-задачи.md -Pattern 'роли'` shows no open stage-3 checkbox/item about roles.
- [ ] **Step 3: Commit** — `git add docs/Оставшиеся-задачи.md && git commit -m "docs: close stage 3 roles after access-roles delivery"`.
