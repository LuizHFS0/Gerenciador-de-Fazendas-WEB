const API = "http://127.0.0.1:8000";
const maquinas = [];
let selecionadoId = null;

const $ = id => document.getElementById(id);

function formatarHoras(h) {
  if (h === null || h === undefined || h === "") return "-";
  return `${Number(h).toLocaleString("pt-BR")} h`;
}

function normalizar(texto) {
  return String(texto ?? "").toLowerCase().normalize("NFD").replace(/[\u0300-\u036f]/g, "");
}

// ---------- Carregar e desenhar ----------
async function carregarMaquinas() {
  try {
    const resposta = await fetch(`${API}/consultarMaquinas`);
    if (!resposta.ok) throw new Error(`Erro ${resposta.status}`);
    const dados = await resposta.json();
    maquinas.length = 0;
    maquinas.push(...dados.maquinas);
  } catch (erro) {
    console.error("Falha ao carregar máquinas:", erro);
  }
  desenharTabela();
}

function desenharTabela() {
  const termo = normalizar($("busca").value.trim());
  const lista = maquinas.filter(m => !termo || normalizar(m.nome).includes(termo));

  $("corpoTabela").innerHTML = "";

  if (lista.length === 0) {
    $("corpoTabela").innerHTML = '<tr><td class="vazio" colspan="9">Nenhuma máquina encontrada.</td></tr>';
    return;
  }

  lista.forEach(m => {
    const tr = document.createElement("tr");
    if (m.id === selecionadoId) tr.classList.add("selecionada");

    [m.id, m.nome, m.tipo, m.status, m.modelo, m.fabricante, m.ano, m.placa, formatarHoras(m.horas_uso)]
      .forEach(valor => {
        const td = document.createElement("td");
        td.textContent = valor ?? "-";
        tr.appendChild(td);
      });

    tr.addEventListener("click", () => {
      selecionadoId = m.id;
      desenharTabela();
    });
    $("corpoTabela").appendChild(tr);
  });
}

// ---------- Pesquisar ----------
$("btnPesquisar").addEventListener("click", desenharTabela);
$("busca").addEventListener("keydown", e => {
  if (e.key === "Enter") desenharTabela();
});

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
    mostrarErroCadastro("Preencha o nome da máquina.");
    return;
  }

  const numero = id => ($(id).value === "" ? null : Number($(id).value));

  try {
    const resposta = await fetch(`${API}/cadastrarMaquina`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        nome,
        placa: $("placa").value.trim(),
        fabricante: $("fabricante").value.trim(),
        modelo: $("modelo").value.trim(),
        ano: numero("ano"),
        horas_uso: numero("horas"),
        tipo: $("tipo").value.trim(),
        status: $("status").value,
        observacoes: $("observacoes").value.trim()
      })
    });

    if (!resposta.ok) {
      const erro = await resposta.json().catch(() => ({}));
      throw new Error(erro.detail || "Erro ao cadastrar a máquina.");
    }

    $("modalCadastro").close();
    await carregarMaquinas();
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
  const maquina = maquinas.find(m => m.id === selecionadoId);
  if (!maquina) {
    $("modalErro").showModal();
    return;
  }
  window.location.href = `maquina.html?id=${maquina.id}`;
});

// ---------- Excluir ----------
$("btnExcluir").addEventListener("click", () => {
  const maquina = maquinas.find(m => m.id === selecionadoId);
  if (!maquina) {
    $("modalErro").showModal();
    return;
  }
  $("textoExcluir").textContent = `Deseja excluir "${maquina.nome}"?`;
  $("erroExcluir").hidden = true;
  $("modalExcluir").showModal();
});

$("confirmarExcluir").addEventListener("click", async () => {
  try {
    const resposta = await fetch(`${API}/excluirMaquina/${selecionadoId}`, { method: "DELETE" });
    if (!resposta.ok) {
      const erro = await resposta.json().catch(() => ({}));
      throw new Error(erro.detail || "Erro ao excluir a máquina.");
    }
    $("modalExcluir").close();
    selecionadoId = null;
    await carregarMaquinas();
  } catch (erro) {
    $("erroExcluir").textContent = erro.message;
    $("erroExcluir").hidden = false;
  }
});

// ---------- Fechar modais ----------
document.querySelectorAll("[data-fechar]").forEach(botao => {
  botao.addEventListener("click", () => $(botao.dataset.fechar).close());
});

carregarMaquinas();