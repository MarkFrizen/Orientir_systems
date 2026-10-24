# -*- coding: utf-8 -*-
"""Task 4 (add-access-roles): roles-matrix.json -> role-compile DSL JSON x6.

Frozen symbol -> DSL mapping (dsl-reference.md is authoritative; design D2/D5):
  Ч    -> Read                       (Subsystem: View; DataProcessor/Report: View)
  П    -> View                       (DataProcessor/Report: View)
  И    -> Insert, InteractiveInsert  (интерактивное добавление = data right + interactive right)
  Изм  -> Update                     (platform has no "interactive update"; D5: Изм -> Update)
  В    -> InputByString
  Пров -> Document: Posting, InteractivePosting, InteractivePostingRegular
          BusinessProcess/Task: Update (Update-equivalent per dispatch)
  Use  -> Use                        (DataProcessor/Report)
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
MATRIX = os.path.join(HERE, "roles-matrix.json")
OUT_DIR = os.path.join(HERE, "roles")

# per-type-family symbol -> list of DSL rights
COMMON = {
    "Ч": ["Read"],
    "П": ["View"],
    "И": ["Insert", "InteractiveInsert"],
    "Изм": ["Update"],
    "В": ["InputByString"],
}
DOCUMENT = dict(COMMON)
DOCUMENT["Пров"] = ["Posting", "InteractivePosting", "InteractivePostingRegular"]
PROCESS = dict(COMMON)
PROCESS["Пров"] = ["Update"]  # Update-equivalent on BusinessProcess./Task.
DATAPROCESSOR = {
    "Ч": ["View"],  # DataProcessor/Report have only Use, View
    "П": ["View"],
    "Use": ["Use"],
}
SUBSYSTEM = {"Ч": ["View"]}  # Subsystem's only right is View (visibility)
CONSTANT = {"Ч": ["Read"], "П": ["View"], "Изм": ["Update"]}
REGISTER = {"Ч": ["Read"], "П": ["View"], "Изм": ["Update"]}


def table_for(obj_type):
    if obj_type == "Document":
        return DOCUMENT
    if obj_type in ("BusinessProcess", "Task"):
        return PROCESS
    if obj_type in ("DataProcessor", "Report"):
        return DATAPROCESSOR
    if obj_type == "Subsystem":
        return SUBSYSTEM
    if obj_type == "Constant":
        return CONSTANT
    if obj_type.endswith("Register"):
        return REGISTER
    return COMMON  # Catalog, ChartOfCharacteristicTypes, etc.


def convert(key, symbols):
    obj_type = key.split(".", 1)[0]
    table = table_for(obj_type)
    rights = []
    for sym in symbols:
        if sym not in table:
            raise SystemExit(
                "ERROR: symbol %r not defined for %s (key %s)" % (sym, obj_type, key)
            )
        for r in table[sym]:
            if r not in rights:
                rights.append(r)
    if not rights:
        raise SystemExit("ERROR: empty rights for %s" % key)
    return "%s: %s" % (key, ", ".join(rights))


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
