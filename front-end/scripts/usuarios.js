const $ = id => document.getElementById(id);
const PERFIS = { dono: "Dono", gerente: "Gerente", funcionario: "Funcionário" };
let acaoConfirmada = null;
let usuarioDoPerfil = null;

async function api(caminho, opcoes = {}) {
  const resposta = await fetch(caminho, { headers: { "Content-Type": "application/json" }, ...opcoes });
  const dados = await resposta.json().catch(() => ({}));
  if (!resposta.ok) throw new Error(dados.detail || "Erro ao falar com o servidor.");
  return dados;
}

function mostrar(elemento, texto) { elemento.textContent = texto; elemento.hidden = false; }

document.querySelectorAll("[data-fechar]").forEach(b =>
  b.addEventListener("click", () => $(b.dataset.fechar).close()));

function celula(tr, conteudo, classe) {
  const td = document.createElement("td");
  if (classe) td.className = classe;
  if (conteudo instanceof Node) td.appendChild(conteudo); else td.textContent = conteudo;
  tr.appendChild(td);
  return td;
}

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

function mostrarSenha(titulo, texto, senha) {
  $("tituloSenha").textContent = titulo;
  $("textoSenha").textContent = texto;
  $("senhaTemp").textContent = senha;
  $("modalSenha").showModal();
}

function desenhar(lista) {
  const corpo = $("corpo");
  corpo.innerHTML = "";
  lista.forEach(u => {
    const tr = document.createElement("tr");
    celula(tr, u.nome, "esq");
    celula(tr, u.usuario);
    celula(tr, PERFIS[u.nivel_acesso] || u.nivel_acesso || "-");
    const situacao = document.createElement("span");
    situacao.append(selo(u.ativo ? "Ativo" : "Desativado", u.ativo ? "" : "inativo"));
    if (u.trocar_senha) situacao.append(" ", selo("Senha temporária", "pendente"));
    celula(tr, situacao);

    const acoes = celula(tr, "", "acoes");
    if (u.nivel_acesso === "dono") {
      acoes.textContent = "Conta do Dono";
    } else {
      acoes.append(
        botao("Perfil", () => {
          usuarioDoPerfil = u;
          $("perfilNome").textContent = u.nome;
          $("novoNivel").value = u.nivel_acesso === "gerente" ? "gerente" : "funcionario";
          $("erroPerfil").hidden = true;
          $("modalPerfil").showModal();
        }),
        botao("Redefinir senha", () => confirmar(
          "Redefinir senha", `Gerar uma nova senha temporária para ${u.nome}? Ele será desconectado.`,
          async () => {
            const r = await api(`/api/usuarios/${u.id}/redefinir-senha`, { method: "POST" });
            mostrarSenha("Nova senha temporária", `Senha de ${u.nome}:`, r.senha_temporaria);
          })),
        botao(u.ativo ? "Desativar" : "Ativar", () => confirmar(
          u.ativo ? "Desativar usuário" : "Ativar usuário",
          u.ativo ? `${u.nome} deixará de conseguir entrar no sistema. Nada é apagado.` : `${u.nome} voltará a poder entrar.`,
          () => api(`/api/usuarios/${u.id}/ativo`, { method: "PUT", body: JSON.stringify({ ativo: !u.ativo }) })))
      );
    }
    corpo.appendChild(tr);
  });
  if (lista.length === 0) {
    corpo.innerHTML = '<tr><td class="vazio" colspan="5">Nenhum usuário.</td></tr>';
  }
}

async function carregar() {
  $("erroPagina").hidden = true;
  try {
    desenhar((await api("/api/usuarios")).usuarios);
  } catch (erro) {
    mostrar($("erroPagina"), erro.message);
  }
}

$("btnNovo").addEventListener("click", () => {
  $("formNovo").reset();
  $("erroNovo").hidden = true;
  $("modalNovo").showModal();
  $("nNome").focus();
});

$("formNovo").addEventListener("submit", async e => {
  e.preventDefault();
  $("erroNovo").hidden = true;
  try {
    const r = await api("/api/usuarios", {
      method: "POST",
      body: JSON.stringify({ nome: $("nNome").value, usuario: $("nUsuario").value,
                             nivel: $("nNivel").value, cargo: $("nCargo").value })
    });
    $("modalNovo").close();
    mostrarSenha("Usuário criado", `Senha temporária de ${r.usuario}:`, r.senha_temporaria);
    carregar();
  } catch (erro) {
    mostrar($("erroNovo"), erro.message);
  }
});

$("okPerfil").addEventListener("click", async () => {
  try {
    await api(`/api/usuarios/${usuarioDoPerfil.id}/nivel`, { method: "PUT", body: JSON.stringify({ nivel: $("novoNivel").value }) });
    $("modalPerfil").close();
    carregar();
  } catch (erro) {
    mostrar($("erroPerfil"), erro.message);
  }
});

$("okConfirma").addEventListener("click", async () => {
  try {
    await acaoConfirmada();
    $("modalConfirma").close();
    carregar();
  } catch (erro) {
    mostrar($("erroConfirma"), erro.message);
  }
});

$("btnCopiar").addEventListener("click", async () => {
  try {
    await navigator.clipboard.writeText($("senhaTemp").textContent);
    $("btnCopiar").textContent = "Copiado";
  } catch (erro) {
    $("btnCopiar").textContent = "Selecione e copie";
  }
});

carregar();