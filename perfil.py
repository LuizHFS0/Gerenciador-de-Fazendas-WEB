"""Perfil de quem está logado: dados do menu do usuário e foto opcional.

A foto é privada: as rotas não recebem id, só trabalham com o usuário da sessão.
Fica no banco da própria fazenda (tabela usuarios_fotos).
"""
import time

from fastapi import APIRouter, HTTPException, Request, Response
from starlette.concurrency import run_in_threadpool

import banco_fazenda as bf
import permissoes
import ponte_admin

router = APIRouter(prefix="/api/perfil", tags=["perfil"])

LIMITE_FOTO = 200 * 1024                       # o navegador já envia 256x256, bem abaixo disso
TIPOS_ACEITOS = {"image/jpeg", "image/png", "image/webp"}
ROTULOS = {"dono": "Dono", "gerente": "Gerente", "funcionario": "Funcionário"}


def tipo_pela_assinatura(dados):
    """Descobre o tipo olhando os primeiros bytes (o que o cliente diz não basta)."""
    if dados[:3] == b"\xff\xd8\xff":
        return "image/jpeg"
    if dados[:8] == b"\x89PNG\r\n\x1a\n":
        return "image/png"
    if dados[:4] == b"RIFF" and dados[8:12] == b"WEBP":
        return "image/webp"
    return None


def _versao_da_foto(usuario_id):
    conn = bf.conectar()
    try:
        linha = conn.execute("SELECT atualizada_em FROM usuarios_fotos WHERE usuario_id = ?", (usuario_id,)).fetchone()
    finally:
        conn.close()
    return linha[0] if linha else None


def _gravar(usuario_id, tipo, dados):
    versao = int(time.time())
    conn = bf.conectar()
    try:
        conn.execute("""INSERT INTO usuarios_fotos (usuario_id, tipo, dados, atualizada_em) VALUES (?, ?, ?, ?)
                        ON CONFLICT(usuario_id) DO UPDATE SET tipo = excluded.tipo, dados = excluded.dados,
                                                              atualizada_em = excluded.atualizada_em""",
                     (usuario_id, tipo, dados, versao))
        conn.commit()
    finally:
        conn.close()
    return versao


@router.get("")
def obter_perfil():
    u = bf.usuario_atual()
    versao = _versao_da_foto(u["id"])
    return {
        "nome": u["nome"], "usuario": u["usuario"],
        "perfil_rotulo": ROTULOS.get(u["nivel"], "Usuário"),
        "fazenda": ponte_admin.resumo_fazenda(u["fazenda_id"]),
        "tem_foto": versao is not None, "foto_versao": versao,
        "sessao_expira_em": u["expira_em"],
        "nivel": u["nivel"], "pode_excluir": permissoes.pode_excluir(u["nivel"]),
        "paginas_bloqueadas": permissoes.paginas_bloqueadas(u["nivel"]),
    }


@router.get("/foto")
def obter_foto():
    conn = bf.conectar()
    try:
        linha = conn.execute("SELECT tipo, dados FROM usuarios_fotos WHERE usuario_id = ?",
                             (bf.usuario_atual()["id"],)).fetchone()
    finally:
        conn.close()
    if not linha:
        raise HTTPException(status_code=404, detail="Sem foto cadastrada.")
    return Response(content=bytes(linha[1]), media_type=linha[0],
                    headers={"Cache-Control": "private, max-age=3600",
                             "Content-Security-Policy": "default-src 'none'"})


@router.put("/foto")
async def salvar_foto(request: Request):
    tipo_informado = (request.headers.get("content-type") or "").split(";")[0].strip().lower()
    if tipo_informado not in TIPOS_ACEITOS:
        raise HTTPException(status_code=415, detail="Envie uma imagem JPEG, PNG ou WebP.")
    tamanho = request.headers.get("content-length")
    if tamanho and tamanho.isdigit() and int(tamanho) > LIMITE_FOTO:
        raise HTTPException(status_code=413, detail="A foto é grande demais (máximo de 200 KB).")

    partes, total = [], 0
    async for pedaco in request.stream():               # corta o envio assim que passar do limite
        total += len(pedaco)
        if total > LIMITE_FOTO:
            raise HTTPException(status_code=413, detail="A foto é grande demais (máximo de 200 KB).")
        partes.append(pedaco)
    dados = b"".join(partes)

    tipo = tipo_pela_assinatura(dados)
    if tipo is None or len(dados) < 100:
        raise HTTPException(status_code=400, detail="O arquivo não é uma imagem válida.")
    versao = await run_in_threadpool(_gravar, bf.usuario_atual()["id"], tipo, dados)
    return {"message": "Foto atualizada!", "foto_versao": versao}


@router.delete("/foto")
def remover_foto():
    conn = bf.conectar()
    try:
        conn.execute("DELETE FROM usuarios_fotos WHERE usuario_id = ?", (bf.usuario_atual()["id"],))
        conn.commit()
    finally:
        conn.close()
    return {"message": "Foto removida."}
