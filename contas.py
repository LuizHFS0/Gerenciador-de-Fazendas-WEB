"""Criação de contas de usuário de uma fazenda (usado pela API, pelo cadastro de funcionários e pela migração)."""
import sqlite3

import senhas

NIVEIS = ("dono", "gerente", "funcionario")


class UsuarioExistente(Exception):
    pass


def existe_login(conn, usuario):
    """O login não diferencia maiúscula de minúscula: Luiz.Silveira e luiz.silveira são o mesmo."""
    return conn.execute("SELECT 1 FROM usuarios WHERE LOWER(usuario) = LOWER(?)", (usuario,)).fetchone() is not None


def criar_usuario(conn, nome, usuario, nivel, cargo="", commit=True):
    """Cria o usuário com uma senha temporária (troca obrigatória no 1º login).

    Devolve (id, senha_temporaria). A senha só existe aqui: no banco fica apenas o hash.
    Com commit=False quem chamou decide quando gravar (para criar tudo numa transação só).
    """
    if nivel not in NIVEIS:
        raise ValueError("Perfil inválido.")
    if existe_login(conn, usuario):
        raise UsuarioExistente()
    temporaria = senhas.gerar_senha_temporaria()
    try:
        cur = conn.execute(
            """INSERT INTO usuarios (nome, usuario, senha, cargo, nivel_acesso, ativo, trocar_senha)
               VALUES (?, ?, ?, ?, ?, 1, 1)""",
            (nome, usuario, senhas.gerar_hash(temporaria), cargo, nivel))
        if commit:
            conn.commit()
    except sqlite3.IntegrityError:
        raise UsuarioExistente()
    return cur.lastrowid, temporaria
