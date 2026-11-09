"""Configuração por variáveis de ambiente. Nenhum segredo fica no código.

Variáveis (todas opcionais em desenvolvimento):
  FAZENDAWEB_AMBIENTE        "producao" liga o modo seguro (cookies Secure, HSTS, /docs desligado)
  FAZENDAWEB_DADOS           pasta absoluta dos bancos (em produção, fora do repositório)
  FAZENDAWEB_BACKUPS         pasta absoluta dos backups (fora da pasta de dados)
  FAZENDAWEB_COOKIE_SECURE   "1" força cookie Secure mesmo em HTTP (atrás de proxy HTTPS)
  FAZENDAWEB_ORIGENS         origens HTTPS aceitas em escritas, separadas por vírgula
  FAZENDAWEB_PROXY_CONFIAVEL "1" confia no cabeçalho X-Forwarded-For do proxy para descobrir o IP
  FAZENDAWEB_LIMITE_GERAL    pedidos por minuto por IP (padrão 600)
  FAZENDAWEB_LIMITE_ESCRITA  escritas por minuto por IP (padrão 120)
  FAZENDAWEB_CSP             substitui a política de conteúdo (CSP)
"""
import os
import time
from urllib.parse import urlsplit


def _env(nome, padrao=""):
    return os.environ.get(nome, padrao)


def em_producao():
    return _env("FAZENDAWEB_AMBIENTE", "desenvolvimento").strip().lower() == "producao"


def cookie_seguro(esquema=None):
    return esquema == "https" or _env("FAZENDAWEB_COOKIE_SECURE") == "1" or em_producao()


def hsts_ativo(esquema=None):
    return esquema == "https" or em_producao()


def admin_habilitado():
    """FAZENDAWEB_ADMIN=0 desliga o painel do SuperAdmin neste processo."""
    return _env("FAZENDAWEB_ADMIN", "1") != "0"


def origens_extras():
    return {o.strip() for o in _env("FAZENDAWEB_ORIGENS").split(",") if o.strip()}


def proxy_confiavel():
    return _env("FAZENDAWEB_PROXY_CONFIAVEL") == "1"


def _inteiro(nome, padrao):
    try:
        v = int(_env(nome, str(padrao)))
        return v if v > 0 else padrao
    except ValueError:
        return padrao


def limite_geral():
    return _inteiro("FAZENDAWEB_LIMITE_GERAL", 600)


def limite_escrita():
    return _inteiro("FAZENDAWEB_LIMITE_ESCRITA", 120)


def ip_do_cliente(headers, client):
    """Só olha X-Forwarded-For se o proxy foi declarado como confiável."""
    if proxy_confiavel():
        encaminhado = headers.get("x-forwarded-for", "")
        if encaminhado:
            return encaminhado.split(",")[-1].strip()[:45]
    return (client.host if client else "?")[:45]


CSP_PADRAO = ("default-src 'self'; script-src 'self' 'unsafe-inline'; style-src 'self' 'unsafe-inline'; "
              "img-src 'self' data: blob:; connect-src 'self'; font-src 'self'; object-src 'none'; "
              "base-uri 'self'; form-action 'self'; frame-ancestors 'none'")


def csp():
    return _env("FAZENDAWEB_CSP") or CSP_PADRAO


def problemas_de_producao():
    """Lista [(gravidade, mensagem)] do que precisa ser resolvido antes de abrir ao público."""
    import caminhos
    from pathlib import Path

    problemas = []

    def alerta(msg, grave=True):
        problemas.append(("ALERTA" if grave else "AVISO", msg))

    if not em_producao():
        alerta("FAZENDAWEB_AMBIENTE não está como 'producao'.")
    if not cookie_seguro("http") and _env("FAZENDAWEB_COOKIE_SECURE") != "1":
        alerta("Cookies sem o atributo Secure: defina FAZENDAWEB_AMBIENTE=producao ou FAZENDAWEB_COOKIE_SECURE=1.")

    origens = origens_extras()
    if not origens:
        alerta("FAZENDAWEB_ORIGENS está vazio: informe a origem HTTPS pública (ex.: https://app.exemplo.com).")
    for origem in sorted(origens):
        try:
            partes = urlsplit(origem)
            if (partes.scheme != "https" or not partes.netloc or partes.path or partes.query or partes.fragment
                    or partes.username or partes.password):
                alerta(f"Origem inválida em FAZENDAWEB_ORIGENS: {origem!r}. Use somente https://host[:porta].")
        except ValueError:
            alerta(f"Origem inválida em FAZENDAWEB_ORIGENS: {origem!r}.")

    pasta = caminhos.dados()
    pasta_backups = caminhos.pasta_backups()
    if not os.environ.get("FAZENDAWEB_DADOS"):
        alerta("Defina FAZENDAWEB_DADOS com um caminho absoluto fora do repositório.")
    elif not Path(os.environ["FAZENDAWEB_DADOS"]).is_absolute():
        alerta("FAZENDAWEB_DADOS precisa ser um caminho absoluto.")
    if not os.environ.get("FAZENDAWEB_BACKUPS"):
        alerta("Defina FAZENDAWEB_BACKUPS com um caminho absoluto separado dos dados.")
    elif not Path(os.environ["FAZENDAWEB_BACKUPS"]).is_absolute():
        alerta("FAZENDAWEB_BACKUPS precisa ser um caminho absoluto.")

    if not pasta.exists():
        alerta(f"A pasta de dados não existe: {pasta}.")
    elif os.name == "posix" and (pasta.stat().st_mode & 0o077):
        alerta(f"A pasta de dados {pasta} é legível por outros usuários (use chmod 700).")

    if not pasta_backups.exists():
        alerta(f"A pasta de backups não existe: {pasta_backups}.")
    elif os.name == "posix" and (pasta_backups.stat().st_mode & 0o077):
        alerta(f"A pasta de backups {pasta_backups} é legível por outros usuários (use chmod 700).")

    superadmin = caminhos.arquivo_superadmin()
    if not superadmin.exists():
        alerta("Não existe conta de SuperAdmin (rode: python superadmin_cli.py criar).")
    recentes = list(pasta_backups.glob("*/manifest.json")) if pasta_backups.exists() else []
    if not recentes:
        alerta("Nenhum backup encontrado (rode: python backups.py backup).")
    elif time.time() - max(p.stat().st_mtime for p in recentes) > 26 * 3600:
        alerta("O último backup tem mais de 26 horas.")
    if not proxy_confiavel():
        alerta("FAZENDAWEB_PROXY_CONFIAVEL não está ligado; o controle de abuso pode agrupar acessos pelo IP do túnel.", grave=False)
    return problemas
