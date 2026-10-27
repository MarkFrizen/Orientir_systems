# -*- coding: utf-8 -*-
"""Task 4 (add-access-roles): roles-matrix.json -> role-compile DSL JSON x6.

Вся конвертация «символы матрицы -> DSL-права» и платформенное замыкание
зависимостей прав живут в общем модуле rights_map.py (единый источник для
этого скрипта и для гейтов check-matrix.py: def<->матрица, def<->XML).
Здесь НЕ хардкодится ни политика, ни замыкание — только чтение матрицы и
запись def-ов.

Замыкание применено ПРЕДВАРИТЕЛЬНО (rights_map.closed_rights): строки objects
содержат итоговый набор прав, который role-compile запишет в Rights.xml
(InteractiveInsert -> Edit/Insert/Read/Update/View; InputByString -> Read/View;
Posting-цепочка -> Edit; подробности и номера строк role-compile.py — в
докстринге rights_map.py). Поэтому повторная компиляция не добавляет прав
сверх def-а, и артефакты доказуемо воспроизводимы из roles-matrix.json.

Profile-level suppression (controller ruling, review of Task 4): BLOCKED —
  suppressing `Edit` for Профиль_Гид on Document.Инцидент/ЗаявкаТуристаНаМаршруте
  while keeping InteractiveInsert is impossible via role-compile (dependency
  closure flips the explicit deny back to true; the platform reportedly does the
  same at load). See task-4-report.md §8. The matrix stays untouched.
setForAttributesByDefault: DSL default (true) — not emitted (controller ruling).
setForNewObjects: never emitted (default false).
Presets are NOT used — explicit right lists everywhere.
"""
import io
import json
import os
import sys

sys.stdout.reconfigure(encoding="utf-8")

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import rights_map  # noqa: E402

MATRIX = os.path.join(HERE, "roles-matrix.json")
OUT_DIR = os.path.join(HERE, "roles")


def convert(key, symbols):
    try:
        return rights_map.rights_line(key, symbols)
    except rights_map.ConversionError as exc:
        raise SystemExit("ERROR: %s" % exc)


def main():
    with io.open(MATRIX, encoding="utf-8") as f:
        matrix = json.load(f)
    os.makedirs(OUT_DIR, exist_ok=True)
    ok = True
    for profile, data in matrix["profiles"].items():
        objects = [convert(k, v) for k, v in data["objects"].items()]
        doc = {
            "name": profile,
            "synonym": data["synonym"],
            "objects": objects,
        }
        path = os.path.join(OUT_DIR, profile + ".json")
        with io.open(path, "w", encoding="utf-8", newline="\n") as f:
            json.dump(doc, f, ensure_ascii=False, indent=2)
            f.write("\n")
        rows = len(data["objects"])
        match = "OK" if rows == len(objects) else "MISMATCH"
        if rows != len(objects):
            ok = False
        print("%s.json: %d objects (matrix rows: %d) %s" % (profile, len(objects), rows, match))
    print("ALL COUNTS MATCH" if ok else "COUNT MISMATCH")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
