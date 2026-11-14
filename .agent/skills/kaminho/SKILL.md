---
name: kaminho
description: Kaminho v2.0 — O roteador semântico, decompositor de intenções multi-agente e indexador inteligente Tri-Modal (.md, .html, .json) de agentes, skills e templates HTML. Reconhece por semântica o que está sendo digitado, decompõe pedidos complexos em pipelines multi-especialistas e lê nativamente arquivos .md e .html em milissegundos com 97% de economia de tokens. Desenvolvido por Mizael Souto.
author: Mizael Souto
version: 2.1.0
aliases: [agent-indexer-router, semantic-router]
supported_formats: [md, html, json]
---

# 🧭 Kaminho v2.0 (`@kaminho`) — Motor Semântico, Decompositor Multi-Agente & Router Tri-Modal (`.md`, `.html`, `.json`)

> **Desenvolvido por:** **Mizael Souto**  
> **Versão:** `2.1.0` (Reconhecimento Semântico por Cosseno de N-Gramas + Radicais Morfológicos + Decomposição de Pipelines Multi-Agente)  
> **Ecossistema Indexado:** **41 Agentes (`.md`)** + **1.281 Skills (`.md`)** + **2.519 Templates/Interfaces (`.html`)**

---

## 🚦 0. Regra de Acesso (Kaminho é o único ponto de entrada)

- As demais skills da biblioteca `1_I-A_Skills` **não estão instaladas** no Claude. Não procure por elas em `~/.claude/skills/`.
- Só use uma skill/agente quando o usuário **pedir pelo nome** ou chamar o Kaminho. Não acione skills por conta própria.
- Para achar uma skill: rode `kaminho_reader.py --route "<pedido>"` ou `--query "<nome>"`, pegue o `path` no índice (relativo a `<SKILLS_DIR>/`, a pasta onde as skills estão instaladas — a mesma que contém `kaminho/`) e leia o `SKILL.md` com Read.
- Se o roteamento cobrir só parte do pedido, avise o usuário e complete a busca com `--query`.

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
   python3 "<SKILLS_DIR>/kaminho/scripts/kaminho_reader.py" --route "Crie um artigo que mostre dados atuais, me pergunte quais dados desejo, e depois gere um plano resumido e uma linguagem bem proxima da humana."
   ```
2. **Manter a ordem literal das frases (`--preserve-order`):**
   ```bash
   python3 "<SKILLS_DIR>/kaminho/scripts/kaminho_reader.py" --route "<TEXTO>" --preserve-order
   ```
3. **Busca Semântica e Léxica nos Índices (`.md`, `.html`, `.json`):**
   ```bash
   python3 "<SKILLS_DIR>/kaminho/scripts/kaminho_reader.py" --format md --query "linguagem humana"
   python3 "<SKILLS_DIR>/kaminho/scripts/kaminho_reader.py" --format html --query "apple hig"
   ```
4. **Inspeção Limpa de Qualquer Arquivo `.md` ou `.html`:**
   ```bash
   python3 "<SKILLS_DIR>/kaminho/scripts/kaminho_reader.py" --file ./caminho/para/arquivo.html
   ```

---

## ⚡ 3. Grafo Semântico de Intenções (`@kaminho v2.0`)

| Conceito Semântico Reconhecido | Fase | Agente Líder | Skills Acionadas Automaticamente |
| :--- | :-: | :--- | :--- |
| **Entrevista Socrática & Levantamento de Requisitos** (*"me pergunte"*, *"tire dúvidas"*, *"quais dados desejo"*) | `10` | `@project-planner` | `grill-me`, `brainstorming`, `caveman` |
| **Descoberta, Instalação, Atualização & Remoção de Skills** (*"instalar skill"*, *"atualizar skills"*, *"remova a skill"*) | `15` | `@skill-installer-manager` | `skill-installer-asimov`, `find-skills`, `agent-skills` |
| **Pesquisa de Dados Atuais & Web Scraping** (*"dados atuais"*, *"últimos 30 dias"*, *"tendências"*) | `20` | `@explorer-agent` | `last30days`, `firecrawl-agent` |
| **Planejamento Estruturado & Plano Resumido** (*"plano resumido"*, *"etapas"*, *"passo a passo"*) | `30` | `@project-planner` | `plan-writing`, `superpowers`, `get-shit-done` |
| **Banco de Dados, Migrations & Queries** (*"modele o banco"*, *"migration"*, *"query lenta"*) | `32` | `@database-architect` | `database-design`, `database-optimizer`, `postgres-pro` |
| **Extração de Design System (`DESIGN.md`) & Prototipagem** (*"extrair paleta"*, *"tokens"*) | `35` | `@getdesign` | `getdesign`, `open-design`, `theme-factory` |
| **Memória Episódica & Agentes Autônomos** (*"memória episódica"*, *"hermes"*, *"openclaw"*) | `35` | `@hermes-agent` | `hermes-agent`, `ai-agentic-systems-multiagent` |
| **Backend, APIs & Endpoints** (*"api rest"*, *"endpoint"*, *"login com jwt"*) | `38` | `@backend-specialist` | `api-patterns`, `api-designer`, `fastapi-expert` |
| **Frontend: Páginas, Componentes & Dashboards** (*"dashboard"*, *"componente"*, *"tailwind"*) | `40` | `@frontend-specialist` | `frontend-design`, `react-best-practices`, `nextjs` |
| **Apps Mobile** (*"app mobile"*, *"react native"*, *"android"*) | `40` | `@mobile-developer` | `mobile-design`, `react-native-expert` |
| **Redação Humanizada & Linguagem Natural (Anti-IA)** (*"próxima da humana"*, *"sem tom robótico"*, *"artigo"*) | `40` | `@humanizer` | `humanizer`, `doc-coauthoring`, `internal-comms` |
| **Design de Interface, Apple HIG & Polimento Visual** (*"interface limpa"*, *"estilo apple"*, *"ui/ux"*) | `40` | `@frontend-ai-engineer` | `apple-hig-designer`, `ui-ux-pro-max`, `impeccable` |
| **Arquitetura RAG Híbrida & Banco Vetorial** (*"busca híbrida"*, *"pgvector"*, *"bm25"*) | `40` | `@rag-data-architect-ai` | `ai-advanced-rag-scale`, `backend-data-rag` |
| **Depuração de Bugs & Erros** (*"corrija o bug"*, *"erro 500"*, *"não responde"*) | `42` | `@debugger` | `systematic-debugging`, `debugging-wizard` |
| **Documentos Executivos (Word, PDF, Excel, Slides)** (*"gerar pdf"*, *"docx"*, *"apresentação"*) | `45` | `@documentation-writer` | `docx`, `pdf`, `pptx`, `xlsx` |
| **Vídeo Programático em React & Motion Graphics** (*"vídeo em react"*, *"remotion"*) | `45` | `@claude-remotion-skill` | `remotion-best-practices` |
| **Currículos Profissionais em YAML + Typst** (*"currículo"*, *"rendercv"*, *"typst"*) | `45` | `@rendercv` | `rendercv`, `pdf` |
| **SEO** (*"seo"*, *"ranquear no google"*) | `46` | `@seo-specialist` | `seo-audit`, `seo-fundamentals` |
| **Performance & Lighthouse** (*"está lenta"*, *"lighthouse"*, *"demora para abrir"*) | `47` | `@performance-optimizer` | `performance-profiling` |
| **Testes Automatizados (Unit, Integração, E2E)** (*"testes e2e"*, *"adicione testes"*, *"playwright"*) | `50` | `@test-engineer` | `tdd-workflow`, `webapp-testing`, `playwright-skill` |
| **Segurança Ofensiva, Pentest & Exploits PoC** (*"pentest"*, *"teste de invasão"*, *"strix"*) | `50` | `@strix` | `strix`, `vulnerability-scanner`, `trailofbits-security` |
| **Auditoria de Segurança Defensiva** (*"auditoria de segurança"*, *"sql injection"*, *"vulnerabilidades"*) | `52` | `@security-auditor` | `security-reviewer`, `secure-code-guardian` |
| **Proteção de Comandos Git & Guardrails** (*"bloquear git push"*, *"reset hard"*) | `55` | `@devops-engineer` | `git-guardrails-claude-code` |
| **DevOps: Deploy, Docker & CI/CD** (*"deploy"*, *"docker"*, *"github actions"*) | `58` | `@devops-engineer` | `deployment-procedures`, `docker-management` |

> Quando nenhuma intenção é reconhecida com segurança, o resultado vem com `"low_confidence": true` e agente `@orchestrator`. Nesse caso, confirme com o usuário ou complete com `--query`.
>
> Qualidade medida por `tests/eval_routing.py`: 47 frases de desenvolvimento + 15 de controle (holdout) que nunca são usadas para ajustar o roteador.

---

## 🧰 4. Ciclo de Vida das Skills (`kaminho_manager.py`)

Gerencia as pastas de `1_I-A_Skills`. A origem de cada uma fica em `kaminho/kaminho-sources.json`. **Nada é apagado direto:** remoções, versões anteriores a um update e duplicatas vão para `1_I-A_Skills/.kaminho-lixeira/` e podem ser restauradas.

```bash
K="<SKILLS_DIR>/kaminho/scripts/kaminho_manager.py"
python3 "$K" doctor                          # saúde: origem, tamanho, estrutura, cópias " 2", links, índice
python3 "$K" sources list                    # origem registrada de cada skill
python3 "$K" sources suggest                 # deduz origens (git remote, plugin.json, README) → status "sugerida"
python3 "$K" sources confirm humanizer xlsx  # aceita as sugestões revisadas
python3 "$K" sources set minha-skill https://github.com/dono/repo --subdir skills/minha-skill --ref main
python3 "$K" check [--deep]                  # há atualização? (--deep baixa e compara arquivo a arquivo)
python3 "$K" update humanizer --dry-run      # mostra o que mudaria
python3 "$K" update humanizer | --all        # atualiza; a versão anterior vai para a quarentena
python3 "$K" remove caveman [--yes]          # quarentena + desfaz links em ~/.claude/skills + reindexa
python3 "$K" restore caveman                 # desfaz remoção (ou desfaz o último update)
python3 "$K" trash list | trash purge --older-than 30 --yes
python3 "$K" organize dupes [--apply]        # cópias " 2" redundantes (idênticas ou contidas no original)
python3 "$K" reindex
```

**Regras para o agente:**
- `remove`, `update` (sem `--dry-run`), `organize ... --apply` e `trash purge` alteram arquivos. **Confirme com o usuário antes** e só então passe `--yes`.
- Uma origem com status `sugerida` é um palpite. Mostre a URL ao usuário e só rode `sources confirm` com o aval dele.
- O `kaminho` é protegido: atualize pelo próprio git.

---
*Desenvolvido por **Mizael Souto** — Criador do **Kaminho v2.0** • Engenharia de Sistemas Agênticos & Arquitetura Semântica de IA.*
