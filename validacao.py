"""Validação central dos dados que chegam nas rotas de escrita.

Roda ANTES da rota, no servidor: tipo, tamanho, faixa e formato de cada campo. Campo desconhecido é ignorado
(não quebra tela antiga); campo conhecido com valor ruim recebe 400 com mensagem clara (antes dava erro 500).
"""
import math
import re
from datetime import date

STATUS_ANIMAL = ("Ativo", "Tratamento", "Seca", "Prenha", "Abate")
STATUS_MAQUINA = ("Ativo", "Manutenção", "Encostado")
MOTIVOS_BAIXA = ("Venda", "Abate", "Morte")


class ErroValidacao(Exception):
    pass


def texto(maximo, obrigatorio=False):
    return ("txt", maximo, obrigatorio)


def numero(minimo=None, maximo=None, obrigatorio=False, maior_que=None):
    return ("num", (minimo, maximo, maior_que), obrigatorio)


def inteiro(minimo, maximo, obrigatorio=False):
    return ("int", (minimo, maximo), obrigatorio)


def data(obrigatorio=False):
    return ("data", None, obrigatorio)


def opcoes(valores, obrigatorio=False):
    return ("enum", tuple(valores), obrigatorio)


def lista(maximo, obrigatorio=False):
    return ("lista", maximo, obrigatorio)


def booleano(obrigatorio=False):
    return ("bool", None, obrigatorio)


def _vazio(v):
    return v is None or (isinstance(v, str) and v.strip() == "")


def _numero(v):
    if isinstance(v, bool):
        raise ErroValidacao("deve ser um número")
    try:
        n = float(v)
    except (TypeError, ValueError):
        raise ErroValidacao("deve ser um número")
    if not math.isfinite(n):
        raise ErroValidacao("deve ser um número finito")
    return n


def _checar(campo, valor, tipo, param):
    if tipo == "txt":
        if not isinstance(valor, (str, int, float)) or isinstance(valor, bool):
            raise ErroValidacao("deve ser um texto")
        if len(str(valor)) > param:
            raise ErroValidacao(f"deve ter no máximo {param} caracteres")
    elif tipo in ("num", "int"):
        n = _numero(valor)
        if tipo == "int" and n != int(n):
            raise ErroValidacao("deve ser um número inteiro")
        minimo, maximo = param[0], param[1]
        if minimo is not None and n < minimo:
            raise ErroValidacao(f"não pode ser menor que {minimo:g}")
        if maximo is not None and n > maximo:
            raise ErroValidacao(f"não pode ser maior que {maximo:g}")
        if tipo == "num" and param[2] is not None and n <= param[2]:
            raise ErroValidacao(f"deve ser maior que {param[2]:g}")
    elif tipo == "data":
        if not isinstance(valor, str) or not re.fullmatch(r"\d{4}-\d{2}-\d{2}", valor):
            raise ErroValidacao("deve ser uma data no formato AAAA-MM-DD")
        try:
            date.fromisoformat(valor)
        except ValueError:
            raise ErroValidacao("não é uma data válida")
    elif tipo == "enum":
        if valor not in param:
            raise ErroValidacao("valor não permitido (use: " + ", ".join(param) + ")")
    elif tipo == "lista":
        if not isinstance(valor, list):
            raise ErroValidacao("deve ser uma lista")
        if len(valor) > param:
            raise ErroValidacao(f"aceita no máximo {param} itens")
    elif tipo == "bool":
        if not isinstance(valor, bool):
            raise ErroValidacao("deve ser verdadeiro ou falso")


def validar(esquema, corpo):
    if not isinstance(corpo, dict):
        raise ErroValidacao("O corpo da requisição deve ser um objeto JSON.")
    for campo, (tipo, param, obrigatorio) in esquema.items():
        valor = corpo.get(campo)
        if _vazio(valor):
            if obrigatorio:
                raise ErroValidacao(f"O campo '{campo}' é obrigatório.")
            continue
        try:
            _checar(campo, valor, tipo, param)
        except ErroValidacao as erro:
            raise ErroValidacao(f"Campo '{campo}' inválido: {erro}.")


_ANIMAL = {"brinco": texto(30, True), "nome": texto(80, True), "tipo": opcoes(("Corte", "Leite", "Exposição"), True),
           "sexo": opcoes(("Macho", "Fêmea"), True), "status": opcoes(STATUS_ANIMAL, True), "lote": texto(50, True),
           "raca": texto(80), "origem": texto(80), "observacoes": texto(1000),
           "peso_atual": numero(0, 5000), "data_nascimento": data()}
_MAQUINA = {"nome": texto(80, True), "tipo": texto(60), "modelo": texto(60), "fabricante": texto(60), "placa": texto(15),
            "status": texto(30), "observacoes": texto(1000), "ano": inteiro(1900, 2100), "horas_uso": numero(0, 10_000_000)}
_ITEM = {"nome": texto(80, True), "categoria": texto(60), "unidade": texto(30), "localizacao": texto(80),
         "observacoes": texto(1000), "quantidade": numero(0, 1_000_000_000), "estoque_minimo": numero(0, 1_000_000_000)}
_MOVIMENTACAO = {"tipo": opcoes(("Entrada", "Saída"), True), "quantidade": numero(maior_que=0, maximo=1_000_000_000, obrigatorio=True),
                 "data_movimentacao": data(True), "responsavel": texto(80), "motivo": texto(200),
                 "observacoes": texto(500), "lote": texto(50)}
_LOTE = {"nome": texto(50, True), "tamanho": numero(0, 1_000_000), "localizacao": texto(100), "descricao": texto(500)}

_CONFIGURACOES = {"nome_fazenda": texto(120, True), "dono": texto(100), "endereco": texto(200), "telefone": texto(30),
                  "email": texto(120), "tamanho": numero(0, 10_000_000), "data_fundacao": data(),
                  "unidade_peso": texto(20), "unidade_area": texto(20),
                  "notif_vacinas": booleano(), "notif_manutencoes": booleano(), "notif_estoque": booleano(),
                  "alerta_dias": inteiro(1, 90), "relatorio_periodo_dias": inteiro(1, 365), "relatorio_logo": booleano()}

# (métodos, padrão do caminho, esquema)
ESQUEMAS = [
    ({"POST"}, r"^/cadastrarAnimal$", _ANIMAL),
    ({"PUT"}, r"^/alterarLote/\d+$", {"lote": texto(50, True)}),
    ({"PUT"}, r"^/alterarStatus/\d+$", {"status": opcoes(STATUS_ANIMAL, True)}),
    ({"POST"}, r"^/pesagens/\d+$", {"data_pesagem": data(True), "peso": numero(0, 5000, True), "observacoes": texto(500)}),
    ({"POST"}, r"^/vacinas/\d+$", {"vacina": texto(80, True), "data_aplicacao": data(True), "proxima_dose": data(),
                                  "responsavel": texto(80), "observacoes": texto(500)}),
    ({"POST"}, r"^/cadastrarMaquina$", _MAQUINA),
    ({"PUT"}, r"^/alterarStatusMaquina/\d+$", {"status": opcoes(STATUS_MAQUINA, True)}),
    ({"POST"}, r"^/manutencoes/\d+$", {"tipo_manutencao": texto(60, True), "data_manutencao": data(True), "proxima_manutencao": data(),
                                      "descricao": texto(1000), "responsavel": texto(80)}),
    ({"POST"}, r"^/cadastrarItem$", _ITEM),
    ({"POST"}, r"^/movimentacoes/\d+$", _MOVIMENTACAO),
    ({"POST"}, r"^/cadastrarLote$", _LOTE),
    ({"PUT"}, r"^/editarLote/\d+$", _LOTE),
    ({"POST"}, r"^/cadastrarFuncionario$", {"nome": texto(100, True), "cpf": texto(14), "telefone": texto(20), "endereco": texto(200),
                                           "cargo": texto(60), "data_admissao": data(), "observacoes": texto(500)}),
    ({"POST"}, r"^/registrarProducaoLeite$", {"data": data(True), "responsavel": texto(80, True), "lote": texto(50, True),
                                             "medicoes": lista(500, True)}),
    ({"POST"}, r"^/api/auth/login$", {"fazenda": texto(60), "usuario": texto(60), "senha": texto(200)}),
    ({"POST"}, r"^/api/auth/trocar-senha$", {"senha_atual": texto(200), "nova_senha": texto(200)}),
    ({"POST"}, r"^/api/usuarios$", {"nome": texto(100, True), "usuario": texto(40, True), "nivel": texto(20, True), "cargo": texto(60)}),
    ({"PUT"}, r"^/api/usuarios/\d+/ativo$", {"ativo": booleano()}),
    ({"PUT"}, r"^/api/usuarios/\d+/nivel$", {"nivel": texto(20, True)}),
    ({"PUT"}, r"^/api/configuracoes$", _CONFIGURACOES),
    ({"POST"}, r"^/baixaAnimal/\d+$", {"motivo": opcoes(MOTIVOS_BAIXA, True), "data": data(True), "observacoes": texto(500)}),
]
_COMPILADOS = [(m, re.compile(p), e) for m, p, e in ESQUEMAS]


def esquema_para(metodo, caminho):
    for metodos, padrao, esquema in _COMPILADOS:
        if metodo in metodos and padrao.match(caminho):
            return esquema
    return None
