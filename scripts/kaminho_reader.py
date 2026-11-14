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


def vector_norm(c: Counter) -> float:
    return math.sqrt(sum(v * v for v in c.values()))


def cosine_similarity_counters(c1: Counter, c2: Counter, n1: float = None, n2: float = None) -> float:
    """Similaridade de cosseno entre vetores esparsos. n1/n2 = normas pré-computadas (opcional, evita recálculo)."""
    if not c1 or not c2:
        return 0.0
    if len(c1) > len(c2):
        c1, c2, n1, n2 = c2, c1, n2, n1
    num = sum(v * c2[k] for k, v in c1.items() if k in c2)
    if num == 0:
        return 0.0
    den1 = n1 if n1 is not None else vector_norm(c1)
    den2 = n2 if n2 is not None else vector_norm(c2)
    if den1 == 0 or den2 == 0:
        return 0.0
    return num / (den1 * den2)


def fold_same_length(text: str) -> str:
    """Minúsculas sem acento preservando o comprimento (índice i do resultado == índice i do original)."""
    out = []
    for ch in text.lower():
        base = [c for c in unicodedata.normalize("NFKD", ch) if not unicodedata.combining(c)]
        out.append(base[0] if len(base) == 1 else ch)
    return "".join(out)


def find_term(text: str, term: str, whole_word: bool):
    """
    Procura `term` (já normalizado) em `text` começando em limite de palavra — e terminando
    em limite também, se whole_word. Retorna (início, fim) ou None. Sem regex: nada a compilar.
    """
    n = len(term)
    start = text.find(term)
    while start != -1:
        before_ok = start == 0 or not text[start - 1].isalnum()
        end = start + n
        after_ok = not whole_word or end == len(text) or not text[end].isalnum()
        if before_ok and after_ok:
            return start, end
        start = text.find(term, start + 1)
    return None


_CATALOG_CACHE: dict = {}


def load_catalog() -> dict:
    """
    Carrega o kaminho-index.json uma única vez por processo e pré-computa os vetores de busca.
    Recarrega automaticamente se o arquivo mudar (mtime), ex.: após instalar/remover skills.
    """
    path = os.path.join(BASE_DIR, "kaminho-index.json")
    try:
        mtime = os.path.getmtime(path)
    except OSError:
        return {"agents": [], "skills": []}
    if _CATALOG_CACHE.get("mtime") == mtime:
        return _CATALOG_CACHE["data"]
    with open(path, "r", encoding="utf-8") as f:
        data = json.load(f)
    _CATALOG_CACHE.update(mtime=mtime, data=data, prepared=False)
    return data


def prepare_catalog_vectors(data: dict) -> None:
    """Pré-computa nomes/descrições normalizados e vetores — só quando o fallback pelo catálogo é usado."""
    if _CATALOG_CACHE.get("prepared") and _CATALOG_CACHE.get("data") is data:
        return
    for ag in data.get("agents", []):
        ag["_name"] = ag["name"].lstrip("@").lower()
        ag["_desc"] = normalize_text(ag.get("description", ""))
        ag["_vec"] = char_ngrams(ag["_name"] + " " + ag["_desc"])
        ag["_norm"] = vector_norm(ag["_vec"])
    for sk in data.get("skills", []):
        sk["_name"] = sk["name"].strip("\"'").lower()
        sk["_desc"] = normalize_text(sk.get("description", ""))
    if _CATALOG_CACHE.get("data") is data:
        _CATALOG_CACHE["prepared"] = True


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
            "tempo real", "extrair dados da web", "navegar no site", "last30days", "firecrawl",
            "noticias", "esta semana", "desta semana", "levantamento", "o que ha de novo", "estado da arte"
        ],
        "stems": ["atuais", "atual", "recent", "ultim", "tendenc", "pesquis", "colet", "extrair dados", "noticia", "levantament", "novidade"],
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
            "estruturar ideias", "arquitetura do plano", "resumo executivo", "prd", "spec", "roadmap", "cronograma de"
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
            "redigir texto", "post de blog", "escreva um post", "ensaio", "humanizer", "humanizar",
            "parecer escrito por ia", "nao parecer ia"
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
        "stems": ["hig", "estetic", "polim", "visual", "apple", "ui/ux"],
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
            "gerar exploit", "poc de seguranca", "teste de invasao", "strix"
        ],
        "stems": ["pentest", "exploit", "invas", "strix", "ofensiv"],
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
        "stems": ["curricul", "rendercv", "typst"],
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
            "embeddings", "reranking", "ragas", "busca semantica"
        ],
        "stems": ["rag", "vetorial", "pgvector", "bm25", "embedding", "rerank"],
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
            "procurar skill", "criar uma skill", "gerenciar skills", "atualizar skills", "atualizar as skills",
            "remover skill", "remover a skill", "remova a skill", "atualize as skills", "desinstalar", "organizar skills", "skills instaladas",
            "atualizacoes das skills", "kaminho doctor"
        ],
        "stems": ["instal", "skill", "catalogo", "asimov", "desinstal", "remov"],
        "semantic_profile": "instalar buscar descobrir novas skills catalogo asimov globalmente skill-installer"
    },
    # ---- Domínios de engenharia de software (adicionados na revisão v2.1) ----
    {
        "id": "database_modeling",
        "intent": "Modelagem de Banco de Dados, Migrations & Otimização de Queries",
        "phase_priority": 32,
        "agent": "@database-architect",
        "skills": ["database-design", "database-optimizer", "postgres-pro", "sql-pro"],
        "phrases": [
            "banco de dados", "modele o banco", "modelar o banco", "schema do banco",
            "migration", "migracao do banco", "query lenta", "otimize a query", "otimizar sql",
            "indice no banco", "tabela de", "postgres", "mysql", "sqlite"
        ],
        "stems": ["sql", "query", "queries", "migrat", "migration", "schema", "postgres", "tabela", "indice", "banco"],
        "semantic_profile": "modelar banco de dados schema tabelas migrations indices otimizar query sql lenta postgres mysql"
    },
    {
        "id": "backend_api",
        "intent": "Backend, APIs REST/GraphQL & Endpoints",
        "phase_priority": 38,
        "agent": "@backend-specialist",
        "skills": ["api-patterns", "api-designer", "backend-architecture-design", "fastapi-expert"],
        "phrases": [
            "api rest", "uma api", "endpoint", "endpoints", "rota da api", "graphql", "webhook",
            "middleware", "autenticacao", "login com jwt", "implemente o login", "upload de arquivos",
            "servidor node", "fastapi", "express"
        ],
        "stems": ["api", "endpoint", "backend", "servidor", "jwt", "oauth", "webhook", "graphql", "middleware"],
        "semantic_profile": "backend api rest graphql endpoints rotas servidor autenticacao jwt oauth middleware webhook upload"
    },
    {
        "id": "frontend_build",
        "intent": "Construção de Frontend: Páginas, Componentes & Dashboards",
        "phase_priority": 40,
        "agent": "@frontend-specialist",
        "skills": ["frontend-design", "react-best-practices", "nextjs", "web-design-guidelines"],
        "phrases": [
            "dashboard", "componente", "landing page", "pagina web", "tela de", "layout responsivo",
            "responsivo", "tailwind", "react", "next.js", "nextjs", "css", "formulario web", "interface"
        ],
        "stems": ["component", "dashboard", "pagina", "tela", "layout", "responsiv", "tailwind", "react", "nextjs", "css", "frontend", "botao", "card"],
        "semantic_profile": "construir frontend pagina componente dashboard card layout responsivo react nextjs tailwind css interface web"
    },
    {
        "id": "mobile_app",
        "intent": "Aplicativos Mobile (React Native, iOS, Android)",
        "phase_priority": 40,
        "agent": "@mobile-developer",
        "skills": ["mobile-design", "react-native-expert", "mobile-app"],
        "phrases": ["app mobile", "aplicativo", "react native", "android", "flutter", "expo"],
        "stems": ["mobile", "aplicativo", "android", "flutter", "expo"],
        "semantic_profile": "criar aplicativo app mobile celular react native android ios flutter expo"
    },
    {
        "id": "debugging",
        "intent": "Depuração: Bugs, Erros & Falhas em Execução",
        "phase_priority": 42,
        "agent": "@debugger",
        "skills": ["systematic-debugging", "debugging-wizard"],
        "phrases": [
            "corrija o bug", "corrigir o bug", "corrija o erro", "bug no", "bug do", "dando erro",
            "nao funciona", "parou de funcionar", "erro 500", "stack trace", "esta quebrando",
            "crash", "exception", "debug", "nao responde", "nao carrega", "travando", "conserte",
            "comportamento estranho", "nao salva", "deu pau"
        ],
        "stems": ["bug", "erro", "debug", "depur", "crash", "falha", "quebr", "exception", "traceback", "trav", "consert"],
        "semantic_profile": "corrigir bug erro falha crash depurar debug excecao stack trace nao funciona quebrado investigar causa"
    },
    {
        "id": "performance_optimization",
        "intent": "Performance, Lighthouse & Core Web Vitals",
        "phase_priority": 47,
        "agent": "@performance-optimizer",
        "skills": ["performance-profiling", "frontend-testing-performance-sec"],
        "phrases": ["performance", "esta lenta", "esta lento", "lighthouse", "core web vitals", "tempo de carregamento",
                    "demora para abrir", "demora para carregar", "muito lento", "segundos para abrir"],
        "stems": ["performance", "lent", "lighthouse", "otimiz", "carregament", "vitals", "demor"],
        "semantic_profile": "melhorar performance pagina lenta lighthouse core web vitals tempo de carregamento profiling otimizar"
    },
    {
        "id": "seo",
        "intent": "SEO & Visibilidade em Buscadores",
        "phase_priority": 46,
        "agent": "@seo-specialist",
        "skills": ["seo-audit", "seo-fundamentals", "programmatic-seo", "ai-seo"],
        "phrases": ["seo", "google search", "ranquear", "meta tags", "sitemap", "palavras-chave"],
        "stems": ["seo", "ranque", "sitemap", "indexac", "buscador"],
        "semantic_profile": "melhorar seo ranquear no google meta tags sitemap palavras chave indexacao buscadores"
    },
    {
        "id": "testing_qa",
        "intent": "Testes Automatizados (Unitários, Integração, E2E)",
        "phase_priority": 50,
        "agent": "@test-engineer",
        "skills": ["tdd-workflow", "webapp-testing", "playwright-skill"],
        "phrases": [
            "testes e2e", "teste e2e", "testes unitarios", "teste unitario", "testes de integracao",
            "escreva testes", "adicione testes", "cobertura de testes", "playwright", "jest", "vitest", "pytest", "tdd"
        ],
        "stems": ["teste", "testes", "e2e", "unitari", "cobertura", "playwright", "jest", "vitest", "pytest", "tdd"],
        "semantic_profile": "escrever testes automatizados unitarios integracao e2e playwright jest vitest pytest cobertura tdd qa"
    },
    {
        "id": "security_audit",
        "intent": "Auditoria de Segurança Defensiva & Revisão de Código Seguro",
        "phase_priority": 52,
        "agent": "@security-auditor",
        "skills": ["security-reviewer", "secure-code-guardian", "vulnerability-scanner"],
        "phrases": [
            "auditoria de seguranca", "auditoria de codigo", "revise o codigo", "procurando vulnerabilidades",
            "vulnerabilidades", "codigo seguro", "owasp", "revisao de seguranca", "falhas de seguranca",
            "sql injection", "xss", "csrf", "vazamento de dados", "secrets expostos"
        ],
        "stems": ["seguranc", "vulnerab", "auditor", "owasp", "segur", "injection", "xss", "csrf", "vazament"],
        "semantic_profile": "auditoria de seguranca defensiva revisar codigo vulnerabilidades owasp codigo seguro revisao"
    },
    {
        "id": "devops_deploy",
        "intent": "DevOps: Deploy, Docker, CI/CD & Infraestrutura",
        "phase_priority": 58,
        "agent": "@devops-engineer",
        "skills": ["deployment-procedures", "docker-management", "devops-engineer"],
        "phrases": [
            "deploy", "faca o deploy", "docker", "kubernetes", "ci/cd", "pipeline de ci", "github actions",
            "publicar em producao", "vercel", "servidor vps", "nginx"
        ],
        "stems": ["deploy", "docker", "kubernet", "ci/cd", "infra", "producao", "vercel", "nginx", "github actions"],
        "semantic_profile": "deploy docker kubernetes ci cd pipeline github actions infraestrutura producao vercel vps nginx"
    }
]

# Pré-computa os vetores de n-gramas para cada nó semântico (executa em ~0.3ms na importação)
for _node in SEMANTIC_INTENT_GRAPH:
    _node["_ngram_vec"] = char_ngrams(
        _node["semantic_profile"] + " " + " ".join(_node["phrases"])
    )
    _node["_ngram_norm"] = vector_norm(_node["_ngram_vec"])
    _node["_phrases_n"] = [normalize_text(p) for p in _node["phrases"]]
    _node["_stems_n"] = [normalize_text(st) for st in _node["stems"]]


# Verbos/expressões que abrem uma nova etapa quando vêm depois de "," ou " e ".
_ACTION_STARTERS = (
    r"(?:me\s+pergunt|pergunt|mostr|ger[ea]|cri[ea]|us[ea]|aplic|fac[ao]|escrev|redij|adicion|inclu|"
    r"implement|configur|corrij|corrig|test[ea]|revis|otimiz|melhor|publiq|document|mont[ea]|"
    r"pesquis|extrai|model|instal|integr|depois|com\s+uma\s+linguagem|uma\s+linguagem|"
    r"tom\s+humano|tom\s+natural)"
)

# Separadores discursivos de múltiplas intenções em português (aplicados ao texto sem acento).
_CLAUSE_SPLIT = re.compile(
    r"\s*,?\s*\be\s+depois(?:\s+disso)?,?\s+"
    r"|\s*,\s*depois(?:\s+disso)?,?\s+"
    r"|\s*,?\s*(?:\be\s+)?em\s+seguida,?\s+"
    r"|\s*,?\s*(?:\be\s+)?alem\s+disso,?\s+"
    r"|\s*,?\s*\be\s+tambem\s+"
    r"|\s*,?\s*\b(?:e\s+)?por\s+fim,?\s+"
    r"|\s*;\s*"
    r"|\s*\.\s+(?=[a-z])"
    r"|\s*,\s*(?:e\s+)?(?=" + _ACTION_STARTERS + r")"
    r"|\s+e\s+(?=" + _ACTION_STARTERS + r")"
)


def decompose_prompt_into_clauses(prompt: str) -> list:
    """
    Quebra um texto complexo do usuário em orações/segmentos semânticos preservando o sentido de cada etapa.
    Exemplo:
      "Crie um artigo que mostre dados atuais, me pergunte quais dados desejo, e depois gere um plano resumido e uma linguagem bem proxima da humana."
    """
    # O casamento é feito numa versão sem acento e com o MESMO comprimento do original,
    # então os índices encontrados recortam o texto original (com acentos) sem deslocamento.
    folded = fold_same_length(prompt)
    pieces, last = [], 0
    for m in _CLAUSE_SPLIT.finditer(folded):
        pieces.append(prompt[last:m.start()])
        last = m.end()
    pieces.append(prompt[last:])
    raw_clauses = [c.strip(" ,.;:") for c in pieces if len(c.strip(" ,.;:")) >= 4]

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


# Pesos da pontuação híbrida. Cada componente tem teto próprio, então a confiança
# fica distribuída em 0–1 em vez de saturar em 1.0 com qualquer acerto.
W_PHRASE_FIRST, W_PHRASE_EXTRA, CAP_PHRASE = 0.45, 0.08, 0.60
W_STEM, CAP_STEM = 0.22, 0.40
W_COSINE = 0.40
COSINE_ONLY_MIN = 0.45        # sem frase/radical, o cosseno sozinho precisa ser alto para valer
CLAUSE_THRESHOLD = 0.24       # nota mínima para uma cláusula ativar um nó
SECOND_BEST_THRESHOLD = 0.30  # 2º colocado quando o 1º já foi usado em outra cláusula
MULTI_INTENT_THRESHOLD = 0.50 # 2ª intenção na MESMA cláusula ("tela de login no estilo macos")
GLOBAL_THRESHOLD = 0.62       # varredura do prompt inteiro (exige frase + reforço)
FALLBACK_MIN = 0.35           # abaixo disso o fallback admite dúvida e devolve @orchestrator


def match_node(norm_cl: str, vec: Counter, node: dict, vec_norm: float = None):
    """
    Pontua uma cláusula (já normalizada) contra um nó de intenção.
    Retorna (nota, trechos) — trechos = intervalos (início, fim) casados por frases/radicais,
    usados para detectar quando um termo está contido em outro já reconhecido.
    """
    spans = []
    phrase_hits = stem_hits = 0
    for p in node["_phrases_n"]:
        span = find_term(norm_cl, p, True)
        if span:
            phrase_hits += 1
            spans.append(span)
    for st in node["_stems_n"]:
        span = find_term(norm_cl, st, False)
        if span:
            stem_hits += 1
            spans.append(span)

    cos = cosine_similarity_counters(vec, node["_ngram_vec"], vec_norm, node["_ngram_norm"])
    if not phrase_hits and not stem_hits and cos < COSINE_ONLY_MIN:
        return 0.0, []

    score = 0.0
    if phrase_hits:
        score += min(CAP_PHRASE, W_PHRASE_FIRST + W_PHRASE_EXTRA * (phrase_hits - 1))
    score += min(CAP_STEM, W_STEM * stem_hits)
    score += cos * W_COSINE
    return round(min(1.0, score), 3), spans


def score_clause_against_node(clause: str, node: dict) -> float:
    """Pontuação semântica híbrida (frases-conceito + radicais + cosseno de n-gramas) de uma cláusula."""
    norm = normalize_text(clause)
    return match_node(norm, char_ngrams(norm), node)[0] if norm else 0.0


def rank_nodes(clause: str, threshold: float) -> list:
    """Retorna [(nota, nó, trechos)] acima do limiar, do maior para o menor."""
    norm = normalize_text(clause)
    if not norm:
        return []
    vec = char_ngrams(norm)
    vnorm = vector_norm(vec)
    ranked = []
    for node in SEMANTIC_INTENT_GRAPH:
        sc, spans = match_node(norm, vec, node, vnorm)
        if sc >= threshold:
            ranked.append((sc, node, spans))
    ranked.sort(reverse=True, key=lambda x: x[0])
    return ranked


def _is_shadowed(spans: list, covered: list) -> bool:
    """True se todo termo casado está dentro de um termo maior já reconhecido (ex.: 'react' dentro de 'react native')."""
    if not spans or not covered:
        return False
    return all(any(cs <= s and e <= ce for cs, ce in covered) for s, e in spans)


def route_prompt(prompt: str, order_by_workflow: bool = True) -> dict:
    """
    Motor Semântico Kaminho v2.0:
    1. Decompõe o texto digitado em cláusulas/intenções.
    2. Avalia semanticamente cada trecho contra o Grafo Semântico e contra os 41 agentes / 1.281 skills do catálogo.
    3. Constrói um Pipeline Multi-Agente quando múltiplas intenções são detectadas no mesmo texto.
    """
    t0 = time.perf_counter()
    catalog = load_catalog()

    clauses = decompose_prompt_into_clauses(prompt)
    detected_steps = []
    used_intent_ids = set()

    def add_step(node, sc, excerpt, clause_index):
        if node["id"] in used_intent_ids:
            # Cláusula complementar da mesma intenção (ex.: "Crie um artigo" + "linguagem humana")
            for existing in detected_steps:
                if existing["semantic_intent"] == node["intent"]:
                    if excerpt not in existing["detected_excerpt"]:
                        existing["detected_excerpt"] += f" + {excerpt}"
                    existing["confidence"] = round(max(existing["confidence"], sc), 3)
                    break
            return
        used_intent_ids.add(node["id"])
        detected_steps.append({
            "clause_index": clause_index,
            "phase_priority": node["phase_priority"],
            "detected_excerpt": excerpt,
            "semantic_intent": node["intent"],
            "confidence": sc,
            "agent": node["agent"],
            "skills": list(node["skills"])
        })

    # 1. Cada cláusula ativa sua intenção dominante e, se houver, uma 2ª intenção forte e independente
    for idx, cl in enumerate(clauses):
        ranked = rank_nodes(cl, CLAUSE_THRESHOLD)
        if not ranked:
            continue
        best_sc, best_node, best_spans = ranked[0]
        best_was_reused = best_node["id"] in used_intent_ids
        add_step(best_node, best_sc, cl, idx + 1)
        covered = list(best_spans)
        for sc, node, spans in ranked[1:]:
            if node["agent"] == best_node["agent"] or _is_shadowed(spans, covered):
                continue
            strong_enough = sc >= MULTI_INTENT_THRESHOLD or (best_was_reused and sc >= SECOND_BEST_THRESHOLD)
            if strong_enough and node["id"] not in used_intent_ids:
                add_step(node, sc, cl, idx + 1)
                covered.extend(spans)
            break  # no máximo uma intenção extra por cláusula

    # 2. Varredura do prompt inteiro: intenções implícitas que cruzam cláusulas,
    #    ignorando termos contidos em termos já reconhecidos
    full_norm = normalize_text(prompt)
    full_vec = char_ngrams(full_norm)
    node_by_id = {n["id"]: n for n in SEMANTIC_INTENT_GRAPH}
    covered_full = []
    for nid in used_intent_ids:
        covered_full.extend(match_node(full_norm, full_vec, node_by_id[nid])[1])
    for full_sc, node, spans in rank_nodes(prompt, GLOBAL_THRESHOLD):
        if node["id"] not in used_intent_ids and not _is_shadowed(spans, covered_full):
            add_step(node, full_sc, prompt[:90], len(detected_steps) + 1)
            covered_full.extend(spans)

    # Fallback para busca semântica direta nos 41 agentes e 1.281 skills do catálogo se nenhum nó do grafo atingir o limiar
    p_norm = normalize_text(prompt)
    p_vec = char_ngrams(p_norm)
    words = [w for w in re.findall(r"[a-z0-9]{4,}", p_norm)]

    if not detected_steps:
        prepare_catalog_vectors(catalog)
        best_agent = "@orchestrator"
        best_ag_score = 0.0
        for ag in catalog.get("agents", []):
            ag_name, desc_norm = ag["_name"], ag["_desc"]
            sc = cosine_similarity_counters(p_vec, ag["_vec"], None, ag["_norm"])
            if ag_name in p_norm or ag_name.replace("-", " ") in p_norm:
                sc += 0.5
            for w in words:
                if w in desc_norm:
                    sc += 0.08
            if sc > best_ag_score:
                best_ag_score = sc
                best_agent = ag["name"]

        if best_ag_score < FALLBACK_MIN:
            best_agent = "@orchestrator"  # sinal fraco: melhor delegar ao orquestrador do que chutar um especialista

        scored_sk = []
        for sk in catalog.get("skills", []):
            sk_name, desc_norm = sk["_name"], sk["_desc"]
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
            "low_confidence": best_ag_score < FALLBACK_MIN,
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
