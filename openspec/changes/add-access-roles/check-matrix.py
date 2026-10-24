# -*- coding: utf-8 -*-
"""Проверка roles-matrix.json — единого источника прав (design.md D3).

Правила (Task 1, specs/access-roles/spec.md, три таблицы раздела 6):
  (a) каждый ключ объекта "<Тип>.<Имя>" имеет исходник
      src/КурсоваяРабота/<Тип plural>/<Имя>.xml;
  (b) ячейки трёх таблиц спеки воспроизведены точно:
      не-«-» ячейка => ключ присутствует в профиле ровно с этими символами;
      «-» ячейка    => ключ ОТСУТСТВУЕТ в профиле (решение контроллера:
                       «-» побеждает правило «присутствует во всех профилях»).
Дополнительные ключи (объекты вне матрицы ТЗ, политика спеки) разрешены —
они проверяются только правилом (a).

Запуск:  python check-matrix.py [путь к roles-matrix.json]
Код возврата: 0 — нарушений нет, 1 — есть нарушения / файл не найден.
"""
import io
import json
import os
import sys

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
REPO_ROOT = os.path.abspath(os.path.join(SCRIPT_DIR, "..", "..", ".."))
SRC_ROOT = os.path.join(REPO_ROOT, "src", "КурсоваяРабота")
DEFAULT_MATRIX = os.path.join(SCRIPT_DIR, "roles-matrix.json")

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

# --- Три таблицы спеки, транскрибированы дословно ---
# Ключ объекта -> 6 ячеек в порядке PROFILES; "-" = отсутствие прав.
SPEC_TABLES = {
    # Права на справочники
    "Catalog.Туристы":              ["ЧПИИзмВ", "ЧПВ", "ЧВ", "ЧПВ", "ЧПВ", "ЧПВ"],
    "Catalog.ЗаявкиНаТур":          ["ЧПИИзмВ", "ЧПВ", "ЧВ", "ЧПВ", "ЧПВ", "ЧПВ"],
    "Catalog.ТурыМаршруты":         ["ЧПВ", "ЧПВ", "ЧВ", "ЧПВ", "ЧПВ", "ЧПВ"],
    "Catalog.Поставщики":           ["ЧПВ", "ЧПВ", "ЧВ", "ЧПВ", "ЧПВ", "ЧПВ"],
    "Catalog.ДоговорыСПоставщиками": ["ЧПВ", "ЧПВ", "-", "ЧПВ", "ЧПВ", "ЧПВ"],
    "Catalog.ОбъектыГостеприимства": ["ЧПВ", "ЧПВ", "ЧВ", "ЧПВ", "ЧПВ", "ЧПВ"],
    "Catalog.НоменклатураУслуг":    ["ЧПВ", "ЧПВ", "ЧВ", "ЧПВ", "ЧПВ", "ЧПВ"],
    "Catalog.ТипыЗапросовТуристов": ["ЧПВ", "ЧПВ", "-", "ЧПВ", "ЧПВ", "ЧПВ"],
    "Catalog.ТипыИнцидентов":       ["ЧПВ", "ЧПВ", "-", "ЧПВ", "ЧПВ", "ЧПВ"],
    "Catalog.Сотрудники":           ["ЧПВ", "ЧПВ", "ЧПВ", "ЧПВ", "ЧПВ", "ЧПВ"],
    # Права на документы
    "Document.ЗаказПоставщику":        ["ЧПИИзмВ", "ЧПВ", "-", "ЧПВ", "ЧПВ", "ЧПВ"],
    "Document.ПодтверждениеУслуги":    ["ЧПИИзмВ", "ЧПВ", "-", "ЧПВ", "ЧПВ", "ЧПВ"],
    "Document.МаршрутныйЛист":         ["ЧПВ", "ЧПИИзмВ", "ЧВ", "ЧПВ", "ЧПВ", "ЧПВ"],
    "Document.СобытиеМаршрута":        ["ЧПВ", "ЧПИИзмВ", "ЧВ", "ЧПВ", "ЧПВ", "ЧПВ"],
    "Document.КорректировкаМаршрута":  ["ЧПВ", "ЧПИИзмВ", "-", "ЧПВ", "ЧПВ", "ЧПВ"],
    "Document.ЗаявкаТуристаНаМаршруте": ["ЧПИИзмВ", "ЧПВ", "ЧПИВ", "ЧПВ", "ЧПВ", "ЧПВ"],
    "Document.Инцидент":               ["ЧПВ", "ЧПВ", "ЧПИВ", "ЧПИИзмВ", "ЧПВ", "ЧПВ"],
    "Document.ПретензияПоставщику":    ["-", "-", "-", "ЧПИИзмВ", "ЧПВ", "ЧПВ"],
    "Document.АктОКомпенсации":        ["-", "-", "-", "ЧПИИзмВ", "ЧПВ", "ЧПВ"],
    # Права на регистры
    "InformationRegister.СтатусыПодтверждений":      ["Ч", "Ч", "-", "Ч", "Ч", "Ч"],
    "InformationRegister.ПараметрыУслуг":            ["Ч", "Ч", "-", "Ч", "Ч", "Ч"],
    "InformationRegister.ГрафикПеремещений":         ["Ч", "Ч", "Ч", "Ч", "Ч", "Ч"],
    "AccumulationRegister.ВзаиморасчётыПоПретензиям": ["-", "-", "-", "Ч", "Ч", "Ч"],
    "AccumulationRegister.ШтрафыИКомпенсации":       ["-", "-", "-", "Ч", "Ч", "Ч"],
    "AccumulationRegister.KPIОператоров":            ["Ч", "Ч", "Ч", "Ч", "Ч", "Ч"],
}

ABSENT = "-"


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


def check(matrix_path, enforce_absent_rule=True):
    errors = []
    if not os.path.isfile(matrix_path):
        return ["roles-matrix.json not found: %s" % matrix_path]

    with io.open(matrix_path, "r", encoding="utf-8") as f:
        matrix = json.load(f)

    profiles = matrix.get("profiles")
    if not isinstance(profiles, dict):
        return ["matrix has no 'profiles' object"]

    # Структура: 6 профилей с синонимами
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

    # (a) каждый ключ объекта -> реальный исходник метаданных
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
                if sym not in VALID_SYMBOLS:
                    errors.append("%s: %r has invalid symbol %r" % (pname, key, sym))

    # (b) таблицы спеки воспроизведены дословно
    for key, cells in SPEC_TABLES.items():
        for pname, cell in zip(PROFILES, cells):
            prof = profiles.get(pname)
            if not isinstance(prof, dict) or not isinstance(prof.get("objects"), dict):
                continue
            objects = prof["objects"]
            if cell == ABSENT:
                if enforce_absent_rule and key in objects:
                    errors.append(
                        "%s: spec cell is '-' but key %r is present (%r)"
                        % (pname, key, objects[key])
                    )
            else:
                expected = parse_cell(cell)
                actual = objects.get(key)
                if actual is None:
                    errors.append("%s: spec cell %r but key %r is absent" % (pname, cell, key))
                elif actual != expected:
                    errors.append(
                        "%s: %r rights %r != spec %r (cell %r)"
                        % (pname, key, actual, expected, cell)
                    )
    return errors


def main():
    matrix_path = sys.argv[1] if len(sys.argv) > 1 else DEFAULT_MATRIX
    errors = check(matrix_path)
    out = io.open(sys.stdout.fileno(), "w", encoding="utf-8", closefd=False)
    if errors:
        out.write("FAIL: %d violation(s)\n" % len(errors))
        for e in errors:
            out.write("  - %s\n" % e)
        out.flush()
        sys.exit(1)
    keys = sum(
        len(p.get("objects", {})) for p in json.load(io.open(matrix_path, encoding="utf-8"))["profiles"].values()
    )
    out.write(
        "OK: 25 spec objects x 6 profiles verified against spec tables "
        "(%d object keys total, metadata files exist)\n" % keys
    )
    out.flush()
    sys.exit(0)


if __name__ == "__main__":
    main()
