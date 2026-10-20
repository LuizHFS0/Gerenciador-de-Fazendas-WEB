import sqlite3
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from starlette.background import BackgroundTask
import os
import tempfile
from datetime import datetime

import math
import unicodedata
from datetime import date, timedelta
from xml.sax.saxutils import escape as _escapar

from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from pathlib import Path

from logs import registrar_log, nome_de

app = FastAPI()

FRONTEND_DIR = Path(__file__).parent / "front-end"


@app.get("/")
def pagina_inicial():
    return FileResponse(FRONTEND_DIR / "dashboard.html")

app.mount(
    "/front-end",
    StaticFiles(directory=FRONTEND_DIR),
    name="front-end"
)


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

TURNO_MANHA = "Manhã"
TURNO_TARDE = "Tarde"

# vaca em produção: fêmea do tipo Leite e ativa (as secas são tiradas só no lançamento)
# LIKE ignora maiúscula; "F%" aceita Fêmea, Femea ou F
_VACAS_LEITE = "a.ativo = 1 AND a.sexo LIKE 'F%' AND a.tipo LIKE 'Leite'"


def _garantir_coluna_responsavel_leite():
    # o formulário de medição grava quem lançou; cria a coluna se ela ainda não existir
    colunas = [c["name"] for c in consultar("PRAGMA table_info(producao_leite)")]
    if colunas and "responsavel" not in colunas:
        executar("ALTER TABLE producao_leite ADD COLUMN responsavel TEXT")


_garantir_coluna_responsavel_leite()


# ---------- Auxiliares do leite ----------
def _chave_alfabetica(texto):
    # ordem alfabética que ignora acento e maiúscula (Ângela vem antes de Bela)
    sem_acento = unicodedata.normalize("NFD", texto or "")
    return "".join(c for c in sem_acento if unicodedata.category(c) != "Mn").lower()


def _data_valida(texto):
    try:
        return datetime.strptime(texto or "", "%Y-%m-%d").date()
    except ValueError:
        raise HTTPException(status_code=400, detail="Data inválida.")


def _validar_dias(dias):
    if not 1 <= dias <= 365:
        raise HTTPException(status_code=400, detail="Período inválido.")


def _br(d):
    return d.strftime("%d/%m/%Y")


def _litros_br(valor):
    return f"{valor:,.1f}".replace(",", "X").replace(".", ",").replace("X", ".")


def _lote_por_nome(nome):
    r = consultar("SELECT id FROM lote WHERE nome = ? AND ativo = 1", (nome,))
    if not r:
        raise HTTPException(status_code=400, detail="Lote não encontrado.")
    return r[0]["id"]


def _vacas_aptas(lote_id):
    return consultar(f"""SELECT a.id, a.nome, a.brinco FROM animais a
                         WHERE a.lote_id = ? AND {_VACAS_LEITE}
                           AND COALESCE(a.status, '') <> 'Seca'""", (lote_id,))


def _resumo_leite(dias, lote=""):
    params = [f"-{dias - 1} day"]
    filtro = ""
    if lote:
        filtro = "AND l.nome = ?"
        params.append(lote)
    return consultar(f"""
        SELECT COALESCE(SUM(p.litros), 0) AS litros,
               COUNT(DISTINCT p.data_producao) AS dias_medidos,
               COUNT(DISTINCT p.animal_id) AS vacas
        FROM producao_leite p
        JOIN animais a ON a.id = p.animal_id
        LEFT JOIN lote l ON l.id = a.lote_id
        WHERE a.ativo = 1
          AND p.data_producao BETWEEN date('now', 'localtime', ?) AND date('now', 'localtime')
          {filtro}""", params)[0]


def _producao_por_vaca(lote, dias, ordem):
    _validar_dias(dias)
    params = [f"-{dias - 1} day"]
    filtro = ""
    if lote:
        filtro = "AND l.nome = ?"
        params.append(lote)

    vacas = consultar(f"""
        SELECT a.id, a.nome, a.brinco, a.status, l.nome AS lote,
               COALESCE(SUM(CASE WHEN p.turno = '{TURNO_MANHA}' THEN p.litros END), 0) AS manha,
               COALESCE(SUM(CASE WHEN p.turno = '{TURNO_TARDE}' THEN p.litros END), 0) AS tarde,
               COALESCE(SUM(p.litros), 0) AS total
        FROM animais a
        LEFT JOIN lote l ON l.id = a.lote_id
        LEFT JOIN producao_leite p
               ON p.animal_id = a.id
              AND p.data_producao BETWEEN date('now', 'localtime', ?) AND date('now', 'localtime')
        WHERE {_VACAS_LEITE} {filtro}
        GROUP BY a.id""", params)

    for v in vacas:
        for campo in ("manha", "tarde", "total"):
            v[campo] = round(v[campo], 2)

    if ordem == "maior":
        vacas.sort(key=lambda v: (-v["total"], _chave_alfabetica(v["nome"])))
    else:
        vacas.sort(key=lambda v: _chave_alfabetica(v["nome"]))
    return vacas


# ---------- Leite: painel ----------
@app.get("/dashboardLeite")
def dashboard_leite(dias: int = 30):
    _validar_dias(dias)
    hoje = consultar("""SELECT COALESCE(SUM(p.litros), 0) AS litros
                        FROM producao_leite p JOIN animais a ON a.id = p.animal_id
                        WHERE a.ativo = 1 AND p.data_producao = date('now', 'localtime')""")[0]["litros"]
    resumo = _resumo_leite(dias)
    vacas = _producao_por_vaca("", dias, "maior")
    media = resumo["litros"] / resumo["dias_medidos"] if resumo["dias_medidos"] else 0

    return {
        "dias": dias,
        "litros_hoje": round(hoje, 2),
        "litros_periodo": round(resumo["litros"], 2),
        "media_diaria": round(media, 2),
        "vacas_produzindo": resumo["vacas"],
        "top5": [v for v in vacas if v["total"] > 0][:5],
    }


# ---------- Leite: lançamento ----------
@app.get("/vacasDoLote/{lote}")
def vacas_do_lote(lote: str, data: str):
    _data_valida(data)
    lote_id = _lote_por_nome(lote)
    vacas = _vacas_aptas(lote_id)

    # o que já foi lançado nessa data aparece preenchido
    lancados = {(r["animal_id"], r["turno"]): r["litros"] for r in consultar(
        "SELECT animal_id, turno, litros FROM producao_leite WHERE data_producao = ?", (data,))}
    for v in vacas:
        v["manha"] = lancados.get((v["id"], TURNO_MANHA))
        v["tarde"] = lancados.get((v["id"], TURNO_TARDE))

    vacas.sort(key=lambda v: _chave_alfabetica(v["nome"]))

    # fêmeas do lote que ficaram de fora, para a tela explicar o motivo
    ids_aptas = {v["id"] for v in vacas}
    animais = consultar("SELECT id, nome, sexo, tipo FROM animais WHERE lote_id = ? AND ativo = 1",
                        (lote_id,))
    ignoradas = []
    for a in animais:
        if a["id"] in ids_aptas or not (a["sexo"] or "").upper().startswith("F"):
            continue
        if (a["tipo"] or "").lower() != "leite":
            motivo = f"tipo {a['tipo'] or 'não informado'}"
        else:
            motivo = "vaca seca"
        ignoradas.append({"nome": a["nome"], "motivo": motivo})

    return {"vacas": vacas, "ignoradas": ignoradas, "total_animais": len(animais)}


@app.post("/registrarProducaoLeite", status_code=201)
def registrar_producao_leite(d: dict):
    data = _data_valida(d.get("data"))
    if data > date.today():
        raise HTTPException(status_code=400, detail="A data não pode ser futura.")

    responsavel = (d.get("responsavel") or "").strip()
    if not responsavel:
        raise HTTPException(status_code=400, detail="Informe o responsável pela medição.")

    lote = d.get("lote")
    permitidas = {v["id"] for v in _vacas_aptas(_lote_por_nome(lote))}

    registros = []   # (animal_id, turno, litros)
    for m in d.get("medicoes") or []:
        animal_id = m.get("animal_id")
        if animal_id not in permitidas:
            raise HTTPException(status_code=400,
                                detail=f"O animal {animal_id} não é uma vaca em produção do lote {lote}.")
        for turno, chave in ((TURNO_MANHA, "manha"), (TURNO_TARDE, "tarde")):
            bruto = m.get(chave)
            if bruto is None or bruto == "":
                continue    # campo vazio = não medido, não grava nada
            try:
                litros = float(bruto)
            except (TypeError, ValueError):
                raise HTTPException(status_code=400, detail="Há um valor de leite inválido.")
            if not math.isfinite(litros) or litros < 0:
                raise HTTPException(status_code=400, detail="O leite não pode ser negativo.")
            registros.append((animal_id, turno, round(litros, 2)))

    if not registros:
        raise HTTPException(status_code=400, detail="Preencha ao menos um valor de leite.")

    conn = conectar()
    try:
        cursor = conn.cursor()
        for animal_id, turno, litros in registros:
            cursor.execute("""SELECT id FROM producao_leite
                              WHERE animal_id = ? AND data_producao = ? AND turno = ?""",
                           (animal_id, data.isoformat(), turno))
            existente = cursor.fetchone()
            if existente:
                cursor.execute("UPDATE producao_leite SET litros = ?, responsavel = ? WHERE id = ?",
                               (litros, responsavel, existente[0]))
            else:
                cursor.execute("""INSERT INTO producao_leite
                                  (animal_id, data_producao, litros, turno, responsavel)
                                  VALUES (?, ?, ?, ?, ?)""",
                               (animal_id, data.isoformat(), litros, turno, responsavel))
        conn.commit()
    finally:
        conn.close()

    registrar_log("Registro", "producao_leite",
                  f"Produção de leite do lote {lote} registrada em {_br(data)} "
                  f"({len(registros)} lançamentos, responsável {responsavel})")
    return {"message": "Produção registrada!", "registros": len(registros)}


# ---------- Leite: tabela ----------
@app.get("/consultarProducaoLeite")
def consultar_producao_leite(lote: str = "", dias: int = 30, ordem: str = "alfabetica"):
    return {"vacas": _producao_por_vaca(lote, dias, ordem)}


# ---------- Leite: relatório em PDF ----------
@app.get("/relatorioLeite")
def relatorio_leite(lote: str = "", dias: int = 30, ordem: str = "maior"):
    try:
        from reportlab.lib import colors
        from reportlab.lib.pagesizes import A4
        from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
        from reportlab.lib.units import cm
        from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle
    except ImportError:
        raise HTTPException(status_code=500,
                            detail="Instale a biblioteca reportlab (pip install reportlab) para gerar o PDF.")

    vacas = _producao_por_vaca(lote, dias, ordem)
    resumo = _resumo_leite(dias, lote)
    media = resumo["litros"] / resumo["dias_medidos"] if resumo["dias_medidos"] else 0
    ranking = sorted((v for v in vacas if v["total"] > 0),
                     key=lambda v: (-v["total"], _chave_alfabetica(v["nome"])))[:5]

    hoje = date.today()
    inicio = hoje - timedelta(days=dias - 1)
    periodo = f"hoje ({_br(hoje)})" if dias == 1 else f"{_br(inicio)} a {_br(hoje)} ({dias} dias)"
    escopo = f"lote {_escapar(lote)}" if lote else "todos os lotes"

    verde = colors.HexColor("#2f4a2b")
    palha = colors.HexColor("#e9e4d2")
    linha = colors.HexColor("#dcd8c8")
    suave = colors.HexColor("#6a7468")

    base = getSampleStyleSheet()
    s_titulo = ParagraphStyle("titulo", parent=base["Title"], alignment=0, fontSize=20,
                              textColor=verde, spaceAfter=4)
    s_sub = ParagraphStyle("sub", parent=base["Normal"], fontSize=10, leading=14, textColor=suave)
    s_h2 = ParagraphStyle("h2", parent=base["Heading2"], fontSize=13, textColor=verde,
                          spaceBefore=16, spaceAfter=6)
    s_cel = ParagraphStyle("cel", parent=base["Normal"], fontSize=9, leading=11)

    def tabela(dados, larguras, direita_a_partir, total=False):
        t = Table(dados, colWidths=[l * cm for l in larguras], repeatRows=1)
        estilo = [
            ("BACKGROUND", (0, 0), (-1, 0), verde),
            ("TEXTCOLOR", (0, 0), (-1, 0), palha),
            ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
            ("FONTSIZE", (0, 0), (-1, -1), 9),
            ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, colors.HexColor("#f7f5ec")]),
            ("LINEBELOW", (0, 0), (-1, -1), 0.4, linha),
            ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
            ("ALIGN", (direita_a_partir, 0), (-1, -1), "RIGHT"),
            ("TOPPADDING", (0, 0), (-1, -1), 5),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
        ]
        if total:
            estilo += [("BACKGROUND", (0, -1), (-1, -1), palha),
                       ("FONTNAME", (0, -1), (-1, -1), "Helvetica-Bold")]
        t.setStyle(TableStyle(estilo))
        return t

    elementos = [
        Paragraph("Relatório de produção de leite", s_titulo),
        Paragraph(f"Período: {periodo}<br/>Abrangência: {escopo}<br/>"
                  f"Gerado em {datetime.now():%d/%m/%Y} às {datetime.now():%H:%M}", s_sub),
        Paragraph("Resumo", s_h2),
        tabela([["Indicador", "Valor"],
                ["Total produzido", f"{_litros_br(resumo['litros'])} L"],
                ["Média por dia com medição", f"{_litros_br(media)} L"],
                ["Dias com medição", str(resumo["dias_medidos"])],
                ["Vacas que produziram", str(resumo["vacas"])]],
               [9, 8], 1),
        Paragraph("As 5 vacas que mais produziram", s_h2),
    ]

    if ranking:
        elementos.append(tabela(
            [["Posição", "Vaca", "Lote", "Total"]] +
            [[str(i), Paragraph(_escapar(v["nome"]), s_cel), v["lote"] or "-", f"{_litros_br(v['total'])} L"]
             for i, v in enumerate(ranking, 1)],
            [2, 8, 3, 4], 3))
    else:
        elementos.append(Paragraph("Nenhuma produção registrada no período.", s_sub))

    elementos.append(Paragraph("Produção por vaca", s_h2))
    if vacas:
        soma_manha = sum(v["manha"] for v in vacas)
        soma_tarde = sum(v["tarde"] for v in vacas)
        linhas = [["Vaca", "Brinco", "Lote", "Status", "Manhã", "Tarde", "Total"]]
        for v in vacas:
            linhas.append([Paragraph(_escapar(v["nome"]), s_cel), v["brinco"] or "-", v["lote"] or "-",
                           v["status"] or "-", _litros_br(v["manha"]), _litros_br(v["tarde"]),
                           _litros_br(v["total"])])
        linhas.append(["Total", "", "", "", _litros_br(soma_manha), _litros_br(soma_tarde),
                       _litros_br(soma_manha + soma_tarde)])
        elementos.append(tabela(linhas, [4.6, 2.2, 1.8, 2.4, 2.0, 2.0, 2.0], 4, total=True))
    else:
        elementos.append(Paragraph("Nenhuma vaca encontrada para o filtro escolhido.", s_sub))

    def rodape(canvas, doc):
        canvas.saveState()
        canvas.setFont("Helvetica", 8)
        canvas.setFillColor(suave)
        canvas.drawString(2 * cm, 1.2 * cm, "Gerenciador de Fazendas")
        canvas.drawRightString(A4[0] - 2 * cm, 1.2 * cm, f"Página {doc.page}")
        canvas.restoreState()

    fd, caminho = tempfile.mkstemp(suffix=".pdf")
    os.close(fd)
    SimpleDocTemplate(caminho, pagesize=A4, leftMargin=2 * cm, rightMargin=2 * cm,
                      topMargin=2 * cm, bottomMargin=2 * cm,
                      title="Relatório de produção de leite").build(
        elementos, onFirstPage=rodape, onLaterPages=rodape)

    nome = f"relatorio-leite-{datetime.now():%Y-%m-%d_%H-%M}.pdf"
    return FileResponse(caminho, filename=nome, media_type="application/pdf",
                        background=BackgroundTask(os.remove, caminho))   # apaga o arquivo temporário