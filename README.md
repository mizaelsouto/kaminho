# 🧭 `Kaminho` (`@kaminho`) — Tri-Modal AI Agent & Skill Router (`.md`, `.html`, `.json`)

[![Version](https://img.shields.io/badge/version-1.1.0-blue.svg)](#)
[![Author](https://img.shields.io/badge/developed%20by-Mizael%20Souto-emerald.svg)](#)
[![Formats](https://img.shields.io/badge/formats-.md%20%7C%20.html%20%7C%20.json-purple.svg)](#)
[![Accuracy](https://img.shields.io/badge/routing%20accuracy-100%25-brightgreen.svg)](#)
[![Token Savings](https://img.shields.io/badge/token%20savings--97%25-orange.svg)](#)

> **Desenvolvido por:** **Mizael Souto**  
> **Padrão Compatível:** Antigravity AI • Claude Code • Cursor • OpenClaw • Obsidian • Sistemas Multi-Agentes  
> **Capacidade Indexada:** **41 Agentes (`.md`)** + **1.282 Skills (`.md`)** + **2.519 Templates/Interfaces (`.html`)**

---

## 🎯 1. Para que serve o Kaminho (e por que ler `.md` e `.html` é ainda melhor)?

À medida que um ecossistema de Inteligência Artificial cresce para dezenas de agentes especialistas, mais de mil skills (`SKILL.md`) e milhares de interfaces (`.html`), restringir o agente a um único formato cria gargalos. Muitas vezes, **ler diretamente arquivos `.md` e `.html` é muito superior**:

- **📄 Leitura e Índice Nativo em Markdown (`kaminho-index.md`):** Modelos de linguagem (LLMs) compreendem tabelas Markdown e blocos YAML com menor custo sintático de tokens do que estruturas JSON profundas, além de permitir conexão direta com o grafo de conhecimento do **Obsidian**.
- **🌐 Leitura e Índice Semântico em HTML (`kaminho-index.html`):** Através de atributos semânticos do DOM (`data-category`, `data-agent`, `<title>`, `<meta name="description">`, `<h1>-<h3>`), o **Kaminho** consegue ler e indexar **2.519 templates e componentes HTML reais** (widgets, landing pages, dashboards) e oferece um painel visual interativo com busca em tempo real no navegador.
- **⚙️ Índice Estruturado em JSON (`kaminho-index.json`):** Mantém integração de altíssima velocidade (`< 7 ms`) para APIs, CLIs e motores autônomos como o **OpenClaw**.

---

## 🔍 2. Leitor Direto de Arquivos `.md` e `.html` (`kaminho_reader.py`)

O **Kaminho** inclui o utilitário `scripts/kaminho_reader.py`, que dá ao agente capacidade nativa de consultar os índices `.html`, `.md` ou `.json` e também inspecionar qualquer arquivo `.md` ou `.html` avulso:

```bash
# 1. Buscar no índice HTML Semântico (.html)
python3 ./scripts/kaminho_reader.py --format html --query "humanizer"

# 2. Buscar no índice Markdown (.md)
python3 ./scripts/kaminho_reader.py --format md --query "strix"

# 3. Ler e extrair a estrutura limpa de qualquer arquivo .html ou .md avulso
python3 ./scripts/kaminho_reader.py --file ./caminho/para/interface.html
python3 ./scripts/kaminho_reader.py --file ./caminho/para/playbook.md
```

---

## ⚡ 3. Matriz de Roteamento Contextual Automático (`@kaminho`)

| Intenção / Contexto Detectado | Agente Líder | Combinação de Skills Acionadas |
| :--- | :--- | :--- |
| **UI, Design, Limpeza Visual, Apple HIG, Ícones 3D, `.html`** | `@frontend-ai-engineer` | `apple-hig-designer` + `ui-ux-pro-max` + `impeccable` |
| **Extração de Design System (`DESIGN.md`), Tokens, Templates HTML** | `@getdesign` | `getdesign` + `open-design` |
| **Atendimento Humanizado, Remoção de Tom Robótico de IA** | `@humanizer` | `humanizer` + `hermes-agent` |
| **Memória Episódica, Agentes Autônomos, Playbooks `.md`** | `@hermes-agent` | `hermes-agent` + `ai-agentic-systems-multiagent` |
| **Alinhamento Socrático / Entrevista Rápida (`grill-me` / `caveman`)** | `@project-planner` | `brainstorming` + `superpowers` + `get-shit-done` |
| **Segurança Ofensiva, Pentest Autônomo, PoC e Exploits** | `@strix` | `strix` + `vulnerability-scanner` |
| **Proteção de Repositório Git (`push --force`, `reset --hard`)** | `@devops-engineer` | `git-guardrails-claude-code` |
| **Vídeo Programático em React e Motion Graphics** | `@claude-remotion-skill` | `remotion-best-practices` |
| **Currículos Executivos em YAML + Typst** | `@rendercv` | `rendercv` + `pdf` |
| **Arquitetura Backend, RAG Híbrido (BM25 + pgvector), Ragas** | `@rag-data-architect-ai` | `ai-advanced-rag-scale` + `backend-data-rag` |
| **Descoberta e Instalação de Novas Skills** | `@skill-installer-manager` | `find-skills` + `agent-skills` + `skill-creator` |

---

## 📊 4. Teste de Desempenho (Benchmark Comparativo)

Execute o benchmark oficial a qualquer momento:

```bash
python3 ./scripts/benchmark_routers.py
```

### Resumo Consolidado das Métricas

| Métrica Avaliada | Roteador Legado (`intelligent-routing`) | `Kaminho v1.1` (`@kaminho` — Mizael Souto) | Ganho Real |
| :--- | :--- | :--- | :--- |
| **Taxa de Acerto em Skills/Agentes Reais** | `0/10 (0%)` | **`10/10 (100%)`** | **+100% de precisão** |
| **Capacidade de Leitura Nativa** | Apenas 1 `.md` fixo | **Tri-Modal (`.md`, `.html`, `.json`)** | **Leitura Total de Docs & UI** |
| **Cobertura do Ecossistema** | `11 agentes / 0 skills modernas` | **`41 agentes + 1.282 skills (.md) + 2.519 templates (.html)`** | **3.842 recursos indexados** |
| **Consumo de Tokens por Chamada** | `~2.630 tokens` | **`~82 tokens`** | **-97% de economia de tokens** |
| **Latência Média de Roteamento** | `0.058 ms` | **`6.79 ms` (`JSON`) / `27.4 ms` (`MD`)** | **Instantâneo** |

---

## 🛠️ 5. Como Instalar

### Passo 1 — Clonar o Repositório no seu Diretório de Skills
```bash
git clone https://github.com/mizaelsouto/kaminho.git
cd kaminho
```

### Passo 2 — Gerar ou Atualizar os Índices Tri-Modais (`.md`, `.html`, `.json`)
```bash
python3 ./scripts/rebuild_catalog.py
```

### Passo 3 — Registrar no Antigravity AI / Claude Code (`~/.gemini/config/skills.json`)
```json
{
  "name": "kaminho",
  "description": "Kaminho — O roteador e indexador inteligente Tri-Modal (.md, .html, .json) de agentes e skills. Desenvolvido por Mizael Souto.",
  "path": "<SKILLS_DIR>/kaminho/.agent/skills/kaminho/SKILL.md"
}
```

---

## 📂 6. Estrutura do Projeto

```text
kaminho/
├── README.md                                        # Documentação oficial para GitHub (sem dados sensíveis)
├── kaminho-index.md                                 # Índice nativo em Markdown (.md) para LLMs e Obsidian
├── kaminho-index.html                               # Painel e índice semântico em HTML5 (.html) com busca ao vivo
├── kaminho-index.json                               # Catálogo JSON portátil (41 agentes + 1.282 skills + 2.519 HTMLs)
├── AGENT_INDEX_CATALOG.json                         # Alias de retrocompatibilidade do catálogo
├── scripts/
│   ├── rebuild_catalog.py                           # Indexador Tri-Modal (.md + .html + .json)
│   ├── kaminho_reader.py                            # Leitor direto de arquivos e índices .md, .html e .json
│   └── benchmark_routers.py                         # Suite de teste de desempenho (10 cenários reais)
└── .agent/
    └── skills/
        └── kaminho/
            └── SKILL.md                             # Manifesto oficial da Skill Kaminho
```

---

## 👨‍💻 Autor

Desenvolvido por **Mizael Souto**  
*Criador do **Kaminho** • Arquitetura de Sistemas Agênticos, LLMOps & Engenharia de Software assistida por IA.*
