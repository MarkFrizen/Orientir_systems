# -*- coding: utf-8 -*-
"""Шаг регенерации пайплайна ролей (design.md D3): матрица -> defs -> role-compile.

Порядок (всё скриптовано, воспроизводимо, без ручных правок Rights.xml):
  1. python restore-role-uuids.py snapshot — слепок UUID существующих ролей
     (role-compile каждый раз генерирует новый UUID, finding IMPORTANT 7);
  2. python emit-role-json.py — roles-matrix.json -> roles/Профиль_*.json
     (конвертация и замыкание прав — из общего модуля rights_map.py);
  3. role-compile x6 — Roles/Профиль_*.xml + Roles/Профиль_*/Ext/Rights.xml,
     регистрация <Role> в Configuration.xml (уже зарегистрированы — no-op);
  4. python restore-role-uuids.py restore — вернуть прежние UUID, печать
     preserved/changed по каждой роли;
  5. python check-matrix.py — каноническая проверка (гейты def<->матрица и
     def<->XML входят в неё).

Запуск:  python regenerate-roles.py [--skip-check]
Код возврата: 0 — успех; ненулевой код первого же упавшего шага — иначе.
"""
import os
import subprocess
import sys

sys.stdout.reconfigure(encoding="utf-8")

HERE = os.path.dirname(os.path.abspath(__file__))
REPO_ROOT = os.path.abspath(os.path.join(HERE, "..", "..", ".."))
SRC_ROOT = os.path.join(REPO_ROOT, "src", "КурсоваяРабота")
ROLE_COMPILE = os.path.join(
    REPO_ROOT, ".opencode", "skills", "role-compile", "scripts", "role-compile.py"
)
PROFILES = [
    "Профиль_Оператор",
    "Профиль_Координатор",
    "Профиль_Гид",
    "Профиль_МенеджерПретензий",
    "Профиль_Руководитель",
    "Профиль_Аудитор",
]

ENV = dict(os.environ, PYTHONIOENCODING="utf-8")


def run(argv, label):
    print("== %s\n   %s" % (label, " ".join(argv)))
    result = subprocess.run(argv, cwd=REPO_ROOT, env=ENV)
    if result.returncode != 0:
        print("FAILED step %r with exit code %d" % (label, result.returncode))
    return result.returncode


def main(argv):
    skip_check = "--skip-check" in argv
    for arg in argv:
        if arg != "--skip-check":
            sys.stderr.write("USAGE ERROR: unexpected argument %r\n" % arg)
            return 2
    py = sys.executable

    steps = [
        ([py, os.path.join(HERE, "restore-role-uuids.py"), "snapshot"], "snapshot role UUIDs"),
        ([py, os.path.join(HERE, "emit-role-json.py")], "emit defs from roles-matrix.json"),
    ]
    for profile in PROFILES:
        steps.append(
            (
                [py, ROLE_COMPILE,
                 "-JsonPath", os.path.join(HERE, "roles", profile + ".json"),
                 "-OutputDir", SRC_ROOT],
                "role-compile %s" % profile,
            )
        )
    steps.append(
        ([py, os.path.join(HERE, "restore-role-uuids.py"), "restore"], "restore role UUIDs")
    )
    if not skip_check:
        steps.append(([py, os.path.join(HERE, "check-matrix.py")], "check-matrix (canonical bare run)"))

    for argv_step, label in steps:
        rc = run(argv_step, label)
        if rc != 0:
            return rc
    print("regenerate-roles: ALL STEPS OK")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
