#!/usr/bin/env python3
"""
Kaminho v2.0 — Motor Semântico, Decompositor de Intenções & Roteador Tri-Modal (.md, .html, .json)
Comandos de alta eficiência:
  --route "<prompt>"     -> Reconhecimento semântico + Pipeline Multi-Agente em < 15ms
  --pipeline "<prompt>"  -> Decompõe um texto complexo em etapas semânticas com agentes e skills por fase
  --format md|html|json --query "<termo>" -> Busca semântica e léxica nos 3.841 recursos (.md e .html)
  --file "<caminho>"     -> Extrai estrutura limpa de qualquer arquivo .md ou .html
Desenvolvido por: Mizael Souto
"""

import argparse
import html as html_lib
import json
import math
import os
import re
import time
import unicodedata
from collections import Counter

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SKILLS_ROOT = os.path.dirname(BASE_DIR)


def normalize_text(text: str) -> str:
    """Remove acentos e normaliza para comparação semântica tolerante a variações."""
    if not text:
        return ""
    nfkd = unicodedata.normalize("NFKD", text.lower())
    no_accents = "".join(c for c in nfkd if not unicodedata.combining(c))
    return re.sub(r"\s+", " ", no_accents).strip()


def char_ngrams(text: str, n: int = 3) -> Counter:
    """Extrai n-gramas de caracteres para similaridade de cosseno sub-palavra (captura radicais e sinônimos morfológicos)."""
    norm = re.sub(r"[^a-z0-9\s]", " ", normalize_text(text))
    padded = f" {norm} "
    if len(padded) < n:
        return Counter([padded])
    return Counter(padded[i : i + n] for i in range(len(padded) - n + 1))


def cosine_similarity_counters(c1: Counter, c2: Counter) -> float:
    """Calcula a similaridade de cosseno entre dois vetores esparsos (Counters)."""
    if not c1 or not c2:
        return 0.0
    common = set(c1.keys()) & set(c2.keys())
    num = sum(c1[k] * c2[k] for k in common)
    if num == 0:
        return 0.0
    den1 = math.sqrt(sum(v * v for v in c1.values()))
    den2 = math.sqrt(sum(v * v for v in c2.values()))
    if den1 == 0 or den2 == 0:
        return 0.0
    return num / (den1 * den2)


# Grafo Semântico de Intenções (Kaminho v2.0)
# Cada nó representa um conceito semântico amplo, frases-conceito, radicais morfológicos, Agente Líder e Skills.
SEMANTIC_INTENT_GRAPH = [
    {
        "id": "socratic_interview",
        "intent": "Entrevista Socrática & Levantamento de Requisitos",
        "phase_priority": 10,
        "agent": "@project-planner",
        "skills": ["grill-me", "brainstorming", "caveman"],
        "phrases": [
            "me pergunte", "faca perguntas", "pergunte quais", "tire duvidas",
            "antes de comecar", "antes de programar", "entreviste", "alinhamento",
            "quais dados desejo", "o que eu quero", "clarificar requisitos",
            "grill-me", "grill me", "caveman", "brainstorming"
        ],
        "stems": ["pergunt", "entrevist", "duvid", "question", "indag", "quais dados", "desejo"],
        "semantic_profile": "perguntar ao usuario quais dados deseja entrevistar alinhar requisitos tirar duvidas questionario interativo socratico grill-me brainstorming"
    },
    {
        "id": "live_research_current_data",
        "intent": "Pesquisa de Dados Atuais, Tendências & Web Scraping",
        "phase_priority": 20,
        "agent": "@explorer-agent",
        "skills": ["last30days", "firecrawl-agent"],
        "phrases": [
            "dados atuais", "dados recentes", "ultimos 30 dias", "ultimas noticias",
            "tendencias atuais", "o que estao falando", "pesquisa atual", "informacoes atuais",
            "tempo real", "extrair dados da web", "navegar no site", "last30days", "firecrawl"
        ],
        "stems": ["atuais", "atual", "recent", "ultim", "tendenc", "pesquis", "colet", "extrair dados"],
        "semantic_profile": "mostrar dados atuais recentes pesquisas nos ultimos 30 dias tendencias mercado noticias fatos reais web scraping last30days firecrawl"
    },
    {
        "id": "planning_and_summary",
        "intent": "Planejamento Estruturado, Escopo & Plano Resumido",
        "phase_priority": 30,
        "agent": "@project-planner",
        "skills": ["plan-writing", "superpowers", "get-shit-done", "planning-with-files"],
        "phrases": [
            "plano resumido", "gere um plano", "criar um plano", "planejamento",
            "etapas do projeto", "roteiro estruturado", "passo a passo", "cronograma",
            "estruturar ideias", "arquitetura do plano", "resumo executivo", "prd", "spec"
        ],
        "stems": ["plano", "planej", "resumid", "etapa", "roteir", "estrutur", "roadmap", "escopo"],
        "semantic_profile": "gerar plano resumido estruturado etapas passo a passo planejamento estrategico sintese executiva tarefas plan-writing superpowers"
    },
    {
        "id": "humanized_writing_article",
        "intent": "Redação Humanizada, Artigos & Linguagem Natural (Anti-IA)",
        "phase_priority": 40,
        "agent": "@humanizer",
        "skills": ["humanizer", "doc-coauthoring", "internal-comms"],
        "phrases": [
            "linguagem bem proxima da humana", "linguagem humana", "proxima da humana",
            "tom humano", "tom natural", "sem parecer ia", "sem tom robotico",
            "texto fluido", "reescrever como humano", "crie um artigo", "escrever artigo",
            "redigir texto", "post de blog", "ensaio", "humanizer", "humanizar"
        ],
        "stems": ["human", "natural", "robotic", "artigo", "redig", "reescrev", "fluidez", "autoral"],
        "semantic_profile": "linguagem bem proxima da humana texto natural fluido sem clichês de inteligencia artificial criar artigo redacao coautoria humanizer doc-coauthoring"
    },
    {
        "id": "ui_ux_apple_hig",
        "intent": "Design de Interface, Apple HIG, UI/UX & Polimento Visual",
        "phase_priority": 40,
        "agent": "@frontend-ai-engineer",
        "skills": ["apple-hig-designer", "ui-ux-pro-max", "impeccable", "frontend-design"],
        "phrases": [
            "apple hig", "estilo apple", "macos", "ios", "interface limpa",
            "estetica clean", "poluicao visual", "melhorar tela", "dashboard bonito",
            "auditoria visual", "componentes visuais", "layout moderno", "impeccable"
        ],
        "stems": ["interface", "layout", "visual", "design", "tela", "hig", "estetic", "ui", "ux"],
        "semantic_profile": "design interface usuario apple hig macos ios componentes bonitos layout responsivo polimento visual ui ux impeccable"
    },
    {
        "id": "design_system_extraction",
        "intent": "Extração de Design System (DESIGN.md), Paletas & Prototipagem",
        "phase_priority": 35,
        "agent": "@getdesign",
        "skills": ["getdesign", "open-design", "theme-factory"],
        "phrases": [
            "design.md", "extrair paleta", "extrair design", "tipografia do site",
            "tokens de cor", "getdesign", "open-design", "prototipar sem figma"
        ],
        "stems": ["palet", "tipograf", "token", "getdesign", "tema"],
        "semantic_profile": "extrair paleta cores tipografia tokens layout de site para design.md prototipagem getdesign open-design"
    },
    {
        "id": "episodic_memory_autonomous_agent",
        "intent": "Agente Autônomo Persistente, Memória Episódica & Aprendizado Contínuo",
        "phase_priority": 35,
        "agent": "@hermes-agent",
        "skills": ["hermes-agent", "ai-agentic-systems-multiagent"],
        "phrases": [
            "hermes", "openclaw", "memoria episodica", "auto-aperfeicoavel",
            "agente persistente", "aprender com sessoes", "playbook conversacional"
        ],
        "stems": ["hermes", "episodic", "openclaw", "autonom", "memor"],
        "semantic_profile": "agente autonomo persistente memoria episodica aprendizado continuo hermes-agent nous research multiagente"
    },
    {
        "id": "offensive_security_pentest",
        "intent": "Segurança Ofensiva, Pentest Autônomo, Auditoria & Exploits PoC",
        "phase_priority": 50,
        "agent": "@strix",
        "skills": ["strix", "vulnerability-scanner", "trailofbits-security"],
        "phrases": [
            "pentest", "explorar vulnerabilidade", "achar falhas de seguranca",
            "gerar exploit", "poc de seguranca", "auditoria de codigo", "owasp", "strix"
        ],
        "stems": ["pentest", "vulnerab", "exploit", "seguranc", "invas", "strix", "auditor"],
        "semantic_profile": "pentest teste de invasao vulnerabilidades seguranca ofensiva poc exploit owasp strix trailofbits"
    },
    {
        "id": "git_safety_guardrails",
        "intent": "Proteção de Comandos Git & Prevenção de Ações Destrutivas",
        "phase_priority": 55,
        "agent": "@devops-engineer",
        "skills": ["git-guardrails-claude-code"],
        "phrases": [
            "git push", "git reset", "bloquear comando perigoso", "hooks de seguranca",
            "proteger repositorio", "evitar force push", "guardrails no git"
        ],
        "stems": ["git", "push", "reset", "branch", "guardrail", "hook"],
        "semantic_profile": "proteger git contra reset hard push force comandos destrutivos hooks seguranca git-guardrails"
    },
    {
        "id": "programmatic_video_remotion",
        "intent": "Criação de Vídeo Programático em React & Motion Graphics",
        "phase_priority": 45,
        "agent": "@claude-remotion-skill",
        "skills": ["remotion-best-practices"],
        "phrases": [
            "remotion", "video em react", "video programatico", "animacao de video",
            "motion graphics", "renderizar mp4"
        ],
        "stems": ["remotion", "video", "animac", "motion", "frame"],
        "semantic_profile": "criar video programatico animacao react motion graphics remotion"
    },
    {
        "id": "curriculum_rendercv",
        "intent": "Geração de Currículos Profissionais em YAML + Typst",
        "phase_priority": 45,
        "agent": "@rendercv",
        "skills": ["rendercv", "pdf"],
        "phrases": [
            "curriculo", "cv profissional", "rendercv", "typst", "curriculo em yaml"
        ],
        "stems": ["curricul", "rendercv", "typst", "resum"],
        "semantic_profile": "criar curriculo profissional executivo yaml typst pdf rendercv"
    },
    {
        "id": "rag_database_backend",
        "intent": "Arquitetura RAG Híbrida, Banco Vetorial & Backend Escalável",
        "phase_priority": 40,
        "agent": "@rag-data-architect-ai",
        "skills": ["ai-advanced-rag-scale", "backend-data-rag", "database-design"],
        "phrases": [
            "rag", "busca hibrida", "bm25", "pgvector", "banco vetorial",
            "embeddings", "reranking", "ragas", "otimizar sql"
        ],
        "stems": ["rag", "vetorial", "pgvector", "bm25", "embedding", "banco"],
        "semantic_profile": "arquitetura rag busca hibrida bm25 pgvector banco de dados vetorial embeddings reranking"
    },
    {
        "id": "office_documents_suite",
        "intent": "Geração e Manipulação de Documentos (Word, PDF, Excel, Slides)",
        "phase_priority": 45,
        "agent": "@documentation-writer",
        "skills": ["docx", "pdf", "pptx", "xlsx", "deckset-presentation-expert"],
        "phrases": [
            "documento word", "arquivo docx", "gerar pdf", "apresentacao de slides",
            "powerpoint", "pptx", "planilha excel", "xlsx", "relatorio formatado"
        ],
        "stems": ["docx", "pdf", "pptx", "xlsx", "planilh", "slide", "apresentac", "word"],
        "semantic_profile": "criar editar documentos word docx pdf apresentacao slides pptx planilha excel xlsx"
    },
    {
        "id": "skill_discovery_installer",
        "intent": "Descoberta, Catálogo e Instalação Global de Skills",
        "phase_priority": 15,
        "agent": "@skill-installer-manager",
        "skills": ["skill-installer-asimov", "find-skills", "agent-skills", "skill-creator"],
        "phrases": [
            "instalar skill", "nova skill", "catalogo de skills", "50 melhores skills",
            "procurar skill", "criar uma skill", "gerenciar skills"
        ],
        "stems": ["instal", "skill", "catalogo", "asimov"],
        "semantic_profile": "instalar buscar descobrir novas skills catalogo asimov globalmente skill-installer"
    }
]

# Pré-computa os vetores de n-gramas para cada nó semântico (executa em ~0.3ms na importação)
for _node in SEMANTIC_INTENT_GRAPH:
    _node["_ngram_vec"] = char_ngrams(
        _node["semantic_profile"] + " " + " ".join(_node["phrases"])
    )


def decompose_prompt_into_clauses(prompt: str) -> list:
    """
    Quebra um texto complexo do usuário em orações/segmentos semânticos preservando o sentido de cada etapa.
    Exemplo:
      "Crie um artigo que mostre dados atuais, me pergunte quais dados desejo, e depois gere um plano resumido e uma linguagem bem proxima da humana."
    """
    # Separadores discursivos de múltiplas intenções em português
    split_pattern = re.compile(
        r"(?:\s*,\s*e\s+depois\s+|\s+e\s+depois\s+|\s*,\s*depois\s+|\s*,\s*em\s+seguida\s+|"
        r"\s+em\s+seguida\s+|\s*;\s*|\s*\.\s+(?=[A-Za-zÀ-ÿ])|"
        r"\s*,\s*(?=(?:me\s+pergunt|pergunt|mostr|ger[ea]|cri[ea]|us[ea]|aplic|fa[cç]a|com\s+uma\s+linguagem))|"
        r"\s+e\s+(?=(?:uma\s+linguagem|tom\s+humano|tom\s+natural|me\s+pergunt|depois\s+|gere\s+|mostre\s+)))",
        re.IGNORECASE
    )
    raw_clauses = [c.strip(" ,.;:") for c in split_pattern.split(prompt) if c and len(c.strip(" ,.;:")) >= 4]

    # Se a primeira cláusula tiver "que mostre / contendo" embutido com outra ação ("Crie um artigo que mostre dados atuais"),
    # separa a criação principal da coleta de dados para precisão cirúrgica
    refined_clauses = []
    for cl in raw_clauses:
        sub_m = re.match(
            r"^((?:crie|escreva|redija|elabore|faca)\s+um\s+(?:artigo|texto|documento|post|relatorio))\s+que\s+(.+)$",
            normalize_text(cl)
        )
        if sub_m and len(cl) > 22:
            idx_que = normalize_text(cl).find(" que ")
            if idx_que != -1:
                part1 = cl[:idx_que].strip()
                part2 = cl[idx_que + 5 :].strip()
                refined_clauses.append(part1)
                refined_clauses.append(part2)
                continue
        refined_clauses.append(cl)

    return refined_clauses if refined_clauses else [prompt.strip()]


def score_clause_against_node(clause: str, node: dict) -> float:
    """Calcula a pontuação semântica híbrida (Frases Conceituais + Radicais Morfológicos + Similaridade de Cosseno N-Gram)."""
    norm_cl = normalize_text(clause)
    if not norm_cl:
        return 0.0

    score = 0.0

    # 1. Match de expressões conceituais completas (peso alto)
    for phrase in node["phrases"]:
        norm_p = normalize_text(phrase)
        if norm_p in norm_cl:
            score += 0.55

    # 2. Match de radicais morfológicos (stems)
    stem_hits = 0
    for stem in node["stems"]:
        if normalize_text(stem) in norm_cl:
            stem_hits += 1
    if stem_hits > 0:
        score += min(0.45, stem_hits * 0.22)

    # 3. Similaridade de Cosseno Vetorial por N-Gramas de caracteres
    cl_vec = char_ngrams(norm_cl)
    cos_sim = cosine_similarity_counters(cl_vec, node["_ngram_vec"])
    score += cos_sim * 0.65

    return round(min(1.0, score), 3)


def route_prompt(prompt: str, order_by_workflow: bool = True) -> dict:
    """
    Motor Semântico Kaminho v2.0:
    1. Decompõe o texto digitado em cláusulas/intenções.
    2. Avalia semanticamente cada trecho contra o Grafo Semântico e contra os 41 agentes / 1.281 skills do catálogo.
    3. Constrói um Pipeline Multi-Agente quando múltiplas intenções são detectadas no mesmo texto.
    """
    t0 = time.perf_counter()
    catalog_path = os.path.join(BASE_DIR, "kaminho-index.json")
    catalog = {"agents": [], "skills": []}
    if os.path.exists(catalog_path):
        with open(catalog_path, "r", encoding="utf-8") as f:
            catalog = json.load(f)

    clauses = decompose_prompt_into_clauses(prompt)
    detected_steps = []
    used_intent_ids = set()

    # Avalia cada cláusula para encontrar sua intenção semântica dominante
    for idx, cl in enumerate(clauses):
        ranked = []
        for node in SEMANTIC_INTENT_GRAPH:
            sc = score_clause_against_node(cl, node)
            if sc >= 0.24:
                ranked.append((sc, node))
        ranked.sort(reverse=True, key=lambda x: x[0])

        if ranked:
            best_sc, best_node = ranked[0]
            # Se o melhor nó já foi usado mas há um segundo nó forte na mesma cláusula, usa o segundo
            if best_node["id"] in used_intent_ids and len(ranked) > 1 and ranked[1][0] >= 0.26:
                best_sc, best_node = ranked[1]

            if best_node["id"] not in used_intent_ids:
                used_intent_ids.add(best_node["id"])
                detected_steps.append({
                    "clause_index": idx + 1,
                    "phase_priority": best_node["phase_priority"],
                    "detected_excerpt": cl,
                    "semantic_intent": best_node["intent"],
                    "confidence": best_sc,
                    "agent": best_node["agent"],
                    "skills": list(best_node["skills"])
                })
            else:
                # Atualiza o trecho se a cláusula complementar a mesma intenção (ex.: "Crie um artigo" + "linguagem humana")
                for existing in detected_steps:
                    if existing["semantic_intent"] == best_node["intent"]:
                        if cl not in existing["detected_excerpt"]:
                            existing["detected_excerpt"] += f" + {cl}"
                        existing["confidence"] = round(max(existing["confidence"], best_sc), 3)
                        break

    # Também faz varredura global no prompt inteiro para capturar intenções implícitas que cruzam cláusulas
    for node in SEMANTIC_INTENT_GRAPH:
        if node["id"] not in used_intent_ids:
            full_sc = score_clause_against_node(prompt, node)
            if full_sc >= 0.42:
                used_intent_ids.add(node["id"])
                detected_steps.append({
                    "clause_index": len(detected_steps) + 1,
                    "phase_priority": node["phase_priority"],
                    "detected_excerpt": prompt[:90],
                    "semantic_intent": node["intent"],
                    "confidence": full_sc,
                    "agent": node["agent"],
                    "skills": list(node["skills"])
                })

    # Fallback para busca semântica direta nos 41 agentes e 1.281 skills do catálogo se nenhum nó do grafo atingir o limiar
    p_norm = normalize_text(prompt)
    p_vec = char_ngrams(p_norm)
    words = [w for w in re.findall(r"[a-z0-9]{4,}", p_norm)]

    if not detected_steps:
        best_agent = "@orchestrator"
        best_ag_score = 0.0
        for ag in catalog.get("agents", []):
            ag_name = ag["name"].lstrip("@").lower()
            desc_norm = normalize_text(ag.get("description", ""))
            sc = cosine_similarity_counters(p_vec, char_ngrams(ag_name + " " + desc_norm))
            if ag_name in p_norm or ag_name.replace("-", " ") in p_norm:
                sc += 0.5
            for w in words:
                if w in desc_norm:
                    sc += 0.08
            if sc > best_ag_score:
                best_ag_score = sc
                best_agent = ag["name"]

        scored_sk = []
        for sk in catalog.get("skills", []):
            sk_name = sk["name"].strip("\"'").lower()
            desc_norm = normalize_text(sk.get("description", ""))
            s_sc = 0.0
            if len(sk_name) > 2 and (sk_name in p_norm or sk_name.replace("-", " ") in p_norm):
                s_sc += 0.6
            for w in words:
                if w in desc_norm:
                    s_sc += 0.08
            if s_sc >= 0.16:
                scored_sk.append((s_sc, sk_name))
        scored_sk.sort(reverse=True, key=lambda x: x[0])
        top_fallback_skills = [s[1] for s in scored_sk[:3]]

        detected_steps.append({
            "clause_index": 1,
            "phase_priority": 30,
            "detected_excerpt": prompt,
            "semantic_intent": "Roteamento Semântico Geral pelo Catálogo",
            "confidence": round(min(1.0, best_ag_score), 3),
            "agent": best_agent,
            "skills": top_fallback_skills
        })

    # Ordena as etapas pela lógica de engenharia (1. Perguntar/Alinhar -> 2. Pesquisar Dados -> 3. Planejar -> 4. Escrever/Humanizar)
    if order_by_workflow and len(detected_steps) > 1:
        detected_steps.sort(key=lambda s: (s["phase_priority"], s["clause_index"]))

    # Numera os passos finais e consolida agentes e as principais skills de cada etapa do pipeline
    pipeline_steps = []
    all_agents = []
    all_skills = []
    for i, st in enumerate(detected_steps, start=1):
        ag = st["agent"]
        if ag not in all_agents:
            all_agents.append(ag)
        for sk in st["skills"][:2]:
            if sk not in all_skills:
                all_skills.append(sk)
        pipeline_steps.append({
            "step": i,
            "semantic_intent": st["semantic_intent"],
            "detected_excerpt": st["detected_excerpt"],
            "confidence": st["confidence"],
            "agent": ag,
            "skills": st["skills"]
        })
    for st in detected_steps:
        for sk in st["skills"][2:]:
            if sk not in all_skills:
                all_skills.append(sk)

    is_multi_step = len(pipeline_steps) > 1
    primary_agent = pipeline_steps[0]["agent"] if pipeline_steps else "@orchestrator"
    elapsed_ms = (time.perf_counter() - t0) * 1000

    if is_multi_step:
        chain_str = " → ".join(
            f"[{s['step']}] {s['agent']} ({', '.join(s['skills'][:2])})"
            for s in pipeline_steps
        )
        announcement = f"🤖 Applying knowledge of @[kaminho v2.0 Semântico] → Pipeline: {chain_str}"
    else:
        announcement = f"🤖 Applying knowledge of @[kaminho v2.0 Semântico] → {primary_agent} + {all_skills[:3]}"

    return {
        "router": "Kaminho v2.0 Semantic & Multi-Agent Pipeline (by Mizael Souto)",
        "mode": "multi-agent-pipeline" if is_multi_step else "single-specialist",
        "primary_agent": primary_agent,
        "agents_in_pipeline": all_agents,
        "recommended_skills": all_skills[:8],
        "semantic_pipeline": pipeline_steps,
        "latency_ms": round(elapsed_ms, 2),
        "announcement": announcement
    }


def read_markdown_source(md_path: str):
    """Lê um índice ou documento .md extraindo tabelas, frontmatter e seções."""
    with open(md_path, "r", encoding="utf-8", errors="ignore") as f:
        text = f.read()
    entries = []
    for line in text.splitlines():
        if (
            line.startswith("|")
            and not line.startswith("| :---")
            and not line.startswith("| Agente")
            and not line.startswith("| Skill")
            and not line.startswith("| Nome")
            and not line.startswith("| Intenção")
        ):
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
    parser = argparse.ArgumentParser(description="Kaminho v2.0 Semantic CLI & Reader (.md, .html, .json) — Desenvolvido por Mizael Souto")
    parser.add_argument("--route", type=str, default="", help="Frase/prompt complexo para análise semântica e geração de pipeline de agentes/skills")
    parser.add_argument("--pipeline", type=str, default="", help="Alias para --route com decomposição semântica multi-etapas")
    parser.add_argument("--preserve-order", action="store_true", help="Mantém a ordem literal das frases em vez da ordem lógica de engenharia")
    parser.add_argument("--format", choices=["md", "html", "json"], default="md", help="Formato do índice a ser lido (padrão: md)")
    parser.add_argument("--query", type=str, default="", help="Termo ou contexto para buscar no índice")
    parser.add_argument("--file", type=str, default="", help="Caminho de um arquivo .md ou .html específico para inspecionar")
    args = parser.parse_args()

    prompt_to_route = args.route or args.pipeline
    if prompt_to_route:
        res = route_prompt(prompt_to_route, order_by_workflow=not args.preserve_order)
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

        q = normalize_text(args.query)
        if q:
            matched = []
            q_vec = char_ngrams(q)
            for it in items:
                nm = normalize_text(it.get("name", ""))
                ds = normalize_text(it.get("description", ""))
                if q in nm or q in ds:
                    matched.append((1.0, it))
                else:
                    sim = cosine_similarity_counters(q_vec, char_ngrams(nm + " " + ds))
                    if sim >= 0.25:
                        matched.append((sim, it))
            matched.sort(reverse=True, key=lambda x: x[0])
            items = [m[1] for m in matched]

        elapsed = (time.perf_counter() - t0) * 1000
        print(f"[Kaminho v2.0 Semantic Reader ({args.format.upper()})] {len(items)} registros encontrados em {elapsed:.2f} ms")
        for it in items[:10]:
            print(f" - {it.get('name')}: {it.get('description')[:110]}")
