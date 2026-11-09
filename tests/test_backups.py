import json
import sqlite3

import backups
import caminhos


def _criar_banco(caminho, valor):
    caminho.parent.mkdir(parents=True, exist_ok=True)
    with sqlite3.connect(caminho) as conn:
        conn.execute("CREATE TABLE exemplo (valor TEXT)")
        conn.execute("INSERT INTO exemplo (valor) VALUES (?)", (valor,))


def test_copiar_consistente_preserva_dados(tmp_path):
    origem = tmp_path / "origem.db"
    destino = tmp_path / "copia" / "destino.db"
    _criar_banco(origem, "registro importante")

    backups.copiar_consistente(origem, destino)

    assert backups.integridade(destino) == "ok"
    with sqlite3.connect(destino) as conn:
        assert conn.execute("SELECT valor FROM exemplo").fetchone()[0] == "registro importante"


def test_backup_inclui_bancos_de_fazendas_e_manifesto(tmp_path):
    pasta_dados = tmp_path / "dados"
    caminhos.configurar(pasta_dados)
    _criar_banco(pasta_dados / "admin.db", "admin")
    _criar_banco(pasta_dados / "superadmin.db", "superadmin")
    _criar_banco(pasta_dados / "fazendas" / "1.db", "fazenda 1")

    destino = backups.backup()

    manifesto = json.loads((destino / "manifest.json").read_text(encoding="utf-8"))
    nomes = {item["arquivo"] for item in manifesto["arquivos"]}
    assert nomes == {"admin.db", "superadmin.db", "fazendas/1.db"}
    assert all(item["integridade"] == "ok" for item in manifesto["arquivos"])
    assert (destino / "fazendas" / "1.db").is_file()
