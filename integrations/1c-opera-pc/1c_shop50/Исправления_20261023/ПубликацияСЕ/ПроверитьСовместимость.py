"""Статическая проверка совместимости с присланными исходниками/XLSX, без доступа к 1С."""
from pathlib import Path
import collections
import json
import re

import openpyxl

PATCH = Path(__file__).resolve().parent
ROOT = PATCH.parents[1]
MODULES = ROOT / "ОбщиеМодули"


def methods(source):
    return {
        match.group(1): match.group(0)
        for match in re.finditer(
            r"(?ms)^(?:Функция|Процедура)\s+(\w+).*?^Конец(?:Функции|Процедуры)\b", source
        )
    }


before = methods((PATCH / "ДоПравки/КХ_ОбменШиныОпера.bsl").read_text())
after_source = (MODULES / "КХ_ОбменШиныОпера.bsl").read_text()
after = methods(after_source)
allowed = {
    "ЗарегистрироватьПакет", "ОтправитьПорциюПакетов", "ОтправитьПакетВСервис",
    "ОбработатьВходящееСообщение", "ОбработатьПодтверждение",
    "СистемыСобственнойОчереди", "УдалитьПодтвержденныеПакеты",
}
changed = {name for name in before if before[name] != after[name]}
assert changed == allowed, changed ^ allowed
assert before.keys() == after.keys()
for name in (
    "КХ_ДанныеОпера.bsl", "КХ_ДанныеПрайсЧекеры.bsl", "КХ_ДанныеСтруктурныхЕдиниц.bsl"
):
    assert (MODULES / name).read_bytes() == (PATCH / "ДоПравки" / name).read_bytes(), name
systems = set(re.findall(r'Системы\.Добавить\("([^"]+)"\)', after["СистемыСобственнойОчереди"]))
old_systems = {"Opera", "PriceCheker", "OperaChange", "OperaState"}
assert systems == old_systems | {"StructuralUnits"}, systems

native = methods((ROOT / "Аудит_20261023/Исходники/Интеграция1СШина.bsl").read_text(encoding="utf-8-sig"))
native_checks = []
for name in (
    "ОчередьДляВыгрузки", "ОтменаЗависшихСообщенийВШине",
    "УдалениеСтарыхЗаписейОчереди", "ОбработатьКвитанцию"
):
    body = native[name]
    assert body.count("И НЕ (ОчередьШины.ВнешняяСистема В (&КХ_СобственныеСистемы))") == 1, name
    assert body.count("КХ_ОбменШиныОпера.СистемыСобственнойОчереди()") == 1, name
    native_checks.append(name)

book = openpyxl.load_workbook(ROOT / "Аудит_20261023/очередьШины.xlsx", read_only=True, data_only=True)
rows = [r for r in book.active.iter_rows(min_row=2, values_only=True) if any(v is not None for v in r)]
tag = lambda row: str(row[4] or "").strip()
assert not any(tag(r) == "StructuralUnits" for r in rows), "Новый тег уже занят в присланном срезе"
legacy_before = [r for r in rows if tag(r) not in old_systems]
legacy_after = [r for r in rows if tag(r) not in systems]
assert legacy_before == legacy_after

module_texts = {p.stem: p.read_text() for p in MODULES.glob("*.bsl")}
exports = {
    name: set(re.findall(r"(?m)^(?:Процедура|Функция)\s+(\w+)\([^\n]*\)\s+Экспорт", text))
    for name, text in module_texts.items()
}
calls = 0
for caller, text in module_texts.items():
    for module, function in re.findall(r"(КХ_\w+)\.(\w+)\s*\(", text):
        if module in exports:
            assert function in exports[module], (caller, module, function)
            calls += 1

result = {
    "scope": "Статический анализ текстов и исторического XLSX; не исполнение в 1С",
    "changed_core_methods": sorted(changed),
    "unchanged_core_methods": len(before) - len(changed),
    "native_dynamic_filters": native_checks,
    "own_systems": sorted(systems),
    "xlsx_rows": len(rows),
    "legacy_rows_retained": len(legacy_after),
    "new_tag_already_used_in_xlsx": False,
    "own_exported_calls_resolved": calls,
    "limitations": [
        "Срез XLSX исторический, он не доказывает отсутствие новых конфликтов в текущей базе.",
        "Код платформы, подписки, права, блокировки, реальная Шина и ACK бэков здесь не исполняются."
    ],
}
(PATCH / "Совместимость.json").write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n")
print(json.dumps(result, ensure_ascii=False))
