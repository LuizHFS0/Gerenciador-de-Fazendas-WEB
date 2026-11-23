// Lote em parceria: cadastro em lote, peso de entrada, alertas e saída.
// Carregue DEPOIS de animais.js. A interface é injetada aqui, então o animais.html só precisa deste <script>.
(function () {
  const $ = id => document.getElementById(id);
  const SEXOS = ["Macho", "Fêmea", "Macho (Castrado)"];
  const MOTIVOS = ["Abate", "Venda", "Devolução ao parceiro", "Morte"];

  // ---------- Estilo ----------
  const estilo = document.createElement("style");
  estilo.textContent = `
    [hidden] { display: none !important; }
    .linha-grupo { display: flex; gap: 8px; align-items: center; margin-bottom: 8px; flex-wrap: wrap; }
    .linha-grupo .g-qtd { width: 90px; }
    .linha-grupo .g-raca { flex: 1; min-width: 120px; }
    .linha-grupo .sep { color: #6a7468; font-weight: 700; }
    .pc-bloco { margin-top: 12px; }
    .pc-bloco > legend, .pc-titulo { font-weight: 700; font-size: .9rem; margin-bottom: 6px; }
    #alertaParceria p { margin: 0 0 6px; padding: 10px 14px; border-radius: 6px; font-weight: 600; }
    .alerta-aviso { background: #fff4d6; border-left: 4px solid #d9b25f; color: #5b4310; }
    .alerta-urgente { background: #fde4e0; border-left: 4px solid #b3392b; color: #6b1d14; }
    .grupo-saida { border: 1px solid #dcd8c8; border-radius: 6px; padding: 8px 10px; margin-bottom: 8px; }
    .grupo-saida .topo-grupo { display: flex; justify-content: space-between; align-items: center; gap: 10px; }
    .grupo-saida input[type=number] { width: 90px; }
    .grupo-saida details { margin-top: 6px; }
    .grupo-saida .animais-grupo { display: grid; grid-template-columns: repeat(auto-fill, minmax(190px, 1fr)); gap: 2px 12px; margin-top: 6px; max-height: 160px; overflow: auto; }
    #tabelaPesos { width: 100%; }
    #pesosScroll { max-height: 50vh; overflow: auto; }
  `;
  document.head.appendChild(estilo);

  // ---------- Estrutura injetada ----------
  const form = $("formCadastro");
  const grade = form.querySelector(".grade");
  const titulo = form.querySelector("h2");
  titulo.id = "tituloCadastro";

  const blocoIndividual = document.createElement("div");
  blocoIndividual.id = "blocoIndividual";
  grade.before(blocoIndividual);
  blocoIndividual.appendChild(grade);

  const seletor = document.createElement("div");
  seletor.className = "campo largo";
  seletor.innerHTML = `
    <label for="tipoCadastro">Tipo de cadastro</label>
    <select id="tipoCadastro">
      <option value="individual">Animal individual</option>
      <option value="parceria">Lote em parceria</option>
      <option value="comum">Lote comum</option>
    </select>`;
  titulo.after(seletor);

  const blocoParceria = document.createElement("div");
  blocoParceria.id = "blocoParceria";
  blocoParceria.hidden = true;
  blocoParceria.innerHTML = `
    <div class="grade">
      <div class="campo"><label for="pLoteNome">Nome do lote</label><input type="text" id="pLoteNome"></div>
      <div class="campo"><label for="pTamanho">Tamanho (ha)</label><input type="number" id="pTamanho" min="0" step="0.01"></div>
      <div class="campo"><label for="pLocalizacao">Localização</label><input type="text" id="pLocalizacao"></div>
      <div class="campo"><label for="pDescricao">Descrição</label><input type="text" id="pDescricao"></div>
      <div class="campo largo" id="campoParceiro">
        <label for="pParceiro">Fazendeiro parceiro (participação no lucro)</label>
        <input type="text" id="pParceiro" list="listaParceiros" autocomplete="off">
        <datalist id="listaParceiros"></datalist>
      </div>
    </div>
    <fieldset class="pc-bloco" style="border:0;padding:0">
      <legend>Animais do lote (quantidade | raça | sexo)</legend>
      <div id="gruposParceria"></div>
      <button type="button" class="secundario" id="btnMaisGrupo" aria-label="Adicionar outro grupo">+</button>
    </fieldset>
    <label class="pc-bloco" style="display:block"><input type="checkbox" id="pPesoIndividual"> Informar o peso de cada animal depois de salvar</label>
    <div class="grade pc-bloco">
      <div class="campo" id="campoPrevisto"><label for="pDataPrevista">Data prevista de saída</label><input type="date" id="pDataPrevista"></div>
      <div class="campo largo"><label for="pObs">Observações</label><textarea id="pObs" rows="3"></textarea></div>
    </div>
    <div id="blocoAutorizacao" class="pc-bloco" hidden>
      <label for="pSenha">Senha de confirmação do gerente</label>
      <input type="password" id="pSenha" autocomplete="off">
    </div>`;
  blocoIndividual.after(blocoParceria);

  const botoes = document.querySelector(".botoes");
  const btnSaida = document.createElement("button");
  btnSaida.type = "button";
  btnSaida.id = "btnSaidaLote";
  btnSaida.textContent = "Saída de lote";
  botoes.appendChild(btnSaida);

  const alertaCaixa = document.createElement("div");
  alertaCaixa.id = "alertaParceria";
  alertaCaixa.hidden = true;
  document.querySelector(".barra-acoes").before(alertaCaixa);

  document.body.insertAdjacentHTML("beforeend", `
    <dialog id="modalPesosParceria">
      <h2>Peso de entrada</h2>
      <p class="dica">Preencha só os que quiser (kg). Os vazios ficam sem peso.</p>
      <div id="pesosScroll"><table id="tabelaPesos"><thead><tr><th>Animal</th><th>Brinco</th><th>Peso (kg)</th></tr></thead><tbody id="corpoPesos"></tbody></table></div>
      <p class="erro" id="erroPesos" role="alert" hidden></p>
      <div class="rodape-modal">
        <button type="button" class="secundario" id="pularPesos">Pular</button>
        <button type="button" id="salvarPesos">Salvar pesos</button>
      </div>
    </dialog>

    <dialog id="modalSaidaLote">
      <form id="formSaidaLote" novalidate>
        <h2>Saída de lote em parceria</h2>
        <div class="campo largo"><label for="sLote">Lote</label><select id="sLote"></select></div>
        <p class="dica" id="sResumo"></p>
        <div class="pc-titulo">Quantos animais saem de cada grupo</div>
        <div id="sGrupos"></div>
        <div class="grade" style="margin-top:12px">
          <div class="campo"><label for="sMotivo">Motivo</label><select id="sMotivo"></select></div>
          <div class="campo"><label for="sData">Data da saída</label><input type="date" id="sData"></div>
          <div class="campo largo"><label for="sDestino">Destino</label><input type="text" id="sDestino" maxlength="120"></div>
          <div class="campo largo"><label for="sObs">Observações</label><textarea id="sObs" rows="2" maxlength="500"></textarea></div>
        </div>
        <div id="sAutorizacao" class="pc-bloco" hidden>
          <label for="sSenha">Senha de confirmação do gerente</label>
          <input type="password" id="sSenha" autocomplete="off">
        </div>
        <label class="pc-bloco" style="display:block"><input type="checkbox" id="sPesoIndividual"> Informar o peso de cada animal que sai</label>
        <p class="dica">Sem escolha manual, saem os animais mais antigos de cada grupo. Os registros ficam guardados.</p>
        <p class="erro" id="erroSaida" role="alert" hidden></p>
        <div class="rodape-modal">
          <button type="button" class="secundario" data-fechar="modalSaidaLote">Cancelar</button>
          <button type="submit" class="perigo" id="confirmarSaida">Registrar saída</button>
        </div>
      </form>
    </dialog>

    <dialog id="modalPesosSaida">
      <h2>Peso de saída</h2>
      <p class="dica">Preencha só os que quiser (kg). O valor em cinza é o último peso registrado.</p>
      <div id="pesosSaidaScroll" style="max-height:50vh;overflow:auto"><table style="width:100%"><thead><tr><th>Animal</th><th>Brinco</th><th>Peso (kg)</th></tr></thead><tbody id="corpoPesosSaida"></tbody></table></div>
      <p class="erro" id="erroPesosSaida" role="alert" hidden></p>
      <div class="rodape-modal">
        <button type="button" class="secundario" id="voltarPesosSaida">Voltar</button>
        <button type="button" class="perigo" id="confirmarPesosSaida">Confirmar saída</button>
      </div>
    </dialog>

    <dialog id="modalLoteVazio">
      <h2>Lote sem animais</h2>
      <p>Todos os animais desse lote saíram. Para desativá-lo, use Utilitários → Gestão de lotes.</p>
      <div class="rodape-modal"><button type="button" data-fechar="modalLoteVazio">Entendi</button></div>
    </dialog>`);

  // fecha os modais novos (o animais.js só ligou os [data-fechar] que já existiam)
  document.querySelectorAll("#modalSaidaLote [data-fechar], #modalLoteVazio [data-fechar]").forEach(b =>
    b.addEventListener("click", () => $(b.dataset.fechar).close()));

  // ---------- Utilidades ----------
  const hoje = () => {
    const d = new Date(), p = n => String(n).padStart(2, "0");
    return `${d.getFullYear()}-${p(d.getMonth() + 1)}-${p(d.getDate())}`;
  };
  const mostrar = (el, texto) => { el.textContent = texto; el.hidden = false; };
  const lerJson = r => r.json().catch(() => ({}));
  const senha = campo => (campo.value ? { senha: campo.value } : null);

  // ---------- Modo do cadastro ----------
  const ativo = () => $("tipoCadastro").value === "parceria";

  function aplicarModo() {
    const tipo = $("tipoCadastro").value;
    const lote = tipo !== "individual";
    const parceria = tipo === "parceria";
    blocoIndividual.hidden = lote;
    blocoParceria.hidden = !lote;
    $("campoParceiro").hidden = !parceria;
    $("campoPrevisto").hidden = !parceria;
    $("erroCadastro").hidden = true;
    titulo.textContent = !lote ? "Cadastrar animal" : parceria ? "Cadastrar lote em parceria" : "Cadastrar lote comum";
    if (parceria) $("pDataPrevista").min = hoje();
    if (lote && $("gruposParceria").children.length === 0) adicionarGrupo();
  }

  function adicionarGrupo() {
    const linha = document.createElement("div");
    linha.className = "linha-grupo";
    linha.innerHTML = `
      <input type="number" class="g-qtd" min="1" step="1" placeholder="Qtd" aria-label="Quantidade">
      <span class="sep">|</span>
      <input type="text" class="g-raca" placeholder="Raça" aria-label="Raça">
      <select class="g-sexo" aria-label="Sexo">${SEXOS.map(s => `<option>${s}</option>`).join("")}</select>
      <button type="button" class="secundario" aria-label="Remover grupo">×</button>`;
    linha.querySelector("button").addEventListener("click", () => {
      if ($("gruposParceria").children.length > 1) linha.remove();
    });
    $("gruposParceria").appendChild(linha);
    linha.querySelector(".g-qtd").focus();
  }

  $("tipoCadastro").addEventListener("change", aplicarModo);
  $("btnMaisGrupo").addEventListener("click", adicionarGrupo);
  form.addEventListener("reset", () => setTimeout(() => {
    $("gruposParceria").replaceChildren();
    $("blocoAutorizacao").hidden = true;
    aplicarModo();
  }, 0));

  async function carregarParceiros() {
    try {
      const r = await fetch("/parceiros");
      if (!r.ok) return;
      const { parceiros } = await r.json();
      $("listaParceiros").replaceChildren(...parceiros.map(p => new Option(p.nome)));
    } catch (e) { console.error("Falha ao carregar parceiros:", e); }
  }
  $("btnCadastrar").addEventListener("click", carregarParceiros);

  // ---------- Cadastro do lote ----------
  async function enviar() {
    const erro = $("erroCadastro");
    const dados = {
      lote: {
        nome: $("pLoteNome").value.trim(), tamanho: $("pTamanho").value,
        localizacao: $("pLocalizacao").value.trim(), descricao: $("pDescricao").value.trim()
      },
      tipo: $("tipoCadastro").value === "comum" ? "comum" : "parceria",
      parceiro: $("pParceiro").value.trim(),
      data_prevista_saida: $("pDataPrevista").value,
      observacoes: $("pObs").value.trim(),
      grupos: [...document.querySelectorAll("#gruposParceria .linha-grupo")].map(l => ({
        quantidade: l.querySelector(".g-qtd").value,
        raca: l.querySelector(".g-raca").value.trim(),
        sexo: l.querySelector(".g-sexo").value
      })),
      autorizacao: senha($("pSenha"))
    };

    if (!dados.lote.nome) return mostrar(erro, "Informe o nome do lote.");
    if (dados.tipo === "parceria" && !dados.parceiro) return mostrar(erro, "Informe o nome do fazendeiro parceiro.");
    if (dados.grupos.some(g => !(Number(g.quantidade) >= 1) || !g.raca)) {
      return mostrar(erro, "Preencha a quantidade e a raça de todos os grupos.");
    }
    if (dados.tipo === "parceria" && !dados.data_prevista_saida) return mostrar(erro, "Informe a data prevista de saída.");

    const botao = form.querySelector('button[type="submit"]');
    botao.disabled = true;
    try {
      const r = await fetch("/cadastrarLoteParceria", {
        method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(dados)
      });
      const corpo = await lerJson(r);
      if (r.status === 403) {
        $("blocoAutorizacao").hidden = false;
        $("pSenha").focus();
        throw new Error(corpo.detail || "Peça a senha de confirmação do gerente.");
      }
      if (!r.ok) throw new Error(corpo.detail || "Erro ao cadastrar o lote em parceria.");

      $("modalCadastro").close();
      await carregarAnimais();
      carregarAlertas();
      if ($("pPesoIndividual").checked) abrirPesos(corpo.lote_id, corpo.animais);
    } catch (e) {
      mostrar(erro, e.message);
    } finally {
      botao.disabled = false;
    }
  }

  // ---------- Peso de entrada ----------
  let loteDosPesos = null;

  function abrirPesos(loteId, lista) {
    loteDosPesos = loteId;
    $("erroPesos").hidden = true;
    $("corpoPesos").replaceChildren(...lista.map(a => {
      const tr = document.createElement("tr");
      tr.dataset.id = a.id;
      [a.nome, a.brinco].forEach(v => { const td = document.createElement("td"); td.textContent = v; tr.appendChild(td); });
      const td = document.createElement("td");
      const input = document.createElement("input");
      input.type = "number"; input.min = "0"; input.step = "0.1";
      input.setAttribute("aria-label", `Peso de ${a.nome}`);
      td.appendChild(input); tr.appendChild(td);
      return tr;
    }));
    $("modalPesosParceria").showModal();
  }

  $("pularPesos").addEventListener("click", () => $("modalPesosParceria").close());
  $("salvarPesos").addEventListener("click", async () => {
    const pesos = [...document.querySelectorAll("#corpoPesos tr")]
      .map(tr => ({ animal_id: Number(tr.dataset.id), peso: tr.querySelector("input").value }))
      .filter(p => p.peso !== "")
      .map(p => ({ ...p, peso: Number(p.peso) }));
    if (pesos.length === 0) return $("modalPesosParceria").close();
    if (pesos.some(p => !(p.peso > 0))) return mostrar($("erroPesos"), "Os pesos devem ser maiores que zero.");
    try {
      const r = await fetch(`/pesosEntradaLote/${loteDosPesos}`, {
        method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ pesos })
      });
      if (!r.ok) throw new Error((await lerJson(r)).detail || "Erro ao salvar os pesos.");
      $("modalPesosParceria").close();
      await carregarAnimais();
    } catch (e) {
      mostrar($("erroPesos"), e.message);
    }
  });

  // ---------- Alertas ----------
  function textoAlerta(a) {
    const base = `Lote ${a.lote}${a.parceiro ? ` (parceiro ${a.parceiro})` : ""}: ${a.animais} animais`;
    if (a.dias_restantes < 0) return `${base} — saída prevista vencida há ${-a.dias_restantes} dia(s).`;
    if (a.dias_restantes === 0) return `${base} — saída prevista para hoje.`;
    return `${base} — saída prevista em ${a.dias_restantes} dia(s) (${formatarData(a.data_prevista_saida)}).`;
  }

  async function carregarAlertas() {
    try {
      const r = await fetch("/alertasParceria");
      if (!r.ok) throw new Error(r.status);
      const { alertas } = await r.json();
      alertaCaixa.replaceChildren(...alertas.map(a => {
        const p = document.createElement("p");
        p.className = `alerta-${a.nivel}`;
        p.textContent = textoAlerta(a);
        return p;
      }));
      alertaCaixa.hidden = alertas.length === 0;
    } catch (e) {
      alertaCaixa.hidden = true;
    }
  }

  // ---------- Saída do lote ----------
  let lotesSaida = [];

  function desenharGruposSaida() {
    const lote = lotesSaida.find(l => String(l.id) === $("sLote").value);
    $("sResumo").textContent = lote
      ? `Parceiro: ${lote.parceiro || "-"} · saída prevista: ${formatarData(lote.data_prevista_saida)} · ${lote.animais} animais no lote`
      : "";
    $("sGrupos").replaceChildren();
    if (!lote) return;

    lote.grupos.forEach(g => {
      const bloco = document.createElement("div");
      bloco.className = "grupo-saida";
      bloco.dataset.raca = g.raca;
      bloco.dataset.sexo = g.sexo;

      const topo = document.createElement("div");
      topo.className = "topo-grupo";
      const rotulo = document.createElement("span");
      rotulo.textContent = `${g.raca || "Sem raça"} · ${g.sexo} (disponíveis: ${g.quantidade})`;
      const qtd = document.createElement("input");
      qtd.type = "number"; qtd.className = "s-qtd"; qtd.min = "0"; qtd.max = String(g.quantidade); qtd.value = "0";
      qtd.setAttribute("aria-label", `Quantidade de ${g.raca} ${g.sexo}`);
      topo.append(rotulo, qtd);

      const det = document.createElement("details");
      const resumo = document.createElement("summary");
      resumo.textContent = "Escolher animais manualmente";
      const lista = document.createElement("div");
      lista.className = "animais-grupo";
      animais.filter(a => a.lote === lote.nome && a.raca === g.raca && a.sexo === g.sexo).forEach(a => {
        const rot = document.createElement("label");
        const cx = document.createElement("input");
        cx.type = "checkbox"; cx.value = a.id;
        cx.addEventListener("change", () => {
          const marcados = lista.querySelectorAll("input:checked").length;
          qtd.disabled = marcados > 0;
          if (marcados > 0) qtd.value = String(marcados);
        });
        rot.append(cx, ` ${a.nome}`);
        lista.appendChild(rot);
      });
      det.append(resumo, lista);
      bloco.append(topo, det);
      $("sGrupos").appendChild(bloco);
    });
  }

  btnSaida.addEventListener("click", async () => {
    $("formSaidaLote").reset();
    pendente = null;
    pesosDigitados = {};
    $("erroSaida").hidden = true;
    $("sAutorizacao").hidden = true;
    $("sMotivo").replaceChildren(...MOTIVOS.map(m => new Option(m)));
    $("sData").value = hoje();
    $("sData").max = hoje();
    try {
      const r = await fetch("/lotesParceria");
      if (!r.ok) throw new Error(`Erro ${r.status}`);
      lotesSaida = (await r.json()).lotes.filter(l => l.animais > 0);
    } catch (e) {
      lotesSaida = [];
      mostrar($("erroSaida"), "Não foi possível carregar os lotes em parceria.");
    }
    $("sLote").replaceChildren(...lotesSaida.map(l => new Option(`${l.nome} — ${l.parceiro || "sem parceiro"}`, l.id)));
    if (lotesSaida.length === 0 && $("erroSaida").hidden) mostrar($("erroSaida"), "Não há lote em parceria com animais.");
    desenharGruposSaida();
    $("modalSaidaLote").showModal();
  });
  $("sLote").addEventListener("change", desenharGruposSaida);

  // ---------- Saída: envio (com ou sem peso de cada animal) ----------
  let pendente = null;          // saída esperando os pesos: { loteId, corpo, lista }
  let pesosDigitados = {};      // id -> texto digitado (não se perde se for preciso tentar de novo)

  // mesma regra do servidor: primeiro os escolhidos a dedo, depois os mais antigos (menor id) de cada grupo
  function animaisDaSaida(lote, grupos, idsManuais) {
    const doLote = animais.filter(a => a.lote === lote.nome).sort((x, y) => x.id - y.id);
    const escolhidos = [...idsManuais];
    grupos.forEach(g => {
      const resto = doLote.filter(a => a.raca === g.raca && a.sexo === g.sexo && !escolhidos.includes(a.id));
      escolhidos.push(...resto.slice(0, g.quantidade).map(a => a.id));
    });
    return escolhidos.map(id => doLote.find(a => a.id === id)).filter(Boolean);
  }

  async function enviarSaida(loteId, corpo) {
    try {
      const r = await fetch(`/saidaLoteParceria/${loteId}`, {
        method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(corpo)
      });
      const resp = await lerJson(r);
      if (r.status === 403) {
        $("modalPesosSaida").close();
        $("sAutorizacao").hidden = false;
        $("sSenha").focus();
        throw new Error(resp.detail || "Peça a senha de confirmação do gerente.");
      }
      if (!r.ok) throw new Error(resp.detail || "Erro ao registrar a saída.");
      $("modalPesosSaida").close();
      $("modalSaidaLote").close();
      await carregarAnimais();
      carregarAlertas();
      if (resp.lote_vazio) $("modalLoteVazio").showModal();
    } catch (err) {
      mostrar($("modalPesosSaida").open ? $("erroPesosSaida") : $("erroSaida"), err.message);
    }
  }

  function abrirPesosSaida() {
    $("erroPesosSaida").hidden = true;
    $("corpoPesosSaida").replaceChildren(...pendente.lista.map(a => {
      const tr = document.createElement("tr");
      tr.dataset.id = a.id;
      [a.nome, a.brinco].forEach(v => { const td = document.createElement("td"); td.textContent = v; tr.appendChild(td); });
      const td = document.createElement("td");
      const input = document.createElement("input");
      input.type = "number"; input.min = "0"; input.step = "0.1";
      input.value = pesosDigitados[a.id] ?? "";
      input.placeholder = a.peso ?? "";
      input.setAttribute("aria-label", `Peso de saída de ${a.nome}`);
      td.appendChild(input); tr.appendChild(td);
      return tr;
    }));
    $("modalPesosSaida").showModal();
  }

  $("formSaidaLote").addEventListener("submit", async e => {
    e.preventDefault();
    const erro = $("erroSaida");
    erro.hidden = true;
    const loteId = $("sLote").value;
    if (!loteId) return mostrar(erro, "Escolha um lote.");
    if (!$("sData").value) return mostrar(erro, "Informe a data da saída.");

    const grupos = [], animalIds = [];
    document.querySelectorAll("#sGrupos .grupo-saida").forEach(bloco => {
      const marcados = [...bloco.querySelectorAll("input[type=checkbox]:checked")].map(c => Number(c.value));
      if (marcados.length > 0) return animalIds.push(...marcados);
      const n = Number(bloco.querySelector(".s-qtd").value);
      if (n > 0) grupos.push({ raca: bloco.dataset.raca, sexo: bloco.dataset.sexo, quantidade: n });
    });
    if (grupos.length === 0 && animalIds.length === 0) {
      return mostrar(erro, "Informe quantos animais saem (ou escolha-os manualmente).");
    }

    const base = {
      motivo: $("sMotivo").value, data: $("sData").value, destino: $("sDestino").value.trim(),
      observacoes: $("sObs").value.trim(), autorizacao: senha($("sSenha"))
    };

    if ($("sPesoIndividual").checked) {
      // descobre quem vai sair para pedir o peso de cada um; o envio leva a lista exata de animais
      const lote = lotesSaida.find(l => String(l.id) === loteId);
      const esperado = animalIds.length + grupos.reduce((soma, g) => soma + g.quantidade, 0);
      const lista = animaisDaSaida(lote, grupos, animalIds);
      if (lista.length !== esperado) {
        return mostrar(erro, "A lista de animais mudou. Feche esta janela, abra de novo e tente outra vez.");
      }
      pendente = { loteId, corpo: { ...base, grupos: [], animal_ids: lista.map(a => a.id) }, lista };
      return abrirPesosSaida();
    }

    const botao = $("confirmarSaida");
    botao.disabled = true;
    await enviarSaida(loteId, { ...base, grupos, animal_ids: animalIds });
    botao.disabled = false;
  });

  $("voltarPesosSaida").addEventListener("click", () => $("modalPesosSaida").close());
  $("confirmarPesosSaida").addEventListener("click", async () => {
    if (!pendente) return;
    const pesos = {};
    for (const tr of document.querySelectorAll("#corpoPesosSaida tr")) {
      const texto = tr.querySelector("input").value;
      pesosDigitados[tr.dataset.id] = texto;
      if (texto === "") continue;
      if (!(Number(texto) > 0)) return mostrar($("erroPesosSaida"), "Os pesos devem ser maiores que zero.");
      pesos[tr.dataset.id] = Number(texto);
    }
    const botao = $("confirmarPesosSaida");
    botao.disabled = true;
    await enviarSaida(pendente.loteId, { ...pendente.corpo, pesos });
    botao.disabled = false;
  });

  window.Parceria = { ativo, enviar, carregarAlertas };
  carregarAlertas();
})();
