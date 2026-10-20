const periodo = $("periodo");
const erroPainel = $("erroPainel");

function celula(tr, texto) {
  const td = document.createElement("td");
  td.textContent = texto;
  tr.appendChild(td);
}

function desenharTop(lista) {
  const corpo = $("corpoTop");
  corpo.innerHTML = "";

  if (lista.length === 0) {
    corpo.innerHTML = '<tr><td class="vazio" colspan="6">Nenhuma produção registrada neste período.</td></tr>';
    return;
  }

  const maior = lista[0].total;
  lista.forEach((vaca, i) => {
    const tr = document.createElement("tr");
    celula(tr, i + 1);
    celula(tr, vaca.nome);
    celula(tr, vaca.brinco || "-");
    celula(tr, vaca.lote || "-");
    celula(tr, formatarLitros(vaca.total));

    const td = document.createElement("td");
    const barra = document.createElement("div");
    barra.className = "rank-barra";
    const preenchido = document.createElement("span");
    preenchido.style.width = `${maior > 0 ? (vaca.total / maior) * 100 : 0}%`;
    barra.appendChild(preenchido);
    td.appendChild(barra);
    tr.appendChild(td);

    corpo.appendChild(tr);
  });
}

async function carregar() {
  erroPainel.hidden = true;
  try {
    const d = await api(`/dashboardLeite?dias=${periodo.value}`);
    $("indHoje").textContent = formatarLitros(d.litros_hoje);
    $("indPeriodo").textContent = formatarLitros(d.litros_periodo);
    $("indMedia").textContent = formatarLitros(d.media_diaria);
    $("indVacas").textContent = d.vacas_produzindo;
    desenharTop(d.top5);
  } catch (erro) {
    mostrarMensagem(erroPainel, erro.message);
  }
}

periodo.addEventListener("change", carregar);
$("btnMedicao").addEventListener("click", () => { window.location.href = "leite-medicao.html"; });
$("btnTabela").addEventListener("click", () => { window.location.href = "leite-tabela.html"; });

$("btnPdf").addEventListener("click", async () => {
  const botao = $("btnPdf");
  botao.disabled = true;
  erroPainel.hidden = true;
  try {
    await baixarRelatorio(`/relatorioLeite?dias=${periodo.value}&ordem=maior`);
  } catch (erro) {
    mostrarMensagem(erroPainel, erro.message);
  } finally {
    botao.disabled = false;
  }
});

carregar();