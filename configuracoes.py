"""Configurações da fazenda: dados cadastrais, logotipo, unidades de medida e preferências.

Tudo fica no banco da própria fazenda (tabela fazenda + fazenda_logo), então cada fazenda tem as suas.
- Dono: vê e altera tudo (GET/PUT /api/configuracoes, PUT/DELETE /api/configuracoes/logo).
- Qualquer usuário logado: lê só o que as telas precisam (GET /api/configuracoes/preferencias e /logo).
"""
import re
import sqlite3
import time

from fastapi import APIRouter, HTTPException, Request, Response
from starlette.concurrency import run_in_threadpool

import banco_fazenda as bf
import ponte_admin
from logs import registrar_log
from perfil import tipo_pela_assinatura

router = APIRouter(prefix="/api/configuracoes", tags=["configuracoes"])

LIMITE_LOGO = 300 * 1024                      # o navegador já reduz para no máximo 512 px
TIPOS_ACEITOS = {"image/jpeg", "image/png", "image/webp"}
UNIDADES_PESO = ("kg", "arroba", "lb")
UNIDADES_AREA = ("ha", "alqueire_mg", "alqueire_sp")
PERIODOS_RELATORIO = (1, 7, 30)               # as mesmas opções das telas de leite
EMAIL = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")

TEXTOS = ("nome_fazenda", "dono", "endereco", "telefone", "email", "data_fundacao")
BOOLEANOS = ("notif_vacinas", "notif_manutencoes", "notif_estoque", "relatorio_logo")
COLUNAS = TEXTOS + ("tamanho", "unidade_peso", "unidade_area", "alerta_dias", "relatorio_periodo_dias") + BOOLEANOS

PADRAO = {"nome_fazenda": "", "dono": "", "endereco": "", "telefone": "", "email": "", "data_fundacao": None,
          "tamanho": None, "unidade_peso": "kg", "unidade_area": "ha",
          "notif_vacinas": True, "notif_manutencoes": True, "notif_estoque": True, "alerta_dias": 15,
          "relatorio_periodo_dias": 30, "relatorio_logo": True}


def ler():
    """Configurações da fazenda de quem está logado (com padrões se ainda não houver cadastro)."""
    conn = bf.conectar()
    conn.row_factory = sqlite3.Row
    try:
        linha = conn.execute(f"SELECT {', '.join(COLUNAS)} FROM fazenda ORDER BY id LIMIT 1").fetchone()
        logo = conn.execute("SELECT atualizada_em FROM fazenda_logo WHERE id = 1").fetchone()
    finally:
        conn.close()
    dados = dict(PADRAO)
    if linha:
        dados.update({c: linha[c] for c in COLUNAS if linha[c] is not None})
        for c in ("dono", "endereco", "telefone", "email"):
            dados[c] = linha[c] or ""
    else:
        dados["nome_fazenda"] = ponte_admin.nome_fazenda(bf.usuario_atual()["fazenda_id"]) or ""
    for c in BOOLEANOS:
        dados[c] = bool(dados[c])
    dados["tem_logo"] = logo is not None
    dados["logo_versao"] = logo[0] if logo else None
    return dados


def logo_bytes():
    conn = bf.conectar()
    try:
        linha = conn.execute("SELECT tipo, dados FROM fazenda_logo WHERE id = 1").fetchone()
    finally:
        conn.close()
    return (linha[0], bytes(linha[1])) if linha else None


@router.get("")
def obter():
    return ler()


@router.get("/preferencias")
def preferencias():
    """O que qualquer tela precisa saber (nome, unidades, alertas, relatórios). Sem telefone, e-mail ou endereço."""
    d = ler()
    return {c: d[c] for c in ("nome_fazenda", "unidade_peso", "unidade_area", "notif_vacinas", "notif_manutencoes",
                              "notif_estoque", "alerta_dias", "relatorio_periodo_dias", "relatorio_logo",
                              "tem_logo", "logo_versao")}


@router.put("")
def salvar(dados: dict):
    valores = {}
    for campo in TEXTOS:
        if campo in dados:
            valores[campo] = (str(dados[campo]).strip() if dados[campo] is not None else "") or None
    if "nome_fazenda" in valores and valores["nome_fazenda"] is None:
        raise HTTPException(status_code=400, detail="Informe o nome da fazenda.")
    if valores.get("email") and not EMAIL.match(valores["email"]):
        raise HTTPException(status_code=400, detail="Informe um e-mail válido.")
    if "tamanho" in dados:
        valores["tamanho"] = float(dados["tamanho"]) if dados["tamanho"] not in (None, "") else None
    for campo, validos in (("unidade_peso", UNIDADES_PESO), ("unidade_area", UNIDADES_AREA)):
        if campo in dados:
            if dados[campo] not in validos:
                raise HTTPException(status_code=400, detail=f"Campo '{campo}' inválido (use: {', '.join(validos)}).")
            valores[campo] = dados[campo]
    if "alerta_dias" in dados:
        valores["alerta_dias"] = int(dados["alerta_dias"])
    if "relatorio_periodo_dias" in dados:
        if int(dados["relatorio_periodo_dias"]) not in PERIODOS_RELATORIO:
            raise HTTPException(status_code=400, detail="Período de relatório inválido (use 1, 7 ou 30 dias).")
        valores["relatorio_periodo_dias"] = int(dados["relatorio_periodo_dias"])
    for campo in BOOLEANOS:
        if campo in dados:
            valores[campo] = 1 if dados[campo] else 0

    conn = bf.conectar()
    try:
        existe = conn.execute("SELECT id FROM fazenda ORDER BY id LIMIT 1").fetchone()
        colunas = [c for c in COLUNAS if c in valores]                    # nomes vêm da lista fixa acima, nunca do cliente
        if existe and colunas:
            conn.execute(f"UPDATE fazenda SET {', '.join(c + ' = ?' for c in colunas)} WHERE id = ?",
                         [valores[c] for c in colunas] + [existe[0]])
        elif not existe:
            if not valores.get("nome_fazenda"):
                raise HTTPException(status_code=400, detail="Informe o nome da fazenda.")
            conn.execute(f"INSERT INTO fazenda ({', '.join(colunas)}) VALUES ({', '.join('?' * len(colunas))})",
                         [valores[c] for c in colunas])
        conn.commit()
    except sqlite3.IntegrityError:
        raise HTTPException(status_code=409, detail="Não foi possível salvar: o nome da fazenda já está em uso.")
    finally:
        conn.close()
    registrar_log("Alteração", "fazenda", "Configurações da fazenda atualizadas")
    return {"message": "Configurações salvas!"}


# ---------- logotipo ----------
@router.get("/logo")
def obter_logo():
    logo = logo_bytes()
    if not logo:
        raise HTTPException(status_code=404, detail="Sem logotipo cadastrado.")
    return Response(content=logo[1], media_type=logo[0],
                    headers={"Cache-Control": "private, max-age=3600", "Content-Security-Policy": "default-src 'none'"})


def _gravar_logo(tipo, dados):
    versao = int(time.time())
    conn = bf.conectar()
    try:
        conn.execute("""INSERT INTO fazenda_logo (id, tipo, dados, atualizada_em) VALUES (1, ?, ?, ?)
                        ON CONFLICT(id) DO UPDATE SET tipo = excluded.tipo, dados = excluded.dados,
                                                      atualizada_em = excluded.atualizada_em""", (tipo, dados, versao))
        conn.commit()
    finally:
        conn.close()
    return versao


@router.put("/logo")
async def salvar_logo(request: Request):
    tipo_informado = (request.headers.get("content-type") or "").split(";")[0].strip().lower()
    if tipo_informado not in TIPOS_ACEITOS:
        raise HTTPException(status_code=415, detail="Envie uma imagem JPEG, PNG ou WebP.")
    partes, total = [], 0
    async for pedaco in request.stream():                 # corta o envio assim que passar do limite
        total += len(pedaco)
        if total > LIMITE_LOGO:
            raise HTTPException(status_code=413, detail="O logotipo é grande demais (máximo de 300 KB).")
        partes.append(pedaco)
    dados = b"".join(partes)
    tipo = tipo_pela_assinatura(dados)                    # o que o cliente diz não basta: confere os primeiros bytes
    if tipo is None or len(dados) < 100:
        raise HTTPException(status_code=400, detail="O arquivo não é uma imagem válida.")
    versao = await run_in_threadpool(_gravar_logo, tipo, dados)
    registrar_log("Alteração", "fazenda", "Logotipo da fazenda atualizado")
    return {"message": "Logotipo atualizado!", "logo_versao": versao}


@router.delete("/logo")
def remover_logo():
    conn = bf.conectar()
    try:
        conn.execute("DELETE FROM fazenda_logo WHERE id = 1")
        conn.commit()
    finally:
        conn.close()
    registrar_log("Alteração", "fazenda", "Logotipo da fazenda removido")
    return {"message": "Logotipo removido."}
