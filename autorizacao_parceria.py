"""Quem pode cadastrar lote em parceria e registrar a saída dele.

- Dono e Gerente: liberados.
- Funcionário (ou qualquer outro perfil): só com a senha de confirmação de um Gerente ou do Dono da MESMA fazenda,
  conferida no servidor. A senha não é guardada nem registrada; o log mostra só o login de quem autorizou.
- Limite de tentativas por usuário (5 erros em 15 minutos), no mesmo estilo do login. Fica em memória, por processo.
"""
import time

from fastapi import HTTPException

import banco_fazenda as bf
import senhas
from logs import registrar_log

PERFIS_LIBERADOS = ("dono", "gerente")
JANELA_FALHAS = 15 * 60
MAX_FALHAS = 5
_falhas = {}


def _recentes(chave):
    agora = time.time()
    lista = [t for t in _falhas.get(chave, []) if agora - t < JANELA_FALHAS]
    if lista:
        _falhas[chave] = lista
    else:
        _falhas.pop(chave, None)
    return lista


def limpar_limitador():
    _falhas.clear()


def checar_permissao_parceria(autorizacao):
    """Retorna None (perfil liberado) ou o login de quem autorizou. Levanta 401/403/429 quando não liberado."""
    usuario = bf.usuario_atual()
    if not usuario:
        raise HTTPException(status_code=401, detail="Faça login para continuar.")
    if usuario["nivel"] in PERFIS_LIBERADOS:
        return None

    senha = autorizacao.get("senha") if isinstance(autorizacao, dict) else None
    if not senha:
        raise HTTPException(status_code=403, detail="Informe a senha de confirmação do gerente.")

    chave = (usuario["fazenda_id"], usuario["id"])
    if len(_recentes(chave)) >= MAX_FALHAS:
        raise HTTPException(status_code=429, detail="Muitas tentativas. Aguarde alguns minutos e tente de novo.")

    conn = bf.conectar()
    try:
        candidatos = conn.execute(
            """SELECT usuario, senha FROM usuarios
               WHERE ativo = 1 AND LOWER(TRIM(nivel_acesso)) IN ('gerente', 'dono')""").fetchall()
    finally:
        conn.close()

    autorizador = None
    for login, guardada in candidatos:                 # confere todos, sem parar no primeiro
        try:
            confere = senhas.verificar(str(senha), guardada)[0]
        except Exception:
            confere = False
        if confere and autorizador is None:
            autorizador = login

    if autorizador is None:
        _falhas.setdefault(chave, []).append(time.time())
        registrar_log("Acesso negado", "usuarios",
                      f'Senha de gerente incorreta ao confirmar uma ação do lote em parceria (usuário "{usuario["usuario"]}")')
        raise HTTPException(status_code=403, detail="Senha do gerente incorreta.")

    _falhas.pop(chave, None)
    return autorizador
