let pagina = 1;

function desenhar(d) {
  const corpo = $("corpo");
  corpo.innerHTML = "";
  if (!d.itens.length) corpo.innerHTML = '<tr><td class="vazio" colspan="6">Nenhum registro ainda.</td></tr>';
  d.itens.forEach(i => {
    const tr = document.createElement("tr");
    celula(tr, dataBR(i.quando));
    celula(tr, ROTULO_ACAO[i.acao] || i.acao);
    celula(tr, i.alvo || "-");
    celula(tr, i.detalhe || "-");
    celula(tr, i.superadmin || "-");
    celula(tr, i.ip || "-");
    corpo.appendChild(tr);
  });
  const inicio = d.total ? (d.pagina - 1) * d.por_pagina + 1 : 0;
  $("infoPagina").textContent = `Mostrando ${inicio}–${Math.min(d.total, d.pagina * d.por_pagina)} de ${d.total}`;
  $("numeroPagina").textContent = `Página ${d.pagina} de ${d.paginas}`;
  $("btnAnterior").disabled = d.pagina <= 1;
  $("btnProxima").disabled = d.pagina >= d.paginas;
  pagina = d.pagina;
}

async function carregar() {
  $("erroPagina").hidden = true;
  try { desenhar(await api(`/auditoria?pagina=${pagina}&por_pagina=20`)); }
  catch (erro) { mostrar($("erroPagina"), erro.message); }
}

$("btnAnterior").addEventListener("click", () => { pagina -= 1; carregar(); });
$("btnProxima").addEventListener("click", () => { pagina += 1; carregar(); });
carregar();
