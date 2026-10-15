const API = "http://127.0.0.1:8000";
const funcionarios = [];
let selecionadoId = null;

const $ = id => document.getElementById(id);

function formatarData(iso) {
  if (!iso || typeof iso !== "string") return "-";
  const [ano, mes, dia] = iso.split("-");
  return `${dia}/${mes}/${ano}`;
}

function formatarCpf(cpf) {
  const d = String(cpf || "").replace(/\D/g, "");
  return d.length === 11 ? d.replace(/(\d{3})(\d{3})(\d{3})(\d{2})/, "$1.$2.$3-$4") : (cpf || "-");
}

// ---------- Carregar e desenhar ----------
async function carregarFuncionarios() {
  try {
    const resposta = await fetch(`${API}/consultarFuncionarios`);
    if (!resposta.ok) throw new Error(`Erro ${resposta.status}`);
    const dados = await resposta.json();
    funcionarios.length = 0;
    funcionarios.push(...dados.funcionarios);
  } catch (erro) {
    console.error("Falha ao carregar funcionários:", erro);
  }
  desenharTabela();
}

function desenharTabela() {
  $("corpoTabela").innerHTML = "";

  if (funcionarios.length === 0) {
    $("corpoTabela").innerHTML = '<tr><td class="vazio" colspan="6">Nenhum funcionário cadastrado.</td></tr>';
    return;
  }

  funcionarios.forEach(f => {
    const tr = document.createElement("tr");
    if (f.id === selecionadoId) tr.classList.add("selecionada");

    [f.id, f.nome, formatarCpf(f.cpf), f.telefone, f.cargo, formatarData(f.data_admissao)].forEach(valor => {
      const td = document.createElement("td");
      td.textContent = valor || "-";
      tr.appendChild(td);
    });

    tr.addEventListener("click", () => {
      selecionadoId = f.id;
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
  const cpf = $("cpf").value.replace(/\D/g, "");   // guarda só os dígitos

  if (!nome) {
    mostrarErroCadastro("Preencha o nome do funcionário.");
    return;
  }
  if (cpf && cpf.length !== 11) {
    mostrarErroCadastro("O CPF deve ter 11 dígitos.");
    return;
  }

  try {
    const resposta = await fetch(`${API}/cadastrarFuncionario`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        nome,
        cpf,
        telefone: $("telefone").value.trim(),
        endereco: $("endereco").value.trim(),
        cargo: $("cargo").value.trim(),
        data_admissao: $("admissao").value || null,
        observacoes: $("observacoes").value.trim()
      })
    });

    if (!resposta.ok) {
      const erro = await resposta.json().catch(() => ({}));
      throw new Error(erro.detail || "Erro ao cadastrar o funcionário.");
    }

    $("modalCadastro").close();
    await carregarFuncionarios();
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
  const funcionario = funcionarios.find(f => f.id === selecionadoId);
  if (!funcionario) {
    $("modalErro").showModal();
    return;
  }
  window.location.href = `funcionario.html?id=${funcionario.id}`;
});

// ---------- Fechar modais ----------
document.querySelectorAll("[data-fechar]").forEach(botao => {
  botao.addEventListener("click", () => $(botao.dataset.fechar).close());
});

carregarFuncionarios();