"""Conexão com o banco da fazenda de quem está logado.

Cada fazenda tem o seu próprio arquivo SQLite (dados/fazendas/<id>.db). O id da
fazenda vem SEMPRE da sessão validada pelo middleware, nunca de parâmetro da
requisição. Sem fazenda no contexto, conectar() falha em vez de escolher um banco.
"""
import os
import sqlite3
from contextvars import ContextVar
from pathlib import Path

from esquema_fazenda import garantir_esquema

DADOS = Path(os.environ.get("FAZENDAWEB_DADOS") or (Path(__file__).resolve().parent / "dados"))

_fazenda = ContextVar("fazenda_id", default=None)
_usuario = ContextVar("usuario_logado", default=None)
_migrados = set()


def configurar_dados(pasta):
    """Troca a pasta de dados (usado nos testes e em scripts)."""
    global DADOS
    DADOS = Path(pasta)
    pasta_fazendas().mkdir(parents=True, exist_ok=True)


def pasta_fazendas():
    return DADOS / "fazendas"


def caminho_banco(fazenda_id):
    return pasta_fazendas() / f"{int(fazenda_id)}.db"      # int(): nada de ../ no caminho


def definir_contexto(fazenda_id, usuario):
    return _fazenda.set(fazenda_id), _usuario.set(usuario)


def limpar_contexto(tokens):
    _fazenda.reset(tokens[0])
    _usuario.reset(tokens[1])


def fazenda_atual():
    return _fazenda.get()


def usuario_atual():
    return _usuario.get()


def usuario_atual_id():
    usuario = _usuario.get()
    return usuario["id"] if usuario else None


def abrir(fazenda_id):
    caminho = caminho_banco(fazenda_id)
    if not caminho.exists():
        raise FileNotFoundError(f"Banco da fazenda {fazenda_id} não existe.")
    conn = sqlite3.connect(str(caminho), timeout=10)
    if str(caminho) not in _migrados:
        garantir_esquema(conn)
        _migrados.add(str(caminho))
    return conn


def conectar():
    """Banco da fazenda da requisição atual. Falha se não houver login no contexto."""
    fazenda_id = _fazenda.get()
    if fazenda_id is None:
        raise RuntimeError("Sem fazenda no contexto: a requisição não passou pela autenticação.")
    return abrir(fazenda_id)