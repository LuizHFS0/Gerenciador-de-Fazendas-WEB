const API = "http://127.0.0.1:8000";
const id = new URLSearchParams(location.search).get("id");
if (!id) location.href = "maquinas.html";

let maquina = null;
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

// ---------- Carregar dados ----------
async function carregarMaquina() {
  try {
    maquina = await api(`/consultarMaquina/${id}`);
  } catch (erro) {
    $("tituloMaquina").textContent = "Máquina não encontrada";
    $("subMaquina").textContent = erro.message;
    return;
  }

  $("tituloMaquina").textContent = maquina.nome;
  $("subMaquina").textContent = [maquina.tipo, maquina.modelo].filter(Boolean).join(" ");
  document.querySelectorAll(".nome-modal").forEach(p => p.textContent = maquina.nome);

  const horas = maquina.horas_uso == null ? "-" : `${Number(maquina.horas_uso).toLocaleString("pt-BR")} h`;
  const campos = [
    ["Tipo", maquina.tipo || "-"], ["Status", maquina.status || "-"],
    ["Modelo", maquina.modelo || "-"], ["Fabricante", maquina.fabricante || "-"],
    ["Ano", maquina.ano || "-"], ["Placa", maquina.placa || "-"],
    ["Horas de uso", horas], ["Observações", maquina.observacoes || "-"]
  ];
  $("dadosMaquina").innerHTML = "";
  campos.forEach(([rotulo, valor]) => {
    const dt = document.createElement("dt");
    const dd = document.createElement("dd");
    dt.textContent = rotulo;
    dd.textContent = valor;
    $("dadosMaquina").append(dt, dd);
  });
}

async function carregarManutencoes() {
  const corpo = $("corpoManutencoes");
  try {
    const dados = await api(`/manutencoes/${id}`);
    corpo.innerHTML = "";
    if (dados.manutencoes.length === 0) {
      corpo.innerHTML = '<tr><td class="vazio" colspan="5">Nenhuma manutenção registrada.</td></tr>';
      return;
    }
    dados.manutencoes.forEach(m => {
      const tr = document.createElement("tr");
      [formatarData(m.data_manutencao), m.tipo_manutencao, m.responsavel || "-",
       formatarData(m.proxima_manutencao), m.descricao || "-"].forEach(valor => {
        const td = document.createElement("td");
        td.textContent = valor;
        tr.appendChild(td);
      });
      corpo.appendChild(tr);
    });
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

// Mudar status
$("btnStatus").addEventListener("click", () => {
  $("novoStatus").value = maquina.status;
  abrir($("modalStatus"));
});

$("okStatus").addEventListener("click", async () => {
  try {
    await api(`/alterarStatusMaquina/${id}`, {
      method: "PUT",
      body: JSON.stringify({ status: $("novoStatus").value })
    });
    $("modalStatus").close();
    carregarMaquina();
  } catch (erro) { mostrarErro($("modalStatus"), erro.message); }
});

// Registrar manutenção
$("btnManutencao").addEventListener("click", () => {
  $("formManutencao").reset();
  $("manData").value = new Date().toISOString().slice(0, 10);
  abrir($("modalManutencao"));
});

$("formManutencao").addEventListener("submit", async e => {
  e.preventDefault();
  try {
    await api(`/manutencoes/${id}`, {
      method: "POST",
      body: JSON.stringify({
        tipo_manutencao: $("manTipo").value,
        responsavel: $("manResp").value.trim(),
        data_manutencao: $("manData").value,
        proxima_manutencao: $("manProx").value || null,
        descricao: $("manDesc").value.trim()
      })
    });
    $("modalManutencao").close();
    carregarManutencoes();
  } catch (erro) { mostrarErro($("modalManutencao"), erro.message); }
});

carregarMaquina();
carregarManutencoes();