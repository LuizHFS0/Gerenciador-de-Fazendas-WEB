
import sqlite3
import secrets
import shutil
from pathlib import Path
from datetime import datetime

from senhas import gerar_hash, gerar_senha_temporaria

# Identificação da fazenda
fazenda_id = input("ID da fazenda: ").strip()
usuario = input("Login do usuário: ").strip()

# Localiza o banco
banco = Path(__file__).parent / "dados" / "fazendas" / f"{fazenda_id}.db"

if not banco.exists():
    print("Banco da fazenda não encontrado!")
    raise SystemExit

# Cria backup antes de alterar
backup = banco.with_name(
    f"{banco.stem}_backup_{datetime.now():%Y%m%d_%H%M%S}.db"
)
shutil.copy2(banco, backup)

conn = sqlite3.connect(banco)
cursor = conn.cursor()

# Procura o usuário
cursor.execute(
    "SELECT id, nome, usuario FROM usuarios WHERE usuario = ?",
    (usuario,)
)

dados = cursor.fetchone()

if not dados:
    print("Usuário não encontrado!")
    conn.close()
    raise SystemExit

id_usuario, nome, login = dados

# Gera nova senha temporária
nova_senha = gerar_senha_temporaria()

# Atualiza senha utilizando o mesmo sistema de hash
cursor.execute("""
    UPDATE usuarios
    SET senha = ?, trocar_senha = 1
    WHERE id = ?
""", (gerar_hash(nova_senha), id_usuario))

# Encerra sessões anteriores do usuário
cursor.execute(
    "DELETE FROM sessoes WHERE usuario_id = ?",
    (id_usuario,)
)

conn.commit()
conn.close()

print("\nSenha redefinida com sucesso!")
print("Nome:", nome)
print("Login:", login)
print("Nova senha temporária:", nova_senha)
print("O usuário deverá trocar a senha no próximo acesso.")
print("Backup criado em:", backup)
