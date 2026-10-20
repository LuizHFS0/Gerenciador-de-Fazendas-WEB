let contexto = null;      // { data, responsavel, lote } depois de confirmado
let entradas = [];        // [{ id, nome, manha: <input>, tarde: <input> }]

const formInicio = $("formInicio");
const erroInicio = $("erroInicio");
const modalConfirma = $("modalConfirma");
const formMedicao = $("formMedicao");
const erroMedicao = $("erroMedicao");

async function iniciar() {
  $("data").value = hojeISO();
  $("data").max = hojeISO();
  try {
    await carregarLotes($("lote"), "Selecione o lote");
  } catch (erro) {
    mostrarMensagem(erroInicio, erro.message);
  }
}

function travarInicio(travar) {
  ["data", "responsavel", "lote", "btnConfirmaLote"].forEach(id => { $(id).disabled = travar; });
  $("avisoTravado").hidden = !travar;
}

// ---------- Passo 1: dados e confirmação do lote ----------
formInicio.addEventListener("submit", e => {
  e.preventDefault();
  erroInicio.hidden = true;

  const data = $("data").value;
  const responsavel = $("responsavel").value.trim();
  const lote = $("lote").value;

  if (!data || !responsavel || !lote) {
    mostrarMensagem(erroInicio, "Preencha a data, o responsável e o lote.");
    return;
  }
  if (data > hojeISO()) {
    mostrarMensagem(erroInicio, "A data não pode ser futura.");
    return;
  }

  contexto = { data, responsavel, lote };

  const lista = $("confirmaDados");
  lista.innerHTML = "";
  [["Lote", lote], ["Data", formatarData(data)], ["Responsável", responsavel]].forEach(([rotulo, valor]) => {
    const dt = document.createElement("dt");
    const dd = document.createElement("dd");
    dt.textContent = rotulo;
    dd.textContent = valor;
    lista.append(dt, dd);
  });
  modalConfirma.showModal();
});

$("okConfirma").addEventListener("click", async () => {
  modalConfirma.close();
  travarInicio(true);
  try {
    const dados = await api(`/vacasDoLote/${encodeURIComponent(contexto.lote)}?data=${contexto.data}`);
    desenharVacas(dados.vacas, dados.ignoradas || [], dados.total_animais || 0);
  } catch (erro) {
    travarInicio(false);          // não deu para carregar: libera para tentar de novo
    contexto = null;
    mostrarMensagem(erroInicio, erro.message);
  }
});

// ---------- Passo 2: leite de cada vaca ----------
function criarEntrada(vaca, turno, valor) {
  const input = document.createElement("input");
  input.type = "number";
  input.min = "0";
  input.step = "0.1";
  input.inputMode = "decimal";
  input.className = "entrada-litros";
  input.setAttribute("aria-label", `Leite da ${turno} de ${vaca.nome}`);
  if (valor !== null && valor !== undefined) input.value = valor;
  input.addEventListener("input", atualizarTotal);
  return input;
}

function desenharVacas(vacas, ignoradas, totalAnimais) {
  const corpo = $("corpoVacas");
  corpo.innerHTML = "";
  entradas = [];
  $("tituloMedicao").textContent = `Leite por vaca: lote ${contexto.lote}, ${formatarData(contexto.data)}`;

  if (vacas.length === 0) {
    const motivo = totalAnimais === 0
      ? "Este lote não tem animais cadastrados."
      : "Este lote não tem vacas em produção.";
    corpo.innerHTML = "";
    const tr = document.createElement("tr");
    const td = document.createElement("td");
    td.className = "vazio";
    td.colSpan = 3;
    td.textContent = `${motivo} Cancele e escolha outro lote.`;
    tr.appendChild(td);
    corpo.appendChild(tr);
    $("btnSalvar").hidden = true;
  } else {
    $("btnSalvar").hidden = false;
    vacas.forEach(vaca => {
      const tr = document.createElement("tr");

      const tdNome = document.createElement("td");
      tdNome.className = "esq";
      tdNome.textContent = vaca.nome;
      const brinco = document.createElement("span");
      brinco.className = "brinco";
      brinco.textContent = `Brinco ${vaca.brinco || "-"}`;
      tdNome.appendChild(brinco);
      tr.appendChild(tdNome);

      const manha = criarEntrada(vaca, "manhã", vaca.manha);
      const tarde = criarEntrada(vaca, "tarde", vaca.tarde);
      [manha, tarde].forEach(input => {
        const td = document.createElement("td");
        td.appendChild(input);
        tr.appendChild(td);
      });

      entradas.push({ id: vaca.id, nome: vaca.nome, manha, tarde });
      corpo.appendChild(tr);
    });
  }

  const fora = $("foraDaLista");
  if (ignoradas.length) {
    fora.textContent = "Só entram fêmeas do tipo Leite que não estão secas. Fora da lista: " +
      ignoradas.map(i => `${i.nome} (${i.motivo})`).join(", ") + ".";
    fora.hidden = false;
  } else {
    fora.hidden = true;
  }

  $("secaoMedicao").hidden = false;
  atualizarTotal();
  const primeiro = corpo.querySelector("input");
  if (primeiro) primeiro.focus();
  $("secaoMedicao").scrollIntoView({ behavior: "smooth", block: "start" });
}

function atualizarTotal() {
  let total = 0;
  entradas.forEach(e => {
    [e.manha, e.tarde].forEach(input => {
      const v = Number(input.value);
      if (input.value !== "" && Number.isFinite(v) && v > 0) total += v;
    });
  });
  $("totalDigitado").textContent = entradas.length ? `Total digitado: ${formatarLitros(total)}` : "";
}

// Enter passa para o próximo campo em vez de enviar a medição sem querer
formMedicao.addEventListener("keydown", e => {
  if (e.key !== "Enter" || e.target.tagName !== "INPUT") return;
  e.preventDefault();
  const campos = [...formMedicao.querySelectorAll("input")];
  const proximo = campos[campos.indexOf(e.target) + 1];
  (proximo || $("btnSalvar")).focus();
});

$("btnCancelar").addEventListener("click", () => { window.location.href = "leite.html"; });

formMedicao.addEventListener("submit", async e => {
  e.preventDefault();
  erroMedicao.hidden = true;

  let preenchidos = 0;
  const medicoes = [];
  for (const entrada of entradas) {
    const item = { animal_id: entrada.id, manha: null, tarde: null };
    for (const turno of ["manha", "tarde"]) {
      const texto = entrada[turno].value;
      if (texto === "") continue;
      const valor = Number(texto);
      if (!Number.isFinite(valor) || valor < 0) {
        mostrarMensagem(erroMedicao, `Valor inválido para ${entrada.nome}. Use um número igual ou maior que zero.`);
        entrada[turno].focus();
        return;
      }
      item[turno] = valor;
      preenchidos++;
    }
    medicoes.push(item);
  }

  if (preenchidos === 0) {
    mostrarMensagem(erroMedicao, "Preencha o leite de pelo menos uma vaca.");
    return;
  }

  const botao = $("btnSalvar");
  botao.disabled = true;
  try {
    const resposta = await api("/registrarProducaoLeite", {
      method: "POST",
      body: JSON.stringify({ ...contexto, medicoes })
    });
    $("textoSucesso").textContent =
      `${resposta.registros} lançamento(s) salvos para o lote ${contexto.lote} em ${formatarData(contexto.data)}.`;
    $("modalSucesso").showModal();
  } catch (erro) {
    mostrarMensagem(erroMedicao, erro.message);
  } finally {
    botao.disabled = false;
  }
});

$("btnNova").addEventListener("click", () => { window.location.href = "leite-medicao.html"; });
$("btnPainel").addEventListener("click", () => { window.location.href = "leite.html"; });

iniciar();