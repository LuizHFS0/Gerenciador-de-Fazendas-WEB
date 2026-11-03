"""Segurança do painel do SuperAdmin: contas, sessões, limite de tentativas e auditoria.

Autenticação INDEPENDENTE da das fazendas: outro banco (superadmin.db), outro cookie (fw_admin, só no /admin),
outra tabela de sessões. Este módulo não importa nada de banco de fazenda.
"""
import hashlib
import re
import secrets
import sqlite3
import time

import admin_banco
import configuracao
import senhas

COOKIE = "fw_admin"
DURACAO = 4 * 60 * 60
OCIOSIDADE = 30 * 60
MIN_SENHA = 12
CABECALHO = "x-requested-with"
CABECALHO_VALOR = "FazendaWEB-Admin"

JANELA_FALHAS = 15 * 60
MAX_FALHAS_USUARIO = 5
MAX_FALHAS_IP = 20
_falhas = {}


# ---------- limite de tentativas ----------
def _recentes(chave):
    agora = time.time()
    lista = [t for t in _falhas.get(chave, []) if agora - t < JANELA_FALHAS]
    if lista:
        _falhas[chave] = lista
    else:
        _falhas.pop(chave, None)
    return lista


def bloqueado(chave_usuario, chave_ip):
    return len(_recentes(chave_usuario)) >= MAX_FALHAS_USUARIO or len(_recentes(chave_ip)) >= MAX_FALHAS_IP


def registrar_falha(*chaves):
    for chave in chaves:
        _falhas.setdefault(chave, []).append(time.time())


def limpar_falhas(chave=None):
    _falhas.pop(chave, None) if chave else _falhas.clear()


# ---------- textos ----------
def limpar_texto(texto, limite=200):
    """Sem caracteres de controle (evita forjar linhas de log) e com tamanho máximo."""
    return re.sub(r"[\x00-\x1f\x7f]", " ", str(texto or ""))[:limite]


def validar_senha(senha):
    if not isinstance(senha, str) or len(senha) < MIN_SENHA:
        raise ValueError(f"A senha do SuperAdmin precisa ter pelo menos {MIN_SENHA} caracteres.")
    if len(senha) > 128:
        raise ValueError("A senha pode ter no máximo 128 caracteres.")
    if len(set(senha)) < 4:
        raise ValueError("A senha é simples demais: use caracteres variados.")


def tipo_pela_assinatura(dados):
    if dados[:3] == b"\xff\xd8\xff":
        return "image/jpeg"
    if dados[:8] == b"\x89PNG\r\n\x1a\n":
        return "image/png"
    if dados[:4] == b"RIFF" and dados[8:12] == b"WEBP":
        return "image/webp"
    return None


# ---------- contas (criadas SÓ por comando no servidor: superadmin_cli.py) ----------
def existe_superadmin():
    admin_banco.garantir_superadmin_db()
    conn = admin_banco.abrir_superadmin()
    try:
        return conn.execute("SELECT 1 FROM superadmins LIMIT 1").fetchone() is not None
    finally:
        conn.close()


def criar_superadmin(usuario, nome, senha):
    """Cria a conta do SuperAdmin. Recusa se já existir alguma: não há como criar outra pelo sistema."""
    usuario = (usuario or "").strip()
    if not re.fullmatch(r"[A-Za-z0-9._-]{3,40}", usuario):
        raise ValueError("Usuário inválido: use de 3 a 40 letras, números, ponto, hífen ou sublinhado.")
    if not (nome or "").strip():
        raise ValueError("Informe o nome.")
    validar_senha(senha)
    if existe_superadmin():
        raise PermissionError("Já existe um SuperAdmin. Esta conta não pode ser criada de novo.")
    conn = admin_banco.abrir_superadmin()
    try:
        conn.execute("INSERT INTO superadmins (usuario, nome, senha_hash, ativo, criado_em) VALUES (?, ?, ?, 1, ?)",
                     (usuario, nome.strip(), senhas.gerar_hash(senha), admin_banco.agora()))
        conn.commit()
    finally:
        conn.close()


def redefinir_senha(usuario, senha):
    validar_senha(senha)
    admin_banco.garantir_superadmin_db()
    conn = admin_banco.abrir_superadmin()
    try:
        linha = conn.execute("SELECT id FROM superadmins WHERE LOWER(usuario) = LOWER(?)", (usuario,)).fetchone()
        if not linha:
            raise LookupError("SuperAdmin não encontrado.")
        conn.execute("UPDATE superadmins SET senha_hash = ? WHERE id = ?", (senhas.gerar_hash(senha), linha["id"]))
        conn.execute("DELETE FROM sessoes_admin WHERE superadmin_id = ?", (linha["id"],))
        conn.commit()
    finally:
        conn.close()


# ---------- sessões ----------
def _hash(token):
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


def criar_sessao(conn, superadmin_id):
    token = secrets.token_urlsafe(32)
    agora = int(time.time())
    conn.execute("DELETE FROM sessoes_admin WHERE expira_em < ?", (agora,))
    conn.execute("""INSERT INTO sessoes_admin (token_hash, superadmin_id, criada_em, expira_em, ultimo_uso)
                    VALUES (?, ?, ?, ?, ?)""", (_hash(token), superadmin_id, agora, agora + DURACAO, agora))
    conn.commit()
    return token


def carregar_sessao(token):
    if not token or len(token) > 100:
        return None
    try:
        conn = admin_banco.abrir_superadmin()
    except sqlite3.OperationalError:
        return None
    try:
        linha = conn.execute("""SELECT s.superadmin_id AS id, a.usuario, a.nome, s.expira_em, s.ultimo_uso
                                FROM sessoes_admin s JOIN superadmins a ON a.id = s.superadmin_id
                                WHERE s.token_hash = ? AND a.ativo = 1""", (_hash(token),)).fetchone()
        agora = int(time.time())
        if not linha or linha["expira_em"] < agora or agora - linha["ultimo_uso"] > OCIOSIDADE:
            return None
        if agora - linha["ultimo_uso"] > 60:
            conn.execute("UPDATE sessoes_admin SET ultimo_uso = ? WHERE token_hash = ?", (agora, _hash(token)))
            conn.commit()
        return {"id": linha["id"], "usuario": linha["usuario"], "nome": linha["nome"], "expira_em": linha["expira_em"]}
    finally:
        conn.close()


def encerrar_sessao(token):
    if not token:
        return
    conn = admin_banco.abrir_superadmin()
    try:
        conn.execute("DELETE FROM sessoes_admin WHERE token_hash = ?", (_hash(token),))
        conn.commit()
    finally:
        conn.close()


# ---------- verificação de origem ----------
def origem_ok(request):
    origem = request.headers.get("origin")
    if not origem:
        return True
    if origem == f"{request.url.scheme}://{request.url.netloc}":
        return True
    return origem in configuracao.origens_extras()


def cabecalho_ok(request):
    return request.headers.get(CABECALHO) == CABECALHO_VALOR


# ---------- auditoria ----------
def auditar(conn, superadmin_id, acao, alvo="", detalhe="", ip=""):
    """Registra uma ação administrativa. Nunca recebe senhas nem tokens: só textos já limpos."""
    conn.execute("""INSERT INTO auditoria_admin (quando, superadmin_id, acao, alvo, detalhe, ip)
                    VALUES (?, ?, ?, ?, ?, ?)""",
                 (admin_banco.agora(), superadmin_id, limpar_texto(acao, 60), limpar_texto(alvo, 120),
                  limpar_texto(detalhe, 300), limpar_texto(ip, 45)))
    conn.commit()
