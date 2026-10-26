"""Funcionário e acesso ao sistema: cadastrar o funcionário já cria o login dele.

- Login no formato Primeiro.Ultimo (Luiz.Silveira). Se já existir, vira Luiz.Silveira2, 3...
- Cargo "Gerente" cria o acesso com perfil de Gerente (só o Dono pode); qualquer outro cargo, perfil de Funcionário.
- Funcionário e acesso são criados numa transação só: se algo falhar, nada fica pela metade.
"""
import re
import sqlite3

from fastapi import APIRouter, HTTPException

import banco_fazenda as bf
import contas
from logs import registrar_log
from permissoes import nivel_efetivo, sem_acento

router = APIRouter(tags=["funcionários e acesso"])

ROTULOS = {"dono": "Dono", "gerente": "Gerente", "funcionario": "Funcionário"}
SUFIXOS = {"jr", "junior", "filho", "neto", "sobrinho"}


def _limpar(parte):
    return re.sub(r"[^A-Za-z0-9]", "", sem_acento(parte))


def base_do_login(nome):
    partes = [p for p in nome.split() if _limpar(p)]
    while len(partes) > 1 and _limpar(partes[-1]).lower() in SUFIXOS:
        partes.pop()                                          # "Carlos Souza Júnior" -> Carlos.Souza
    if not partes:
        raise HTTPException(status_code=400, detail="Não consegui gerar um usuário a partir desse nome.")
    login = _limpar(partes[0]).capitalize()
    if len(partes) > 1:
        login += "." + _limpar(partes[-1]).capitalize()
    login = login[:36]
    return login if len(login) >= 3 else login + "1"


def gerar_login(conn, nome):
    base = base_do_login(nome)
    candidato, n = base, 1
    while contas.existe_login(conn, candidato):
        n += 1
        candidato = f"{base}{n}"
    return candidato


def nivel_pelo_cargo(cargo):
    """Só o cargo exatamente "Gerente" (sem diferenciar maiúscula) dá perfil de Gerente.
    É estrito de propósito: este campo concede privilégio, então grafia parecida não conta."""
    return "gerente" if cargo.strip().casefold() == "gerente" else "funcionario"


def _checar_quem_pode_criar(nivel_novo):
    if nivel_novo == "gerente" and bf.usuario_atual()["nivel"] != "dono":
        raise HTTPException(status_code=403, detail="Apenas o Dono pode cadastrar um Gerente.")


def _criar_acesso(conn, nome, cargo, nivel):
    """Cria o usuário (sem gravar ainda). Devolve (usuario_id, login, senha_temporaria)."""
    for _ in range(20):                                       # tenta de novo se dois cadastros colidirem
        login = gerar_login(conn, nome)
        try:
            usuario_id, senha = contas.criar_usuario(conn, nome, login, nivel, cargo, commit=False)
            return usuario_id, login, senha
        except contas.UsuarioExistente:
            continue
    raise HTTPException(status_code=409, detail="Não foi possível gerar um usuário único. Tente de novo.")


@router.post("/cadastrarFuncionario", status_code=201)
def cadastrar_funcionario(f: dict):
    nome = str(f.get("nome") or "").strip()
    if not nome:
        raise HTTPException(status_code=400, detail="Preencha o nome do funcionário.")
    cpf = "".join(c for c in str(f.get("cpf") or "") if c.isdigit())
    if cpf and len(cpf) != 11:
        raise HTTPException(status_code=400, detail="O CPF deve ter 11 dígitos.")
    cargo = str(f.get("cargo") or "").strip()
    nivel = nivel_pelo_cargo(cargo)
    _checar_quem_pode_criar(nivel)

    conn = bf.conectar()
    try:
        if cpf and conn.execute("SELECT 1 FROM funcionarios WHERE cpf = ? AND ativo = 1", (cpf,)).fetchone():
            raise HTTPException(status_code=409, detail="Já existe um funcionário com esse CPF.")
        cur = conn.execute(
            """INSERT INTO funcionarios (nome, cpf, telefone, endereco, cargo, data_admissao, observacoes, ativo)
               VALUES (?, ?, ?, ?, ?, ?, ?, 1)""",
            (nome, cpf, str(f.get("telefone") or ""), str(f.get("endereco") or ""), cargo,
             f.get("data_admissao"), str(f.get("observacoes") or "")))
        funcionario_id = cur.lastrowid
        usuario_id, login, senha = _criar_acesso(conn, nome, cargo, nivel)
        conn.execute("UPDATE funcionarios SET usuario_id = ? WHERE id = ?", (usuario_id, funcionario_id))
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()

    registrar_log("Cadastro", "funcionarios",
                  f'Funcionário "{nome}" cadastrado, com acesso "{login}" (perfil {nivel})')
    return {"message": "Funcionário cadastrado!", "id": funcionario_id,
            "acesso": {"usuario": login, "perfil": ROTULOS[nivel], "senha_temporaria": senha}}


def _funcionario(conn, funcionario_id):
    linha = conn.execute("SELECT id, nome, cargo, usuario_id FROM funcionarios WHERE id = ? AND ativo = 1",
                         (funcionario_id,)).fetchone()
    if not linha:
        raise HTTPException(status_code=404, detail="Funcionário não encontrado.")
    return linha


@router.get("/api/funcionarios/{funcionario_id}/acesso")
def ver_acesso(funcionario_id: int):
    conn = bf.conectar()
    try:
        _, _, _, usuario_id = _funcionario(conn, funcionario_id)
        if not usuario_id:
            return {"tem_acesso": False}
        u = conn.execute("SELECT id, usuario, nivel_acesso, ativo, trocar_senha FROM usuarios WHERE id = ?",
                         (usuario_id,)).fetchone()
    finally:
        conn.close()
    if not u:
        return {"tem_acesso": False}
    nivel = nivel_efetivo(u[2])
    return {"tem_acesso": True, "usuario_id": u[0], "usuario": u[1], "nivel": nivel, "perfil": ROTULOS[nivel],
            "ativo": bool(u[3]), "senha_temporaria_pendente": bool(u[4])}      # nunca devolve a senha nem o hash


@router.post("/api/funcionarios/{funcionario_id}/acesso", status_code=201)
def criar_acesso_do_funcionario(funcionario_id: int):
    """Para funcionários cadastrados antes de existir login: cria o acesso agora."""
    conn = bf.conectar()
    try:
        _, nome, cargo, usuario_id = _funcionario(conn, funcionario_id)
        if usuario_id and conn.execute("SELECT 1 FROM usuarios WHERE id = ?", (usuario_id,)).fetchone():
            raise HTTPException(status_code=409, detail="Este funcionário já tem acesso ao sistema.")
        nivel = nivel_pelo_cargo(cargo or "")
        _checar_quem_pode_criar(nivel)
        novo_id, login, senha = _criar_acesso(conn, nome, cargo or "", nivel)
        conn.execute("UPDATE funcionarios SET usuario_id = ? WHERE id = ?", (novo_id, funcionario_id))
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()
    registrar_log("Cadastro", "usuarios", f'Acesso "{login}" criado para o funcionário "{nome}" (perfil {nivel})')
    return {"usuario": login, "perfil": ROTULOS[nivel], "senha_temporaria": senha}
