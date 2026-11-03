const NS = "http://www.w3.org/2000/svg";

function svg(tag, atributos = {}, texto) {
  const e = document.createElementNS(NS, tag);
  Object.entries(atributos).forEach(([k, v]) => e.setAttribute(k, v));
  if (texto !== undefined) e.textContent = texto;
  return e;
}

function rosca(destino, ativas, desativadas) {
  destino.innerHTML = "";
  const total = ativas + desativadas, R = 40, C = 2 * Math.PI * R;
  const grafico = svg("svg", { viewBox: "0 0 120 120", role: "img", "aria-label": `${ativas} fazendas ativas e ${desativadas} desativadas` });
  grafico.appendChild(svg("circle", { cx: 60, cy: 60, r: R, fill: "none", stroke: "#e8ecef", "stroke-width": 18 }));
  if (total > 0) {
    const verde = (ativas / total) * C;
    grafico.appendChild(svg("circle", { cx: 60, cy: 60, r: R, fill: "none", stroke: "#2f6b3c", "stroke-width": 18,
      "stroke-dasharray": `${verde} ${C - verde}`, transform: "rotate(-90 60 60)" }));
    if (desativadas > 0) {
      grafico.appendChild(svg("circle", { cx: 60, cy: 60, r: R, fill: "none", stroke: "#b4561f", "stroke-width": 18,
        "stroke-dasharray": `${C - verde} ${verde}`, "stroke-dashoffset": -verde, transform: "rotate(-90 60 60)" }));
    }
  }
  grafico.appendChild(svg("text", { x: 60, y: 62, "text-anchor": "middle", "font-size": 20, "font-weight": 700, fill: "#1f2933" }, String(total)));
  grafico.appendChild(svg("text", { x: 60, y: 76, "text-anchor": "middle", "font-size": 8, fill: "#62707e" }, "fazendas"));
  const legenda = el("ul", "legenda");
  [["cor-ok", "Ativas", ativas], ["cor-ruim", "Desativadas", desativadas]].forEach(([cor, nome, n]) => {
    const li = el("li");
    li.append(el("i", cor), `${nome}: ${n}` + (total ? ` (${Math.round((n / total) * 100)}%)` : ""));
    legenda.appendChild(li);
  });
  destino.append(grafico, legenda);
}

function barrasSimples(destino, itens, cor) {
  destino.innerHTML = "";
  const maior = Math.max(1, ...itens.map(i => i.valor));
  itens.forEach(i => {
    const linha = el("div", "barra-linha");
    const trilho = el("div", "trilho");
    const barra = el("span", cor);
    barra.style.width = `${(i.valor / maior) * 100}%`;
    trilho.appendChild(barra);
    linha.append(el("span", "", i.nome), trilho, el("strong", "", String(i.valor)));
    destino.appendChild(linha);
  });
  if (!itens.length) destino.textContent = "Sem dados.";
}

function barrasEmpilhadas(destino, planos) {
  destino.innerHTML = "";
  const maior = Math.max(1, ...planos.map(p => p.total));
  planos.forEach(p => {
    const linha = el("div", "barra-linha");
    const trilho = el("div", "trilho");
    trilho.style.width = `${(p.total / maior) * 100}%`;
    trilho.style.minWidth = p.total ? "24px" : "0";
    [["cor-ok", p.em_dia], ["cor-ruim", p.pendentes]].forEach(([cor, n]) => {
      if (!n) return;
      const parte = el("span", cor);
      parte.style.width = `${(n / p.total) * 100}%`;
      parte.title = `${cor === "cor-ok" ? "Em dia" : "Pendente"}: ${n}`;
      trilho.appendChild(parte);
    });
    const area = el("div");
    area.appendChild(trilho);
    linha.append(el("span", "", p.nome), area, el("strong", "", `${p.em_dia}/${p.pendentes}`));
    destino.appendChild(linha);
  });
  if (!planos.length) destino.textContent = "Sem dados.";
}

function colunasPorMes(destino, meses) {
  destino.innerHTML = "";
  const largura = 360, altura = 150, base = 125, topo = 20, maior = Math.max(1, ...meses.map(m => m.cadastros));
  const passo = largura / meses.length;
  const grafico = svg("svg", { viewBox: `0 0 ${largura} ${altura}`, role: "img",
    "aria-label": "Cadastros de fazendas por mês: " + meses.map(m => `${m.mes}: ${m.cadastros}`).join(", ") });
  grafico.appendChild(svg("line", { x1: 0, y1: base, x2: largura, y2: base, stroke: "#d9dee2" }));
  meses.forEach((m, i) => {
    const h = (m.cadastros / maior) * (base - topo), x = i * passo + passo * 0.18, l = passo * 0.64;
    grafico.appendChild(svg("rect", { x, y: base - h, width: l, height: Math.max(h, m.cadastros ? 2 : 0), rx: 2, fill: "#1d2b3a" }));
    if (m.cadastros) grafico.appendChild(svg("text", { x: x + l / 2, y: base - h - 4, "text-anchor": "middle", class: "valor" }, String(m.cadastros)));
    if (i % 2 === 0 || meses.length < 7) {
      const [a, mes] = m.mes.split("-");
      grafico.appendChild(svg("text", { x: x + l / 2, y: base + 13, "text-anchor": "middle" }, `${mes}/${a.slice(2)}`));
    }
  });
  destino.appendChild(grafico);
}

function atividade(lista) {
  const corpo = $("corpoAtividade");
  corpo.innerHTML = "";
  if (!lista.length) {
    corpo.innerHTML = '<tr><td class="vazio" colspan="4">Nenhuma atividade registrada ainda.</td></tr>';
    return;
  }
  lista.forEach(a => {
    const tr = document.createElement("tr");
    celula(tr, dataBR(a.quando));
    celula(tr, ROTULO_ACAO[a.acao] || a.acao);
    celula(tr, a.alvo || "-");
    celula(tr, a.superadmin || "-");
    corpo.appendChild(tr);
  });
}

async function carregar() {
  try {
    const d = await api("/dashboard");
    $("indTotal").textContent = d.total;
    $("indAtivas").textContent = d.ativas;
    $("indDesativadas").textContent = d.desativadas;
    $("indEmDia").textContent = d.em_dia;
    $("indPendentes").textContent = d.pendentes;
    $("indFuncionarios").textContent = d.funcionarios;
    if (d.pendentes_ativas > 0) {
      $("textoPendentes").textContent = d.pendentes_ativas === 1
        ? "1 fazenda ativa está com o pagamento pendente."
        : `${d.pendentes_ativas} fazendas ativas estão com o pagamento pendente.`;
      $("avisoPendentes").hidden = false;
    }
    rosca($("graficoRosca"), d.ativas, d.desativadas);
    barrasSimples($("graficoPlanos"), d.por_plano.map(p => ({ nome: p.nome, valor: p.total })), "cor-marinho");
    barrasEmpilhadas($("graficoPagamento"), d.por_plano);
    colunasPorMes($("graficoMeses"), d.cadastros_por_mes);
    atividade(d.atividade);
  } catch (erro) {
    mostrar($("erroPainel"), erro.message);
  }
}

carregar();
