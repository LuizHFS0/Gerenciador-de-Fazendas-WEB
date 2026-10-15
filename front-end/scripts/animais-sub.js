const API = "http://127.0.0.1:8000";
const id = new URLSearchParams(location.search).get("id");
if (!id) location.href = "animais.html";

let animal = null;

const $ = seletor => document.getElementById(seletor);

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

function formatarPeso(peso) {
  if (peso === null || peso === undefined || peso === "") return "-";
  return `${Number(peso).toLocaleString("pt-BR")} kg`;
}

function preencherTabela(corpo, linhas, colunas) {
  corpo.innerHTML = "";
  if (linhas.length === 0) {
    corpo.innerHTML = `<tr><td class="vazio" colspan="${colunas}">Nenhum registro ainda.</td></tr>`;
    return;
  }
  linhas.forEach(valores => {
    const tr = document.createElement("tr");
    valores.forEach(v => {
      const td = document.createElement("td");
      td.textContent = v;
      tr.appendChild(td);
    });
    corpo.appendChild(tr);
  });
}

// ---------- Carregar dados ----------
async function carregarAnimal() {
  try {
    animal = await api(`/consultarAnimal/${id}`);
  } catch (erro) {
    $("tituloAnimal").textContent = "Animal não encontrado";
    $("subAnimal").textContent = erro.message;
    return;
  }

  $("tituloAnimal").textContent = animal.nome;
  $("subAnimal").textContent = `Brinco ${animal.brinco}`;
  document.querySelectorAll(".nome-modal").forEach(p => p.textContent = animal.nome);

  const campos = [
    ["Brinco", animal.brinco], ["Tipo", animal.tipo], ["Sexo", animal.sexo],
    ["Raça", animal.raca || "-"], ["Peso atual", formatarPeso(animal.peso_atual)],
    ["Data de nascimento", formatarData(animal.data_nascimento)],
    ["Status", animal.status], ["Lote", animal.lote || "-"],
    ["Origem", animal.origem || "-"], ["Observações", animal.observacoes || "-"]
  ];
  $("dadosAnimal").innerHTML = "";
  campos.forEach(([rotulo, valor]) => {
    const dt = document.createElement("dt");
    const dd = document.createElement("dd");
    dt.textContent = rotulo;
    dd.textContent = valor;
    $("dadosAnimal").append(dt, dd);
  });
}

async function carregarPesagens() {
  try {
    const dados = await api(`/pesagens/${id}`);
    preencherTabela($("corpoPesagens"),
      dados.pesagens.map(p => [formatarData(p.data_pesagem), formatarPeso(p.peso), p.observacoes || "-"]), 3);
  } catch (erro) { console.error(erro); }
}

async function carregarVacinas() {
  try {
    const dados = await api(`/vacinas/${id}`);
    preencherTabela($("corpoVacinas"),
      dados.vacinas.map(v => [v.vacina, formatarData(v.data_aplicacao), formatarData(v.proxima_dose),
                              v.responsavel || "-", v.observacoes || "-"]), 5);
  } catch (erro) { console.error(erro); }
}

// ---------- Modais ----------
function abrir(modal) {
  modal.querySelector(".erro").hidden = true;
  modal.showModal();
}

function mostrarErro(modal, mensagem) {
  const p = modal.querySelector(".erro");
  p.textContent = mensagem;
  p.hidden = false;
}

document.querySelectorAll("[data-fechar]").forEach(botao => {
  botao.addEventListener("click", () => $(botao.dataset.fechar).close());
});

// Mudar de lote
$("btnLote").addEventListener("click", async () => {
  try {
    const dados = await api("/consultarLotes");
    $("novoLote").innerHTML = "";
    dados.lotes.forEach(l => {
      const opcao = new Option(l.nome, l.nome);
      opcao.selected = l.nome === animal.lote;
      $("novoLote").add(opcao);
    });
  } catch (erro) { console.error(erro); }
  abrir($("modalLote"));
});

$("okLote").addEventListener("click", async () => {
  try {
    await api(`/alterarLote/${id}`, { method: "PUT", body: JSON.stringify({ lote: $("novoLote").value }) });
    $("modalLote").close();
    carregarAnimal();
  } catch (erro) { mostrarErro($("modalLote"), erro.message); }
});

// Mudar status
$("btnStatus").addEventListener("click", () => {
  $("novoStatus").value = animal.status;
  abrir($("modalStatus"));
});

$("okStatus").addEventListener("click", async () => {
  try {
    await api(`/alterarStatus/${id}`, { method: "PUT", body: JSON.stringify({ status: $("novoStatus").value }) });
    $("modalStatus").close();
    carregarAnimal();
  } catch (erro) { mostrarErro($("modalStatus"), erro.message); }
});

// Pesagem
$("btnPesagem").addEventListener("click", () => {
  $("formPesagem").reset();
  $("pesData").value = new Date().toISOString().slice(0, 10);
  abrir($("modalPesagem"));
});

$("formPesagem").addEventListener("submit", async e => {
  e.preventDefault();
  try {
    await api(`/pesagens/${id}`, {
      method: "POST",
      body: JSON.stringify({
        data_pesagem: $("pesData").value,
        peso: Number($("pesPeso").value),
        observacoes: $("pesObs").value.trim()
      })
    });
    $("modalPesagem").close();
    carregarPesagens();
    carregarAnimal();   // o peso atual pode ter mudado
  } catch (erro) { mostrarErro($("modalPesagem"), erro.message); }
});

// Vacina
$("btnVacina").addEventListener("click", () => {
  $("formVacina").reset();
  abrir($("modalVacina"));
});

$("formVacina").addEventListener("submit", async e => {
  e.preventDefault();
  try {
    await api(`/vacinas/${id}`, {
      method: "POST",
      body: JSON.stringify({
        vacina: $("vacNome").value.trim(),
        data_aplicacao: $("vacData").value,
        proxima_dose: $("vacProx").value || null,
        responsavel: $("vacResp").value.trim(),
        observacoes: $("vacObs").value.trim()
      })
    });
    $("modalVacina").close();
    carregarVacinas();
  } catch (erro) { mostrarErro($("modalVacina"), erro.message); }
});

carregarAnimal();
carregarPesagens();
carregarVacinas();