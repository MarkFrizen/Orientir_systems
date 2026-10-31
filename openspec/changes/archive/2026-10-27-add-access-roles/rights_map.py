# -*- coding: utf-8 -*-
"""Общий модуль конвертации roles-matrix.json -> DSL role-compile.

Единый источник конвертации «символы матрицы -> DSL-права», который ИСПОЛЬЗУЮТ
ОБА скрипта пайплайна:
  * emit-role-json.py — генерация roles/Профиль_*.json;
  * check-matrix.py   — гейт def<->матрица (правило g) и def<->XML (правило h).

Никакой политики в emit-role-json.py не хардкодится: только таблицы конвертации
ниже + платформенное замыкание зависимостей прав, которое применяется ЗДЕСЬ,
чтобы defs совпадали с итоговым содержимым Rights.xml (с точностью до порядка
узлов). Порядок прав в строке def — канонический порядок платформы
(RIGHT_ORDER в role-compile.py), тот же, что пишет компилятор.

Таблица конвертации (design.md D2, dsl-reference.md — полномочный список прав
по типам, строки 10–29):
  Ч    -> Read       (Subsystem: View — единственное право, dsl-reference:26;
                      DataProcessor/Report: View — у них только Use/View, dsl-reference:24)
  П    -> View       (DataProcessor/Report: View)
  И    -> Insert, InteractiveInsert
  Изм  -> Update     (отдельного «интерактивного изменения» у платформы нет;
                      гейт редактирования — Edit, он приходит замыканием от
                      InteractiveInsert, см. ниже. Ячеек «Изм» без «И» в матрице
                      нет — проверено, поэтому D2-формула «Изм -> Edit, Update»
                      и «Изм -> Update + замыкание от И» дают идентичный результат.)
  В    -> InputByString
  Пров -> Document: Posting, InteractivePosting, InteractivePostingRegular
          BusinessProcess/Task: Update (spec, «Объекты вне матрицы» п.4)
  Use  -> Use        (DataProcessor/Report)
  Configuration.<имя> -> тождественно: ThinClient / WebClient / SaveUserData /
          Output (spec, «Объекты вне матрицы» п.7 «Права запуска клиента»;
          тип Configuration и его права перечислены в dsl-reference.md:12).

Замыкание зависимостей прав применяется ПОЛНОСТЬЮ алгоритмом самого компилятора
(close_rights_dependencies из role-compile.py; таблица RIGHT_DEPS —
role-compile.py:779–814, измерена на платформе; правило «Разрешение перебивает
запрет» — role-compile.py:891). Ключевые пары, объясняющие расхождение def-ов
со «старой» таблицей символов (finding IMPORTANT 3):
  * И:  InteractiveInsert -> Edit, Insert, Read, Update, View (role-compile.py:795),
        т.е. каждая ячейка с «И» дополнительно получает Edit и Update
        (Read/View уже есть от «Ч»/«П»); Insert -> Read (role-compile.py:785);
  * В:  InputByString -> Read, View (role-compile.py:784), т.е. каждый объект
        с «В» дополнительно получает View (для ячеек «Ч,В» без «П» — ровно
        расхождение «+View на В-объектах»);
  * Изм/Пров: Update -> Read (role-compile.py:808), Posting -> Read, Update
        (role-compile.py:802), InteractivePosting(Regular) -> Edit, Posting,
        Read, Update, View (role-compile.py:796–797) — для документов с «Пров»
        замыкание добавляет Edit;
  * Edit -> Read, Update, View (role-compile.py:781); View -> Read (:812);
  * DataProcessor/Report: View -> Use по типу (RIGHT_DEPS_BY_TYPE,
        role-compile.py:824–826, 830–832);
  * Configuration: у клиентских прав зависимостей нет; легаси-блок режимов окна
        (CONFIGURATION_LEGACY_DEPS, role-compile.py:835, 913) дописывается
        только для формата <= 2.18, у нас Rights version="2.20" (rank 220) —
        не применяется.
"""
import importlib.util
import os

HERE = os.path.dirname(os.path.abspath(__file__))
REPO_ROOT = os.path.abspath(os.path.join(HERE, "..", "..", ".."))
SRC_ROOT = os.path.join(REPO_ROOT, "src", "КурсоваяРабота")
ROLE_COMPILE_PY = os.path.join(
    REPO_ROOT, ".opencode", "skills", "role-compile", "scripts", "role-compile.py"
)


def _load_role_compile():
    """Динамический импорт role-compile.py (имя с дефисом — только importlib).

    Замыкание прав берётся ИЗ САМОГО компилятора, а не копируется: def-ы и
    Rights.xml не могут разойтись из-за рассинхрона таблиц.
    """
    spec = importlib.util.spec_from_file_location("role_compile_impl", ROLE_COMPILE_PY)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)  # __main__-гард у скрипта есть, main() не исполняется
    return module


rc = _load_role_compile()

# Ранг формата выгрузки (2.20 -> 220): влияет на легаси-замыкание Configuration.
FORMAT_RANK = rc.format_rank(rc.detect_format_version(SRC_ROOT))

# per-type-family symbol -> list of DSL rights (единственная «политика» конвертации)
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
PROCESS["Пров"] = ["Update"]  # Update-эквивалент на BusinessProcess./Task. (spec п.4)
DATAPROCESSOR = {
    "Ч": ["View"],  # у DataProcessor/Report есть только Use и View (dsl-reference:24)
    "П": ["View"],
    "Use": ["Use"],
}
SUBSYSTEM = {"Ч": ["View"]}  # единственное право подсистемы — View (dsl-reference:26)
CONSTANT = {"Ч": ["Read"], "П": ["View"], "Изм": ["Update"]}
REGISTER = {"Ч": ["Read"], "П": ["View"], "Изм": ["Update"]}

# Права запуска клиента (spec п.7): точный набор токенов для Configuration.*.
# dsl-reference.md:12 перечисляет все допустимые права Configuration; спека
# мандатирует ровно эти четыре всем шести профилям.
CONFIGURATION_TOKENS = ["ThinClient", "WebClient", "SaveUserData", "Output"]
CONFIGURATION = {token: [token] for token in CONFIGURATION_TOKENS}


class ConversionError(Exception):
    """Недопустимый символ/ключ при конвертации матрицы."""


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
    if obj_type == "Configuration":
        return CONFIGURATION
    if obj_type.endswith("Register"):
        return REGISTER
    return COMMON  # Catalog, ChartOfCharacteristicTypes и пр.


def base_rights(key, symbols):
    """Символы матрицы -> DSL-права БЕЗ замыкания (порядок таблицы, без дублей)."""
    obj_type = key.split(".", 1)[0]
    table = table_for(obj_type)
    rights = []
    for sym in symbols:
        if sym not in table:
            raise ConversionError(
                "symbol %r not defined for %s (key %s)" % (sym, obj_type, key)
            )
        for r in table[sym]:
            if r not in rights:
                rights.append(r)
    if not rights:
        raise ConversionError("empty rights for %s" % key)
    return rights


def closed_rights(key, symbols):
    """Символы матрицы -> итоговые DSL-права ПОСЛЕ платформенного замыкания.

    Результат побайтово равен набору прав, который role-compile запишет в
    Rights.xml для этой ячейки (тот же алгоритм close_rights_dependencies и
    тот же канонический порядок sort_rights_canonical), поэтому сгенерированные
    артефакты доказуемо воспроизводимы из матрицы.
    """
    dicts = [
        {"Name": r, "Value": "true", "Condition": None} for r in base_rights(key, symbols)
    ]
    closed, _added = rc.close_rights_dependencies(key, dicts, FORMAT_RANK)
    ordered = rc.sort_rights_canonical(key, closed)
    return [d["Name"] for d in ordered]


def rights_line(key, symbols):
    """Строка objects для role-compile DSL: "Ключ: Право1, Право2"."""
    return "%s: %s" % (key, ", ".join(closed_rights(key, symbols)))
