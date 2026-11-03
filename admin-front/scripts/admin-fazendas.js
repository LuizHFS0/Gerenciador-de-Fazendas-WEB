const estado = { busca: "", plano: "", pagamento: "", situacao: "", ordem: "nome", direcao: "asc", pagina: 1, por_pagina: 10 };
let planos = [];
let acaoConfirmada = null;
let acaoEscolha = null;
let alvoReemitir = null;
let codigoEditado = false;
let temporizador = null;

const nomePlano = codigo => (planos.find(p => p.codigo === codigo) || { nome: codigo }).nome;

// ---------- lista ----------
function desenhar(dados) {
  const corpo = $("corpo");
  corpo.innerHTML = "";
  if (!dados.itens.length) {
    corpo.innerHTML = '<tr><td class="vazio" colspan="6">Nenhuma fazenda encontrada.</td></tr>';
  }
  dados.itens.forEach(f => {
    const tr = document.createElement("tr");
    const nome = el("span", "", f.nome);
    nome.append(el("small", "", `código: ${f.codigo}`));
    celula(tr, nome);
    celula(tr, String(f.funcionarios), "num");
    celula(tr, selo(f.plano_nome || nomePlano(f.plano), f.plano === "pro" ? "pro" : ""));
    celula(tr, selo(ROTULO_PAGAMENTO[f.pagamento] || f.pagamento, f.pagamento === "em_dia" ? "ok" : "ruim"));
    celula(tr, selo(f.ativa ? "Ativa" : "Desativada", f.ativa ? "ok" : "ruim"));
    const acoes = celula(tr, "", "acoes");
    [
      [f.ativa ? "Desativar" : "Ativar", () => confirmarAtivacao(f)],
      ["Plano", () => escolherPlano(f)],
      ["Pagamento", () => escolherPagamento(f)],
      ["Acesso do Dono", () => abrirReemitir(f)]
    ].forEach(([texto, aoClicar]) => {
      const b = el("button", "secundario pequeno", texto);
      b.type = "button";
      b.addEventListener("click", aoClicar);
      acoes.appendChild(b);
    });
    corpo.appendChild(tr);
  });
  const inicio = dados.total ? (dados.pagina - 1) * dados.por_pagina + 1 : 0;
  const fim = Math.min(dados.total, dados.pagina * dados.por_pagina);
  $("infoPagina").textContent = `Mostrando ${inicio}–${fim} de ${dados.total}`;
  $("numeroPagina").textContent = `Página ${dados.pagina} de ${dados.paginas}`;
  $("btnAnterior").disabled = dados.pagina <= 1;
  $("btnProxima").disabled = dados.pagina >= dados.paginas;
  estado.pagina = dados.pagina;
}

async function carregar() {
  $("erroPagina").hidden = true;
  const params = new URLSearchParams();
  Object.entries(estado).forEach(([k, v]) => { if (v !== "" && v !== null) params.set(k, v); });
  try {
    desenhar(await api("/fazendas?" + params));
  } catch (erro) {
    mostrar($("erroPagina"), erro.message);
  }
}

function filtrar() { estado.pagina = 1; carregar(); }

$("busca").addEventListener("input", () => {
  clearTimeout(temporizador);
  temporizador = setTimeout(() => { estado.busca = $("busca").value.trim(); filtrar(); }, 300);
});
[["fPlano", "plano"], ["fPagamento", "pagamento"], ["fSituacao", "situacao"], ["fOrdem", "ordem"], ["fDirecao", "direcao"]].forEach(([id, campo]) =>
  $(id).addEventListener("change", () => { estado[campo] = $(id).value; filtrar(); }));
$("fPorPagina").addEventListener("change", () => { estado.por_pagina = Number($("fPorPagina").value); filtrar(); });
$("btnAnterior").addEventListener("click", () => { estado.pagina -= 1; carregar(); });
$("btnProxima").addEventListener("click", () => { estado.pagina += 1; carregar(); });

// ---------- ações simples ----------
function confirmar(titulo, texto, acao) {
  $("confirmaTitulo").textContent = titulo;
  $("confirmaTexto").textContent = texto;
  $("erroConfirma").hidden = true;
  acaoConfirmada = acao;
  $("modalConfirma").showModal();
}

function confirmarAtivacao(f) {
  confirmar(f.ativa ? "Desativar fazenda" : "Ativar fazenda",
    f.ativa ? `${f.nome}: todos os usuários perdem o acesso agora. Nenhum dado é apagado e você pode reativar quando quiser.`
            : `${f.nome}: os usuários voltam a poder entrar.`,
    () => api(`/fazendas/${f.id}/ativa`, { method: "PUT", body: JSON.stringify({ ativa: !f.ativa }) }));
}

$("okConfirma").addEventListener("click", async () => {
  try {
    await acaoConfirmada();
    $("modalConfirma").close();
    carregar();
  } catch (erro) {
    mostrar($("erroConfirma"), erro.message);
  }
});

function abrirEscolha(titulo, rotulo, f, opcoes, atual, aoSalvar) {
  $("escolhaTitulo").textContent = titulo;
  $("escolhaRotulo").textContent = rotulo;
  $("escolhaNome").textContent = f.nome;
  const s = $("escolhaSelect");
  s.innerHTML = "";
  opcoes.forEach(([valor, texto]) => s.add(new Option(texto, valor)));
  s.value = atual;
  $("erroEscolha").hidden = true;
  acaoEscolha = aoSalvar;
  $("modalEscolha").showModal();
}

function escolherPlano(f) {
  abrirEscolha("Mudar plano", "Plano", f, planos.map(p => [p.codigo, p.nome]), f.plano,
    valor => api(`/fazendas/${f.id}/plano`, { method: "PUT", body: JSON.stringify({ plano: valor }) }));
}

function escolherPagamento(f) {
  abrirEscolha("Situação do pagamento", "Pagamento", f, [["em_dia", "Em dia"], ["pendente", "Pendente"]], f.pagamento,
    valor => api(`/fazendas/${f.id}/pagamento`, { method: "PUT", body: JSON.stringify({ pagamento: valor }) }));
}

$("okEscolha").addEventListener("click", async () => {
  try {
    await acaoEscolha($("escolhaSelect").value);
    $("modalEscolha").close();
    carregar();
  } catch (erro) {
    mostrar($("erroEscolha"), erro.message);
  }
});

// ---------- entrega do acesso (a senha só aparece agora) ----------
function mostrarAcesso(titulo, texto, fazenda, acesso) {
  $("acTitulo").textContent = titulo;
  $("acTexto").textContent = texto;
  $("acFazenda").textContent = fazenda;
  $("acCodigo").textContent = acesso.codigo_fazenda;
  $("acUsuario").textContent = acesso.usuario;
  $("acSenha").textContent = acesso.senha_temporaria;
  $("btnCopiarAcesso").textContent = "Copiar acesso";
  $("modalAcesso").showModal();
}
ligarCopiar($("btnCopiarAcesso"), () =>
  `Código da fazenda: ${$("acCodigo").textContent}\nUsuário: ${$("acUsuario").textContent}\nSenha temporária: ${$("acSenha").textContent}`);

function abrirReemitir(f) {
  alvoReemitir = f;
  $("reemitirNome").textContent = f.nome;
  $("reemitirSenha").value = "";
  $("erroReemitir").hidden = true;
  $("modalReemitir").showModal();
  $("reemitirSenha").focus();
}

$("okReemitir").addEventListener("click", async () => {
  $("erroReemitir").hidden = true;
  const senha = $("reemitirSenha").value;
  if (!senha) return mostrar($("erroReemitir"), "Informe a sua senha para confirmar.");
  try {
    const r = await api(`/fazendas/${alvoReemitir.id}/reemitir-acesso`, { method: "POST", body: JSON.stringify({ senha_confirmacao: senha }) });
    $("reemitirSenha").value = "";
    $("modalReemitir").close();
    mostrarAcesso("Nova senha temporária", "Entregue estes dados ao Dono:", alvoReemitir.nome, r.acesso);
  } catch (erro) {
    $("reemitirSenha").value = "";
    mostrar($("erroReemitir"), erro.message);
  }
});

// ---------- cadastro de fazenda ----------
function slug(texto) {
  return texto.normalize("NFD").replace(/[\u0300-\u036f]/g, "").toLowerCase().replace(/[^a-z0-9]+/g, "-").replace(/^-+|-+$/g, "").slice(0, 30).replace(/-+$/, "");
}

$("btnNova").addEventListener("click", () => {
  $("formNova").reset();
  codigoEditado = false;
  $("erroNova").hidden = true;
  $("modalNova").showModal();
  $("nNome").focus();
});
$("nNome").addEventListener("input", () => { if (!codigoEditado) $("nCodigo").value = slug($("nNome").value); });
$("nCodigo").addEventListener("input", () => { codigoEditado = true; });

$("formNova").addEventListener("submit", async e => {
  e.preventDefault();
  $("erroNova").hidden = true;
  const corpo = {
    nome: $("nNome").value.trim(), codigo: $("nCodigo").value.trim().toLowerCase(), plano: $("nPlano").value,
    pagamento: $("nPagamento").value, contato_nome: $("nContatoNome").value.trim(), contato_email: $("nContatoEmail").value.trim(),
    contato_telefone: $("nContatoTelefone").value.trim(), observacoes: $("nObs").value.trim(), dono_nome: $("nDono").value.trim(),
    pagamento_verificado: $("nVerificado").checked, senha_confirmacao: $("nSenha").value
  };
  if (!corpo.nome || !corpo.codigo || !corpo.dono_nome) return mostrar($("erroNova"), "Preencha o nome da fazenda, o código e o nome do Dono.");
  if (!corpo.pagamento_verificado) return mostrar($("erroNova"), "Marque a confirmação de que verificou o pagamento.");
  if (!corpo.senha_confirmacao) return mostrar($("erroNova"), "Informe a sua senha para confirmar o cadastro.");
  $("btnSalvarNova").disabled = true;
  try {
    const r = await api("/fazendas", { method: "POST", body: JSON.stringify(corpo) });
    $("nSenha").value = "";
    $("modalNova").close();
    carregar();
    mostrarAcesso("Fazenda cadastrada", "Entregue estes dados ao Dono da fazenda:", r.fazenda.nome, r.acesso);
  } catch (erro) {
    $("nSenha").value = "";
    mostrar($("erroNova"), erro.message);
  } finally {
    $("btnSalvarNova").disabled = false;
  }
});

// ---------- início ----------
(async () => {
  const url = new URLSearchParams(location.search);               // o dashboard aponta para cá com filtros prontos
  ["plano", "pagamento", "situacao", "busca"].forEach(c => { if (url.get(c)) estado[c] = url.get(c); });
  try {
    planos = (await api("/planos")).planos;
    planos.forEach(p => { $("fPlano").add(new Option(p.nome, p.codigo)); $("nPlano").add(new Option(p.nome, p.codigo)); });
  } catch (erro) { mostrar($("erroPagina"), erro.message); }
  $("busca").value = estado.busca;
  $("fPlano").value = estado.plano;
  $("fPagamento").value = estado.pagamento;
  $("fSituacao").value = estado.situacao;
  carregar();
})();
