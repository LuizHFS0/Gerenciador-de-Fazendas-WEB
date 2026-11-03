"""Painel do SuperAdmin: uma aplicação SEPARADA, montada em /admin dentro do mesmo site.

Separação (aplicada no servidor, não só na tela):
- Autenticação própria (superadmin.db, cookie fw_admin só em /admin). Um login de fazenda não vale aqui, e vice-versa.
- Só opera sobre dados ADMINISTRATIVOS (admin.db). Este módulo não importa nada de banco de fazenda.
- A única ponte com o lado das fazendas é provisionar_fazenda: cria a fazenda com o Dono inicial e, enquanto o
  Dono não ativou a conta, reemite a senha temporária. Não existe rota que leia, liste ou altere dados internos.
- Lista fechada de operações: tudo o que não está declarado aqui não existe.
"""
import math
import re
import sqlite3
import time
from datetime import date
from pathlib import Path

from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import FileResponse, JSONResponse, RedirectResponse, Response
from fastapi.staticfiles import StaticFiles
from starlette.concurrency import run_in_threadpool

import admin_banco
import admin_seguranca as seg
import configuracao
import senhas
from provisionar_fazenda import AcessoJaAtivado, ProvisionamentoErro, provisionar, reemitir_acesso_inicial

PASTA_FRONT = Path(__file__).resolve().parent / "admin-front"
PAGINA_LOGIN = "/admin/login.html"
PUBLICAS = {("POST", "/api/login"), ("POST", "/api/logout"), ("GET", "/login.html")}
METODOS_SEGUROS = ("GET", "HEAD", "OPTIONS")
RESERVADOS = {"admin", "api", "login", "logout", "suporte", "www", "app", "static", "front-end", "dados", "root"}
CODIGO_VALIDO = re.compile(r"^[a-z0-9][a-z0-9-]{2,29}$")
ORDENS = {"nome": "LOWER(f.nome)", "funcionarios": "f.funcionarios", "plano": "f.plano",
          "pagamento": "f.pagamento", "ativa": "f.ativa", "criada_em": "f.criada_em"}
LIMITE_FOTO = 200 * 1024


def _erro(status, mensagem):
    return HTTPException(status_code=status, detail=mensagem)


def _caminho_relativo(request):
    caminho, raiz = request.scope["path"], request.scope.get("root_path", "")
    return caminho[len(raiz):] if raiz and caminho.startswith(raiz) else caminho


def _ip(request):
    return configuracao.ip_do_cliente(request.headers, request.client)


def _eu(request):
    return request.state.superadmin


def _texto(dados, campo, rotulo, minimo=0, maximo=200, obrigatorio=False):
    valor = dados.get(campo)
    if valor is None or valor == "":
        if obrigatorio:
            raise _erro(400, f"Informe {rotulo}.")
        return ""
    if not isinstance(valor, str):
        raise _erro(400, f"{rotulo[0].upper() + rotulo[1:]} inválido.")
    valor = valor.strip()
    if len(valor) < minimo or len(valor) > maximo:
        raise _erro(400, f"{rotulo[0].upper() + rotulo[1:]} deve ter de {minimo} a {maximo} caracteres.")
    return valor


def _fazenda_provisionada(conn, fazenda_id):
    linha = conn.execute("SELECT * FROM fazendas WHERE id = ? AND situacao = 'provisionada'", (fazenda_id,)).fetchone()
    if not linha:
        raise _erro(404, "Fazenda não encontrada.")
    return linha


def _plano_valido(conn, codigo):
    if not conn.execute("SELECT 1 FROM planos WHERE codigo = ? AND ativo = 1", (codigo,)).fetchone():
        raise _erro(400, "Plano inválido.")


def _confirmar_senha(request, dados):
    """Operações sensíveis pedem a senha do SuperAdmin de novo. Erros contam para o bloqueio de tentativas."""
    sa, ip = _eu(request), _ip(request)
    chave_u, chave_ip = ("u", ip, sa["usuario"].lower()), ("ip", ip)
    if seg.bloqueado(chave_u, chave_ip):
        raise _erro(429, "Muitas tentativas. Aguarde alguns minutos.")
    conn = admin_banco.abrir_superadmin()
    try:
        hash_atual = conn.execute("SELECT senha_hash FROM superadmins WHERE id = ?", (sa["id"],)).fetchone()["senha_hash"]
        if not senhas.verificar(str(dados.get("senha_confirmacao") or "")[:200], hash_atual)[0]:
            seg.registrar_falha(chave_u, chave_ip)
            seg.auditar(conn, sa["id"], "confirmacao_falhou", "", "Senha de confirmação incorreta", ip)
            raise _erro(403, "Senha de confirmação incorreta.")
    finally:
        conn.close()


def _auditar(request, acao, alvo="", detalhe=""):
    conn = admin_banco.abrir_superadmin()
    try:
        seg.auditar(conn, _eu(request)["id"], acao, alvo, detalhe, _ip(request))
    finally:
        conn.close()


def _linha_fazenda(l):
    return {"id": l["id"], "codigo": l["codigo"], "nome": l["nome"], "funcionarios": l["funcionarios"],
            "plano": l["plano"], "pagamento": l["pagamento"], "ativa": bool(l["ativa"]), "criada_em": l["criada_em"]}


def criar_admin_app(pasta_front=None):
    admin = FastAPI(docs_url=None, redoc_url=None, openapi_url=None)

    # ---------- proteção de TUDO o que é do admin ----------
    @admin.middleware("http")
    async def protecao(request: Request, call_next):
        rel, metodo = _caminho_relativo(request), request.method
        pagina = rel == "/" or rel.endswith(".html")

        def negar(status, detalhe):
            if pagina and metodo == "GET":
                return RedirectResponse(PAGINA_LOGIN, status_code=303)
            return JSONResponse({"detail": detalhe}, status_code=status)

        if metodo not in METODOS_SEGUROS:
            if not seg.origem_ok(request):
                return JSONResponse({"detail": "Origem não permitida."}, status_code=403)
            if not seg.cabecalho_ok(request):
                return JSONResponse({"detail": "Cabeçalho obrigatório ausente."}, status_code=403)
        if (metodo, rel) in PUBLICAS:
            return await call_next(request)
        sessao = await run_in_threadpool(seg.carregar_sessao, request.cookies.get(seg.COOKIE))
        if sessao is None:
            return negar(401, "Faça login como SuperAdmin.")
        request.state.superadmin = sessao
        return await call_next(request)

    # ---------- login, logout e conta ----------
    @admin.post("/api/login")
    def login(request: Request, dados: dict):
        usuario = seg.limpar_texto(dados.get("usuario"), 60).strip()
        senha = str(dados.get("senha") or "")[:200]
        ip = _ip(request)
        chave_u, chave_ip = ("u", ip, usuario.lower()), ("ip", ip)
        if seg.bloqueado(chave_u, chave_ip):
            raise _erro(429, "Muitas tentativas. Aguarde alguns minutos e tente de novo.")
        conn = admin_banco.abrir_superadmin()
        try:
            linha = conn.execute("SELECT id, nome, senha_hash, ativo FROM superadmins WHERE LOWER(usuario) = LOWER(?)",
                                 (usuario,)).fetchone()
            confere = senhas.verificar(senha, linha["senha_hash"] if linha else senhas.HASH_FALSO)[0]
            if not (linha and linha["ativo"] and confere):
                seg.registrar_falha(chave_u, chave_ip)
                seg.auditar(conn, linha["id"] if linha else None, "login_falhou", usuario, "", ip)
                raise _erro(401, "Usuário ou senha inválidos.")
            token = seg.criar_sessao(conn, linha["id"])
            conn.execute("UPDATE superadmins SET ultimo_login = ? WHERE id = ?", (admin_banco.agora(), linha["id"]))
            conn.commit()
            seg.auditar(conn, linha["id"], "login", usuario, "", ip)
        finally:
            conn.close()
        seg.limpar_falhas(chave_u)
        resposta = JSONResponse({"nome": linha["nome"]})
        resposta.set_cookie(seg.COOKIE, token, max_age=seg.DURACAO, httponly=True, samesite="strict",
                            secure=configuracao.cookie_seguro(request.url.scheme), path="/admin")
        return resposta

    @admin.post("/api/logout")
    def logout(request: Request):
        token = request.cookies.get(seg.COOKIE)
        try:
            sessao = seg.carregar_sessao(token)
            if sessao:
                _auditar_direto(sessao["id"], "logout", sessao["usuario"], _ip(request))
            seg.encerrar_sessao(token)
        except Exception as erro:                                  # sair nunca deve falhar para o usuário
            print("Falha ao encerrar a sessão do admin:", type(erro).__name__)
        resposta = JSONResponse({"message": "Sessão encerrada."})
        resposta.delete_cookie(seg.COOKIE, path="/admin")
        return resposta

    def _auditar_direto(superadmin_id, acao, alvo, ip):
        conn = admin_banco.abrir_superadmin()
        try:
            seg.auditar(conn, superadmin_id, acao, alvo, "", ip)
        finally:
            conn.close()

    @admin.post("/api/logout-todas")
    def logout_todas(request: Request):
        sa = _eu(request)
        conn = admin_banco.abrir_superadmin()
        try:
            conn.execute("DELETE FROM sessoes_admin WHERE superadmin_id = ?", (sa["id"],))
            conn.commit()
            seg.auditar(conn, sa["id"], "logout_todas", sa["usuario"], "", _ip(request))
        finally:
            conn.close()
        resposta = JSONResponse({"message": "Todas as sessões foram encerradas."})
        resposta.delete_cookie(seg.COOKIE, path="/admin")
        return resposta

    @admin.post("/api/trocar-senha")
    def trocar_senha(request: Request, dados: dict):
        sa = _eu(request)
        nova = dados.get("nova_senha")
        try:
            seg.validar_senha(nova)
        except ValueError as erro:
            raise _erro(400, str(erro))
        conn = admin_banco.abrir_superadmin()
        try:
            atual = conn.execute("SELECT senha_hash FROM superadmins WHERE id = ?", (sa["id"],)).fetchone()["senha_hash"]
            if not senhas.verificar(str(dados.get("senha_atual") or "")[:200], atual)[0]:
                raise _erro(400, "A senha atual está incorreta.")
            if nova == dados.get("senha_atual"):
                raise _erro(400, "A nova senha precisa ser diferente da atual.")
            conn.execute("UPDATE superadmins SET senha_hash = ? WHERE id = ?", (senhas.gerar_hash(nova), sa["id"]))
            conn.execute("DELETE FROM sessoes_admin WHERE superadmin_id = ? AND token_hash <> ?",
                         (sa["id"], seg._hash(request.cookies.get(seg.COOKIE) or "")))
            conn.commit()
            seg.auditar(conn, sa["id"], "senha_trocada", sa["usuario"], "", _ip(request))
        finally:
            conn.close()
        return {"message": "Senha alterada!"}

    # ---------- perfil e foto (o mesmo menu de usuário das fazendas) ----------
    @admin.get("/api/perfil")
    def perfil(request: Request):
        sa = _eu(request)
        conn = admin_banco.abrir_superadmin()
        try:
            f = conn.execute("SELECT atualizada_em FROM superadmins_fotos WHERE superadmin_id = ?", (sa["id"],)).fetchone()
        finally:
            conn.close()
        return {"nome": sa["nome"], "usuario": sa["usuario"], "perfil_rotulo": "SuperAdmin", "fazenda": None,
                "tem_foto": f is not None, "foto_versao": f["atualizada_em"] if f else None,
                "sessao_expira_em": sa["expira_em"]}

    @admin.get("/api/perfil/foto")
    def ver_foto(request: Request):
        conn = admin_banco.abrir_superadmin()
        try:
            f = conn.execute("SELECT tipo, dados FROM superadmins_fotos WHERE superadmin_id = ?", (_eu(request)["id"],)).fetchone()
        finally:
            conn.close()
        if not f:
            raise _erro(404, "Sem foto cadastrada.")
        return Response(content=bytes(f["dados"]), media_type=f["tipo"],
                        headers={"Cache-Control": "private, max-age=3600", "Content-Security-Policy": "default-src 'none'"})

    def _gravar_foto(superadmin_id, tipo, dados):
        versao = int(time.time())
        conn = admin_banco.abrir_superadmin()
        try:
            conn.execute("""INSERT INTO superadmins_fotos (superadmin_id, tipo, dados, atualizada_em) VALUES (?, ?, ?, ?)
                            ON CONFLICT(superadmin_id) DO UPDATE SET tipo = excluded.tipo, dados = excluded.dados,
                                                                     atualizada_em = excluded.atualizada_em""",
                         (superadmin_id, tipo, dados, versao))
            conn.commit()
        finally:
            conn.close()
        return versao

    @admin.put("/api/perfil/foto")
    async def salvar_foto(request: Request):
        informado = (request.headers.get("content-type") or "").split(";")[0].strip().lower()
        if informado not in {"image/jpeg", "image/png", "image/webp"}:
            raise _erro(415, "Envie uma imagem JPEG, PNG ou WebP.")
        partes, total = [], 0
        async for pedaco in request.stream():
            total += len(pedaco)
            if total > LIMITE_FOTO:
                raise _erro(413, "A foto é grande demais (máximo de 200 KB).")
            partes.append(pedaco)
        dados = b"".join(partes)
        tipo = seg.tipo_pela_assinatura(dados)
        if tipo is None or len(dados) < 100:
            raise _erro(400, "O arquivo não é uma imagem válida.")
        versao = await run_in_threadpool(_gravar_foto, _eu(request)["id"], tipo, dados)
        return {"message": "Foto atualizada!", "foto_versao": versao}

    @admin.delete("/api/perfil/foto")
    def remover_foto(request: Request):
        conn = admin_banco.abrir_superadmin()
        try:
            conn.execute("DELETE FROM superadmins_fotos WHERE superadmin_id = ?", (_eu(request)["id"],))
            conn.commit()
        finally:
            conn.close()
        return {"message": "Foto removida."}

    # ---------- planos e dashboard (só dados administrativos) ----------
    @admin.get("/api/planos")
    def planos():
        conn = admin_banco.abrir_admin()
        try:
            return {"planos": [dict(l) for l in conn.execute("SELECT codigo, nome FROM planos WHERE ativo = 1 ORDER BY nome")]}
        finally:
            conn.close()

    @admin.get("/api/dashboard")
    def dashboard():
        conn = admin_banco.abrir_admin()
        try:
            prov = "situacao = 'provisionada'"
            resumo = conn.execute(f"""SELECT COUNT(*) AS total, COALESCE(SUM(ativa = 1), 0) AS ativas,
                                             COALESCE(SUM(ativa = 0), 0) AS desativadas,
                                             COALESCE(SUM(funcionarios), 0) AS funcionarios,
                                             COALESCE(SUM(pagamento = 'em_dia'), 0) AS em_dia,
                                             COALESCE(SUM(pagamento = 'pendente'), 0) AS pendentes,
                                             COALESCE(SUM(pagamento = 'pendente' AND ativa = 1), 0) AS pendentes_ativas
                                      FROM fazendas WHERE {prov}""").fetchone()
            por_plano = [dict(l) for l in conn.execute(f"""
                SELECT p.codigo, p.nome, COUNT(f.id) AS total,
                       COALESCE(SUM(f.pagamento = 'em_dia'), 0) AS em_dia,
                       COALESCE(SUM(f.pagamento = 'pendente'), 0) AS pendentes
                FROM planos p LEFT JOIN fazendas f ON f.plano = p.codigo AND f.{prov}
                WHERE p.ativo = 1 GROUP BY p.codigo, p.nome ORDER BY p.nome""")]
            meses_banco = {l["mes"]: l["n"] for l in conn.execute(f"""
                SELECT substr(criada_em, 1, 7) AS mes, COUNT(*) AS n FROM fazendas WHERE {prov} GROUP BY mes""")}
        finally:
            conn.close()
        hoje, meses = date.today(), []
        for atras in range(11, -1, -1):
            m, a = hoje.month - atras, hoje.year
            while m <= 0:
                m, a = m + 12, a - 1
            chave = f"{a:04d}-{m:02d}"
            meses.append({"mes": chave, "cadastros": meses_banco.get(chave, 0)})
        sc = admin_banco.abrir_superadmin()
        try:
            atividade = [dict(l) for l in sc.execute("""
                SELECT a.quando, a.acao, a.alvo, s.nome AS superadmin
                FROM auditoria_admin a LEFT JOIN superadmins s ON s.id = a.superadmin_id
                ORDER BY a.id DESC LIMIT 8""")]
        finally:
            sc.close()
        return {**dict(resumo), "por_plano": por_plano, "cadastros_por_mes": meses, "atividade": atividade}

    # ---------- fazendas ----------
    @admin.get("/api/fazendas")
    def listar_fazendas(busca: str = "", plano: str = "", pagamento: str = "", situacao: str = "",
                        ordem: str = "nome", direcao: str = "asc", pagina: int = 1, por_pagina: int = 10):
        if ordem not in ORDENS or direcao not in ("asc", "desc"):
            raise _erro(400, "Ordenação inválida.")
        if pagamento and pagamento not in admin_banco.PAGAMENTOS:
            raise _erro(400, "Situação de pagamento inválida.")
        if situacao not in ("", "ativa", "desativada"):
            raise _erro(400, "Situação inválida.")
        pagina, por_pagina = max(1, pagina), min(100, max(5, por_pagina))
        onde, params = ["f.situacao = 'provisionada'"], []
        busca = busca.strip()[:100]
        if busca:
            padrao = "%" + busca.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_") + "%"
            onde.append("(f.nome LIKE ? ESCAPE '\\' OR f.codigo LIKE ? ESCAPE '\\')")
            params += [padrao, padrao]
        if plano:
            onde.append("f.plano = ?")
            params.append(plano)
        if pagamento:
            onde.append("f.pagamento = ?")
            params.append(pagamento)
        if situacao:
            onde.append("f.ativa = ?")
            params.append(1 if situacao == "ativa" else 0)
        filtro = " AND ".join(onde)
        conn = admin_banco.abrir_admin()
        try:
            total = conn.execute(f"SELECT COUNT(*) FROM fazendas f WHERE {filtro}", params).fetchone()[0]
            linhas = conn.execute(
                f"""SELECT f.*, COALESCE(p.nome, f.plano) AS plano_nome
                    FROM fazendas f LEFT JOIN planos p ON p.codigo = f.plano
                    WHERE {filtro}
                    ORDER BY {ORDENS[ordem]} {direcao.upper()}, f.id
                    LIMIT ? OFFSET ?""", params + [por_pagina, (pagina - 1) * por_pagina]).fetchall()
        finally:
            conn.close()
        itens = [{**_linha_fazenda(l), "plano_nome": l["plano_nome"]} for l in linhas]
        return {"itens": itens, "total": total, "pagina": pagina, "por_pagina": por_pagina,
                "paginas": max(1, math.ceil(total / por_pagina))}

    @admin.get("/api/fazendas/{fazenda_id}")
    def detalhe_fazenda(fazenda_id: int):
        conn = admin_banco.abrir_admin()
        try:
            l = _fazenda_provisionada(conn, fazenda_id)
            return {**_linha_fazenda(l), "contato_nome": l["contato_nome"], "contato_email": l["contato_email"],
                    "contato_telefone": l["contato_telefone"], "observacoes": l["observacoes"],
                    "pagamento_atualizado_em": l["pagamento_atualizado_em"]}
        finally:
            conn.close()

    @admin.post("/api/fazendas", status_code=201)
    def cadastrar_fazenda(request: Request, dados: dict):
        nome = _texto(dados, "nome", "o nome da fazenda", 3, 100, True)
        codigo = _texto(dados, "codigo", "o código da fazenda", 3, 30, True).lower()
        if not CODIGO_VALIDO.match(codigo) or codigo in RESERVADOS:
            raise _erro(400, "Código inválido ou reservado: use de 3 a 30 letras minúsculas, números e hífen.")
        contato_nome = _texto(dados, "contato_nome", "o nome do contato", 0, 100)
        contato_email = _texto(dados, "contato_email", "o e-mail do contato", 0, 120)
        if contato_email and not re.fullmatch(r"[^@\s]+@[^@\s]+\.[^@\s]+", contato_email):
            raise _erro(400, "E-mail do contato inválido.")
        contato_telefone = _texto(dados, "contato_telefone", "o telefone do contato", 0, 30)
        observacoes = _texto(dados, "observacoes", "as observações", 0, 500)
        plano = _texto(dados, "plano", "o plano", 1, 30, True)
        pagamento = _texto(dados, "pagamento", "a situação do pagamento", 1, 20, True)
        if pagamento not in admin_banco.PAGAMENTOS:
            raise _erro(400, "Situação de pagamento inválida.")
        dono_nome = _texto(dados, "dono_nome", "o nome do Dono", 3, 100, True)
        if len(re.findall(r"[^\W\d_]{2,}", dono_nome)) < 1:
            raise _erro(400, "O nome do Dono precisa ter letras.")
        if dados.get("pagamento_verificado") is not True:
            raise _erro(400, "Confirme que você verificou o pagamento.")
        _confirmar_senha(request, dados)

        conn = admin_banco.abrir_admin()
        try:
            _plano_valido(conn, plano)
            # sobras de um cadastro interrompido (processo caiu no meio) não bloqueiam o código
            conn.execute("""DELETE FROM fazendas WHERE situacao = 'provisionando'
                            AND criada_em < datetime('now', 'localtime', '-10 minutes')""")
            try:
                cur = conn.execute("""INSERT INTO fazendas (codigo, nome, ativa, funcionarios, criada_em, plano, pagamento,
                                                            pagamento_atualizado_em, contato_nome, contato_email,
                                                            contato_telefone, observacoes, situacao)
                                      VALUES (?, ?, 0, 0, ?, ?, ?, ?, ?, ?, ?, ?, 'provisionando')""",
                                   (codigo, nome, admin_banco.agora(), plano, pagamento, admin_banco.agora(),
                                    contato_nome, contato_email, contato_telefone, observacoes))
            except sqlite3.IntegrityError:
                raise _erro(409, "Já existe uma fazenda com esse código.")
            conn.commit()
            fazenda_id = cur.lastrowid
            try:
                acesso = provisionar(fazenda_id, nome, dono_nome)
            except ProvisionamentoErro as erro:
                conn.execute("DELETE FROM fazendas WHERE id = ?", (fazenda_id,))
                conn.commit()
                _auditar(request, "fazenda_falhou", codigo, str(erro))
                raise _erro(400, str(erro))
            except Exception:
                conn.execute("DELETE FROM fazendas WHERE id = ?", (fazenda_id,))
                conn.commit()
                _auditar(request, "fazenda_falhou", codigo, "erro inesperado no provisionamento")
                raise _erro(500, "Não foi possível criar a fazenda. Nada foi cadastrado; tente de novo.")
            conn.execute("UPDATE fazendas SET ativa = 1, situacao = 'provisionada' WHERE id = ?", (fazenda_id,))
            conn.commit()
        finally:
            conn.close()
        _auditar(request, "fazenda_criada", codigo, f"plano={plano}, pagamento={pagamento}")
        return {"fazenda": {"id": fazenda_id, "codigo": codigo, "nome": nome},
                "acesso": {"codigo_fazenda": codigo, "usuario": acesso["usuario"],
                           "senha_temporaria": acesso["senha_temporaria"]}}

    @admin.put("/api/fazendas/{fazenda_id}/ativa")
    def alterar_ativa(fazenda_id: int, request: Request, dados: dict):
        if not isinstance(dados.get("ativa"), bool):
            raise _erro(400, "Informe se a fazenda deve ficar ativa (true) ou desativada (false).")
        conn = admin_banco.abrir_admin()
        try:
            l = _fazenda_provisionada(conn, fazenda_id)
            conn.execute("UPDATE fazendas SET ativa = ? WHERE id = ?", (1 if dados["ativa"] else 0, fazenda_id))
            conn.commit()
        finally:
            conn.close()
        _auditar(request, "fazenda_ativada" if dados["ativa"] else "fazenda_desativada", l["codigo"])
        return {"ativa": dados["ativa"]}

    @admin.put("/api/fazendas/{fazenda_id}/plano")
    def alterar_plano(fazenda_id: int, request: Request, dados: dict):
        plano = _texto(dados, "plano", "o plano", 1, 30, True)
        conn = admin_banco.abrir_admin()
        try:
            l = _fazenda_provisionada(conn, fazenda_id)
            _plano_valido(conn, plano)
            conn.execute("UPDATE fazendas SET plano = ? WHERE id = ?", (plano, fazenda_id))
            conn.commit()
        finally:
            conn.close()
        _auditar(request, "plano_alterado", l["codigo"], f"{l['plano']} -> {plano}")
        return {"plano": plano}

    @admin.put("/api/fazendas/{fazenda_id}/pagamento")
    def alterar_pagamento(fazenda_id: int, request: Request, dados: dict):
        pagamento = dados.get("pagamento")
        if pagamento not in admin_banco.PAGAMENTOS:
            raise _erro(400, "Situação de pagamento inválida.")
        conn = admin_banco.abrir_admin()
        try:
            l = _fazenda_provisionada(conn, fazenda_id)
            conn.execute("UPDATE fazendas SET pagamento = ?, pagamento_atualizado_em = ? WHERE id = ?",
                         (pagamento, admin_banco.agora(), fazenda_id))
            conn.commit()
        finally:
            conn.close()
        _auditar(request, "pagamento_alterado", l["codigo"], f"{l['pagamento']} -> {pagamento}")
        return {"pagamento": pagamento}

    @admin.post("/api/fazendas/{fazenda_id}/reemitir-acesso")
    def reemitir_acesso(fazenda_id: int, request: Request, dados: dict):
        conn = admin_banco.abrir_admin()
        try:
            l = _fazenda_provisionada(conn, fazenda_id)
        finally:
            conn.close()
        _confirmar_senha(request, dados)
        try:
            acesso = reemitir_acesso_inicial(fazenda_id)
        except AcessoJaAtivado as erro:
            _auditar(request, "reemissao_recusada", l["codigo"], "Dono já ativou o acesso")
            raise _erro(409, str(erro))
        except ProvisionamentoErro as erro:
            raise _erro(400, str(erro))
        _auditar(request, "acesso_dono_reemitido", l["codigo"])
        return {"acesso": {"codigo_fazenda": l["codigo"], "usuario": acesso["usuario"],
                           "senha_temporaria": acesso["senha_temporaria"]}}

    # ---------- auditoria do próprio painel ----------
    @admin.get("/api/auditoria")
    def auditoria(pagina: int = 1, por_pagina: int = 20):
        pagina, por_pagina = max(1, pagina), min(100, max(5, por_pagina))
        conn = admin_banco.abrir_superadmin()
        try:
            total = conn.execute("SELECT COUNT(*) FROM auditoria_admin").fetchone()[0]
            itens = [dict(l) for l in conn.execute("""
                SELECT a.id, a.quando, a.acao, a.alvo, a.detalhe, a.ip, s.nome AS superadmin
                FROM auditoria_admin a LEFT JOIN superadmins s ON s.id = a.superadmin_id
                ORDER BY a.id DESC LIMIT ? OFFSET ?""", (por_pagina, (pagina - 1) * por_pagina))]
        finally:
            conn.close()
        return {"itens": itens, "total": total, "pagina": pagina, "por_pagina": por_pagina,
                "paginas": max(1, math.ceil(total / por_pagina))}

    # ---------- páginas (por último: o que não for API cai aqui) ----------
    @admin.get("/")
    def raiz():
        return RedirectResponse("/admin/dashboard.html", status_code=303)

    pasta = Path(pasta_front) if pasta_front else PASTA_FRONT
    pasta.mkdir(parents=True, exist_ok=True)
    admin.mount("/", StaticFiles(directory=pasta), name="admin-front")
    return admin


def montar_admin(app, pasta_front=None):
    admin_banco.garantir_admin_db()
    admin_banco.garantir_superadmin_db()
    app.mount("/admin", criar_admin_app(pasta_front), name="admin")
