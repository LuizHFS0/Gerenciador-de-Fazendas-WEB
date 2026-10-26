"""Senhas: hash scrypt (biblioteca padrão), compatibilidade com o SHA-256 antigo e senhas temporárias."""
import base64
import hashlib
import hmac
import os
import re
import secrets

N, R, P = 2 ** 14, 8, 1
ALFABETO = "ABCDEFGHJKLMNPQRSTUVWXYZabcdefghijkmnopqrstuvwxyz23456789"   # sem 0/O, 1/l/I
_SHA256_HEX = re.compile(r"^[0-9a-fA-F]{64}$")


def _b64(dados):
    return base64.b64encode(dados).decode("ascii")


def gerar_hash(senha):
    sal = os.urandom(16)
    h = hashlib.scrypt(senha.encode("utf-8"), salt=sal, n=N, r=R, p=P, dklen=32)
    return f"scrypt${N}${R}${P}${_b64(sal)}${_b64(h)}"


def verificar(senha, guardado):
    """Devolve (confere, precisa_atualizar_hash)."""
    guardado = guardado or ""
    if guardado.startswith("scrypt$"):
        try:
            _, n, r, p, sal, esperado = guardado.split("$")
            h = hashlib.scrypt(senha.encode("utf-8"), salt=base64.b64decode(sal),
                               n=int(n), r=int(r), p=int(p), dklen=32)
            return hmac.compare_digest(_b64(h), esperado), False
        except (ValueError, TypeError):
            return False, False
    if _SHA256_HEX.match(guardado):                  # formato do app desktop antigo
        legado = hashlib.sha256(senha.encode("utf-8")).hexdigest()
        confere = hmac.compare_digest(legado, guardado.lower())
        return confere, confere
    return False, False


# hash de mentira: o login gasta o mesmo tempo quando o usuário não existe
HASH_FALSO = gerar_hash("senha-que-ninguem-usa")


def gerar_senha_temporaria(tamanho=12):
    return "".join(secrets.choice(ALFABETO) for _ in range(tamanho))


def validar_nova_senha(senha):
    if not isinstance(senha, str) or len(senha) < 8:
        raise ValueError("A nova senha precisa ter pelo menos 8 caracteres.")
    if len(senha) > 128:
        raise ValueError("A nova senha pode ter no máximo 128 caracteres.")