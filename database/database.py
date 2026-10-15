import sqlite3

def conectar():
    """Estabelece uma conexão com o banco de dados SQLite."""
    try:
        conexao = sqlite3.connect('banco.db')
        return conexao
    except sqlite3.Error as e:
        print(f"Erro ao conectar ao banco de dados: {e}")
        return None

def criar_tabela():
    conn = conectar()
    cursor = conn.cursor()

    cursor.execute('''
        CREATE TABLE IF NOT EXISTS animais (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            nome TEXT NOT NULL,
            especie TEXT NOT NULL,
            idade INTEGER NOT NULL,
            status INTEGER NOT NULL
        )
    ''')

    cursor.execute('''
        CREATE TABLE IF NOT EXISTS maquinas (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            nome TEXT NOT NULL,
            tipo TEXT NOT NULL,
            status INTEGER NOT NULL
        )
    ''')

    cursor.execute('''ALTER TABLE estoque ADD COLUMN ativo INTEGER DEFAULT 1;''')
    cursor.execute('''ALTER TABLE movimentacoes_estoque ADD COLUMN lote_id INTEGER REFERENCES lote(id);''')
    conn.commit()

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS funcionarios (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            nome TEXT NOT NULL,
            cargo TEXT NOT NULL,
            status INTEGER NOT NULL
        )
    """)

    conn.close()


criar_tabela()
