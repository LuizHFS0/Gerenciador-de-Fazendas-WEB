"""Bancos do lado administrativo: admin.db (cadastro das fazendas) e superadmin.db (contas, sessões, auditoria).

Este módulo NÃO importa nada de banco de fazenda: o painel admin só enxerga dados administrativos.
"""
import sqlite3
from datetime import datetime

import caminhos

PLANOS_INICIAIS = (("basico", "Básico"), ("pro", "Pro"))
PAGAMENTOS = ("em_dia", "pendente")

# colunas acrescentadas ao admin.db criado na etapa 1 (só o essencial para administrar a fazenda)
COLUNAS_FAZENDAS = [
    ("plano", "TEXT NOT NULL DEFAULT 'basico'"),
    ("pagamento", "TEXT NOT NULL DEFAULT 'em_dia'"),
    ("pagamento_atualizado_em", "TEXT"),
    ("contato_nome", "TEXT"),
    ("contato_email", "TEXT"),
    ("contato_telefone", "TEXT"),
    ("observacoes", "TEXT"),
    ("situacao", "TEXT NOT NULL DEFAULT 'provisionada'"),     # provisionando | provisionada
]


def agora():
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")


def _colunas(conn, tabela):
    return {l[1] for l in conn.execute(f"PRAGMA table_info({tabela})")}


def garantir_admin_db():
    caminhos.dados().mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(caminhos.arquivo_admin()))
    try:
        conn.execute("""CREATE TABLE IF NOT EXISTS fazendas(
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            codigo TEXT NOT NULL UNIQUE,
            nome TEXT NOT NULL,
            ativa INTEGER NOT NULL DEFAULT 1,
            funcionarios INTEGER NOT NULL DEFAULT 0,
            criada_em TEXT)""")
        existentes = _colunas(conn, "fazendas")
        for coluna, definicao in COLUNAS_FAZENDAS:
            if coluna not in existentes:
                conn.execute(f"ALTER TABLE fazendas ADD COLUMN {coluna} {definicao}")
        conn.execute("""CREATE TABLE IF NOT EXISTS planos(
            codigo TEXT PRIMARY KEY,
            nome TEXT NOT NULL,
            ativo INTEGER NOT NULL DEFAULT 1)""")
        for codigo, nome in PLANOS_INICIAIS:
            conn.execute("INSERT OR IGNORE INTO planos (codigo, nome, ativo) VALUES (?, ?, 1)", (codigo, nome))
        conn.execute("CREATE INDEX IF NOT EXISTS idx_fazendas_plano ON fazendas(plano, pagamento, ativa)")
        conn.execute("""CREATE TABLE IF NOT EXISTS interessados(
            id INTEGER PRIMARY KEY AUTOINCREMENT, nome TEXT NOT NULL, email TEXT NOT NULL,
            telefone TEXT NOT NULL, fazenda TEXT, mensagem TEXT,
            status TEXT NOT NULL DEFAULT 'novo', criado_em TEXT NOT NULL)""")
        conn.execute("CREATE INDEX IF NOT EXISTS idx_interessados_criado ON interessados(id DESC)")
        conn.commit()
    finally:
        conn.close()


def garantir_superadmin_db():
    caminhos.dados().mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(caminhos.arquivo_superadmin()))
    try:
        conn.execute("""CREATE TABLE IF NOT EXISTS superadmins(
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            usuario TEXT NOT NULL UNIQUE,
            nome TEXT NOT NULL,
            senha_hash TEXT NOT NULL,
            ativo INTEGER NOT NULL DEFAULT 1,
            criado_em TEXT NOT NULL,
            ultimo_login TEXT)""")
        conn.execute("""CREATE TABLE IF NOT EXISTS sessoes_admin(
            token_hash TEXT PRIMARY KEY,
            superadmin_id INTEGER NOT NULL,
            criada_em INTEGER NOT NULL,
            expira_em INTEGER NOT NULL,
            ultimo_uso INTEGER NOT NULL,
            FOREIGN KEY(superadmin_id) REFERENCES superadmins(id))""")
        conn.execute("""CREATE TABLE IF NOT EXISTS superadmins_fotos(
            superadmin_id INTEGER PRIMARY KEY,
            tipo TEXT NOT NULL,
            dados BLOB NOT NULL,
            atualizada_em INTEGER NOT NULL,
            FOREIGN KEY(superadmin_id) REFERENCES superadmins(id))""")
        conn.execute("""CREATE TABLE IF NOT EXISTS auditoria_admin(
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            quando TEXT NOT NULL,
            superadmin_id INTEGER,
            acao TEXT NOT NULL,
            alvo TEXT,
            detalhe TEXT,
            ip TEXT)""")
        conn.execute("CREATE INDEX IF NOT EXISTS idx_auditoria_admin_quando ON auditoria_admin(id DESC)")
        conn.commit()
    finally:
        conn.close()


def abrir_admin():
    conn = sqlite3.connect(str(caminhos.arquivo_admin()), timeout=10)
    conn.row_factory = sqlite3.Row
    return conn


def abrir_superadmin():
    conn = sqlite3.connect(str(caminhos.arquivo_superadmin()), timeout=10)
    conn.row_factory = sqlite3.Row
    return conn


def registrar_fazenda(conn, fazenda_id, codigo, nome, funcionarios=0, plano="basico", pagamento="em_dia"):
    """Usado pela migração da fazenda 1 e pelos testes. O cadastro pelo painel tem o seu próprio fluxo."""
    conn.execute("""INSERT INTO fazendas (id, codigo, nome, ativa, funcionarios, criada_em, plano, pagamento,
                                          pagamento_atualizado_em, situacao)
                    VALUES (?, ?, ?, 1, ?, ?, ?, ?, ?, 'provisionada')""",
                 (fazenda_id, codigo, nome, funcionarios, agora(), plano, pagamento, agora()))
