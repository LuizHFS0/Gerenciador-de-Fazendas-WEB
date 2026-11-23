// Módulo de bezerros de uma vaca: ciclo reprodutivo, linha do tempo, parto e crias.
const id = new URLSearchParams(location.search).get("id");
if (!id) location.href = "animais.html";

const $ = seletor => document.getElementById(seletor);
const STATUS = {
  coberta: "Coberta, aguardando diagnóstico", gestante: "Gestante", parida: "Parida", vazia: "Vazia", aborto: "Aborto"
};
const SITUACAO = { vivo: "Nasceu vivo", natimorto: "Nasceu sem vida", faleceu_apos: "Faleceu após o nascimento" };
const COBERTURA = { monta: "Monta natural", ia: "Inseminação", repasse: "Repasse" };
const ASSISTENCIA = { normal: "Normal", assistido: "Assistido", cesarea: "Cesárea" };

let dados = null;
let podeGerenciar = false;      // Gerente ou Dono: registrar cobertura e parto (o servidor confere de novo)

async function api(caminho, opcoes = {}) {
  const resposta = await fetch(caminho, { headers: { "Content-Type": "application/json" }, ...opcoes });
  const corpo = await resposta.json().catch(() => ({}));
  if (!resposta.ok) throw new Error(corpo.detail || "Erro ao falar com o servidor.");
  return corpo;
}

function el(tag, classe, texto) {
  const e = document.createElement(tag);
  if (classe) e.className = classe;
  if (texto !== undefined) e.textContent = texto;
  return e;
}

function formatarData(iso) {
  if (!iso || typeof iso !== "string") return "-";
  const [ano, mes, dia] = iso.slice(0, 10).split("-");
  return `${dia}/${mes}/${ano}`;
}

function hoje() {
  const d = new Date();
  d.setMinutes(d.getMinutes() - d.getTimezoneOffset());
  return d.toISOString().slice(0, 10);
}

function textoDias(dias) {
  if (dias < 0) return `atrasado há ${-dias} ${dias === -1 ? "dia" : "dias"}`;
  if (dias === 0) return "hoje";
  return `faltam ${dias} ${dias === 1 ? "dia" : "dias"}`;
}

function avisoPagina(texto) {
  $("msgPagina").textContent = texto;
  $("msgPagina").hidden = false;
  setTimeout(() => { $("msgPagina").hidden = true; }, 8000);
}

// ---------- desenho ----------
function desenharLinha(lista, destino) {
  destino.innerHTML = "";
  lista.forEach(e => {
    const li = el("li", e.previsto ? "previsto" : "");
    const topo = el("div");
    topo.append(el("span", "titulo", e.titulo), el("span", "quando", formatarData(e.data)));
    if (e.previsto) topo.append(" ", el("span", "selo previsto", "previsto"));
    li.appendChild(topo);
    const extras = [e.detalhe && e.detalhe !== "Previsto" && e.detalhe !== "Prevista" ? e.detalhe : "",
                    e.responsavel ? `por ${e.responsavel}` : ""].filter(Boolean).join(" · ");
    if (extras) li.appendChild(el("span", "detalhe", extras));
    destino.appendChild(li);
  });
}

function desenharCiclo() {
  const atual = dados.ciclo_atual;
  const conteudo = $("conteudoCiclo");
  conteudo.innerHTML = "";
  $("btnCobertura").hidden = !(podeGerenciar && !atual);
  $("btnEvento").hidden = !atual;
  $("btnParto").hidden = !(podeGerenciar && atual);

  if (!atual) {
    conteudo.appendChild(el("p", "alertas-vazio", podeGerenciar
      ? "Esta vaca não tem ciclo em andamento. Registre a cobertura para começar o acompanhamento."
      : "Esta vaca não tem ciclo em andamento. Peça a um gerente para registrar a cobertura."));
    $("secLinha").hidden = true;
    return;
  }

  const resumo = el("div", "resumo-ciclo");
  const campo = (rotulo, valor) => { const d = el("div"); d.append(el("small", "", rotulo), el("strong", "", valor)); return d; };
  const situacao = el("div");
  situacao.append(el("small", "", "Situação"), el("span", "selo", STATUS[atual.status] || atual.status));
  resumo.append(
    situacao,
    campo("Cobertura", `${formatarData(atual.data_cobertura)} · ${COBERTURA[atual.tipo_cobertura] || ""}`),
    campo("Touro", atual.touro),
    campo("Parto previsto", `${formatarData(atual.data_prevista_parto)} (${textoDias(atual.dias_para_parto)})`)
  );
  conteudo.appendChild(resumo);
  if (atual.observacoes) conteudo.appendChild(el("p", "dica", `Observações: ${atual.observacoes}`));

  $("secLinha").hidden = false;
  desenharLinha(atual.linha_do_tempo, $("linhaTempo"));
  $("dicaLinha").hidden = !atual.linha_do_tempo.some(e => e.previsto);
}

function desenharCrias() {
  const corpo = $("corpoCrias");
  corpo.innerHTML = "";
  $("secCrias").hidden = dados.bezerros.length === 0;
  dados.bezerros.forEach(b => {
    const tr = document.createElement("tr");
    const tdNome = document.createElement("td");
    if (b.ativo) {
      const a = el("a", "", b.nome);
      a.href = `animal.html?id=${b.id}`;
      tdNome.appendChild(a);
    } else {
      tdNome.textContent = b.nome;
    }
    tr.appendChild(tdNome);
    [b.brinco || "-", b.sexo, formatarData(b.data_nascimento),
     b.ativo ? (b.status || "Ativo") : `Baixa${b.baixa_motivo ? " (" + b.baixa_motivo.toLowerCase() + ")" : ""}`].forEach(v => {
      const td = document.createElement("td");
      td.textContent = v;
      tr.appendChild(td);
    });
    corpo.appendChild(tr);
  });
}

function desenharHistorico() {
  const area = $("historico");
  area.innerHTML = "";
  $("secHistorico").hidden = dados.historico.length === 0;
  dados.historico.forEach(c => {
    const det = el("details", "ciclo-antigo");
    det.appendChild(el("summary", "", `Cobertura de ${formatarData(c.data_cobertura)} · ${STATUS[c.status] || c.status}`));
    const info = [`${COBERTURA[c.tipo_cobertura] || "Cobertura"} com ${c.touro}`];
    if (c.data_encerramento) info.push(`encerrado em ${formatarData(c.data_encerramento)}`);
    det.appendChild(el("p", "dica", info.join(" · ")));
    if (c.parto) {
      const p = c.parto;
      const partoInfo = [`Parto em ${formatarData(p.data_parto)}`, p.tipo_parto === "gemeos" ? "gêmeos" : "único"];
      if (p.tipo_assistencia) partoInfo.push(ASSISTENCIA[p.tipo_assistencia].toLowerCase());
      det.appendChild(el("p", "", partoInfo.join(" · ")));
      const lista = el("ul", "alertas-lista");
      p.bezerros.forEach(b => {
        const li = document.createElement("li");
        const esq = b.animal_id ? el("a", "", `${b.animal || "Bezerro"} (${b.sexo})`) : el("span", "", `Bezerro ${b.ordem} (${b.sexo})`);
        if (b.animal_id) esq.href = `animal.html?id=${b.animal_id}`;
        const dir = el("span", "detalhe", [SITUACAO[b.situacao] || b.situacao, b.peso_nascimento ? FW_CONFIG.peso(b.peso_nascimento) : "", b.causa || ""].filter(Boolean).join(" · "));
        li.append(esq, dir);
        lista.appendChild(li);
      });
      det.appendChild(lista);
    }
    const linha = el("ol", "linha-tempo");
    det.appendChild(linha);
    desenharLinha(c.linha_do_tempo.filter(e => !e.previsto), linha);
    area.appendChild(det);
  });
}

async function carregar() {
  await FW_CONFIG.pronto;
  try {
    dados = await api(`/reproducao/${id}`);
  } catch (erro) {
    $("titulo").textContent = "Módulo de bezerros";
    $("erroPagina").textContent = erro.message;
    $("erroPagina").hidden = false;
    return;
  }
  const v = dados.vaca;
  $("titulo").textContent = `Bezerros de ${v.nome}`;
  $("sub").textContent = `Brinco ${v.brinco || "-"} · ${v.tipo || "-"}${v.lote ? " · Lote " + v.lote : ""}`;
  $("linkVoltar").href = `animal.html?id=${id}`;
  document.querySelectorAll(".nome-modal").forEach(p => { p.textContent = v.nome; });
  $("secCiclo").hidden = false;
  desenharCiclo();
  desenharCrias();
  desenharHistorico();
}

// ---------- modais ----------
function abrir(modal) {
  modal.querySelector(".erro").hidden = true;
  modal.showModal();
}

function mostrarErro(modal, mensagem) {
  const p = modal.querySelector(".erro");
  p.textContent = mensagem;
  p.hidden = false;
}

document.querySelectorAll("[data-fechar]").forEach(b => b.addEventListener("click", () => $(b.dataset.fechar).close()));

// cobertura
async function carregarTouros() {
  const sel = $("cobTouroSel");
  sel.innerHTML = "";
  sel.add(new Option("Nenhum (informar abaixo)", ""));
  try {
    (await api("/touros")).touros.forEach(t => sel.add(new Option(`${t.nome}${t.brinco ? " (" + t.brinco + ")" : ""}`, t.id)));
  } catch (erro) { console.error(erro); }
}

function previsaoCobertura() {
  const dia = $("cobData").value;
  if (!dia) { $("cobPrevisao").textContent = ""; return; }
  const previsto = new Date(dia + "T00:00:00");
  previsto.setDate(previsto.getDate() + dados.config.gestacao_dias);
  $("cobPrevisao").textContent = `Parto previsto para ${previsto.toLocaleDateString("pt-BR")} (${dados.config.gestacao_dias} dias de gestação).`;
}

$("btnCobertura").addEventListener("click", async () => {
  $("formCobertura").reset();
  $("cobData").value = hoje();
  $("cobData").max = hoje();
  await carregarTouros();
  previsaoCobertura();
  abrir($("modalCobertura"));
});
$("cobData").addEventListener("input", previsaoCobertura);
$("cobTouroSel").addEventListener("change", () => { if ($("cobTouroSel").value) $("cobTouroTxt").value = ""; });
$("cobTouroTxt").addEventListener("input", () => { if ($("cobTouroTxt").value) $("cobTouroSel").value = ""; });

$("formCobertura").addEventListener("submit", async e => {
  e.preventDefault();
  try {
    const resposta = await api(`/reproducao/${id}/cobertura`, {
      method: "POST",
      body: JSON.stringify({
        tipo_cobertura: $("cobTipo").value,
        data_cobertura: $("cobData").value,
        touro_id: $("cobTouroSel").value ? Number($("cobTouroSel").value) : null,
        touro_texto: $("cobTouroTxt").value.trim(),
        observacoes: $("cobObs").value.trim()
      })
    });
    $("modalCobertura").close();
    avisoPagina(`Cobertura registrada. Parto previsto para ${formatarData(resposta.data_prevista_parto)}.`);
    carregar();
  } catch (erro) { mostrarErro($("modalCobertura"), erro.message); }
});

// evento
function ajustarCamposEvento() {
  const tipo = $("evTipo").value;
  $("evResultadoBox").hidden = tipo !== "diagnostico";
  $("evTituloBox").hidden = tipo !== "acompanhamento";
  $("evOutroBox").hidden = !(tipo === "acompanhamento" && $("evTitulo").value === "__outro");
  const aviso = $("evAviso");
  aviso.hidden = !["aborto", "diagnostico"].includes(tipo);
  aviso.textContent = tipo === "aborto" ? "O aborto encerra o ciclo atual."
    : "Diagnóstico negativo encerra o ciclo como vazia; positivo marca a vaca como gestante.";
}

$("btnEvento").addEventListener("click", () => {
  $("formEvento").reset();
  $("evData").value = hoje();
  $("evData").max = hoje();
  ajustarCamposEvento();
  abrir($("modalEvento"));
});
$("evTipo").addEventListener("change", ajustarCamposEvento);
$("evTitulo").addEventListener("change", ajustarCamposEvento);

$("formEvento").addEventListener("submit", async e => {
  e.preventDefault();
  const tipo = $("evTipo").value;
  const corpo = { tipo, data: $("evData").value, observacoes: $("evObs").value.trim() };
  if (tipo === "diagnostico") corpo.resultado = $("evResultado").value;
  if (tipo === "acompanhamento") corpo.titulo = $("evTitulo").value === "__outro" ? $("evOutro").value.trim() : $("evTitulo").value;
  try {
    await api(`/ciclos/${dados.ciclo_atual.id}/eventos`, { method: "POST", body: JSON.stringify(corpo) });
    $("modalEvento").close();
    avisoPagina("Evento registrado.");
    carregar();
  } catch (erro) { mostrarErro($("modalEvento"), erro.message); }
});

// parto
function blocoCria(n, total) {
  const bloco = el("fieldset", "bloco-cria");
  bloco.dataset.ordem = n;
  bloco.appendChild(el("h3", "", total > 1 ? `Bezerro ${n}` : "Bezerro"));
  const grade = el("div", "grade");
  bloco.appendChild(grade);
  const campo = (rotulo, controle, largo) => {
    const c = el("div", "campo" + (largo ? " largo" : ""));
    c.append(el("label", "", rotulo), controle);
    grade.appendChild(c);
    return c;
  };
  const sexo = document.createElement("select");
  sexo.dataset.campo = "sexo";
  sexo.add(new Option("Fêmea", "Fêmea"));
  sexo.add(new Option("Macho", "Macho"));
  const situacao = document.createElement("select");
  situacao.dataset.campo = "situacao";
  Object.entries(SITUACAO).forEach(([valor, rotulo]) => situacao.add(new Option(rotulo, valor)));
  const peso = Object.assign(document.createElement("input"), { type: "number", min: "0", step: "0.1" });
  peso.dataset.campo = "peso";
  const brinco = Object.assign(document.createElement("input"), { type: "text", maxLength: 30, placeholder: "Em branco: gerado sozinho" });
  brinco.dataset.campo = "brinco";
  const nome = Object.assign(document.createElement("input"), { type: "text", maxLength: 80, placeholder: `Em branco: Cria de ${dados.vaca.nome}` });
  nome.dataset.campo = "nome";
  const raca = Object.assign(document.createElement("input"), { type: "text", maxLength: 80, placeholder: dados.vaca.raca ? `Em branco: ${dados.vaca.raca}` : "" });
  raca.dataset.campo = "raca";
  const causa = Object.assign(document.createElement("input"), { type: "text", maxLength: 200, placeholder: "Se souber" });
  causa.dataset.campo = "causa";
  const manter = document.createElement("input");
  manter.type = "checkbox";
  manter.dataset.campo = "manter_historico";

  campo("Sexo", sexo);
  campo("Situação", situacao);
  campo("Peso ao nascer (kg)", peso);
  const cBrinco = campo("Brinco", brinco);
  const cNome = campo("Nome", nome);
  const cRaca = campo("Raça", raca);
  const cCausa = campo("Causa (opcional)", causa, true);
  const cManter = el("div", "opcao");
  const idManter = `manter${n}`;
  manter.id = idManter;
  cManter.append(manter, Object.assign(el("label", "", "Manter no histórico do rebanho (fica como baixa por morte)"), { htmlFor: idManter }));
  cManter.style.gridColumn = "1 / -1";
  grade.appendChild(cManter);

  const ajustar = () => {
    const vivo = situacao.value === "vivo";
    [cBrinco, cNome, cRaca].forEach(c => { c.hidden = !vivo && !manter.checked; });
    cCausa.hidden = vivo;
    cManter.hidden = situacao.value !== "faleceu_apos";
    if (situacao.value === "natimorto") manter.checked = false;
  };
  situacao.addEventListener("change", ajustar);
  manter.addEventListener("change", ajustar);
  ajustar();
  return bloco;
}

function desenharBlocos() {
  const total = $("parTipo").value === "gemeos" ? Number($("parQtd").value) : 1;
  $("parQtdBox").hidden = $("parTipo").value !== "gemeos";
  const area = $("blocosCrias");
  const anteriores = [...area.querySelectorAll(".bloco-cria")];
  area.innerHTML = "";
  for (let n = 1; n <= total; n++) area.appendChild(anteriores[n - 1] || blocoCria(n, total));
  area.querySelectorAll(".bloco-cria h3").forEach((h, i) => { h.textContent = total > 1 ? `Bezerro ${i + 1}` : "Bezerro"; });
}

$("btnParto").addEventListener("click", () => {
  $("formParto").reset();
  $("parData").value = hoje();
  $("parData").max = hoje();
  $("blocosCrias").innerHTML = "";
  desenharBlocos();
  abrir($("modalParto"));
});
$("parTipo").addEventListener("change", desenharBlocos);
$("parQtd").addEventListener("change", desenharBlocos);

$("formParto").addEventListener("submit", async e => {
  e.preventDefault();
  const bezerros = [...$("blocosCrias").querySelectorAll(".bloco-cria")].map(bloco => {
    const valor = nome => bloco.querySelector(`[data-campo="${nome}"]`);
    return {
      sexo: valor("sexo").value, situacao: valor("situacao").value,
      peso: valor("peso").value === "" ? null : Number(valor("peso").value),
      brinco: valor("brinco").value.trim(), nome: valor("nome").value.trim(), raca: valor("raca").value.trim(),
      causa: valor("causa").value.trim(), manter_historico: valor("manter_historico").checked
    };
  });
  try {
    const resposta = await api(`/ciclos/${dados.ciclo_atual.id}/parto`, {
      method: "POST",
      body: JSON.stringify({
        data_parto: $("parData").value, tipo_parto: $("parTipo").value,
        tipo_assistencia: $("parAssist").value || null, observacoes: $("parObs").value.trim(), bezerros
      })
    });
    $("modalParto").close();
    const vivos = resposta.bezerros.filter(b => b.situacao === "vivo").length;
    avisoPagina(vivos
      ? `Parto registrado. ${vivos === 1 ? "O bezerro foi cadastrado" : vivos + " bezerros foram cadastrados"} e ${resposta.tarefas_geradas} tarefa(s) de manejo foram criadas.`
      : "Parto registrado e ciclo encerrado.");
    carregar();
  } catch (erro) { mostrarErro($("modalParto"), erro.message); }
});

// ---------- início ----------
(async () => {
  try {
    const perfil = await api("/api/perfil");
    podeGerenciar = perfil.nivel === "gerente" || perfil.nivel === "dono";
  } catch (_) { podeGerenciar = false; }
  carregar();
})();
