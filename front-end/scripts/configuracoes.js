const $ = id => document.getElementById(id);
const TEXTOS = ["nome_fazenda", "dono", "telefone", "email", "endereco", "data_fundacao"];
const MARCAS = ["notif_vacinas", "notif_manutencoes", "notif_estoque", "relatorio_logo"];
const SELECTS = ["unidade_peso", "unidade_area", "relatorio_periodo_dias"];
const MAX_LADO = 512;                 // o logotipo é reduzido aqui, no navegador, antes de enviar
const LIMITE_LOGO = 300 * 1024;

function mostrar(elemento, texto) { elemento.textContent = texto; elemento.hidden = false; }
function limparMensagens() { $("msgOk").hidden = true; $("msgErro").hidden = true; }

async function api(caminho, opcoes = {}) {
  const resposta = await fetch(caminho, opcoes);
  const dados = await resposta.json().catch(() => ({}));
  if (!resposta.ok) throw new Error(dados.detail || `Erro ${resposta.status}`);
  return dados;
}

// ---------- logotipo ----------
function desenharLogo(config) {
  const logo = $("logoPrevia");
  logo.innerHTML = "";
  $("btnRemoverLogo").hidden = !config.tem_logo;
  if (config.tem_logo) {
    const img = new Image();
    img.alt = "";
    img.onerror = () => { logo.textContent = (config.nome_fazenda || "?").charAt(0).toUpperCase(); };
    img.src = `/api/configuracoes/logo?v=${config.logo_versao || Date.now()}`;
    logo.appendChild(img);
  } else {
    logo.textContent = ($("nome_fazenda").value || config.nome_fazenda || "?").trim().charAt(0).toUpperCase();
  }
}

function exportar(imagem, largura, altura, tipo, qualidade, fundo) {
  const tela = document.createElement("canvas");
  tela.width = largura; tela.height = altura;
  const ctx = tela.getContext("2d");
  if (fundo) { ctx.fillStyle = fundo; ctx.fillRect(0, 0, largura, altura); }
  ctx.drawImage(imagem, 0, 0, largura, altura);
  return new Promise(resolve => tela.toBlob(resolve, tipo, qualidade));
}

async function prepararLogo(arquivo) {
  const url = URL.createObjectURL(arquivo);
  try {
    const imagem = await new Promise((ok, falha) => {
      const i = new Image(); i.onload = () => ok(i); i.onerror = () => falha(new Error("Não foi possível ler essa imagem.")); i.src = url;
    });
    const fator = Math.min(1, MAX_LADO / Math.max(imagem.naturalWidth, imagem.naturalHeight));
    const l = Math.max(1, Math.round(imagem.naturalWidth * fator));
    const a = Math.max(1, Math.round(imagem.naturalHeight * fator));
    let blob = await exportar(imagem, l, a, "image/png");                      // PNG mantém a transparência
    if (!blob || blob.size > LIMITE_LOGO) blob = await exportar(imagem, l, a, "image/jpeg", 0.85, "#ffffff");
    if (!blob || blob.size > LIMITE_LOGO) throw new Error("A imagem continua grande demais. Escolha outra.");
    return blob;
  } finally {
    URL.revokeObjectURL(url);
  }
}

$("btnLogo").addEventListener("click", () => $("arquivoLogo").click());

$("arquivoLogo").addEventListener("change", async () => {
  const arquivo = $("arquivoLogo").files[0];
  $("arquivoLogo").value = "";
  if (!arquivo) return;
  limparMensagens();
  try {
    const blob = await prepararLogo(arquivo);
    await api("/api/configuracoes/logo", { method: "PUT", headers: { "Content-Type": blob.type }, body: blob });
    desenharLogo(await api("/api/configuracoes"));
    mostrar($("msgOk"), "Logotipo atualizado.");
  } catch (erro) { mostrar($("msgErro"), erro.message); }
});

$("btnRemoverLogo").addEventListener("click", async () => {
  limparMensagens();
  try {
    await api("/api/configuracoes/logo", { method: "DELETE" });
    desenharLogo(await api("/api/configuracoes"));
    mostrar($("msgOk"), "Logotipo removido.");
  } catch (erro) { mostrar($("msgErro"), erro.message); }
});

// ---------- formulário ----------
function preencher(config) {
  TEXTOS.forEach(id => { $(id).value = config[id] || ""; });
  $("tamanho").value = config.tamanho ?? "";
  SELECTS.forEach(id => { $(id).value = String(config[id]); });
  MARCAS.forEach(id => { $(id).checked = !!config[id]; });
  $("alerta_dias").value = config.alerta_dias;
  desenharLogo(config);
}

function coletar() {
  const dados = {};
  TEXTOS.forEach(id => { dados[id] = $(id).value.trim(); });
  dados.data_fundacao = $("data_fundacao").value || null;
  dados.tamanho = $("tamanho").value === "" ? null : Number($("tamanho").value);
  dados.unidade_peso = $("unidade_peso").value;
  dados.unidade_area = $("unidade_area").value;
  dados.relatorio_periodo_dias = Number($("relatorio_periodo_dias").value);
  dados.alerta_dias = Number($("alerta_dias").value);
  MARCAS.forEach(id => { dados[id] = $(id).checked; });
  return dados;
}

$("formConfig").addEventListener("submit", async e => {
  e.preventDefault();
  limparMensagens();
  if (!$("nome_fazenda").value.trim()) { mostrar($("msgErro"), "Informe o nome da fazenda."); $("nome_fazenda").focus(); return; }
  if (!($("alerta_dias").value >= 1 && $("alerta_dias").value <= 90)) { mostrar($("msgErro"), "A antecedência dos alertas vai de 1 a 90 dias."); return; }
  $("btnSalvar").disabled = true;
  try {
    await api("/api/configuracoes", { method: "PUT", headers: { "Content-Type": "application/json" }, body: JSON.stringify(coletar()) });
    preencher(await api("/api/configuracoes"));
    mostrar($("msgOk"), "Configurações salvas.");
  } catch (erro) { mostrar($("msgErro"), erro.message); }
  finally { $("btnSalvar").disabled = false; }
});

$("nome_fazenda").addEventListener("input", () => {                      // sem logotipo, a inicial acompanha o nome digitado
  if ($("btnRemoverLogo").hidden) $("logoPrevia").textContent = ($("nome_fazenda").value.trim().charAt(0) || "?").toUpperCase();
});

(async () => {
  try { preencher(await api("/api/configuracoes")); }
  catch (erro) { mostrar($("msgErro"), "Não foi possível carregar as configurações: " + erro.message); }
})();
