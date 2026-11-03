"""Проверка присланного среза; не подключается к 1С и ничего туда не записывает."""
from pathlib import Path
import collections
import json
import re
import urllib.parse

import openpyxl

ROOT = Path(__file__).resolve().parent
SOURCES = ROOT / "Исходники"
OWN = {"Opera", "PriceCheker", "OperaChange", "OperaState"}


def method(text, name):
    pattern = (
        r"^(?:Процедура|Функция)\s+" + re.escape(name)
        + r"\([^\n]*\).*?^Конец(?:Процедуры|Функции)\b"
    )
    match = re.search(pattern, text, flags=re.M | re.S)
    if match is None:
        raise AssertionError("Не найден метод: " + name)
    return match.group(0)


native = (SOURCES / "Интеграция1СШина.bsl").read_text(encoding="utf-8-sig")
opera = (SOURCES / "КХ_ОбменШиныОпера.bsl").read_text(encoding="utf-8-sig")
systems = set(re.findall(r'Системы\.Добавить\("([^"]+)"\)', method(opera, "СистемыСобственнойОчереди")))
assert systems == OWN, systems

filter_checks = {}
for name in (
    "ОчередьДляВыгрузки", "ОтменаЗависшихСообщенийВШине",
    "УдалениеСтарыхЗаписейОчереди", "ОбработатьКвитанцию",
):
    body = method(native, name)
    assert body.count("И НЕ (ОчередьШины.ВнешняяСистема В (&КХ_СобственныеСистемы))") == 1, name
    assert body.count('Запрос.УстановитьПараметр("КХ_СобственныеСистемы", КХ_ОбменШиныОпера.СистемыСобственнойОчереди())') == 1, name
    filter_checks[name] = "Исключение и его параметр присутствуют"

write_body = method(opera, "НаборОчереди")
for field in ("ИдентификаторОбъекта", "УзелПолучатель", "КаналСервисаИнтеграции", "ВнешняяСистема"):
    assert "Набор.Отбор." + field + ".Установить(" in write_body, field
assert '"КХ_OperaChange", "", "OperaChange"' in method(opera, "ЗарегистрироватьНоменклатуры")

book = openpyxl.load_workbook(ROOT / "очередьШины.xlsx", read_only=True, data_only=True)
sheet = book.active
rows = [row for row in sheet.iter_rows(min_row=2, values_only=True) if any(v is not None for v in row)]


def value(row, index):
    return str(row[index] or "").strip()


own_rows = [r for r in rows if value(r, 4) in OWN]
legacy_rows = [r for r in rows if value(r, 4) not in OWN]
grouped = collections.Counter((value(r, 4), value(r, 8)) for r in rows)
pairs = collections.defaultdict(list)
for row in rows:
    pairs[(value(row, 0), value(row, 3))].append(row)
mixed = [key for key, group in pairs.items()
         if any(value(r, 4) in OWN for r in group)
         and any(value(r, 4) not in OWN for r in group)]

packets = []
for row in own_rows:
    if value(row, 4) != "Opera":
        continue
    payload = json.loads(row[11])
    assert value(row, 0) == payload["batch_id"]
    assert payload["message_type"] == "products"
    assert payload["project"] == "opera"
    packets.append({"batch_id": payload["batch_id"], "source_revision": payload["source_revision"],
                    "status": value(row, 8), "products_count": len(payload["products"])})

lint = json.loads((ROOT / "Проверки" / "bsl-json.json").read_text())
diagnostics = {}
for file in lint["fileinfos"]:
    name = Path(urllib.parse.unquote(urllib.parse.urlparse(file["path"]).path)).name
    diagnostics[name] = dict(collections.Counter(d["severity"] for d in file["diagnostics"]))

result = {
    "scope": "Статическое чтение исходников и выгрузки XLSX; без исполнения запросов в 1С",
    "native_filter_checks": filter_checks,
    "own_write_filter": ["ИдентификаторОбъекта", "УзелПолучатель", "КаналСервисаИнтеграции", "ВнешняяСистема"],
    "queue_rows": len(rows), "legacy_rows_retained_by_system_exclusion": len(legacy_rows),
    "own_rows_excluded_from_native_processing": len(own_rows),
    "groups": [{"external_system": system, "status": status, "count": count}
               for (system, status), count in sorted(grouped.items())],
    "mixed_own_legacy_object_recipient_pairs": mixed,
    "opera_packets": packets,
    "bsl_language_server_severities": diagnostics,
    "limitations": [
        "Проверка добавленного исключения по внешней системе не воспроизводит целиком платформенные запросы.",
        "XLSX не подтверждает текущую доставку старого обмена, расписание, источники подписок и активные сервисы.",
        "Нулевое число пересечений ключей относится только к присланному срезу.",
        "Статический анализ не является компиляцией и исполнением в платформе 1С.",
    ],
}
(ROOT / "Проверки" / "Изоляция_результат.json").write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n")
print(json.dumps({"rows": len(rows), "legacy": len(legacy_rows), "own": len(own_rows),
                  "mixed_pairs": len(mixed), "filter_methods_checked": len(filter_checks)}, ensure_ascii=False))
