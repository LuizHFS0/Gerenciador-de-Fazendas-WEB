const API = "http://127.0.0.1:8000";
const botao = document.getElementById("btnBackup");
const msg = document.getElementById("msgBackup");

botao.addEventListener("click", async () => {
  botao.disabled = true;
  msg.hidden = true;
  try {
    const resposta = await fetch(`${API}/backup`);
    if (!resposta.ok) throw new Error(`Erro ${resposta.status}`);

    const blob = await resposta.blob();
    const agora = new Date();
    const pad = n => String(n).padStart(2, "0");
    const nome = `backup-${agora.getFullYear()}-${pad(agora.getMonth() + 1)}-${pad(agora.getDate())}_${pad(agora.getHours())}-${pad(agora.getMinutes())}.db`;

    const link = document.createElement("a");
    link.href = URL.createObjectURL(blob);
    link.download = nome;
    link.click();
    URL.revokeObjectURL(link.href);
  } catch (erro) {
    msg.textContent = "Não foi possível gerar o backup: " + erro.message;
    msg.hidden = false;
  } finally {
    botao.disabled = false;
  }
});