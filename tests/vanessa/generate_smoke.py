# -*- coding: utf-8 -*-
"""Генерирует дымовые feature-сценарии Vanessa-ADD и профиль запуска VBParams."""

import json
import os
import re

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
CFG = os.path.join(ROOT, 'src', 'КурсоваяРабота')

# Кортеж: каталог исходников, вид метаданных, вид навигационной ссылки, заголовок сценария.
# У справочников и документов открывается список (e1cib/list), у обработок — форма
# (e1cib/app): списка у обработки нет, и ссылка list для неё не разрешается.
KINDS = [
    ('Catalogs', 'Справочник', 'list', 'Открытие списка'),
    ('Documents', 'Документ', 'list', 'Открытие списка'),
    ('InformationRegisters', 'РегистрСведений', 'list', 'Открытие списка'),
    ('AccumulationRegisters', 'РегистрНакопления', 'list', 'Открытие списка'),
    ('BusinessProcesses', 'БизнесПроцесс', 'list', 'Открытие списка'),
    ('Tasks', 'Задача', 'list', 'Открытие списка'),
    ('ChartsOfCharacteristicTypes', 'ПланВидовХарактеристик', 'list', 'Открытие списка'),
    ('DataProcessors', 'Обработка', 'app', 'Открытие обработки'),
]

SECTIONS = [
    'Оператор сопровождения',
    'Координатор логистики',
    'Гид на маршруте',
    'Менеджер по претензиям',
    'Руководитель направления',
    'Администратор ИС',
    'Сервис',
]


def synonym(path):
    text = open(path, encoding='utf-8').read()
    m = re.search(r'<Synonym>.*?<v8:content>([^<]*)</v8:content>', text, re.S)
    return m.group(1) if m else ''


def main():
    objects = []
    for folder, kind, link, caption in KINDS:
        base = os.path.join(CFG, folder)
        if not os.path.isdir(base):
            continue
        for name in sorted(os.listdir(base)):
            xml = os.path.join(base, name + '.xml')
            if os.path.isfile(xml):
                objects.append((kind, name, synonym(xml), link, caption))

    lines = [
        '# language: ru',
        '',
        'Функционал: Дымовые тесты конфигурации КурсоваяРабота',
        '    Проверка открытия разделов и списков прикладных объектов в стандартном интерфейсе.',
        '',
        'Сценарий: Открытие разделов командного интерфейса',
    ]
    for s in SECTIONS:
        lines.append('    Когда Я нажимаю кнопку командного интерфейса "%s"' % s)
    lines.append('')

    for kind, name, syn, link, caption in objects:
        title = syn if syn else name
        lines += [
            'Сценарий: %s - %s %s' % (caption, kind, title),
            '    Дано Я открываю навигационную ссылку "e1cib/%s/%s.%s"' % (link, kind, name),
            '    Тогда открылось окно "%s*"' % title,
            '',
        ]

    out_dir = os.path.join(ROOT, 'tests', 'vanessa')
    os.makedirs(os.path.join(out_dir, 'features'), exist_ok=True)
    with open(os.path.join(out_dir, 'features', 'smoke.feature'), 'w', encoding='utf-8', newline='\r\n') as f:
        f.write('\n'.join(lines))

    results = os.path.join(ROOT, 'build', 'vanessa', 'results')
    os.makedirs(results, exist_ok=True)
    vaparams = {
        'КаталогФич': os.path.join(out_dir, 'features'),
        'ВыполнитьСценарии': True,
        'ЗавершитьРаботуСистемы': True,
        'ОстановкаПриВозникновенииОшибки': False,
        'ДелатьЛогВыполненияСценариевВТекстовыйФайл': True,
        'ИмяФайлаЛогВыполненияСценариев': os.path.join(results, 'log.txt'),
        'ДелатьОтчетВФорматеjUnit': True,
        'ДелатьОтчетВФорматеАллюр': False,
        'КаталогOutputjUnit': os.path.join(results, 'junit'),
        'ВыгружатьСтатусВыполненияСценариевВФайл': True,
        'ПутьКФайлуДляВыгрузкиСтатусаВыполненияСценариев': os.path.join(results, 'status.log'),
        'СписокТеговИсключение': [],
    }
    with open(os.path.join(out_dir, 'vaparams.json'), 'w', encoding='utf-8-sig') as f:
        json.dump(vaparams, f, ensure_ascii=False, indent=2)

    print('Объектов в сценариях: %d' % len(objects))
    print('Feature: %s' % os.path.join(out_dir, 'features', 'smoke.feature'))
    print('VBParams: %s' % os.path.join(out_dir, 'vaparams.json'))


if __name__ == '__main__':
    main()
