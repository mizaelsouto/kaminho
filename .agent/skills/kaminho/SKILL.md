---
name: kaminho
description: Kaminho v2.0 — O roteador semântico, decompositor de intenções multi-agente e indexador inteligente Tri-Modal (.md, .html, .json) de agentes, skills e templates HTML. Reconhece por semântica o que está sendo digitado, decompõe pedidos complexos em pipelines multi-especialistas e lê nativamente arquivos .md e .html em milissegundos com 97% de economia de tokens. Desenvolvido por Mizael Souto.
author: Mizael Souto
version: 2.0.0
aliases: [agent-indexer-router, semantic-router]
supported_formats: [md, html, json]
---

# 🧭 Kaminho v2.0 (`@kaminho`) — Motor Semântico, Decompositor Multi-Agente & Router Tri-Modal (`.md`, `.html`, `.json`)

> **Desenvolvido por:** **Mizael Souto**  
> **Versão:** `2.0.0` (Reconhecimento Semântico por Cosseno de N-Gramas + Radicais Morfológicos + Decomposição de Pipelines Multi-Agente)  
> **Ecossistema Indexado:** **41 Agentes (`.md`)** + **1.281 Skills (`.md`)** + **2.519 Templates/Interfaces (`.html`)**

---

## 🧠 1. O que há de novo no Kaminho v2.0 (Reconhecimento Semântico & Pipeline Multi-Agente)?

Ao contrário de roteadores tradicionais baseados apenas em palavras-chave exatas, o **Kaminho v2.0** analisa a **intenção semântica** do que o usuário está digitando e separa pedidos compostos em um **Pipeline de Execução Multi-Especialista**:

1. **Compreensão Semântica (Sem precisar digitar o nome da ferramenta):**
   - *"me pergunte quais dados desejo"* ➔ Reconhece **Entrevista Socrática & Levantamento de Requisitos** (`@project-planner` + `grill-me`, `brainstorming`)
   - *"mostre dados atuais"* ➔ Reconhece **Pesquisa de Dados Atuais & Tendências** (`@explorer-agent` + `last30days`, `firecrawl-agent`)
   - *"depois gere um plano resumido"* ➔ Reconhece **Planejamento Estruturado & Síntese** (`@project-planner` + `plan-writing`, `superpowers`)
   - *"linguagem bem próxima da humana"* ➔ Reconhece **Redação Humanizada Anti-IA** (`@humanizer` + `humanizer`, `doc-coauthoring`)

2. **Ordenação Inteligente de Engenharia:**
   Mesmo que o usuário escreva as ideias fora de ordem na frase, o Kaminho v2.0 organiza o pipeline na sequência lógica ideal:
   `[1] Alinhar/Perguntar` ➔ `[2] Pesquisar Dados` ➔ `[3] Planejar/Arquitetar` ➔ `[4] Criar/Redigir/Humanizar` ➔ `[5] Auditar/Proteger`.

---

## 🔍 2. Comandos do Motor Semântico (`kaminho_reader.py`)

1. **Roteamento Semântico & Decomposição de Pipeline (`--route` ou `--pipeline`):**
   ```bash
   python3 "/Users/upper/Documents/Projetos /1_I-A_Skills/kaminho/scripts/kaminho_reader.py" --route "Crie um artigo que mostre dados atuais, me pergunte quais dados desejo, e depois gere um plano resumido e uma linguagem bem proxima da humana."
   ```
2. **Manter a ordem literal das frases (`--preserve-order`):**
   ```bash
   python3 "/Users/upper/Documents/Projetos /1_I-A_Skills/kaminho/scripts/kaminho_reader.py" --route "<TEXTO>" --preserve-order
   ```
3. **Busca Semântica e Léxica nos Índices (`.md`, `.html`, `.json`):**
   ```bash
   python3 "/Users/upper/Documents/Projetos /1_I-A_Skills/kaminho/scripts/kaminho_reader.py" --format md --query "linguagem humana"
   python3 "/Users/upper/Documents/Projetos /1_I-A_Skills/kaminho/scripts/kaminho_reader.py" --format html --query "apple hig"
   ```
4. **Inspeção Limpa de Qualquer Arquivo `.md` ou `.html`:**
   ```bash
   python3 "/Users/upper/Documents/Projetos /1_I-A_Skills/kaminho/scripts/kaminho_reader.py" --file ./caminho/para/arquivo.html
   ```

---

## ⚡ 3. Grafo Semântico de Intenções (`@kaminho v2.0`)

| Conceito Semântico Reconhecido | Fase | Agente Líder | Skills Acionadas Automaticamente |
| :--- | :-: | :--- | :--- |
| **Entrevista Socrática & Levantamento de Requisitos** (*"me pergunte"*, *"tire dúvidas"*, *"quais dados desejo"*) | `10` | `@project-planner` | `grill-me`, `brainstorming`, `caveman` |
| **Descoberta & Instalação Global de Skills** (*"instalar skill"*, *"catálogo asimov"*) | `15` | `@skill-installer-manager` | `skill-installer-asimov`, `find-skills`, `agent-skills` |
| **Pesquisa de Dados Atuais & Web Scraping** (*"dados atuais"*, *"últimos 30 dias"*, *"tendências"*) | `20` | `@explorer-agent` | `last30days`, `firecrawl-agent` |
| **Planejamento Estruturado & Plano Resumido** (*"plano resumido"*, *"etapas"*, *"passo a passo"*) | `30` | `@project-planner` | `plan-writing`, `superpowers`, `get-shit-done` |
| **Extração de Design System (`DESIGN.md`) & Prototipagem** (*"extrair paleta"*, *"tokens"*) | `35` | `@getdesign` | `getdesign`, `open-design`, `theme-factory` |
| **Memória Episódica & Agentes Autônomos** (*"memória episódica"*, *"hermes"*, *"openclaw"*) | `35` | `@hermes-agent` | `hermes-agent`, `ai-agentic-systems-multiagent` |
| **Redação Humanizada & Linguagem Natural (Anti-IA)** (*"próxima da humana"*, *"sem tom robótico"*, *"artigo"*) | `40` | `@humanizer` | `humanizer`, `doc-coauthoring`, `internal-comms` |
| **Design de Interface, Apple HIG & Polimento Visual** (*"interface limpa"*, *"estilo apple"*, *"ui/ux"*) | `40` | `@frontend-ai-engineer` | `apple-hig-designer`, `ui-ux-pro-max`, `impeccable` |
| **Arquitetura RAG Híbrida & Banco Vetorial** (*"busca híbrida"*, *"pgvector"*, *"bm25"*) | `40` | `@rag-data-architect-ai` | `ai-advanced-rag-scale`, `backend-data-rag` |
| **Documentos Executivos (Word, PDF, Excel, Slides)** (*"gerar pdf"*, *"docx"*, *"apresentação"*) | `45` | `@documentation-writer` | `docx`, `pdf`, `pptx`, `xlsx` |
| **Vídeo Programático em React & Motion Graphics** (*"vídeo em react"*, *"remotion"*) | `45` | `@claude-remotion-skill` | `remotion-best-practices` |
| **Currículos Profissionais em YAML + Typst** (*"currículo"*, *"rendercv"*, *"typst"*) | `45` | `@rendercv` | `rendercv`, `pdf` |
| **Segurança Ofensiva, Pentest & Exploits PoC** (*"pentest"*, *"vulnerabilidades"*, *"strix"*) | `50` | `@strix` | `strix`, `vulnerability-scanner`, `trailofbits-security` |
| **Proteção de Comandos Git & Guardrails** (*"bloquear git push"*, *"reset hard"*) | `55` | `@devops-engineer` | `git-guardrails-claude-code` |

---
*Desenvolvido por **Mizael Souto** — Criador do **Kaminho v2.0** • Engenharia de Sistemas Agênticos & Arquitetura Semântica de IA.*
