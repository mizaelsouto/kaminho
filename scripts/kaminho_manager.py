#!/usr/bin/env python3
"""
Kaminho — Gerenciador do ciclo de vida das skills instaladas.

Uma "skill instalada" (pacote) é cada pasta de primeiro nível em SKILLS_ROOT que contém
um SKILL.md ou agentes em .agent/agents/. A origem de cada pacote fica registrada em
kaminho-sources.json, ao lado deste repositório.

Comandos:
  doctor                         Relatório de saúde (origem, tamanho, estrutura, duplicatas, links, índice)
  sources list                   Mostra a origem registrada de cada pacote
  sources suggest [pacote ...]   Deduz a origem provável (git remote, plugin.json, README) para confirmar
  sources confirm <pacote ...>   Aceita a origem sugerida
  sources set <pacote> <url> [--subdir D] [--ref R]   Define a origem manualmente
  check [pacote ...] [--deep]    Verifica atualizações (git ls-remote; --deep baixa e compara arquivos)
  update <pacote ...>|--all [--dry-run]   Atualiza a partir da origem (versão anterior vai para a quarentena)
  remove <pacote ...> [--yes]    Move para a quarentena, desfaz links e reindexa
  restore <pacote> [--from ID]   Restaura da quarentena
  trash list | trash purge [--older-than DIAS] [--yes]
  organize dupes [--apply]       Encontra cópias " 2"; --apply move as redundantes para a quarentena
  reindex                        Regenera kaminho-index.{json,md,html}

Desenvolvido por: Mizael Souto
"""

import argparse
import datetime as dt
import filecmp
import hashlib
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SKILLS_ROOT = os.environ.get("SKILLS_ROOT", os.path.dirname(BASE_DIR))
SOURCES_PATH = os.environ.get("KAMINHO_SOURCES", os.path.join(BASE_DIR, "kaminho-sources.json"))
TRASH_DIR = os.path.join(SKILLS_ROOT, ".kaminho-lixeira")
TRASH_LOG = os.path.join(TRASH_DIR, "registro.json")
PROTECTED = {"kaminho"}  # o próprio gerenciador não se remove nem se sobrescreve
GIT_TIMEOUT = 90

_default_links = [os.path.expanduser("~/.claude/skills"), os.path.expanduser("~/.agents/skills")]
LINK_ROOTS = [p for p in os.environ.get("KAMINHO_LINK_ROOTS", os.pathsep.join(_default_links)).split(os.pathsep) if p]

# "nome 2", "nome 2.md", "nome 3.json" — cópias duplicadas criadas pelo Finder/sincronização
DUP_RE = re.compile(r"^(?P<base>.+) (?P<n>[2-9])(?P<ext>\.[A-Za-z0-9]+)?$")
SKIP_DIRS = {".git", "node_modules", ".venv", "__pycache__", ".kaminho-lixeira"}
GITHUB_RE = re.compile(r"https?://github\.com/([A-Za-z0-9_.-]+)/([A-Za-z0-9_.-]+)")
JUNK_OWNERS = {"user-attachments", "org", "user", "owner", "your-org", "your-username", "username",
               "orgs", "features", "sponsors", "topics", "marketplace", "apps", "settings", "login"}
# Skills oficiais publicadas em github.com/anthropics/skills (pasta skills/<nome>).
# Usadas só como SUGESTÃO quando o pacote não traz pista própria; o usuário confirma.
ANTHROPIC_SKILLS = {
    "algorithmic-art", "brand-guidelines", "canvas-design", "claude-api", "doc-coauthoring", "docx",
    "frontend-design", "internal-comms", "mcp-builder", "pdf", "pptx", "skill-creator",
    "slack-gif-creator", "theme-factory", "web-artifacts-builder", "webapp-testing", "xlsx",
}
JUNK_REPOS = {"repo", "repository", "your-repo", "assets", "issues", "pulls"}


# ----------------------------------------------------------------------------- utilidades

def now_id() -> str:
    return dt.datetime.now().strftime("%Y%m%d-%H%M%S")


def load_json(path: str, default):
    try:
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    except (OSError, json.JSONDecodeError):
        return default


def save_json(path: str, data) -> None:
    os.makedirs(os.path.dirname(path), exist_ok=True)
    tmp = path + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
        f.write("\n")
    os.replace(tmp, path)


def human_size(n: int) -> str:
    for unit in ("B", "KB", "MB", "GB"):
        if n < 1024 or unit == "GB":
            return f"{n:.0f} {unit}" if unit == "B" else f"{n:.1f} {unit}"
        n /= 1024
    return f"{n:.1f} GB"


def walk(path: str):
    """os.walk sem .git/node_modules/venv/lixeira e sem seguir links."""
    for root, dirs, files in os.walk(path):
        dirs[:] = [d for d in dirs if d not in SKIP_DIRS]
        yield root, dirs, files


def disk_usage(paths: list) -> dict:
    """{caminho: bytes} via um único `du -sk` (bem mais rápido que stat arquivo a arquivo em Python)."""
    out = {}
    if not paths:
        return out
    try:
        p = subprocess.run(["du", "-sk", *paths], capture_output=True, text=True, timeout=300)
        for line in p.stdout.splitlines():
            kb, path = line.split("\t", 1)
            out[path] = int(kb) * 1024
    except (OSError, subprocess.TimeoutExpired, ValueError):
        pass
    return out


def path_size(path: str) -> int:
    if os.path.isfile(path):
        return os.path.getsize(path)
    return disk_usage([path]).get(path, 0)


def tree_digest(path: str, ignore_dups: bool = True) -> dict:
    """{caminho relativo: sha1} de todos os arquivos (para comparar instalação x origem)."""
    out = {}
    for root, dirs, files in walk(path):
        if ignore_dups:
            dirs[:] = [d for d in dirs if not DUP_RE.match(d)]
        for f in files:
            if ignore_dups and DUP_RE.match(f):
                continue
            fp = os.path.join(root, f)
            if os.path.islink(fp) or f == ".DS_Store":
                continue
            h = hashlib.sha1()
            try:
                with open(fp, "rb") as fh:
                    for chunk in iter(lambda: fh.read(1 << 16), b""):
                        h.update(chunk)
            except OSError:
                continue
            out[os.path.relpath(fp, path)] = h.hexdigest()
    return out


def run_git(args, cwd=None):
    """Executa git sem prompt interativo de credenciais. Retorna (ok, stdout|stderr)."""
    env = dict(os.environ, GIT_TERMINAL_PROMPT="0")
    try:
        p = subprocess.run(["git", *args], cwd=cwd, env=env, capture_output=True, text=True, timeout=GIT_TIMEOUT)
    except (OSError, subprocess.TimeoutExpired) as e:
        return False, str(e)
    return p.returncode == 0, (p.stdout if p.returncode == 0 else p.stderr).strip()


def confirm(question: str, assume_yes: bool) -> bool:
    if assume_yes:
        return True
    if not sys.stdin.isatty():
        print(f"{question} — sem terminal interativo; repita com --yes para confirmar.")
        return False
    return input(f"{question} [s/N] ").strip().lower() in ("s", "sim", "y", "yes")


# ----------------------------------------------------------------------------- pacotes

def is_package(path: str) -> bool:
    if not os.path.isdir(path) or os.path.islink(path):
        return False
    for root, dirs, files in walk(path):
        if "SKILL.md" in files:
            return True
        if os.path.basename(root) == "agents" and os.path.basename(os.path.dirname(root)) == ".agent" \
                and any(f.endswith(".md") for f in files):
            return True
        # basta encontrar o primeiro; limita a profundidade para não varrer pacotes enormes
        if root.count(os.sep) - path.count(os.sep) >= 6:
            dirs[:] = []
    return False


def list_packages() -> list:
    names = []
    for name in sorted(os.listdir(SKILLS_ROOT), key=str.lower):
        if name.startswith(".") or DUP_RE.match(name):
            continue
        if is_package(os.path.join(SKILLS_ROOT, name)):
            names.append(name)
    return names


def install_path(pkg: str) -> str:
    """
    Onde o conteúdo do repositório de origem fica dentro do pacote.
    Padrão do ecossistema: <pacote>/.agent/skills/<pacote>/ (raiz do repo copiada ali).
    """
    root = os.path.join(SKILLS_ROOT, pkg)
    conventional = os.path.join(root, ".agent", "skills", pkg)
    if os.path.isdir(conventional):
        return conventional
    skills_dir = os.path.join(root, ".agent", "skills")
    if os.path.isdir(skills_dir):
        children = [d for d in os.listdir(skills_dir) if os.path.isdir(os.path.join(skills_dir, d)) and not DUP_RE.match(d)]
        if len(children) == 1:
            return os.path.join(skills_dir, children[0])
    return root


def require_package(pkg: str) -> str:
    path = os.path.join(SKILLS_ROOT, pkg)
    if not os.path.isdir(path):
        sys.exit(f"Pacote não encontrado: {pkg} (em {SKILLS_ROOT})")
    return path


# ----------------------------------------------------------------------------- origens

def load_sources() -> dict:
    data = load_json(SOURCES_PATH, {})
    data.setdefault("version", 1)
    data.setdefault("packages", {})
    return data


def git_origin(path: str):
    if not os.path.isdir(os.path.join(path, ".git")):
        return None
    ok, out = run_git(["remote", "get-url", "origin"], cwd=path)
    return out if ok and out else None


def normalize_repo_url(url: str) -> str:
    url = url.strip().rstrip("/")
    m = re.match(r"git@github\.com:(.+)", url)
    if m:
        url = "https://github.com/" + m.group(1)
    return re.sub(r"\.git$", "", url)


def suggest_source(pkg: str):
    """
    Deduz a origem provável do pacote. Retorna (url, evidência, confiança 0–1) ou None.
    Ordem de evidência: git remote > plugin/package.json > links do GitHub em README/SKILL.md.
    """
    root = os.path.join(SKILLS_ROOT, pkg)
    origin = git_origin(root)
    if origin:
        return normalize_repo_url(origin), "git remote origin", 1.0, ""
    if pkg in ANTHROPIC_SKILLS:
        return "https://github.com/anthropics/skills", "catálogo oficial anthropics/skills", 0.8, f"skills/{pkg}"
    cloud = cloud_only_files(root)

    candidates = {}  # url -> [pontos, evidências]

    def add(url, pts, why):
        c = candidates.setdefault(url, [0.0, set()])
        c[0] += pts
        c[1].add(why)

    meta_names = {"plugin.json", "package.json", "marketplace.json", "pyproject.toml", "SKILL.md", "README.md", "readme.md"}
    base = install_path(pkg)
    for r, dirs, files in walk(base):
        depth = r.count(os.sep) - base.count(os.sep)
        # raiz do repo + pastas de manifesto de plugin; não desce em sub-skills (open-design tem 550)
        if depth >= 1:
            dirs[:] = []
            if not os.path.basename(r).endswith("-plugin"):
                continue
        dirs[:] = [d for d in dirs if not DUP_RE.match(d)]
        for f in files:
            if f not in meta_names or os.path.join(r, f) in cloud:
                continue
            try:
                with open(os.path.join(r, f), "r", encoding="utf-8", errors="ignore") as fh:
                    text = fh.read(200_000)
            except OSError:
                continue
            weight = 3.0 if f.endswith((".json", ".toml")) else 1.0
            for owner, repo in GITHUB_RE.findall(text):
                repo = re.sub(r"\.git$", "", repo).rstrip(".")
                if owner.lower() in JUNK_OWNERS or repo.lower() in JUNK_REPOS or not repo:
                    continue
                add(f"https://github.com/{owner}/{repo}", weight, os.path.relpath(os.path.join(r, f), base))

    if not candidates:
        return None
    key = re.sub(r"[^a-z0-9]", "", pkg.lower())
    for url, c in candidates.items():
        repo_key = re.sub(r"[^a-z0-9]", "", url.rsplit("/", 1)[-1].lower())
        if repo_key and (repo_key in key or key in repo_key):
            c[0] += 5.0  # nome do repo parecido com o nome do pacote é o sinal mais forte
    ranked = sorted(candidates.items(), key=lambda kv: -kv[1][0])
    best_url, (pts, why) = ranked[0]
    total = sum(c[0] for c in candidates.values())
    conf = round(min(0.95, 0.4 * (pts / total) + (0.5 if pts >= 5 else 0.0)), 2)
    return best_url, ", ".join(sorted(why)[:3]), conf, ""


def cmd_sources(args):
    data = load_sources()
    pk = data["packages"]

    if args.action == "list":
        names = list_packages()
        print(f"{'pacote':32} {'status':11} origem")
        for n in names:
            e = pk.get(n, {})
            st = e.get("status", "desconhecida")
            url = e.get("repo", "—")
            extra = f"  (subdir {e['subdir']})" if e.get("subdir") else ""
            print(f"{n:32} {st:11} {url}{extra}")
        return

    if args.action == "suggest":
        names = args.packages or list_packages()
        changed = 0
        for n in names:
            require_package(n)
            if pk.get(n, {}).get("status") == "confirmada" and not args.packages:
                continue
            sug = suggest_source(n)
            if not sug:
                print(f"  ?  {n:30} sem pista de origem — use: sources set {n} <url>")
                continue
            url, why, conf, subdir = sug
            entry = pk.setdefault(n, {})
            if entry.get("status") == "confirmada" and entry.get("repo") == url:
                continue
            is_git = why == "git remote origin"
            entry.update(repo=url, ref=entry.get("ref", ""), subdir=subdir or entry.get("subdir", ""),
                         status="confirmada" if is_git else "sugerida", evidence=why, confidence=conf)
            if is_git:
                entry["type"] = "git"
            changed += 1
            save_json(SOURCES_PATH, data)  # salva a cada pacote: uma interrupção não perde o progresso
            sub = f" [{subdir}]" if subdir else ""
            print(f"  {'✓' if is_git else '~'}  {n:30} {url}{sub}  (confiança {conf}, via {why})", flush=True)
        save_json(SOURCES_PATH, data)
        print(f"\n{changed} origem(ns) registrada(s) em {os.path.relpath(SOURCES_PATH, SKILLS_ROOT)}. "
              f"Revise e aceite com: sources confirm <pacote ...>")
        return

    if args.action == "confirm":
        for n in args.packages:
            e = pk.get(n)
            if not e or not e.get("repo"):
                print(f"  ✗ {n}: sem origem sugerida — rode 'sources suggest {n}' ou 'sources set'")
                continue
            e["status"] = "confirmada"
            print(f"  ✓ {n}: {e['repo']}")
        save_json(SOURCES_PATH, data)
        return

    if args.action == "set":
        if len(args.packages) != 2:
            sys.exit("uso: sources set <pacote> <url> [--subdir D] [--ref R]")
        n, url = args.packages
        require_package(n)
        e = pk.setdefault(n, {})
        e.update(repo=normalize_repo_url(url), status="confirmada", evidence="manual", confidence=1.0)
        if args.subdir is not None:
            e["subdir"] = args.subdir.strip("/")
        if args.ref is not None:
            e["ref"] = args.ref
        save_json(SOURCES_PATH, data)
        print(f"  ✓ {n}: {e['repo']}" + (f" (subdir {e.get('subdir')})" if e.get("subdir") else ""))


# ----------------------------------------------------------------------------- atualizações

def remote_head(repo: str, ref: str):
    ok, out = run_git(["ls-remote", repo, ref or "HEAD"])
    if not ok:
        return None, out.splitlines()[-1] if out else "falha no git ls-remote"
    for line in out.splitlines():
        sha, name = line.split("\t", 1)
        if not ref or name in (ref, f"refs/heads/{ref}", f"refs/tags/{ref}", "HEAD"):
            return sha, None
    return None, f"ref '{ref}' não encontrada"


def fetch_source(entry: dict, dest: str):
    """Clone raso da origem. Retorna (pasta com o conteúdo da skill, commit) ou levanta RuntimeError."""
    args = ["clone", "--depth", "1", "--quiet"]
    if entry.get("ref"):
        args += ["--branch", entry["ref"]]
    ok, out = run_git(args + [entry["repo"], dest])
    if not ok:
        raise RuntimeError(out.splitlines()[-1] if out else "falha no git clone")
    _, sha = run_git(["rev-parse", "HEAD"], cwd=dest)
    src = os.path.join(dest, entry["subdir"]) if entry.get("subdir") else dest
    if not os.path.isdir(src):
        raise RuntimeError(f"subdir '{entry.get('subdir')}' não existe na origem")
    return src, sha


def diff_trees(installed: dict, upstream: dict):
    added = sorted(set(upstream) - set(installed))
    removed = sorted(set(installed) - set(upstream))
    changed = sorted(k for k in set(installed) & set(upstream) if installed[k] != upstream[k])
    return added, changed, removed


def update_targets(args, data) -> list:
    pk = data["packages"]
    if getattr(args, "all", False) or not args.packages:
        return [n for n in list_packages() if pk.get(n, {}).get("status") == "confirmada"]
    for n in args.packages:
        require_package(n)
    return args.packages


def cmd_check(args):
    data = load_sources()
    pk = data["packages"]
    targets = update_targets(args, data)
    if not targets:
        print("Nenhum pacote com origem confirmada. Rode 'sources suggest' e depois 'sources confirm'.")
        return
    counts = {"atualizado": 0, "desatualizado": 0, "desconhecido": 0, "erro": 0}
    for n in targets:
        e = pk.get(n)
        if not e or e.get("status") != "confirmada":
            print(f"  ·  {n:30} origem não confirmada")
            counts["desconhecido"] += 1
            continue
        path = os.path.join(SKILLS_ROOT, n)
        if e.get("type") == "git":
            run_git(["fetch", "--quiet"], cwd=path)
            ok, behind = run_git(["rev-list", "--count", "HEAD..@{u}"], cwd=path)
            if not ok:
                print(f"  ✗  {n:30} {behind}")
                counts["erro"] += 1
            elif behind == "0":
                print(f"  ✓  {n:30} em dia (git)")
                counts["atualizado"] += 1
            else:
                print(f"  ↑  {n:30} {behind} commit(s) novo(s) na origem (git)")
                counts["desatualizado"] += 1
            continue

        sha, err = remote_head(e["repo"], e.get("ref", ""))
        if err:
            print(f"  ✗  {n:30} {err}")
            counts["erro"] += 1
            continue
        e["last_checked"] = dt.datetime.now().isoformat(timespec="seconds")
        e["remote_commit"] = sha
        if e.get("installed_commit") == sha and not args.deep:
            print(f"  ✓  {n:30} em dia ({sha[:8]})")
            counts["atualizado"] += 1
            continue
        if not args.deep:
            if e.get("installed_commit"):
                print(f"  ↑  {n:30} nova versão {sha[:8]} (instalada {e['installed_commit'][:8]})")
                counts["desatualizado"] += 1
            else:
                print(f"  ?  {n:30} versão instalada desconhecida; origem em {sha[:8]} — use --deep para comparar arquivos")
                counts["desconhecido"] += 1
            continue
        with tempfile.TemporaryDirectory(prefix="kaminho-") as tmp:
            try:
                src, sha = fetch_source(e, os.path.join(tmp, "src"))
            except RuntimeError as ex:
                print(f"  ✗  {n:30} {ex}")
                counts["erro"] += 1
                continue
            a, c, r = diff_trees(tree_digest(install_path(n)), tree_digest(src))
        if not (a or c or r):
            e["installed_commit"] = sha  # conteúdo idêntico: agora sabemos a versão instalada
            print(f"  ✓  {n:30} idêntico à origem ({sha[:8]})")
            counts["atualizado"] += 1
        else:
            print(f"  ↑  {n:30} difere da origem: +{len(a)} novos, ~{len(c)} alterados, -{len(r)} só locais")
            counts["desatualizado"] += 1
    save_json(SOURCES_PATH, data)
    print("\nResumo: " + ", ".join(f"{v} {k}" for k, v in counts.items() if v))


def cmd_update(args):
    data = load_sources()
    pk = data["packages"]
    targets = update_targets(args, data)
    if not targets:
        print("Nada a atualizar (nenhuma origem confirmada).")
        return
    any_changed = False
    for n in targets:
        if n in PROTECTED:
            print(f"  ·  {n}: protegido — atualize pelo próprio git")
            continue
        e = pk.get(n)
        if not e or e.get("status") != "confirmada":
            print(f"  ·  {n}: origem não confirmada, pulando")
            continue
        path = os.path.join(SKILLS_ROOT, n)

        if e.get("type") == "git":
            if args.dry_run:
                ok, out = run_git(["fetch", "--quiet"], cwd=path)
                ok, behind = run_git(["rev-list", "--count", "HEAD..@{u}"], cwd=path)
                print(f"  ~  {n}: {behind if ok else '?'} commit(s) seriam aplicados (git pull --ff-only)")
                continue
            ok, out = run_git(["pull", "--ff-only", "--quiet"], cwd=path)
            print(f"  {'✓' if ok else '✗'}  {n}: {'atualizado (git)' if ok else out}")
            any_changed |= ok
            continue

        target = install_path(n)
        with tempfile.TemporaryDirectory(prefix="kaminho-") as tmp:
            try:
                src, sha = fetch_source(e, os.path.join(tmp, "src"))
            except RuntimeError as ex:
                print(f"  ✗  {n}: {ex}")
                continue
            a, c, r = diff_trees(tree_digest(target), tree_digest(src))
            if not (a or c or r):
                e["installed_commit"] = sha
                e["installed_at"] = e.get("installed_at") or dt.datetime.now().isoformat(timespec="seconds")
                print(f"  ✓  {n}: já idêntico à origem ({sha[:8]})")
                continue
            print(f"  ↑  {n}: +{len(a)} novos, ~{len(c)} alterados, -{len(r)} removidos/locais  → {sha[:8]}")
            for label, items in (("+", a), ("~", c), ("-", r)):
                for it in items[:8]:
                    print(f"        {label} {it}")
                if len(items) > 8:
                    print(f"        {label} … e mais {len(items) - 8}")
            if args.dry_run:
                continue
            # A versão atual vai inteira para a quarentena (inclui alterações locais), depois copia a nova.
            entry_id = now_id()
            backup = os.path.join(TRASH_DIR, entry_id, n + "-antes-do-update")
            os.makedirs(os.path.dirname(backup), exist_ok=True)
            shutil.copytree(target, backup, symlinks=True)
            shutil.rmtree(target)
            shutil.copytree(src, target, symlinks=True, ignore=shutil.ignore_patterns(".git"))
            log_trash(entry_id, n, backup, os.path.relpath(target, SKILLS_ROOT), "update", [],
                      previous_commit=e.get("installed_commit"))
            e["installed_commit"] = sha
            e["installed_at"] = dt.datetime.now().isoformat(timespec="seconds")
            any_changed = True
            print(f"     versão anterior guardada em {os.path.relpath(backup, SKILLS_ROOT)}")
    save_json(SOURCES_PATH, data)
    if any_changed and not args.no_reindex:
        reindex()


# ----------------------------------------------------------------------------- quarentena

def log_trash(entry_id, pkg, stored_at, original_rel, reason, links, **extra):
    log = load_json(TRASH_LOG, [])
    log.append({"id": entry_id, "package": pkg, "stored_at": os.path.relpath(stored_at, SKILLS_ROOT),
                "original": original_rel, "reason": reason, "links": links,
                "date": dt.datetime.now().isoformat(timespec="seconds"), **extra})
    save_json(TRASH_LOG, log)


def links_into(path: str) -> list:
    """Links simbólicos nas pastas de skills do agente (~/.claude/skills…) que apontam para dentro de `path`."""
    real = os.path.realpath(path)
    found = []
    for root in LINK_ROOTS:
        if not os.path.isdir(root):
            continue
        for r, dirs, files in os.walk(root):
            for name in dirs + files:
                p = os.path.join(r, name)
                if os.path.islink(p):
                    tgt = os.path.realpath(p)
                    if tgt == real or tgt.startswith(real + os.sep):
                        found.append((p, os.readlink(p)))
            if r.count(os.sep) - root.count(os.sep) >= 2:
                dirs[:] = []
    return found


def cmd_remove(args):
    for n in args.packages:
        if n in PROTECTED:
            print(f"  ✗ {n}: protegido, não pode ser removido pelo Kaminho")
            continue
        path = require_package(n)
        links = links_into(path)
        size = path_size(path)
        print(f"Remover '{n}' ({human_size(size)}) → quarentena .kaminho-lixeira/")
        for p, _ in links:
            print(f"   desfaz link: {p}")
        if not confirm("Confirmar?", args.yes):
            print("   cancelado.")
            continue
        entry_id = now_id()
        dest = os.path.join(TRASH_DIR, entry_id, n)
        os.makedirs(os.path.dirname(dest), exist_ok=True)
        shutil.move(path, dest)
        for p, _ in links:
            os.unlink(p)
        log_trash(entry_id, n, dest, n, "remove", [[p, t] for p, t in links])
        print(f"  ✓ {n} movido para {os.path.relpath(dest, SKILLS_ROOT)} (restaure com: restore {n})")
    if not args.no_reindex:
        reindex()


def cmd_restore(args):
    log = load_json(TRASH_LOG, [])
    cands = [e for e in log if e["package"] == args.package and (not args.from_id or e["id"] == args.from_id)
             and os.path.exists(os.path.join(SKILLS_ROOT, e["stored_at"]))]
    if not cands:
        sys.exit(f"Nada na quarentena para '{args.package}'. Veja: trash list")
    e = cands[-1]
    stored = os.path.join(SKILLS_ROOT, e["stored_at"])
    original = os.path.join(SKILLS_ROOT, e["original"])
    if os.path.exists(original):
        if e["reason"] != "update":
            sys.exit(f"Já existe {e['original']}; remova-o ou renomeie antes de restaurar.")
        # desfaz um update: a versão nova volta para a quarentena e a antiga é reposta
        swap = os.path.join(TRASH_DIR, now_id(), args.package + "-desfeito")
        os.makedirs(os.path.dirname(swap), exist_ok=True)
        shutil.move(original, swap)
        log_trash(os.path.basename(os.path.dirname(swap)), args.package, swap, e["original"], "update-desfeito", [])
    shutil.move(stored, original)
    for link, target in e.get("links", []):
        if not os.path.lexists(link):
            os.makedirs(os.path.dirname(link), exist_ok=True)
            os.symlink(target, link)
    log = [x for x in load_json(TRASH_LOG, []) if not (x["id"] == e["id"] and x["package"] == e["package"])]
    save_json(TRASH_LOG, log)
    print(f"  ✓ {args.package} restaurado em {e['original']} ({len(e.get('links', []))} link(s) refeito(s))")
    if e["reason"] == "update":
        data = load_sources()
        entry = data["packages"].get(args.package)
        if entry is not None:
            entry["installed_commit"] = e.get("previous_commit")  # volta a registrar a versão anterior
            save_json(SOURCES_PATH, data)
        print(f"    versão registrada voltou para {(e.get('previous_commit') or '')[:8] or 'desconhecida'}")
    if not args.no_reindex:
        reindex()


def cmd_trash(args):
    log = load_json(TRASH_LOG, [])
    if args.action == "list":
        if not log:
            print("Quarentena vazia.")
            return
        for e in log:
            p = os.path.join(SKILLS_ROOT, e["stored_at"])
            size = path_size(p) if os.path.exists(p) else 0
            print(f"  {e['id']}  {e['reason']:16} {e['package']:30} {human_size(size):>9}  {e['stored_at']}")
        return
    # purge
    cutoff = dt.datetime.now() - dt.timedelta(days=args.older_than)
    victims = [e for e in log if dt.datetime.fromisoformat(e["date"]) <= cutoff]
    if not victims:
        print(f"Nada com mais de {args.older_than} dia(s) na quarentena.")
        return
    total = 0
    for e in victims:
        p = os.path.join(SKILLS_ROOT, e["stored_at"])
        if os.path.exists(p):
            total += path_size(p)
        print(f"  apagar: {e['stored_at']}")
    if not confirm(f"Apagar DEFINITIVAMENTE {len(victims)} item(ns) ({human_size(total)})?", args.yes):
        print("cancelado.")
        return
    for e in victims:
        p = os.path.join(SKILLS_ROOT, e["stored_at"])
        if os.path.isdir(p) and not os.path.islink(p):
            shutil.rmtree(p)
        elif os.path.lexists(p):
            os.unlink(p)
    keep = [e for e in log if e not in victims]
    save_json(TRASH_LOG, keep)
    for d in os.listdir(TRASH_DIR):
        dp = os.path.join(TRASH_DIR, d)
        if os.path.isdir(dp) and not os.listdir(dp):
            os.rmdir(dp)
    print(f"  ✓ {len(victims)} item(ns) apagado(s), {human_size(total)} liberados")


# ----------------------------------------------------------------------------- organização

def tree_listing(path: str) -> dict:
    """{caminho relativo: tamanho} — comparação barata antes de calcular hashes."""
    out = {}
    for r, dirs, files in walk(path):
        for f in files:
            fp = os.path.join(r, f)
            if f != ".DS_Store" and not os.path.islink(fp):
                try:
                    out[os.path.relpath(fp, path)] = os.path.getsize(fp)
                except OSError:
                    pass
    return out


def contained_in(dup: str, orig: str) -> bool:
    """True se todo arquivo da cópia existe, igual, no original (cópia idêntica, parcial ou vazia)."""
    ld, lo = tree_listing(dup), tree_listing(orig)
    if any(lo.get(k) != size for k, size in ld.items()):
        return False
    return all(filecmp.cmp(os.path.join(dup, k), os.path.join(orig, k), shallow=False) for k in ld)


def cloud_only_files(root: str = None) -> set:
    """
    Arquivos cujo conteúdo não está no disco (macOS 'dataless'). O Kaminho simplesmente
    não os abre — abrir dispararia um download. Não há relatório nem comando sobre isso.
    """
    root = root or SKILLS_ROOT
    if sys.platform != "darwin":
        return set()
    cmd = ["find", root, "(", "-name", ".git", "-o", "-name", "node_modules", "-o", "-name", ".kaminho-lixeira", ")",
           "-prune", "-o", "-type", "f", "-flags", "+dataless", "-print"]
    try:
        p = subprocess.run(cmd, capture_output=True, text=True, timeout=300)
    except (OSError, subprocess.TimeoutExpired):
        return set()
    return {line for line in p.stdout.splitlines() if line}


def scan_package(pkg: str) -> dict:
    """Uma passagem pelo pacote, sem stat por arquivo: SKILL.md encontrados e cópias ' N'."""
    root = os.path.join(SKILLS_ROOT, pkg)
    skill_files, dupes = [], []
    for r, dirs, files in walk(root):
        for name in dirs + files:
            m = DUP_RE.match(name)
            if m and os.path.lexists(os.path.join(r, m.group("base") + (m.group("ext") or ""))):
                dupes.append(os.path.join(r, name))
        dirs[:] = [d for d in dirs if not DUP_RE.match(d)]
        if "SKILL.md" in files:
            skill_files.append(os.path.join(r, "SKILL.md"))
    return {"skill_files": skill_files, "dupes": dupes}


def find_dupes(root: str = None) -> list:
    """[(cópia, original, redundante?)] — redundante = idêntica ao original ou totalmente contida nele."""
    root = root or SKILLS_ROOT
    out = []
    for r, dirs, files in walk(root):
        for name in dirs + files:
            m = DUP_RE.match(name)
            if not m:
                continue
            orig = os.path.join(r, m.group("base") + (m.group("ext") or ""))
            dup = os.path.join(r, name)
            if not os.path.lexists(orig):
                continue
            if os.path.isdir(dup) and os.path.isdir(orig):
                same = contained_in(dup, orig)
            elif os.path.isfile(dup) and os.path.isfile(orig):
                same = filecmp.cmp(dup, orig, shallow=False)
            else:
                same = False
            out.append((dup, orig, same))
        dirs[:] = [d for d in dirs if not DUP_RE.match(d)]  # não desce dentro das cópias
    return out


def cmd_organize(args):
    dupes = find_dupes()
    same = [d for d in dupes if d[2]]
    diff = [d for d in dupes if not d[2]]
    print(f"Cópias ' N' encontradas: {len(dupes)} — {len(same)} redundantes (idênticas ou contidas no original), "
          f"{len(diff)} com conteúdo próprio")
    for dup, orig, _ in diff:
        print(f"  ≠ revisar: {os.path.relpath(dup, SKILLS_ROOT)}  (difere de '{os.path.basename(orig)}')")
    if not args.apply:
        for dup, _, _ in same[:15]:
            print(f"  = {os.path.relpath(dup, SKILLS_ROOT)}")
        if len(same) > 15:
            print(f"  … e mais {len(same) - 15}")
        if same:
            print("\nRode 'organize dupes --apply' para mover as redundantes para a quarentena (reversível).")
        return
    if not same:
        return
    entry_id = now_id()
    for dup, _, _ in same:
        rel = os.path.relpath(dup, SKILLS_ROOT)
        dest = os.path.join(TRASH_DIR, entry_id, "duplicatas", rel)
        os.makedirs(os.path.dirname(dest), exist_ok=True)
        shutil.move(dup, dest)
        log_trash(entry_id, rel, dest, rel, "duplicata", [])
    print(f"  ✓ {len(same)} cópia(s) redundante(s) movida(s) para .kaminho-lixeira/{entry_id}/duplicatas/")
    if not args.no_reindex:
        reindex()


def read_frontmatter(path: str) -> dict:
    try:
        with open(path, "r", encoding="utf-8", errors="ignore") as f:
            head = f.read(4096)
    except OSError:
        return {}
    m = re.match(r"^---\s*\n(.*?)\n---", head, re.S)
    if not m:
        return {}
    fm = {}
    for line in m.group(1).splitlines():
        mm = re.match(r"^([A-Za-z_-]+):\s*(.*)$", line)
        if mm:
            fm[mm.group(1)] = mm.group(2).strip()
    return fm


def structure_issues(pkg: str, skill_files: list, cloud: set = frozenset()) -> list:
    issues = []
    root = os.path.join(SKILLS_ROOT, pkg)
    if skill_files and not os.path.isdir(os.path.join(root, ".agent", "skills")):
        issues.append("fora do padrão <pacote>/.agent/skills/<nome>/")
    bad = 0
    for sf in skill_files:
        if sf in cloud:
            continue  # não abre arquivo cujo conteúdo não está no disco
        fm = read_frontmatter(sf)
        if not fm.get("name") or not fm.get("description"):
            bad += 1
    if bad:
        issues.append(f"{bad} SKILL.md sem name/description no frontmatter")
    return issues


def index_orphans() -> list:
    idx = load_json(os.path.join(BASE_DIR, "kaminho-index.json"), {})
    missing = []
    for kind in ("agents", "skills"):
        for it in idx.get(kind, []):
            p = os.path.join(SKILLS_ROOT, it.get("path", "").lstrip("./"))
            if not os.path.exists(p):
                missing.append(it.get("path"))
    return missing


def broken_links() -> list:
    out = []
    for root in LINK_ROOTS:
        if not os.path.isdir(root):
            continue
        for r, dirs, files in os.walk(root):
            for name in dirs + files:
                p = os.path.join(r, name)
                if os.path.islink(p) and not os.path.exists(p):
                    out.append((p, os.readlink(p)))
            if r.count(os.sep) - root.count(os.sep) >= 2:
                dirs[:] = []
    return out


def cmd_doctor(args):
    data = load_sources()
    pk = data["packages"]
    rows, problems, all_dupes = [], 0, []
    names = list_packages()
    sizes = disk_usage([os.path.join(SKILLS_ROOT, n) for n in names])
    cloud = cloud_only_files()  # só para não abrir esses arquivos

    for n in names:
        scan = scan_package(n)
        all_dupes.extend(scan["dupes"])
        issues = structure_issues(n, scan["skill_files"], cloud)
        if scan["dupes"]:
            issues.append(f"{len(scan['dupes'])} cópia(s) ' N'")
        mtimes = [os.path.getmtime(f) for f in scan["skill_files"] if os.path.lexists(f)]
        e = pk.get(n, {})
        rows.append({
            "package": n, "size": sizes.get(os.path.join(SKILLS_ROOT, n), 0),
            "skills": len(scan["skill_files"]),
            "modified": dt.datetime.fromtimestamp(max(mtimes)).strftime("%Y-%m-%d") if mtimes else "—",
            "source": e.get("status", "desconhecida"),
            "version": (e.get("installed_commit") or "")[:8] or "—",
            "issues": issues,
        })
        problems += bool(issues)

    orphans = index_orphans()
    links = broken_links()
    non_pkg = [d for d in sorted(os.listdir(SKILLS_ROOT)) if os.path.isdir(os.path.join(SKILLS_ROOT, d))
               and not d.startswith(".") and d not in {r["package"] for r in rows}]

    if args.json:
        print(json.dumps({"packages": rows, "index_orphans": orphans, "broken_links": links,
                          "duplicates": [os.path.relpath(a, SKILLS_ROOT) for a in all_dupes],
                          "non_packages": non_pkg}, ensure_ascii=False, indent=2))
        return

    total = sum(r["size"] for r in rows)
    src_counts = {}
    for r in rows:
        src_counts[r["source"]] = src_counts.get(r["source"], 0) + 1
    print(f"🩺 Kaminho doctor — {len(rows)} pacotes, {human_size(total)} em {SKILLS_ROOT}\n")
    print(f"{'pacote':30} {'tamanho':>9} {'skills':>6}  {'SKILL.md em':10}  {'origem':12} {'versão':8}  problemas")
    for r in sorted(rows, key=lambda x: (not x["issues"], x["package"].lower())):
        print(f"{r['package'][:30]:30} {human_size(r['size']):>9} {r['skills']:>6}  {r['modified']:10}  {r['source']:12} "
              f"{r['version']:8}  {'; '.join(r['issues']) or '✓'}")
    print("\nResumo")
    print(f"  origem: " + ", ".join(f"{v} {k}" for k, v in sorted(src_counts.items())))
    print(f"  pacotes com problemas de estrutura/duplicatas: {problems}")
    print(f"  cópias ' N': {len(all_dupes)} → 'organize dupes' compara e limpa")
    print(f"  entradas do índice apontando para arquivos inexistentes: {len(orphans)}"
          + (" → 'reindex'" if orphans else ""))
    for o in orphans[:5]:
        print(f"     {o}")
    print(f"  links quebrados em {', '.join(LINK_ROOTS)}: {len(links)}")
    for p, t in links:
        print(f"     {p} → {t}")
    if non_pkg:
        print(f"  pastas que não são skills (ignoradas): {', '.join(non_pkg)}")
    if src_counts.get("desconhecida") or src_counts.get("sugerida"):
        print("\nPróximo passo: 'sources suggest' e 'sources confirm' para habilitar check/update.")


# ----------------------------------------------------------------------------- índice

def reindex():
    sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
    import rebuild_catalog  # noqa: E402
    print("\nReindexando…")
    rebuild_catalog.build_catalog()


# ----------------------------------------------------------------------------- CLI

def main():
    ap = argparse.ArgumentParser(description="Kaminho — gerenciador de skills instaladas (por Mizael Souto)")
    sub = ap.add_subparsers(dest="cmd", required=True)

    p = sub.add_parser("doctor", help="relatório de saúde")
    p.add_argument("--json", action="store_true")
    p.set_defaults(func=cmd_doctor)

    p = sub.add_parser("sources", help="origem de cada pacote")
    p.add_argument("action", choices=["list", "suggest", "confirm", "set"])
    p.add_argument("packages", nargs="*")
    p.add_argument("--subdir")
    p.add_argument("--ref")
    p.set_defaults(func=cmd_sources)

    p = sub.add_parser("check", help="verifica atualizações")
    p.add_argument("packages", nargs="*")
    p.add_argument("--deep", action="store_true", help="baixa a origem e compara arquivo a arquivo")
    p.set_defaults(func=cmd_check)

    p = sub.add_parser("update", help="atualiza pacotes")
    p.add_argument("packages", nargs="*")
    p.add_argument("--all", action="store_true")
    p.add_argument("--dry-run", action="store_true")
    p.add_argument("--no-reindex", action="store_true")
    p.set_defaults(func=cmd_update)

    p = sub.add_parser("remove", help="move pacotes para a quarentena")
    p.add_argument("packages", nargs="+")
    p.add_argument("--yes", action="store_true")
    p.add_argument("--no-reindex", action="store_true")
    p.set_defaults(func=cmd_remove)

    p = sub.add_parser("restore", help="restaura da quarentena")
    p.add_argument("package")
    p.add_argument("--from", dest="from_id")
    p.add_argument("--no-reindex", action="store_true")
    p.set_defaults(func=cmd_restore)

    p = sub.add_parser("trash", help="quarentena")
    p.add_argument("action", choices=["list", "purge"])
    p.add_argument("--older-than", type=int, default=30)
    p.add_argument("--yes", action="store_true")
    p.set_defaults(func=cmd_trash)

    p = sub.add_parser("organize", help="organização")
    p.add_argument("what", choices=["dupes"])
    p.add_argument("--apply", action="store_true")
    p.add_argument("--no-reindex", action="store_true")
    p.set_defaults(func=cmd_organize)

    p = sub.add_parser("reindex", help="regenera o índice")
    p.set_defaults(func=lambda a: reindex())

    args = ap.parse_args()
    if args.cmd == "update" and bool(args.all) == bool(args.packages):
        ap.error("informe os pacotes OU --all")
    args.func(args)


if __name__ == "__main__":
    main()
