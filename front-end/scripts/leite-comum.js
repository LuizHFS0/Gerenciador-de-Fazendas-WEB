const API = "http://127.0.0.1:8000";
const $ = id => document.getElementById(id);

async function api(caminho, opcoes = {}) {
  let resposta;
  try {
    resposta = await fetch(API + caminho, {
      headers: { "Content-Type": "application/json" },
      ...opcoes
    });
  } catch {
    throw new Error("Não foi possível conectar ao servidor. Confira se a API está rodando.");
  }
  const dados = await resposta.json().catch(() => ({}));
  if (!resposta.ok) throw new Error(dados.detail || "Erro ao falar com o servidor.");
  return dados;
}

function formatarLitros(valor) {
  return `${Number(valor || 0).toLocaleString("pt-BR", { minimumFractionDigits: 1, maximumFractionDigits: 1 })} L`;
}

function formatarData(iso) {
  if (!iso || typeof iso !== "string") return "-";
  const [ano, mes, dia] = iso.split("-");
  return `${dia}/${mes}/${ano}`;
}

// data de hoje no fuso local (toISOString usaria UTC e viraria o dia à noite)
function hojeISO() {
  const d = new Date();
  const mes = String(d.getMonth() + 1).padStart(2, "0");
  const dia = String(d.getDate()).padStart(2, "0");
  return `${d.getFullYear()}-${mes}-${dia}`;
}

function mostrarMensagem(elemento, texto) {
  elemento.textContent = texto;
  elemento.hidden = false;
}

async function carregarLotes(select, textoPadrao) {
  const dados = await api("/consultarLotes");
  select.innerHTML = "";
  select.add(new Option(textoPadrao, ""));
  dados.lotes.forEach(l => select.add(new Option(l.nome, l.nome)));
}

async function baixarRelatorio(caminho) {
  const resposta = await fetch(API + caminho).catch(() => {
    throw new Error("Não foi possível conectar ao servidor. Confira se a API está rodando.");
  });
  if (!resposta.ok) {
    const erro = await resposta.json().catch(() => ({}));
    throw new Error(erro.detail || "Erro ao gerar o relatório.");
  }
  const url = URL.createObjectURL(await resposta.blob());
  const link = document.createElement("a");
  link.href = url;
  link.download = `relatorio-leite-${hojeISO()}.pdf`;
  document.body.appendChild(link);
  link.click();
  link.remove();
  setTimeout(() => URL.revokeObjectURL(url), 1000);
}

document.querySelectorAll("[data-fechar]").forEach(botao => {
  botao.addEventListener("click", () => $(botao.dataset.fechar).close());
});