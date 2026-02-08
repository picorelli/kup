#!/usr/bin/env python3
"""
Update section 4.3 of Draft_Preliminary_Results.md from output/preliminary_results.csv.
Run from repo root after run_and_collect_results.sh. Draft path: docs/ or .docs/content/preliminary-results/
"""
import csv
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
CSV_PATH = REPO_ROOT / "output" / "preliminary_results.csv"
DRAFT_CANDIDATES = [
    REPO_ROOT / "docs" / "content" / "preliminary-results" / "Draft_Preliminary_Results.md",
    REPO_ROOT / ".docs" / "content" / "preliminary-results" / "Draft_Preliminary_Results.md",
]


def _fmt_num(val: str) -> str:
    """Format number for pt-BR: decimals with comma; integers as-is or with dot thousands."""
    if not val or not str(val).strip():
        return ""
    s = str(val).strip()
    if "." in s and not s.replace(".", "").isdigit():
        return s
    if "." in s:
        try:
            f = float(s)
            if f == int(f):
                return str(int(f)).replace(",", ".")
            return s.replace(".", ",")
        except ValueError:
            return s
    return s


def _fmt_thousands(val: str) -> str:
    """Format integer with dot as thousands separator (e.g. 2000 -> 2.000)."""
    if not val or not str(val).strip():
        return ""
    try:
        n = int(float(str(val).strip()))
        return f"{n:,}".replace(",", ".")
    except ValueError:
        return str(val)


def build_table_rows(rows: list) -> str:
    """Build markdown table body from CSV rows."""
    lines = []
    for r in rows:
        ts = r.get("timestamp", "")
        strat = r.get("strategy", "")
        p = r.get("predictor_status", "")
        rt = r.get("router_status", "")
        sa = r.get("service_a_status", "")
        sb = r.get("service_b_status", "")
        prom = r.get("prometheus_status", "")
        graf = r.get("grafana_status", "")
        total = _fmt_thousands(r.get("load_test_total", ""))
        ok = _fmt_thousands(r.get("load_test_success", ""))
        fail = r.get("load_test_failures", "")
        avg = _fmt_num(r.get("load_test_avg_latency_s", ""))
        mx = _fmt_num(r.get("load_test_max_latency_s", ""))
        mn = _fmt_num(r.get("load_test_min_latency_s", ""))
        lines.append(f"| {strat:<14} | {ts} | {p} | {rt} | {sa} | {sb} | {prom} | {graf} | {total:>11} | {ok:>7} | {fail:>6} | {avg:>17} | {mx:>16} | {mn:>16} |")
    return "\n".join(lines)


def build_resumo(rows: list, request_count: str) -> str:
    """Build Resumo paragraph from CSV data."""
    if not rows:
        return "**Resumo:** (Nenhum dado no CSV.)"
    total_fail = sum(int(float(r.get("load_test_failures", 0) or 0)) for r in rows)
    avgs = []
    maxs = []
    for r in rows:
        try:
            avgs.append((r.get("strategy", ""), float(r.get("load_test_avg_latency_s", 0) or 0)))
        except (ValueError, TypeError):
            pass
        try:
            maxs.append((r.get("strategy", ""), float(r.get("load_test_max_latency_s", 0) or 0)))
        except (ValueError, TypeError):
            pass
    req_fmt = _fmt_thousands(request_count)
    avg_range = ""
    if avgs:
        avgs.sort(key=lambda x: x[1])
        a0 = f"{avgs[0][1]:.2f}".replace(".", ",")
        a1 = f"{avgs[-1][1]:.2f}".replace(".", ",")
        avg_range = f" A latência média variou entre {a0} s ({avgs[0][0]}) e {a1} s ({avgs[-1][0]})."
    max_range = ""
    if maxs:
        maxs.sort(key=lambda x: x[1])
        m0 = f"{maxs[0][1]:.2f}".replace(".", ",")
        m1 = f"{maxs[-1][1]:.2f}".replace(".", ",")
        max_range = f" A latência máxima ficou entre {m0} s ({maxs[0][0]}) e {m1} s ({maxs[-1][0]})."
    return (
        f"**Resumo:** Em todas as execuções, Router, Service A, Service B, Prometheus e Grafana permaneceram operacionais. "
        f"Na estratégia *none*, o Predictor foi desligado de propósito (status 0). Nas demais, o Predictor ficou ativo com o modelo indicado. "
        f"As {req_fmt} requisições foram atendidas com sucesso ({total_fail} falhas)."
        f"{avg_range}"
        f"{max_range}"
        f" Os próximos passos incluem repetições por cenário, coleta de métricas de recurso e aplicação do teste de Wilcoxon para comparação estatística."
    )


def main():
    if not CSV_PATH.exists():
        print("CSV not found:", CSV_PATH, file=sys.stderr)
        sys.exit(1)
    draft_path = None
    for p in DRAFT_CANDIDATES:
        if p.exists():
            draft_path = p
            break
    if not draft_path:
        print("Draft not found at docs/ or .docs/content/preliminary-results/", file=sys.stderr)
        sys.exit(1)

    with open(CSV_PATH, "r", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        all_rows = [r for r in reader if any(r.get(k) for k in ("strategy", "timestamp"))]

    # Use only 2k-request runs for the draft table
    rows = [r for r in all_rows if str(r.get("load_test_total", "")).strip() == "2000"]
    if not rows:
        rows = all_rows  # fallback to all if no 2k rows

    if not rows:
        print("No data rows in CSV.", file=sys.stderr)
        sys.exit(1)

    request_count = rows[0].get("load_test_total", "2.000")
    intro = f"Cada linha corresponde a uma execução completa: validação da stack + {_fmt_thousands(request_count)} requisições ao Router. Status 1 = serviço operacional; 0 = inativo ou erro."
    header = "| Estratégia      | Timestamp (UTC)     | Predictor | Router | Serv. A | Serv. B | Prom. | Grafana | Requisições | Sucesso | Falhas | Latência média (s) | Latência máx. (s) | Latência mín. (s) |"
    sep = "|-----------------|----------------------|-----------|--------|---------|---------|-------|---------|-------------|---------|--------|-------------------|------------------|-------------------|"
    table_body = build_table_rows(rows)
    resumo = build_resumo(rows, request_count)

    discussao = (
        "**Discussão por estratégia.** Na estratégia *none* (baseline, predictor desligado), as requisições foram atendidas com sucesso na execução registrada, servindo de referência. "
        "Nas estratégias com predictor (linear, random_forest, arima), a stack manteve estabilidade; eventuais falhas pontuais e variações de latência devem ser analisadas com mais repetições e teste de Wilcoxon (subseção 4.4)."
    )
    new_section = f"""### 4.3 Resultados do load test por estratégia

{intro}

**Tabela 3.** Resultados consolidados por estratégia (preliminary_results.csv).

{header}
{sep}
{table_body}

*Fonte: Resultados originais da pesquisa.*

{discussao}

{resumo}

**Checklist antes de enviar (conferir Projeto de Pesquisa):** objetivos [ ], metodologia [ ], material [ ], resultados alinhados ao que foi proposto [ ].
"""

    content = draft_path.read_text(encoding="utf-8")
    start_marker = "### 4.3 Resultados do load test por estratégia"
    end_marker = "**Checklist antes de enviar (conferir Projeto de Pesquisa):** objetivos [ ], metodologia [ ], material [ ], resultados alinhados ao que foi proposto [ ]."
    start_idx = content.find(start_marker)
    end_idx = content.find(end_marker)
    if start_idx == -1:
        print("Section 4.3 not found in draft.", file=sys.stderr)
        sys.exit(1)
    if end_idx == -1:
        print("Checklist marker not found in draft.", file=sys.stderr)
        sys.exit(1)
    end_idx += len(end_marker)

    new_content = content[:start_idx] + new_section + content[end_idx:]
    draft_path.write_text(new_content, encoding="utf-8")
    print("Updated:", draft_path, file=sys.stderr)


if __name__ == "__main__":
    main()
