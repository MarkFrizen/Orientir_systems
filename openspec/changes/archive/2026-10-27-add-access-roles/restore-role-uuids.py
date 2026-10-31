# -*- coding: utf-8 -*-
"""Сохранение UUID ролей при перекомпиляции (finding IMPORTANT 7).

role-compile.py генерирует новый <Role uuid="..."> при КАЖДОЙ компиляции
(role-compile.py:1745, 1759). UUID роли — стабильный идентификатор объекта
метаданных: он меняется в базе и в ссылках, поэтому регенерация не должна его
переписывать. Скрипт встраивается в шаг регенерации (regenerate-roles.py):

  1. ДО компиляции:  python restore-role-uuids.py snapshot
     — читает текущие <Role uuid="..."> из src/КурсоваяРабота/Roles/Профиль_*.xml
       и сохраняет их в role-uuids.snapshot.json (рядом со скриптом);
  2. ПОСЛЕ компиляции: python restore-role-uuids.py restore
     — возвращает старые значения атрибута uuid, печатая preserved/changed
       по каждой роли.

Роль Администратор не компилируется пайплайном и не трогается (snapshot
охватывает только Профиль_*). Файлы правятся побайтовой заменой атрибута —
BOM, CRLF и остальное содержимое не затрагиваются.
"""
import io
import json
import os
import re
import sys

sys.stdout.reconfigure(encoding="utf-8")

HERE = os.path.dirname(os.path.abspath(__file__))
REPO_ROOT = os.path.abspath(os.path.join(HERE, "..", "..", ".."))
ROLES_DIR = os.path.join(REPO_ROOT, "src", "КурсоваяРабота", "Roles")
DEFAULT_SNAPSHOT = os.path.join(HERE, "role-uuids.snapshot.json")
ROLE_GLOB = re.compile(r"^Профиль_.*\.xml$")
UUID_ATTR = re.compile(rb'(<Role uuid=")([0-9a-fA-F-]+)(">)')

USAGE = """restore-role-uuids.py — сохранение UUID ролей при перекомпиляции.

Запуск:
    python restore-role-uuids.py snapshot [--file <путь>]  — снять слепок UUID (ДО role-compile)
    python restore-role-uuids.py restore  [--file <путь>]  — вернуть UUID из слепка (ПОСЛЕ role-compile)
    python restore-role-uuids.py --help

Слепок по умолчанию: role-uuids.snapshot.json рядом со скриптом.
Код возврата: 0 — успех, 1 — ошибка (нет слепка/файлов роли), 2 — ошибка аргументов.
"""


def role_xml_paths():
    if not os.path.isdir(ROLES_DIR):
        return []
    return [
        os.path.join(ROLES_DIR, f)
        for f in sorted(os.listdir(ROLES_DIR))
        if ROLE_GLOB.match(f) and os.path.isfile(os.path.join(ROLES_DIR, f))
    ]


def read_uuid(path):
    data = open(path, "rb").read()
    m = UUID_ATTR.search(data)
    return m.group(2).decode("ascii") if m else None


def cmd_snapshot(snapshot_path):
    paths = role_xml_paths()
    if not paths:
        sys.stderr.write("FAIL: no Профиль_*.xml role files under %s\n" % ROLES_DIR)
        return 1
    snapshot = {}
    for path in paths:
        role = os.path.basename(path)[: -len(".xml")]
        uuid = read_uuid(path)
        if uuid is None:
            sys.stderr.write("FAIL: %s has no <Role uuid=...> attribute\n" % path)
            return 1
        snapshot[role] = uuid
        print("snapshot %s: %s" % (role, uuid))
    with io.open(snapshot_path, "w", encoding="utf-8", newline="\n") as f:
        json.dump(snapshot, f, ensure_ascii=False, indent=2, sort_keys=True)
        f.write("\n")
    print("snapshot written: %s (%d roles)" % (snapshot_path, len(snapshot)))
    return 0


def cmd_restore(snapshot_path):
    if not os.path.isfile(snapshot_path):
        sys.stderr.write(
            "FAIL: snapshot not found: %s — run `python restore-role-uuids.py "
            "snapshot` BEFORE role-compile\n" % snapshot_path
        )
        return 1
    with io.open(snapshot_path, encoding="utf-8") as f:
        snapshot = json.load(f)
    rc = 0
    for role, old_uuid in sorted(snapshot.items()):
        path = os.path.join(ROLES_DIR, role + ".xml")
        if not os.path.isfile(path):
            sys.stderr.write("FAIL: role file missing: %s\n" % path)
            rc = 1
            continue
        data = open(path, "rb").read()
        m = UUID_ATTR.search(data)
        if m is None:
            sys.stderr.write("FAIL: %s has no <Role uuid=...> attribute\n" % path)
            rc = 1
            continue
        current = m.group(2).decode("ascii")
        if current == old_uuid:
            print("preserved  %s: %s" % (role, current))
            continue
        fixed = UUID_ATTR.sub(
            lambda mm: mm.group(1) + old_uuid.encode("ascii") + mm.group(3), data, count=1
        )
        open(path, "wb").write(fixed)
        print("changed->restored  %s: %s -> %s" % (role, current, old_uuid))
    return rc


def main(argv):
    if not argv or argv[0] in ("-h", "--help", "help"):
        print(USAGE)
        return 0 if argv else 2
    cmd = argv[0]
    snapshot_path = DEFAULT_SNAPSHOT
    rest = argv[1:]
    if "--file" in rest:
        idx = rest.index("--file")
        if idx + 1 >= len(rest):
            sys.stderr.write("USAGE ERROR: --file requires a value\n\n%s" % USAGE)
            return 2
        snapshot_path = rest[idx + 1]
        rest = rest[:idx] + rest[idx + 2:]
    if rest:
        sys.stderr.write("USAGE ERROR: unexpected argument(s) %r\n\n%s" % (rest, USAGE))
        return 2
    if cmd == "snapshot":
        return cmd_snapshot(snapshot_path)
    if cmd == "restore":
        return cmd_restore(snapshot_path)
    sys.stderr.write("USAGE ERROR: unknown command %r\n\n%s" % (cmd, USAGE))
    return 2


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
