"""Limited local source/packaging checks; no 1C or ESB compilation/runtime."""
import hashlib
import json
import re
import sys
import uuid
from pathlib import Path

sys.path.insert(0, "/tmp/esb_parsers")
import yaml
from tree_sitter import Language, Parser
import tree_sitter_bsl

root = Path(__file__).resolve().parent
parser = Parser(Language(tree_sitter_bsl.language()))
checks = []


def check(name, passed, details=""):
    checks.append({"check": name, "pass": bool(passed), "details": details})


parts = [
    ("SharedUserTest.yaml", "yaml"),
    ("InfoBases_Добавка.xbsl", "bsl"),
    ("КХ_ТестОбщегоДоступа.bsl", "bsl"),
    ("МодульТестовогоСервиса.bsl", "bsl"),
    ("МодульТестовогоБэка.bsl", "bsl"),
    ("01_ПодготовитьИС_ИзКонсоли50.txt", "bsl"),
    ("02_Настроить_В_ОбеихБазах.txt", "bsl"),
    ("02б_НастроитьБэк_Только50.txt", "bsl"),
    ("03_ПроверитьОтправку.txt", "bsl"),
]
sources = {name: (root / name).read_text() for name, _ in parts}
order = (root / "Порядок.txt").read_text()
combined = "# Эксперимент общего пользователя — №50 и №410\n\n" + order
for name, language in parts:
    combined += f"\n\n## {name}\n\n```{language}\n{sources[name].rstrip()}\n```\n"
(root / "ВесьКодДляКопирования.md").write_text(combined)

for name, language in parts:
    if language != "bsl" or name.endswith(".xbsl"):
        continue  # XBSL is a different language; the BSL parser cannot validate it.
    # Normalize only parser input for known tree-sitter-bsl 0.1.6 limitations.
    # Delivered code is never changed to satisfy this incomplete grammar.
    normalized = re.sub(r"КонецЦикла;", "КонецЦикла", sources[name], flags=re.I)
    normalized = re.sub(r"ВызватьИсключение\s*;", 'ВызватьИсключение "parser placeholder";', normalized, flags=re.I)
    tree = parser.parse(normalized.encode())
    errors = []
    pending = [tree.root_node]
    while pending:
        node = pending.pop()
        if node.type == "ERROR" or node.is_missing:
            errors.append({"type": node.type, "row": node.start_point.row + 1})
        pending.extend(node.children)
    check("Limited BSL parse: " + name, not errors, json.dumps(errors))

schema = yaml.safe_load(sources["SharedUserTest.yaml"])
graph = schema["Схема"]
nodes = {n["Имя"] for n in graph["Узлы"]}
groups = {g["Имя"] for g in graph["ГруппыУчастников"]}
check("Four native test nodes", nodes == {"FromShops", "ToBackend", "FromBackend", "ToShops"})
check("Two test groups", groups == {"Shops", "Backend"})
check("Both backend routes", {(r["Из"], r["В"]) for r in graph["Маршруты"]} == {("FromShops", "ToBackend"), ("FromBackend", "ToShops")})
check("Graph references", all(c["Узел"] in nodes and c["Группа"] in groups for c in graph["Связи"]))


def identifiers(value):
    result = []
    if isinstance(value, dict):
        for key, child in value.items():
            if key == "Ид":
                result.append(str(uuid.UUID(child)))
            else:
                result.extend(identifiers(child))
    elif isinstance(value, list):
        for child in value:
            result.extend(identifiers(child))
    return result


ids = identifiers(schema)
check("Schema UUID uniqueness", len(ids) == len(set(ids)))
for file, procedure in [("МодульТестовогоСервиса.bsl", "Принять"), ("МодульТестовогоБэка.bsl", "ПринятьНаБэке")]:
    check("Callback: " + file, f"КХ_ТестОбщегоДоступа.{procedure}(Сообщение, Отказ)" in sources[file])
for code in ["00000000-0000-4000-8000-000000000050", "00000000-0000-4000-8000-000000000410", "00000000-0000-4000-8000-000000000003"]:
    check("Fixture/client address: " + code, code in sources["InfoBases_Добавка.xbsl"] and code in sources["КХ_ТестОбщегоДоступа.bsl"])

report = {
    "kind": "LOCAL_SOURCE_AND_PACKAGING_CHECKS_ONLY",
    "date": "2026-10-28",
    "limitations": [
        "Not a 1C or ESB compile or runtime test; XBSL not parsed.",
        "BSL parser input uses two explicitly documented grammar workarounds.",
        "Does not prove identity binding, membership, queue selection or fault recovery.",
        "Previous 76-check report is superseded; that count was not runtime evidence.",
    ],
    "passed": sum(c["pass"] for c in checks),
    "total": len(checks),
    "checks": checks,
    "sha256": {name: hashlib.sha256((root / name).read_bytes()).hexdigest() for name in [n for n, _ in parts] + ["Порядок.txt", "ВесьКодДляКопирования.md"]},
}
(root / "ПроверкаКомплекта.json").write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n")
print(json.dumps({"passed": report["passed"], "total": report["total"], "failures": [c for c in checks if not c["pass"]]}, ensure_ascii=False))
raise SystemExit(0 if all(c["pass"] for c in checks) else 1)
