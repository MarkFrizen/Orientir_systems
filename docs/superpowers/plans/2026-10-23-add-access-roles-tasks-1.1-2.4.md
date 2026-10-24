# Add Access Roles (Part 1: Matrix & Role Metadata) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Create the 14-task rights matrix (`roles-matrix.json`) and generate 6 `Профиль_*` roles into the configuration metadata sources without touching the existing `Администратор` role.

**Architecture:** Single source of truth — `roles-matrix.json` in the change directory (design D3). Roles are generated exclusively through the `role-compile` toolchain (`python .opencode/skills/role-compile/scripts/role-compile.py -JsonPath <json> -OutputDir src/КурсоваяРабота`), which writes `Roles/Имя.xml` + `Roles/Имя/Ext/Rights.xml` and registers `<Role>` in `Configuration.xml`. Manual GUID edits are forbidden; fixes are made in JSON and regenerated.

**Tech Stack:** 1C:Enterprise 8.3 XML configuration sources (`src/КурсоваяРабота/`), project skill tooling (`.opencode/skills/role-compile`, `role-validate`, `role-info`, `cf-edit`, `cf-validate`, `meta-info`), Python for validation scripts, PowerShell on Windows.

**Spec:** `openspec/changes/add-access-roles/specs/access-roles/spec.md` (all rights tables), `openspec/changes/add-access-roles/design.md` (D2 conversion, D3 generation), `openspec/changes/add-access-roles/proposal.md` (ТЗ deviations). Read all three before starting.

## Global Constraints

- Working directory: `D:\Projects\1C_prj\7 семестр\Kursovaya`; config root: `src\КурсоваяРабота`.
- Role names verbatim: `Профиль_Оператор`, `Профиль_Координатор`, `Профиль_Гид`, `Профиль_МенеджерПретензий`, `Профиль_Руководитель`, `Профиль_Аудитор`.
- `Roles/Администратор.xml`, `Roles/Администратор/Ext/Rights.xml`, `DefaultRoles` section of `Configuration.xml`, and UUID `527785c9-76dd-4423-a179-dd3d73bb9a2a` are immutable in this plan.
- In every generated profile JSON/`Rights.xml`: `setForNewObjects` must stay `false` (default) — a profile with `true` becomes an admin clone.
- DSL identifiers in role JSONs MUST be taken from `.opencode/skills/role-compile/dsl-reference.md` (it is the source of truth for permission names, preset expansion, and which metadata types can carry rights). Semantic intent per design D2: Ч→чтение, П→просмотр, И→интерактивное добавление, Изм→интерактивное изменение, В→ввод по строке, Пров→обновление (проведение), Use→запуск обработки, подсистема→видимость.
- Enums carry no rights in the DSL (per `role-compile/SKILL.md` «Что можно писать в objects»): spec item about `Перечисления` is satisfied by giving nothing — no JSON entry, covered in Task 3 notes.
- Commits: conventional style, no profanity in commit messages (repo rule).
- Part 2 of this plan set (`docs/superpowers/plans/2026-10-23-add-access-roles-tasks-3.1-5.1.md`) starts from these committed artifacts; do not load to IB here.

## Review Focus

1. Profile accidentally generated with `setForNewObjects=true` → silent full rights (pinned in Task 7).
2. `Администратор` role files/UUID touched by tooling (pinned in Task 7).
3. `role-compile` failed to register roles in `Configuration.xml` composition (pinned in Task 5).
4. `Пров` (Update) leaked to documents where the profile has no `Изм` — breaks the posting rule of the spec (pinned in Task 2).
5. Name drift between spec tables and metadata (e.g. `ТурыМаршруты` vs `ТурыМаршрут`) → compile rejects or wrong GUIDs (pinned in Task 1).

---

<!-- openspec-task: 1.1 -->
### Task 1: roles-matrix.json — core ТЗ tables

**Files:**
- Create: `openspec/changes/add-access-roles/roles-matrix.json`
- Create: `openspec/changes/add-access-roles/check-matrix.py`

**Interfaces:**
- Produces: `roles-matrix.json` schema: `{ "profiles": { "<РольИмя>": { "synonym": "<отображаемое имя>", "objects": { "<ТипОбъекта>.<Имя>": ["Ч","П","И","Изм","В","Пров"], ... } } } }`. Symbols are the ТЗ legend; conversion to DSL happens in Task 4. Object keys use metadata type prefixes: `Catalog.`, `Document.`, `InformationRegister.`, `AccumulationRegister.`, `DataProcessor.`, `Constant.`, `ChartOfCharacteristicTypes.`, `BusinessProcess.`, `Task.`, `Subsystem.`.

- [x] **Step 1: Write the failing checker** `check-matrix.py` — for profiles' object keys: (a) every key `<Тип>.<Имя>` has a corresponding source `src/КурсоваяРабота/<Тип plural>/<Имя>.xml` (mapping `Catalog`→`Catalogs`, `Document`→`Documents`, `InformationRegister`→`InformationRegisters`, `AccumulationRegister`→`AccumulationRegisters`, `DataProcessor`→`DataProcessors`, `Constant`→`Constants`, `ChartOfCharacteristicTypes`→`ChartsOfCharacteristicTypes`, `BusinessProcess`→`BusinessProcesses`, `Task`→`Tasks`, `Subsystem`→`Subsystems`); (b) the 10 справочники, 9 документов, 6 регистров from the spec tables appear in ALL 6 profiles (with any non-empty rights list, including lists containing only «-» rows → key ABSENT for «-»); exit 1 on any violation.
- [x] **Step 2: Run it, verify it FAILS** — `python openspec/changes/add-access-roles/check-matrix.py`; expected: error `roles-matrix.json not found`.
- [x] **Step 3: Write `roles-matrix.json`** copying the three spec tables verbatim for all 6 profiles: «Права на справочники» (rows=objects, columns=profiles, symbol strings like `ЧПИИзмВ` → split into the symbol list; cells transcribed exactly as written — every non-«-» cell in the ТЗ already starts with `Ч`), «Права на документы», «Права на регистры» (Ч only; «-» → omit key). Synonyms: `Профиль_Оператор`→«Оператор сопровождения», `Профиль_Координатор`→«Координатор логистики», `Профиль_Гид`→«Гид на маршруте», `Профиль_МенеджерПретензий`→«Менеджер по претензиям», `Профиль_Руководитель`→«Руководитель направления», `Профиль_Аудитор`→«Аудитор (только чтение)».
- [x] **Step 4: Extend `check-matrix.py` with the «-» rule**: for every table cell «-» the key must be absent from that profile; run checker; expected PASS (all 25 spec objects resolve to real metadata files — if not, STOP and report the mismatching names, per task 1.1).
- [x] **Step 5: Commit** — `git add openspec/changes/add-access-roles/roles-matrix.json openspec/changes/add-access-roles/check-matrix.py && git commit -m "feat(roles): add access rights matrix core tables"`.

<!-- openspec-task: 1.2 -->
### Task 2: Posting documents → Пров symbols

**Files:**
- Modify: `openspec/changes/add-access-roles/roles-matrix.json`
- Modify: `openspec/changes/add-access-roles/check-matrix.py`

**Interfaces:**
- Consumes: Task 1 matrix. Produces: every document with posting enabled that a profile can interactively edit (`Изм`) gains `Пров` in that profile's rights list; the final matrix with posting rule satisfied.

- [x] **Step 1: Enumerate posting-enabled documents.** Run: `Select-String -Path src\КурсоваяРабота\Documents\*.xml -Pattern '<Проведён>.*true'` (if the tag name differs in this export format, use the `meta-info` skill on one document to find the exact property, then re-grep). Expected: a subset of the 9 documents (e.g. `ЗаказПоставщику`, `ПодтверждениеУслуги`, `МаршрутныйЛист`, `СобытиеМаршрута`, `КорректировкаМаршрута`, `ЗаявкаТуристаНаМаршруте`, `Инцидент`, `ПретензияПоставщику`, `АктОКомпенсации` — keep only those actually flagged). Record the list in the chat before proceeding; it is the input for step 3.
- [x] **Step 2: Add the failing posting invariants to `check-matrix.py`**: (a) `Пров` appears ONLY on `Document.*` keys whose name is in the posting list passed via CLI `--post <csv>` and only if `Изм` is present for the same profile+document; (b) profile `Профиль_Гид` contains no `Пров` anywhere. Run checker, expected FAIL (no `Пров` yet on cells that need it).
- [x] **Step 3: Apply the rule** to `roles-matrix.json`: add `Пров` to every profile×document cell that has `Изм` and whose document is in the posting list. Expected additions per design D5: Оператор — `ЗаказПоставщику`, `ПодтверждениеУслуги`, `ЗаявкаТуристаНаМаршруте` (+ any other posting doc with `Изм`); Координатор — `МаршрутныйЛист`, `СобытиеМаршрута`, `КорректировкаМаршрута`; Менеджер — `Инцидент`, `ПретензияПоставщику`, `АктОКомпенсации`; recompute from actual flags, not from this expectation.
- [x] **Step 4: Run checker** `python check-matrix.py --post <list>`; expected PASS.
- [x] **Step 5: Commit** — `git commit -am "feat(roles): add posting Update rights to matrix"`.

<!-- openspec-task: 1.3 -->
### Task 3: Off-matrix policy + subsystem View

**Files:**
- Modify: `openspec/changes/add-access-roles/roles-matrix.json`
- Modify: `openspec/changes/add-access-roles/check-matrix.py`

**Interfaces:**
- Produces: matrix with all spec-required objects: ЧХ, техническая НСИ, `Пользователи`, константа, БП×4, `ЗадачаИсполнителя`, 5 регистров, обработки×5, `Subsystem.*` rows.

- [x] **Step 1: Add failing coverage checks to `check-matrix.py`** — `--require <list>`: every object of the off-matrix spec requirement appears in ≥1 profile; plus the exact per-object policy assertions from spec «Объекты вне матрицы ТЗ» items 1–6 and «Права на ролевые подсистемы» mapping (Аудитор: 5 бизнес-подсистем; Гид: `ГидНаМаршруте`; etc.), and the negative: `НастройкиИнтеграций`/`ОбменСФайлами` absent in all 6 profiles; `Аудитор` has no `BusinessProcess.*`/`Task.*` keys. Run, expected FAIL.
- [x] **Step 2: Fill the matrix.**
  - `ChartOfCharacteristicTypes.ДополнительныеРеквизитыТуриста` and `...Услуг`: `["Ч","П","В"]` for all profiles.
  - `Catalog.Валюты`, `Catalog.ЕдиницыИзмерения`, `Catalog.СтраныМира`: `["Ч","П","В"]` for all profiles.
  - `Catalog.Пользователи`: `["Ч","П"]` for all profiles.
  - `Constant.ПорогСогласованияРуководителем`: `["Ч"]` for all profiles.
  - `BusinessProcess.КонтрольПодтверждений`, `BusinessProcess.КоординацияМаршрута`, `BusinessProcess.ОбработкаЗапросаТуриста`, `BusinessProcess.УрегулированиеИнцидента`, `Task.ЗадачаИсполнителя`: `["Ч","П","Пров"]` for Оператор/Координатор/МенеджерПретензий/Руководитель, `["Ч","П"]` for Гид, absent for Аудитор. (`Пров` here means platform Update on БП/задачи — the DSL term for task state update; verify via `dsl-reference.md` and substitute its exact semantics, matrix symbol stays `Пров`.)
  - `InformationRegister.АдресацияЗадач`, `InformationRegister.СтатусыИнцидентов`: `["Ч"]` for the four business profiles + Гид (всем бизнес-профилям per spec); `InformationRegister.ИсторияОбработокЗапросов`: `["Ч"]` for Оператор/Менеджер/Руководитель/Аудитор; `InformationRegister.СрокиКонтроля`: `["Ч"]` for Оператор/Координатор/Руководитель/Аудитор.
  - `DataProcessor.ПросроченныеСрокиИSLA`: `["Ч","П","Use"]` for Оператор/Руководитель; `DataProcessor.ПересчётТайминговМаршрутов`: `["Ч","П","Use"]` for Координатор; `DataProcessor.ФормированиеЗапросовПоставщикам`: `["Ч","П","Use"]` for Оператор; `DataProcessor.СводкаСтатусов`: `["Ч","П","Use"]` for Оператор/Координатор/Менеджер/Руководитель/Аудитор.
  - `Subsystem.*`: mapping per spec — `Subsystem.ОператорСопровождения` → `Профиль_Оператор`: `["Ч"]`; `Subsystem.КоординаторЛогистики` → Координатор; `Subsystem.ГидНаМаршруте` → Гид; `Subsystem.МенеджерПоПретензиям` → МенеджерПретензий; `Subsystem.РуководительНаправления` → Руководитель; `Профиль_Аудитор` — все пять бизнес-подсистем по `["Ч"]`. Перед фиксацией формата проверь по `dsl-reference.md`, нужно ли отдельно перечислять вложенные подсистемы; если нужно — добавь ключ на каждую вложенную подсистему рабочего места (имена — из `src/КурсоваяРабота/Subsystems/`).
  - `Enums`: no entries (DSL disallows; record in the JSON top-level `"$note"` key: «Перечисления прав не имеют — чтение доступно всем»).
- [x] **Step 3: Run checker** with the full required-object list; expected PASS.
- [x] **Step 4: Commit** — `git commit -am "feat(roles): add off-matrix and subsystem rights to matrix"`.

<!-- openspec-task: 2.1 -->
### Task 4: Generate 6 roles via role-compile

**Files:**
- Create: `openspec/changes/add-access-roles/roles/Профиль_Оператор.json` … `roles/Профиль_Аудитор.json` (6 files)
- Generated: `src/КурсоваяРабота/Roles/Профиль_*.xml`, `src/КурсоваяРабота/Roles/Профиль_*/Ext/Rights.xml`

**Interfaces:**
- Consumes: `roles-matrix.json` (Tasks 1–3). Produces: 6 role metadata file pairs registered in `Configuration.xml` (registration verified in Task 5).

- [x] **Step 1: Read `.opencode/skills/role-compile/dsl-reference.md` fully** and freeze the symbol→DSL table: `Ч`→чтение, `П`→просмотр, `И`→интерактивное добавление, `Изм`→интерактивное изменение, `В`→ввод по строке, `Пров`→проведение/Update, `Use`→использование обработки, subsystem visibility. Cells equal to `ЧПВ` MAY use preset `@view` (it expands exactly to reading+presentation+input-by-string for catalogs/documents and view+use for processors) — verify expansion in the reference before relying on it; explicit rights are always acceptable.
- [x] **Step 2: Write `emit-role-json.py`** (in `openspec/changes/add-access-roles/`): reads `roles-matrix.json`, emits `roles/<Профиль>.json` per profile in role-compile DSL shape (`{"name", "synonym", "objects": ["Тип.Имя: Право1, Право2", ...]}`, omit `setForNewObjects` or set `false`). Run; expected: 6 JSON files, each object count equals matrix row count.
- [x] **Step 3: Compile each role:**
  ```powershell
  python ".opencode/skills/role-compile/scripts/role-compile.py" -JsonPath "openspec/changes/add-access-roles/roles/Профиль_Оператор.json" -OutputDir "src/КурсоваяРабота"
  ```
  (repeat for all 6). Expected: no DSL errors; `Roles/<Имя>.xml` + `Roles/<Имя>/Ext/Rights.xml` created for each.
- [x] **Step 4: Verify presence** — `Get-ChildItem src\КурсоваяРабота\Roles` shows 7 role dirs/files (6 new + `Администратор`).
- [x] **Step 5: Commit** — `git add src/КурсоваяРабота/Roles openspec/changes/add-access-roles/roles && git commit -m "feat(roles): generate 6 profile roles from rights matrix"`.

<!-- openspec-task: 2.2 -->
### Task 5: Configuration composition registration

**Files:**
- Modify (only if needed): `src/КурсоваяРабота/Configuration.xml` (via `cf-edit`)

**Interfaces:**
- Consumes: Task 4 generated roles. Produces: 7 `<Role>` records in `Configuration.xml`.

- [x] **Step 1: Count registrations** — `Select-String -Path src\КурсоваяРабота\Configuration.xml -Pattern '<Role>'`. Expected: 7 lines. If `role-compile` already registered (its SKILL.md states it does), approve and skip step 2.
- [x] **Step 2: If fewer than 7** — use skill `cf-edit` to add missing roles to the configuration composition; re-run step 1; expected 7.
- [x] **Step 3: Confirm `DefaultRoles` still empty** — `Select-String -Pattern '<DefaultRoles/>'` finds the empty tag; expected: present, untouched.
- [x] **Step 4: Commit if step 2 ran** — `git commit -am "fix(config): register profile roles in composition"`.

<!-- openspec-task: 2.3 -->
### Task 6: Validate roles and configuration

**Files:**
- Read: all generated `Roles/Профиль_*/Ext/Rights.xml`

**Interfaces:**
- Consumes: Tasks 4–5. Produces: validated metadata ready for Part 2 (IB load).

- [x] **Step 1: `/role-validate` each of the 6** `src/КурсоваяРабота/Roles/Профиль_*/Ext/Rights.xml` (skill `role-validate`). Expected: all valid. Any failure: fix `roles-matrix.json`/emitted JSON, re-run Task 4 step 2–3 (regenerate, never hand-edit `Rights.xml`), re-validate.
- [x] **Step 2: `/cf-validate`** configuration. Expected: valid, no complaints about role composition.
- [x] **Step 3: Spot semantic check** — `/role-info` for `Профиль_Аудитор`: every object shows only reading-level rights; no object shows delete/mark-for-deletion; and no profile shows `setForNewObjects=true` (grep: `Select-String src\КурсоваяРабота\Roles\Профиль_*.xml -Pattern '<SetForNewObjects>.*true'` → no matches). Expected: PASS.
- [x] **Step 4: Commit** any matrix/JSON corrections: `git commit -am "fix(roles): corrections after validation"`.

<!-- openspec-task: 2.4 -->
### Task 7: Администратор immutability guard

**Files:**
- Read only.

**Interfaces:**
- Consumes: final git tree after Tasks 4–6. Produces: verified invariant for Part 2.

- [x] **Step 1:** `git diff HEAD~N -- src/КурсоваяРабота/Roles/Администратор.xml src/КурсоваяРабота/Roles/Администратор` (N = commits of this plan) — expected: EMPTY diff.
- [x] **Step 2:** `Select-String -Path src\КурсоваяРабота\Roles\Администратор.xml -Pattern '527785c9-76dd-4423-a179-dd3d73bb9a2a'` — expected: match.
- [x] **Step 3:** `Select-String -Path src\КурсоваяРабота\Configuration.xml -Pattern '<DefaultRoles/>'` — expected: empty tag (no auto-role assignment).
- [x] **Step 4:** If any check failed: revert the offending tooling change (regenerate from matrix / `git checkout` the `Администратор` paths), re-run Tasks 6–7, and only then proceed to the commit below.
- [x] **Step 5: Commit** (only if step 4 produced changes) — `git commit -am "fix(roles): restore administrator role immutability"`.
