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
Дополнительные ключи объектов (политика «вне матрицы ТЗ») разрешены —
они проверяются только правилами (a) и (e).

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
MATRIX_SYMBOLS = VALID_SYMBOLS + [POSTING_SYMBOL]

# Профиль, которому «Пров» запрещён всегда (только чтение/создание, без правки).
NO_POSTING_PROFILE = "Профиль_Гид"

ABSENT = "-"

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
