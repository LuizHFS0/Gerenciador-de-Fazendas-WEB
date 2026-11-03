"""Ponte ÚNICA entre o painel admin e o lado das fazendas.

Só faz duas coisas: criar o banco de uma fazenda nova com a conta inicial do Dono, e (enquanto o Dono ainda
não ativou o acesso) gerar de novo a senha temporária dele. Não lê, não lista e não altera nenhum dado
operacional. Depois que o Dono troca a senha, nada daqui consegue mexer na conta dele.
"""
import sqlite3
from pathlib import Path

from fastapi import HTTPException

import banco_fazenda as bf
import contas
import senhas
from funcionarios_acesso import gerar_login


class ProvisionamentoErro(Exception):
    pass


class AcessoJaAtivado(ProvisionamentoErro):
    pass


def _apagar(caminho):
    for sufixo in ("", "-wal", "-shm"):
        Path(str(caminho) + sufixo).unlink(missing_ok=True)
    bf._migrados.discard(str(caminho))


def provisionar(fazenda_id, nome_fazenda, dono_nome):
    """Cria dados/fazendas/<id>.db com o esquema e o Dono. Devolve {usuario, senha_temporaria}."""
    caminho = bf.caminho_banco(fazenda_id)
    if caminho.exists():
        raise ProvisionamentoErro("O banco desta fazenda já existe.")
    bf.pasta_fazendas().mkdir(parents=True, exist_ok=True)
    criado, conn = False, None
    try:
        sqlite3.connect(str(caminho)).close()
        criado = True
        conn = bf.abrir(fazenda_id)
        conn.execute("INSERT INTO fazenda (nome_fazenda, dono) VALUES (?, ?)", (nome_fazenda, dono_nome))
        login = gerar_login(conn, dono_nome)
        _, senha = contas.criar_usuario(conn, dono_nome, login, "dono", "Dono", commit=False)
        conn.commit()
    except HTTPException as erro:
        conn and conn.close()
        conn = None
        criado and _apagar(caminho)
        raise ProvisionamentoErro(str(erro.detail))
    except Exception:
        conn and conn.close()
        conn = None
        criado and _apagar(caminho)
        raise
    finally:
        conn and conn.close()
    return {"usuario": login, "senha_temporaria": senha}


def reemitir_acesso_inicial(fazenda_id):
    """Nova senha temporária do Dono, SÓ se ele ainda não ativou a conta (nunca trocou a senha)."""
    if not bf.caminho_banco(fazenda_id).exists():
        raise ProvisionamentoErro("O banco desta fazenda não existe.")
    conn = bf.abrir(fazenda_id)
    try:
        dono = conn.execute("""SELECT id, usuario, trocar_senha FROM usuarios
                               WHERE LOWER(TRIM(nivel_acesso)) = 'dono' ORDER BY id LIMIT 1""").fetchone()
        if not dono:
            raise ProvisionamentoErro("Esta fazenda não tem conta de Dono.")
        if not dono[2]:
            raise AcessoJaAtivado("O Dono já ativou o acesso. O painel não pode mais redefinir a senha dele.")
        temporaria = senhas.gerar_senha_temporaria()
        conn.execute("UPDATE usuarios SET senha = ?, trocar_senha = 1 WHERE id = ?",
                     (senhas.gerar_hash(temporaria), dono[0]))
        conn.execute("DELETE FROM sessoes WHERE usuario_id = ?", (dono[0],))
        conn.commit()
    finally:
        conn.close()
    return {"usuario": dono[1], "senha_temporaria": temporaria}
