"""Aplica no api.py as 3 edições do lote em parceria (o api.py é grande, então é mais seguro editar do que reescrever).

Uso (na pasta do api.py):   python aplicar_api.py
ou apontando o arquivo:     python aplicar_api.py caminho/do/api.py

- Faz uma cópia de segurança em api.py.bak antes de mexer.
- Se algum ponto de edição não for encontrado (ou aparecer mais de uma vez), NÃO altera nada.
- Pode rodar duas vezes: se já estiver aplicado, avisa e sai.
"""
import shutil
import sys
from pathlib import Path

caminho = Path(sys.argv[1] if len(sys.argv) > 1 else "api.py")
if not caminho.is_file():
    sys.exit(f"Arquivo não encontrado: {caminho}")

with open(caminho, encoding="utf-8", newline="") as f:
    texto = f.read()
eol = "\r\n" if "\r\n" in texto else "\n"          # respeita o fim de linha do seu arquivo

if "instalar_rotas_parceria" in texto:
    sys.exit("O api.py já está com o lote em parceria. Nada a fazer.")


def trocar(texto, antigo, novo, nome):
    if texto.count(antigo) != 1:
        sys.exit(f"Não encontrei (ou encontrei mais de uma vez) o ponto de edição '{nome}'. Nada foi alterado.")
    return texto.replace(antigo, novo)


# 1) /dashboard: contagem de animais em parceria
antigo = '"funcionarios_ativos": contar("funcionarios", "WHERE ativo = 1"),'
texto = trocar(texto, antigo,
               antigo + eol + '        "animais_parceria": contar("animais", "WHERE ativo = 1 AND parceria = 1"),',
               "/dashboard")

# 2) /consultarAnimais: devolve o campo parceria
texto = trocar(texto, "a.origem, a.observacoes,", "a.origem, a.observacoes, a.parceria,", "/consultarAnimais")

# 3) instala as rotas do lote em parceria antes da seção de backup
ancora = "# ---------- Utilitários: backup ----------"
bloco = eol.join([
    "# ---------- Lote em parceria ----------",
    "from rotas_parceria import instalar_rotas_parceria",
    "from autorizacao_parceria import checar_permissao_parceria",
    "instalar_rotas_parceria(app, consultar, executar, conectar, registrar_log, checar_permissao_parceria)",
    "", "", ""])
texto = trocar(texto, ancora, bloco + ancora, "instalação das rotas")

shutil.copy2(caminho, caminho.with_name(caminho.name + ".bak"))
with open(caminho, "w", encoding="utf-8", newline="") as f:
    f.write(texto)
print(f"Pronto! 3 edições aplicadas em {caminho} (cópia de segurança: {caminho.name}.bak).")
