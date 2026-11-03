"""Auditoria de segurança do lado das fazendas: quem entrou, quem falhou, o que foi negado.

Dois destinos: a tabela `auditoria` do banco da própria fazenda e o arquivo dados/seguranca.log (JSON, uma linha por
evento, com rotação). Nunca recebe senha, token ou cookie: só evento, usuário (texto), IP e um detalhe curto.
"""
import json
import logging
import logging.handlers
import re
from datetime import datetime

import banco_fazenda as bf
import caminhos

_logger = logging.getLogger("fazendaweb.seguranca")
_logger.setLevel(logging.INFO)
_logger.propagate = False
_destino_atual = None


def _preparar_logger():
    global _destino_atual
    destino = caminhos.arquivo_log_seguranca()
    if _destino_atual == destino:
        return
    for h in list(_logger.handlers):
        _logger.removeHandler(h)
        h.close()
    destino.parent.mkdir(parents=True, exist_ok=True)
    h = logging.handlers.RotatingFileHandler(destino, maxBytes=5_000_000, backupCount=5, encoding="utf-8")
    h.setFormatter(logging.Formatter("%(message)s"))
    _logger.addHandler(h)
    _destino_atual = destino


def limpar(texto, limite=200):
    """Sem quebra de linha nem caracteres de controle (ninguém forja linha de log) e com tamanho máximo."""
    return re.sub(r"[\x00-\x1f\x7f]", " ", str(texto or ""))[:limite]


def registrar(evento, detalhe="", usuario_id=None, usuario_texto="", ip="", fazenda_id=None):
    quando = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    registro = {"t": quando, "evento": limpar(evento, 40), "fazenda": fazenda_id, "usuario_id": usuario_id,
                "usuario": limpar(usuario_texto, 60), "ip": limpar(ip, 45), "detalhe": limpar(detalhe)}
    try:
        _preparar_logger()
        _logger.info(json.dumps(registro, ensure_ascii=False))
    except Exception:
        pass                                              # auditar nunca derruba a operação
    if fazenda_id is not None and bf.caminho_banco(fazenda_id).exists():
        try:
            conn = bf.abrir(fazenda_id)
            try:
                conn.execute("""INSERT INTO auditoria (quando, evento, usuario_id, usuario_texto, ip, detalhe)
                                VALUES (?, ?, ?, ?, ?, ?)""",
                             (quando, registro["evento"], usuario_id, registro["usuario"], registro["ip"], registro["detalhe"]))
                conn.commit()
            finally:
                conn.close()
        except Exception:
            pass
