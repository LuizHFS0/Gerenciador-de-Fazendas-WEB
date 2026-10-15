import sqlite3
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from starlette.background import BackgroundTask
import os
import tempfile
from datetime import datetime

from logs import registrar_log, nome_de

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

STATUS_ANIMAL = ("Ativo", "Tratamento", "Seca", "Prenha", "Abate")
STATUS_MAQUINA = ("Ativo", "Manutenção", "Encostado")
TIPOS_MOVIMENTACAO = ("Entrada", "Saída")


# ---------- Banco ----------
def conectar():
    return sqlite3.connect("banco.db")   # o mesmo caminho do CAMINHO_BANCO em logs.py


def consultar(sql, params=()):
    conn = conectar()
    try:
        conn.row_factory = sqlite3.Row
        return [dict(l) for l in conn.execute(sql, params).fetchall()]
    finally:
        conn.close()


def executar(sql, params=()):
    conn = conectar()
    try:
        cur = conn.execute(sql, params)
        conn.commit()
        return cur.rowcount
    finally:
        conn.close()


def contar(tabela, onde=""):
    # "tabela" e "onde" são sempre textos fixos do código, nunca vêm da requisição
    return consultar(f"SELECT COUNT(*) AS n FROM {tabela} {onde}")[0]["n"]


# ---------- Dashboard ----------
@app.get("/dashboard")
def obter_dados_dashboard():
    return {
        "animais_ativos": contar("animais", "WHERE ativo = 1"),
        "maquinas_operacao": contar("maquinas", "WHERE status = 'Ativo' AND ativo = 1"),
        "funcionarios_ativos": contar("funcionarios", "WHERE ativo = 1"),
        "estoque_baixo": contar("estoque", "WHERE ativo = 1 AND quantidade <= estoque_minimo"),
    }

@app.get("/movimentacoesDashboard")
def obter_movimentacoes_dashboard():
    return consultar(
        """SELECT m.data_movimentacao, m.tipo, m.quantidade, m.responsavel, m.motivo,
                  m.observacoes, i.nome AS item
           FROM movimentacoes_estoque m
           LEFT JOIN estoque i ON i.id = m.item_id
           ORDER BY m.data_movimentacao DESC, m.id DESC LIMIT 5""")


# ---------- Animais ----------
@app.get("/consultarAnimais")
def consultar_animais():
    return {"animais": consultar("""
        SELECT a.id, a.brinco, a.nome, a.tipo, a.sexo, a.raca,
               a.peso_atual, a.data_nascimento, a.status,
               a.origem, a.observacoes,
               l.nome AS lote
        FROM animais a
        LEFT JOIN lote l ON l.id = a.lote_id
        WHERE a.ativo = 1
    """)}


@app.get("/consultarAnimal/{animal_id}")
def consultar_animal(animal_id: int):
    r = consultar("""SELECT a.*, l.nome AS lote FROM animais a
                     LEFT JOIN lote l ON l.id = a.lote_id
                     WHERE a.id = ? AND a.ativo = 1""", (animal_id,))
    if not r:
        raise HTTPException(status_code=404, detail="Animal não encontrado.")
    return r[0]


@app.post("/cadastrarAnimal", status_code=201)
def cadastrar_animal(animal: dict):
    conn = conectar()
    try:
        cursor = conn.cursor()

        # o combobox manda o NOME do lote (A, B, C); o banco guarda o lote_id
        cursor.execute("SELECT id FROM lote WHERE nome = ?", (animal.get("lote"),))
        linha_lote = cursor.fetchone()
        if linha_lote is None:
            raise HTTPException(status_code=400, detail="Lote não encontrado.")

        cursor.execute("""
            INSERT INTO animais (brinco, nome, tipo, sexo, raca, peso_atual,
                                 data_nascimento, status, lote_id, origem,
                                 observacoes, ativo)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 1)""", (
                animal["brinco"],
                animal["nome"],
                animal["tipo"],
                animal["sexo"],
                animal.get("raca", ""),
                animal.get("peso_atual"),
                animal.get("data_nascimento"),
                animal["status"],
                linha_lote[0],
                animal.get("origem", ""),
                animal.get("observacoes", ""),
            ))
        conn.commit()
    except sqlite3.IntegrityError:
        raise HTTPException(status_code=409, detail="Já existe um animal com esse brinco.")
    finally:
        conn.close()

    registrar_log("Cadastro", "animais",
                  f'Animal "{animal["nome"]}" cadastrado (brinco {animal["brinco"]})')
    return {"message": "Animal cadastrado com sucesso!"}


# "Exclui" apenas marcando ativo = 0
@app.delete("/excluirAnimal/{animal_id}")
def excluir_animal(animal_id: int):
    nome = nome_de("animais", animal_id)
    if executar("UPDATE animais SET ativo = 0 WHERE id = ? AND ativo = 1", (animal_id,)) == 0:
        raise HTTPException(status_code=404, detail="Animal não encontrado.")

    registrar_log("Exclusão", "animais", f'Animal "{nome}" excluído')
    return {"message": "Animal excluído com sucesso!"}


@app.put("/alterarLote/{animal_id}")
def alterar_lote(animal_id: int, dados: dict):
    lote = consultar("SELECT id FROM lote WHERE nome = ?", (dados.get("lote"),))
    if not lote:
        raise HTTPException(status_code=400, detail="Lote não encontrado.")
    if executar("UPDATE animais SET lote_id = ? WHERE id = ? AND ativo = 1",
                (lote[0]["id"], animal_id)) == 0:
        raise HTTPException(status_code=404, detail="Animal não encontrado.")

    registrar_log("Alteração", "animais",
                  f'Animal "{nome_de("animais", animal_id)}" movido para o lote {dados["lote"]}')
    return {"message": "Lote alterado!"}


@app.put("/alterarStatus/{animal_id}")
def alterar_status(animal_id: int, dados: dict):
    if dados.get("status") not in STATUS_ANIMAL:
        raise HTTPException(status_code=400, detail="Status inválido.")
    if executar("UPDATE animais SET status = ? WHERE id = ? AND ativo = 1",
                (dados["status"], animal_id)) == 0:
        raise HTTPException(status_code=404, detail="Animal não encontrado.")

    registrar_log("Alteração", "animais",
                  f'Status do animal "{nome_de("animais", animal_id)}" alterado para {dados["status"]}')
    return {"message": "Status alterado!"}


@app.get("/pesagens/{animal_id}")
def listar_pesagens(animal_id: int):
    return {"pesagens": consultar(
        "SELECT data_pesagem, peso, observacoes FROM pesagens "
        "WHERE animal_id = ? ORDER BY data_pesagem DESC, id DESC", (animal_id,))}


@app.post("/pesagens/{animal_id}", status_code=201)
def adicionar_pesagem(animal_id: int, d: dict):
    executar("""INSERT INTO pesagens (animal_id, data_pesagem, peso, observacoes)
                VALUES (?, ?, ?, ?)""",
             (animal_id, d["data_pesagem"], d["peso"], d.get("observacoes", "")))
    # o peso atual do animal passa a ser o da pesagem mais recente
    executar("""UPDATE animais SET peso_atual = (
                    SELECT peso FROM pesagens WHERE animal_id = ?
                    ORDER BY data_pesagem DESC, id DESC LIMIT 1)
                WHERE id = ?""", (animal_id, animal_id))

    registrar_log("Registro", "pesagens",
                  f'Pesagem de {d["peso"]} kg registrada para "{nome_de("animais", animal_id)}"')
    return {"message": "Pesagem registrada!"}


@app.get("/vacinas/{animal_id}")
def listar_vacinas(animal_id: int):
    return {"vacinas": consultar(
        "SELECT vacina, data_aplicacao, proxima_dose, responsavel, observacoes FROM vacinas "
        "WHERE animal_id = ? ORDER BY data_aplicacao DESC, id DESC", (animal_id,))}


@app.post("/vacinas/{animal_id}", status_code=201)
def adicionar_vacina(animal_id: int, d: dict):
    executar("""INSERT INTO vacinas (animal_id, vacina, data_aplicacao, proxima_dose,
                                     responsavel, observacoes)
                VALUES (?, ?, ?, ?, ?, ?)""",
             (animal_id, d["vacina"], d["data_aplicacao"], d.get("proxima_dose"),
              d.get("responsavel", ""), d.get("observacoes", "")))

    registrar_log("Registro", "vacinas",
                  f'Vacina {d["vacina"]} aplicada em "{nome_de("animais", animal_id)}"')
    return {"message": "Vacina cadastrada!"}


@app.get("/consultarLotes")
def consultar_lotes():
    return {"lotes": consultar("SELECT id, nome FROM lote WHERE ativo = 1")}


# ---------- Máquinas ----------
@app.get("/consultarMaquinas")
def consultar_maquinas():
    return {"maquinas": consultar(
        """SELECT id, nome, tipo, status, modelo, fabricante, ano, placa, horas_uso
           FROM maquinas WHERE ativo = 1""")}


@app.get("/consultarMaquina/{maquina_id}")
def consultar_maquina(maquina_id: int):
    r = consultar("SELECT * FROM maquinas WHERE id = ? AND ativo = 1", (maquina_id,))
    if not r:
        raise HTTPException(status_code=404, detail="Máquina não encontrada.")
    return r[0]


@app.post("/cadastrarMaquina", status_code=201)
def cadastrar_maquina(m: dict):
    executar("""INSERT INTO maquinas (nome, tipo, modelo, fabricante, ano, placa,
                                      horas_uso, status, observacoes, ativo)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, 1)""",
             (m["nome"], m.get("tipo", ""), m.get("modelo", ""), m.get("fabricante", ""),
              m.get("ano"), m.get("placa", ""), m.get("horas_uso"),
              m.get("status", "Ativo"), m.get("observacoes", "")))

    registrar_log("Cadastro", "maquinas", f'Máquina "{m["nome"]}" cadastrada')
    return {"message": "Máquina cadastrada!"}


@app.delete("/excluirMaquina/{maquina_id}")
def excluir_maquina(maquina_id: int):
    nome = nome_de("maquinas", maquina_id)
    if executar("UPDATE maquinas SET ativo = 0 WHERE id = ? AND ativo = 1", (maquina_id,)) == 0:
        raise HTTPException(status_code=404, detail="Máquina não encontrada.")

    registrar_log("Exclusão", "maquinas", f'Máquina "{nome}" excluída')
    return {"message": "Máquina excluída!"}


@app.put("/alterarStatusMaquina/{maquina_id}")
def alterar_status_maquina(maquina_id: int, dados: dict):
    if dados.get("status") not in STATUS_MAQUINA:
        raise HTTPException(status_code=400, detail="Status inválido.")
    if executar("UPDATE maquinas SET status = ? WHERE id = ? AND ativo = 1",
                (dados["status"], maquina_id)) == 0:
        raise HTTPException(status_code=404, detail="Máquina não encontrada.")

    registrar_log("Alteração", "maquinas",
                  f'Status da máquina "{nome_de("maquinas", maquina_id)}" alterado para {dados["status"]}')
    return {"message": "Status alterado!"}


@app.get("/manutencoes/{maquina_id}")
def listar_manutencoes(maquina_id: int):
    return {"manutencoes": consultar(
        """SELECT data_manutencao, tipo_manutencao, responsavel, proxima_manutencao, descricao
           FROM manutencoes WHERE maquina_id = ?
           ORDER BY data_manutencao DESC, id DESC""", (maquina_id,))}


@app.post("/manutencoes/{maquina_id}", status_code=201)
def registrar_manutencao(maquina_id: int, d: dict):
    executar("""INSERT INTO manutencoes (maquina_id, tipo_manutencao, data_manutencao,
                                         proxima_manutencao, descricao, responsavel)
                VALUES (?, ?, ?, ?, ?, ?)""",
             (maquina_id, d["tipo_manutencao"], d["data_manutencao"],
              d.get("proxima_manutencao"), d.get("descricao", ""), d.get("responsavel", "")))

    registrar_log("Manutenção", "manutencoes",
                  f'Manutenção {d["tipo_manutencao"].lower()} registrada em "{nome_de("maquinas", maquina_id)}"')
    return {"message": "Manutenção registrada!"}


# ---------- Estoque ----------
@app.get("/consultarEstoque")
def consultar_estoque():
    return {"itens": consultar(
        """SELECT id, nome, categoria, unidade, quantidade, estoque_minimo, localizacao
           FROM estoque WHERE ativo = 1""")}


@app.get("/consultarItem/{item_id}")
def consultar_item(item_id: int):
    r = consultar("SELECT * FROM estoque WHERE id = ? AND ativo = 1", (item_id,))
    if not r:
        raise HTTPException(status_code=404, detail="Item não encontrado.")
    return r[0]


@app.post("/cadastrarItem", status_code=201)
def cadastrar_item(i: dict):
    executar("""INSERT INTO estoque (nome, categoria, unidade, quantidade, estoque_minimo,
                                     localizacao, observacoes, ativo)
                VALUES (?, ?, ?, ?, ?, ?, ?, 1)""",
             (i["nome"], i.get("categoria", ""), i.get("unidade", ""), i.get("quantidade") or 0,
              i.get("estoque_minimo") or 0, i.get("localizacao", ""), i.get("observacoes", "")))

    registrar_log("Cadastro", "estoque", f'Item "{i["nome"]}" cadastrado no estoque')
    return {"message": "Item cadastrado!"}


@app.delete("/excluirItem/{item_id}")
def excluir_item(item_id: int):
    nome = nome_de("estoque", item_id)
    if executar("UPDATE estoque SET ativo = 0 WHERE id = ? AND ativo = 1", (item_id,)) == 0:
        raise HTTPException(status_code=404, detail="Item não encontrado.")

    registrar_log("Exclusão", "estoque", f'Item "{nome}" excluído do estoque')
    return {"message": "Item excluído!"}


@app.get("/movimentacoes/{item_id}")
def listar_movimentacoes(item_id: int):
    return {"movimentacoes": consultar(
        """SELECT m.data_movimentacao, m.tipo, m.quantidade, m.responsavel, m.motivo,
                  m.observacoes, l.nome AS lote
           FROM movimentacoes_estoque m
           LEFT JOIN lote l ON l.id = m.lote_id
           WHERE m.item_id = ?
           ORDER BY m.data_movimentacao DESC, m.id DESC""", (item_id,))}


@app.post("/movimentacoes/{item_id}", status_code=201)
def registrar_movimentacao(item_id: int, d: dict):
    tipo = d.get("tipo")
    if tipo not in TIPOS_MOVIMENTACAO:
        raise HTTPException(status_code=400, detail="Tipo de movimentação inválido.")
    try:
        quantidade = float(d.get("quantidade"))
    except (TypeError, ValueError):
        raise HTTPException(status_code=400, detail="Quantidade inválida.")
    if quantidade <= 0:
        raise HTTPException(status_code=400, detail="A quantidade deve ser maior que zero.")

    conn = conectar()
    try:
        cursor = conn.cursor()
        cursor.execute("SELECT nome, quantidade FROM estoque WHERE id = ? AND ativo = 1", (item_id,))
        item = cursor.fetchone()
        if item is None:
            raise HTTPException(status_code=404, detail="Item não encontrado.")
        nome, atual = item[0], item[1] or 0

        if tipo == "Saída" and quantidade > atual:
            raise HTTPException(status_code=400, detail=f"Estoque insuficiente (disponível: {atual:g}).")

        lote_id = None
        if d.get("lote"):
            cursor.execute("SELECT id FROM lote WHERE nome = ?", (d["lote"],))
            linha = cursor.fetchone()
            if linha is None:
                raise HTTPException(status_code=400, detail="Lote não encontrado.")
            lote_id = linha[0]

        nova = round(atual + quantidade if tipo == "Entrada" else atual - quantidade, 3)

        cursor.execute("""INSERT INTO movimentacoes_estoque
                          (item_id, tipo, quantidade, data_movimentacao, responsavel, motivo,
                           observacoes, lote_id)
                          VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
                       (item_id, tipo, quantidade, d["data_movimentacao"], d.get("responsavel", ""),
                        d.get("motivo", ""), d.get("observacoes", ""), lote_id))
        cursor.execute("UPDATE estoque SET quantidade = ? WHERE id = ?", (nova, item_id))
        conn.commit()
    finally:
        conn.close()

    destino = f' (lote {d["lote"]})' if d.get("lote") else ""
    registrar_log("Movimentação", "estoque", f'{tipo} de {quantidade:g} em "{nome}"{destino}')
    return {"message": "Movimentação registrada!"}


# ---------- Funcionários ----------
@app.get("/consultarFuncionarios")
def consultar_funcionarios():
    return {"funcionarios": consultar(
        """SELECT id, nome, cpf, telefone, cargo, data_admissao
           FROM funcionarios WHERE ativo = 1""")}


@app.get("/consultarFuncionario/{funcionario_id}")
def consultar_funcionario(funcionario_id: int):
    r = consultar("SELECT * FROM funcionarios WHERE id = ? AND ativo = 1", (funcionario_id,))
    if not r:
        raise HTTPException(status_code=404, detail="Funcionário não encontrado.")
    return r[0]


@app.post("/cadastrarFuncionario", status_code=201)
def cadastrar_funcionario(f: dict):
    cpf = "".join(c for c in (f.get("cpf") or "") if c.isdigit())   # só os dígitos
    if cpf and consultar("SELECT id FROM funcionarios WHERE cpf = ? AND ativo = 1", (cpf,)):
        raise HTTPException(status_code=409, detail="Já existe um funcionário com esse CPF.")

    executar("""INSERT INTO funcionarios (nome, cpf, telefone, endereco, cargo,
                                          data_admissao, observacoes, ativo)
                VALUES (?, ?, ?, ?, ?, ?, ?, 1)""",
             (f["nome"], cpf, f.get("telefone", ""), f.get("endereco", ""), f.get("cargo", ""),
              f.get("data_admissao"), f.get("observacoes", "")))

    registrar_log("Cadastro", "funcionarios", f'Funcionário "{f["nome"]}" cadastrado')
    return {"message": "Funcionário cadastrado!"}


@app.get("/movimentacoesFuncionario/{funcionario_id}")
def movimentacoes_funcionario(funcionario_id: int):
    r = consultar("SELECT nome FROM funcionarios WHERE id = ? AND ativo = 1", (funcionario_id,))
    if not r:
        raise HTTPException(status_code=404, detail="Funcionário não encontrado.")
    nome = r[0]["nome"]

    # junta os registros em que o campo "responsável" tem o nome do funcionário
    return {"movimentacoes": consultar(
        """SELECT * FROM (
               SELECT v.data_aplicacao AS data, 'Vacina' AS tipo,
                      v.vacina || ' em ' || COALESCE(a.nome, 'animal removido') AS descricao
               FROM vacinas v LEFT JOIN animais a ON a.id = v.animal_id
               WHERE LOWER(TRIM(v.responsavel)) = LOWER(TRIM(?))
               UNION ALL
               SELECT m.data_manutencao, 'Manutenção ' || LOWER(m.tipo_manutencao),
                      'Máquina ' || COALESCE(q.nome, 'removida')
               FROM manutencoes m LEFT JOIN maquinas q ON q.id = m.maquina_id
               WHERE LOWER(TRIM(m.responsavel)) = LOWER(TRIM(?))
               UNION ALL
               SELECT e.data_movimentacao, 'Estoque (' || e.tipo || ')',
                      printf('%g', e.quantidade) || ' de ' || COALESCE(i.nome, 'item removido')
               FROM movimentacoes_estoque e LEFT JOIN estoque i ON i.id = e.item_id
               WHERE LOWER(TRIM(e.responsavel)) = LOWER(TRIM(?))
           ) ORDER BY data DESC LIMIT 100""", (nome, nome, nome))}


# ---------- Utilitários: alertas ----------
@app.get("/alertas")
def alertas():
    limite = "date('now', 'localtime', '+15 day')"
    return {
        # só vale a aplicação mais recente de cada vacina por animal
        "vacinas": consultar(f"""
            SELECT v.vacina, v.proxima_dose, a.nome AS animal, a.id AS animal_id
            FROM vacinas v JOIN animais a ON a.id = v.animal_id
            WHERE a.ativo = 1 AND v.proxima_dose IS NOT NULL AND v.proxima_dose <= {limite}
              AND NOT EXISTS (SELECT 1 FROM vacinas v2
                              WHERE v2.animal_id = v.animal_id
                                AND LOWER(TRIM(v2.vacina)) = LOWER(TRIM(v.vacina))
                                AND v2.data_aplicacao > v.data_aplicacao)
            ORDER BY v.proxima_dose"""),
        # só vale a manutenção mais recente de cada máquina
        "manutencoes": consultar(f"""
            SELECT q.nome AS maquina, q.id AS maquina_id, m.data_manutencao, m.proxima_manutencao
            FROM manutencoes m JOIN maquinas q ON q.id = m.maquina_id
            WHERE q.ativo = 1 AND m.proxima_manutencao IS NOT NULL AND m.proxima_manutencao <= {limite}
              AND NOT EXISTS (SELECT 1 FROM manutencoes m2
                              WHERE m2.maquina_id = m.maquina_id
                                AND m2.data_manutencao > m.data_manutencao)
            ORDER BY m.proxima_manutencao"""),
        "estoque": consultar("""
            SELECT id, nome, quantidade, estoque_minimo, unidade, localizacao
            FROM estoque WHERE ativo = 1 AND quantidade <= estoque_minimo
            ORDER BY nome"""),
    }


# ---------- Utilitários: gestão de lotes ----------
@app.get("/gerenciarLotes")
def gerenciar_lotes():
    return {"lotes": consultar("""
        SELECT l.id, l.nome, l.tamanho, l.localizacao, l.descricao,
               (SELECT COUNT(*) FROM animais a WHERE a.lote_id = l.id AND a.ativo = 1) AS animais
        FROM lote l WHERE l.ativo = 1 ORDER BY l.nome""")}


@app.post("/cadastrarLote", status_code=201)
def cadastrar_lote(l: dict):
    nome = (l.get("nome") or "").strip()
    if not nome:
        raise HTTPException(status_code=400, detail="Informe o nome do lote.")
    try:
        executar("""INSERT INTO lote (nome, tamanho, localizacao, descricao, ativo)
                    VALUES (?, ?, ?, ?, 1)""",
                 (nome, l.get("tamanho"), l.get("localizacao", ""), l.get("descricao", "")))
    except sqlite3.IntegrityError:
        raise HTTPException(status_code=409, detail="Já existe um lote com esse nome.")

    registrar_log("Cadastro", "lote", f'Lote "{nome}" cadastrado')
    return {"message": "Lote cadastrado!"}


@app.put("/editarLote/{lote_id}")
def editar_lote(lote_id: int, l: dict):
    nome = (l.get("nome") or "").strip()
    if not nome:
        raise HTTPException(status_code=400, detail="Informe o nome do lote.")
    try:
        alterados = executar("""UPDATE lote SET nome = ?, tamanho = ?, localizacao = ?, descricao = ?
                                WHERE id = ? AND ativo = 1""",
                             (nome, l.get("tamanho"), l.get("localizacao", ""),
                              l.get("descricao", ""), lote_id))
    except sqlite3.IntegrityError:
        raise HTTPException(status_code=409, detail="Já existe um lote com esse nome.")
    if alterados == 0:
        raise HTTPException(status_code=404, detail="Lote não encontrado.")

    registrar_log("Alteração", "lote", f'Lote "{nome}" editado')
    return {"message": "Lote atualizado!"}


@app.delete("/excluirLote/{lote_id}")
def excluir_lote(lote_id: int):
    nome = nome_de("lote", lote_id)
    n = consultar("SELECT COUNT(*) AS n FROM animais WHERE lote_id = ? AND ativo = 1", (lote_id,))[0]["n"]
    if n > 0:
        raise HTTPException(status_code=400,
                            detail=f"O lote tem {n} animal(is). Mova-os para outro lote antes de desativar.")
    if executar("UPDATE lote SET ativo = 0 WHERE id = ? AND ativo = 1", (lote_id,)) == 0:
        raise HTTPException(status_code=404, detail="Lote não encontrado.")

    registrar_log("Exclusão", "lote", f'Lote "{nome}" desativado')
    return {"message": "Lote desativado!"}


# ---------- Utilitários: backup ----------
@app.get("/backup")
def backup():
    origem = conectar()
    fd, caminho = tempfile.mkstemp(suffix=".db")
    os.close(fd)
    destino = sqlite3.connect(caminho)
    try:
        origem.backup(destino)      # cópia consistente, mesmo com o banco em uso
    finally:
        destino.close()
        origem.close()

    registrar_log("Backup", "banco", "Backup do banco gerado")
    nome = f"backup-{datetime.now():%Y-%m-%d_%H-%M}.db"
    return FileResponse(caminho, filename=nome, media_type="application/octet-stream",
                        background=BackgroundTask(os.remove, caminho))   # apaga a cópia temporária


# ---------- Fazenda e logs ----------
@app.get("/detalhesFazenda")
def detalhes_fazenda():
    fazenda = consultar("SELECT * FROM fazenda ORDER BY id LIMIT 1")
    return {
        "fazenda": fazenda[0] if fazenda else None,
        "totais": {
            "animais": contar("animais", "WHERE ativo = 1"),
            "funcionarios": contar("funcionarios", "WHERE ativo = 1"),
            "maquinas": contar("maquinas", "WHERE ativo = 1"),
            "produtos": contar("estoque", "WHERE ativo = 1"),
            "lotes": contar("lote", "WHERE ativo = 1"),
        },
    }


@app.get("/ultimosLogs")
def ultimos_logs(limite: int = 5):
    return {"logs": consultar(
        """SELECT l.data_hora, l.acao, l.tabela_afetada, l.descricao, u.nome AS usuario
           FROM logs l LEFT JOIN usuarios u ON u.id = l.usuario_id
           ORDER BY l.data_hora DESC, l.id DESC LIMIT ?""", (limite,))}