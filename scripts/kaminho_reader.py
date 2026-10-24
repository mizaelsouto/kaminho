#!/usr/bin/env python3
"""
Kaminho — Leitor e Roteador Tri-Modal (.md, .html, .json)
Comandos de alta eficiência:
  --route "<prompt>"  -> Retorna em < 7ms o Agente Líder + Top 3 Skills (~80 tokens)
  --format md|html|json --query "<termo>" -> Busca direta nos 3.842 recursos (.md e .html)
  --file "<caminho>"  -> Extrai estrutura limpa de qualquer arquivo .md ou .html
Desenvolvido por: Mizael Souto
"""

import argparse
import html as html_lib
import json
import os
import re
import time

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SKILLS_ROOT = os.path.dirname(BASE_DIR)

CONTEXT_MATRIX = [
    (["humanizer", "humanizar", "robótico", "tom humano", "natural"], "@humanizer", ["humanizer", "hermes-agent"]),
    (["hermes", "openclaw", "memória episódica", "persona", "playbook"], "@hermes-agent", ["hermes-agent", "ai-agentic-systems-multiagent"]),
    (["pentest", "poc", "exploit", "vulnerabilidade", "strix"], "@strix", ["strix", "vulnerability-scanner"]),
    (["design.md", "paleta", "tipografia", "tokens", "getdesign"], "@getdesign", ["getdesign", "open-design"]),
    (["remotion", "vídeo", "animação", "motion graphics"], "@claude-remotion-skill", ["remotion-best-practices"]),
    (["currículo", "rendercv", "typst", "yaml"], "@rendercv", ["rendercv", "pdf"]),
    (["git push", "git reset", "hooks de segurança", "guardrails"], "@devops-engineer", ["git-guardrails-claude-code"]),
    (["apple hig", "ícones 3d", "estética clean", "poluição visual", "chat", "ui", "html", "layout"], "@frontend-ai-engineer", ["apple-hig-designer", "ui-ux-pro-max", "impeccable"]),
    (["grill-me", "caveman", "entrevista", "requisitos", "antes de programar"], "@project-planner", ["brainstorming", "superpowers", "get-shit-done"]),
    (["rag", "bm25", "pgvector", "ragas", "híbrida", "banco"], "@rag-data-architect-ai", ["ai-advanced-rag-scale", "backend-data-rag"]),
]


def route_prompt(prompt: str):
    """Roteia um prompt completo em < 7ms retornando o pacote enxuto (~80 tokens)."""
    t0 = time.perf_counter()
    catalog_path = os.path.join(BASE_DIR, "kaminho-index.json")
    with open(catalog_path, "r", encoding="utf-8") as f:
        catalog = json.load(f)

    p_low = prompt.lower()
    words = [w.strip(".,?!:;()[]\"'") for w in p_low.split() if len(w) > 3]

    best_agent = "@orchestrator"
    best_agent_score = 0
    matched_skills = []

    for kws, target_agent, target_skills in CONTEXT_MATRIX:
        hits = sum(4 for kw in kws if kw in p_low)
        if hits > best_agent_score:
            best_agent_score = hits
            best_agent = target_agent
            matched_skills = list(target_skills)

    for ag in catalog.get("agents", []):
        ag_name = ag["name"].lstrip("@").lower()
        desc_low = ag.get("description", "").lower()
        score = 0
        if ag_name in p_low or ag_name.replace("-", " ") in p_low:
            score += 10
        for w in words:
            if w in desc_low:
                score += 1
        if score > best_agent_score:
            best_agent_score = score
            best_agent = ag["name"]

    scored_skills = [(20, s) for s in matched_skills]
    seen_skills = set(matched_skills)

    for sk in catalog.get("skills", []):
        sk_name = sk["name"].strip("\"'").lower()
        if sk_name in seen_skills:
            continue
        desc_low = sk.get("description", "").lower()
        s_score = 0
        if len(sk_name) > 2 and (sk_name in p_low or sk_name.replace("-", " ") in p_low):
            s_score += 12
        for w in words:
            if w in desc_low:
                s_score += 1
        if s_score >= 4:
            scored_skills.append((s_score, sk_name))
            seen_skills.add(sk_name)

    scored_skills.sort(reverse=True, key=lambda x: x[0])
    top_skills = [s[1] for s in scored_skills[:3]]
    elapsed_ms = (time.perf_counter() - t0) * 1000

    return {
        "router": "Kaminho v1.1 (by Mizael Souto)",
        "primary_agent": best_agent,
        "recommended_skills": top_skills,
        "latency_ms": round(elapsed_ms, 2),
        "announcement": f"🤖 Applying knowledge of @[kaminho] → {best_agent} + {top_skills}"
    }


def read_markdown_source(md_path: str):
    """Lê um índice ou documento .md extraindo tabelas, frontmatter e seções."""
    with open(md_path, "r", encoding="utf-8", errors="ignore") as f:
        text = f.read()
    entries = []
    for line in text.splitlines():
        if line.startswith("|") and not line.startswith("| :---") and not line.startswith("| Agente") and not line.startswith("| Skill") and not line.startswith("| Nome"):
            cols = [c.strip().strip("`*") for c in line.strip("|").split("|")]
            if len(cols) >= 3:
                entries.append({
                    "name": cols[0],
                    "path": cols[1],
                    "description": cols[2],
                    "source_format": "md"
                })
    return entries


def read_html_source(html_path: str):
    """Lê um índice ou página .html extraindo linhas semânticas (<tr>/<td>) e metadados DOM."""
    with open(html_path, "r", encoding="utf-8", errors="ignore") as f:
        text = f.read()
    entries = []
    row_pattern = re.compile(
        r'<tr[^>]*class="searchable-row"[^>]*data-category="([^"]+)"[^>]*>(.*?)</tr>',
        re.IGNORECASE | re.DOTALL
    )
    td_pattern = re.compile(r"<td[^>]*>(.*?)</td>", re.IGNORECASE | re.DOTALL)
    for m in row_pattern.finditer(text):
        category = m.group(1)
        row_html = m.group(2)
        tds = [re.sub(r"<[^>]+>", "", td).strip() for td in td_pattern.findall(row_html)]
        if len(tds) >= 3:
            entries.append({
                "category": category,
                "name": html_lib.unescape(tds[0]),
                "path": html_lib.unescape(tds[1].replace(".md", "").replace(".html", "").strip()),
                "description": html_lib.unescape(tds[2]),
                "source_format": "html"
            })
    return entries


def inspect_single_file(file_path: str):
    """Lê qualquer arquivo .md ou .html individual e retorna sua estrutura limpa para o Agente."""
    ext = os.path.splitext(file_path)[1].lower()
    with open(file_path, "r", encoding="utf-8", errors="ignore") as f:
        raw = f.read()

    if ext in (".html", ".htm"):
        title = re.findall(r"<title[^>]*>(.*?)</title>", raw, re.I | re.S)
        headings = [re.sub(r"<[^>]+>", "", h).strip() for h in re.findall(r"<h[1-3][^>]*>(.*?)</h[1-3]>", raw, re.I | re.S)]
        clean_body = re.sub(r"<(script|style)[^>]*>.*?</\1>", "", raw, flags=re.I | re.S)
        clean_body = re.sub(r"<[^>]+>", " ", clean_body)
        clean_body = re.sub(r"\s+", " ", html_lib.unescape(clean_body)).strip()
        return {
            "format": "html",
            "path": file_path,
            "title": title[0].strip() if title else os.path.basename(file_path),
            "headings": headings[:15],
            "excerpt": clean_body[:800]
        }
    else:
        headings = [h.strip() for h in re.findall(r"^#{1,3}\s+(.+)$", raw, re.M)]
        clean_body = re.sub(r"^---\s*\n.*?\n---\s*", "", raw, flags=re.S).strip()
        return {
            "format": "md",
            "path": file_path,
            "headings": headings[:15],
            "excerpt": clean_body[:800]
        }


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Kaminho CLI & Reader (.md, .html, .json) — Desenvolvido por Mizael Souto")
    parser.add_argument("--route", type=str, default="", help="Frase/prompt para rotear em < 7ms e retornar o agente e skills ideais")
    parser.add_argument("--format", choices=["md", "html", "json"], default="md", help="Formato do índice a ser lido (padrão: md)")
    parser.add_argument("--query", type=str, default="", help="Termo ou contexto para buscar no índice")
    parser.add_argument("--file", type=str, default="", help="Caminho de um arquivo .md ou .html específico para inspecionar")
    args = parser.parse_args()

    if args.route:
        res = route_prompt(args.route)
        print(json.dumps(res, ensure_ascii=False, indent=2))
    elif args.file:
        info = inspect_single_file(args.file)
        print(json.dumps(info, ensure_ascii=False, indent=2))
    else:
        t0 = time.perf_counter()
        if args.format == "md":
            target = os.path.join(BASE_DIR, "kaminho-index.md")
            items = read_markdown_source(target)
        elif args.format == "html":
            target = os.path.join(BASE_DIR, "kaminho-index.html")
            items = read_html_source(target)
        else:
            target = os.path.join(BASE_DIR, "kaminho-index.json")
            with open(target, "r", encoding="utf-8") as f:
                data = json.load(f)
            items = data.get("agents", []) + data.get("skills", []) + data.get("html_resources", [])

        q = args.query.lower().strip()
        if q:
            items = [it for it in items if q in it.get("name", "").lower() or q in it.get("description", "").lower()]
        elapsed = (time.perf_counter() - t0) * 1000
        print(f"[Kaminho Reader ({args.format.upper()})] {len(items)} registros lidos em {elapsed:.2f} ms")
        for it in items[:10]:
            print(f" - {it.get('name')}: {it.get('description')[:110]}")
