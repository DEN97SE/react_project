"""Проверка данных, модели миграции и области патча; не исполнение BSL в 1С."""
from copy import deepcopy
from pathlib import Path
import json
import re

ROOT = Path(__file__).parent
IDS = {410: '40933103-84ba-4d00-ab50-ce9efa15eda8', 50: '3370588b-0742-11e0-b9c1-001a64c3f566'}
NODE = {n: 'S'+v.replace('-', '') for n,v in IDS.items()}
checks = []


def check(ok, label):
    if not ok:
        raise AssertionError(label)
    checks.append(label)


def plan(number, state, rows, inactive=True):
    """Модель ограничений разового исправления транспортного адреса."""
    if not inactive or state['full_active'] or state['catalog_requests']:
        raise ValueError('processing')
    if state['pc_store_id'] != IDS[number] or state['pc_node_code'] != NODE[number]:
        raise ValueError('identity')
    legacy = {'Backend_PC'} | ({NODE[410]} if number == 50 else set())
    if state['pc_backend_node'] not in legacy | {NODE[number]}:
        raise ValueError('unexpected backend')
    result, new_state = deepcopy(rows), deepcopy(state)
    keys, moved = set(), 0
    for row in result:
        if row['status'] != 'confirmed':
            body = json.loads(row['body'])
            if body.get('store_id') != IDS[number] or body.get('source_node') != NODE[number] or body.get('project') != 'pricechecker' or body.get('message_type') != 'products' or body.get('batch_id') != row['id']:
                raise ValueError('payload')
            if row['receiver'] != NODE[number]:
                if row['receiver'] not in legacy:
                    raise ValueError('recipient')
                row.update(receiver=NODE[number], status='waiting', transport_id='', attempt='', sent_at='0001', loaded_at='0001', error='transport address corrected')
                moved += 1
        key = row['id'], row['receiver'], row['channel']
        if key in keys:
            raise ValueError('collision')
        keys.add(key)
    new_state['pc_backend_node'] = NODE[number]
    return new_state, result, moved


def fixture(n, receiver='Backend_PC'):
    batch = 'c5f3584f-3b29-4187-a80c-ccbbd767d696'
    body = json.dumps({'store_id': IDS[n], 'source_node': NODE[n], 'project': 'pricechecker', 'message_type': 'products', 'batch_id': batch, 'session_id': 'ea2f7001-d82c-46ae-8602-cc7e20c0de07', 'source_epoch': 'bf8fe678-440b-4c5b-bd68-b73bc51089d4', 'source_revision': '0', 'products': [{'nomenclature_id': 'A', 'barcodes': [{'barcode': '000123'}]}]}, ensure_ascii=False, indent=2)
    row = dict(id=batch, receiver=receiver, channel='Основной_PC_FromShops', status='sent', body=body, transport_id='old-id', attempt='old-attempt', sent_at='2026', loaded_at='0001', registered_at='2026', error='waiting ack', custom='preserve')
    state = dict(pc_store_id=IDS[n], pc_node_code=NODE[n], pc_backend_node=receiver, node_code=NODE[n], opera_backend_node='BackendOpera', source_epoch='original epoch', revision=0, full_active=False, catalog_requests=[])
    return state, [row]


for number in IDS:
    state, rows = fixture(number)
    old = deepcopy((state, rows))
    new_state, new_rows, moved = plan(number, state, rows)
    check(moved == 1 and new_rows[0]['receiver'] == NODE[number], f'{number}: устаревший Backend_PC перенаправляется на свою ИС')
    check(new_rows[0]['body'] == rows[0]['body'] and new_rows[0]['id'] == rows[0]['id'] and new_rows[0]['channel'] == rows[0]['channel'], f'{number}: batch_id, JSON и канал не меняются')
    check(new_rows[0]['status'] == 'waiting' and not new_rows[0]['transport_id'] and not new_rows[0]['attempt'], f'{number}: требуется новая транспортная попытка, не фиктивный ACK')
    check((state, rows) == old, f'{number}: план не меняет исходные данные до применения')
    check({k:v for k,v in new_state.items() if k != 'pc_backend_node'} == {k:v for k,v in state.items() if k != 'pc_backend_node'}, f'{number}: источник, эпоха, версия и Opera не меняются')
    check(plan(number, new_state, new_rows)[2] == 0, f'{number}: повторное исправление не переносит пакет снова')

state, rows = fixture(50, NODE[410])
check(plan(50, state, rows)[1][0]['receiver'] == NODE[50], '50: исправляется известная жёсткая привязка к адресу 410')
state, rows = fixture(410)
rows[0]['status'] = 'confirmed'
check(plan(410, state, rows)[1] == rows and plan(410, state, rows)[2] == 0, 'Подтверждённые записи остаются без изменений')


def rejects(label, mutate=None, **kwargs):
    state, rows = fixture(410)
    if mutate:
        mutate(state, rows)
    before = deepcopy((state, rows))
    try:
        plan(410, state, rows, **kwargs)
    except ValueError:
        check((state, rows) == before, label)
    else:
        raise AssertionError('Unexpected success: '+label)


rejects('Активное подключение блокирует исправление', inactive=False)
rejects('Активная full блокирует исправление', lambda s,r: s.update(full_active=True))
rejects('Ожидающий запрос full блокирует исправление', lambda s,r: s.update(catalog_requests=[{'id':'pending'}]))
rejects('Чужой магазин в состоянии блокирует исправление', lambda s,r: s.update(pc_store_id=IDS[50]))
rejects('Смена отправителя не допускается', lambda s,r: s.update(pc_node_code=NODE[50]))
rejects('Неизвестный настроенный адрес не заменяется', lambda s,r: s.update(pc_backend_node='OtherBackend'))
rejects('Чужой store_id в пакете отклоняется', lambda s,r: r[0].update(body=r[0]['body'].replace(IDS[410], IDS[50])))
rejects('Чужой source_node в пакете отклоняется', lambda s,r: r[0].update(body=r[0]['body'].replace(NODE[410], NODE[50])))
rejects('Чужой проект в пакете отклоняется', lambda s,r: r[0].update(body=r[0]['body'].replace('pricechecker','opera')))
rejects('Несовпадение batch_id с ключом отклоняется', lambda s,r: r[0].update(id='other-id'))
rejects('Неизвестный получатель пакета не заменяется', lambda s,r: r[0].update(receiver='OtherBackend'))
rejects('Коллизия старого и нового ключа блокирует всю операцию', lambda s,r: r.append({**r[0], 'receiver':NODE[410]}))

original = (ROOT/'ИсходникПользователя.bsl').read_text()
patched = (ROOT/'КХ_ПилотШины.bsl').read_text()
addition = (ROOT/'ДобавитьВКХ_ПилотШины.bsl').read_text()
expected = original.replace('КХ_ОбменШиныОпера.НастроитьМаршрутПрайсЧекеров(Данные.node_code, "S4093310384ba4d00ab50ce9efa15eda8");','КХ_ОбменШиныОпера.НастроитьМаршрутПрайсЧекеров(Данные.node_code, Данные.node_code);').replace('Маршрут.КодПолучателя <> "S4093310384ba4d00ab50ce9efa15eda8"','Маршрут.КодПолучателя <> Данные.node_code')
pos=expected.rfind('// }} semidockij - 28.10.2026')
expected = expected[:pos]+addition+'\n'+expected[pos:]
check(patched == expected, 'Присланный модуль изменён только двумя заменами и добавлением одной процедуры')
check('НастроитьПолучателяОпера("BackendOpera")' in patched, 'Получатель Opera остаётся BackendOpera')
check('PC = "Основной_PC_FromShops"' in patched, 'Сохранено актуальное короткое имя PC-канала из присланного файла')
check(addition.index('ПоместитьВоВременноеХранилище') < addition.index('Набор.Записать(Истина)'), 'Временная копия создаётся до первой записи изменений')
check('Отбор.ВнешняяСистема.Установить("PriceCheker")' in addition and 'Отбор.ИдентификаторОбъекта.Установить("КХ_OperaState")' in addition, 'Наборы ограничены PC и точным корнем технического состояния')
check('СтрокаОчереди.СтроковыйОбъект =' not in addition and 'СтрокаОчереди.ИдентификаторОбъекта =' not in addition and 'Состояние.Вставить("source_epoch"' not in addition, 'Код не присваивает новые JSON пакетов, batch_id или эпохи')
check('Набор.Очистить(' not in addition and 'Удалить(' not in addition, 'Код не удаляет пакеты')
check('ОтменитьТранзакцию();' in addition, 'При ошибке предусмотрен откат транзакции')
check('КодПолучателя' in (ROOT/'ОбработчикPC_ТолькоТело.bsl').read_text() and 'Backend_PC' not in (ROOT/'ОбработчикPC_ТолькоТело.bsl').read_text(), 'Проверка отправителя ACK использует настроенный адрес PC')

report={'passed':len(checks), 'checks':checks, 'limitations':'Проверены модель данных и область патча. BSL в платформе 1С не компилировался и не исполнялся; пользовательские очереди не изменены.'}
(ROOT/'Проверка.json').write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n')
print(json.dumps(report,ensure_ascii=False,indent=2))
