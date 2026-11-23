"""Rotas do módulo de bezerros (FazendaWEB).

Uso no api.py, DEPOIS de instalar_autenticacao(app) e das funções consultar/executar:

    from rotas_bezerros import instalar_rotas_bezerros
    instalar_rotas_bezerros(app, consultar, executar, conectar, registrar_log)

Quem pode o quê está em permissoes.py (aplicado no servidor, antes da rota):
  consultar, registrar evento e concluir tarefa: qualquer usuário logado
  registrar cobertura, parto e dispensar tarefa: Gerente ou Dono
  /api/avisos/* (configuração dos avisos): Gerente ou Dono
"""
import math
from datetime import date, timedelta

from fastapi import HTTPException

import banco_fazenda as bf
import esquema_bezerros

TIPOS_COBERTURA = ("monta", "ia", "repasse")
ROTULO_COBERTURA = {"monta": "Monta natural", "ia": "Inseminação", "repasse": "Repasse"}
STATUS_ATIVOS = ("coberta", "gestante")
RESULTADOS = ("positivo", "negativo", "inconclusivo")
TIPOS_EVENTO = ("diagnostico", "secagem", "acompanhamento", "aborto")
ACOMPANHAMENTOS = ("Vacina", "Vermífugo", "Mudança de lote", "Outro")
TIPOS_PARTO = ("unico", "gemeos")
ASSISTENCIAS = ("normal", "assistido", "cesarea")
SITUACOES = ("vivo", "natimorto", "faleceu_apos")
SEXOS_CRIA = ("Macho", "Fêmea")
TIPOS_TAREFA = ("geral", "vacina", "pesagem")
SEXOS_PROTOCOLO = ("todos", "Macho", "Fêmea")
MIN_DIAS_PARTO = 150      # parto antes disso é erro de data (aborto tem registro próprio)
MAX_GEMEOS = 4

# status do animal controlados pelo ciclo reprodutivo (a lista completa está em api.py: STATUS_ANIMAL)
STATUS_ATIVO = "Ativo"
STATUS_PRENHA = "Prenha"
STATUS_SECA = "Seca"


def _trocar_status(cur, animal_id, de, para):
    """Troca o status só se ele ainda estiver em 'de' (tupla). Status manual de outro tipo nunca é sobrescrito."""
    marcas = ",".join("?" * len(de))
    cur.execute(f"UPDATE animais SET status = ? WHERE id = ? AND status IN ({marcas})", (para, animal_id, *de))
    return cur.rowcount


def _aplicar_secagens(cur, hoje, dias_antes):
    limite = (hoje + timedelta(days=dias_antes)).isoformat()
    cur.execute("""UPDATE animais SET status = ? WHERE status = ? AND ativo = 1 AND id IN (
                       SELECT c.vaca_id FROM ciclos_reprodutivos c
                       WHERE c.status = 'gestante' AND c.data_prevista_parto <= ?)""",
                (STATUS_SECA, STATUS_PRENHA, limite))
    return cur.rowcount


def sincronizar_status_reprodutivo(conectar, hoje=None):
    """Passa para Seca as vacas prenhes cujo parto previsto está dentro da antecedência configurada.
    Só afeta quem está 'Prenha'. Pode rodar quantas vezes for preciso (idempotente)."""
    hoje = hoje or date.today()
    conn = conectar()
    try:
        cur = conn.cursor()
        cur.execute("SELECT valor FROM config_avisos WHERE chave = 'secagem_dias_antes'")
        linha = cur.fetchone()
        try:
            dias = int(linha[0]) if linha else esquema_bezerros.CONFIG_PADRAO["secagem_dias_antes"]
        except (TypeError, ValueError):
            dias = esquema_bezerros.CONFIG_PADRAO["secagem_dias_antes"]
        mudou = _aplicar_secagens(cur, hoje, dias)
        conn.commit()
        return mudou
    finally:
        conn.close()

# (mínimo, máximo) de cada ajuste de config_avisos
LIMITES_CONFIG = {
    "aviso_dias_amarelo": (1, 90), "aviso_dias_laranja": (0, 30), "aviso_dias_parto": (1, 90),
    "gestacao_dias": (200, 320), "diagnostico_dias": (20, 120), "secagem_dias_antes": (30, 90),
}


def _data(valor, mensagem):
    try:
        return date.fromisoformat(str(valor))
    except ValueError:
        raise HTTPException(status_code=400, detail=mensagem)


def _texto(valor, maximo, mensagem):
    texto = (valor or "").strip() if isinstance(valor, str) or valor is None else str(valor).strip()
    if len(texto) > maximo:
        raise HTTPException(status_code=400, detail=mensagem)
    return texto


def _inteiro(valor, minimo, maximo, mensagem):
    if isinstance(valor, bool):
        raise HTTPException(status_code=400, detail=mensagem)
    try:
        n = float(valor)
    except (TypeError, ValueError):
        raise HTTPException(status_code=400, detail=mensagem)
    if not math.isfinite(n) or n != int(n) or not minimo <= int(n) <= maximo:
        raise HTTPException(status_code=400, detail=mensagem)
    return int(n)


def _peso(valor, mensagem="O peso deve ser maior que zero."):
    if valor in (None, ""):
        return None
    try:
        peso = float(valor)
    except (TypeError, ValueError):
        raise HTTPException(status_code=400, detail=mensagem)
    if not math.isfinite(peso) or peso <= 0 or peso > 5000:
        raise HTTPException(status_code=400, detail=mensagem)
    return round(peso, 2)


def _quem():
    u = bf.usuario_atual() or {}
    return u.get("nome") or u.get("usuario") or ""


def nivel_por_dias(dias, cfg, janela_amarela=None):
    """vencida (vermelho) | urgente (laranja) | aviso (amarelo) | None (ainda longe)."""
    if dias < 0:
        return "vencida"
    if dias <= cfg["aviso_dias_laranja"]:
        return "urgente"
    if dias <= (janela_amarela if janela_amarela is not None else cfg["aviso_dias_amarelo"]):
        return "aviso"
    return None


def instalar_rotas_bezerros(app, consultar, executar, conectar, registrar_log):

    # ---------- configuração dos avisos ----------
    def ler_config():
        cfg = dict(esquema_bezerros.CONFIG_PADRAO)
        for linha in consultar("SELECT chave, valor FROM config_avisos"):
            if linha["chave"] in cfg:
                try:
                    cfg[linha["chave"]] = int(linha["valor"])
                except (TypeError, ValueError):
                    pass
        return cfg

    def salvar_config(cur, valores):
        for chave, valor in valores.items():
            cur.execute("""INSERT INTO config_avisos (chave, valor) VALUES (?, ?)
                           ON CONFLICT(chave) DO UPDATE SET valor = excluded.valor""", (chave, str(valor)))

    # ---------- consultas de apoio ----------
    def vaca_ou_erro(vaca_id):
        r = consultar("""SELECT a.id, a.nome, a.brinco, a.sexo, a.tipo, a.raca, a.status, a.lote_id, a.parceria,
                                a.data_nascimento, l.nome AS lote
                         FROM animais a LEFT JOIN lote l ON l.id = a.lote_id
                         WHERE a.id = ? AND a.ativo = 1""", (vaca_id,))
        if not r:
            raise HTTPException(status_code=404, detail="Animal não encontrado.")
        if r[0]["sexo"] != "Fêmea":
            raise HTTPException(status_code=400, detail="O módulo de bezerros existe só para fêmeas.")
        return r[0]

    def ciclo_ou_erro(ciclo_id):
        r = consultar("SELECT * FROM ciclos_reprodutivos WHERE id = ?", (ciclo_id,))
        if not r:
            raise HTTPException(status_code=404, detail="Ciclo não encontrado.")
        return r[0]

    def rotulo_touro(c):
        if c["touro_id"]:
            t = consultar("SELECT nome, brinco FROM animais WHERE id = ?", (c["touro_id"],))
            if t:
                return f'{t[0]["nome"]} ({t[0]["brinco"]})' if t[0]["brinco"] else t[0]["nome"]
        return c["touro_texto"] or "Não informado"

    def dias_ate(iso, hoje=None):
        return (date.fromisoformat(iso) - (hoje or date.today())).days

    # ---------- touros para o select ----------
    @app.get("/touros")
    def listar_touros():
        return {"touros": consultar("""SELECT id, nome, brinco, raca FROM animais
                                       WHERE ativo = 1 AND sexo = 'Macho' ORDER BY nome""")}

    # ---------- visão da vaca: ciclo atual, linha do tempo, histórico e crias ----------
    def montar_linha_do_tempo(ciclo, vaca, cfg):
        eventos = consultar("SELECT * FROM eventos_reprodutivos WHERE ciclo_id = ? ORDER BY data, id", (ciclo["id"],))
        linha = [{"tipo": "cobertura", "titulo": ROTULO_COBERTURA.get(ciclo["tipo_cobertura"], "Cobertura"),
                  "data": ciclo["data_cobertura"], "previsto": False,
                  "detalhe": f"Touro: {rotulo_touro(ciclo)}" + (f' · {ciclo["observacoes"]}' if ciclo["observacoes"] else ""),
                  "responsavel": None}]
        for e in eventos:
            if e["tipo"] == "diagnostico":
                titulo, detalhe = "Diagnóstico de gestação", {"positivo": "Positivo (prenha)", "negativo": "Negativo (vazia)",
                                                              "inconclusivo": "Inconclusivo"}.get(e["resultado"], "")
            elif e["tipo"] == "secagem":
                titulo, detalhe = "Secagem da vaca", ""
            elif e["tipo"] == "aborto":
                titulo, detalhe = "Aborto", ""
            else:
                titulo, detalhe = e["titulo"] or "Acompanhamento", ""
            if e["observacoes"]:
                detalhe = f'{detalhe} · {e["observacoes"]}' if detalhe else e["observacoes"]
            linha.append({"tipo": e["tipo"], "titulo": titulo, "data": e["data"], "previsto": False,
                          "detalhe": detalhe or None, "responsavel": e["responsavel"]})
        if ciclo["status"] in STATUS_ATIVOS:
            feitos = {e["tipo"] for e in eventos}
            inicio = date.fromisoformat(ciclo["data_cobertura"])
            if "diagnostico" not in feitos:
                linha.append({"tipo": "previsto_diagnostico", "titulo": "Diagnóstico de gestação",
                              "data": (inicio + timedelta(days=cfg["diagnostico_dias"])).isoformat(),
                              "previsto": True, "detalhe": "Previsto", "responsavel": None})
            if "secagem" not in feitos:
                prevista = date.fromisoformat(ciclo["data_prevista_parto"]) - timedelta(days=cfg["secagem_dias_antes"])
                linha.append({"tipo": "previsto_secagem", "titulo": "Secagem da vaca", "data": prevista.isoformat(),
                              "previsto": True, "detalhe": "Prevista", "responsavel": None})
            linha.append({"tipo": "previsto_parto", "titulo": "Parto", "data": ciclo["data_prevista_parto"],
                          "previsto": True, "detalhe": "Previsto", "responsavel": None})
        linha.sort(key=lambda x: (x["data"], x["previsto"]))
        return linha

    def resumo_parto(ciclo_id):
        p = consultar("SELECT * FROM partos WHERE ciclo_id = ?", (ciclo_id,))
        if not p:
            return None
        crias = consultar("""SELECT b.ordem, b.sexo, b.peso_nascimento, b.situacao, b.causa, b.animal_id, a.nome AS animal
                             FROM partos_bezerros b LEFT JOIN animais a ON a.id = b.animal_id
                             WHERE b.parto_id = ? ORDER BY b.ordem""", (p[0]["id"],))
        return {"data_parto": p[0]["data_parto"], "tipo_parto": p[0]["tipo_parto"],
                "tipo_assistencia": p[0]["tipo_assistencia"], "observacoes": p[0]["observacoes"], "bezerros": crias}

    @app.get("/reproducao/{vaca_id}")
    def reproducao_da_vaca(vaca_id: int):
        sincronizar_status_reprodutivo(conectar)
        vaca = vaca_ou_erro(vaca_id)
        cfg = ler_config()
        ciclos = consultar("SELECT * FROM ciclos_reprodutivos WHERE vaca_id = ? ORDER BY data_cobertura DESC, id DESC",
                           (vaca_id,))
        atual, historico = None, []
        for c in ciclos:
            if c["status"] in STATUS_ATIVOS and atual is None:
                atual = {**c, "touro": rotulo_touro(c), "dias_para_parto": dias_ate(c["data_prevista_parto"]),
                         "linha_do_tempo": montar_linha_do_tempo(c, vaca, cfg)}
            else:
                historico.append({**c, "touro": rotulo_touro(c), "parto": resumo_parto(c["id"]),
                                  "linha_do_tempo": montar_linha_do_tempo(c, vaca, cfg)})
        filhos = consultar("""SELECT a.id, a.nome, a.brinco, a.sexo, a.data_nascimento, a.status, a.ativo,
                                     a.baixa_motivo
                              FROM animais a WHERE a.mae_id = ? ORDER BY a.data_nascimento DESC, a.id DESC""", (vaca_id,))
        return {"vaca": vaca, "config": cfg, "ciclo_atual": atual, "historico": historico, "bezerros": filhos}

    # ---------- cobertura (abre um ciclo) ----------
    @app.post("/reproducao/{vaca_id}/cobertura", status_code=201)
    def registrar_cobertura(vaca_id: int, d: dict):
        vaca = vaca_ou_erro(vaca_id)
        tipo = d.get("tipo_cobertura")
        if tipo not in TIPOS_COBERTURA:
            raise HTTPException(status_code=400, detail="Escolha o tipo de cobertura: monta natural, inseminação ou repasse.")
        dia = _data(d.get("data_cobertura"), "Informe a data da cobertura.")
        if dia > date.today():
            raise HTTPException(status_code=400, detail="A data da cobertura não pode ser no futuro.")
        if vaca["data_nascimento"] and dia.isoformat() < vaca["data_nascimento"]:
            raise HTTPException(status_code=400, detail="A cobertura é anterior ao nascimento da vaca.")

        touro_id, touro_texto = None, _texto(d.get("touro_texto"), 120, "O nome do touro ou do sêmen é longo demais.")
        if d.get("touro_id") not in (None, ""):
            touro_id = _inteiro(d.get("touro_id"), 1, 2_000_000_000, "Touro inválido.")
            if touro_id == vaca_id:
                raise HTTPException(status_code=400, detail="A vaca não pode ser o próprio touro.")
            if not consultar("SELECT 1 FROM animais WHERE id = ? AND ativo = 1 AND sexo = 'Macho'", (touro_id,)):
                raise HTTPException(status_code=400, detail="Touro não encontrado entre os machos ativos.")
            touro_texto = ""
        elif not touro_texto:
            raise HTTPException(status_code=400, detail="Escolha o touro do sistema ou informe o touro (ou sêmen) usado.")
        obs = _texto(d.get("observacoes"), 500, "As observações são longas demais.")

        cfg = ler_config()
        prevista = dia + timedelta(days=cfg["gestacao_dias"])
        conn = conectar()
        try:
            cur = conn.cursor()
            cur.execute("SELECT 1 FROM ciclos_reprodutivos WHERE vaca_id = ? AND status IN ('coberta', 'gestante')", (vaca_id,))
            if cur.fetchone():
                raise HTTPException(status_code=409, detail="Esta vaca já tem um ciclo em andamento. Encerre-o antes de abrir outro.")
            cur.execute("""INSERT INTO ciclos_reprodutivos (vaca_id, tipo_cobertura, touro_id, touro_texto, data_cobertura,
                                                            data_prevista_parto, status, observacoes)
                           VALUES (?, ?, ?, ?, ?, ?, 'coberta', ?)""",
                        (vaca_id, tipo, touro_id, touro_texto or None, dia.isoformat(), prevista.isoformat(), obs or None))
            ciclo_id = cur.lastrowid
            conn.commit()
        finally:
            conn.close()
        registrar_log("Cadastro", "ciclos_reprodutivos",
                      f'Cobertura de "{vaca["nome"]}" registrada em {dia:%d/%m/%Y} ({ROTULO_COBERTURA[tipo].lower()}); '
                      f'parto previsto para {prevista:%d/%m/%Y}')
        return {"message": "Cobertura registrada!", "ciclo_id": ciclo_id, "data_prevista_parto": prevista.isoformat()}

    # ---------- eventos da linha do tempo ----------
    @app.post("/ciclos/{ciclo_id}/eventos", status_code=201)
    def registrar_evento(ciclo_id: int, d: dict):
        ciclo = ciclo_ou_erro(ciclo_id)
        if ciclo["status"] not in STATUS_ATIVOS:
            raise HTTPException(status_code=409, detail="Este ciclo já foi encerrado.")
        vaca = vaca_ou_erro(ciclo["vaca_id"])
        tipo = d.get("tipo")
        if tipo not in TIPOS_EVENTO:
            raise HTTPException(status_code=400, detail="Escolha o tipo do evento.")
        dia = _data(d.get("data"), "Informe a data do evento.")
        if dia > date.today():
            raise HTTPException(status_code=400, detail="A data do evento não pode ser no futuro.")
        if dia.isoformat() < ciclo["data_cobertura"]:
            raise HTTPException(status_code=400, detail="O evento é anterior à cobertura.")
        obs = _texto(d.get("observacoes"), 500, "As observações são longas demais.")

        resultado, titulo = None, None
        if tipo == "diagnostico":
            resultado = d.get("resultado")
            if resultado not in RESULTADOS:
                raise HTTPException(status_code=400, detail="Informe o resultado do diagnóstico.")
        elif tipo == "acompanhamento":
            titulo = _texto(d.get("titulo"), 60, "O título é longo demais.")
            if not titulo:
                raise HTTPException(status_code=400, detail="Escolha ou escreva o que foi feito.")
        elif tipo == "secagem" and consultar(
                "SELECT 1 FROM eventos_reprodutivos WHERE ciclo_id = ? AND tipo = 'secagem'", (ciclo_id,)):
            raise HTTPException(status_code=409, detail="A secagem deste ciclo já foi registrada.")

        novo_status, encerra = None, False
        if tipo == "diagnostico":
            if resultado == "positivo":
                novo_status = "gestante"
            elif resultado == "negativo":
                novo_status, encerra = "vazia", True
        elif tipo == "aborto":
            novo_status, encerra = "aborto", True

        conn = conectar()
        try:
            cur = conn.cursor()
            cur.execute("""INSERT INTO eventos_reprodutivos (ciclo_id, tipo, data, resultado, titulo, observacoes, responsavel)
                           VALUES (?, ?, ?, ?, ?, ?, ?)""",
                        (ciclo_id, tipo, dia.isoformat(), resultado, titulo, obs or None, _quem()))
            if novo_status:
                cur.execute("UPDATE ciclos_reprodutivos SET status = ?, data_encerramento = ? WHERE id = ?",
                            (novo_status, dia.isoformat() if encerra else None, ciclo_id))
            if tipo == "diagnostico" and resultado == "positivo":
                _trocar_status(cur, ciclo["vaca_id"], (STATUS_ATIVO,), STATUS_PRENHA)
            elif (tipo == "diagnostico" and resultado == "negativo") or tipo == "aborto":
                _trocar_status(cur, ciclo["vaca_id"], (STATUS_PRENHA, STATUS_SECA), STATUS_ATIVO)
            elif tipo == "secagem":
                _trocar_status(cur, ciclo["vaca_id"], (STATUS_PRENHA,), STATUS_SECA)
            conn.commit()
        finally:
            conn.close()
        nome_evento = {"diagnostico": f"diagnóstico {resultado}", "secagem": "secagem", "aborto": "aborto",
                       "acompanhamento": (titulo or "acompanhamento").lower()}[tipo]
        registrar_log("Registro", "eventos_reprodutivos", f'Evento "{nome_evento}" registrado para "{vaca["nome"]}" em {dia:%d/%m/%Y}')
        return {"message": "Evento registrado!", "status_ciclo": novo_status or ciclo["status"]}

    # ---------- parto (cria os bezerros) ----------
    def gerar_tarefas(cur, animal_id, sexo, nascimento, protocolo):
        n = 0
        for item in protocolo:
            if item["so_sexo"] not in ("todos", sexo):
                continue
            cur.execute("""INSERT INTO tarefas_bezerro (animal_id, protocolo_id, nome, tipo, data_prevista, status)
                           VALUES (?, ?, ?, ?, ?, 'pendente')""",
                        (animal_id, item["id"], item["nome"], item["tipo"],
                         (nascimento + timedelta(days=item["dias_apos_nascimento"])).isoformat()))
            n += 1
        return n

    @app.post("/ciclos/{ciclo_id}/parto", status_code=201)
    def registrar_parto(ciclo_id: int, d: dict):
        ciclo = ciclo_ou_erro(ciclo_id)
        if ciclo["status"] not in STATUS_ATIVOS:
            raise HTTPException(status_code=409, detail="Este ciclo já foi encerrado.")
        vaca = vaca_ou_erro(ciclo["vaca_id"])

        dia = _data(d.get("data_parto"), "Informe a data do parto.")
        if dia > date.today():
            raise HTTPException(status_code=400, detail="A data do parto não pode ser no futuro.")
        if (dia - date.fromisoformat(ciclo["data_cobertura"])).days < MIN_DIAS_PARTO:
            raise HTTPException(status_code=400, detail=f"O parto precisa ser pelo menos {MIN_DIAS_PARTO} dias depois da cobertura. "
                                                         "Se a gestação foi interrompida, registre como aborto.")
        tipo_parto = d.get("tipo_parto") or "unico"
        if tipo_parto not in TIPOS_PARTO:
            raise HTTPException(status_code=400, detail="Escolha se o parto foi único ou de gêmeos.")
        assistencia = d.get("tipo_assistencia") or None
        if assistencia is not None and assistencia not in ASSISTENCIAS:
            raise HTTPException(status_code=400, detail="Tipo de parto inválido.")
        obs = _texto(d.get("observacoes"), 500, "As observações são longas demais.")

        crias = d.get("bezerros")
        if not isinstance(crias, list) or not crias:
            raise HTTPException(status_code=400, detail="Informe ao menos um bezerro.")
        if tipo_parto == "unico" and len(crias) != 1:
            raise HTTPException(status_code=400, detail="Parto único tem um bezerro. Para mais de um, escolha gêmeos.")
        if tipo_parto == "gemeos" and not 2 <= len(crias) <= MAX_GEMEOS:
            raise HTTPException(status_code=400, detail=f"Parto de gêmeos tem de 2 a {MAX_GEMEOS} bezerros.")

        limpas, brincos_pedidos = [], set()
        for i, c in enumerate(crias, 1):
            if not isinstance(c, dict):
                raise HTTPException(status_code=400, detail="Bezerro inválido.")
            if c.get("sexo") not in SEXOS_CRIA:
                raise HTTPException(status_code=400, detail=f"Escolha o sexo do bezerro {i}.")
            situacao = c.get("situacao") or "vivo"
            if situacao not in SITUACOES:
                raise HTTPException(status_code=400, detail=f"Situação inválida no bezerro {i}.")
            brinco = _texto(c.get("brinco"), 30, f"O brinco do bezerro {i} é longo demais.")
            if brinco:
                if brinco.casefold() in brincos_pedidos:
                    raise HTTPException(status_code=400, detail="Há dois bezerros com o mesmo brinco.")
                brincos_pedidos.add(brinco.casefold())
            limpas.append({
                "ordem": i, "sexo": c["sexo"], "situacao": situacao, "brinco": brinco,
                "nome": _texto(c.get("nome"), 80, f"O nome do bezerro {i} é longo demais."),
                "raca": _texto(c.get("raca"), 80, f"A raça do bezerro {i} é longa demais."),
                "peso": _peso(c.get("peso"), f"O peso do bezerro {i} deve ser maior que zero."),
                "causa": _texto(c.get("causa"), 200, f"A causa do bezerro {i} é longa demais."),
                "observacoes": _texto(c.get("observacoes"), 300, f"As observações do bezerro {i} são longas demais."),
                "manter_historico": bool(c.get("manter_historico")),
            })

        protocolo = consultar("SELECT * FROM protocolo_bezerro WHERE ativo = 1 ORDER BY dias_apos_nascimento, id")
        criados, tarefas = [], 0
        conn = conectar()
        try:
            cur = conn.cursor()
            cur.execute("SELECT 1 FROM ciclos_reprodutivos WHERE id = ? AND status IN ('coberta', 'gestante')", (ciclo_id,))
            if not cur.fetchone():
                raise HTTPException(status_code=409, detail="Este ciclo já foi encerrado.")
            for c in limpas:
                if c["brinco"]:
                    cur.execute("SELECT 1 FROM animais WHERE brinco = ? COLLATE NOCASE", (c["brinco"],))
                    if cur.fetchone():
                        raise HTTPException(status_code=409, detail=f'Já existe um animal com o brinco "{c["brinco"]}".')
            cur.execute("SELECT COUNT(*) FROM animais WHERE mae_id = ?", (vaca["id"],))
            sequencia = cur.fetchone()[0]

            cur.execute("""INSERT INTO partos (ciclo_id, data_parto, tipo_parto, tipo_assistencia, observacoes)
                           VALUES (?, ?, ?, ?, ?)""", (ciclo_id, dia.isoformat(), tipo_parto, assistencia, obs or None))
            parto_id = cur.lastrowid

            for c in limpas:
                animal_id = None
                vivo = c["situacao"] == "vivo"
                if vivo or (c["situacao"] == "faleceu_apos" and c["manter_historico"]):
                    brinco = c["brinco"]
                    while not brinco:                                  # brinco automático: BRINCO-DA-MÃE-C1, C2...
                        sequencia += 1
                        candidato = f'{vaca["brinco"] or "V" + str(vaca["id"])}-C{sequencia}'
                        cur.execute("SELECT 1 FROM animais WHERE brinco = ? COLLATE NOCASE", (candidato,))
                        if not cur.fetchone() and candidato.casefold() not in brincos_pedidos:
                            brinco = candidato
                    nome = c["nome"] or f'Cria de {vaca["nome"]} {dia.year}' + (f' ({c["ordem"]})' if tipo_parto == "gemeos" else "")
                    cur.execute("""INSERT INTO animais (brinco, nome, tipo, sexo, raca, peso_atual, data_nascimento, status,
                                                        lote_id, origem, observacoes, ativo, parceria, mae_id, pai_id, pai_texto,
                                                        baixa_motivo, baixa_data, baixa_observacoes)
                                   VALUES (?, ?, ?, ?, ?, ?, ?, 'Ativo', ?, 'Nascido na fazenda', ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                                (brinco, nome, vaca["tipo"] or "Corte", c["sexo"], c["raca"] or vaca["raca"] or "", c["peso"],
                                 dia.isoformat(), vaca["lote_id"], c["observacoes"], 1 if vivo else 0, vaca["parceria"] or 0,
                                 vaca["id"], ciclo["touro_id"], ciclo["touro_texto"],
                                 None if vivo else "Morte", None if vivo else dia.isoformat(), None if vivo else (c["causa"] or None)))
                    animal_id = cur.lastrowid
                    if c["peso"]:
                        cur.execute("""INSERT INTO pesagens (animal_id, data_pesagem, peso, observacoes)
                                       VALUES (?, ?, ?, 'Peso ao nascer')""", (animal_id, dia.isoformat(), c["peso"]))
                    if vivo:
                        tarefas += gerar_tarefas(cur, animal_id, c["sexo"], dia, protocolo)
                    criados.append({"id": animal_id, "nome": nome, "brinco": brinco, "situacao": c["situacao"]})
                cur.execute("""INSERT INTO partos_bezerros (parto_id, ordem, sexo, peso_nascimento, situacao, causa, observacoes, animal_id)
                               VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
                            (parto_id, c["ordem"], c["sexo"], c["peso"], c["situacao"], c["causa"] or None,
                             c["observacoes"] or None, animal_id))
            cur.execute("UPDATE ciclos_reprodutivos SET status = 'parida', data_encerramento = ? WHERE id = ?",
                        (dia.isoformat(), ciclo_id))
            _trocar_status(cur, ciclo["vaca_id"], (STATUS_PRENHA, STATUS_SECA), STATUS_ATIVO)
            conn.commit()
        except HTTPException:
            conn.rollback()
            raise
        finally:
            conn.close()

        vivos = sum(1 for c in limpas if c["situacao"] == "vivo")
        registrar_log("Cadastro", "partos",
                      f'Parto de "{vaca["nome"]}" registrado em {dia:%d/%m/%Y}: {len(limpas)} cria(s), {vivos} viva(s)')
        return {"message": "Parto registrado!", "bezerros": criados, "tarefas_geradas": tarefas}

    # ---------- tarefas do bezerro ----------
    def tarefa_ou_erro(tarefa_id):
        r = consultar("""SELECT t.*, a.nome AS animal, a.data_nascimento, a.ativo AS animal_ativo
                         FROM tarefas_bezerro t JOIN animais a ON a.id = t.animal_id WHERE t.id = ?""", (tarefa_id,))
        if not r or not r[0]["animal_ativo"]:
            raise HTTPException(status_code=404, detail="Tarefa não encontrada.")
        return r[0]

    @app.get("/bezerros/tarefas/{animal_id}")
    def tarefas_do_bezerro(animal_id: int):
        cfg, hoje = ler_config(), date.today()
        linhas = consultar("""SELECT t.id, t.nome, t.tipo, t.data_prevista, t.data_realizada, t.responsavel, t.observacoes,
                                     t.status, p.orientacao
                              FROM tarefas_bezerro t LEFT JOIN protocolo_bezerro p ON p.id = t.protocolo_id
                              WHERE t.animal_id = ?
                              ORDER BY CASE t.status WHEN 'pendente' THEN 0 ELSE 1 END, t.data_prevista, t.id""", (animal_id,))
        for t in linhas:
            if t["status"] == "pendente":
                t["dias_restantes"] = dias_ate(t["data_prevista"], hoje)
                t["nivel"] = nivel_por_dias(t["dias_restantes"], cfg)
            else:
                t["dias_restantes"], t["nivel"] = None, None
        return {"tarefas": linhas}

    @app.get("/bezerros/alertas")
    def alertas_bezerros():
        cfg, hoje = ler_config(), date.today()
        sincronizar_status_reprodutivo(conectar, hoje)
        tarefas = []
        for t in consultar("""SELECT t.id, t.animal_id, t.nome, t.data_prevista, a.nome AS animal, a.brinco
                              FROM tarefas_bezerro t JOIN animais a ON a.id = t.animal_id
                              WHERE t.status = 'pendente' AND a.ativo = 1 ORDER BY t.data_prevista, a.nome, t.id"""):
            dias = dias_ate(t["data_prevista"], hoje)
            nivel = nivel_por_dias(dias, cfg)
            if nivel:
                tarefas.append({**t, "dias_restantes": dias, "nivel": nivel})

        gestacoes = []
        ciclos = consultar("""SELECT c.id, c.vaca_id, c.status, c.data_cobertura, c.data_prevista_parto, a.nome AS vaca, a.tipo
                              FROM ciclos_reprodutivos c JOIN animais a ON a.id = c.vaca_id
                              WHERE c.status IN ('coberta', 'gestante') AND a.ativo = 1 ORDER BY c.data_prevista_parto""")
        for c in ciclos:
            eventos = {e["tipo"] for e in consultar("SELECT tipo FROM eventos_reprodutivos WHERE ciclo_id = ?", (c["id"],))}
            candidatos = [("parto", "Parto previsto", c["data_prevista_parto"], cfg["aviso_dias_parto"])]
            if "diagnostico" not in eventos:
                diag = date.fromisoformat(c["data_cobertura"]) + timedelta(days=cfg["diagnostico_dias"])
                candidatos.append(("diagnostico", "Diagnóstico de gestação", diag.isoformat(), None))
            if "secagem" not in eventos:
                sec = date.fromisoformat(c["data_prevista_parto"]) - timedelta(days=cfg["secagem_dias_antes"])
                candidatos.append(("secagem", "Secagem da vaca", sec.isoformat(), None))
            for tipo, titulo, data_alvo, janela in candidatos:
                dias = dias_ate(data_alvo, hoje)
                nivel = nivel_por_dias(dias, cfg, janela)
                if nivel:
                    gestacoes.append({"ciclo_id": c["id"], "vaca_id": c["vaca_id"], "vaca": c["vaca"], "tipo": tipo,
                                      "titulo": titulo, "data": data_alvo, "dias_restantes": dias, "nivel": nivel})
        gestacoes.sort(key=lambda g: g["data"])
        return {"tarefas": tarefas, "gestacoes": gestacoes, "total": len(tarefas) + len(gestacoes)}

    @app.post("/tarefasBezerro/{tarefa_id}/concluir")
    def concluir_tarefa(tarefa_id: int, d: dict):
        t = tarefa_ou_erro(tarefa_id)
        if t["status"] != "pendente":
            raise HTTPException(status_code=409, detail="Esta tarefa já foi encerrada.")
        dia = _data(d.get("data") or date.today().isoformat(), "Informe a data em que foi feita.")
        if dia > date.today():
            raise HTTPException(status_code=400, detail="A data não pode ser no futuro.")
        if t["data_nascimento"] and dia.isoformat() < t["data_nascimento"]:
            raise HTTPException(status_code=400, detail="A data é anterior ao nascimento do bezerro.")
        obs = _texto(d.get("observacoes"), 300, "As observações são longas demais.")
        peso = _peso(d.get("peso")) if t["tipo"] == "pesagem" else None

        proximo = None
        if t["protocolo_id"]:
            p = consultar("SELECT * FROM protocolo_bezerro WHERE id = ? AND ativo = 1", (t["protocolo_id"],))
            if p and p[0]["repetir_a_cada_dias"] and t["data_nascimento"]:
                data_proxima = dia + timedelta(days=p[0]["repetir_a_cada_dias"])
                idade = (data_proxima - date.fromisoformat(t["data_nascimento"])).days
                if p[0]["repetir_ate_dias"] is None or idade <= p[0]["repetir_ate_dias"]:
                    proximo = data_proxima

        conn = conectar()
        try:
            cur = conn.cursor()
            cur.execute("""UPDATE tarefas_bezerro SET status = 'feita', data_realizada = ?, responsavel = ?, observacoes = ?
                           WHERE id = ? AND status = 'pendente'""", (dia.isoformat(), _quem(), obs or None, tarefa_id))
            if cur.rowcount == 0:
                raise HTTPException(status_code=409, detail="Outra pessoa já encerrou esta tarefa.")
            if t["tipo"] == "vacina":
                cur.execute("""INSERT INTO vacinas (animal_id, vacina, data_aplicacao, proxima_dose, responsavel, observacoes)
                               VALUES (?, ?, ?, NULL, ?, ?)""", (t["animal_id"], t["nome"], dia.isoformat(), _quem(), obs or ""))
            if peso:
                cur.execute("""INSERT INTO pesagens (animal_id, data_pesagem, peso, observacoes)
                               VALUES (?, ?, ?, ?)""", (t["animal_id"], dia.isoformat(), peso, t["nome"]))
                cur.execute("""UPDATE animais SET peso_atual = (SELECT peso FROM pesagens WHERE animal_id = ?
                                                                ORDER BY data_pesagem DESC, id DESC LIMIT 1)
                               WHERE id = ?""", (t["animal_id"], t["animal_id"]))
            if proximo:
                cur.execute("""INSERT INTO tarefas_bezerro (animal_id, protocolo_id, nome, tipo, data_prevista, status)
                               VALUES (?, ?, ?, ?, ?, 'pendente')""",
                            (t["animal_id"], t["protocolo_id"], t["nome"], t["tipo"], proximo.isoformat()))
            conn.commit()
        except HTTPException:
            conn.rollback()
            raise
        finally:
            conn.close()
        registrar_log("Registro", "tarefas_bezerro", f'Tarefa "{t["nome"]}" concluída para "{t["animal"]}" em {dia:%d/%m/%Y}')
        return {"message": "Tarefa concluída!", "proxima": proximo.isoformat() if proximo else None}

    @app.post("/tarefasBezerro/{tarefa_id}/dispensar")
    def dispensar_tarefa(tarefa_id: int, d: dict):
        t = tarefa_ou_erro(tarefa_id)
        motivo = _texto(d.get("observacoes"), 300, "O motivo é longo demais.")
        if executar("""UPDATE tarefas_bezerro SET status = 'dispensada', responsavel = ?, observacoes = ?
                       WHERE id = ? AND status = 'pendente'""", (_quem(), motivo or None, tarefa_id)) == 0:
            raise HTTPException(status_code=409, detail="Esta tarefa já foi encerrada.")
        registrar_log("Alteração", "tarefas_bezerro", f'Tarefa "{t["nome"]}" dispensada para "{t["animal"]}"')
        return {"message": "Tarefa dispensada."}

    # ---------- Configurações > Avisos > Bezerros ----------
    def protocolo_completo():
        return consultar("""SELECT id, nome, tipo, dias_apos_nascimento, repetir_a_cada_dias, repetir_ate_dias, so_sexo,
                                   ativo, orientacao
                            FROM protocolo_bezerro ORDER BY ativo DESC, dias_apos_nascimento, id""")

    @app.get("/api/avisos/bezerros")
    def obter_avisos_bezerros():
        return {"config": ler_config(), "padrao": dict(esquema_bezerros.CONFIG_PADRAO), "protocolo": protocolo_completo()}

    @app.put("/api/avisos/bezerros/config")
    def salvar_config_avisos(d: dict):
        novos = {}
        for chave, (minimo, maximo) in LIMITES_CONFIG.items():
            if chave in d:
                novos[chave] = _inteiro(d[chave], minimo, maximo, f"O valor deve ficar entre {minimo} e {maximo}.")
        atual = {**ler_config(), **novos}
        if atual["aviso_dias_laranja"] >= atual["aviso_dias_amarelo"]:
            raise HTTPException(status_code=400, detail="O aviso laranja precisa ser mais próximo que o amarelo.")
        conn = conectar()
        try:
            salvar_config(conn.cursor(), novos)
            conn.commit()
        finally:
            conn.close()
        registrar_log("Alteração", "config_avisos", "Configuração dos avisos de bezerros atualizada")
        return {"message": "Configuração salva!", "config": atual}

    def validar_item(d):
        nome = _texto(d.get("nome"), 80, "O nome da tarefa é longo demais.")
        if not nome:
            raise HTTPException(status_code=400, detail="Informe o nome da tarefa.")
        tipo = d.get("tipo") or "geral"
        if tipo not in TIPOS_TAREFA:
            raise HTTPException(status_code=400, detail="Tipo de tarefa inválido.")
        so_sexo = d.get("so_sexo") or "todos"
        if so_sexo not in SEXOS_PROTOCOLO:
            raise HTTPException(status_code=400, detail="Escolha para quais bezerros vale a tarefa.")
        dias = _inteiro(d.get("dias_apos_nascimento"), 0, 1500, "Os dias após o nascimento vão de 0 a 1500.")
        repetir = None
        if d.get("repetir_a_cada_dias") not in (None, ""):
            repetir = _inteiro(d.get("repetir_a_cada_dias"), 1, 365, "Repetir a cada 1 a 365 dias.")
        ate = None
        if repetir and d.get("repetir_ate_dias") not in (None, ""):
            ate = _inteiro(d.get("repetir_ate_dias"), 1, 1500, "Repetir até o dia 1 a 1500 de vida.")
            if ate < dias:
                raise HTTPException(status_code=400, detail="O fim da repetição não pode ser antes do início.")
        return {"nome": nome, "tipo": tipo, "so_sexo": so_sexo, "dias": dias, "repetir": repetir, "ate": ate,
                "orientacao": _texto(d.get("orientacao"), 200, "A orientação é longa demais.") or None}

    @app.post("/api/avisos/bezerros/protocolo", status_code=201)
    def criar_item_protocolo(d: dict):
        v = validar_item(d)
        conn = conectar()
        try:
            cur = conn.cursor()
            cur.execute("""INSERT INTO protocolo_bezerro (nome, tipo, dias_apos_nascimento, repetir_a_cada_dias, repetir_ate_dias,
                                                          so_sexo, ativo, orientacao)
                           VALUES (?, ?, ?, ?, ?, ?, 1, ?)""",
                        (v["nome"], v["tipo"], v["dias"], v["repetir"], v["ate"], v["so_sexo"], v["orientacao"]))
            item_id = cur.lastrowid
            conn.commit()
        finally:
            conn.close()
        registrar_log("Cadastro", "protocolo_bezerro", f'Tarefa "{v["nome"]}" adicionada ao protocolo dos bezerros')
        return {"message": "Tarefa adicionada!", "id": item_id}

    @app.put("/api/avisos/bezerros/protocolo/{item_id}")
    def editar_item_protocolo(item_id: int, d: dict):
        atual = consultar("SELECT * FROM protocolo_bezerro WHERE id = ?", (item_id,))
        if not atual:
            raise HTTPException(status_code=404, detail="Tarefa não encontrada.")
        ativo = atual[0]["ativo"]
        if "ativo" in d:
            if not isinstance(d["ativo"], bool):
                raise HTTPException(status_code=400, detail="O campo 'ativo' deve ser verdadeiro ou falso.")
            ativo = 1 if d["ativo"] else 0
        # só liga/desliga? Então os demais campos ficam como estão
        base = {k: d.get(k, atual[0][k]) for k in ("nome", "tipo", "so_sexo", "dias_apos_nascimento",
                                                    "repetir_a_cada_dias", "repetir_ate_dias", "orientacao")}
        v = validar_item(base)
        executar("""UPDATE protocolo_bezerro SET nome = ?, tipo = ?, dias_apos_nascimento = ?, repetir_a_cada_dias = ?,
                                                 repetir_ate_dias = ?, so_sexo = ?, ativo = ?, orientacao = ? WHERE id = ?""",
                 (v["nome"], v["tipo"], v["dias"], v["repetir"], v["ate"], v["so_sexo"], ativo, v["orientacao"], item_id))
        registrar_log("Alteração", "protocolo_bezerro", f'Tarefa "{v["nome"]}" do protocolo dos bezerros alterada')
        return {"message": "Tarefa salva!"}

    @app.post("/api/avisos/bezerros/restaurar-padrao")
    def restaurar_padrao(d: dict):
        conn = conectar()
        try:
            cur = conn.cursor()
            nomes_padrao = {item[0] for item in esquema_bezerros.PROTOCOLO_PADRAO}
            for nome, tipo, dias, cada, ate, sexo, ativo, orient in esquema_bezerros.PROTOCOLO_PADRAO:
                cur.execute("SELECT id FROM protocolo_bezerro WHERE nome = ? ORDER BY id LIMIT 1", (nome,))
                existente = cur.fetchone()
                if existente:       # reaproveita a linha, para não perder o vínculo com tarefas já geradas
                    cur.execute("""UPDATE protocolo_bezerro SET tipo = ?, dias_apos_nascimento = ?, repetir_a_cada_dias = ?,
                                          repetir_ate_dias = ?, so_sexo = ?, ativo = ?, orientacao = ? WHERE id = ?""",
                                (tipo, dias, cada, ate, sexo, ativo, orient, existente[0]))
                else:
                    cur.execute("""INSERT INTO protocolo_bezerro (nome, tipo, dias_apos_nascimento, repetir_a_cada_dias,
                                          repetir_ate_dias, so_sexo, ativo, orientacao) VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
                                (nome, tipo, dias, cada, ate, sexo, ativo, orient))
            for item in cur.execute("SELECT id, nome FROM protocolo_bezerro").fetchall():
                if item[1] not in nomes_padrao:          # tarefas criadas pelo usuário ficam desativadas, não somem
                    conn.execute("UPDATE protocolo_bezerro SET ativo = 0 WHERE id = ?", (item[0],))
            cur.execute("DELETE FROM config_avisos")
            conn.commit()
        finally:
            conn.close()
        registrar_log("Alteração", "protocolo_bezerro", "Protocolo e avisos dos bezerros restaurados ao padrão")
        return {"message": "Padrão restaurado!"}

    @app.post("/api/avisos/bezerros/aplicar-aos-atuais")
    def aplicar_aos_atuais(d: dict):
        protocolo = consultar("SELECT * FROM protocolo_bezerro WHERE ativo = 1")
        hoje = date.today().isoformat()
        criadas = 0
        conn = conectar()
        try:
            cur = conn.cursor()
            bezerros = cur.execute("""SELECT id, sexo, data_nascimento FROM animais
                                      WHERE ativo = 1 AND mae_id IS NOT NULL AND data_nascimento IS NOT NULL""").fetchall()
            for animal_id, sexo, nascimento in bezerros:
                nasc = date.fromisoformat(nascimento)
                for item in protocolo:
                    if item["so_sexo"] not in ("todos", sexo):
                        continue
                    data_prevista = (nasc + timedelta(days=item["dias_apos_nascimento"])).isoformat()
                    if data_prevista < hoje:             # o que já passou não vira pendência nova
                        continue
                    existe = cur.execute("SELECT 1 FROM tarefas_bezerro WHERE animal_id = ? AND protocolo_id = ?",
                                         (animal_id, item["id"])).fetchone()
                    if existe:
                        continue
                    cur.execute("""INSERT INTO tarefas_bezerro (animal_id, protocolo_id, nome, tipo, data_prevista, status)
                                   VALUES (?, ?, ?, ?, ?, 'pendente')""",
                                (animal_id, item["id"], item["nome"], item["tipo"], data_prevista))
                    criadas += 1
            conn.commit()
        finally:
            conn.close()
        registrar_log("Alteração", "tarefas_bezerro", f"Protocolo aplicado aos bezerros atuais: {criadas} tarefa(s) nova(s)")
        return {"message": f"{criadas} tarefa(s) criada(s) para os bezerros atuais.", "criadas": criadas}
