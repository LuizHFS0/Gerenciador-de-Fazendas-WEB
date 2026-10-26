"""Login, sessões e proteção das rotas da API das fazendas (etapa 1).

Princípios:
- Tudo é bloqueado por padrão: só as rotas de PUBLICAS dispensam login.
- A sessão é um token aleatório guardado (como hash) no banco da própria fazenda.
- O id da fazenda vem da sessão validada, nunca da requisição.
- Fazenda desativada ou usuário desativado perdem o acesso na hora, sem apagar dados.
"""
import hashlib
import os
import re
import secrets
import sqlite3
import time
from urllib.parse import quote

from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import JSONResponse, RedirectResponse
from starlette.concurrency import run_in_threadpool

import banco_fazenda as bf
import contas
import permissoes
import ponte_admin
import senhas
from logs import registrar_log
from funcionarios_acesso import router as rotas_funcionarios
from perfil import router as rotas_perfil

COOKIE = "fw_sessao"
DURACAO_SESSAO = 12 * 60 * 60
PAGINA_LOGIN = "/front-end/login.html"
PAGINA_TROCA = "/front-end/trocar-senha.html"
PAGINA_INICIAL = "/front-end/dashboard.html"
NIVEIS_CRIAVEIS = ("gerente", "funcionario")
METODOS_SEGUROS = ("GET", "HEAD", "OPTIONS")
PUBLICAS = {("POST", "/api/auth/login"), ("POST", "/api/auth/logout"), ("GET", PAGINA_LOGIN)}
LIBERADAS_NA_TROCA = {"/api/auth/eu", "/api/auth/trocar-senha", PAGINA_TROCA}
# origens extras aceitas em escrita (atrás de proxy com HTTPS, por exemplo), separadas por vírgula
ORIGENS_EXTRAS = {o.strip() for o in os.environ.get("FAZENDAWEB_ORIGENS", "").split(",") if o.strip()}

JANELA_FALHAS = 15 * 60
MAX_FALHAS_USUARIO = 5
MAX_FALHAS_IP = 20
_falhas = {}
_ultimo_contador = {}


# ---------- limite de tentativas (em memória, por processo) ----------
def _recentes(chave):
    agora = time.time()
    lista = [t for t in _falhas.get(chave, []) if agora - t < JANELA_FALHAS]
    if lista:
        _falhas[chave] = lista
    else:
        _falhas.pop(chave, None)
    return lista


def _bloqueado(chave_usuario, chave_ip):
    return (len(_recentes(chave_usuario)) >= MAX_FALHAS_USUARIO
            or len(_recentes(chave_ip)) >= MAX_FALHAS_IP)


def _registrar_falha(*chaves):
    for chave in chaves:
        _falhas.setdefault(chave, []).append(time.time())


def limpar_limitador():
    _falhas.clear()


# ---------- sessões ----------
def _hash_token(token):
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


def criar_sessao(conn, usuario_id):
    token = secrets.token_urlsafe(32)
    agora = int(time.time())
    conn.execute("DELETE FROM sessoes WHERE expira_em < ?", (agora,))
    conn.execute("INSERT INTO sessoes (token_hash, usuario_id, criada_em, expira_em) VALUES (?, ?, ?, ?)",
                 (_hash_token(token), usuario_id, agora, agora + DURACAO_SESSAO))
    conn.commit()
    return token


def _separar_cookie(valor):
    if not valor or "." not in valor:
        return None, None
    prefixo, token = valor.split(".", 1)
    if not (prefixo.isascii() and prefixo.isdigit()) or not token:
        return None, None
    return int(prefixo), token


def carregar_sessao(valor_cookie):
    """Valida o cookie. O prefixo só diz qual banco consultar: o token precisa existir nele."""
    fazenda_id, token = _separar_cookie(valor_cookie)
    if fazenda_id is None or not bf.caminho_banco(fazenda_id).exists():
        return None
    conn = bf.abrir(fazenda_id)
    try:
        linha = conn.execute(
            """SELECT u.id, u.nome, u.usuario, u.nivel_acesso, u.trocar_senha, s.expira_em
               FROM sessoes s JOIN usuarios u ON u.id = s.usuario_id
               WHERE s.token_hash = ? AND u.ativo = 1""", (_hash_token(token),)).fetchone()
    finally:
        conn.close()
    if not linha or linha[5] < time.time():
        return None
    return {"fazenda_id": fazenda_id, "id": linha[0], "nome": linha[1], "usuario": linha[2],
            "nivel": permissoes.nivel_efetivo(linha[3]), "trocar_senha": bool(linha[4]),
            "expira_em": int(linha[5])}


def _encerrar_sessao(valor_cookie):
    fazenda_id, token = _separar_cookie(valor_cookie)
    if fazenda_id is None or not bf.caminho_banco(fazenda_id).exists():
        return
    conn = bf.abrir(fazenda_id)
    try:
        conn.execute("DELETE FROM sessoes WHERE token_hash = ?", (_hash_token(token),))
        conn.commit()
    finally:
        conn.close()


def sincronizar_contador(fazenda_id):
    """Informa ao admin SÓ quantos funcionários a fazenda tem (o admin nunca lê a tabela)."""
    try:
        conn = bf.abrir(fazenda_id)
        try:
            n = conn.execute("SELECT COUNT(*) FROM funcionarios WHERE ativo = 1").fetchone()[0]
        finally:
            conn.close()
        chave = (str(bf.DADOS), fazenda_id)
        if _ultimo_contador.get(chave) != n:
            ponte_admin.atualizar_funcionarios(fazenda_id, n)
            _ultimo_contador[chave] = n
    except Exception as erro:
        print("Falha ao atualizar o contador de funcionários:", erro)


# ---------- middleware ----------
def _eh_pagina(caminho):
    return caminho == "/" or caminho.endswith(".html")


def _origem_permitida(request):
    origem = request.headers.get("origin")
    if not origem:
        return True                                    # clientes que não são navegador
    if origem == f"{request.url.scheme}://{request.url.netloc}":
        return True                                    # mesma origem
    return origem in ORIGENS_EXTRAS


def _negar(request, status, detalhe, codigo):
    if request.method == "GET" and _eh_pagina(request.url.path):
        if codigo == "fazenda_desativada":
            destino = f"{PAGINA_LOGIN}?motivo=desativada"
        elif codigo == "trocar_senha":
            destino = PAGINA_TROCA
        elif codigo == "sem_permissao":
            destino = PAGINA_INICIAL
        elif request.url.path == "/":
            destino = PAGINA_LOGIN
        else:
            destino = f"{PAGINA_LOGIN}?proximo={quote(request.url.path)}"
        return RedirectResponse(destino, status_code=303)
    return JSONResponse({"detail": detalhe, "codigo": codigo}, status_code=status)


def _cabecalhos(resposta):
    resposta.headers.setdefault("X-Content-Type-Options", "nosniff")
    resposta.headers.setdefault("X-Frame-Options", "DENY")
    resposta.headers.setdefault("Referrer-Policy", "same-origin")
    return resposta


async def middleware(request: Request, call_next):
    metodo, caminho = request.method, request.url.path

    # CSRF: escrita vinda de outro site é recusada (o cookie também é SameSite=Lax)
    if metodo not in METODOS_SEGUROS and not _origem_permitida(request):
        return _cabecalhos(JSONResponse({"detail": "Origem não permitida."}, status_code=403))

    if (metodo, caminho) in PUBLICAS:
        return _cabecalhos(await call_next(request))

    sessao = await run_in_threadpool(carregar_sessao, request.cookies.get(COOKIE))
    if sessao is None:
        return _cabecalhos(_negar(request, 401, "Faça login para continuar.", "nao_autenticado"))

    if not await run_in_threadpool(ponte_admin.fazenda_ativa, sessao["fazenda_id"]):
        return _cabecalhos(_negar(request, 403, "O acesso desta fazenda está desativado.",
                                  "fazenda_desativada"))

    if sessao["trocar_senha"] and caminho not in LIBERADAS_NA_TROCA:
        return _cabecalhos(_negar(request, 403, "Troque a senha temporária para continuar.",
                                  "trocar_senha"))

    if not permissoes.permitido(sessao["nivel"], metodo, caminho):
        return _cabecalhos(_negar(request, 403, "Seu perfil não tem permissão para isso.", "sem_permissao"))

    if caminho == "/" and metodo == "GET":
        # o dashboard precisa abrir dentro de /front-end: em "/" os links relativos (estilo/, scripts/) quebram
        return _cabecalhos(RedirectResponse(PAGINA_INICIAL, status_code=303))

    tokens = bf.definir_contexto(sessao["fazenda_id"], sessao)
    try:
        resposta = await call_next(request)
    finally:
        bf.limpar_contexto(tokens)

    if metodo not in METODOS_SEGUROS and resposta.status_code < 400:
        await run_in_threadpool(sincronizar_contador, sessao["fazenda_id"])
    return _cabecalhos(resposta)


# ---------- permissões ----------
def exigir_dono():
    usuario = bf.usuario_atual()
    if not usuario or usuario["nivel"] != "dono":
        raise HTTPException(status_code=403, detail="Apenas o Dono da fazenda pode fazer isso.")


# ---------- rotas de autenticação ----------
auth = APIRouter(prefix="/api/auth", tags=["autenticação"])


def _cookie_seguro(request):
    return request.url.scheme == "https" or os.environ.get("FAZENDAWEB_COOKIE_SECURE") == "1"


@auth.post("/login")
def login(request: Request, dados: dict):
    codigo = str(dados.get("fazenda") or "").strip().lower()
    usuario = str(dados.get("usuario") or "").strip()
    senha = str(dados.get("senha") or "")
    ip = request.client.host if request.client else "?"
    chave_usuario, chave_ip = ("u", ip, codigo, usuario.lower()), ("ip", ip)

    if _bloqueado(chave_usuario, chave_ip):
        raise HTTPException(status_code=429, detail="Muitas tentativas. Aguarde alguns minutos e tente de novo.")

    fazenda = ponte_admin.buscar_por_codigo(codigo) if codigo else None
    conn = bf.abrir(fazenda["id"]) if fazenda and bf.caminho_banco(fazenda["id"]).exists() else None
    try:
        linha = None
        if conn is not None and usuario:
            linha = conn.execute(
                "SELECT id, nome, senha, nivel_acesso, ativo, trocar_senha FROM usuarios "
                "WHERE LOWER(usuario) = LOWER(?) ORDER BY id LIMIT 1",
                (usuario,)).fetchone()
        # confere sempre uma senha, mesmo sem usuário, para não revelar o que existe pelo tempo de resposta
        confere, atualizar = senhas.verificar(senha, linha[2] if linha else senhas.HASH_FALSO)
        if not (conn is not None and linha and linha[4] and confere):
            _registrar_falha(chave_usuario, chave_ip)
            raise HTTPException(status_code=401, detail="Fazenda, usuário ou senha inválidos.")
        if not fazenda["ativa"]:
            raise HTTPException(status_code=403,
                                detail="O acesso desta fazenda está desativado. Fale com o suporte.")
        if atualizar:
            conn.execute("UPDATE usuarios SET senha = ? WHERE id = ?", (senhas.gerar_hash(senha), linha[0]))
            conn.commit()
        token = criar_sessao(conn, linha[0])
    finally:
        if conn is not None:
            conn.close()

    _falhas.pop(chave_usuario, None)
    sincronizar_contador(fazenda["id"])
    resposta = JSONResponse({
        "usuario": {"nome": linha[1], "nivel": permissoes.nivel_efetivo(linha[3])},
        "trocar_senha": bool(linha[5]),
    })
    resposta.set_cookie(COOKIE, f"{fazenda['id']}.{token}", max_age=DURACAO_SESSAO, httponly=True,
                        samesite="lax", secure=_cookie_seguro(request), path="/")
    return resposta


@auth.post("/logout")
def logout(request: Request):
    try:
        _encerrar_sessao(request.cookies.get(COOKIE))
    except Exception as erro:
        print("Falha ao encerrar a sessão:", erro)
    resposta = JSONResponse({"message": "Sessão encerrada."})
    resposta.delete_cookie(COOKIE, path="/")
    return resposta


@auth.post("/logout-todas")
def logout_todas():
    """Encerra TODAS as sessões do usuário (todos os aparelhos), inclusive a atual."""
    usuario = bf.usuario_atual()
    conn = bf.conectar()
    try:
        conn.execute("DELETE FROM sessoes WHERE usuario_id = ?", (usuario["id"],))
        conn.commit()
    finally:
        conn.close()
    registrar_log("Alteração", "usuarios", f'Usuário "{usuario["usuario"]}" saiu de todos os dispositivos')
    resposta = JSONResponse({"message": "Todas as sessões foram encerradas."})
    resposta.delete_cookie(COOKIE, path="/")
    return resposta


@auth.get("/eu")
def quem_sou_eu():
    u = bf.usuario_atual()
    return {"nome": u["nome"], "usuario": u["usuario"], "nivel": u["nivel"],
            "trocar_senha": u["trocar_senha"],
            "fazenda": {"id": u["fazenda_id"], "nome": ponte_admin.nome_fazenda(u["fazenda_id"])}}


@auth.post("/trocar-senha")
def trocar_senha(request: Request, dados: dict):
    usuario = bf.usuario_atual()
    atual, nova = str(dados.get("senha_atual") or ""), dados.get("nova_senha")
    try:
        senhas.validar_nova_senha(nova)
    except ValueError as erro:
        raise HTTPException(status_code=400, detail=str(erro))
    if nova == atual:
        raise HTTPException(status_code=400, detail="A nova senha precisa ser diferente da atual.")

    conn = bf.conectar()
    try:
        guardada = conn.execute("SELECT senha FROM usuarios WHERE id = ?", (usuario["id"],)).fetchone()[0]
        if not senhas.verificar(atual, guardada)[0]:
            raise HTTPException(status_code=400, detail="A senha atual está incorreta.")
        conn.execute("UPDATE usuarios SET senha = ?, trocar_senha = 0 WHERE id = ?",
                     (senhas.gerar_hash(nova), usuario["id"]))
        # as outras sessões desse usuário deixam de valer; a atual continua
        _, token = _separar_cookie(request.cookies.get(COOKIE))
        conn.execute("DELETE FROM sessoes WHERE usuario_id = ? AND token_hash <> ?",
                     (usuario["id"], _hash_token(token)))
        conn.commit()
    finally:
        conn.close()
    registrar_log("Alteração", "usuarios", f'Usuário "{usuario["usuario"]}" trocou a própria senha')
    return {"message": "Senha alterada!"}


# ---------- gestão de usuários da fazenda (só o Dono) ----------
usuarios = APIRouter(prefix="/api/usuarios", tags=["usuários"])
_USUARIO_VALIDO = re.compile(r"^[A-Za-z0-9._-]{3,40}$")


def _alvo(conn, usuario_id):
    linha = conn.execute("SELECT id, usuario, nivel_acesso FROM usuarios WHERE id = ?", (usuario_id,)).fetchone()
    if not linha:
        raise HTTPException(status_code=404, detail="Usuário não encontrado.")
    if (linha[2] or "").strip().lower() == "dono":
        raise HTTPException(status_code=400, detail="A conta do Dono não pode ser alterada por aqui.")
    return linha


@usuarios.get("")
def listar_usuarios():
    exigir_dono()
    conn = bf.conectar()
    try:
        conn.row_factory = sqlite3.Row
        linhas = conn.execute("""SELECT id, nome, usuario, cargo, nivel_acesso, ativo, trocar_senha
                                 FROM usuarios ORDER BY nome COLLATE NOCASE""").fetchall()
    finally:
        conn.close()
    return {"usuarios": [{**dict(l), "nivel_acesso": (l["nivel_acesso"] or "").strip().lower()}
                         for l in linhas]}          # nunca devolve a coluna senha


@usuarios.post("", status_code=201)
def criar_usuario(dados: dict):
    exigir_dono()
    nome = str(dados.get("nome") or "").strip()
    login_novo = str(dados.get("usuario") or "").strip()
    nivel = str(dados.get("nivel") or "").strip().lower()
    if not nome:
        raise HTTPException(status_code=400, detail="Informe o nome.")
    if not _USUARIO_VALIDO.match(login_novo):
        raise HTTPException(status_code=400,
                            detail="O usuário deve ter de 3 a 40 caracteres: letras, números, ponto, hífen ou sublinhado.")
    if nivel not in NIVEIS_CRIAVEIS:
        raise HTTPException(status_code=400, detail="Perfil inválido. Escolha Gerente ou Funcionário.")
    conn = bf.conectar()
    try:
        novo_id, temporaria = contas.criar_usuario(conn, nome, login_novo, nivel, str(dados.get("cargo") or "").strip())
    except contas.UsuarioExistente:
        raise HTTPException(status_code=409, detail="Já existe um usuário com esse login.")
    finally:
        conn.close()
    registrar_log("Cadastro", "usuarios", f'Usuário "{login_novo}" criado com o perfil {nivel}')
    return {"id": novo_id, "usuario": login_novo, "senha_temporaria": temporaria}


@usuarios.put("/{usuario_id}/ativo")
def alterar_ativo(usuario_id: int, dados: dict):
    exigir_dono()
    ativo = 1 if dados.get("ativo") else 0
    conn = bf.conectar()
    try:
        alvo = _alvo(conn, usuario_id)
        conn.execute("UPDATE usuarios SET ativo = ? WHERE id = ?", (ativo, usuario_id))
        if not ativo:
            conn.execute("DELETE FROM sessoes WHERE usuario_id = ?", (usuario_id,))
        conn.commit()
    finally:
        conn.close()
    registrar_log("Alteração", "usuarios", f'Usuário "{alvo[1]}" {"ativado" if ativo else "desativado"}')
    return {"message": "Usuário ativado!" if ativo else "Usuário desativado!"}


@usuarios.put("/{usuario_id}/nivel")
def alterar_nivel(usuario_id: int, dados: dict):
    exigir_dono()
    nivel = str(dados.get("nivel") or "").strip().lower()
    if nivel not in NIVEIS_CRIAVEIS:
        raise HTTPException(status_code=400, detail="Perfil inválido. Escolha Gerente ou Funcionário.")
    conn = bf.conectar()
    try:
        alvo = _alvo(conn, usuario_id)
        conn.execute("UPDATE usuarios SET nivel_acesso = ? WHERE id = ?", (nivel, usuario_id))
        conn.commit()
    finally:
        conn.close()
    registrar_log("Alteração", "usuarios", f'Perfil do usuário "{alvo[1]}" alterado para {nivel}')
    return {"message": "Perfil alterado!"}


@usuarios.post("/{usuario_id}/redefinir-senha")
def redefinir_senha(usuario_id: int):
    exigir_dono()
    temporaria = senhas.gerar_senha_temporaria()
    conn = bf.conectar()
    try:
        alvo = _alvo(conn, usuario_id)
        conn.execute("UPDATE usuarios SET senha = ?, trocar_senha = 1 WHERE id = ?",
                     (senhas.gerar_hash(temporaria), usuario_id))
        conn.execute("DELETE FROM sessoes WHERE usuario_id = ?", (usuario_id,))
        conn.commit()
    finally:
        conn.close()
    registrar_log("Alteração", "usuarios", f'Senha do usuário "{alvo[1]}" redefinida')
    return {"usuario": alvo[1], "senha_temporaria": temporaria}


def instalar_autenticacao(app):
    app.middleware("http")(middleware)
    app.include_router(auth)
    app.include_router(usuarios)
    app.include_router(rotas_perfil)
    app.include_router(rotas_funcionarios)
