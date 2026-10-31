# -*- coding: utf-8 -*-
"""Проверка roles-matrix.json — единого источника прав (design.md D3).

Таблицы прав ЧИТАЮТСЯ ИЗ СПЕКИ at runtime (specs/access-roles/spec.md,
разделы «Права на справочники», «Права на документы», «Права на регистры») —
никаких захардкоженных ожиданий: если spec.md изменён, проверяется новая матрица.

Правила:
  (a) каждый ключ объекта "<Тип>.<Имя>" имеет исходник
      src/КурсоваяРабота/<Тип plural>/<Имя>.xml; список прав непустой,
      без дублей символов, символы только из легенды ТЗ (Ч, П, И, Изм, В).
      Особый случай — ключи Configuration.*: единственный источник —
      Configuration.xml (имя обязано совпасть с именем конфигурации), а вместо
      символов ТЗ несут только клиентские токены запуска (ThinClient, WebClient,
      SaveUserData, Output — spec «Объекты вне матрицы» п.7, dsl-reference:12);
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
      документ проводимый и у профиля есть «Изм»;
      Профиль_Гид не содержит «Пров» нигде.
      Правило (b) при этом усиливается: ожидаемый список прав ячейки спеки =
      символы ячейки + «Пров», если документ проводимый и в ячейке есть «Изм».
      Набор проводимых документов ПО УМОЛЧАНИЮ ВЫВОДИТСЯ из
      src/КурсоваяРабота/Documents/*.xml (<Posting>Allow</Posting>);
      --post переопределяет его, но каждый токен валидируется (см. USAGE).
Правило (f): политика «Объекты вне матрицы ТЗ» (spec.md, пункты 1–7) и
сопоставления «Права на ролевые подсистемы» воспроизведены точно
(OFF_MATRIX_POLICY): права по профилям совпадают, незадействованному профилю
ключ запрещён, каждый объект политики присутствует хотя бы в одном профиле
(покрытие); НастройкиИнтеграций/ОбменСФайлами и подсистема АдминистраторИС
со всем деревом вложенных подсистем запрещены везде;
Профиль_Аудитор не содержит ключей BusinessProcess.*/Task.*; символ «Use»
допустим только у ключей DataProcessor.*; Configuration.<имя> присутствует
во всех шести профилях ровно с токенами запуска клиента (п.7).
Прочие дополнительные ключи объектов разрешены — они проверяются правилами
(a) и (e).
Правило (g): def<->матрица — сгенерированные roles/Профиль_*.json совпадают
 с конверсией матрицы через общий модуль rights_map.py (тот же модуль использует
 emit-role-json.py — политика конвертации существует в одном экземпляре);
 для каждого ключа матрицы ожидаемые DSL-права == права в def-е.
Правило (h): def<->XML — для каждой роли наборы прав в def-е и в
 src/КурсоваяРабота/Roles/Профиль_*/Ext/Rights.xml совпадают в обе стороны
 (def ⊆ XML и XML ⊆ def): замыкание зависимостей прав применяется заранее в
 rights_map.closed_rights, поэтому сгенерированные артефакты доказуемо
 воспроизводимы из матрицы (с точностью до порядка узлов).

Запуск (канонический — без аргументов, из каталога change):
    python check-matrix.py
Полная справка: python check-matrix.py --help
Код возврата: 0 — нарушений нет, 1 — есть нарушения / файлы не найдены,
2 — ошибка аргументов командной строки.
"""
import io
import json
import os
import re
import sys
import xml.etree.ElementTree as ET

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, SCRIPT_DIR)
import rights_map  # noqa: E402  — общий модуль конвертации (emit + checker)

REPO_ROOT = os.path.abspath(os.path.join(SCRIPT_DIR, "..", "..", ".."))
SRC_ROOT = os.path.join(REPO_ROOT, "src", "КурсоваяРабота")
DEFAULT_MATRIX = os.path.join(SCRIPT_DIR, "roles-matrix.json")
SPEC_PATH = os.path.join(SCRIPT_DIR, "specs", "access-roles", "spec.md")
ROLES_DEF_DIR = os.path.join(SCRIPT_DIR, "roles")
XML_ROLES_DIR = os.path.join(SRC_ROOT, "Roles")

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

# Configuration.* (spec «Объекты вне матрицы ТЗ» п.7 — права запуска клиента):
# несут ТОЛЬКО клиентские токены из rights_map.CONFIGURATION_TOKENS, символы ТЗ
# у них недопустимы; у прочих ключей клиентские токены недопустимы (не входят в
# MATRIX_SYMBOLS и падают на проверке «invalid symbol»).
CONFIGURATION_TYPE = "Configuration"
CONFIGURATION_NAME = "КурсоваяРабота"
CONFIGURATION_KEY = "%s.%s" % (CONFIGURATION_TYPE, CONFIGURATION_NAME)
CONFIGURATION_XML = os.path.join(SRC_ROOT, "Configuration.xml")
CONFIGURATION_TOKENS = list(rights_map.CONFIGURATION_TOKENS)

# Профиль, которому «Пров» запрещён всегда (только чтение/создание, без правки).
NO_POSTING_PROFILE = "Профиль_Гид"

ABSENT = "-"

# ---------------------------------------------------------------------------
# Правило (f): политика «Объекты вне матрицы ТЗ» (spec.md, одноимённое
# требование, пункты 1–7) и «Права на ролевые подсистемы» (сопоставления после
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
    # п.7: права запуска клиента — Configuration.<имя конфигурации> ровно с этим
    # набором токенов всем шести профилям. Без ThinClient/WebClient/
    # SaveUserData/Output платформа отказывает в сеансе пользователю, которому
    # назначена только профиль-роль (spec «Объекты вне матрицы» п.7).
    CONFIGURATION_KEY: {p: list(CONFIGURATION_TOKENS) for p in PROFILES},
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
    # бизнес-подсистем. Вложенные подсистемы — отдельные объекты метаданных
    # (Subsystems/<Родитель>/Subsystems/<Ребёнок>.xml), поэтому на каждую
    # нужен собственный ключ (spec.md: View на подсистему и все её вложенные).
    # Заполняется циклом ниже из _SUBSYSTEM_GRANTS.
}

# Родительская подсистема -> (профиль-владелец, вложенные подсистемы).
# Список детей сверен с диском: src/КурсоваяРабота/Subsystems/*/Subsystems/*.xml.
# Вложенные подсистемы — отдельные объекты метаданных с КВАЛИФИЦИРОВАННЫМ
# платформенным именем «Subsystem.<Родитель>.Subsystem.<Ребёнок>» (так их
# знает ConfigDumpInfo.xml и загружает LoadConfigFromFiles; плоское имя
# «Subsystem.<Ребёнок>» платформа отбрасывает как «Неизвестный объект
# метаданных» — task-9-report.md). Родители остаются «Subsystem.<Имя>».
_SUBSYSTEM_GRANTS = {
    "ОператорСопровождения": (_P_OP, ["ЗаказыПоставщикам", "ЗапросыТуристов", "МоиЗаявки", "Подтверждения"]),
    "КоординаторЛогистики": (_P_KO, ["Корректировки", "МаршрутныеЛисты"]),
    "ГидНаМаршруте": (_P_GID, ["МоиОбращения", "МойМаршрут", "НоваяЗаявка", "НовыйИнцидент"]),
    "МенеджерПоПретензиям": (_P_ME, ["АктыКомпенсаций", "Инциденты", "Претензии"]),
    "РуководительНаправления": (_P_RUK, ["KPIОтчеты", "Согласования", "Эскалации"]),
}
for _parent, (_owner, _children) in _SUBSYSTEM_GRANTS.items():
    OFF_MATRIX_POLICY["Subsystem." + _parent] = {_owner: ["Ч"], _P_AU: ["Ч"]}
    for _child in _children:
        _qual = "Subsystem.%s.Subsystem.%s" % (_parent, _child)
        OFF_MATRIX_POLICY[_qual] = {_owner: ["Ч"], _P_AU: ["Ч"]}

# Ключи, запрещённые во ВСЕХ шести профилях (права имеет только роль
# Администратор: spec сценарии «Настройки интеграций закрыты для профилей»,
# п.5 НастройкиИнтеграций, п.6 ОбменСФайлами, подсистема АдминистраторИС
# вместе со всем её деревом вложенных подсистем). Дети АдминистраторИС
# перечислены в квалифицированной платформенной форме; плоские варианты
# оставлены как защита в глубину — правило (a) их всё равно бы отвергло
# (find_metadata_xml плоские имена детей не разыскивает).
FORBIDDEN_EVERYWHERE = [
    "InformationRegister.НастройкиИнтеграций",
    "DataProcessor.ОбменСФайлами",
    "Subsystem.АдминистраторИС",
    "Subsystem.АдминистраторИС.Subsystem.СправочникиНСИ",
    "Subsystem.АдминистраторИС.Subsystem.НастройкиИнтеграций",
    "Subsystem.СправочникиНСИ",
    "Subsystem.НастройкиИнтеграций",
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

USAGE = """check-matrix.py — проверка roles-matrix.json и сгенерированных артефактов.

Канонический запуск (без аргументов, из каталога change):
    python check-matrix.py

Формы запуска:
    python check-matrix.py                      все проверки; набор проводимых
                                                документов ВЫВОДИТСЯ из
                                                src/КурсоваяРабота/Documents/*.xml
                                                (<Posting>Allow</Posting>)
    python check-matrix.py --post Имя1,Имя2     переопределить набор проводимых
                                                документов; допустимы ТОЛЬКО голые
                                                имена проводимых документов из
                                                Documents/ (без префикса
                                                "Document.") — неизвестное имя или
                                                токен с префиксом -> выход с кодом 2
    python check-matrix.py путь/к/roles-matrix.json
                                                альтернативный путь к матрице
    python check-matrix.py --help               эта справка

Коды возврата: 0 — нарушений нет; 1 — нарушения/файлы не найдены;
2 — ошибка аргументов командной строки.
"""


class UsageError(Exception):
    """Ошибка аргументов командной строки (выход с кодом 2)."""


def find_metadata_xml(folder, name):
    """Путь к исходнику метаданных или None.

    Прямой путь: <SRC_ROOT>/<folder>/<name>.xml. Вложенные подсистемы —
    отдельные объекты метаданных: платформенное квалифицированное имя
    «Subsystem.<Родитель>.Subsystem.<Ребёнок>» (ConfigDumpInfo.xml) даёт
    name = "<Родитель>.Subsystem.<Ребёнок>", а исходник лежит в
    <SRC_ROOT>/Subsystems/<Родитель>/Subsystems/<Ребёнок>.xml — спускаемся
    по цепочке произвольной глубины. Плоское имя ребёнка НЕ разыскивается
    по всем родителям: платформа его не знает («Неизвестный объект
    метаданных», task-9-report.md), поэтому ключ обязан быть квалифицированным.
    """
    direct = os.path.join(SRC_ROOT, folder, name + ".xml")
    if os.path.isfile(direct):
        return direct
    if folder == "Subsystems" and ".Subsystem." in name:
        segments = name.split(".Subsystem.")
        path = os.path.join(SRC_ROOT, folder, segments[0] + ".xml")
        for seg in segments[1:]:
            path = os.path.join(os.path.splitext(path)[0], "Subsystems", seg + ".xml")
        if os.path.isfile(path):
            return path
    return None


def actual_configuration_name():
    """Имя корневого объекта конфигурации из Configuration.xml или None."""
    if not os.path.isfile(CONFIGURATION_XML):
        return None
    with io.open(CONFIGURATION_XML, encoding="utf-8-sig") as f:
        head = f.read(8000)
    m = re.search(r"<Name>([^<]+)</Name>", head)
    return m.group(1) if m else None


def derive_posting_docs():
    """Проводимые документы: Documents/*.xml c <Posting>Allow</Posting> (design D5)."""
    docs_dir = os.path.join(SRC_ROOT, "Documents")
    posting = []
    if not os.path.isdir(docs_dir):
        return posting
    for fname in sorted(os.listdir(docs_dir)):
        if not fname.endswith(".xml"):
            continue
        with io.open(os.path.join(docs_dir, fname), encoding="utf-8-sig") as f:
            text = f.read()
        if "<Posting>Allow</Posting>" in text:
            posting.append(fname[: -len(".xml")])
    return posting


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


def _parse_def_file(def_path, pname, errors):
    """roles/<Профиль>.json -> {key: [rights]} или None."""
    try:
        with io.open(def_path, encoding="utf-8") as f:
            doc = json.load(f)
    except (OSError, ValueError) as exc:
        errors.append("%s: cannot read def %s: %s" % (pname, def_path, exc))
        return None
    entries = {}
    for item in doc.get("objects", []):
        if not isinstance(item, str):
            errors.append(
                "%s: def %s: object-form entry %r is not supported by the pipeline "
                "(emit-role-json.py writes shorthand strings only)" % (pname, def_path, item)
            )
            continue
        key, sep, rest = item.partition(":")
        if not sep:
            errors.append("%s: def %s: malformed object string %r" % (pname, def_path, item))
            continue
        rights = [r.strip() for r in rest.split(",") if r.strip()]
        key = key.strip()
        if key in entries:
            errors.append("%s: def %s: duplicate object %r" % (pname, def_path, key))
        entries[key] = rights
    return entries


def _parse_rights_xml(rights_path, pname, errors):
    """Roles/<Профиль>/Ext/Rights.xml -> {object name: set(rights со value=true)}."""
    ns = "{http://v8.1c.ru/8.2/roles}"
    try:
        root = ET.parse(rights_path).getroot()
    except (OSError, ET.ParseError) as exc:
        errors.append("%s: cannot parse %s: %s" % (pname, rights_path, exc))
        return None
    xml_map = {}
    for obj in root.findall(ns + "object"):
        name = (obj.findtext(ns + "name") or "").strip()
        rights = set()
        for rt in obj.findall(ns + "right"):
            rname = (rt.findtext(ns + "name") or "").strip()
            rvalue = (rt.findtext(ns + "value") or "").strip()
            if rvalue != "true":
                errors.append(
                    "%s: %s: object %r carries a deny entry %r=%r — the pipeline "
                    "never emits denies (dependency closure flips them anyway)"
                    % (pname, os.path.basename(rights_path), name, rname, rvalue)
                )
                continue
            rights.add(rname)
        if name in xml_map:
            errors.append("%s: %s: duplicate object %r" % (pname, rights_path, name))
        xml_map[name] = rights
    return xml_map


def check_generated_artifacts(profiles, errors):
    """Правила (g) и (h): def<->матрица и def<->XML (наборы прав, обе стороны).

    (g) expected DSL-права каждого ключа матрицы считаются общим модулем
        rights_map (его же использует emit-role-json.py) и сравниваются с
        roles/Профиль_*.json;
    (h) тот же набор сравнивается с Roles/Профиль_*/Ext/Rights.xml:
        def ⊆ XML и XML ⊆ def — сгенерированные артефакты доказуемо
        воспроизводимы из матрицы (rights_map предварительно применяет
        платформенное замыкание зависимостей прав).
    """
    for pname in PROFILES:
        prof = profiles.get(pname)
        objects = prof.get("objects") if isinstance(prof, dict) else None
        if not isinstance(objects, dict):
            continue

        # expected: матрица -> DSL через общий модуль конвертации
        expected = {}
        for key, syms in objects.items():
            if not isinstance(syms, list):
                continue
            try:
                expected[key] = rights_map.closed_rights(key, syms)
            except rights_map.ConversionError as exc:
                errors.append("%s: matrix->DSL conversion failed for %r: %s" % (pname, key, exc))

        # (g) def-файл
        def_path = os.path.join(ROLES_DEF_DIR, pname + ".json")
        def_entries = None
        if not os.path.isfile(def_path):
            errors.append(
                "%s: generated def not found: %s (run emit-role-json.py)" % (pname, def_path)
            )
        else:
            def_entries = _parse_def_file(def_path, pname, errors)
        if def_entries is not None:
            for key in sorted(set(expected) | set(def_entries)):
                exp = expected.get(key)
                act = def_entries.get(key)
                if exp is None:
                    errors.append(
                        "%s: def has object %r that is absent from the matrix — "
                        "def is not regenerable from roles-matrix.json" % (pname, key)
                    )
                elif act is None:
                    errors.append(
                        "%s: def lacks matrix key %r (expected rights %r) — "
                        "run emit-role-json.py" % (pname, key, exp)
                    )
                elif set(act) != set(exp):
                    errors.append(
                        "%s: def rights for %r %r != matrix conversion %r "
                        "(missing: %r, extra: %r)"
                        % (
                            pname, key, sorted(act), sorted(exp),
                            sorted(set(exp) - set(act)), sorted(set(act) - set(exp)),
                        )
                    )

        # (h) Rights.xml
        rights_path = os.path.join(XML_ROLES_DIR, pname, "Ext", "Rights.xml")
        if not os.path.isfile(rights_path):
            errors.append(
                "%s: compiled rights not found: %s (run role-compile)" % (pname, rights_path)
            )
            continue
        xml_map = _parse_rights_xml(rights_path, pname, errors)
        if xml_map is None:
            continue
        reference = def_entries if def_entries is not None else {k: list(v) for k, v in expected.items()}
        for key in sorted(set(reference) | set(xml_map)):
            exp = set(reference.get(key, []))
            act = xml_map.get(key)
            if act is None:
                errors.append(
                    "%s: Rights.xml lacks object %r present in def (%r) — recompile "
                    "the role from the regenerated def" % (pname, key, sorted(exp))
                )
            elif key not in reference:
                errors.append(
                    "%s: Rights.xml has object %r absent from def (%r) — XML is not "
                    "regenerable from the matrix" % (pname, key, sorted(act))
                )
            elif act != exp:
                errors.append(
                    "%s: Rights.xml rights for %r %r != def %r (missing in XML: %r, "
                    "extra in XML: %r)"
                    % (
                        pname, key, sorted(act), sorted(exp),
                        sorted(exp - act), sorted(act - exp),
                    )
                )


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
            if not isinstance(rights, list) or not rights:
                errors.append("%s: rights for %r must be a non-empty list" % (pname, key))
                continue
            if mtype == CONFIGURATION_TYPE:
                # Configuration.*: источник — Configuration.xml, имя обязано
                # совпасть с именем корневого объекта; права — только клиентские
                # токены запуска (spec п.7), символы ТЗ недопустимы.
                cfg_name = actual_configuration_name()
                if cfg_name is None:
                    errors.append(
                        "%s: Configuration.xml not found at %s" % (pname, CONFIGURATION_XML)
                    )
                elif mname != cfg_name:
                    errors.append(
                        "%s: key %r does not match the configuration root name %r "
                        "(expected key %r)"
                        % (pname, key, cfg_name, "%s.%s" % (CONFIGURATION_TYPE, cfg_name))
                    )
                for sym in rights:
                    if sym not in CONFIGURATION_TOKENS:
                        errors.append(
                            "%s: %r token %r invalid — Configuration.* keys carry only "
                            "the client-level launch tokens %r (spec п.7, "
                            "dsl-reference.md:12)" % (pname, key, sym, CONFIGURATION_TOKENS)
                        )
                if len(set(rights)) != len(rights):
                    errors.append("%s: %r has duplicate tokens: %r" % (pname, key, rights))
                continue
            folder = TYPE_TO_FOLDER.get(mtype)
            if folder is None:
                errors.append("%s: unknown metadata type %r in key %r" % (pname, mtype, key))
                continue
            xml = find_metadata_xml(folder, mname)
            if xml is None:
                errors.append(
                    "%s: metadata file not found for key %r (expected %s%s)"
                    % (
                        pname,
                        key,
                        os.path.join(SRC_ROOT, folder, mname + ".xml"),
                        "; nested subsystems must use the qualified platform form "
                        "Subsystem.<Родитель>.Subsystem.<Ребёнок> (flat child names "
                        "are unknown to the platform)"
                        if folder == "Subsystems"
                        else "",
                    )
                )
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

    # (f) политика объектов вне матрицы ТЗ (пункты 1–7) и ролевые подсистемы:
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

    # (g)+(h) сгенерированные артефакты: def<->матрица, def<->XML
    check_generated_artifacts(profiles, errors)
    return errors


def parse_args(argv):
    """argv -> (matrix_path, posting_docs, posting_source, want_help).

    Ошибки аргументов — UsageError (main выходит с кодом 2 и печатает USAGE).
    """
    derived = derive_posting_docs()
    posting = list(derived)
    posting_source = "derived from Documents/*.xml (<Posting>Allow</Posting>)"
    positional = []
    i = 0
    while i < len(argv):
        arg = argv[i]
        if arg in ("-h", "--help", "help"):
            return None, None, None, True
        if arg == "--post":
            if i + 1 >= len(argv):
                raise UsageError("--post requires a comma-separated value")
            raw = argv[i + 1]
            i += 2
        elif arg.startswith("--post="):
            raw = arg[len("--post="):]
            i += 1
        elif arg.startswith("-"):
            raise UsageError("unknown option %r" % arg)
        else:
            positional.append(arg)
            i += 1
            continue
        tokens = [p.strip() for p in raw.split(",") if p.strip()]
        if not tokens:
            raise UsageError("--post value is empty")
        for tok in tokens:
            if "." in tok:
                raise UsageError(
                    "--post token %r looks prefixed (e.g. 'Document.%s'): pass bare "
                    "document names only" % (tok, tok)
                )
            if tok not in derived:
                raise UsageError(
                    "--post token %r is unknown or not posting-enabled; derived set "
                    "(<Posting>Allow</Posting>): %s" % (tok, ", ".join(derived) or "<empty>")
                )
        posting = tokens
        posting_source = "--post override"
    if len(positional) > 1:
        raise UsageError(
            "expected at most one positional argument (path to roles-matrix.json), "
            "got %d: %r" % (len(positional), positional)
        )
    matrix_path = positional[0] if positional else DEFAULT_MATRIX
    return matrix_path, posting, posting_source, False


def main():
    out = io.open(sys.stdout.fileno(), "w", encoding="utf-8", closefd=False)
    try:
        matrix_path, posting, posting_source, want_help = parse_args(sys.argv[1:])
    except UsageError as exc:
        sys.stderr.write("USAGE ERROR: %s\n\n%s" % (exc, USAGE))
        sys.exit(2)
    if want_help:
        out.write(USAGE)
        out.flush()
        sys.exit(0)
    errors = check(matrix_path, posting_docs=posting)
    if errors:
        out.write("FAIL: %d violation(s)\n" % len(errors))
        for e in errors:
            out.write("  - %s\n" % e)
        out.write(
            "canonical invocation: python check-matrix.py   (from %s)\n" % SCRIPT_DIR
        )
        out.flush()
        sys.exit(1)
    with io.open(matrix_path, encoding="utf-8") as f:
        keys = sum(len(p.get("objects", {})) for p in json.load(f)["profiles"].values())
    out.write(
        "OK: %d spec rows x 6 profiles parsed from spec.md and verified "
        "(%d object keys total, metadata files exist, %d posting docs %s); "
        "defs match the matrix conversion and Rights.xml matches defs "
        "(rules g/h via rights_map)\n"
        % (len(load_spec_tables(SPEC_PATH)[0]), keys, len(posting), posting_source)
    )
    out.flush()
    sys.exit(0)


if __name__ == "__main__":
    main()
