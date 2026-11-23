const API = "";   // mesma origem: a API e o front saem do mesmo servidor
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
  return FW_CONFIG.peso(peso);              // kg, arroba ou libra, conforme Configurações
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
  await FW_CONFIG.pronto;
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
    ["Origem", animal.origem || "-"]
  ];
  if (animal.mae_nome) campos.push(["Mãe", animal.mae_nome, `animal.html?id=${animal.mae_id}`]);
  if (animal.pai_nome) campos.push(["Pai", animal.pai_nome, animal.pai_id ? `animal.html?id=${animal.pai_id}` : null]);
  campos.push(["Observações", animal.observacoes || "-"]);
  $("dadosAnimal").innerHTML = "";
  campos.forEach(([rotulo, valor, href]) => {
    const dt = document.createElement("dt");
    const dd = document.createElement("dd");
    dt.textContent = rotulo;
    if (href) {
      const link = document.createElement("a");
      link.href = href;
      link.textContent = valor;
      dd.appendChild(link);
    } else {
      dd.textContent = valor;
    }
    $("dadosAnimal").append(dt, dd);
  });
  $("btnBezerros").hidden = animal.sexo !== "Fêmea";     // só vaca tem módulo de bezerros
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

// ---------- Tarefas do bezerro (avisos de manejo) ----------
let podeGerenciar = false;      // Gerente ou Dono pode dispensar tarefas (o servidor confere de novo)
let tarefaAtual = null;

function hojeIso() {
  const d = new Date();
  d.setMinutes(d.getMinutes() - d.getTimezoneOffset());
  return d.toISOString().slice(0, 10);
}

function seloDaTarefa(t) {
  const selo = document.createElement("span");
  selo.className = "selo";
  if (t.status === "feita") { selo.classList.add("feita"); selo.textContent = `Feita em ${formatarData(t.data_realizada)}`; }
  else if (t.status === "dispensada") { selo.classList.add("dispensada"); selo.textContent = "Dispensada"; }
  else {
    const d = t.dias_restantes;
    if (t.nivel) selo.classList.add(t.nivel);
    selo.textContent = d < 0 ? `Atrasada há ${-d} ${d === -1 ? "dia" : "dias"}` : d === 0 ? "Hoje" : d === 1 ? "Amanhã" : `Em ${d} dias`;
  }
  return selo;
}

function abrirTarefa(t) {
  tarefaAtual = t;
  $("formTarefa").reset();
  $("tarefaTitulo").textContent = `Concluir: ${t.nome}`;
  $("tarData").value = hojeIso();
  $("tarData").max = hojeIso();
  $("tarPesoBox").hidden = t.tipo !== "pesagem";
  $("tarefaOrientacao").hidden = !t.orientacao;
  $("tarefaOrientacao").textContent = t.orientacao || "";
  abrir($("modalTarefa"));
}

function abrirDispensa(t) {
  tarefaAtual = t;
  $("formDispensa").reset();
  abrir($("modalDispensa"));
}

async function carregarTarefas() {
  try {
    const { tarefas } = await api(`/bezerros/tarefas/${id}`);
    $("secTarefas").hidden = tarefas.length === 0;
    const corpo = $("corpoTarefas");
    corpo.innerHTML = "";
    tarefas.forEach(t => {
      const tr = document.createElement("tr");
      const tdNome = document.createElement("td");
      tdNome.textContent = t.nome;
      if (t.orientacao) tdNome.title = t.orientacao;
      const tdData = document.createElement("td");
      tdData.textContent = formatarData(t.data_prevista);
      const tdSelo = document.createElement("td");
      tdSelo.appendChild(seloDaTarefa(t));
      const tdAcoes = document.createElement("td");
      if (t.status === "pendente") {
        tdAcoes.className = "botoes";
        const concluir = document.createElement("button");
        concluir.type = "button";
        concluir.textContent = "Concluir";
        concluir.addEventListener("click", () => abrirTarefa(t));
        tdAcoes.appendChild(concluir);
        if (podeGerenciar) {
          const dispensar = document.createElement("button");
          dispensar.type = "button";
          dispensar.className = "secundario";
          dispensar.textContent = "Dispensar";
          dispensar.addEventListener("click", () => abrirDispensa(t));
          tdAcoes.appendChild(dispensar);
        }
      }
      tr.append(tdNome, tdData, tdSelo, tdAcoes);
      corpo.appendChild(tr);
    });
  } catch (erro) { console.error(erro); }
}

function avisoTarefas(texto) {
  $("msgTarefas").textContent = texto;
  $("msgTarefas").hidden = false;
  setTimeout(() => { $("msgTarefas").hidden = true; }, 6000);
}

$("formTarefa").addEventListener("submit", async e => {
  e.preventDefault();
  const corpo = { data: $("tarData").value, observacoes: $("tarObs").value.trim() };
  if (tarefaAtual.tipo === "pesagem" && $("tarPeso").value !== "") corpo.peso = Number($("tarPeso").value);
  try {
    const r = await api(`/tarefasBezerro/${tarefaAtual.id}/concluir`, { method: "POST", body: JSON.stringify(corpo) });
    $("modalTarefa").close();
    avisoTarefas(r.proxima ? `Tarefa concluída. A próxima ficou para ${formatarData(r.proxima)}.` : "Tarefa concluída.");
    carregarTarefas();
    carregarAnimal();                                   // o peso atual pode ter mudado
    if (tarefaAtual.tipo === "vacina") carregarVacinas();
    if (tarefaAtual.tipo === "pesagem") carregarPesagens();
  } catch (erro) { mostrarErro($("modalTarefa"), erro.message); }
});

$("formDispensa").addEventListener("submit", async e => {
  e.preventDefault();
  try {
    await api(`/tarefasBezerro/${tarefaAtual.id}/dispensar`, { method: "POST", body: JSON.stringify({ observacoes: $("dispObs").value.trim() }) });
    $("modalDispensa").close();
    avisoTarefas("Tarefa dispensada.");
    carregarTarefas();
  } catch (erro) { mostrarErro($("modalDispensa"), erro.message); }
});

$("btnBezerros").addEventListener("click", () => { location.href = `bezerros.html?id=${id}`; });

carregarAnimal();
carregarPesagens();
carregarVacinas();
(async () => {
  try { podeGerenciar = (await api("/api/perfil")).pode_excluir === true; } catch (_) { podeGerenciar = false; }
  carregarTarefas();
})();
