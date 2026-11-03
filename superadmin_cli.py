"""Cria ou redefine a conta do SuperAdmin. Roda só no servidor, com acesso ao terminal.

  python superadmin_cli.py criar --usuario luiz --nome "Luiz Silva"      (pede a senha, sem mostrar)
  python superadmin_cli.py redefinir-senha --usuario luiz                (pede a nova senha)

'criar' recusa rodar se já existir um SuperAdmin. Não existe nenhuma rota web que crie SuperAdmin.
"""
import argparse
import getpass
import sys

import admin_seguranca


def _pedir_senha():
    senha = getpass.getpass("Senha (mínimo 12 caracteres): ")
    if senha != getpass.getpass("Repita a senha: "):
        raise SystemExit("As senhas não são iguais.")
    return senha


def principal(argv=None):
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = p.add_subparsers(dest="comando", required=True)
    c = sub.add_parser("criar")
    c.add_argument("--usuario", required=True)
    c.add_argument("--nome", required=True)
    r = sub.add_parser("redefinir-senha")
    r.add_argument("--usuario", required=True)
    a = p.parse_args(argv)
    try:
        if a.comando == "criar":
            admin_seguranca.criar_superadmin(a.usuario, a.nome, _pedir_senha())
            print(f"SuperAdmin '{a.usuario}' criado. Entre em /admin/login.html.")
        else:
            admin_seguranca.redefinir_senha(a.usuario, _pedir_senha())
            print("Senha redefinida. As sessões abertas foram encerradas.")
    except (ValueError, PermissionError, LookupError) as erro:
        raise SystemExit(f"Erro: {erro}")


if __name__ == "__main__":
    principal(sys.argv[1:])
