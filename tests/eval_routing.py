#!/usr/bin/env python3
"""
Kaminho — Suíte de avaliação do roteamento semântico.

Cada caso traz um prompt e os agentes que DEVEM aparecer no pipeline
(`expect`), opcionalmente na ordem dada (`ordered=True`).

Uso:
  python3 tests/eval_routing.py            # resumo + falhas
  python3 tests/eval_routing.py -v         # mostra todos os casos
Sai com código 1 se a taxa de acerto ficar abaixo de --min (padrão 0.85).
"""

import argparse
import os
import statistics
import sys
import time

sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "scripts"))
import kaminho_reader as k  # noqa: E402

CASES = [
    # --- multi-etapa ---
    ("Crie um artigo que mostre dados atuais, me pergunte quais dados desejo, e depois gere um plano resumido e uma linguagem bem proxima da humana.",
     ["@project-planner", "@explorer-agent", "@humanizer"], True),
    ("faça um dashboard responsivo e depois escreva testes e2e", ["@frontend-specialist", "@test-engineer"], True),
    ("crie uma API REST de pedidos, depois faça o deploy com docker", ["@backend-specialist", "@devops-engineer"], True),
    ("modele o banco postgres e em seguida implemente os endpoints", ["@database-architect", "@backend-specialist"], True),
    ("me pergunte o que preciso antes de começar e depois monte o plano passo a passo", ["@project-planner"], False),
    ("pesquise as tendências dos últimos 30 dias e escreva um post com tom humano", ["@explorer-agent", "@humanizer"], True),
    ("implemente o login com jwt e depois faça uma auditoria de segurança", ["@backend-specialist", "@security-auditor"], False),
    ("corrija o bug do formulário e adicione testes unitários", ["@debugger", "@test-engineer"], True),
    ("extraia a paleta e os tokens do site e depois crie a interface no estilo apple", ["@getdesign", "@frontend-ai-engineer"], True),
    ("gere um pdf do relatório, além disso crie uma apresentação em slides", ["@documentation-writer"], False),
    # --- intenção única ---
    ("corrija o bug no login jwt", ["@debugger"], False),
    ("a aplicação está dando erro 500 quando salvo o usuário", ["@debugger"], False),
    ("quero um vídeo em react com remotion", ["@claude-remotion-skill"], False),
    ("monte meu currículo em typst", ["@rendercv"], False),
    ("faça um pentest na minha aplicação web", ["@strix"], False),
    ("bloqueie git push --force no repositório", ["@devops-engineer"], False),
    ("crie um componente de card responsivo com tailwind", ["@frontend-specialist"], False),
    ("escreva testes e2e com playwright para o checkout", ["@test-engineer"], False),
    ("configure o pipeline de ci/cd no github actions", ["@devops-engineer"], False),
    ("otimize a query sql que está lenta", ["@database-architect"], False),
    ("crie a migration para a tabela de clientes", ["@database-architect"], False),
    ("crie um endpoint para upload de arquivos", ["@backend-specialist"], False),
    ("revise o código desse PR procurando vulnerabilidades", ["@security-auditor"], False),
    ("implemente busca híbrida com pgvector e bm25", ["@rag-data-architect-ai"], False),
    ("quero instalar uma nova skill do catálogo", ["@skill-installer-manager"], False),
    ("verifique se há atualizações das skills instaladas", ["@skill-installer-manager"], False),
    ("remova a skill caveman", ["@skill-installer-manager"], False),
    ("gere uma planilha excel com os dados de vendas", ["@documentation-writer"], False),
    ("reescreva esse texto para não parecer escrito por IA", ["@humanizer"], False),
    ("a página está lenta, melhore a performance e o lighthouse", ["@performance-optimizer"], False),
    ("crie um app mobile em react native", ["@mobile-developer"], False),
    ("melhore o seo da landing page", ["@seo-specialist"], False),
    # --- 2ª rodada (usados no ajuste do vocabulário) ---
    ("adicione autenticação com google no meu site e escreva a documentação", ["@backend-specialist"], False),
    ("o botão de salvar não responde quando clico", ["@debugger"], False),
    ("preciso de uma tela de cadastro bonita no estilo do macos", ["@frontend-ai-engineer"], False),
    ("suba a aplicação na vps com nginx e certificado ssl", ["@devops-engineer"], False),
    ("crie um índice para acelerar a busca de pedidos por data", ["@database-architect"], False),
    ("cobre o módulo de pagamentos com testes de integração", ["@test-engineer"], False),
    ("verifique se há sql injection no formulário de busca", ["@security-auditor"], False),
    ("faça um levantamento das notícias sobre IA desta semana", ["@explorer-agent"], False),
    ("transforme esse relatório em uma apresentação", ["@documentation-writer"], False),
    ("o site demora 8 segundos para abrir", ["@performance-optimizer"], False),
    ("quero um roadmap de 3 meses para o produto", ["@project-planner"], False),
    ("reescreva o email para ficar mais natural", ["@humanizer"], False),
    ("crie uma tela de login em react e conecte na api", ["@frontend-specialist"], False),
    ("gere um apk android do meu app", ["@mobile-developer"], False),
    ("como faço para ranquear melhor no google", ["@seo-specialist"], False),
]

# Conjunto de controle: NUNCA ajuste nós/pesos olhando para estes casos.
# Mede como o roteador generaliza para frases novas. Placar separado, não reprova a suíte.
HOLDOUT = [
    ("o checkout quebra quando o carrinho está vazio", ["@debugger"], False),
    ("monte um painel administrativo com gráficos de vendas", ["@frontend-specialist"], False),
    ("preciso de uma rota que devolva o histórico do cliente", ["@backend-specialist"], False),
    ("normalize as tabelas e crie chaves estrangeiras", ["@database-architect"], False),
    ("coloque o projeto num container e publique na aws", ["@devops-engineer"], False),
    ("garanta que o fluxo de compra não regrida com testes automatizados", ["@test-engineer"], False),
    ("analise se as senhas estão sendo armazenadas de forma segura", ["@security-auditor"], False),
    ("me ajuda a definir as etapas do lançamento do produto", ["@project-planner"], False),
    ("faça uma tabela comparativa em xlsx dos fornecedores", ["@documentation-writer"], False),
    ("deixe esse texto menos robótico", ["@humanizer"], False),
    ("quais são as novidades do mercado de IA neste mês", ["@explorer-agent"], False),
    ("o app iOS está consumindo muita bateria", ["@mobile-developer"], False),
    ("antes de codar, me faça perguntas sobre o que preciso", ["@project-planner"], False),
    ("crie a página de preços e depois otimize o tempo de carregamento", ["@frontend-specialist", "@performance-optimizer"], True),
    ("refatore o serviço de notificações em python", ["@backend-specialist"], False),
]


def check(case):
    prompt, expect, ordered = case
    t0 = time.perf_counter()
    res = k.route_prompt(prompt)
    ms = (time.perf_counter() - t0) * 1000
    got = [s["agent"] for s in res["semantic_pipeline"]]
    ok = all(a in got for a in expect)
    if ok and ordered:
        idx = [got.index(a) for a in expect]
        ok = idx == sorted(idx)
    return ok, got, ms, res


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("-v", "--verbose", action="store_true")
    ap.add_argument("--min", type=float, default=0.85)
    args = ap.parse_args()

    k.route_prompt("aquecimento")  # 1ª chamada carrega o catálogo (custo de inicialização medido à parte)

    def run(cases, label):
        passed, times = 0, []
        for case in cases:
            ok, got, ms, res = check(case)
            times.append(ms)
            passed += ok
            if args.verbose or not ok:
                mark = "✅" if ok else "❌"
                conf = [s["confidence"] for s in res["semantic_pipeline"]]
                print(f"{mark} {ms:6.1f}ms  [{label}] {case[0][:64]}\n      esperado {case[1]}  obtido {got}  conf {conf}")
        return passed, times

    passed, times = run(CASES, "dev")
    h_passed, h_times = run(HOLDOUT, "holdout")
    rate = passed / len(CASES)
    all_t = times + h_times
    print(f"\nAcerto dev:     {passed}/{len(CASES)} ({rate:.0%})")
    print(f"Acerto holdout: {h_passed}/{len(HOLDOUT)} ({h_passed / len(HOLDOUT):.0%})  ← frases nunca usadas no ajuste")
    print(f"Latência: mediana {statistics.median(all_t):.1f} ms, máx {max(all_t):.1f} ms")
    sys.exit(0 if rate >= args.min else 1)


if __name__ == "__main__":
    main()
