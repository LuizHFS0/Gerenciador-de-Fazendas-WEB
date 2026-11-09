"""Backups consistentes dos bancos SQLite do FazendaWEB.

A API sqlite3.Connection.backup() inclui transações ainda no WAL.
Nunca copie um .db ativo com shutil.copy().
"""
import argparse
import hashlib
import json
import os
import shutil
import sqlite3
import sys
import tempfile
from contextlib import closing
from datetime import datetime, timezone
from pathlib import Path

import caminhos


def _uri_somente_leitura(caminho):
    return caminho.resolve().as_uri() + "?mode=ro"


def integridade(caminho):
    """Retorna 'ok' quando PRAGMA integrity_check aprova o banco."""
    caminho = Path(caminho)
    if not caminho.is_file():
        return "arquivo inexistente"
    try:
        with closing(sqlite3.connect(_uri_somente_leitura(caminho), uri=True, timeout=30)) as conn:
            resultado = conn.execute("PRAGMA integrity_check").fetchone()
            return str(resultado[0]) if resultado else "sem resultado"
    except (sqlite3.Error, OSError, ValueError) as erro:
        return f"erro: {type(erro).__name__}: {erro}"


def copiar_consistente(origem, destino):
    """Copia um banco SQLite aberto para um novo arquivo consistente."""
    origem, destino = Path(origem), Path(destino)
    if not origem.is_file():
        raise FileNotFoundError(f"Banco não encontrado: {origem}")
    if origem.resolve() == destino.resolve():
        raise ValueError("Origem e destino do backup não podem ser o mesmo arquivo.")
    destino.parent.mkdir(parents=True, exist_ok=True)
    if destino.exists():
        raise FileExistsError(f"O destino já existe: {destino}")

    try:
        with closing(sqlite3.connect(_uri_somente_leitura(origem), uri=True, timeout=30)) as fonte:
            with closing(sqlite3.connect(str(destino), timeout=30)) as copia:
                fonte.backup(copia, pages=256, sleep=0.1)
                copia.commit()
    except Exception:
        destino.unlink(missing_ok=True)
        for sufixo in ("-wal", "-shm"):
            Path(str(destino) + sufixo).unlink(missing_ok=True)
        raise

    resultado = integridade(destino)
    if resultado != "ok":
        destino.unlink(missing_ok=True)
        raise sqlite3.DatabaseError(f"Backup inconsistente ({destino}): {resultado}")
    return destino


def _bancos_existentes(pasta_dados):
    candidatos = [pasta_dados / "admin.db", pasta_dados / "superadmin.db"]
    pasta_fazendas = pasta_dados / "fazendas"
    if pasta_fazendas.exists():
        candidatos.extend(sorted(pasta_fazendas.glob("*.db")))
    return [p for p in candidatos if p.is_file()]


def _sha256(caminho):
    digest = hashlib.sha256()
    with Path(caminho).open("rb") as arquivo:
        for bloco in iter(lambda: arquivo.read(1024 * 1024), b""):
            digest.update(bloco)
    return digest.hexdigest()


def backup():
    """Cria um backup completo em uma pasta datada e retorna o caminho final."""
    pasta_dados = caminhos.dados().resolve()
    pasta_backups = caminhos.pasta_backups().resolve()
    if pasta_backups == pasta_dados or pasta_dados in pasta_backups.parents:
        raise ValueError("A pasta de backups não pode ficar dentro da pasta de dados.")
    bancos = _bancos_existentes(pasta_dados)
    if not bancos:
        raise RuntimeError(f"Nenhum banco SQLite encontrado em {pasta_dados}.")

    pasta_backups.mkdir(parents=True, exist_ok=True)
    identificador = datetime.now().astimezone().strftime("%Y-%m-%d_%H-%M-%S_%f")
    destino_final = pasta_backups / identificador
    temporaria = Path(tempfile.mkdtemp(prefix=".backup-temporario-", dir=pasta_backups))
    arquivos_manifesto = []

    try:
        for origem in bancos:
            relativo = origem.relative_to(pasta_dados)
            destino = temporaria / relativo
            copiar_consistente(origem, destino)
            arquivos_manifesto.append({
                "arquivo": relativo.as_posix(),
                "tamanho_bytes": destino.stat().st_size,
                "sha256": _sha256(destino),
                "integridade": "ok",
            })

        manifesto = {
            "formato": 1,
            "criado_em": datetime.now(timezone.utc).isoformat(timespec="seconds"),
            "origem_dados": str(pasta_dados),
            "arquivos": arquivos_manifesto,
        }
        (temporaria / "manifest.json").write_text(
            json.dumps(manifesto, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )
        os.replace(temporaria, destino_final)
    except Exception:
        shutil.rmtree(temporaria, ignore_errors=True)
        raise

    return destino_final


def principal(argv=None):
    parser = argparse.ArgumentParser(description="Ferramenta de backup do FazendaWEB.")
    parser.add_argument("comando", choices=("backup",), help="Operação a executar.")
    args = parser.parse_args(argv)
    if args.comando == "backup":
        try:
            destino = backup()
            print(f"Backup concluído: {destino}")
            return 0
        except Exception as erro:
            print(f"Falha ao criar backup: {type(erro).__name__}: {erro}", file=sys.stderr)
            return 1
    return 2


if __name__ == "__main__":
    raise SystemExit(principal())
