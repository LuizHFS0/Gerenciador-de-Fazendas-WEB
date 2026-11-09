const animais = [];

async function carregarAnimais() {
  try {
    await FW_CONFIG.pronto;
    const resposta = await fetch("/consultarAnimais");
    if (!resposta.ok) throw new Error(`Erro ${resposta.status}`);

    const dados = await resposta.json();
    console.log("Primeiro animal da API:", dados.animais[0]);   // para conferir os nomes

    animais.length = 0;
    animais.push(...dados.animais.map(a => ({
      id: a.id,
      brinco: a.brinco,
      nome: a.nome,
      tipo: a.tipo,
      sexo: a.sexo,
      peso: a.peso_atual ?? a.peso,
      raca: a.raca,
      origem: a.origem,
      nascimento: a.data_nascimento ?? a.nascimento,
      status: a.status,
      lote: a.lote ?? a.lote_id,
      observacoes: a.observacoes
    })));
  } catch (erro) {
    console.error("Falha ao carregar animais:", erro);
  }
  desenharTabela();
}


let selecionadoId = null;

const corpoTabela = document.getElementById("corpoTabela");
const campoBusca = document.getElementById("busca");
const modalCadastro = document.getElementById("modalCadastro");
const formCadastro = document.getElementById("formCadastro");
const erroCadastro = document.getElementById("erroCadastro");
const modalErro = document.getElementById("modalErro");

function formatarData(iso) {
  if (!iso || typeof iso !== "string") return "-";
  const [ano, mes, dia] = iso.split("-");
  return `${dia}/${mes}/${ano}`;
}

function formatarPeso(peso) {
  if (peso === null || peso === undefined || peso === "") return "-";
  return FW_CONFIG.peso(peso);              // kg, arroba ou libra, conforme Configurações
}

function normalizar(texto) {
  return texto.toLowerCase().normalize("NFD").replace(/[\u0300-\u036f]/g, "");
}

// ---------- Tabela ----------
function desenharTabela() {
  const termo = normalizar(campoBusca.value.trim());
  const lista = animais.filter(a =>
    !termo || normalizar(`${a.nome} ${a.brinco} ${a.raca} ${a.lote} ${a.status}`).includes(termo)
  );

  corpoTabela.innerHTML = "";

  if (lista.length === 0) {
    const tr = document.createElement("tr");
    tr.innerHTML = '<td class="vazio" colspan="9">Nenhum animal encontrado.</td>';
    corpoTabela.appendChild(tr);
    return;
  }

  lista.forEach(a => {
    const tr = document.createElement("tr");
    tr.dataset.id = a.id;
    if (a.id === selecionadoId) tr.classList.add("selecionada");

    [a.id, a.brinco, a.nome, a.tipo, a.sexo, formatarPeso(a.peso), formatarData(a.nascimento), a.status, a.lote]
      .forEach(valor => {
        const td = document.createElement("td");
        td.textContent = valor;
        tr.appendChild(td);
      });

    tr.addEventListener("click", () => {
      selecionadoId = a.id;
      desenharTabela();
    });
    corpoTabela.appendChild(tr);
  });
}

// ---------- Pesquisar ----------
document.getElementById("btnPesquisar").addEventListener("click", desenharTabela);
campoBusca.addEventListener("keydown", e => {
  if (e.key === "Enter") desenharTabela();
});

// ---------- Cadastrar ----------
const campoLote = document.getElementById("lote");

// A lista vem da API toda vez que o modal abre: o que foi criado, renomeado ou desativado
// em Gestão de lotes já aparece aqui, sem depender de nada fixo na página.
async function carregarLotes() {
  campoLote.innerHTML = "";
  try {
    const resposta = await fetch("/consultarLotes");
    if (!resposta.ok) throw new Error(`Erro ${resposta.status}`);
    const { lotes } = await resposta.json();
    lotes.forEach(l => campoLote.add(new Option(l.nome, l.nome)));
    if (lotes.length === 0) {
      mostrarErroCadastro("Nenhum lote cadastrado. Crie um em Utilitários → Gestão de lotes.");
    }
  } catch (erro) {
    console.error("Falha ao carregar lotes:", erro);
    mostrarErroCadastro("Não foi possível carregar a lista de lotes.");
  }
}

document.getElementById("btnCadastrar").addEventListener("click", async () => {
  formCadastro.reset();
  erroCadastro.hidden = true;
  modalCadastro.showModal();
  document.getElementById("nome").focus();
  await carregarLotes();
});

document.getElementById("cancelarCadastro").addEventListener("click", () => modalCadastro.close());

formCadastro.addEventListener("submit", async e => {
  e.preventDefault();

  const nome = document.getElementById("nome").value.trim();
  const brinco = document.getElementById("brinco").value.trim();
  const pesoTexto = document.getElementById("peso").value;

  if (!nome || !brinco) {
    mostrarErroCadastro("Preencha o nome e o brinco.");
    return;
  }
  if (!campoLote.value) {
    mostrarErroCadastro("Escolha um lote. Se não houver nenhum, crie em Utilitários → Gestão de lotes.");
    return;
  }

  const novoAnimal = {
    brinco,
    nome,
    tipo: document.getElementById("tipo").value,
    sexo: document.getElementById("sexo").value,
    peso_atual: pesoTexto === "" ? null : Number(pesoTexto),
    raca: document.getElementById("raca").value.trim(),
    origem: document.getElementById("origem").value.trim(),
    data_nascimento: document.getElementById("nascimento").value || null,
    status: document.getElementById("status").value,
    lote: document.getElementById("lote").value,
    observacoes: document.getElementById("observacoes").value.trim()
  };

  try {
    const resposta = await fetch("/cadastrarAnimal", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(novoAnimal)
    });

    if (!resposta.ok) {
      const erro = await resposta.json().catch(() => ({}));
      throw new Error(erro.detail || "Erro ao cadastrar o animal.");
    }

    modalCadastro.close();
    await carregarAnimais();   // recarrega a tabela já com o novo animal
  } catch (erro) {
    mostrarErroCadastro(erro.message);
  }
});

function mostrarErroCadastro(mensagem) {
  erroCadastro.textContent = mensagem;
  erroCadastro.hidden = false;
}

// ---------- Informações ----------
// ---------- Informações ----------
document.getElementById("btnInformacoes").addEventListener("click", () => {
  const animal = animais.find(a => a.id === selecionadoId);
  if (!animal) {
    modalErro.showModal();
    return;
  }
  window.location.href = `animal.html?id=${animal.id}`;
});

// ---------- Baixa (venda, abate ou morte) ----------
const modalBaixa = document.getElementById("modalBaixa");
const formBaixa = document.getElementById("formBaixa");
const erroBaixa = document.getElementById("erroBaixa");

function hojeISO() {
  const d = new Date();
  const pad = n => String(n).padStart(2, "0");
  return `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())}`;
}

document.getElementById("btnBaixa").addEventListener("click", () => {
  const animal = animais.find(a => a.id === selecionadoId);

  if (!animal) {
    modalErro.showModal();
    return;
  }

  formBaixa.reset();
  document.getElementById("textoBaixa").textContent = `${animal.nome} (brinco ${animal.brinco})`;
  document.getElementById("dataBaixa").value = hojeISO();
  document.getElementById("dataBaixa").max = hojeISO();
  erroBaixa.hidden = true;
  modalBaixa.showModal();
});

formBaixa.addEventListener("submit", async e => {
  e.preventDefault();
  const motivo = formBaixa.querySelector('input[name="motivoBaixa"]:checked');
  const data = document.getElementById("dataBaixa").value;
  if (!motivo) return mostrarErroBaixa("Escolha o motivo da baixa: venda, abate ou morte.");
  if (!data) return mostrarErroBaixa("Informe a data da baixa.");

  const botao = document.getElementById("confirmarBaixa");
  botao.disabled = true;
  try {
    const resposta = await fetch(`/baixaAnimal/${selecionadoId}`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ motivo: motivo.value, data, observacoes: document.getElementById("obsBaixa").value.trim() })
    });
    if (!resposta.ok) {
      const erro = await resposta.json().catch(() => ({}));
      throw new Error(erro.detail || "Erro ao registrar a baixa.");
    }
    modalBaixa.close();
    selecionadoId = null;
    await carregarAnimais();
  } catch (erro) {
    mostrarErroBaixa(erro.message);
  } finally {
    botao.disabled = false;
  }
});

function mostrarErroBaixa(texto) {
  erroBaixa.textContent = texto;
  erroBaixa.hidden = false;
}

// ---------- Fechar modais ----------
document.querySelectorAll("[data-fechar]").forEach(botao => {
  botao.addEventListener("click", () => document.getElementById(botao.dataset.fechar).close());
});

carregarAnimais();