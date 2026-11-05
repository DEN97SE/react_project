#!/usr/bin/env python3
"""Structural checks only: this is not a 1C compiler or a BSL interpreter."""
import re
from pathlib import Path
ROOT = Path(__file__).resolve().parents[1]

def tokens(text):
    clean=[]
    for line in text.splitlines():
        i=0
        out=[]
        while i<len(line):
            if line.startswith('//',i):
                break
            if line[i]=='"':
                i+=1
                while i<len(line):
                    if line[i]=='"':
                        if i+1<len(line) and line[i+1]=='"':
                            i+=2
                            continue
                        i+=1
                        break
                    i+=1
                else:
                    raise AssertionError('Unterminated string: '+line)
                out.append(' STRING ')
            else:
                out.append(line[i]);i+=1
        clean.append(''.join(out))
    return '\n'.join(clean)

modules={}
for path in sorted((ROOT/'modules').glob('*.txt')):
    raw=path.read_text()
    src=tokens(raw)
    delimiters=[]
    for c in src:
        if c in '([':delimiters.append(c)
        elif c in ')]':
            assert delimiters and delimiters.pop()=={')':'(',']':'['}[c],path.name
    assert not delimiters,path.name
    starts={'функция':'конецфункции','процедура':'конецпроцедуры','если':'конецесли','пока':'конеццикла','для':'конеццикла','попытка':'конецпопытки'}
    ends=set(starts.values())
    stack=[]
    for match in re.finditer(r'(?<![\w.])(Функция|Процедура|Если|Пока|Для|Попытка|КонецФункции|КонецПроцедуры|КонецЕсли|КонецЦикла|КонецПопытки)\b',src,re.I):
        word=match[1].lower()
        if word in starts:stack.append(starts[word])
        elif word in ends:assert stack and stack.pop()==word,(path.name,word)
    assert not stack,(path.name,stack)
    defs=re.findall(r'^\s*(?:Функция|Процедура)\s+(\w+)\s*\([^\n]*?\)\s*(Экспорт)?',src,re.M|re.I)
    assert len({name.lower() for name,_ in defs})==len(defs),path.name
    assert all(name.lower()!='состояние' for name,_ in defs),path.name
    modules[path.stem]={name.lower() for name,export in defs if export}
    # All referenced information registers/constants existed in the supplied source.
    assert not re.search(r'(?:РегистрыСведений|РегистрСведений)\.(?!РаспределениеКМПоКатегориям\b|ОчередьШины\b)\w+',raw),path.name
    assert 'Константы.' not in src,path.name
    native_calls=set(re.findall(r'Интеграция1СШина(?:Переопределяемый)?\.(\w+)\s*\(',src))
    assert native_calls <= {'ЗарегистрироватьОбъектВОчереди'},path.name
    if native_calls:assert path.stem=='КХ_КП_ОчередьКабинета',path.name
    print('PASS structure:',path.name)
for path in (ROOT/'modules').glob('*.txt'):
    src=tokens(path.read_text())
    for mod,method in re.findall(r'(КХ_\w+)\.(\w+)\s*\(',src):
        if mod=='КХ_ОбменШиныОпера':
            assert method=='СистемыСобственнойОчереди',(path.name,method)
        else:
            assert mod in modules and method.lower() in modules[mod],(path.name,mod,method)
    calls=set(re.findall(r'Интеграция1СШина\.(\w+)\s*\(',src))
    assert calls <= {'ЗарегистрироватьОбъектВОчереди'},(path.name,calls)
assert not (ROOT/'modules'/'Интеграция1СШина.txt').exists()
for path in (ROOT/'modules').glob('*.txt'):
    assert 'AMQP' not in path.read_text(),path.name
transport=(ROOT/'modules'/'КХ_КП_ТранспортШины.txt').read_text()
assert 'Параметры.Вставить("configuration", "Astor")' in transport
assert 'СоздатьСообщение()' in transport and '.ОтправитьСообщение(Сообщение)' in transport
bus=(ROOT/'bus'/'Integration.txt').read_text()
assert 'Получить("configuration")' in bus
assert 'Http_kp_Astor' in bus and 'Http_kp_DO' in bus
assert 'Установить("Authorization", Integration.Параметры.API_key)' in bus
assert 'X-API-Key' not in bus
assert 'ПолучитьТелоКакПоток()' in bus and 'УстановитьТело(ПотокТела)' in bus
queue=(ROOT/'modules'/'КХ_КП_ОчередьКабинета.txt').read_text()
assert 'Возврат 259200;' in queue
# Every persistent delete goes through the manager factory with all five dimensions.
assert queue.count('.Удалить();')==1
factory=queue[queue.index('Функция МенеджерНашейЗаписи'):queue.index('Процедура СохранитьЗапись')]
for dim in ['ИдентификаторОбъекта','ИдентификаторСообщения','КаналСервисаИнтеграции','УзелПолучатель','ВнешняяСистема']:
    assert 'Менеджер.'+dim+' =' in factory,dim
assert 'Маркер.СрокUTC =' not in queue
assert 'Если Применено Тогда' in queue
assert 'КП.ПодтвержденоПрименение' in queue
finish=queue[queue.index('Процедура ЗавершитьОтправку'):queue.index('Функция ВременныйHTTPКод')]
assert 'УдалитьЗапись' not in finish
print('PASS exports, existing registrar reuse, full-key deletion, fixed 72h deadline, no deletion on transport success, Astor routing/Auth')
print('NOT RUN: 1C compilation/runtime, SQL data, Bus project or HTTP delivery')
