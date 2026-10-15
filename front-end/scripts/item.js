const API = "http://127.0.0.1:8000";
const id = new URLSearchParams(location.search).get("id");
if (!id) location.href = "estoque.html";

let item = null;
const $ = elemento => document.getElementById(elemento);

async function api(caminho, opcoes = {}) {
  const resposta = await fetch(API + caminho, {
    headers: { "Content-Type": "application/json" },
    ...opcoes
  });
  const dados = await resposta.json().catch(() => ({}));
  if (!resposta.ok) throw new Error(dados.detail || "Erro ao falar com o servidor.");
  return dados;
}

function formatarData(iso) {
  if (!iso || typeof iso !== "string") return "-";
  const [ano, mes, dia] = iso.split("-");
  return `${dia}/${mes}/${ano}`;
}

function formatarNumero(n) {
  if (n === null || n === undefined || n === "") return "-";
  return Number(n).toLocaleString("pt-BR");
}

// ---------- Carregar dados ----------
async function carregarItem() {
  try {
    item = await api(`/consultarItem/${id}`);
  } catch (erro) {
    $("tituloItem").textContent = "Item não encontrado";
    $("subItem").textContent = erro.message;
    return;
  }

  $("tituloItem").textContent = item.nome;
  $("subItem").textContent = item.categoria || "";
  document.querySelectorAll(".nome-modal").forEach(p => p.textContent = item.nome);

  const unidade = item.unidade || "";
  const baixo = Number(item.quantidade) <= Number(item.estoque_minimo);
  const campos = [
    ["Categoria", item.categoria || "-"],
    ["Unidade", unidade || "-"],
    ["Quantidade atual", `${formatarNumero(item.quantidade)} ${unidade}${baixo ? " (no mínimo ou abaixo)" : ""}`],
    ["Estoque mínimo", `${formatarNumero(item.estoque_minimo)} ${unidade}`],
    ["Localização", item.localizacao || "-"],
    ["Observações", item.observacoes || "-"]
  ];
  $("dadosItem").innerHTML = "";
  campos.forEach(([rotulo, valor]) => {
    const dt = document.createElement("dt");
    const dd = document.createElement("dd");
    dt.textContent = rotulo;
    dd.textContent = valor;
    $("dadosItem").append(dt, dd);
  });
}

async function carregarMovimentacoes() {
  const corpo = $("corpoMovimentacoes");
  try {
    const dados = await api(`/movimentacoes/${id}`);
    corpo.innerHTML = "";
    if (dados.movimentacoes.length === 0) {
      corpo.innerHTML = '<tr><td class="vazio" colspan="7">Nenhuma movimentação registrada.</td></tr>';
      return;
    }
    dados.movimentacoes.forEach(m => {
      const tr = document.createElement("tr");
      [formatarData(m.data_movimentacao), m.tipo, formatarNumero(m.quantidade), m.lote || "-",
       m.responsavel || "-", m.motivo || "-", m.observacoes || "-"].forEach(valor => {
        const td = document.createElement("td");
        td.textContent = valor;
        tr.appendChild(td);
      });
      corpo.appendChild(tr);
    });
  } catch (erro) { console.error(erro); }
}

// ---------- Modal de movimentação ----------
function mostrarErro(modal, mensagem) {
  const p = modal.querySelector(".erro");
  p.textContent = mensagem;
  p.hidden = false;
}

document.querySelectorAll("[data-fechar]").forEach(botao => {
  botao.addEventListener("click", () => $(botao.dataset.fechar).close());
});

$("btnMovimentacao").addEventListener("click", async () => {
  $("formMovimentacao").reset();
  $("movData").value = new Date().toISOString().slice(0, 10);

  // lotes disponíveis para o destino
  try {
    const dados = await api("/consultarLotes");
    $("movLote").innerHTML = '<option value="">Nenhum</option>';
    dados.lotes.forEach(l => $("movLote").add(new Option(l.nome, l.nome)));
  } catch (erro) { console.error(erro); }

  $("modalMovimentacao").querySelector(".erro").hidden = true;
  $("modalMovimentacao").showModal();
});

$("formMovimentacao").addEventListener("submit", async e => {
  e.preventDefault();
  try {
    await api(`/movimentacoes/${id}`, {
      method: "POST",
      body: JSON.stringify({
        tipo: $("movTipo").value,
        quantidade: Number($("movQtd").value),
        data_movimentacao: $("movData").value,
        lote: $("movLote").value || null,
        responsavel: $("movResp").value.trim(),
        motivo: $("movMotivo").value.trim(),
        observacoes: $("movObs").value.trim()
      })
    });
    $("modalMovimentacao").close();
    carregarMovimentacoes();
    carregarItem();      // a quantidade atual mudou
  } catch (erro) { mostrarErro($("modalMovimentacao"), erro.message); }
});

carregarItem();
carregarMovimentacoes();