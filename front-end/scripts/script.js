function definirTexto(seletor, valor) {
  const el = document.querySelector(seletor);
  if (!el) {
    console.warn(`Elemento ${seletor} não existe no HTML`);
    return;
  }
  el.textContent = valor;
}

function formatarData(iso) {
  if (!iso || typeof iso !== "string") return "-";
  const [ano, mes, dia] = iso.slice(0, 10).split("-");
  return `${dia}/${mes}/${ano}`;
}

function formatarDataHora(texto) {
  if (!texto) return "-";
  const hora = texto.slice(11, 16);
  return hora ? `${formatarData(texto)} ${hora}` : formatarData(texto);
}

async function carregarDashboard() {
  try {
    const resposta = await fetch('http://127.0.0.1:8000/dashboard');
    if (!resposta.ok) throw new Error(`Erro ${resposta.status}`);
    const dados = await resposta.json();

    definirTexto('#animais-ativos', dados.animais_ativos);
    definirTexto('#maquinas-em-operacao', dados.maquinas_operacao);
    definirTexto('#funcionarios-ativos', dados.funcionarios_ativos);
    desenharTabela();
  } catch (erro) {
    console.error('Falha ao carregar o dashboard:', erro);
  }
}

async function desenharTabela() {
  try {
    const resposta = await fetch('http://127.0.0.1:8000/obterLogsEstoque?limite=5');
    const dados = await resposta.json();
    document.getElementById("corpoTabela").innerHTML = "";

    if (dados.logs.length === 0) {
      document.getElementById("corpoTabela").innerHTML = '<tr><td class="vazio" colspan="9">Nenhuma movimentação encontrada.</td></tr>';
      return;
    }
    dados.logs.forEach(m => {
      const tr = document.createElement("tr");
      [formatarDataHora(m.data_hora), m.acao || "-", m.nome_usuario || "-", m.descricao || "-"].forEach(valor => {
          const td = document.createElement("td");
          td.textContent = valor ?? "-";
          tr.appendChild(td);
        });
      document.getElementById("corpoTabela").appendChild(tr);
    });
  } catch (erro) {
    console.error("Falha ao carregar movimentações:", erro);
  }
}

carregarDashboard();