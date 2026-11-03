"""Onde ficam os arquivos de dados. Módulo neutro: não importa nada de banco de fazenda nem do admin.

dados/
  fazendas/<id>.db   banco operacional de CADA fazenda (animais, estoque, usuários da fazenda...)
  admin.db           cadastro administrativo das fazendas (nome, código, plano, pagamento, ativa).
                     A fazenda só lê dali o código e se está ativa; o SuperAdmin administra aqui.
  superadmin.db      contas, sessões e auditoria do SuperAdmin. Só o painel admin abre este arquivo.
  seguranca.log      eventos de segurança em JSON (sem senhas nem tokens)
"""
import os
from pathlib import Path

_dados = Path(os.environ.get("FAZENDAWEB_DADOS") or (Path(__file__).resolve().parent / "dados"))


def dados():
    return _dados


def configurar(pasta):
    """Troca a pasta de dados (testes e scripts)."""
    global _dados
    _dados = Path(pasta)
    pasta_fazendas().mkdir(parents=True, exist_ok=True)


def pasta_fazendas():
    return _dados / "fazendas"


def arquivo_admin():
    return _dados / "admin.db"


def arquivo_superadmin():
    return _dados / "superadmin.db"


def arquivo_log_seguranca():
    return _dados / "seguranca.log"


def pasta_backups():
    return Path(os.environ.get("FAZENDAWEB_BACKUPS") or (_dados.parent / "backups"))
