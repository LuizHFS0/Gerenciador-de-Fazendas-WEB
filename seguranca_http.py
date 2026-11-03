"""Camada de segurança HTTP (ASGI): limite de tamanho, validação do corpo, limite de abuso, cabeçalhos e erros.

Fica por FORA da autenticação: pedido abusivo ou malformado é barrado antes de gastar banco de dados.
"""
import json
import logging
import secrets
import sqlite3
import time
from collections import deque
from types import SimpleNamespace

from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse

import configuracao
import validacao

MAX_CORPO = 2 * 1024 * 1024
SEM_BUFFER = ("/api/perfil/foto", "/admin/api/perfil/foto")        # as rotas de foto limitam o próprio envio
ROTAS_DE_DOCUMENTACAO = ("/docs", "/redoc", "/openapi.json", "/docs/oauth2-redirect")
METODOS_COM_CORPO = ("POST", "PUT", "PATCH", "DELETE")
log = logging.getLogger("fazendaweb")


def _janela(dicionario, chave, limite, agora):
    fila = dicionario.setdefault(chave, deque())
    while fila and agora - fila[0] > 60:
        fila.popleft()
    if len(fila) >= limite:
        return max(1, int(60 - (agora - fila[0])) + 1)
    fila.append(agora)
    return 0


class SegurancaHTTP:
    def __init__(self, app):
        self.app = app
        self._geral, self._escrita = {}, {}

    async def __call__(self, scope, receive, send):
        if scope["type"] != "http":
            return await self.app(scope, receive, send)
        metodo, caminho = scope["method"], scope["path"]
        cab = {k.decode("latin-1").lower(): v.decode("latin-1") for k, v in scope["headers"]}
        esquema_url = scope.get("scheme", "http")
        enviar = self._com_cabecalhos(send, caminho, esquema_url)

        if configuracao.em_producao() and caminho in ROTAS_DE_DOCUMENTACAO:
            return await self._responder(enviar, 404, {"detail": "Não encontrado."})

        # ---- limite de abuso por IP ----
        cliente = SimpleNamespace(host=scope["client"][0]) if scope.get("client") else None
        ip = configuracao.ip_do_cliente(cab, cliente)
        agora = time.time()
        if len(self._geral) > 20000:
            self._geral.clear(); self._escrita.clear()
        espera = _janela(self._geral, ip, configuracao.limite_geral(), agora)
        if not espera and metodo in METODOS_COM_CORPO:
            espera = _janela(self._escrita, ip, configuracao.limite_escrita(), agora)
        if espera:
            return await self._responder(enviar, 429, {"detail": "Muitos pedidos. Aguarde um instante e tente de novo."},
                                         {"Retry-After": str(espera)})

        # ---- tamanho e validação do corpo ----
        if metodo in METODOS_COM_CORPO and not caminho.endswith(SEM_BUFFER):
            tamanho = cab.get("content-length")
            if tamanho and tamanho.isdigit() and int(tamanho) > MAX_CORPO:
                return await self._responder(enviar, 413, {"detail": "O envio é grande demais."})
            corpo, mais = bytearray(), True
            while mais:
                msg = await receive()
                if msg["type"] == "http.disconnect":
                    return
                corpo += msg.get("body", b"")
                mais = msg.get("more_body", False)
                if len(corpo) > MAX_CORPO:
                    return await self._responder(enviar, 413, {"detail": "O envio é grande demais."})
            corpo = bytes(corpo)
            # quem não tem sessão (e não está tentando o login) recebe 401 da autenticação, sem comentário sobre o corpo
            tem_sessao = "fw_sessao=" in cab.get("cookie", "") or caminho == "/api/auth/login"
            esquema = validacao.esquema_para(metodo, caminho) if tem_sessao else None
            if esquema is not None and corpo:
                if cab.get("content-type", "").split(";")[0].strip().lower() != "application/json":
                    return await self._responder(enviar, 415, {"detail": "Envie os dados em JSON."})
                try:
                    validacao.validar(esquema, json.loads(corpo))
                except (ValueError, validacao.ErroValidacao) as erro:
                    detalhe = str(erro) if isinstance(erro, validacao.ErroValidacao) else "JSON inválido."
                    return await self._responder(enviar, 400, {"detail": detalhe})
            enviado = False

            async def reenviar():
                nonlocal enviado
                if not enviado:
                    enviado = True
                    return {"type": "http.request", "body": corpo, "more_body": False}
                return await receive()
            return await self.app(scope, reenviar, enviar)
        return await self.app(scope, receive, enviar)

    @staticmethod
    async def _responder(enviar, status, corpo, extra=None):
        resposta = JSONResponse(corpo, status_code=status, headers=extra or {})
        await resposta({"type": "http", "headers": [], "method": "GET", "path": "/"}, None, enviar)

    @staticmethod
    def _com_cabecalhos(send, caminho, esquema_url):
        async def enviar(msg):
            if msg["type"] == "http.response.start":
                existentes = {k.decode("latin-1").lower() for k, _ in msg.get("headers", [])}
                tipo = next((v.decode("latin-1") for k, v in msg.get("headers", []) if k.decode("latin-1").lower() == "content-type"), "")
                html = tipo.startswith("text/html")
                pad = {"x-content-type-options": "nosniff", "x-frame-options": "DENY", "referrer-policy": "same-origin",
                       "permissions-policy": "camera=(), microphone=(), geolocation=()",
                       "cross-origin-opener-policy": "same-origin"}
                if html:
                    pad["content-security-policy"] = configuracao.csp()
                if html or tipo.startswith(("application/json", "application/pdf", "application/octet-stream")):
                    pad["cache-control"] = "no-store"          # dados de fazenda não ficam em cache de navegador nem de proxy
                if configuracao.hsts_ativo(esquema_url):
                    pad["strict-transport-security"] = "max-age=31536000; includeSubDomains"
                msg["headers"] = list(msg.get("headers", [])) + [
                    (k.encode("latin-1"), v.encode("latin-1")) for k, v in pad.items() if k not in existentes]
            await send(msg)
        return enviar


# ---------- erros: nunca mostrar detalhe interno ----------
async def _erro_de_validacao(request, erro):
    campos = sorted({str(l) for e in erro.errors() for l in e.get("loc", ())[1:2]})
    return JSONResponse({"detail": "Dados inválidos.", "campos": campos}, status_code=400)


async def _banco_ocupado(request, erro):
    log.warning("Banco indisponível: %s", erro)
    return JSONResponse({"detail": "O sistema está ocupado. Tente de novo em instantes."}, status_code=503,
                        headers={"Retry-After": "2"})


async def _erro_interno(request, erro):
    codigo = secrets.token_hex(4)
    log.error("Erro interno %s em %s %s", codigo, request.method, request.url.path, exc_info=erro)   # detalhes só no log do servidor
    return JSONResponse({"detail": "Erro interno. Se persistir, informe o código.", "codigo_erro": codigo}, status_code=500)


def instalar_seguranca(app):
    app.add_middleware(SegurancaHTTP)                 # por último = mais externo: roda antes da autenticação
    app.add_exception_handler(RequestValidationError, _erro_de_validacao)
    app.add_exception_handler(sqlite3.OperationalError, _banco_ocupado)
    app.add_exception_handler(Exception, _erro_interno)
