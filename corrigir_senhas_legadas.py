"""Troca as senhas no formato antigo (SHA-256 sem sal, do app desktop) por uma senha temporária nova.

Quem tem hash antigo e nunca entrou depois da migração continua com uma senha fraca guardada. Este script
invalida essas senhas: gera uma temporária (hash scrypt), exige a troca no próximo login e encerra as sessões.

  python corrigir_senhas_legadas.py            só LISTA quem seria afetado (não altera nada)
  python corrigir_senhas_legadas.py --aplicar  faz backup, troca as senhas e mostra as temporárias (uma única vez)

Respeita FAZENDAWEB_DADOS. Pare a API antes de aplicar. Depois, desative por /usuarios.html contas que ninguém usa mais.
"""
import argparse
import re
import sqlite3
import sys
from datetime import datetime

import caminhos
from backups import copiar_consistente
from senhas import gerar_hash, gerar_senha_temporaria

SHA256_HEX = re.compile(r"^[0-9a-fA-F]{64}$")


def bancos_das_fazendas():
    """Só <id>.db: ignora cópias como 2_backup_*.db que ficam na mesma pasta."""
    return sorted((p for p in caminhos.pasta_fazendas().glob("*.db") if p.stem.isdigit()), key=lambda p: int(p.stem))


def legadas(caminho):
    conn = sqlite3.connect(str(caminho))
    try:
        linhas = conn.execute("SELECT id, usuario, nivel_acesso, ativo, senha FROM usuarios").fetchall()
    except sqlite3.OperationalError:
        return []
    finally:
        conn.close()
    return [(i, u, n, a) for i, u, n, a, s in linhas if SHA256_HEX.match(s or "")]


def corrigir(caminho, afetadas, pasta_backup):
    copiar_consistente(caminho, pasta_backup / "fazendas" / caminho.name)       # cópia antes de mexer
    conn = sqlite3.connect(str(caminho))
    novas = []
    try:
        for uid, usuario, _, _ in afetadas:
            senha = gerar_senha_temporaria()
            conn.execute("UPDATE usuarios SET senha = ?, trocar_senha = 1 WHERE id = ?", (gerar_hash(senha), uid))
            conn.execute("DELETE FROM sessoes WHERE usuario_id = ?", (uid,))
            novas.append((usuario, senha))
        conn.commit()
    finally:
        conn.close()
    return novas


def principal(argv=None):
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--aplicar", action="store_true", help="executa de verdade (sem isso só lista)")
    a = p.parse_args(argv)
    pasta_backup = caminhos.pasta_backups() / f"pre-senhas-legadas-{datetime.now():%Y-%m-%d_%H%M%S}"
    total = 0
    for caminho in bancos_das_fazendas():
        afetadas = legadas(caminho)
        for _, usuario, nivel, ativo in afetadas:
            print(f"fazenda {caminho.stem}: {usuario} (nível '{nivel}', {'ativo' if ativo else 'inativo'}) tem hash antigo")
        total += len(afetadas)
        if afetadas and a.aplicar:
            for usuario, senha in corrigir(caminho, afetadas, pasta_backup):
                print(f"  -> fazenda {caminho.stem} | {usuario} | senha temporária: {senha}")
    if not total:
        print("Nenhuma senha em formato antigo. Nada a fazer.")
    elif a.aplicar:
        print(f"\n{total} conta(s) corrigida(s). Backup em: {pasta_backup}\nAnote as senhas acima: não serão mostradas de novo.")
    else:
        print(f"\n{total} conta(s) afetada(s). Nada foi alterado. Para corrigir: python corrigir_senhas_legadas.py --aplicar")
    return 0


if __name__ == "__main__":
    sys.exit(principal())
