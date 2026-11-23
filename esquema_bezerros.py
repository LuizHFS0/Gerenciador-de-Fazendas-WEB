"""Esquema do módulo de bezerros (idempotente: pode rodar toda vez que o banco da fazenda abre).

Chame aplicar(conn) dentro de esquema_fazenda.garantir_esquema, depois de esquema_parceria.aplicar.
Cada fazenda tem o próprio banco, por isso as tabelas não precisam de fazenda_id.

Tabelas novas
  ciclos_reprodutivos   um ciclo por tentativa de cobertura da vaca (da monta ao desfecho)
  eventos_reprodutivos  a linha do tempo do ciclo (diagnóstico, secagem, acompanhamentos...)
  partos                o parto que encerra o ciclo
  partos_bezerros       cada cria do parto (viva, natimorta...) e, se viva, o animal criado
  protocolo_bezerro     as tarefas de manejo do bezerro (editáveis em Configurações > Avisos)
  tarefas_bezerro       as tarefas geradas para cada bezerro nascido
  config_avisos         ajustes dos avisos (antecedência, dias de gestação...)
Colunas novas em animais: mae_id, pai_id (genealogia) e pai_texto (touro/sêmen sem cadastro).
"""

# valores iniciais de config_avisos (a tela de Configurações altera; "restaurar padrão" volta a eles)
CONFIG_PADRAO = {
    "aviso_dias_amarelo": 7,      # faixa amarela: faltam até N dias
    "aviso_dias_laranja": 1,      # faixa laranja: falta até N dia (0 = só no dia); vencido é sempre vermelho
    "aviso_dias_parto": 30,       # o aviso do parto previsto começa N dias antes (amarelo)
    "gestacao_dias": 283,         # duração média da gestação, para calcular o parto previsto
    "diagnostico_dias": 30,       # lembrete do diagnóstico de gestação: N dias depois da cobertura
    "secagem_dias_antes": 60,     # lembrete da secagem (vacas de leite): N dias antes do parto previsto
}

# (nome, tipo, dias após o nascimento, repetir a cada N dias, repetir até o dia N, só para sexo, ativo, orientação)
# tipo: geral | vacina (ao concluir, também entra em vacinas) | pesagem (ao concluir, pode registrar o peso)
PROTOCOLO_PADRAO = [
    ("Colostro", "geral", 0, None, None, "todos", 1, "Nas primeiras 6 horas de vida (no máximo em 24 horas)."),
    ("Pesagem ao nascer", "pesagem", 0, None, None, "todos", 1, "Pesar nas primeiras 24 horas."),
    ("Cura do umbigo", "geral", 1, 1, 5, "todos", 1, "Uma vez por dia nos primeiros dias."),
    ("Brincagem / identificação", "geral", 7, None, None, "todos", 1, "Colocar o brinco e conferir o cadastro."),
    ("Vermifugação", "geral", 30, 60, 210, "todos", 1, "A primeira aos 30 dias, depois a cada 60 dias até a desmama."),
    ("Pesagem de acompanhamento", "pesagem", 30, 60, 210, "todos", 1, "Acompanha o ganho de peso até a desmama."),
    ("Vacina de clostridioses (1ª dose)", "vacina", 90, None, None, "todos", 1, "Confirme o calendário com o veterinário."),
    ("Vacina de clostridioses (reforço)", "vacina", 120, None, None, "todos", 1, "Reforço cerca de 30 dias depois da 1ª dose."),
    ("Vacina de brucelose", "vacina", 120, None, None, "Fêmea", 1, "Só fêmeas, entre 3 e 8 meses de idade."),
    ("Vacina contra raiva (1ª dose)", "vacina", 90, None, None, "todos", 0, "Ative se a sua região exigir."),
    ("Vacina contra raiva (reforço)", "vacina", 120, None, None, "todos", 0, "Ative se a sua região exigir."),
    ("Castração", "geral", 120, None, None, "Macho", 0, "Opcional, só machos."),
    ("Desmama", "geral", 210, None, None, "todos", 1, "Separar o bezerro da mãe."),
]


def _colunas(conn, tabela):
    return {linha[1] for linha in conn.execute(f"PRAGMA table_info({tabela})")}


def semear_protocolo(conn):
    """Grava o protocolo padrão (só usado quando a tabela está vazia ou em 'restaurar padrão')."""
    conn.executemany(
        """INSERT INTO protocolo_bezerro (nome, tipo, dias_apos_nascimento, repetir_a_cada_dias, repetir_ate_dias,
                                          so_sexo, ativo, orientacao)
           VALUES (?, ?, ?, ?, ?, ?, ?, ?)""", PROTOCOLO_PADRAO)


def aplicar(conn):
    conn.execute("""CREATE TABLE IF NOT EXISTS ciclos_reprodutivos (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        vaca_id INTEGER NOT NULL,
                        tipo_cobertura TEXT NOT NULL,
                        touro_id INTEGER,
                        touro_texto TEXT,
                        data_cobertura TEXT NOT NULL,
                        data_prevista_parto TEXT NOT NULL,
                        status TEXT NOT NULL DEFAULT 'coberta',
                        data_encerramento TEXT,
                        observacoes TEXT,
                        FOREIGN KEY(vaca_id) REFERENCES animais(id),
                        FOREIGN KEY(touro_id) REFERENCES animais(id))""")
    conn.execute("CREATE INDEX IF NOT EXISTS idx_ciclos_vaca ON ciclos_reprodutivos(vaca_id, status)")

    conn.execute("""CREATE TABLE IF NOT EXISTS eventos_reprodutivos (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        ciclo_id INTEGER NOT NULL,
                        tipo TEXT NOT NULL,
                        data TEXT NOT NULL,
                        resultado TEXT,
                        titulo TEXT,
                        observacoes TEXT,
                        responsavel TEXT,
                        FOREIGN KEY(ciclo_id) REFERENCES ciclos_reprodutivos(id))""")
    conn.execute("CREATE INDEX IF NOT EXISTS idx_eventos_ciclo ON eventos_reprodutivos(ciclo_id, data)")

    conn.execute("""CREATE TABLE IF NOT EXISTS partos (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        ciclo_id INTEGER NOT NULL UNIQUE,
                        data_parto TEXT NOT NULL,
                        tipo_parto TEXT NOT NULL DEFAULT 'unico',
                        tipo_assistencia TEXT,
                        observacoes TEXT,
                        FOREIGN KEY(ciclo_id) REFERENCES ciclos_reprodutivos(id))""")

    conn.execute("""CREATE TABLE IF NOT EXISTS partos_bezerros (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        parto_id INTEGER NOT NULL,
                        ordem INTEGER NOT NULL,
                        sexo TEXT NOT NULL,
                        peso_nascimento REAL,
                        situacao TEXT NOT NULL DEFAULT 'vivo',
                        causa TEXT,
                        observacoes TEXT,
                        animal_id INTEGER,
                        FOREIGN KEY(parto_id) REFERENCES partos(id),
                        FOREIGN KEY(animal_id) REFERENCES animais(id))""")

    conn.execute("""CREATE TABLE IF NOT EXISTS protocolo_bezerro (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        nome TEXT NOT NULL,
                        tipo TEXT NOT NULL DEFAULT 'geral',
                        dias_apos_nascimento INTEGER NOT NULL,
                        repetir_a_cada_dias INTEGER,
                        repetir_ate_dias INTEGER,
                        so_sexo TEXT NOT NULL DEFAULT 'todos',
                        ativo INTEGER NOT NULL DEFAULT 1,
                        orientacao TEXT)""")

    conn.execute("""CREATE TABLE IF NOT EXISTS tarefas_bezerro (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        animal_id INTEGER NOT NULL,
                        protocolo_id INTEGER,
                        nome TEXT NOT NULL,
                        tipo TEXT NOT NULL DEFAULT 'geral',
                        data_prevista TEXT NOT NULL,
                        data_realizada TEXT,
                        responsavel TEXT,
                        observacoes TEXT,
                        status TEXT NOT NULL DEFAULT 'pendente',
                        FOREIGN KEY(animal_id) REFERENCES animais(id),
                        FOREIGN KEY(protocolo_id) REFERENCES protocolo_bezerro(id))""")
    conn.execute("CREATE INDEX IF NOT EXISTS idx_tarefas_animal ON tarefas_bezerro(animal_id, status)")
    conn.execute("CREATE INDEX IF NOT EXISTS idx_tarefas_data ON tarefas_bezerro(status, data_prevista)")

    conn.execute("""CREATE TABLE IF NOT EXISTS config_avisos (
                        chave TEXT PRIMARY KEY,
                        valor TEXT NOT NULL)""")

    existentes = _colunas(conn, "animais")
    for nome, definicao in (("mae_id", "INTEGER"), ("pai_id", "INTEGER"), ("pai_texto", "TEXT")):
        if nome not in existentes:
            conn.execute(f"ALTER TABLE animais ADD COLUMN {nome} {definicao}")

    if conn.execute("SELECT COUNT(*) FROM protocolo_bezerro").fetchone()[0] == 0:
        semear_protocolo(conn)
    conn.commit()
