const CABECALHO_ADMIN = { "X-Requested-With": "FazendaWEB-Admin" };
const $ = id => document.getElementById(id);

async function api(caminho, opcoes = {}) {
  const resposta = await fetch("/admin/api" + caminho, {
    ...opcoes,
    headers: { "Content-Type": "application/json", ...CABECALHO_ADMIN, ...(opcoes.headers || {}) }
  });
  const dados = await resposta.json().catch(() => ({}));
  if (!resposta.ok) throw new Error(dados.detail || "Erro ao falar com o servidor.");
  return dados;
}

function el(tag, classe, texto) {
  const e = document.createElement(tag);
  if (classe) e.className = classe;
  if (texto !== undefined) e.textContent = texto;
  return e;
}

function mostrar(elemento, texto) { elemento.textContent = texto; elemento.hidden = false; }

function dataBR(texto) {
  if (!texto) return "-";
  const [d, h] = String(texto).split(" ");
  const [a, m, dia] = d.split("-");
  return `${dia}/${m}/${a}${h ? " " + h.slice(0, 5) : ""}`;
}

const ROTULO_PAGAMENTO = { em_dia: "Em dia", pendente: "Pendente" };
const ROTULO_ACAO = {
  login: "Entrou", login_falhou: "Tentativa de login recusada", logout: "Saiu", logout_todas: "Saiu de todos os dispositivos",
  senha_trocada: "Trocou a senha", fazenda_criada: "Cadastrou uma fazenda", fazenda_falhou: "Falha ao cadastrar fazenda",
  fazenda_ativada: "Ativou uma fazenda", fazenda_desativada: "Desativou uma fazenda", plano_alterado: "Mudou o plano",
  pagamento_alterado: "Mudou o pagamento", acesso_dono_reemitido: "Gerou nova senha temporária do Dono",
  reemissao_recusada: "Nova senha do Dono recusada", confirmacao_falhou: "Senha de confirmação incorreta"
};

function selo(texto, tipo = "") { return el("span", `selo ${tipo}`.trim(), texto); }

function celula(tr, conteudo, classe) {
  const td = document.createElement("td");
  if (classe) td.className = classe;
  if (conteudo instanceof Node) td.appendChild(conteudo); else td.textContent = conteudo;
  tr.appendChild(td);
  return td;
}

document.querySelectorAll("[data-fechar]").forEach(b => b.addEventListener("click", () => $(b.dataset.fechar).close()));

// copia o acesso para entregar ao Dono
function ligarCopiar(botao, obter) {
  botao.addEventListener("click", async () => {
    try { await navigator.clipboard.writeText(obter()); botao.textContent = "Copiado"; }
    catch (e) { botao.textContent = "Selecione e copie"; }
  });
}
