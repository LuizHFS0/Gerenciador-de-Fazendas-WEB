"""Rotas do lote em parceria (FazendaWEB).

Uso no api.py, DEPOIS de instalar_autenticacao(app) e das funções consultar/executar:

    from rotas_parceria import instalar_rotas_parceria
    instalar_rotas_parceria(app, consultar, executar, conectar, registrar_log, checar_permissao)

checar_permissao(autorizacao) é a regra "só Dono e Gerente; Funcionário com a senha do gerente".
Ela deve retornar normalmente quando liberado e levantar HTTPException(403, ...) quando não.
Sem ela, as rotas que gravam recusam o pedido (falham fechadas).
"""
import math
import sqlite3
from datetime import date

from fastapi import HTTPException

SEXOS = ("Macho", "Fêmea", "Macho (Castrado)")
SUFIXO_SEXO = {"Macho": "M", "Fêmea": "F", "Macho (Castrado)": "MC"}
MOTIVOS_SAIDA = ("Abate", "Venda", "Devolução ao parceiro", "Morte")
MAX_ANIMAIS = 2000
ALERTA_AVISO_DIAS = 7      # faixa amarela
ALERTA_URGENTE_DIAS = 1    # faixa vermelha (inclui vencido)


def _inteiro_positivo(valor, mensagem):
    try:
        n = int(valor)
    except (TypeError, ValueError):
        raise HTTPException(status_code=400, detail=mensagem)
    if n < 1:
        raise HTTPException(status_code=400, detail=mensagem)
    return n


def _data(valor, mensagem):
    try:
        return date.fromisoformat(str(valor))
    except ValueError:
        raise HTTPException(status_code=400, detail=mensagem)


def _grupos_cadastro(bruto):
    if not isinstance(bruto, list) or not bruto:
        raise HTTPException(status_code=400, detail="Informe ao menos um grupo (quantidade, raça e sexo).")
    juntos = {}
    for g in bruto:
        if not isinstance(g, dict):
            raise HTTPException(status_code=400, detail="Grupo de animais inválido.")
        raca = (g.get("raca") or "").strip()
        sexo = g.get("sexo")
        if not raca:
            raise HTTPException(status_code=400, detail="Informe a raça de todos os grupos.")
        if len(raca) > 60:
            raise HTTPException(status_code=400, detail="O nome da raça é longo demais.")
        if sexo not in SEXOS:
            raise HTTPException(status_code=400, detail="Escolha o sexo de todos os grupos.")
        qtd = _inteiro_positivo(g.get("quantidade"), "A quantidade de cada grupo deve ser um número maior que zero.")
        chave = (raca.casefold(), sexo)
        if chave in juntos:
            juntos[chave][2] += qtd              # mesma raça e sexo repetidos: soma
        else:
            juntos[chave] = [raca, sexo, qtd]
    grupos = list(juntos.values())
    if sum(g[2] for g in grupos) > MAX_ANIMAIS:
        raise HTTPException(status_code=400, detail=f"Um lote aceita no máximo {MAX_ANIMAIS} animais por cadastro.")
    return grupos


def instalar_rotas_parceria(app, consultar, executar, conectar, registrar_log, checar_permissao=None):

    def exigir_permissao(d):
        if checar_permissao is None:
            raise HTTPException(status_code=503, detail="A permissão do lote em parceria ainda não foi configurada.")
        return checar_permissao(d.get("autorizacao"))        # login de quem autorizou, ou None

    def _por(quem):
        return f", autorizado por {quem}" if quem else ""

    # ---------- Parceiros ----------
    @app.get("/parceiros")
    def listar_parceiros():
        return {"parceiros": consultar("SELECT id, nome FROM parceiros WHERE ativo = 1 ORDER BY nome")}

    # ---------- Cadastro do lote ----------
    @app.post("/cadastrarLoteParceria", status_code=201)
    def cadastrar_lote_parceria(d: dict):
        autorizador = exigir_permissao(d)

        lote = d.get("lote") or {}
        nome_lote = (lote.get("nome") or "").strip()
        comum = d.get("tipo") == "comum"          # lote comum: sem parceiro, sem data de saída
        parceiro = "" if comum else (d.get("parceiro") or "").strip()
        if not nome_lote:
            raise HTTPException(status_code=400, detail="Informe o nome do lote.")
        previsto = None
        if not comum:
            if not parceiro:
                raise HTTPException(status_code=400, detail="Informe o nome do fazendeiro parceiro.")
            if len(parceiro) > 120:
                raise HTTPException(status_code=400, detail="O nome do parceiro é longo demais.")
            previsto = _data(d.get("data_prevista_saida"), "Informe a data prevista de saída.")
            if previsto < date.today():
                raise HTTPException(status_code=400, detail="A data prevista de saída não pode ser no passado.")
        tipo_lote = "normal" if comum else "parceria"
        data_saida = previsto.isoformat() if previsto else None
        origem = "Cadastro em lote" if comum else f"Parceria: {parceiro}"
        grupos = _grupos_cadastro(d.get("grupos"))
        total = sum(g[2] for g in grupos)

        tamanho = lote.get("tamanho")
        if tamanho in ("", None):
            tamanho = None
        else:
            try:
                tamanho = float(tamanho)
            except (TypeError, ValueError):
                raise HTTPException(status_code=400, detail="Tamanho do lote inválido.")
            if not math.isfinite(tamanho) or tamanho < 0:
                raise HTTPException(status_code=400, detail="Tamanho do lote inválido.")
        localizacao = (lote.get("localizacao") or "").strip()
        descricao = (lote.get("descricao") or "").strip()
        observacoes = (d.get("observacoes") or "").strip()

        conn = conectar()
        try:
            cur = conn.cursor()

            cur.execute("SELECT id, ativo FROM lote WHERE nome = ?", (nome_lote,))
            existente = cur.fetchone()
            if existente and existente[1] == 1:
                raise HTTPException(status_code=409, detail="Já existe um lote com esse nome.")

            parceiro_id = None
            if not comum:
                cur.execute("SELECT id FROM parceiros WHERE nome = ?", (parceiro,))     # NOCASE na coluna
                linha = cur.fetchone()
                if linha:
                    parceiro_id = linha[0]
                    cur.execute("UPDATE parceiros SET ativo = 1 WHERE id = ?", (parceiro_id,))
                else:
                    cur.execute("INSERT INTO parceiros (nome, ativo) VALUES (?, 1)", (parceiro,))
                    parceiro_id = cur.lastrowid

            if existente:        # lote desativado com o mesmo nome: reativa o registro (o nome é único)
                lote_id = existente[0]
                cur.execute("""UPDATE lote SET tamanho = ?, localizacao = ?, descricao = ?, observacoes = ?,
                                      tipo = ?, parceiro_id = ?, data_prevista_saida = ?, ativo = 1
                               WHERE id = ?""",
                            (tamanho, localizacao, descricao, observacoes, tipo_lote, parceiro_id, data_saida, lote_id))
            else:
                cur.execute("""INSERT INTO lote (nome, tamanho, localizacao, descricao, observacoes,
                                                 tipo, parceiro_id, data_prevista_saida, ativo)
                               VALUES (?, ?, ?, ?, ?, ?, ?, ?, 1)""",
                            (nome_lote, tamanho, localizacao, descricao, observacoes, tipo_lote, parceiro_id, data_saida))
                lote_id = cur.lastrowid

            # o brinco continua de onde o lote parou, mesmo que já tenha tido animais antes
            cur.execute("SELECT COUNT(*) FROM animais WHERE lote_id = ?", (lote_id,))
            seq = cur.fetchone()[0]

            criados = []
            for raca, sexo, qtd in grupos:
                for _ in range(qtd):
                    seq += 1
                    brinco = f"{'LOTE' if comum else 'PARC'}-{lote_id:03d}-{seq:03d}"
                    nome = f"{raca} {SUFIXO_SEXO[sexo]} {seq:03d}"
                    cur.execute("""INSERT INTO animais (brinco, nome, tipo, sexo, raca, peso_atual, data_nascimento,
                                                        status, lote_id, origem, observacoes, ativo, parceria)
                                   VALUES (?, ?, 'Corte', ?, ?, NULL, NULL, 'Ativo', ?, ?, '', 1, ?)""",
                                (brinco, nome, sexo, raca, lote_id, origem, 0 if comum else 1))
                    criados.append({"id": cur.lastrowid, "nome": nome, "brinco": brinco})
            conn.commit()
        except sqlite3.IntegrityError:
            conn.rollback()
            raise HTTPException(status_code=409, detail="Já existe um animal com um dos brincos gerados.")
        finally:
            conn.close()

        if comum:
            detalhe = "lote comum"
        else:
            detalhe = f"parceria com {parceiro}, saída prevista {previsto:%d/%m/%Y}"
        registrar_log("Cadastro", "lote", f'Lote "{nome_lote}" cadastrado: {total} animais ({detalhe}{_por(autorizador)})')
        return {"message": "Lote cadastrado!" if comum else "Lote em parceria cadastrado!",
                "lote_id": lote_id, "animais": criados}

    # ---------- Peso de entrada (opcional, depois do cadastro) ----------
    @app.post("/pesosEntradaLote/{lote_id}")
    def pesos_entrada(lote_id: int, d: dict):
        itens = d.get("pesos")
        if not isinstance(itens, list) or not itens:
            raise HTTPException(status_code=400, detail="Nenhum peso informado.")

        validos = {l["id"] for l in consultar(
            "SELECT id FROM animais WHERE lote_id = ? AND ativo = 1 AND parceria = 1", (lote_id,))}
        pesos = {}
        for item in itens:
            try:
                animal_id = int(item.get("animal_id"))
                peso = float(item.get("peso"))
            except (TypeError, ValueError, AttributeError):
                raise HTTPException(status_code=400, detail="Há um peso inválido.")
            if animal_id not in validos:
                raise HTTPException(status_code=400, detail="Há um animal que não pertence a esse lote.")
            if not math.isfinite(peso) or peso <= 0:
                raise HTTPException(status_code=400, detail="O peso deve ser maior que zero.")
            pesos[animal_id] = round(peso, 2)

        hoje = date.today().isoformat()
        conn = conectar()
        try:
            cur = conn.cursor()
            for animal_id, peso in pesos.items():
                cur.execute("""INSERT INTO pesagens (animal_id, data_pesagem, peso, observacoes)
                               VALUES (?, ?, ?, 'Peso de entrada')""", (animal_id, hoje, peso))
                cur.execute("UPDATE animais SET peso_atual = ? WHERE id = ?", (peso, animal_id))
            conn.commit()
        finally:
            conn.close()

        registrar_log("Registro", "pesagens", f"Peso de entrada de {len(pesos)} animais do lote {lote_id} registrado")
        return {"message": "Pesos registrados!", "registrados": len(pesos)}

    # ---------- Consulta e alertas ----------
    @app.get("/lotesParceria")
    def lotes_parceria():
        lotes = consultar("""
            SELECT l.id, l.nome, l.data_prevista_saida, l.observacoes, p.nome AS parceiro,
                   (SELECT COUNT(*) FROM animais a WHERE a.lote_id = l.id AND a.ativo = 1) AS animais
            FROM lote l LEFT JOIN parceiros p ON p.id = l.parceiro_id
            WHERE l.ativo = 1 AND l.tipo = 'parceria'
            ORDER BY l.data_prevista_saida, l.nome""")
        for l in lotes:
            l["grupos"] = consultar("""SELECT raca, sexo, COUNT(*) AS quantidade FROM animais
                                       WHERE lote_id = ? AND ativo = 1 GROUP BY raca, sexo
                                       ORDER BY raca, sexo""", (l["id"],))
        return {"lotes": lotes}

    @app.get("/alertasParceria")
    def alertas_parceria():
        hoje = date.today()
        saida = []
        for l in lotes_parceria()["lotes"]:
            if not l["animais"] or not l["data_prevista_saida"]:
                continue                       # lote já esvaziado ou sem data: sem alerta
            dias = (date.fromisoformat(l["data_prevista_saida"]) - hoje).days
            if dias > ALERTA_AVISO_DIAS:
                continue
            saida.append({
                "lote_id": l["id"], "lote": l["nome"], "parceiro": l["parceiro"], "animais": l["animais"],
                "data_prevista_saida": l["data_prevista_saida"], "dias_restantes": dias,
                "nivel": "urgente" if dias <= ALERTA_URGENTE_DIAS else "aviso",
            })
        return {"alertas": saida}

    # ---------- Saída do lote ----------
    @app.post("/saidaLoteParceria/{lote_id}")
    def saida_lote_parceria(lote_id: int, d: dict):
        autorizador = exigir_permissao(d)

        motivo = d.get("motivo")
        if motivo not in MOTIVOS_SAIDA:
            raise HTTPException(status_code=400, detail="Escolha o motivo da saída: " + ", ".join(MOTIVOS_SAIDA).lower() + ".")
        dia = _data(d.get("data"), "Informe a data da saída.")
        if dia > date.today():
            raise HTTPException(status_code=400, detail="A data da saída não pode ser no futuro.")

        lote = consultar("SELECT nome FROM lote WHERE id = ? AND ativo = 1 AND tipo = 'parceria'", (lote_id,))
        if not lote:
            raise HTTPException(status_code=404, detail="Lote em parceria não encontrado.")
        nome_lote = lote[0]["nome"]

        animais = {a["id"]: a for a in consultar(
            "SELECT id, nome, raca, sexo, data_nascimento FROM animais WHERE lote_id = ? AND ativo = 1 ORDER BY id",
            (lote_id,))}

        # 1) animais escolhidos a dedo
        escolhidos = []
        for bruto in d.get("animal_ids") or []:
            animal_id = _inteiro_positivo(bruto, "Há um animal inválido na seleção.")
            if animal_id not in animais:
                raise HTTPException(status_code=400, detail="Há um animal que não está mais nesse lote.")
            if animal_id not in escolhidos:
                escolhidos.append(animal_id)

        # 2) o resto por quantidade: saem os mais antigos (menor código) do grupo, pulando os já escolhidos
        pedidos = {}
        for g in d.get("grupos") or []:
            qtd = int(g.get("quantidade") or 0) if str(g.get("quantidade") or "0").lstrip("-").isdigit() else -1
            if qtd < 0:
                raise HTTPException(status_code=400, detail="Há uma quantidade de saída inválida.")
            if qtd == 0:
                continue
            chave = ((g.get("raca") or "").strip().casefold(), g.get("sexo"))
            pedidos[chave] = pedidos.get(chave, 0) + qtd
        for (raca, sexo), qtd in pedidos.items():
            do_grupo = [i for i, a in animais.items()
                        if (a["raca"] or "").strip().casefold() == raca and a["sexo"] == sexo and i not in escolhidos]
            if len(do_grupo) < qtd:
                raise HTTPException(status_code=400,
                                    detail=f"O grupo {raca or 'sem raça'} ({sexo}) tem só {len(do_grupo)} animal(is) disponível(is).")
            escolhidos += do_grupo[:qtd]

        if not escolhidos:
            raise HTTPException(status_code=400, detail="Escolha ao menos um animal ou uma quantidade para sair.")
        for animal_id in escolhidos:
            nascimento = animais[animal_id]["data_nascimento"]
            if nascimento and dia.isoformat() < nascimento:
                raise HTTPException(status_code=400,
                                    detail=f'A data da saída é anterior ao nascimento de "{animais[animal_id]["nome"]}".')

        destino = (d.get("destino") or "").strip()
        obs = (d.get("observacoes") or "").strip()
        texto = " | ".join(p for p in (f"Destino: {destino}" if destino else "", obs) if p) or None

        # peso de saída por animal (opcional): {"id": peso}; vazio = não pesado
        bruto_pesos = d.get("pesos") or {}
        if not isinstance(bruto_pesos, dict):
            raise HTTPException(status_code=400, detail="Pesos de saída inválidos.")
        pesos = {}
        for chave, valor in bruto_pesos.items():
            if valor in ("", None):
                continue
            try:
                animal_id, peso = int(chave), float(valor)
            except (TypeError, ValueError):
                raise HTTPException(status_code=400, detail="Há um peso de saída inválido.")
            if animal_id not in escolhidos:
                raise HTTPException(status_code=400, detail="Há um peso para um animal que não está saindo.")
            if not math.isfinite(peso) or peso <= 0:
                raise HTTPException(status_code=400, detail="O peso de saída deve ser maior que zero.")
            pesos[animal_id] = round(peso, 2)

        conn = conectar()
        try:
            cur = conn.cursor()
            for animal_id in escolhidos:
                if animal_id in pesos:
                    cur.execute("""INSERT INTO pesagens (animal_id, data_pesagem, peso, observacoes)
                                   VALUES (?, ?, ?, 'Peso de saída')""", (animal_id, dia.isoformat(), pesos[animal_id]))
                    cur.execute("""UPDATE animais SET peso_atual = (
                                       SELECT peso FROM pesagens WHERE animal_id = ?
                                       ORDER BY data_pesagem DESC, id DESC LIMIT 1)
                                   WHERE id = ?""", (animal_id, animal_id))
                cur.execute("""UPDATE animais SET ativo = 0, baixa_motivo = ?, baixa_data = ?, baixa_observacoes = ?
                               WHERE id = ? AND ativo = 1""", (motivo, dia.isoformat(), texto, animal_id))
                if cur.rowcount == 0:
                    raise HTTPException(status_code=409, detail="Outra pessoa mexeu nesse lote agora. Atualize e tente de novo.")
            cur.execute("SELECT COUNT(*) FROM animais WHERE lote_id = ? AND ativo = 1", (lote_id,))
            restantes = cur.fetchone()[0]
            conn.commit()
        finally:
            conn.close()

        registrar_log("Baixa", "animais",
                      f'Saída de {len(escolhidos)} animais do lote em parceria "{nome_lote}": {motivo.lower()} em {dia:%d/%m/%Y}{_por(autorizador)}'
                      + (f" ({len(pesos)} pesados)" if pesos else ""))
        return {"message": f"Saída registrada ({len(escolhidos)} animais).", "saidos": len(escolhidos),
                "restantes": restantes, "lote_vazio": restantes == 0, "pesados": len(pesos)}
