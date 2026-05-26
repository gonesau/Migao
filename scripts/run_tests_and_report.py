"""Run pytest and generate an HTML summary report.

Usage:
    uv run python scripts/run_tests_and_report.py
"""

from __future__ import annotations

import ast
import html
import re
import subprocess
import sys
import xml.etree.ElementTree as ET
from dataclasses import dataclass
from pathlib import Path


ROOT = Path(__file__).resolve().parent.parent
REPORTS_DIR = ROOT / "reports"
JUNIT_PATH = REPORTS_DIR / "junit.xml"
HTML_PATH = REPORTS_DIR / "test_summary.html"
TESTS_DIR = ROOT / "tests"


@dataclass
class TestResult:
    module: str
    classname: str
    test_name: str
    nodeid: str
    status: str
    duration_sec: float
    reason: str
    objective: str


def _humanize_test_name(name: str) -> str:
    base = name.replace("test_", "").replace("_", " ").strip()
    if not base:
        return name
    return base[0].upper() + base[1:]


def _collect_test_objectives() -> dict[tuple[str, str], str]:
    """Map (module_stem, test_name) to objective text from docstring or function name."""
    objectives: dict[tuple[str, str], str] = {}
    for path in TESTS_DIR.glob("test_*.py"):
        module_stem = path.stem
        source = path.read_text(encoding="utf-8")
        tree = ast.parse(source, filename=str(path))

        for node in tree.body:
            if isinstance(node, ast.FunctionDef) and node.name.startswith("test_"):
                doc = ast.get_docstring(node) or _humanize_test_name(node.name)
                objectives[(module_stem, node.name)] = doc
            elif isinstance(node, ast.ClassDef):
                for child in node.body:
                    if isinstance(child, ast.FunctionDef) and child.name.startswith("test_"):
                        doc = ast.get_docstring(child) or _humanize_test_name(child.name)
                        objectives[(module_stem, child.name)] = doc
    return objectives


def _run_pytest_and_collect_xml() -> int:
    REPORTS_DIR.mkdir(parents=True, exist_ok=True)
    cmd = ["uv", "run", "pytest", f"--junitxml={JUNIT_PATH}"]
    proc = subprocess.run(cmd, cwd=ROOT, check=False)
    return proc.returncode


def _extract_module_from_classname(classname: str) -> str:
    # Pytest often emits values like: tests.test_foo.TestClass
    if not classname:
        return "unknown"
    parts = classname.split(".")
    if len(parts) >= 2 and parts[0] == "tests":
        # tests.test_file.TestClass  -> test_file
        # tests.test_file            -> test_file
        return parts[1]
    if len(parts) >= 2:
        return parts[-2]
    return parts[0]


def _parse_junit_results(objectives: dict[tuple[str, str], str]) -> list[TestResult]:
    tree = ET.parse(JUNIT_PATH)
    root = tree.getroot()
    results: list[TestResult] = []

    for testcase in root.findall(".//testcase"):
        classname = testcase.attrib.get("classname", "")
        test_name = testcase.attrib.get("name", "")
        duration = float(testcase.attrib.get("time", "0") or "0")
        module = _extract_module_from_classname(classname)

        status = "passed"
        reason = "Sin excepciones y aserciones satisfechas."

        failure = testcase.find("failure")
        error = testcase.find("error")
        skipped = testcase.find("skipped")

        if failure is not None:
            status = "failed"
            reason = (failure.attrib.get("message") or (failure.text or "")).strip()
        elif error is not None:
            status = "error"
            reason = (error.attrib.get("message") or (error.text or "")).strip()
        elif skipped is not None:
            status = "skipped"
            reason = (skipped.attrib.get("message") or (skipped.text or "")).strip()

        reason = re.sub(r"\s+", " ", reason).strip()
        if len(reason) > 320:
            reason = reason[:317] + "..."
        if not reason:
            reason = "Sin detalle adicional."

        objective = objectives.get((module, test_name), _humanize_test_name(test_name))
        nodeid = f"{module}::{classname.split('.')[-1] if classname else ''}::{test_name}".replace("::::", "::")
        results.append(
            TestResult(
                module=module,
                classname=classname,
                test_name=test_name,
                nodeid=nodeid,
                status=status,
                duration_sec=duration,
                reason=reason,
                objective=objective,
            )
        )
    return results


def _status_badge(status: str) -> str:
    cls = {
        "passed": "ok",
        "failed": "fail",
        "error": "err",
        "skipped": "skip",
    }.get(status, "unk")
    return f'<span class="badge {cls}">{html.escape(status.upper())}</span>'


def _render_html(results: list[TestResult], exit_code: int) -> None:
    totals = {
        "total": len(results),
        "passed": sum(r.status == "passed" for r in results),
        "failed": sum(r.status == "failed" for r in results),
        "error": sum(r.status == "error" for r in results),
        "skipped": sum(r.status == "skipped" for r in results),
        "duration": sum(r.duration_sec for r in results),
    }

    by_module: dict[str, list[TestResult]] = {}
    for r in results:
        by_module.setdefault(r.module, []).append(r)

    module_rows: list[str] = []
    detail_rows: list[str] = []
    for module, module_tests in sorted(by_module.items()):
        m_total = len(module_tests)
        m_passed = sum(t.status == "passed" for t in module_tests)
        m_failed = sum(t.status in {"failed", "error"} for t in module_tests)
        m_skipped = sum(t.status == "skipped" for t in module_tests)
        rate = (m_passed / m_total * 100.0) if m_total else 0.0
        module_rows.append(
            "<tr>"
            f"<td>{html.escape(module)}</td>"
            f"<td>{m_total}</td><td>{m_passed}</td><td>{m_failed}</td><td>{m_skipped}</td>"
            f"<td>{rate:.1f}%</td>"
            "</tr>"
        )

        for test in module_tests:
            detail_rows.append(
                "<tr>"
                f"<td>{html.escape(test.nodeid)}</td>"
                f"<td>{html.escape(test.objective)}</td>"
                f"<td>{_status_badge(test.status)}</td>"
                f"<td>{test.duration_sec:.3f}s</td>"
                f"<td>{html.escape(test.reason)}</td>"
                "</tr>"
            )

    outcome = "OK" if exit_code == 0 else "FALLA"
    report = f"""<!doctype html>
<html lang="es">
<head>
  <meta charset="utf-8" />
  <meta name="viewport" content="width=device-width,initial-scale=1" />
  <title>Resumen de tests</title>
  <style>
    body {{ font-family: Arial, sans-serif; margin: 24px; background: #0b1020; color: #e7ecff; }}
    h1, h2 {{ margin: 0 0 12px; }}
    .muted {{ color: #aeb8dd; margin-bottom: 16px; }}
    .cards {{ display: grid; grid-template-columns: repeat(6, minmax(90px, 1fr)); gap: 10px; margin: 16px 0 22px; }}
    .card {{ background: #141c34; border: 1px solid #263056; border-radius: 10px; padding: 10px; }}
    .k {{ color: #9fb0e8; font-size: 12px; display: block; }}
    .v {{ font-size: 21px; font-weight: 700; }}
    table {{ width: 100%; border-collapse: collapse; margin: 12px 0 26px; }}
    th, td {{ border-bottom: 1px solid #29335d; text-align: left; padding: 10px 8px; vertical-align: top; }}
    th {{ color: #b5c2ef; font-weight: 600; }}
    .badge {{ padding: 3px 7px; border-radius: 999px; font-size: 12px; font-weight: 700; }}
    .ok {{ background: #1f6f4a; color: #b8f5da; }}
    .fail, .err {{ background: #7a2d2d; color: #ffd1d1; }}
    .skip {{ background: #5e4d1f; color: #ffe9b3; }}
    .unk {{ background: #3a3f57; color: #d9def5; }}
  </style>
</head>
<body>
  <h1>Resumen de ejecución de tests</h1>
  <p class="muted">Resultado global: <strong>{outcome}</strong>. Reporte generado desde pytest + JUnit XML.</p>

  <div class="cards">
    <div class="card"><span class="k">Total</span><span class="v">{totals["total"]}</span></div>
    <div class="card"><span class="k">Passed</span><span class="v">{totals["passed"]}</span></div>
    <div class="card"><span class="k">Failed</span><span class="v">{totals["failed"]}</span></div>
    <div class="card"><span class="k">Errors</span><span class="v">{totals["error"]}</span></div>
    <div class="card"><span class="k">Skipped</span><span class="v">{totals["skipped"]}</span></div>
    <div class="card"><span class="k">Duración</span><span class="v">{totals["duration"]:.2f}s</span></div>
  </div>

  <h2>Resumen por módulo</h2>
  <table>
    <thead><tr><th>Módulo</th><th>Total</th><th>Passed</th><th>Failed/Error</th><th>Skipped</th><th>Pass %</th></tr></thead>
    <tbody>
      {"".join(module_rows)}
    </tbody>
  </table>

  <h2>Detalle por test</h2>
  <table>
    <thead><tr><th>Test</th><th>Qué prueba</th><th>Estado</th><th>Tiempo</th><th>Por qué pasó/falló</th></tr></thead>
    <tbody>
      {"".join(detail_rows)}
    </tbody>
  </table>
</body>
</html>
"""
    HTML_PATH.write_text(report, encoding="utf-8")


def main() -> int:
    objectives = _collect_test_objectives()
    exit_code = _run_pytest_and_collect_xml()
    results = _parse_junit_results(objectives)
    _render_html(results, exit_code)
    print(f"Reporte HTML generado en: {HTML_PATH}")
    return exit_code


if __name__ == "__main__":
    raise SystemExit(main())
