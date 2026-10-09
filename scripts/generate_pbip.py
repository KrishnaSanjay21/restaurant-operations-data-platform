"""Generate a source-controlled Power BI Project (PBIP/PBIR) over local evidence exports."""
from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
BASE = ROOT / "powerbi"
NAME = "RestaurantOperations"
MODEL = BASE / f"{NAME}.SemanticModel"
REPORT = BASE / f"{NAME}.Report"
SCHEMA = "https://developer.microsoft.com/json-schemas/fabric"


def save_json(path: Path, value: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2) + "\n", encoding="utf-8")


def field(entity: str, property_name: str, *, measure: bool = False) -> dict:
    kind = "Measure" if measure else "Column"
    return {
        "field": {
            kind: {
                "Expression": {"SourceRef": {"Entity": entity}},
                "Property": property_name,
            }
        },
        "queryRef": f"{entity}.{property_name}",
        "nativeQueryRef": property_name,
    }


def visual(page: str, name: str, visual_type: str, x: int, y: int, w: int, h: int,
           order: int, slots: dict[str, list[dict]]) -> None:
    save_json(
        REPORT / "definition" / "pages" / page / "visuals" / name / "visual.json",
        {
            "$schema": f"{SCHEMA}/item/report/definition/visualContainer/2.7.0/schema.json",
            "name": name,
            "position": {"x": x, "y": y, "z": order, "height": h, "width": w, "tabOrder": order},
            "visual": {
                "visualType": visual_type,
                "query": {"queryState": slots},
                "drillFilterOtherVisuals": True,
            },
        },
    )


def projection(item: dict) -> dict:
    return {"projections": [item]}


def make_model() -> None:
    save_json(MODEL / "definition.pbism", {
        "$schema": f"{SCHEMA}/item/semanticModel/definitionProperties/1.0.0/schema.json",
        "version": "4.0", "settings": {}})
    definition = MODEL / "definition"
    (definition / "tables").mkdir(parents=True, exist_ok=True)
    (definition / "database.tmdl").write_text(
        "database RestaurantOperations\n\tcompatibilityLevel: 1702\n\tcompatibilityMode: powerBI\n\tlanguage: 1033\n",
        encoding="utf-8",
    )
    (definition / "model.tmdl").write_text(
        "model Model\n\tculture: en-US\n\tdefaultPowerBIDataSourceVersion: powerBI_V3\n"
        "\tsourceQueryCulture: en-US\n\nref table Portfolio\nref table Risk\nref table Trend\n"
        "ref table Violations\nref table Complaints\n",
        encoding="utf-8",
    )
    data_root = str((ROOT / "dashboard").resolve()).replace("/", "\\")
    (definition / "expressions.tmdl").write_text(
        f'expression DataRoot = "{data_root}" meta [IsParameterQuery=true, Type="Text", IsParameterQueryRequired=true]\n',
        encoding="utf-8",
    )
    tables = {
        "Portfolio": ("portfolio_kpis.csv", [
            ("restaurants", "int64"), ("inspections", "int64"), ("violations", "int64"),
            ("complaints", "int64"), ("priority_restaurants", "int64")]),
        "Risk": ("priority_restaurants.csv", [
            ("restaurant_name", "string"), ("borough", "string"), ("cuisine_description", "string"),
            ("risk_score", "double"), ("risk_tier", "string"),
            ("critical_violation_count", "int64"), ("matched_complaint_count", "int64")]),
        "Trend": ("monthly_trend.csv", [
            ("month", "dateTime"), ("inspections", "int64"), ("complaints", "int64"),
            ("critical_violations", "int64")]),
        "Violations": ("repeat_violations.csv", [
            ("violation_code", "string"), ("violation_description", "string"), ("occurrences", "int64")]),
        "Complaints": ("complaint_mix.csv", [("complaint_type", "string"), ("complaints", "int64")]),
    }
    for table_name, (filename, columns) in tables.items():
        column_text = "".join(
            f"\tcolumn {name}\n\t\tdataType: {dtype}\n\t\tsourceColumn: {name}\n" for name, dtype in columns
        )
        type_map = ", ".join(
            f'{{"{name}", ' + (
                "Int64.Type}" if dtype == "int64" else
                "type number}" if dtype == "double" else
                "type date}" if dtype == "dateTime" else "type text}"
            ) for name, dtype in columns
        )
        measures = ""
        if table_name == "Portfolio":
            measures = (
                "\tmeasure Restaurants = SUM(Portfolio[restaurants])\n\t\tformatString: #,##0\n"
                "\tmeasure Inspections = SUM(Portfolio[inspections])\n\t\tformatString: #,##0\n"
                "\tmeasure Violations = SUM(Portfolio[violations])\n\t\tformatString: #,##0\n"
                "\tmeasure Complaints = SUM(Portfolio[complaints])\n\t\tformatString: #,##0\n"
                "\tmeasure 'Priority Restaurants' = SUM(Portfolio[priority_restaurants])\n\t\tformatString: #,##0\n"
            )
        content = (
            f"table {table_name}\n{column_text}{measures}\n\tpartition {table_name} = m\n\t\tmode: import\n"
            "\t\tsource =\n\t\t\tlet\n"
            f'\t\t\t\tSource = Csv.Document(File.Contents(DataRoot & "\\{filename}"), '
            "[Delimiter=\",\", Encoding=65001, QuoteStyle=QuoteStyle.Csv]),\n"
            "\t\t\t\tHeaders = Table.PromoteHeaders(Source, [PromoteAllScalars=true]),\n"
            f"\t\t\t\tTypes = Table.TransformColumnTypes(Headers, {{{type_map}}})\n"
            "\t\t\tin\n\t\t\t\tTypes\n"
        )
        (definition / "tables" / f"{table_name}.tmdl").write_text(content, encoding="utf-8")


def make_report() -> None:
    save_json(BASE / f"{NAME}.pbip", {
        "$schema": f"{SCHEMA}/pbip/pbipProperties/1.0.0/schema.json", "version": "1.0",
        "artifacts": [{"report": {"path": f"{NAME}.Report"}}],
        "settings": {"enableAutoRecovery": True}})
    save_json(REPORT / "definition.pbir", {
        "$schema": f"{SCHEMA}/item/report/definitionProperties/2.0.0/schema.json", "version": "4.0",
        "datasetReference": {"byPath": {"path": f"../{NAME}.SemanticModel"}}})
    definition = REPORT / "definition"
    save_json(definition / "version.json", {
        "$schema": f"{SCHEMA}/item/report/definition/versionMetadata/1.0.0/schema.json", "version": "2.0.0"})
    save_json(definition / "report.json", {
        "$schema": f"{SCHEMA}/item/report/definition/report/3.2.0/schema.json",
        "settings": {"exportDataMode": "AllowSummarized", "useEnhancedTooltips": True}})
    pages = (("overview", "Operations Overview"), ("priorities", "Restaurant Priorities"))
    save_json(definition / "pages" / "pages.json", {
        "$schema": f"{SCHEMA}/item/report/definition/pagesMetadata/1.0.0/schema.json",
        "pageOrder": [item[0] for item in pages], "activePageName": "overview"})
    for name, display in pages:
        save_json(definition / "pages" / name / "page.json", {
            "$schema": f"{SCHEMA}/item/report/definition/page/2.1.0/schema.json",
            "name": name, "displayName": display, "displayOption": "FitToPage", "height": 720, "width": 1280})
    for index, measure in enumerate(("Restaurants", "Inspections", "Violations", "Complaints", "Priority Restaurants")):
        visual("overview", f"card{index}", "cardVisual", 20 + index * 250, 20, 230, 100, index,
               {"Data": projection(field("Portfolio", measure, measure=True))})
    visual("overview", "trend", "lineChart", 20, 145, 760, 530, 10, {
        "Category": projection(field("Trend", "month")),
        "Y": {"projections": [field("Trend", "inspections"), field("Trend", "complaints")]}})
    visual("overview", "complaintMix", "clusteredBarChart", 800, 145, 450, 530, 11, {
        "Category": projection(field("Complaints", "complaint_type")),
        "Y": projection(field("Complaints", "complaints"))})
    visual("priorities", "risk", "clusteredBarChart", 20, 20, 760, 655, 20, {
        "Category": projection(field("Risk", "restaurant_name")), "Y": projection(field("Risk", "risk_score"))})
    visual("priorities", "violations", "clusteredBarChart", 800, 20, 450, 655, 21, {
        "Category": projection(field("Violations", "violation_code")),
        "Y": projection(field("Violations", "occurrences"))})


if __name__ == "__main__":
    make_model()
    make_report()
    print(BASE / f"{NAME}.pbip")

