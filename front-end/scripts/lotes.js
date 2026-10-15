const API = "http://127.0.0.1:8000";
const lotes = [];
let selecionadoId = null;
let editandoId = null;     // null = cadastrando, número = editando

const $ = id => document.getElementById(id);

async function carregarLotes() {
  try {
    const resposta = await fetch(`${API}/gerenciarLotes`);
    if (!resposta.ok) throw new Error(`Erro ${resposta.status}`);
    const dados = await resposta.json();
    lotes.length = 0;
    lotes.push(...dados.lotes);
  } catch (erro) {
    console.error("Falha ao carregar lotes:", erro);
  }
  desenharTabela();
}

function desenharTabela() {
  $("corpoTabela").innerHTML = "";
  if (lotes.length === 0) {
    $("corpoTabela").innerHTML = '<tr><td class="vazio" colspan="6">Nenhum lote cadastrado.</td></tr>';
    return;
  }
  lotes.forEach(l => {
    const tr = document.createElement("tr");
    if (l.id === selecionadoId) tr.classList.add("selecionada");
    const tamanho = l.tamanho == null ? "-" : `${Number(l.tamanho).toLocaleString("pt-BR")} ha`;
    [l.id, l.nome, tamanho, l.localizacao, l.descricao, l.animais].forEach(valor => {
      const td = document.createElement("td");
      td.textContent = valor === null || valor === undefined || valor === "" ? "-" : valor;
      tr.appendChild(td);
    });
    tr.addEventListener("click", () => { selecionadoId = l.id; desenharTabela(); });
    $("corpoTabela").appendChild(tr);
  });
}

function selecionado() {
  const lote = lotes.find(l => l.id === selecionadoId);
  if (!lote) $("modalErro").showModal();
  return lote;
}

function mostrarErroLote(mensagem) {
  $("erroLote").textContent = mensagem;
  $("erroLote").hidden = false;
}

// ---------- Cadastrar e editar ----------
function abrirFormulario(lote) {
  editandoId = lote ? lote.id : null;
  $("tituloModal").textContent = lote ? "Editar lote" : "Cadastrar lote";
  $("formLote").reset();
  if (lote) {
    $("nome").value = lote.nome;
    $("tamanho").value = lote.tamanho ?? "";
    $("localizacao").value = lote.localizacao ?? "";
    $("descricao").value = lote.descricao ?? "";
  }
  $("erroLote").hidden = true;
  $("modalLote").showModal();
  $("nome").focus();
}

$("btnCadastrar").addEventListener("click", () => abrirFormulario(null));
$("btnEditar").addEventListener("click", () => {
  const lote = selecionado();
  if (lote) abrirFormulario(lote);
});

$("formLote").addEventListener("submit", async e => {
  e.preventDefault();

  const nome = $("nome").value.trim();
  if (!nome) {
    mostrarErroLote("Preencha o nome do lote.");
    return;
  }

  const corpo = {
    nome,
    tamanho: $("tamanho").value === "" ? null : Number($("tamanho").value),
    localizacao: $("localizacao").value.trim(),
    descricao: $("descricao").value.trim()
  };

  try {
    const resposta = await fetch(editandoId ? `${API}/editarLote/${editandoId}` : `${API}/cadastrarLote`, {
      method: editandoId ? "PUT" : "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(corpo)
    });
    if (!resposta.ok) {
      const erro = await resposta.json().catch(() => ({}));
      throw new Error(erro.detail || "Erro ao salvar o lote.");
    }
    $("modalLote").close();
    await carregarLotes();
  } catch (erro) {
    mostrarErroLote(erro.message);
  }
});

// ---------- Desativar ----------
$("btnExcluir").addEventListener("click", () => {
  const lote = selecionado();
  if (!lote) return;
  $("textoExcluir").textContent = `Deseja desativar o lote "${lote.nome}"?`;
  $("erroExcluir").hidden = true;
  $("modalExcluir").showModal();
});

$("confirmarExcluir").addEventListener("click", async () => {
  try {
    const resposta = await fetch(`${API}/excluirLote/${selecionadoId}`, { method: "DELETE" });
    if (!resposta.ok) {
      const erro = await resposta.json().catch(() => ({}));
      throw new Error(erro.detail || "Erro ao desativar o lote.");
    }
    $("modalExcluir").close();
    selecionadoId = null;
    await carregarLotes();
  } catch (erro) {
    $("erroExcluir").textContent = erro.message;
    $("erroExcluir").hidden = false;
  }
});

document.querySelectorAll("[data-fechar]").forEach(botao => {
  botao.addEventListener("click", () => $(botao.dataset.fechar).close());
});

carregarLotes();