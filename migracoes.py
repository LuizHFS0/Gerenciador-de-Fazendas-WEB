"""Migração organizada dos bancos das fazendas: backup, aplicação, validação e volta atrás.

Para cada banco: (1) integrity_check do original, (2) cópia de segurança, (3) aplica as mudanças de esquema,
(4) confere que nenhuma tabela perdeu linha e que o banco continua íntegro, (5) se algo falhar, devolve o original.
Com simular=True tudo acontece numa CÓPIA temporária e o banco real nem é tocado.
"""
import os
import shutil
import sqlite3
import tempfile
from datetime import datetime
from pathlib import Path

import caminhos
from backups import copiar_consistente, integridade
from esquema_fazenda import SCHEMA_VERSAO, garantir_esquema


def contagens(conn):
    tabelas = [l[0] for l in conn.execute("SELECT name FROM sqlite_master WHERE type = 'table' AND name NOT LIKE 'sqlite_%'")]
    return {t: conn.execute(f'SELECT COUNT(*) FROM "{t}"').fetchone()[0] for t in tabelas}


def versao_do_banco(caminho):
    conn = sqlite3.connect(str(caminho))
    try:
        try:
            linha = conn.execute("SELECT versao FROM schema_versao WHERE id = 1").fetchone()
        except sqlite3.OperationalError:
            return None
        return linha[0] if linha else None
    finally:
        conn.close()


def _devolver(backup, original):
    shutil.copy2(backup, original)
    for sufixo in ("-wal", "-shm"):
        Path(str(original) + sufixo).unlink(missing_ok=True)


def migrar_arquivo(caminho, aplicar=garantir_esquema, simular=True, pasta_backup=None):
    caminho = Path(caminho)
    rel = {"arquivo": caminho.name, "ok": False, "simulacao": simular, "erros": [], "backup": None,
           "versao_antes": None, "versao_depois": None, "tabelas_novas": []}
    integ = integridade(caminho)
    if integ != "ok":
        rel["erros"].append(f"banco original com defeito ({integ}); nada foi feito")
        return rel
    rel["versao_antes"] = versao_do_banco(caminho)

    if simular:
        pasta_tmp = Path(tempfile.mkdtemp(prefix="simulacao-"))
        trabalho = pasta_tmp / caminho.name
        copiar_consistente(caminho, trabalho)
        backup = None
    else:
        pasta = Path(pasta_backup) if pasta_backup else caminhos.pasta_backups() / f"pre-migracao-{datetime.now():%Y-%m-%d_%H%M%S}"
        backup = pasta / caminho.name
        copiar_consistente(caminho, backup)
        rel["backup"] = str(backup)
        trabalho = caminho

    try:
        conn = sqlite3.connect(str(trabalho))
        try:
            antes = contagens(conn)
            aplicar(conn)
            conn.commit()
            depois = contagens(conn)
        finally:
            conn.close()
        for tabela, n in antes.items():
            if tabela not in depois:
                rel["erros"].append(f"a tabela {tabela} desapareceu")
            elif depois[tabela] != n:
                rel["erros"].append(f"a tabela {tabela} tinha {n} linhas e ficou com {depois[tabela]}")
        if integridade(trabalho) != "ok":
            rel["erros"].append("o banco ficou com defeito depois da migração")
        rel["tabelas_novas"] = sorted(set(depois) - set(antes))
        rel["versao_depois"] = versao_do_banco(trabalho)
    except Exception as erro:
        rel["erros"].append(f"falha ao aplicar: {type(erro).__name__}: {erro}")

    if rel["erros"] and not simular:
        _devolver(backup, caminho)                                    # volta atrás: o original é restaurado
        rel["erros"].append("o banco original foi devolvido ao estado anterior")
    if simular:
        shutil.rmtree(trabalho.parent, ignore_errors=True)
    rel["ok"] = not rel["erros"]
    return rel


def migrar_todas_as_fazendas(simular=True):
    pasta_backup = None if simular else caminhos.pasta_backups() / f"pre-migracao-{datetime.now():%Y-%m-%d_%H%M%S}"
    relatorios = []
    for caminho in sorted(caminhos.pasta_fazendas().glob("*.db"), key=lambda p: (len(p.stem), p.stem)):
        relatorios.append(migrar_arquivo(caminho, simular=simular, pasta_backup=(pasta_backup / "fazendas") if pasta_backup else None))
    return relatorios
