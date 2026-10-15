const API = "http://127.0.0.1:8000";
const itens = [];
let selecionadoId = null;

const $ = id => document.getElementById(id);

function formatarNumero(n) {
  if (n === null || n === undefined || n === "") return "-";
  return Number(n).toLocaleString("pt-BR");
}

// ---------- Carregar e desenhar ----------
async function carregarItens() {
  try {
    const resposta = await fetch(`${API}/consultarEstoque`);
    if (!resposta.ok) throw new Error(`Erro ${resposta.status}`);
    const dados = await resposta.json();
    itens.length = 0;
    itens.push(...dados.itens);
  } catch (erro) {
    console.error("Falha ao carregar o estoque:", erro);
  }
  desenharTabela();
}

function desenharTabela() {
  $("corpoTabela").innerHTML = "";

  if (itens.length === 0) {
    $("corpoTabela").innerHTML = '<tr><td class="vazio" colspan="7">Nenhum item no estoque.</td></tr>';
    return;
  }

  itens.forEach(i => {
    const tr = document.createElement("tr");
    if (i.id === selecionadoId) tr.classList.add("selecionada");

    const valores = [i.id, i.nome, i.categoria, i.unidade, formatarNumero(i.quantidade),
                     formatarNumero(i.estoque_minimo), i.localizacao];
    valores.forEach((valor, posicao) => {
      const td = document.createElement("td");
      td.textContent = valor || "-";
      // quantidade no mínimo ou abaixo: destaque
      if (posicao === 4 && Number(i.quantidade) <= Number(i.estoque_minimo)) td.classList.add("baixo");
      tr.appendChild(td);
    });

    tr.addEventListener("click", () => {
      selecionadoId = i.id;
      desenharTabela();
    });
    $("corpoTabela").appendChild(tr);
  });
}

// ---------- Cadastrar ----------
$("btnCadastrar").addEventListener("click", () => {
  $("formCadastro").reset();
  $("erroCadastro").hidden = true;
  $("modalCadastro").showModal();
  $("nome").focus();
});

$("formCadastro").addEventListener("submit", async e => {
  e.preventDefault();

  const nome = $("nome").value.trim();
  if (!nome) {
    mostrarErroCadastro("Preencha o nome do item.");
    return;
  }

  try {
    const resposta = await fetch(`${API}/cadastrarItem`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        nome,
        categoria: $("categoria").value.trim(),
        unidade: $("unidade").value,
        quantidade: Number($("quantidade").value || 0),
        estoque_minimo: Number($("minimo").value || 0),
        localizacao: $("localizacao").value.trim(),
        observacoes: $("observacoes").value.trim()
      })
    });

    if (!resposta.ok) {
      const erro = await resposta.json().catch(() => ({}));
      throw new Error(erro.detail || "Erro ao cadastrar o item.");
    }

    $("modalCadastro").close();
    await carregarItens();
  } catch (erro) {
    mostrarErroCadastro(erro.message);
  }
});

function mostrarErroCadastro(mensagem) {
  $("erroCadastro").textContent = mensagem;
  $("erroCadastro").hidden = false;
}

// ---------- Informações ----------
$("btnInformacoes").addEventListener("click", () => {
  const item = itens.find(i => i.id === selecionadoId);
  if (!item) {
    $("modalErro").showModal();
    return;
  }
  window.location.href = `item.html?id=${item.id}`;
});

// ---------- Excluir ----------
$("btnExcluir").addEventListener("click", () => {
  const item = itens.find(i => i.id === selecionadoId);
  if (!item) {
    $("modalErro").showModal();
    return;
  }
  $("textoExcluir").textContent = `Deseja excluir "${item.nome}"?`;
  $("erroExcluir").hidden = true;
  $("modalExcluir").showModal();
});

$("confirmarExcluir").addEventListener("click", async () => {
  try {
    const resposta = await fetch(`${API}/excluirItem/${selecionadoId}`, { method: "DELETE" });
    if (!resposta.ok) {
      const erro = await resposta.json().catch(() => ({}));
      throw new Error(erro.detail || "Erro ao excluir o item.");
    }
    $("modalExcluir").close();
    selecionadoId = null;
    await carregarItens();
  } catch (erro) {
    $("erroExcluir").textContent = erro.message;
    $("erroExcluir").hidden = false;
  }
});

// ---------- Fechar modais ----------
document.querySelectorAll("[data-fechar]").forEach(botao => {
  botao.addEventListener("click", () => $(botao.dataset.fechar).close());
});

carregarItens();