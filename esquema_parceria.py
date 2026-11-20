"""Esquema do lote em parceria (idempotente: pode rodar toda vez que o banco da fazenda abre).

Chame aplicar(conn) dentro de esquema_fazenda.garantir_esquema, junto das outras migrações.
Cada fazenda tem o próprio banco, por isso a tabela parceiros não precisa de fazenda_id.
"""


def _colunas(conn, tabela):
    return {linha[1] for linha in conn.execute(f"PRAGMA table_info({tabela})")}


def aplicar(conn):
    conn.execute("""CREATE TABLE IF NOT EXISTS parceiros (
                        id    INTEGER PRIMARY KEY AUTOINCREMENT,
                        nome  TEXT NOT NULL UNIQUE COLLATE NOCASE,
                        ativo INTEGER NOT NULL DEFAULT 1)""")

    novas = {
        "lote": [
            ("tipo", "TEXT NOT NULL DEFAULT 'normal'"),
            ("parceiro_id", "INTEGER"),
            ("data_prevista_saida", "TEXT"),
            ("observacoes", "TEXT"),
        ],
        "animais": [
            ("parceria", "INTEGER NOT NULL DEFAULT 0"),
        ],
    }
    for tabela, colunas in novas.items():
        existentes = _colunas(conn, tabela)
        for nome, definicao in colunas:
            if nome not in existentes:
                conn.execute(f"ALTER TABLE {tabela} ADD COLUMN {nome} {definicao}")
    conn.commit()
