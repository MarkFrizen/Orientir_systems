# -*- coding: utf-8 -*-
"""Проверка roles-matrix.json — единого источника прав (design.md D3).

Таблицы прав ЧИТАЮТСЯ ИЗ СПЕКИ at runtime (specs/access-roles/spec.md,
разделы «Права на справочники», «Права на документы», «Права на регистры») —
никаких захардкоженных ожиданий: если spec.md изменён, проверяется новая матрица.

Правила:
  (a) каждый ключ объекта "<Тип>.<Имя>" имеет исходник
      src/КурсоваяРабота/<Тип plural>/<Имя>.xml; список прав непустой,
      без дублей символов, символы только из легенды ТЗ (Ч, П, И, Изм, В);
  (b) ячейки трёх таблиц спеки воспроизведены точно:
      не-«-» ячейка => ключ присутствует в профиле ровно с этими символами;
      «-» ячейка    => ключ ОТСУТСТВУЕТ в профиле (решение контроллера:
                       «-» побеждает правило «присутствует во всех профилях»);
  (c) профилей ровно 6 (spec.md:10 запрещает иные, напр. Профиль_Администратор);
  (d) каждая строка таблиц спеки содержит ровно 6 ячеек прав — короткая/длинная
      строка FAIL loudly, а не молча отбрасывается;
  (e) инварианты проведения (design.md D5, «Право обновления при проведении»):
      символ «Пров» допустим только у ключей Document./BusinessProcess./Task.;
      для Document.* «Пров» обязан присутствовать тогда и только тогда, когда
      документ проводимый (--post) и у профиля есть «Изм»;
      Профиль_Гид не содержит «Пров» нигде.
      Правило (b) при этом усиливается: ожидаемый список прав ячейки спеки =
      символы ячейки + «Пров», если документ проводимый и в ячейке есть «Изм».
Правило (f): политика «Объекты вне матрицы ТЗ» (spec.md, пункты 1–6) и
сопоставления «Права на ролевые подсистемы» воспроизведены точно
(OFF_MATRIX_POLICY): права по профилям совпадают, незадействованному профилю
ключ запрещён, каждый объект политики присутствует хотя бы в одном профиле
(покрытие); НастройкиИнтеграций/ОбменСФайлами/АдминистраторИС запрещены везде;
Профиль_Аудитор не содержит ключей BusinessProcess.*/Task.*; символ «Use»
допустим только у ключей DataProcessor.*.
Прочие дополнительные ключи объектов разрешены — они проверяются правилами
(a) и (e).

Запуск:  python check-matrix.py [--post <csv имён проводимых документов>]
                                 [путь к roles-matrix.json]
Код возврата: 0 — нарушений нет, 1 — есть нарушения / файлы не найдены.
"""
import io
import json
import os
import sys

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
REPO_ROOT = os.path.abspath(os.path.join(SCRIPT_DIR, "..", "..", ".."))
SRC_ROOT = os.path.join(REPO_ROOT, "src", "КурсоваяРабота")
DEFAULT_MATRIX = os.path.join(SCRIPT_DIR, "roles-matrix.json")
SPEC_PATH = os.path.join(SCRIPT_DIR, "specs", "access-roles", "spec.md")

# Профили в порядке колонок таблиц спеки (Опер | Коор | Гид | Менедж | Рук | Аудит)
PROFILES = [
    "Профиль_Оператор",
    "Профиль_Координатор",
    "Профиль_Гид",
    "Профиль_МенеджерПретензий",
    "Профиль_Руководитель",
    "Профиль_Аудитор",
]

SYNONYMS = {
    "Профиль_Оператор": "Оператор сопровождения",
    "Профиль_Координатор": "Координатор логистики",
    "Профиль_Гид": "Гид на маршруте",
    "Профиль_МенеджерПретензий": "Менеджер по претензиям",
    "Профиль_Руководитель": "Руководитель направления",
    "Профиль_Аудитор": "Аудитор (только чтение)",
}

TYPE_TO_FOLDER = {
    "Catalog": "Catalogs",
    "Document": "Documents",
    "InformationRegister": "InformationRegisters",
    "AccumulationRegister": "AccumulationRegisters",
    "DataProcessor": "DataProcessors",
    "Constant": "Constants",
    "ChartOfCharacteristicTypes": "ChartsOfCharacteristicTypes",
    "BusinessProcess": "BusinessProcesses",
    "Task": "Tasks",
    "Subsystem": "Subsystems",
}

# Условные обозначения ТЗ (design.md D2): Ч, П, И, Изм, В
VALID_SYMBOLS = ["Ч", "П", "Изм", "И", "В"]

# Право обновления при проведении (design.md D5) — только для документов,
# бизнес-процессов и задач; в таблицах спеки не встречается.
POSTING_SYMBOL = "Пров"
POSTING_PREFIXES = ("Document.", "BusinessProcess.", "Task.")

# «Использование» обработок (spec «Объекты вне матрицы ТЗ» п.6: Use) —
# символ вне алфавита таблиц спеки, допустим только у DataProcessor.*.
USE_SYMBOL = "Use"
USE_PREFIXES = ("DataProcessor.",)

MATRIX_SYMBOLS = VALID_SYMBOLS + [POSTING_SYMBOL, USE_SYMBOL]

# Профиль, которому «Пров» запрещён всегда (только чтение/создание, без правки).
NO_POSTING_PROFILE = "Профиль_Гид"

ABSENT = "-"

# ---------------------------------------------------------------------------
# Правило (f): политика «Объекты вне матрицы ТЗ» (spec.md, одноимённое
# требование, пункты 1–6) и «Права на ролевые подсистемы» (сопоставления после
# сценариев). Это проза, а не таблицы спеки, поэтому ожидания кодируются здесь
# явно; при изменении spec.md блок нужно синхронно править.
# Значение None / отсутствующий профиль = ключ обязан ОТСУТСТВОВАТЬ в профиле.
# ---------------------------------------------------------------------------
_P_OP = "Профиль_Оператор"
_P_KO = "Профиль_Координатор"
_P_GID = "Профиль_Гид"
_P_ME = "Профиль_МенеджерПретензий"
_P_RUK = "Профиль_Руководитель"
_P_AU = "Профиль_Аудитор"

# п.4: БП и задача — Update (в DSL «Пров») Оператору/Координатору/
# МенеджерПретензий/Руководителю; Гиду View+Presentation; Аудитору ничего.
_BP_TASK_RIGHTS = {
    _P_OP: ["Ч", "П", POSTING_SYMBOL],
    _P_KO: ["Ч", "П", POSTING_SYMBOL],
    _P_GID: ["Ч", "П"],
    _P_ME: ["Ч", "П", POSTING_SYMBOL],
    _P_RUK: ["Ч", "П", POSTING_SYMBOL],
}

# п.6: Use-обработки по рабочим местам.
_PROC_RIGHTS = ["Ч", "П", USE_SYMBOL]

OFF_MATRIX_POLICY = {
    # п.1: ЧХ и техническая НСИ — View+Presentation+ItemInput всем профилям
    "ChartOfCharacteristicTypes.ДополнительныеРеквизитыТуриста": {p: ["Ч", "П", "В"] for p in PROFILES},
    "ChartOfCharacteristicTypes.ДополнительныеРеквизитыУслуг": {p: ["Ч", "П", "В"] for p in PROFILES},
    "Catalog.Валюты": {p: ["Ч", "П", "В"] for p in PROFILES},
    "Catalog.ЕдиницыИзмерения": {p: ["Ч", "П", "В"] for p in PROFILES},
    "Catalog.СтраныМира": {p: ["Ч", "П", "В"] for p in PROFILES},
    # п.2: Пользователи — View+Presentation всем (автор/ответственный)
    "Catalog.Пользователи": {p: ["Ч", "П"] for p in PROFILES},
    # п.3: константа — View всем
    "Constant.ПорогСогласованияРуководителем": {p: ["Ч"] for p in PROFILES},
    # п.4: бизнес-процессы (4) и задача
    "BusinessProcess.КонтрольПодтверждений": dict(_BP_TASK_RIGHTS),
    "BusinessProcess.КоординацияМаршрута": dict(_BP_TASK_RIGHTS),
    "BusinessProcess.ОбработкаЗапросаТуриста": dict(_BP_TASK_RIGHTS),
    "BusinessProcess.УрегулированиеИнцидента": dict(_BP_TASK_RIGHTS),
    "Task.ЗадачаИсполнителя": dict(_BP_TASK_RIGHTS),
    # п.5: регистры сведений
    "InformationRegister.АдресацияЗадач": {
        _P_OP: ["Ч"], _P_KO: ["Ч"], _P_GID: ["Ч"], _P_ME: ["Ч"], _P_RUK: ["Ч"],
    },
    "InformationRegister.СтатусыИнцидентов": {
        _P_OP: ["Ч"], _P_KO: ["Ч"], _P_GID: ["Ч"], _P_ME: ["Ч"], _P_RUK: ["Ч"],
    },
    "InformationRegister.ИсторияОбработокЗапросов": {
        _P_OP: ["Ч"], _P_ME: ["Ч"], _P_RUK: ["Ч"], _P_AU: ["Ч"],
    },
    "InformationRegister.СрокиКонтроля": {
        _P_OP: ["Ч"], _P_KO: ["Ч"], _P_RUK: ["Ч"], _P_AU: ["Ч"],
    },
    # п.6: обработки
    "DataProcessor.ПросроченныеСрокиИSLA": {_P_OP: list(_PROC_RIGHTS), _P_RUK: list(_PROC_RIGHTS)},
    "DataProcessor.ПересчётТайминговМаршрутов": {_P_KO: list(_PROC_RIGHTS)},
    "DataProcessor.ФормированиеЗапросовПоставщикам": {_P_OP: list(_PROC_RIGHTS)},
    "DataProcessor.СводкаСтатусов": {
        _P_OP: list(_PROC_RIGHTS), _P_KO: list(_PROC_RIGHTS), _P_ME: list(_PROC_RIGHTS),
        _P_RUK: list(_PROC_RIGHTS), _P_AU: list(_PROC_RIGHTS),
    },
    # «Права на ролевые подсистемы»: своё рабочее место + Аудитору все пять
    # бизнес-подсистем. Вложенные подсистемы в этой конфигурации не являются
    # отдельными объектами метаданных (Subsystems/*.xml не содержат
    # ChildSubsystems) — достаточно одного ключа на подсистему верхнего уровня.
    "Subsystem.ОператорСопровождения": {_P_OP: ["Ч"], _P_AU: ["Ч"]},
    "Subsystem.КоординаторЛогистики": {_P_KO: ["Ч"], _P_AU: ["Ч"]},
    "Subsystem.ГидНаМаршруте": {_P_GID: ["Ч"], _P_AU: ["Ч"]},
    "Subsystem.МенеджерПоПретензиям": {_P_ME: ["Ч"], _P_AU: ["Ч"]},
    "Subsystem.РуководительНаправления": {_P_RUK: ["Ч"], _P_AU: ["Ч"]},
}

# Ключи, запрещённые во ВСЕХ шести профилях (права имеет только роль
# Администратор: spec сценарии «Настройки интеграций закрыты для профилей»,
# п.5 НастройкиИнтеграций, п.6 ОбменСФайлами, подсистема АдминистраторИС).
FORBIDDEN_EVERYWHERE = [
    "InformationRegister.НастройкиИнтеграций",
    "DataProcessor.ОбменСФайлами",
    "Subsystem.АдминистраторИС",
]

# Профиль, которому запрещены любые ключи BusinessProcess.*/Task.* (п.4:
# «Аудитору — ничего по процессам») и подсистема АдминистраторИС с детьми.
NO_BP_TASK_PROFILE = _P_AU
ADMIN_SUBSYSTEM_PREFIX = "Subsystem.АдминистраторИС"

# Заголовки разделов спеки -> тип объектов её таблицы; ожидаемое число строк.
SPEC_SECTIONS = {
    "Requirement: Права на справочники": ("Catalog", 10),
    "Requirement: Права на документы": ("Document", 9),
    "Requirement: Права на регистры": ("Register", 6),
}

# Префиксы строк таблицы регистров: «Сведения X» / «Накопления X»
REGISTER_PREFIX = {
    "Сведения": "InformationRegister",
    "Накопления": "AccumulationRegister",
}

HEADER_FIRST_CELLS = ("Справочник", "Документ", "Регистр")


def parse_cell(cell):
    """'ЧПИИзмВ' -> ['Ч','П','И','Изм','В']; «Изм» распознаётся жадно."""
    symbols = []
    i = 0
    while i < len(cell):
        for sym in VALID_SYMBOLS:  # порядок: Изм раньше И
            if cell.startswith(sym, i):
                symbols.append(sym)
                i += len(sym)
                break
        else:
            raise ValueError("недопустимый символ в ячейке %r (позиция %d)" % (cell, i))
    return symbols


def split_row(line):
    """'| a | b |' -> ['a', 'b']"""
    return [c.strip() for c in line.strip().strip("|").split("|")]


def is_separator_row(line):
    cells = split_row(line)
    return bool(cells) and all(c and set(c) <= {"-", ":"} for c in cells)


def load_spec_tables(path):
    """Парсит три markdown-таблицы спеки.

    Возвращает (tables, errors): tables = {"<Тип>.<Имя>": [6 ячеек]},
    errors — список нарушений формата/состава спеки.
    """
    tables = {}
    errors = []
    if not os.path.isfile(path):
        return {}, ["spec.md not found: %s" % path]
    with io.open(path, "r", encoding="utf-8") as f:
        lines = f.read().splitlines()

    section = None  # (kind, expected_rows)
    seen_rows = {}
    for line in lines:
        stripped = line.strip()
        if stripped.startswith("### "):
            section = SPEC_SECTIONS.get(stripped[4:].strip())
            continue
        if stripped.startswith("#### "):
            continue  # сценарии внутри требования — раздел сохраняется
        if stripped.startswith("#"):
            section = None
            continue
        if not stripped.startswith("|") or is_separator_row(stripped):
            continue
        if section is None:
            errors.append("spec.md: table row outside the three matrix sections: %r" % stripped)
            continue
        kind, _ = section
        cells = split_row(stripped)
        if cells and cells[0] in HEADER_FIRST_CELLS:
            if len(cells) != 7:
                errors.append(
                    "spec.md: header row must have 7 cells (name + 6 profiles), got %d: %r"
                    % (len(cells), stripped)
                )
            continue
        if len(cells) != 7:
            errors.append(
                "spec.md: %s row must have exactly 7 cells (name + 6 profiles), got %d: %r"
                % (kind, len(cells), stripped)
            )
            continue
        name = cells[0]
        row_cells = cells[1:]
        if kind == "Register":
            parts = name.split(" ", 1)
            if len(parts) != 2 or parts[0] not in REGISTER_PREFIX:
                errors.append("spec.md: register row %r: cannot map type prefix" % name)
                continue
            key = "%s.%s" % (REGISTER_PREFIX[parts[0]], parts[1])
        else:
            key = "%s.%s" % (kind, name)
        if key in tables:
            errors.append("spec.md: duplicate row %r" % key)
            continue
        tables[key] = row_cells
        seen_rows[kind] = seen_rows.get(kind, 0) + 1

    for heading, (kind, expected) in SPEC_SECTIONS.items():
        actual = seen_rows.get(kind, 0)
        if actual != expected:
            errors.append(
                "spec.md: section %r: expected %d table rows, parsed %d"
                % (heading, expected, actual)
            )
    for key, row_cells in sorted(tables.items()):
        for cell in row_cells:
            if cell != ABSENT:
                try:
                    parse_cell(cell)
                except ValueError as exc:
                    errors.append("spec.md: %s: %s" % (key, exc))
    return tables, errors


def check(matrix_path, spec_path=SPEC_PATH, posting_docs=None):
    posting = set(posting_docs or [])
    spec_tables, errors = load_spec_tables(spec_path)
    if not os.path.isfile(matrix_path):
        errors.append("roles-matrix.json not found: %s" % matrix_path)
        return errors

    with io.open(matrix_path, "r", encoding="utf-8") as f:
        matrix = json.load(f)

    profiles = matrix.get("profiles")
    if not isinstance(profiles, dict):
        errors.append("matrix has no 'profiles' object")
        return errors

    # служебные ключи верхнего уровня допустимы только с префиксом «$»
    for extra in sorted(set(matrix.keys()) - {"profiles"}):
        if not extra.startswith("$"):
            errors.append(
                "unexpected top-level matrix key %r (only 'profiles' and '$'-notes allowed)"
                % extra
            )

    # (c) профилей ровно 6: требуемые присутствуют, посторонних нет
    for name in PROFILES:
        prof = profiles.get(name)
        if prof is None:
            errors.append("profile missing: %s" % name)
            continue
        expected_syn = SYNONYMS[name]
        if prof.get("synonym") != expected_syn:
            errors.append(
                "profile %s synonym %r != expected %r"
                % (name, prof.get("synonym"), expected_syn)
            )
        if not isinstance(prof.get("objects"), dict):
            errors.append("profile %s has no 'objects' map" % name)
    for stray in sorted(set(profiles.keys()) - set(PROFILES)):
        errors.append(
            "unexpected profile %r: spec allows exactly 6 profiles "
            "(Профиль_Администратор forbidden)" % stray
        )

    # (a) каждый ключ объекта -> реальный исходник метаданных; права валидны
    for pname, prof in profiles.items():
        objects = prof.get("objects")
        if not isinstance(objects, dict):
            continue
        for key, rights in objects.items():
            if "." not in key:
                errors.append("%s: key %r has no type prefix" % (pname, key))
                continue
            mtype, mname = key.split(".", 1)
            folder = TYPE_TO_FOLDER.get(mtype)
            if folder is None:
                errors.append("%s: unknown metadata type %r in key %r" % (pname, mtype, key))
                continue
            xml = os.path.join(SRC_ROOT, folder, mname + ".xml")
            if not os.path.isfile(xml):
                errors.append("%s: metadata file not found for key %r (%s)" % (pname, key, xml))
            if not isinstance(rights, list) or not rights:
                errors.append("%s: rights for %r must be a non-empty list" % (pname, key))
                continue
            for sym in rights:
                if sym not in MATRIX_SYMBOLS:
                    errors.append("%s: %r has invalid symbol %r" % (pname, key, sym))
                elif sym == POSTING_SYMBOL and not key.startswith(POSTING_PREFIXES):
                    errors.append(
                        "%s: %r has %r but key type allows only %s"
                        % (pname, key, POSTING_SYMBOL, "/".join(POSTING_PREFIXES))
                    )
                elif sym == USE_SYMBOL and not key.startswith(USE_PREFIXES):
                    errors.append(
                        "%s: %r has %r but key type allows only %s"
                        % (pname, key, USE_SYMBOL, "/".join(USE_PREFIXES))
                    )
            if len(set(rights)) != len(rights):
                errors.append("%s: %r has duplicate symbols: %r" % (pname, key, rights))

    # (e) инварианты проведения: «Пров» <=> проводимый документ + «Изм»
    for pname, prof in profiles.items():
        objects = prof.get("objects")
        if not isinstance(objects, dict):
            continue
        for key, rights in objects.items():
            if not isinstance(rights, list):
                continue
            has_prov = POSTING_SYMBOL in rights
            if has_prov and pname == NO_POSTING_PROFILE:
                errors.append(
                    "%s: %r contains %r but this profile must never have it"
                    % (pname, key, POSTING_SYMBOL)
                )
            if not key.startswith("Document."):
                continue  # BusinessProcess./Task.: префикс проверен правилом (a)
            doc = key.split(".", 1)[1]
            if has_prov and doc not in posting:
                errors.append(
                    "%s: %r has %r but document is not posting-enabled (--post)"
                    % (pname, key, POSTING_SYMBOL)
                )
            if doc in posting:
                has_izm = "Изм" in rights
                if has_izm and not has_prov:
                    errors.append(
                        "%s: %r is a posting document with 'Изм' but lacks %r"
                        % (pname, key, POSTING_SYMBOL)
                    )
                if has_prov and not has_izm:
                    errors.append(
                        "%s: %r has %r without 'Изм'" % (pname, key, POSTING_SYMBOL)
                    )

    # (b) таблицы спеки (разобранные из spec.md) воспроизведены дословно
    for key in sorted(spec_tables):
        cells = spec_tables[key]
        for pname, cell in zip(PROFILES, cells):
            prof = profiles.get(pname)
            if not isinstance(prof, dict) or not isinstance(prof.get("objects"), dict):
                continue
            objects = prof["objects"]
            if cell == ABSENT:
                if key in objects:
                    errors.append(
                        "%s: spec cell is '-' but key %r is present (%r)"
                        % (pname, key, objects[key])
                    )
            else:
                expected = parse_cell(cell)
                # решение контроллера: ячейка спеки + «Пров» на пересечении
                # (проводимый документ ∩ у профиля есть «Изм»)
                if (
                    key.startswith("Document.")
                    and key.split(".", 1)[1] in posting
                    and "Изм" in expected
                ):
                    expected = expected + [POSTING_SYMBOL]
                actual = objects.get(key)
                if actual is None:
                    errors.append("%s: spec cell %r but key %r is absent" % (pname, cell, key))
                elif actual != expected:
                    errors.append(
                        "%s: %r rights %r != spec %r (cell %r)"
                        % (pname, key, actual, expected, cell)
                    )

    # (f) политика объектов вне матрицы ТЗ (пункты 1–6) и ролевые подсистемы:
    # точное совпадение прав по профилям; покрытие — каждый объект политики
    # присутствует хотя бы в одном профиле; запрещённые ключи отсутствуют везде.
    def _objects_of(pname):
        prof = profiles.get(pname)
        if isinstance(prof, dict) and isinstance(prof.get("objects"), dict):
            return prof["objects"]
        return {}

    for key in sorted(OFF_MATRIX_POLICY):
        expected_map = OFF_MATRIX_POLICY[key]
        present_in = []
        for pname in PROFILES:
            objects = _objects_of(pname)
            expected = expected_map.get(pname)
            actual = objects.get(key)
            if actual is not None:
                present_in.append(pname)
            if expected is None:
                if actual is not None:
                    errors.append(
                        "%s: off-matrix policy does not grant %r to this profile "
                        "but it is present (%r)" % (pname, key, actual)
                    )
            elif actual is None:
                errors.append(
                    "%s: off-matrix policy requires %r = %r but key is absent"
                    % (pname, key, expected)
                )
            elif actual != expected:
                errors.append(
                    "%s: %r rights %r != off-matrix policy %r"
                    % (pname, key, actual, expected)
                )
        if not present_in:
            errors.append(
                "spec coverage: off-matrix object %r appears in no profile" % key
            )

    for key in FORBIDDEN_EVERYWHERE:
        for pname in PROFILES:
            if key in _objects_of(pname):
                errors.append(
                    "%s: key %r is forbidden in all 6 profiles "
                    "(rights belong to role Администратор only)" % (pname, key)
                )

    for key in _objects_of(NO_BP_TASK_PROFILE):
        if key.startswith(("BusinessProcess.", "Task.")):
            errors.append(
                "%s: %r forbidden — auditor gets no rights on business "
                "processes/tasks (spec, Объекты вне матрицы п.4)"
                % (NO_BP_TASK_PROFILE, key)
            )
        if key.startswith(ADMIN_SUBSYSTEM_PREFIX):
            errors.append(
                "%s: %r forbidden — АдминистраторИС belongs to role "
                "Администратор" % (NO_BP_TASK_PROFILE, key)
            )
    return errors


def parse_args(argv):
    """[--post <csv>] [matrix_path] -> (matrix_path, posting_docs)"""
    posting = []
    positional = []
    i = 0
    while i < len(argv):
        arg = argv[i]
        if arg == "--post":
            if i + 1 >= len(argv):
                raise ValueError("--post requires a comma-separated value")
            posting = [p.strip() for p in argv[i + 1].split(",") if p.strip()]
            i += 2
        elif arg.startswith("--post="):
            posting = [p.strip() for p in arg[len("--post="):].split(",") if p.strip()]
            i += 1
        else:
            positional.append(arg)
            i += 1
    matrix_path = positional[0] if positional else DEFAULT_MATRIX
    return matrix_path, posting


def main():
    try:
        matrix_path, posting = parse_args(sys.argv[1:])
    except ValueError as exc:
        sys.stderr.write("FAIL: %s\n" % exc)
        sys.exit(1)
    errors = check(matrix_path, posting_docs=posting)
    out = io.open(sys.stdout.fileno(), "w", encoding="utf-8", closefd=False)
    if errors:
        out.write("FAIL: %d violation(s)\n" % len(errors))
        for e in errors:
            out.write("  - %s\n" % e)
        out.flush()
        sys.exit(1)
    with io.open(matrix_path, encoding="utf-8") as f:
        keys = sum(len(p.get("objects", {})) for p in json.load(f)["profiles"].values())
    out.write(
        "OK: %d spec rows x 6 profiles parsed from spec.md and verified "
        "(%d object keys total, metadata files exist, %d posting docs via --post)\n"
        % (len(load_spec_tables(SPEC_PATH)[0]), keys, len(posting))
    )
    out.flush()
    sys.exit(0)


if __name__ == "__main__":
    main()
