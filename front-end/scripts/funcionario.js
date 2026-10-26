const API = "http://127.0.0.1:8000";
const id = new URLSearchParams(location.search).get("id");
if (!id) location.href = "funcionarios.html";

const $ = elemento => document.getElementById(elemento);

let perfilAtual = null;     // quem está vendo a página (decide quais botões aparecem)
let acessoAtual = null;
let acaoConfirmada = null;

async function api(caminho, opcoes = {}) {
  const resposta = await fetch(API + caminho, { headers: { "Content-Type": "application/json" }, ...opcoes });
  const dados = await resposta.json().catch(() => ({}));
  if (!resposta.ok) throw new Error(dados.detail || "Erro ao falar com o servidor.");
  return dados;
}

function formatarData(iso) {
  if (!iso || typeof iso !== "string") return "-";
  const [ano, mes, dia] = iso.split("-");
  return `${dia}/${mes}/${ano}`;
}

function formatarCpf(cpf) {
  const d = String(cpf || "").replace(/\D/g, "");
  return d.length === 11 ? d.replace(/(\d{3})(\d{3})(\d{3})(\d{2})/, "$1.$2.$3-$4") : (cpf || "-");
}

function mostrar(elemento, texto) { elemento.textContent = texto; elemento.hidden = false; }

document.querySelectorAll("[data-fechar]").forEach(b =>
  b.addEventListener("click", () => $(b.dataset.fechar).close()));

async function carregarFuncionario() {
  let f;
  try {
    f = await api(`/consultarFuncionario/${id}`);
  } catch (erro) {
    $("tituloFuncionario").textContent = "Funcionário não encontrado";
    $("subFuncionario").textContent = erro.message;
    return false;
  }

  $("tituloFuncionario").textContent = f.nome;
  $("subFuncionario").textContent = f.cargo || "";

  const campos = [
    ["CPF", formatarCpf(f.cpf)],
    ["Telefone", f.telefone || "-"],
    ["Endereço", f.endereco || "-"],
    ["Cargo", f.cargo || "-"],
    ["Data de admissão", formatarData(f.data_admissao)],
    ["Observações", f.observacoes || "-"]
  ];
  $("dadosFuncionario").innerHTML = "";
  campos.forEach(([rotulo, valor]) => {
    const dt = document.createElement("dt");
    const dd = document.createElement("dd");
    dt.textContent = rotulo;
    dd.textContent = valor;
    $("dadosFuncionario").append(dt, dd);
  });
  return true;
}

async function carregarMovimentacoes() {
  const corpo = $("corpoMovimentacoes");
  try {
    const dados = await api(`/movimentacoesFuncionario/${id}`);
    corpo.innerHTML = "";
    if (dados.movimentacoes.length === 0) {
      corpo.innerHTML = '<tr><td class="vazio" colspan="3">Nenhuma movimentação encontrada para este funcionário.</td></tr>';
      return;
    }
    dados.movimentacoes.forEach(m => {
      const tr = document.createElement("tr");
      [formatarData(m.data), m.tipo, m.descricao].forEach((valor, i) => {
        const td = document.createElement("td");
        td.textContent = valor || "-";
        if (i === 2) td.className = "esq";
        tr.appendChild(td);
      });
      corpo.appendChild(tr);
    });
  } catch (erro) { console.error(erro); }
}

// ---------- Acesso ao sistema ----------
function selo(texto, classe = "") {
  const s = document.createElement("span");
  s.className = `selo ${classe}`.trim();
  s.textContent = texto;
  return s;
}

function botao(texto, aoClicar) {
  const b = document.createElement("button");
  b.type = "button";
  b.className = "secundario";
  b.textContent = texto;
  b.addEventListener("click", aoClicar);
  return b;
}

function confirmar(titulo, texto, acao) {
  $("confirmaTitulo").textContent = titulo;
  $("confirmaTexto").textContent = texto;
  $("erroConfirma").hidden = true;
  acaoConfirmada = acao;
  $("modalConfirma").showModal();
}

function mostrarSenha(titulo, texto, usuario, senha) {
  $("tituloSenha").textContent = titulo;
  $("textoSenha").textContent = texto;
  $("acFazenda").textContent = (perfilAtual && perfilAtual.fazenda && perfilAtual.fazenda.codigo) || "-";
  $("acUsuario").textContent = usuario;
  $("acSenha").textContent = senha;
  $("btnCopiarAcesso").textContent = "Copiar acesso";
  $("modalSenha").showModal();
}

async function carregarAcesso() {
  const lista = $("dadosAcesso");
  lista.innerHTML = "";
  $("botoesAcesso").innerHTML = "";
  $("erroAcesso").hidden = true;

  let a;
  try {
    a = await api(`/api/funcionarios/${id}/acesso`);
  } catch (erro) {
    $("semAcesso").hidden = true;
    mostrar($("erroAcesso"), erro.message);
    return;
  }
  acessoAtual = a;
  const ehDono = perfilAtual && perfilAtual.nivel === "dono";

  if (!a.tem_acesso) {
    $("semAcesso").hidden = false;
    $("botoesAcesso").append(botao("Criar acesso", () => confirmar(
      "Criar acesso",
      "Criar o acesso ao sistema para este funcionário? Será gerada uma senha temporária.",
      async () => {
        const r = await api(`/api/funcionarios/${id}/acesso`, { method: "POST" });
        mostrarSenha("Acesso criado", "Entregue estes dados ao funcionário:", r.usuario, r.senha_temporaria);
      })));
    return;
  }

  $("semAcesso").hidden = true;
  const situacao = document.createElement("span");
  situacao.append(selo(a.ativo ? "Ativo" : "Desativado", a.ativo ? "" : "inativo"));
  if (a.senha_temporaria_pendente) situacao.append(" ", selo("Aguardando o primeiro acesso", "pendente"));
  [["Usuário", a.usuario], ["Perfil", a.perfil], ["Situação", situacao]].forEach(([rotulo, valor]) => {
    const dt = document.createElement("dt");
    const dd = document.createElement("dd");
    dt.textContent = rotulo;
    if (valor instanceof Node) dd.appendChild(valor); else dd.textContent = valor;
    lista.append(dt, dd);
  });

  if (ehDono && a.nivel !== "dono") {            // só o Dono gerencia contas
    $("botoesAcesso").append(
      botao("Mudar perfil", () => {
        $("novoNivel").value = a.nivel === "gerente" ? "gerente" : "funcionario";
        $("erroPerfil").hidden = true;
        $("modalPerfil").showModal();
      }),
      botao("Redefinir senha", () => confirmar(
        "Redefinir senha", "Gerar uma nova senha temporária? Ele será desconectado de todos os aparelhos.",
        async () => {
          const r = await api(`/api/usuarios/${a.usuario_id}/redefinir-senha`, { method: "POST" });
          mostrarSenha("Nova senha temporária", "Entregue estes dados ao funcionário:", r.usuario, r.senha_temporaria);
        })),
      botao(a.ativo ? "Desativar acesso" : "Ativar acesso", () => confirmar(
        a.ativo ? "Desativar acesso" : "Ativar acesso",
        a.ativo ? "Ele deixará de conseguir entrar no sistema. Nada é apagado." : "Ele voltará a poder entrar no sistema.",
        () => api(`/api/usuarios/${a.usuario_id}/ativo`, { method: "PUT", body: JSON.stringify({ ativo: !a.ativo }) })))
    );
  }
}

$("okConfirma").addEventListener("click", async () => {
  try {
    await acaoConfirmada();
    $("modalConfirma").close();
    carregarAcesso();
  } catch (erro) {
    mostrar($("erroConfirma"), erro.message);
  }
});

$("okPerfil").addEventListener("click", async () => {
  try {
    await api(`/api/usuarios/${acessoAtual.usuario_id}/nivel`, { method: "PUT", body: JSON.stringify({ nivel: $("novoNivel").value }) });
    $("modalPerfil").close();
    carregarAcesso();
  } catch (erro) {
    mostrar($("erroPerfil"), erro.message);
  }
});

$("btnCopiarAcesso").addEventListener("click", async () => {
  const texto = `Código da fazenda: ${$("acFazenda").textContent}\nUsuário: ${$("acUsuario").textContent}\nSenha temporária: ${$("acSenha").textContent}`;
  try {
    await navigator.clipboard.writeText(texto);
    $("btnCopiarAcesso").textContent = "Copiado";
  } catch (erro) {
    $("btnCopiarAcesso").textContent = "Selecione e copie";
  }
});

(async () => {
  try { perfilAtual = await api("/api/perfil"); } catch (erro) { perfilAtual = null; }
  if (await carregarFuncionario()) {
    carregarAcesso();
    carregarMovimentacoes();
  }
})();
