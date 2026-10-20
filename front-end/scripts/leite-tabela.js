const erroTabela = $("erroTabela");

function filtros() {
  return new URLSearchParams({
    lote: $("lote").value,
    dias: $("periodo").value,
    ordem: $("ordem").value
  });
}

function linha(valores, classes = []) {
  const tr = document.createElement("tr");
  valores.forEach((valor, i) => {
    const td = document.createElement("td");
    td.textContent = valor;
    if (classes[i]) td.className = classes[i];
    tr.appendChild(td);
  });
  return tr;
}

function desenhar(vacas) {
  const corpo = $("corpoTabela");
  const rodape = $("rodapeTabela");
  corpo.innerHTML = "";
  rodape.innerHTML = "";

  if (vacas.length === 0) {
    corpo.innerHTML = '<tr><td class="vazio" colspan="7">Nenhuma vaca encontrada para este filtro.</td></tr>';
    return;
  }

  let manha = 0, tarde = 0;
  vacas.forEach(v => {
    manha += v.manha;
    tarde += v.tarde;
    corpo.appendChild(linha(
      [v.nome, v.brinco || "-", v.lote || "-", v.status || "-",
       formatarLitros(v.manha), formatarLitros(v.tarde), formatarLitros(v.total)],
      ["esq"]));
  });

  rodape.appendChild(linha(
    [`${vacas.length} vaca(s)`, "", "", "", formatarLitros(manha), formatarLitros(tarde), formatarLitros(manha + tarde)],
    ["esq"]));
}

async function carregar() {
  erroTabela.hidden = true;
  try {
    const dados = await api(`/consultarProducaoLeite?${filtros()}`);
    desenhar(dados.vacas);
  } catch (erro) {
    mostrarMensagem(erroTabela, erro.message);
  }
}

["lote", "periodo", "ordem"].forEach(id => $(id).addEventListener("change", carregar));

$("btnPdf").addEventListener("click", async () => {
  const botao = $("btnPdf");
  botao.disabled = true;
  erroTabela.hidden = true;
  try {
    await baixarRelatorio(`/relatorioLeite?${filtros()}`);
  } catch (erro) {
    mostrarMensagem(erroTabela, erro.message);
  } finally {
    botao.disabled = false;
  }
});

(async () => {
  try {
    await carregarLotes($("lote"), "Todos os lotes");
  } catch (erro) {
    mostrarMensagem(erroTabela, erro.message);
  }
  carregar();
})();