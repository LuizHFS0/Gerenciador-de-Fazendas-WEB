"""Transforma o banco.db atual na fazenda 1 do FazendaWEB.

O banco.db original NÃO é alterado: o script faz uma cópia consistente em
dados/fazendas/1.db e registra a fazenda em dados/admin.db.

Exemplos:
  python migrar_fazenda_1.py --codigo minha-fazenda --dono luiz
  python migrar_fazenda_1.py --codigo minha-fazenda --novo-dono dono --nome-dono "Luiz Silva"
"""
import argparse
import re
import sqlite3
import sys
from pathlib import Path

import banco_fazenda as bf
import contas
import ponte_admin

CODIGO_VALIDO = re.compile(r"^[a-z0-9][a-z0-9-]{2,29}$")


def migrar(origem, codigo, dono=None, novo_dono=None, nome_dono=None, fazenda_id=1, dados=None):
    if dados:
        bf.configurar_dados(dados)
    origem = Path(origem)
    if not origem.exists():
        raise SystemExit(f"Não encontrei {origem}.")
    if not CODIGO_VALIDO.match(codigo or ""):
        raise SystemExit("O código da fazenda deve ter de 3 a 30 caracteres: letras minúsculas, números e hífen.")
    if bool(dono) == bool(novo_dono):
        raise SystemExit("Informe --dono USUARIO (conta que já existe) ou --novo-dono USUARIO (cria uma conta).")

    destino = bf.caminho_banco(fazenda_id)
    if destino.exists():
        raise SystemExit(f"{destino} já existe. Nada foi feito.")
    ponte_admin.garantir_admin_db()
    admin = sqlite3.connect(str(ponte_admin.caminho_admin()))
    try:
        if admin.execute("SELECT 1 FROM fazendas WHERE id = ? OR codigo = ?", (fazenda_id, codigo)).fetchone():
            raise SystemExit("Já existe uma fazenda com esse id ou código no admin.db. Nada foi feito.")

        # confere a escolha do Dono ANTES de copiar qualquer coisa
        src = sqlite3.connect(origem.resolve().as_uri() + "?mode=ro", uri=True)
        try:
            try:
                existentes = src.execute("SELECT usuario, nome, nivel_acesso, ativo FROM usuarios").fetchall()
            except sqlite3.OperationalError:
                existentes = []
            if dono and dono not in [u[0] for u in existentes]:
                lista = "\n".join(f"  {u[0]} ({u[1]}, perfil {u[2]}, {'ativo' if u[3] else 'inativo'})" for u in existentes)
                raise SystemExit(f"O usuário '{dono}' não existe no banco. Usuários encontrados:\n{lista or '  (nenhum)'}")
            bf.pasta_fazendas().mkdir(parents=True, exist_ok=True)
            dst = sqlite3.connect(str(destino))
            try:
                src.backup(dst)                     # cópia consistente, mesmo com o banco em uso
            finally:
                dst.close()
        finally:
            src.close()

        conn = bf.abrir(fazenda_id)                 # aplica garantir_esquema (colunas novas, sessões)
        try:
            senha_temporaria = None
            if dono:
                conn.execute("UPDATE usuarios SET nivel_acesso = 'gerente' WHERE LOWER(TRIM(nivel_acesso)) = 'dono'")
                conn.execute("UPDATE usuarios SET nivel_acesso = 'dono', ativo = 1 WHERE usuario = ?", (dono,))
            else:
                conn.execute("UPDATE usuarios SET nivel_acesso = 'gerente' WHERE LOWER(TRIM(nivel_acesso)) = 'dono'")
                _, senha_temporaria = contas.criar_usuario(conn, nome_dono or novo_dono, novo_dono, "dono")
            conn.commit()
            linha = conn.execute("SELECT nome_fazenda FROM fazenda ORDER BY id LIMIT 1").fetchone()
            nome = linha[0] if linha else codigo
            funcionarios = conn.execute("SELECT COUNT(*) FROM funcionarios WHERE ativo = 1").fetchone()[0]
        finally:
            conn.close()

        ponte_admin.registrar_fazenda(admin, fazenda_id, codigo, nome, funcionarios)
        admin.commit()
    finally:
        admin.close()
    return {"fazenda_id": fazenda_id, "codigo": codigo, "nome": nome, "banco": str(destino),
            "senha_temporaria": senha_temporaria}


def principal():
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--origem", default="banco.db")
    p.add_argument("--codigo", required=True, help="código usado no login (ex.: minha-fazenda)")
    p.add_argument("--dono", help="usuário que já existe e passa a ser o Dono")
    p.add_argument("--novo-dono", help="cria uma conta nova de Dono (com senha temporária)")
    p.add_argument("--nome-dono", help="nome completo do novo Dono")
    p.add_argument("--id", type=int, default=1, dest="fazenda_id")
    p.add_argument("--dados", help="pasta de dados (padrão: ./dados)")
    a = p.parse_args()
    r = migrar(a.origem, a.codigo, a.dono, a.novo_dono, a.nome_dono, a.fazenda_id, a.dados)
    print(f"Fazenda {r['fazenda_id']} ('{r['nome']}') criada em {r['banco']}.")
    print(f"Para entrar: código da fazenda = {r['codigo']}")
    if r["senha_temporaria"]:
        print(f"\nSenha temporária do novo Dono (aparece só agora, será trocada no 1º login): {r['senha_temporaria']}")
    print("\nO banco.db original não foi alterado. O sistema web passa a usar o banco em dados/fazendas/.")


if __name__ == "__main__":
    principal()