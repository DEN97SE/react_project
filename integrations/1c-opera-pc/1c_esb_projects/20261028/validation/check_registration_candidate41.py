from pathlib import Path
import json
import re
import yaml
from tree_sitter import Language, Parser
import tree_sitter_bsl
import tree_sitter_powershell

ROOT = Path('/workspace')
SOURCE = ROOT / '1c_esb_projects/20261028/Opera_PC'
CANDIDATE = ROOT / '1c_esb_projects/20261028/Opera_PC_1.0-41_registration_candidate'
CLIENT = ROOT / '1c_shop50/АвтоПодключение_20261028'
CHECKS = []


def check(name, condition):
    CHECKS.append({'name': name, 'passed': bool(condition)})
    assert condition, name


for path in SOURCE.rglob('*'):
    if path.is_file() and path.name != 'Assembly.yaml':
        check('original unchanged: ' + str(path.relative_to(SOURCE)),
              path.read_bytes() == (CANDIDATE / path.relative_to(SOURCE)).read_bytes())

docs = {}
ids = []


def walk_ids(value):
    if isinstance(value, dict):
        if 'Ид' in value:
            ids.append(value['Ид'])
        for item in value.values():
            walk_ids(item)
    elif isinstance(value, list):
        for item in value:
            walk_ids(item)


for path in CANDIDATE.rglob('*.yaml'):
    docs[path.name] = yaml.safe_load(path.read_text(encoding='utf-8-sig'))
    walk_ids(docs[path.name])
check('unique metadata IDs in candidate', len(ids) == len(set(ids)))
service = docs['InfoBases.yaml']
check('HTTP admin-only', service['КонтрольДоступа']['Разрешения']['Вызов'] == 'РазрешеноАдминистраторам')
server = (CANDIDATE / 'Komandor/Opera_PC/Основной/InfoBases.xbsl').read_text()
for route in service['ШаблоныUrl']:
    check('route admin-only: ' + route['Шаблон'], route['КонтрольДоступа']['Разрешения']['Вызов'] == 'РазрешеноАдминистраторам')
    for method in route['Методы']:
        check('method admin-only: ' + route['Шаблон'] + '/' + method['Метод'],
              method['КонтрольДоступа']['Разрешения']['Вызов'] == 'РазрешеноАдминистраторам')
        check('declared HTTP handler: ' + method['Обработчик'],
              re.search(r'^метод ' + method['Обработчик'] + r'\(', server, re.M) is not None)
check('one catalog only', sum(d.get('ВидЭлемента') == 'Справочник' for d in docs.values()) == 1)
check('no unsupported secret catalog', 'КлючиРегистрацииМагазинов.yaml' not in docs and 'КлючиРегистрацииМагазинов' not in server)
check('request explicitly initialized', 'пер Вход = новый ЗаявкаМагазина("", "")' in server)
check('response explicitly initialized', 'пер Ответ = новый ОтветРегистрации("", "", "", "")' in server)
check('existing participant guard before key issue', server.index('если УчастникСуществует(Код)', server.index('метод ЗарегистрироватьМагазин')) < server.index('СгенерироватьДанныеЗапросаТокенаДоступа('))
check('existing participant reports recovery requirement', 'existing_participant_use_central_cache_or_recover' in server)
check('single location issuing credentials', server.count('СгенерироватьДанныеЗапросаТокенаДоступа(') == 1)
check('no EDO dependencies', 'ExchangeVEDO' not in server and 'ВнутреннийEDO' not in server)
check('responses disable cache', '"Cache-Control", "no-store"' in server)
for process, group in [('Opera', 'MagazyniOpera'), ('PC', 'MagazinyPriceChecker')]:
    check('existing group: ' + group, group in [g['Имя'] for g in docs[process + '.yaml']['Схема']['ГруппыУчастников']])
    check('registration group: ' + group, process + '.ДобавитьУчастниковВГруппы("' + group + '", ИС)' in server)

registration = docs['РегистрацияМагазинов.yaml']
check('third visible integration process', registration['ВидЭлемента'] == 'ПроцессИнтеграции' and registration['Имя'] == 'РегистрацияМагазинов')
check('new process uses existing participant catalog', registration['СправочникУчастников'].endswith('::Exch'))
nodes = registration['Схема']['Узлы']
check('programmatic source documented', nodes[0]['Вид'] == 'ПрограммныйИсточник')
check('result translator documented', nodes[1]['Вид'] == 'Транслятор')
process_code = (CANDIDATE / 'Komandor/Opera_PC/Основной/РегистрацияМагазинов.xbsl').read_text()
check('translator handler exists', 'метод ' + nodes[1]['Преобразование'] + '(' in process_code)
check('new route connected', registration['Схема']['Маршруты'][0]['Из'] == nodes[0]['Имя'] and registration['Схема']['Маршруты'][0]['В'] == nodes[1]['Имя'])
emit = server[server.index('метод ОтразитьРегистрациюНаСхеме('):]
check('event contains no credentials', not any(token in emit for token in ['ОтветРегистрации', 'clientsecret', 'clientid', 'Запрос.Тело', 'ДанныеДоступа']))
event_type=server[server.index('структура СобытиеРегистрацииМагазина'):server.index('структура ОшибкаРегистрации')]
check('audit DTO has no credential fields', 'clientid' not in event_type and 'clientsecret' not in event_type)
check('event only after committed registration', server.index('Транзакция.Фиксировать()') < server.index('Ответ.schema_event_queued ='))
check('event failure preserves HTTP keys', 'поймать Искл: Исключение\n        возврат Ложь' in emit)
check('event uses documented dispatch', 'РегистрацияМагазинов.ОтправитьСообщениеВУзлы' in emit)
check('response identifies acceptance only', 'schema_event_queued: Булево = Ложь' in server)

files = [
    (tree_sitter_bsl, CLIENT / 'КХ_НастройкаПодключенийШины.bsl'),
    (tree_sitter_bsl, CLIENT / 'ГотовыйЗапуск/КХ_ЗапускРегистрацииШины.bsl'),
    (tree_sitter_bsl, CLIENT / 'ГотовыйЗапуск/00_ПроверкаОтправлятораБезИзменений.txt'),
    (tree_sitter_powershell, CLIENT / 'ГотовыйЗапуск/Run-StoreEnrollment.ps1'),
    (tree_sitter_powershell, CLIENT / 'ГотовыйЗапуск/Test-EnrollmentApi.ps1'),
]
for language, path in files:
    tree = Parser(Language(language.language())).parse(path.read_bytes())
    check('syntax parsing: ' + path.name, not tree.root_node.has_error)
    if path.suffix in ('.bsl', '.txt'):
        check('no data delivery calls: ' + path.name, not any(call in path.read_text() for call in (
            'ОтправитьСообщение(', 'ВыполнитьОбработку(', 'НачатьПолнуюВыгрузку(', 'УдалитьПодтвержденныеПакеты(')))
module = (CLIENT / 'КХ_НастройкаПодключенийШины.bsl').read_text()
check('original ИмяПользователя preserved', 'Настройки.ИмяПользователя =' not in module)
runner = (CLIENT / 'ГотовыйЗапуск/Run-StoreEnrollment.ps1').read_text()
check('preview exits before registration', runner.index('READY_PREVIEW') < runner.index("$Stage = 'REGISTRATION'"))
check('database/store guard precedes HTTP registration', runner.index('Store UUID mismatch') < runner.index('$Registration = Invoke-RestMethod'))
check('DPAPI cache', 'ConvertFrom-SecureString' in runner and '.json.dpapi' in runner)
for path in (CLIENT / 'ГотовыйЗапуск').glob('*.ps1'):
    for line in path.read_text().splitlines():
        if 'Write-Host' in line:
            check('no credential output: ' + path.name + ':' + line.strip()[:55],
                  not any(token in line for token in ('clientsecret', 'DbPassword', 'BootstrapToken', 'RegistrationJson')))

report = {
    'passed': len(CHECKS), 'checks': CHECKS,
    'esb_compilation_run': False, 'one_c_platform_compilation_run': False,
    'windows_com_runtime_run': False, 'deployed_to_user_environment': False,
    'note': 'Tree-sitter parses client syntax; YAML/source checks do not replace ESB/1C compilation or runtime tests.',
    'server_scope': 'One sequential registration worker. Concurrent same-GUID enrolment is not claimed.'
}
(ROOT / '1c_esb_projects/20261028/validation/registration_candidate41_checks.json').write_text(
    json.dumps(report, ensure_ascii=False, indent=2) + '\n')
print('Passed', len(CHECKS), 'checks. ESB/1C compilation and runtime remain pending.')
