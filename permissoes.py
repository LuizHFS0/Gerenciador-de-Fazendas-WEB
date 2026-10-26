"""Quem pode o quê dentro de uma fazenda. Aplicado no SERVIDOR, por rota, antes de a rota rodar.

Perfis: funcionario (1) < gerente (2) < dono (3).
- Funcionário: consulta, registra e move. Não exclui nada ("excluir" = marcar ativo = 0) e não vê funcionários.
- Gerente: tudo isso, mais excluir e a área de funcionários. Não gerencia usuários, backup nem dados da fazenda.
- Dono: tudo.
Rota que não está na lista abaixo exige Gerente (falha fechada: rota nova não vaza para o Funcionário).
"""
import re
import unicodedata

NIVEIS = {"funcionario": 1, "gerente": 2, "dono": 3}


def sem_acento(texto):
    return unicodedata.normalize("NFD", texto or "").encode("ascii", "ignore").decode("ascii")


def nivel_efetivo(texto):
    """Normaliza o valor guardado em usuarios.nivel_acesso. Valor desconhecido = menor privilégio."""
    t = sem_acento(texto).strip().lower()
    return t if t in NIVEIS else "funcionario"


def _regra(metodos, padrao, minimo):
    return frozenset(metodos.split()), re.compile(padrao), NIVEIS[minimo]


POLITICA = [
    # só o Dono
    _regra("GET", r"^/backup$", "dono"),
    _regra("GET", r"^/(detalhesFazenda|ultimosLogs)$", "dono"),
    _regra("GET POST PUT DELETE", r"^/api/usuarios(/.*)?$", "dono"),
    # funcionários (CPF, telefone...) e acesso deles ao sistema: Gerente ou Dono
    _regra("GET POST PUT DELETE",
           r"^/(consultarFuncionarios|consultarFuncionario/\d+|cadastrarFuncionario|movimentacoesFuncionario/\d+)$", "gerente"),
    _regra("GET POST PUT DELETE", r"^/api/funcionarios/\d+/acesso$", "gerente"),
    # excluir (marcar ativo = 0) e editar a estrutura: Gerente ou Dono
    _regra("DELETE", r"^/(excluirAnimal|excluirMaquina|excluirItem|excluirLote)/\d+$", "gerente"),
    _regra("PUT", r"^/editarLote/\d+$", "gerente"),
    # dia a dia: qualquer usuário logado
    _regra("GET", r"^/(dashboard|movimentacoesDashboard|consultarAnimais|consultarAnimal/\d+|pesagens/\d+|vacinas/\d+"
                  r"|consultarLotes|consultarMaquinas|consultarMaquina/\d+|manutencoes/\d+|consultarEstoque"
                  r"|consultarItem/\d+|movimentacoes/\d+|alertas|gerenciarLotes|dashboardLeite|vacasDoLote/[^/]+"
                  r"|consultarProducaoLeite|relatorioLeite)$", "funcionario"),
    _regra("POST", r"^/(cadastrarAnimal|cadastrarMaquina|cadastrarItem|cadastrarLote|registrarProducaoLeite"
                   r"|pesagens/\d+|vacinas/\d+|manutencoes/\d+|movimentacoes/\d+)$", "funcionario"),
    _regra("PUT", r"^/(alterarLote|alterarStatus|alterarStatusMaquina)/\d+$", "funcionario"),
]

# páginas restritas (pelo nome do arquivo)
PAGINAS = {"fazenda.html": "dono", "usuarios.html": "dono", "funcionarios.html": "gerente", "funcionario.html": "gerente"}


def permitido(nivel, metodo, caminho):
    n = NIVEIS[nivel_efetivo(nivel)]
    metodo = "GET" if metodo == "HEAD" else metodo
    if caminho == "/" or caminho.startswith("/front-end/"):
        minimo = PAGINAS.get(caminho.rsplit("/", 1)[-1])
        return minimo is None or n >= NIVEIS[minimo]
    if caminho.startswith(("/api/auth/", "/api/perfil")):
        return True                                           # login, troca de senha, menu do usuário
    for metodos, padrao, minimo in POLITICA:
        if metodo in metodos and padrao.match(caminho):
            return n >= minimo
    return n >= NIVEIS["gerente"]                              # rota desconhecida


def pode_excluir(nivel):
    return NIVEIS[nivel_efetivo(nivel)] >= NIVEIS["gerente"]


def paginas_bloqueadas(nivel):
    n = NIVEIS[nivel_efetivo(nivel)]
    return sorted(nome for nome, minimo in PAGINAS.items() if n < NIVEIS[minimo])
