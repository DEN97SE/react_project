"""Проверки данных и модели контракта; не исполнение BSL в платформе 1С."""
from collections import Counter, defaultdict
from copy import deepcopy
from decimal import Decimal
from pathlib import Path
import json
import re

ROOT = Path('/workspace/1c_shop50')
LOG = Path('/workspace/attachments/d7fb594c-215f-4579-b8a3-3ce99aaaa4f0/bus_log.md')
CURRENT = ROOT / 'ОбщиеМодули/КХ_ДанныеОпера.bsl'
BEFORE = ROOT / 'Исправления_20261029/ПовторыШтрихкодов/ДоПравки/КХ_ДанныеОпера.bsl'


def remove_identical(rows):
    """Модель правила: ключ включает товар и всю экспортируемую запись."""
    result, seen = [], set()
    for product, barcode in rows:
        key = (product, json.dumps(barcode, sort_keys=True, ensure_ascii=False))
        if key not in seen:
            seen.add(key)
            result.append((product, deepcopy(barcode)))
    return result


def remaining_collisions(rows):
    groups = defaultdict(list)
    for product, entry in rows:
        groups[(product, entry['barcode'])].append(entry)
    return {k: v for k, v in groups.items() if len(v) > 1}


def check(condition, explanation):
    if not condition:
        raise AssertionError(explanation)
    checks.append(explanation)


checks, rows, product_ids = [], [], set()
section = LOG.read_text().split('## Номенклатура с повторяющимся штрихкодом', 1)[1].split('## Пакеты', 1)[0]
for line in section.splitlines():
    if not re.match(r'\| \d+ \|', line):
        continue
    fields = [field.strip() for field in line.strip('|').split('|')]
    product = fields[1].strip('`')
    product_ids.add(product)
    for barcode, unit, quantity in re.findall(r'(\d+)\s*\(([^,]+),\s*([^)]+)\)', fields[4]):
        rows.append((product, {'barcode': barcode, 'unit': unit.strip(), 'quantity_in_package': quantity.strip()}))

original = deepcopy(rows)
clean = remove_identical(rows)
check(len(product_ids) == 26, 'Воспроизведены все 26 карточек из таблицы лога')
check(len(rows) - len(clean) == 22, 'Удаляются 22 полностью одинаковые экспортируемые записи')
check(set(p for p, _ in clean) == product_ids, 'Ни один товар не исчезает при удалении дублей')
check(rows == original, 'Модель не изменяет исходные карточки')
check(remove_identical(clean) == clean, 'Повторная нормализация не меняет результат')
check(set((p, e['barcode']) for p, e in clean) == set((p, e['barcode']) for p, e in rows), 'Не теряются штрихкоды ни одного товара')
check(set((p, tuple(sorted(e.items()))) for p, e in clean) == set((p, tuple(sorted(e.items()))) for p, e in rows), 'Не теряются варианты единиц и количества')

collisions = remaining_collisions(clean)
check(len(collisions) == 4, 'Четыре неодинаковых варианта намеренно остаются для проверки')
same_quantity = [entries for entries in collisions.values() if len({Decimal(e['quantity_in_package']) for e in entries}) == 1]
quantity_conflicts = [entries for entries in collisions.values() if len({Decimal(e['quantity_in_package']) for e in entries}) > 1]
check(len(same_quantity) == 3, 'Сохраняются три случая с одинаковым количеством и разными названиями упаковки')
check(len(quantity_conflicts) == 1, 'Конфликт количества не скрывается нормализацией')
check({e['quantity_in_package'] for e in quantity_conflicts[0]} == {'1', '30'}, 'У плюшки сохраняется явный конфликт 1/30')

example = {'barcode': '000123', 'unit': 'шт', 'quantity_in_package': '1'}
check(len(remove_identical([('A', example), ('B', example)])) == 2, 'Карточки разных товаров не объединяются')
check(len(remove_identical([('A', example), ('A', {**example, 'barcode': '123'})])) == 2, 'Ведущие нули штрихкода сохраняют значение')
check(len(remove_identical([('A', {'barcode': '000123'}), ('A', example)])) == 2, 'Отсутствующие поля не подменяются выдуманными значениями')
extra = [('A', {**example, 'unit': 'кор'}), ('A', example), ('A', {**example, 'unit': 'кор'})]
check([e['unit'] for _, e in remove_identical(extra)] == ['кор', 'шт'], 'Порядок оставшихся разных записей сохраняется')

old, new = BEFORE.read_text(), CURRENT.read_text()
method = 'Функция ПодготовитьШтрихКоды(ТаблицаШтрихКодов)'
old_prefix, old_tail = old.split(method, 1)
new_prefix, new_tail = new.split(method, 1)
old_method, old_suffix = old_tail.split('КонецФункции', 1)
new_method, new_suffix = new_tail.split('КонецФункции', 1)
check(old_suffix == new_suffix, 'Все методы после ПодготовитьШтрихКоды остались побайтно теми же')
check(new_prefix == old_prefix.replace(
    '// Как работает: преобразует каждую строку в структуру штрихкода и добавляет её в массив соответствующего товара.',
    '// Как работает: преобразует строки в структуры штрихкода, сохраняя только одно одинаковое представление для каждого товара.'),
    'До функции изменено только пояснение её назначения')
check('ЗначениеВСтрокуВнутр(Новый Структура(' in new_method and '"Номенклатура,Данные", СтрокаШтрихКода.Номенклатура, ДанныеШтрихКода' in new_method,
      'BSL-ключ включает ссылку товара и полную структуру экспортируемого штрихкода')
check(not re.search(r'Записать\(|НачатьТранзакцию\(|ОтправитьСообщение\(', new_method),
      'Правка не добавляет запись бизнес-данных, очереди или отправку')

result = {'passed': len(checks), 'checks': checks, 'scope': 'Разбор таблицы лога, модель правила и проверка области изменения; BSL в 1С не исполнялся',
          'log_products': len(product_ids), 'removed_identical_entries': len(rows)-len(clean), 'remaining_alias_groups': len(same_quantity), 'remaining_quantity_conflicts': len(quantity_conflicts)}
Path(__file__).with_name('ПроверкаПравил.json').write_text(json.dumps(result, ensure_ascii=False, indent=2) + '\n')
print(json.dumps(result, ensure_ascii=False, indent=2))
