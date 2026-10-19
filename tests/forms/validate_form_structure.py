"""Структурная проверка Form.xml по правилам, подтверждённым платформой 1С.

Проверяет:
  * ConditionalAppearance лежит последним ребёнком внутри <Attributes>;
  * selection в правилах — имя поля формы (без Объект./Список.);
  * left в условиях — Объект.<поле> для карточек, Список.<поле> для журналов;
  * числа — xs:decimal, булевы — xs:boolean, перечисления — dcscor:DesignTimeValue;
  * <Events> стоит после <AutoCommandBar> и до <ChildItems>;
  * у каждого <Event> есть процедура в модуле формы;
  * у каждой команды есть обработчик, у каждой кнопки — существующая команда;
  * в ОткрытьФорму указано полное имя формы (Документ.X.Форма.Y);
  * нет двойного BOM.

Использование:
  python tests/forms/validate_form_structure.py [<Form.xml> ...]
  без аргументов — все формы src/КурсоваяРабота.
"""
import io
import os
import re
import sys
import xml.etree.ElementTree as ET

NS = "{http://v8.1c.ru/8.3/xcf/logform}"
SET = "{http://v8.1c.ru/8.1/data-composition-system/settings}"
COR = "{http://v8.1c.ru/8.1/data-composition-system/core}"
SRC = os.path.join("src", "КурсоваяРабота")
XSI = "{http://www.w3.org/2001/XMLSchema-instance}type"


def read_module(form_path):
    module = os.path.join(os.path.dirname(form_path), "Form", "Module.bsl")
    if not os.path.exists(module):
        return ""
    return io.open(module, encoding="utf-8-sig", errors="replace").read()


def check_rules(root, errors):
    attrs = [c for c in root if c.tag == NS + "Attributes"]
    is_list = False
    if attrs:
        for a in attrs[0]:
            if a.get("name") == "Список":
                is_list = True

    expected_prefix = "Список." if is_list else "Объект."

    for item in root.iter(SET + "item"):
        selection = item.find(SET + "selection")
        if selection is None:
            continue
        fields = [f.text or "" for f in selection.iter(SET + "field")]
        for f in fields:
            if f.startswith(("Объект.", "Список.")):
                errors.append("selection должен быть именем поля формы, а не путём: %s" % f)

        filt = item.find(SET + "filter")
        if filt is None:
            continue
        for comp in filt.iter(SET + "item"):
            left = comp.find(SET + "left")
            right = comp.find(SET + "right")
            if left is None:
                continue
            left_text = (left.text or "").strip()
            if left_text and not left_text.startswith(expected_prefix):
                errors.append("условие должно ссылаться на %s<поле>, а не %s" % (expected_prefix, left_text))

            if right is None:
                continue
            rtype = right.get(XSI, "")
            rtext = (right.text or "").strip()
            if re.match(r"^-?\d+(\.\d+)?$", rtext) and rtype != "xs:decimal":
                errors.append("числовой литерал %s должен быть xs:decimal, а не %s" % (rtext, rtype))
            if rtext in ("true", "false") and rtype != "xs:boolean":
                errors.append("булев литерал %s должен быть xs:boolean, а не %s" % (rtext, rtype))
            if rtext.startswith("Перечисление.") and rtype != "dcscor:DesignTimeValue":
                errors.append("перечисление %s должно быть dcscor:DesignTimeValue, а не %s" % (rtext, rtype))


def check(path):
    errors, warnings = [], []

    raw = open(path, "rb").read()
    if raw.startswith(b"\xef\xbb\xbf\xef\xbb\xbf"):
        errors.append("двойной BOM")
    elif not raw.startswith(b"\xef\xbb\xbf"):
        warnings.append("нет BOM")

    try:
        root = ET.parse(path).getroot()
    except ET.ParseError as ex:
        return ["XML не разбирается: %s" % ex], warnings

    children = list(root)
    tags = [c.tag.replace(NS, "") for c in children]

    ca_nodes = list(root.iter(NS + "ConditionalAppearance"))
    if ca_nodes:
        ca = ca_nodes[0]
        parent_tag = None
        for parent in root.iter():
            if ca in list(parent):
                parent_tag = parent.tag.replace(NS, "")
        if parent_tag != "Attributes":
            errors.append("ConditionalAppearance должен быть внутри <Attributes>, а он в <%s>" % parent_tag)
        else:
            attrs = [c for c in root if c.tag == NS + "Attributes"][0]
            if list(attrs)[-1] is not ca:
                errors.append("ConditionalAppearance должен быть последним ребёнком <Attributes>")
        check_rules(root, errors)

    if "Events" in tags:
        i_events = tags.index("Events")
        i_acb = tags.index("AutoCommandBar") if "AutoCommandBar" in tags else -1
        i_child = tags.index("ChildItems") if "ChildItems" in tags else len(tags)
        if i_acb >= 0 and i_events < i_acb:
            errors.append("<Events> должен идти после <AutoCommandBar>")
        if i_events > i_child:
            errors.append("<Events> должен идти до <ChildItems>")

    module = read_module(path)
    if module:
        for ev in root.iter(NS + "Event"):
            handler = (ev.text or "").strip()
            if handler and ("Процедура %s(" % handler) not in module and ("Функция %s(" % handler) not in module:
                errors.append("нет обработчика события %s: %s" % (ev.get("name"), handler))

        for m in re.finditer(r'ОткрытьФорму\("([^"]+)"', module):
            name = m.group(1)
            parts = name.split(".")
            if len(parts) == 3:
                errors.append("в ОткрытьФорму неполное имя формы: %s" % name)
            elif len(parts) >= 4 and parts[2] != "Форма":
                errors.append("в ОткрытьФорму нет сегмента .Форма.: %s" % name)

    commands = {}
    for cmd in root.iter(NS + "Command"):
        name = cmd.get("name")
        action = cmd.findtext(NS + "Action")
        commands[name] = action
        if action and module and ("Процедура %s(" % action) not in module:
            errors.append("нет обработчика команды %s: %s" % (name, action))

    for btn in root.iter(NS + "Button"):
        ref = btn.findtext(NS + "CommandName") or ""
        if ref.startswith("Form.Command."):
            cmd_name = ref[len("Form.Command."):]
            if cmd_name not in commands:
                errors.append("кнопка %s ссылается на несуществующую команду %s" % (btn.get("name"), cmd_name))

    return errors, warnings


def main(argv):
    if len(argv) > 1:
        files = argv[1:]
    else:
        files = []
        for dirpath, _, names in os.walk(SRC):
            if "Form.xml" in names:
                files.append(os.path.join(dirpath, "Form.xml"))

    total_errors = 0
    for path in sorted(files):
        errors, warnings = check(path)
        if errors or warnings:
            print(path.encode("ascii", "backslashreplace").decode())
            for e in errors:
                print("  ERROR:", e)
            for w in warnings:
                print("  warn:", w)
        total_errors += len(errors)

    print("\nforms:", len(files), "errors:", total_errors)
    return 1 if total_errors else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
