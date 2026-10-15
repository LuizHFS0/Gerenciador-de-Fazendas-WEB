function definirTexto(seletor, valor) {
  const el = document.querySelector(seletor);
  if (!el) {
    console.warn(`Elemento ${seletor} não existe no HTML`);
    return;
  }
  el.textContent = valor;
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
  const resposta = await fetch('http://127.0.0.1:8000/movimentacoesDashboard');
  const movimentacoes = await resposta.json();
  const termo = normalizar($("busca").value.trim());
  const lista = movimentacoes.filter(m => !termo || normalizar(m.item).includes(termo));

  $("corpoTabela").innerHTML = "";

  if (lista.length === 0) {
    $("corpoTabela").innerHTML = '<tr><td class="vazio" colspan="9">Nenhuma movimentação encontrada.</td></tr>';
    return;
  }

  lista.forEach(m => {
    const tr = document.createElement("tr");
    if (m.id === selecionadoId) tr.classList.add("selecionada");

    [, formatarHoras(m.horas_uso)]
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

carregarDashboard();