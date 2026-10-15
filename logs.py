import sqlite3
from datetime import datetime

# Precisa ser o mesmo banco usado no api.py
CAMINHO_BANCO = "banco.db"

# Tabelas das quais nome_de() pode buscar o nome (lista fixa, por segurança)
TABELAS_COM_NOME = {"animais", "maquinas", "funcionarios", "estoque", "lote"}


def registrar_log(acao, tabela, descricao, usuario_id=None):
    """Grava uma movimentação na tabela logs.

    Abre e fecha a própria conexão. Se der erro, só avisa no terminal:
    um log que falha nunca derruba a operação principal.
    Chame depois do commit da rota, fora do try que mantém a conexão aberta.
    """
    conn = None
    try:
        conn = sqlite3.connect(CAMINHO_BANCO)
        conn.execute(
            """INSERT INTO logs (usuario_id, acao, tabela_afetada, data_hora, descricao)
               VALUES (?, ?, ?, ?, ?)""",
            (usuario_id, acao, tabela, datetime.now().strftime("%Y-%m-%d %H:%M:%S"), descricao),
        )
        conn.commit()
    except Exception as erro:
        print("Falha ao registrar log:", erro)
    finally:
        if conn:
            conn.close()


def nome_de(tabela, registro_id):
    """Devolve o nome de um registro para usar na descrição do log."""
    if tabela not in TABELAS_COM_NOME:
        return f"#{registro_id}"
    conn = None
    try:
        conn = sqlite3.connect(CAMINHO_BANCO)
        linha = conn.execute(f"SELECT nome FROM {tabela} WHERE id = ?", (registro_id,)).fetchone()
        return linha[0] if linha else f"#{registro_id}"
    except Exception:
        return f"#{registro_id}"
    finally:
        if conn:
            conn.close()