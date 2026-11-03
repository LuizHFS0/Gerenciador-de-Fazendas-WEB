"""Confere a configuração antes de abrir o sistema ao público. Saída 1 se houver ALERTA.

  python verificar_producao.py
"""
import sys

import configuracao


def principal():
    problemas = configuracao.problemas_de_producao()
    for gravidade, mensagem in problemas:
        print(f"[{gravidade}] {mensagem}")
    if not problemas:
        print("Configuração de produção: tudo certo.")
    return 1 if any(g == "ALERTA" for g, _ in problemas) else 0


if __name__ == "__main__":
    sys.exit(principal())
