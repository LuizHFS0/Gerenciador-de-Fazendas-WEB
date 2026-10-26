"""Esquema do banco de cada fazenda (um arquivo SQLite por fazenda).

garantir_esquema() pode rodar quantas vezes for preciso: só cria o que falta.
"""

TABELAS = [
    """CREATE TABLE IF NOT EXISTS animais(
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        brinco TEXT UNIQUE,
        nome TEXT,
        tipo TEXT,
        sexo TEXT,
        raca TEXT,
        data_nascimento TEXT,
        peso_atual REAL,
        lote_id INTEGER,
        status TEXT,
        origem TEXT,
        observacoes TEXT,
        ativo INTEGER DEFAULT 1,
        FOREIGN KEY(lote_id) REFERENCES lote(id))""",
    """CREATE TABLE IF NOT EXISTS aplicacoes_agricolas(
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        plantacao_id INTEGER,
        produto TEXT,
        tipo TEXT,
        quantidade REAL,
        data_aplicacao TEXT,
        responsavel TEXT,
        observacoes TEXT,
        FOREIGN KEY(plantacao_id) REFERENCES plantacoes(id))""",
    """CREATE TABLE IF NOT EXISTS estoque(
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        nome TEXT,
        categoria TEXT,
        unidade TEXT,
        quantidade REAL,
        estoque_minimo REAL,
        localizacao TEXT,
        observacoes TEXT,
        ativo INTEGER DEFAULT 1)""",
    """CREATE TABLE IF NOT EXISTS fazenda(
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        nome_fazenda TEXT NOT NULL UNIQUE,
        tamanho REAL,
        endereco TEXT,
        data_fundacao TEXT,
        dono TEXT,
        logo_fazenda TEXT)""",
    """CREATE TABLE IF NOT EXISTS funcionarios(
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        nome TEXT NOT NULL,
        cpf TEXT,
        telefone TEXT,
        endereco TEXT,
        cargo TEXT,
        data_admissao TEXT,
        observacoes TEXT,
        ativo INTEGER DEFAULT 1,
        usuario_id INTEGER)""",
    """CREATE TABLE IF NOT EXISTS usuarios(
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        nome TEXT NOT NULL,
        usuario TEXT UNIQUE NOT NULL,
        senha TEXT NOT NULL,
        cargo TEXT,
        nivel_acesso TEXT,
        ativo INTEGER DEFAULT 1,
        trocar_senha INTEGER NOT NULL DEFAULT 0)""",
    """CREATE TABLE IF NOT EXISTS logs(
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        usuario_id INTEGER,
        acao TEXT,
        tabela_afetada TEXT,
        data_hora TEXT,
        descricao TEXT,
        FOREIGN KEY(usuario_id) REFERENCES usuarios(id))""",
    """CREATE TABLE IF NOT EXISTS lote(
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        nome TEXT NOT NULL UNIQUE,
        tamanho REAL,
        localizacao TEXT,
        descricao TEXT,
        ativo INTEGER DEFAULT 1)""",
    """CREATE TABLE IF NOT EXISTS maquinas(
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        nome TEXT,
        tipo TEXT,
        modelo TEXT,
        fabricante TEXT,
        ano INTEGER,
        placa TEXT,
        horas_uso REAL,
        status TEXT,
        observacoes TEXT,
        ativo INTEGER DEFAULT 1)""",
    """CREATE TABLE IF NOT EXISTS manutencoes(
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        maquina_id INTEGER,
        tipo_manutencao TEXT,
        data_manutencao TEXT,
        proxima_manutencao TEXT,
        descricao TEXT,
        responsavel TEXT,
        FOREIGN KEY(maquina_id) REFERENCES maquinas(id))""",
    """CREATE TABLE IF NOT EXISTS movimentacoes_estoque(
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        item_id INTEGER,
        tipo TEXT,
        quantidade REAL,
        data_movimentacao TEXT,
        responsavel TEXT,
        motivo TEXT,
        observacoes TEXT,
        lote_id INTEGER REFERENCES lote(id),
        FOREIGN KEY(item_id) REFERENCES estoque(id))""",
    """CREATE TABLE IF NOT EXISTS pesagens(
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        animal_id INTEGER,
        data_pesagem TEXT,
        peso REAL,
        observacoes TEXT,
        FOREIGN KEY (animal_id) REFERENCES animais(id))""",
    """CREATE TABLE IF NOT EXISTS plantacoes(
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        cultura TEXT,
        area TEXT,
        hectares REAL,
        data_plantio TEXT,
        previsao_colheita TEXT,
        status TEXT,
        observacoes TEXT)""",
    """CREATE TABLE IF NOT EXISTS producao_leite(
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        animal_id INTEGER,
        data_producao TEXT,
        litros REAL,
        turno TEXT,
        observacoes TEXT,
        responsavel TEXT,
        FOREIGN KEY(animal_id) REFERENCES animais(id))""",
    """CREATE TABLE IF NOT EXISTS produtor_rural(
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        pessoa TEXT NOT NULL,
        nome TEXT NOT NULL,
        registro_mapa TEXT NOT NULL,
        data_nasc TEXT,
        rg TEXT UNIQUE,
        cpf_cnpj TEXT UNIQUE NOT NULL,
        endereco TEXT,
        telefone TEXT,
        celular TEXT,
        email TEXT)""",
    """CREATE TABLE IF NOT EXISTS reproducao(
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        animal_id INTEGER,
        tipo TEXT,
        data_evento TEXT,
        resultado TEXT,
        observacoes TEXT,
        FOREIGN KEY(animal_id) REFERENCES animais(id))""",
    """CREATE TABLE IF NOT EXISTS vacinas(
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        animal_id INTEGER,
        vacina TEXT,
        data_aplicacao TEXT,
        proxima_dose TEXT,
        responsavel TEXT,
        observacoes TEXT,
        FOREIGN KEY (animal_id) REFERENCES animais(id))""",
    # sessões de login desta fazenda (só o hash do token fica guardado)
    """CREATE TABLE IF NOT EXISTS sessoes(
        token_hash TEXT PRIMARY KEY,
        usuario_id INTEGER NOT NULL,
        criada_em INTEGER NOT NULL,
        expira_em INTEGER NOT NULL,
        FOREIGN KEY(usuario_id) REFERENCES usuarios(id))""",
    # foto opcional de cada usuário (JPEG, PNG ou WebP, até 200 KB), privada: só o próprio usuário a vê
    """CREATE TABLE IF NOT EXISTS usuarios_fotos(
        usuario_id INTEGER PRIMARY KEY,
        tipo TEXT NOT NULL,
        dados BLOB NOT NULL,
        atualizada_em INTEGER NOT NULL,
        FOREIGN KEY(usuario_id) REFERENCES usuarios(id))""",
    "CREATE INDEX IF NOT EXISTS idx_sessoes_usuario ON sessoes(usuario_id)",
    "CREATE INDEX IF NOT EXISTS idx_leite_chave ON producao_leite(animal_id, data_producao, turno)",
]

# colunas que bancos mais antigos podem não ter: (tabela, coluna, definição)
COLUNAS_NOVAS = [
    ("usuarios", "trocar_senha", "INTEGER NOT NULL DEFAULT 0"),
    ("funcionarios", "usuario_id", "INTEGER"),
    ("producao_leite", "responsavel", "TEXT"),
    ("estoque", "ativo", "INTEGER DEFAULT 1"),
    ("maquinas", "ativo", "INTEGER DEFAULT 1"),
    ("movimentacoes_estoque", "lote_id", "INTEGER REFERENCES lote(id)"),
]


def garantir_esquema(conn):
    for ddl in TABELAS:
        conn.execute(ddl)
    for tabela, coluna, definicao in COLUNAS_NOVAS:
        existentes = {linha[1] for linha in conn.execute(f"PRAGMA table_info({tabela})")}
        if coluna not in existentes:
            conn.execute(f"ALTER TABLE {tabela} ADD COLUMN {coluna} {definicao}")
    conn.commit()
