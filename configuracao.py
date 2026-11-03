"""Configuração por variáveis de ambiente. Nenhum segredo fica no código.

O sistema NÃO tem chave de assinatura para guardar: as sessões são tokens aleatórios cujo hash fica no banco.
Variáveis (todas opcionais em desenvolvimento):
  FAZENDAWEB_AMBIENTE        "producao" liga o modo seguro (cookies Secure, HSTS, /docs desligado)
  FAZENDAWEB_DADOS           pasta dos bancos (padrão: ./dados)
  FAZENDAWEB_BACKUPS         pasta dos backups (padrão: ../backups em relação à pasta de dados)
  FAZENDAWEB_COOKIE_SECURE   "1" força cookie Secure mesmo em HTTP (atrás de proxy HTTPS)
  FAZENDAWEB_ORIGENS         origens extras aceitas em escritas, separadas por vírgula (https://meu-dominio)
  FAZENDAWEB_PROXY_CONFIAVEL "1" confia no cabeçalho X-Forwarded-For do proxy para descobrir o IP
  FAZENDAWEB_LIMITE_GERAL    pedidos por minuto por IP (padrão 600)
  FAZENDAWEB_LIMITE_ESCRITA  escritas por minuto por IP (padrão 120)
  FAZENDAWEB_CSP             substitui a política de conteúdo (CSP)
"""
import os
import time


def _env(nome, padrao=""):
    return os.environ.get(nome, padrao)


def em_producao():
    return _env("FAZENDAWEB_AMBIENTE", "desenvolvimento").strip().lower() == "producao"


def cookie_seguro(esquema=None):
    return esquema == "https" or _env("FAZENDAWEB_COOKIE_SECURE") == "1" or em_producao()


def hsts_ativo(esquema=None):
    return esquema == "https" or em_producao()


def admin_habilitado():
    """FAZENDAWEB_ADMIN=0 desliga o painel do SuperAdmin neste processo (ex.: para rodá-lo em outro servidor)."""
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
    """IP de quem chamou. Só olha X-Forwarded-For se você declarou o proxy como confiável."""
    if proxy_confiavel():
        encaminhado = headers.get("x-forwarded-for", "")
        if encaminhado:
            return encaminhado.split(",")[-1].strip()[:45]       # o último salto é o que o seu proxy anexou
    return (client.host if client else "?")[:45]


CSP_PADRAO = ("default-src 'self'; script-src 'self' 'unsafe-inline'; style-src 'self' 'unsafe-inline'; "
              "img-src 'self' data: blob:; connect-src 'self'; font-src 'self'; object-src 'none'; "
              "base-uri 'self'; form-action 'self'; frame-ancestors 'none'")


def csp():
    return _env("FAZENDAWEB_CSP") or CSP_PADRAO


def problemas_de_producao():
    """Lista [(gravidade, mensagem)] do que precisa ser resolvido antes de abrir ao público."""
    import caminhos
    problemas = []

    def alerta(msg, grave=True):
        problemas.append(("ALERTA" if grave else "AVISO", msg))

    if not em_producao():
        alerta("FAZENDAWEB_AMBIENTE não está como 'producao' (docs abertos, cookie sem Secure).")
    if not cookie_seguro("http") and _env("FAZENDAWEB_COOKIE_SECURE") != "1":
        alerta("Cookies sem o atributo Secure: defina FAZENDAWEB_AMBIENTE=producao ou FAZENDAWEB_COOKIE_SECURE=1.")
    if not origens_extras():
        alerta("FAZENDAWEB_ORIGENS está vazio: informe o endereço HTTPS público (ex.: https://app.exemplo.com).")
    pasta = caminhos.dados()
    if pasta.exists() and os.name == "posix" and (pasta.stat().st_mode & 0o077):
        alerta(f"A pasta de dados {pasta} é legível por outros usuários do servidor (use chmod 700).")
    superadmin = caminhos.arquivo_superadmin()
    if not superadmin.exists():
        alerta("Não existe conta de SuperAdmin (rode: python superadmin_cli.py criar).")
    backups = caminhos.pasta_backups()
    recentes = [p for p in backups.glob("*/manifest.json")] if backups.exists() else []
    if not recentes:
        alerta("Nenhum backup encontrado (rode: python backups.py backup).")
    elif time.time() - max(p.stat().st_mtime for p in recentes) > 26 * 3600:
        alerta("O último backup tem mais de 26 horas.")
    if not proxy_confiavel():
        alerta("FAZENDAWEB_PROXY_CONFIAVEL não está ligado: atrás de um proxy, todos os acessos parecem vir do mesmo IP.", grave=False)
    return problemas
