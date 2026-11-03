"""Ponte estreita entre a API das fazendas e o banco do SuperAdmin (dados/admin.db).

O lado das fazendas só LÊ do admin: o código da fazenda (para o login) e se ela está
ativa. A única escrita permitida é o contador de funcionários. Nada mais passa por aqui.
"""
import sqlite3

import caminhos


def caminho_admin():
    return caminhos.arquivo_admin()


def _somente_leitura():
    return sqlite3.connect(caminho_admin().resolve().as_uri() + "?mode=ro", uri=True, timeout=5)


def _ler(sql, params):
    try:
        conn = _somente_leitura()
    except sqlite3.OperationalError:
        return None
    try:
        return conn.execute(sql, params).fetchone()
    except sqlite3.OperationalError:
        return None
    finally:
        conn.close()


def buscar_por_codigo(codigo):
    linha = _ler("SELECT id, ativa FROM fazendas WHERE codigo = ?", (codigo,))
    return {"id": linha[0], "ativa": bool(linha[1])} if linha else None


def fazenda_ativa(fazenda_id):
    linha = _ler("SELECT ativa FROM fazendas WHERE id = ?", (fazenda_id,))
    return bool(linha and linha[0])          # fazenda desconhecida conta como bloqueada


def nome_fazenda(fazenda_id):
    linha = _ler("SELECT nome FROM fazendas WHERE id = ?", (fazenda_id,))
    return linha[0] if linha else None


def resumo_fazenda(fazenda_id):
    """Só nome e código: o que o menu do usuário mostra."""
    linha = _ler("SELECT nome, codigo FROM fazendas WHERE id = ?", (fazenda_id,))
    return {"nome": linha[0], "codigo": linha[1]} if linha else None


def atualizar_funcionarios(fazenda_id, quantidade):
    conn = sqlite3.connect(str(caminho_admin()), timeout=5)
    try:
        conn.execute("UPDATE fazendas SET funcionarios = ? WHERE id = ?", (int(quantidade), fazenda_id))
        conn.commit()
    finally:
        conn.close()
