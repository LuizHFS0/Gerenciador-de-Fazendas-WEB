const API = "http://127.0.0.1:8000";
const id = new URLSearchParams(location.search).get("id");
if (!id) location.href = "funcionarios.html";

const $ = elemento => document.getElementById(elemento);

async function api(caminho) {
  const resposta = await fetch(API + caminho);
  const dados = await resposta.json().catch(() => ({}));
  if (!resposta.ok) throw new Error(dados.detail || "Erro ao falar com o servidor.");
  return dados;
}

function formatarData(iso) {
  if (!iso || typeof iso !== "string") return "-";
  const [ano, mes, dia] = iso.split("-");
  return `${dia}/${mes}/${ano}`;
}

function formatarCpf(cpf) {
  const d = String(cpf || "").replace(/\D/g, "");
  return d.length === 11 ? d.replace(/(\d{3})(\d{3})(\d{3})(\d{2})/, "$1.$2.$3-$4") : (cpf || "-");
}

async function carregarFuncionario() {
  let f;
  try {
    f = await api(`/consultarFuncionario/${id}`);
  } catch (erro) {
    $("tituloFuncionario").textContent = "Funcionário não encontrado";
    $("subFuncionario").textContent = erro.message;
    return;
  }

  $("tituloFuncionario").textContent = f.nome;
  $("subFuncionario").textContent = f.cargo || "";

  const campos = [
    ["CPF", formatarCpf(f.cpf)],
    ["Telefone", f.telefone || "-"],
    ["Endereço", f.endereco || "-"],
    ["Cargo", f.cargo || "-"],
    ["Data de admissão", formatarData(f.data_admissao)],
    ["Observações", f.observacoes || "-"]
  ];
  $("dadosFuncionario").innerHTML = "";
  campos.forEach(([rotulo, valor]) => {
    const dt = document.createElement("dt");
    const dd = document.createElement("dd");
    dt.textContent = rotulo;
    dd.textContent = valor;
    $("dadosFuncionario").append(dt, dd);
  });
}

async function carregarMovimentacoes() {
  const corpo = $("corpoMovimentacoes");
  try {
    const dados = await api(`/movimentacoesFuncionario/${id}`);
    corpo.innerHTML = "";
    if (dados.movimentacoes.length === 0) {
      corpo.innerHTML = '<tr><td class="vazio" colspan="3">Nenhuma movimentação encontrada para este funcionário.</td></tr>';
      return;
    }
    dados.movimentacoes.forEach(m => {
      const tr = document.createElement("tr");
      [formatarData(m.data), m.tipo, m.descricao].forEach((valor, i) => {
        const td = document.createElement("td");
        td.textContent = valor || "-";
        if (i === 2) td.className = "esq";
        tr.appendChild(td);
      });
      corpo.appendChild(tr);
    });
  } catch (erro) { console.error(erro); }
}

carregarFuncionario();
carregarMovimentacoes();