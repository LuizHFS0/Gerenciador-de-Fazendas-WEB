"""Liga o menu do usuário em todas as páginas internas do front-end.

Uso (na pasta do projeto, onde fica o api.py):
    python adicionar_menu.py            # procura em ./front-end
    python adicionar_menu.py caminho/do/front-end

O que faz: em cada .html, coloca <script src=".../scripts/sessao.js"></script> antes do primeiro
<script src=...> da página (ou antes de </body>). Não mexe no login.html nem no trocar-senha.html,
nem nas páginas que já têm o menu. Guarda uma cópia de cada página alterada em backup-html/.
Pode rodar de novo sem problema.
"""
import os
import re
import shutil
import sys
from pathlib import Path

IGNORAR = {"login.html", "trocar-senha.html"}
PRIMEIRO_SCRIPT = re.compile(r"<script\b[^>]*\bsrc=", re.I)


def tag_para(pagina, scripts):
    rel = os.path.relpath(scripts / "sessao.js", pagina.parent).replace(os.sep, "/")
    return f'<script src="{rel}"></script>'


def processar(pagina, scripts, backup):
    texto = pagina.read_text(encoding="utf-8")
    if "sessao.js" in texto:
        return "já tinha"
    tag = tag_para(pagina, scripts)
    achou = PRIMEIRO_SCRIPT.search(texto)
    if achou:
        inicio = texto.rfind("\n", 0, achou.start()) + 1
        antes = texto[inicio:achou.start()]
        if antes.strip() == "":                      # o script está sozinho na linha: entra uma linha nova antes
            novo = texto[:inicio] + f"{antes}{tag}\n" + texto[inicio:]
        else:                                        # página escrita numa linha só: entra logo antes do script
            novo = texto[:achou.start()] + tag + texto[achou.start():]
    elif re.search(r"</body>", texto, re.I):
        novo = re.sub(r"(</body>)", f"  {tag}\n\\1", texto, count=1, flags=re.I)
    else:
        return "sem </body> nem scripts: não alterei"
    destino = backup / pagina.relative_to(scripts.parent)
    destino.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(pagina, destino)
    pagina.write_text(novo, encoding="utf-8")
    aviso = "" if 'class="usuario"' in texto or "class='usuario'" in texto else " (atenção: esta página não tem o bloco .usuario, então o menu não vai aparecer nela)"
    return "menu ligado" + aviso


def principal():
    front = Path(sys.argv[1] if len(sys.argv) > 1 else "front-end")
    scripts = front / "scripts"
    if not front.is_dir():
        raise SystemExit(f"Não encontrei a pasta {front}. Rode na pasta do projeto ou passe o caminho.")
    if not (scripts / "sessao.js").exists():
        raise SystemExit(f"Falta {scripts / 'sessao.js'}. Copie o sessao.js para essa pasta primeiro.")
    backup = Path("backup-html")
    resumo = {"menu ligado": 0, "já tinha": 0, "outros": 0}
    for pagina in sorted(front.rglob("*.html")):
        if pagina.name in IGNORAR:
            continue
        resultado = processar(pagina, scripts, backup)
        chave = "menu ligado" if resultado.startswith("menu ligado") else "já tinha" if resultado == "já tinha" else "outros"
        resumo[chave] += 1
        print(f"{resultado:<22} {pagina}")
    print(f"\n{resumo['menu ligado']} página(s) alterada(s), {resumo['já tinha']} já tinham o menu, {resumo['outros']} com aviso.")
    if resumo["menu ligado"]:
        print("Cópias das páginas originais em backup-html/. Recarregue o navegador (Ctrl+F5).")


if __name__ == "__main__":
    principal()