/* Menu do usuário e controle de sessão das páginas internas.
 *
 * Inclua com:  <script src="../scripts/sessao.js"></script>  (antes dos outros scripts da página)
 * Ele troca o bloco ".usuario" da barra superior por um botão que abre o menu:
 * foto (ou avatar padrão), nome, perfil, fazenda, trocar senha, sair e sair de todos os dispositivos.
 * Também leva ao login quando a sessão acaba.
 *
 * Para outra área (ex.: painel admin) defina window.FW_SESSAO_CONFIG antes de incluir o script.
 */
(function () {
  "use strict";

  const cfg = Object.assign({
    perfil: "/api/perfil", foto: "/api/perfil/foto",
    sair: "/api/auth/logout", sairTodas: "/api/auth/logout-todas", trocarSenha: "/api/auth/trocar-senha",
    login: "/front-end/login.html", trocaObrigatoria: "/front-end/trocar-senha.html",
    cabecalhos: {}, minSenha: 8
  }, window.FW_SESSAO_CONFIG || {});

  const fetchOriginal = window.fetch.bind(window);
  const CORES = ["#2f4a2b", "#8a5a2b", "#4f6b3a", "#b4561f", "#5b6f55", "#7a5c2e"];
  const TIPOS_FOTO = /^image\/(jpeg|png|webp)$/;
  const LIMITE_ARQUIVO = 10 * 1024 * 1024;

  // ---------- sessão: leva ao login quando acabar ----------
  window.fetch = async function (...args) {
    const resposta = await fetchOriginal(...args);
    if (resposta.status === 401) {
      location.href = `${cfg.login}?proximo=${encodeURIComponent(location.pathname)}`;
    } else if (resposta.status === 403) {
      resposta.clone().json().then(corpo => {
        if (corpo.codigo === "fazenda_desativada") location.href = `${cfg.login}?motivo=desativada`;
        if (corpo.codigo === "trocar_senha" && cfg.trocaObrigatoria) location.href = cfg.trocaObrigatoria;
      }).catch(() => {});
    }
    return resposta;
  };

  async function chamar(caminho, metodo, corpo, tipo) {
    const cabecalhos = Object.assign({}, cfg.cabecalhos);
    if (tipo) cabecalhos["Content-Type"] = tipo;
    const resposta = await fetchOriginal(caminho, { method: metodo, headers: cabecalhos, body: corpo });
    const dados = await resposta.json().catch(() => ({}));
    if (!resposta.ok) throw new Error(dados.detail || "Não foi possível concluir a ação.");
    return dados;
  }

  // ---------- estilo (injetado: as páginas não precisam mudar o CSS) ----------
  const CSS = `
  .usuario{position:relative}
  .fw-usuario{display:inline-flex;align-items:center;gap:10px;background:transparent;border:0;color:inherit;font:inherit;cursor:pointer;padding:4px 10px 4px 4px;border-radius:999px}
  .fw-usuario:hover,.fw-usuario[aria-expanded="true"]{background:rgba(255,255,255,.14)}
  .fw-usuario:focus-visible{outline:2px solid var(--dourado,#d9b25f);outline-offset:2px}
  .fw-av{width:34px;height:34px;border-radius:50%;display:inline-grid;place-items:center;font-weight:700;overflow:hidden;flex:none;color:#fff;background:#2f4a2b}
  .fw-av img{width:100%;height:100%;object-fit:cover;display:block}
  .fw-av.grande{width:72px;height:72px;font-size:1.8rem}
  .fw-seta{width:10px;height:10px;flex:none;transition:transform .15s}
  .fw-usuario[aria-expanded="true"] .fw-seta{transform:rotate(180deg)}
  .fw-painel{position:absolute;right:0;top:calc(100% + 10px);width:min(320px,calc(100vw - 24px));background:#fff;color:#26302a;border:1px solid #dcd8c8;border-radius:10px;box-shadow:0 12px 32px rgba(33,53,32,.28);padding:18px;z-index:60;white-space:normal;text-align:left;font-size:.95rem;line-height:1.4}
  .fw-painel[hidden],.fw-previa[hidden],.fw-msg[hidden]{display:none}
  .fw-cab{display:flex;gap:14px;align-items:center;margin-bottom:12px}
  .fw-nome{font-weight:700;font-size:1.05rem;overflow-wrap:anywhere}
  .fw-sub{color:#6a7468;font-size:.88rem;overflow-wrap:anywhere}
  .fw-selo{display:inline-block;margin-top:4px;padding:1px 10px;border-radius:10px;background:#e9e4d2;color:#213520;font-size:.8rem;font-weight:700}
  .fw-info{border-top:1px solid #dcd8c8;padding:10px 0;color:#6a7468;font-size:.88rem}
  .fw-info div+div{margin-top:2px}
  .fw-acoes{display:flex;flex-direction:column;gap:6px;border-top:1px solid #dcd8c8;padding-top:12px}
  .fw-btn{font:inherit;font-size:.92rem;text-align:left;padding:8px 12px;border-radius:6px;border:1px solid #dcd8c8;background:#fff;color:#26302a;cursor:pointer}
  .fw-btn:hover{background:#f7f5ec}
  .fw-btn:focus-visible{outline:2px solid #2f4a2b;outline-offset:1px}
  .fw-btn.sair{background:#2f4a2b;border-color:#2f4a2b;color:#e9e4d2;font-weight:700;text-align:center}
  .fw-btn.sair:hover{background:#213520}
  .fw-btn.discreto{border-color:transparent;color:#6a7468;font-size:.85rem}
  .fw-btn[disabled]{opacity:.6;cursor:wait}
  .fw-previa{text-align:center;padding:8px 0 12px}
  .fw-previa img{width:128px;height:128px;border-radius:50%;object-fit:cover;border:3px solid #e9e4d2}
  .fw-previa p{margin:8px 0;color:#6a7468;font-size:.88rem}
  .fw-previa .fw-acoes{border-top:0;padding-top:0}
  .fw-msg{margin-top:10px;font-size:.88rem;font-weight:700;color:#b4561f}
  .fw-msg.ok{color:#2f4a2b}
  dialog.fw-dialogo{border:1px solid #dcd8c8;border-radius:10px;padding:22px;width:min(380px,calc(100% - 32px));color:#26302a;background:#fff;font-family:inherit}
  dialog.fw-dialogo::backdrop{background:rgba(33,53,32,.6)}
  dialog.fw-dialogo h2{font-size:1.1rem;margin-bottom:12px}
  .fw-campo{display:flex;flex-direction:column;gap:3px;margin-bottom:10px}
  .fw-campo label{font-weight:700;font-size:.88rem}
  .fw-campo input{font:inherit;padding:8px 10px;border:1px solid #dcd8c8;border-radius:6px}
  .fw-rodape{display:flex;justify-content:flex-end;gap:8px;margin-top:14px}
  @media (max-width:560px){.fw-painel{position:fixed;left:12px;right:12px;top:72px;width:auto}}
  @media (prefers-reduced-motion:reduce){.fw-seta{transition:none}}`;

  // ---------- utilidades ----------
  function el(tag, classe, texto) {
    const e = document.createElement(tag);
    if (classe) e.className = classe;
    if (texto !== undefined) e.textContent = texto;
    return e;
  }

  function corDoNome(nome) {
    let soma = 0;
    for (const c of nome) soma += c.codePointAt(0);
    return CORES[soma % CORES.length];
  }

  function horaDaSessao(epoch) {
    if (!epoch) return "";
    const d = new Date(epoch * 1000);
    const hora = d.toLocaleTimeString("pt-BR", { hour: "2-digit", minute: "2-digit" });
    return d.toDateString() === new Date().toDateString()
      ? `Sessão ativa até ${hora}` : `Sessão ativa até ${d.toLocaleDateString("pt-BR")} ${hora}`;
  }

  // ---------- estado e montagem ----------
  let perfil = null;
  let botao, painel, entradaFoto, previa, mensagem;
  const avatares = [];            // elementos que mostram a foto/inicial e precisam atualizar juntos

  function preencherAvatar(span) {
    span.textContent = "";
    if (perfil.tem_foto) {
      const img = el("img");
      img.alt = "";
      img.src = `${cfg.foto}?v=${perfil.foto_versao || 0}`;
      img.addEventListener("error", () => { span.textContent = ""; span.style.background = corDoNome(perfil.nome); span.textContent = perfil.nome.trim().charAt(0).toUpperCase(); });
      span.style.background = "transparent";
      span.appendChild(img);
    } else {
      span.style.background = corDoNome(perfil.nome);
      span.textContent = perfil.nome.trim().charAt(0).toUpperCase() || "?";
    }
  }

  function criarAvatar(grande) {
    const span = el("span", grande ? "fw-av grande" : "fw-av");
    span.setAttribute("aria-hidden", "true");
    avatares.push(span);
    preencherAvatar(span);
    return span;
  }

  function atualizarAvatares() { avatares.forEach(preencherAvatar); botaoRemover.hidden = !perfil.tem_foto; }

  let botaoRemover;

  function aviso(texto, ok) {
    mensagem.textContent = texto;
    mensagem.className = ok ? "fw-msg ok" : "fw-msg";
    mensagem.hidden = !texto;
  }

  function montar(bloco) {
    const estilo = el("style");
    estilo.id = "fw-estilo-menu";
    estilo.textContent = CSS;
    document.head.appendChild(estilo);

    bloco.textContent = "";
    botao = el("button", "fw-usuario");
    botao.type = "button";
    botao.setAttribute("aria-haspopup", "dialog");
    botao.setAttribute("aria-expanded", "false");
    botao.setAttribute("aria-label", `Menu do usuário ${perfil.nome}`);
    botao.appendChild(criarAvatar(false));
    botao.appendChild(el("span", "", perfil.nome));
    botao.insertAdjacentHTML("beforeend", '<svg class="fw-seta" viewBox="0 0 10 10" aria-hidden="true"><path d="M1 3l4 4 4-4" fill="none" stroke="currentColor" stroke-width="1.6" stroke-linecap="round" stroke-linejoin="round"/></svg>');

    painel = el("div", "fw-painel");
    painel.hidden = true;
    painel.setAttribute("role", "dialog");
    painel.setAttribute("aria-label", "Menu do usuário");

    const cab = el("div", "fw-cab");
    cab.appendChild(criarAvatar(true));
    const dados = el("div");
    dados.appendChild(el("div", "fw-nome", perfil.nome));
    dados.appendChild(el("div", "fw-sub", `@${perfil.usuario}`));
    dados.appendChild(el("span", "fw-selo", perfil.perfil_rotulo));
    cab.appendChild(dados);
    painel.appendChild(cab);

    const info = el("div", "fw-info");
    if (perfil.fazenda) info.appendChild(el("div", "", `${perfil.fazenda.nome} (${perfil.fazenda.codigo})`));
    const sessao = horaDaSessao(perfil.sessao_expira_em);
    if (sessao) info.appendChild(el("div", "", sessao));
    painel.appendChild(info);

    previa = el("div", "fw-previa");
    previa.hidden = true;
    painel.appendChild(previa);

    const acoes = el("div", "fw-acoes");
    const alterarFoto = acao("Alterar foto", () => entradaFoto.click());
    botaoRemover = acao("Remover foto", removerFoto);
    botaoRemover.hidden = !perfil.tem_foto;
    acoes.append(alterarFoto, botaoRemover, acao("Trocar senha", abrirTrocaSenha),
                 Object.assign(acao("Sair", sair), { className: "fw-btn sair" }),
                 Object.assign(acao("Sair de todos os dispositivos", sairDeTodos), { className: "fw-btn discreto" }));
    painel.appendChild(acoes);
    mensagem = el("div", "fw-msg");
    mensagem.hidden = true;
    mensagem.setAttribute("role", "status");
    painel.appendChild(mensagem);

    entradaFoto = el("input");
    entradaFoto.type = "file";
    entradaFoto.accept = "image/jpeg,image/png,image/webp";
    entradaFoto.hidden = true;
    entradaFoto.addEventListener("change", escolherFoto);

    bloco.append(botao, painel, entradaFoto);
    botao.addEventListener("click", () => (painel.hidden ? abrir() : fechar()));
    document.addEventListener("click", e => { if (!painel.hidden && !bloco.contains(e.target)) fechar(); });
    document.addEventListener("keydown", teclado);
  }

  function acao(texto, aoClicar) {
    const b = el("button", "fw-btn", texto);
    b.type = "button";
    b.addEventListener("click", aoClicar);
    return b;
  }

  function focaveis() {
    return [...painel.querySelectorAll("button:not([hidden]):not([disabled])")].filter(b => !b.closest("[hidden]"));
  }

  function abrir() {
    aviso("");
    painel.hidden = false;
    botao.setAttribute("aria-expanded", "true");
    const lista = focaveis();
    if (lista.length) lista[0].focus();
  }

  function fechar(devolverFoco = true) {
    cancelarPrevia();
    painel.hidden = true;
    botao.setAttribute("aria-expanded", "false");
    if (devolverFoco) botao.focus();
  }

  function teclado(e) {
    if (painel.hidden) return;
    if (e.key === "Escape") { fechar(); return; }
    if (e.key !== "Tab") return;
    const lista = focaveis();
    if (!lista.length) return;
    const primeiro = lista[0], ultimo = lista[lista.length - 1];
    if (e.shiftKey && document.activeElement === primeiro) { e.preventDefault(); ultimo.focus(); }
    else if (!e.shiftKey && document.activeElement === ultimo) { e.preventDefault(); primeiro.focus(); }
  }

  // ---------- foto: recorta em quadrado, reduz para 256x256 e envia ----------
  let blobPrevia = null, urlPrevia = null;

  function cancelarPrevia() {
    if (urlPrevia) URL.revokeObjectURL(urlPrevia);
    blobPrevia = urlPrevia = null;
    previa.hidden = true;
    previa.textContent = "";
  }

  async function recortarQuadrado(arquivo) {
    const origem = await createImageBitmap(arquivo);          // já respeita a rotação da câmera
    const lado = Math.min(origem.width, origem.height);
    const canvas = document.createElement("canvas");
    canvas.width = canvas.height = 256;
    const ctx = canvas.getContext("2d");
    ctx.fillStyle = "#ffffff";                                // PNG transparente vira fundo branco
    ctx.fillRect(0, 0, 256, 256);
    ctx.drawImage(origem, (origem.width - lado) / 2, (origem.height - lado) / 2, lado, lado, 0, 0, 256, 256);
    if (origem.close) origem.close();
    return new Promise((ok, falha) =>
      canvas.toBlob(b => (b ? ok(b) : falha(new Error("Não foi possível preparar a imagem."))), "image/jpeg", 0.85));
  }

  async function escolherFoto() {
    const arquivo = entradaFoto.files && entradaFoto.files[0];
    entradaFoto.value = "";
    if (!arquivo) return;
    aviso("");
    if (!TIPOS_FOTO.test(arquivo.type)) { aviso("Escolha uma imagem JPEG, PNG ou WebP."); return; }
    if (arquivo.size > LIMITE_ARQUIVO) { aviso("A imagem é grande demais (máximo de 10 MB)."); return; }
    try {
      cancelarPrevia();
      blobPrevia = await recortarQuadrado(arquivo);
      urlPrevia = URL.createObjectURL(blobPrevia);
      const img = el("img");
      img.alt = "Pré-visualização da nova foto";
      img.src = urlPrevia;
      const botoes = el("div", "fw-acoes");
      botoes.append(Object.assign(acao("Salvar foto", salvarFoto), { className: "fw-btn sair" }),
                    acao("Cancelar", cancelarPrevia));
      previa.append(img, el("p", "", "Assim a foto vai aparecer."), botoes);
      previa.hidden = false;
      botoes.querySelector("button").focus();
    } catch (erro) {
      aviso(erro.message || "Não foi possível ler essa imagem.");
    }
  }

  async function salvarFoto() {
    const salvar = previa.querySelector(".sair");
    salvar.disabled = true;
    try {
      const r = await chamar(cfg.foto, "PUT", blobPrevia, "image/jpeg");
      perfil.tem_foto = true;
      perfil.foto_versao = r.foto_versao;
      cancelarPrevia();
      atualizarAvatares();
      aviso("Foto atualizada.", true);
    } catch (erro) {
      salvar.disabled = false;
      aviso(erro.message);
    }
  }

  async function removerFoto() {
    try {
      await chamar(cfg.foto, "DELETE");
      perfil.tem_foto = false;
      perfil.foto_versao = null;
      atualizarAvatares();
      aviso("Foto removida. Voltou o avatar padrão.", true);
    } catch (erro) { aviso(erro.message); }
  }

  // ---------- sair ----------
  async function sair() {
    await chamar(cfg.sair, "POST").catch(() => {});
    location.href = cfg.login;
  }

  let confirmaTodas = null;
  async function sairDeTodos(e) {
    const b = e.currentTarget;
    if (!confirmaTodas) {                                     // primeiro clique pede confirmação
      const original = b.textContent;
      b.textContent = "Confirmar: sair de todos";
      confirmaTodas = setTimeout(() => { b.textContent = original; confirmaTodas = null; }, 4000);
      return;
    }
    clearTimeout(confirmaTodas);
    confirmaTodas = null;
    await chamar(cfg.sairTodas, "POST").catch(() => {});
    location.href = cfg.login;
  }

  // ---------- trocar senha ----------
  function abrirTrocaSenha() {
    fechar(false);
    const dialogo = el("dialog", "fw-dialogo");
    const form = el("form");
    form.noValidate = true;
    form.appendChild(el("h2", "", "Trocar senha"));
    const campos = {};
    [["atual", "Senha atual", "current-password"], ["nova", "Nova senha", "new-password"], ["confirma", "Repita a nova senha", "new-password"]]
      .forEach(([id, rotulo, auto]) => {
        const c = el("div", "fw-campo");
        const l = el("label", "", rotulo);
        const i = el("input");
        i.type = "password"; i.autocomplete = auto; i.id = `fw-${id}`; l.htmlFor = i.id;
        campos[id] = i;
        c.append(l, i);
        form.appendChild(c);
      });
    const erro = el("div", "fw-msg");
    erro.hidden = true;
    erro.setAttribute("role", "alert");
    const rodape = el("div", "fw-rodape");
    const cancelar = acao("Cancelar", () => dialogo.close());
    const enviar = el("button", "fw-btn sair", "Salvar");
    enviar.type = "submit";
    rodape.append(cancelar, enviar);
    form.append(erro, rodape);
    dialogo.appendChild(form);
    document.body.appendChild(dialogo);
    dialogo.addEventListener("close", () => { dialogo.remove(); botao.focus(); });

    form.addEventListener("submit", async e => {
      e.preventDefault();
      erro.hidden = true;
      const mostrar = t => { erro.textContent = t; erro.hidden = false; };
      if (!campos.atual.value || !campos.nova.value) return mostrar("Preencha a senha atual e a nova senha.");
      if (campos.nova.value.length < cfg.minSenha) return mostrar(`A nova senha precisa ter pelo menos ${cfg.minSenha} caracteres.`);
      if (campos.nova.value !== campos.confirma.value) return mostrar("As duas senhas novas não são iguais.");
      enviar.disabled = true;
      try {
        await chamar(cfg.trocarSenha, "POST",
                     JSON.stringify({ senha_atual: campos.atual.value, nova_senha: campos.nova.value }), "application/json");
        dialogo.close();
        abrir();
        aviso("Senha alterada. As outras sessões foram encerradas.", true);
      } catch (e2) {
        enviar.disabled = false;
        mostrar(e2.message);
      }
    });
    dialogo.showModal();
    campos.atual.focus();
  }

  // ---------- permissões: esconde o que o perfil não pode usar ----------
  // (a barreira de verdade fica no servidor; isto só evita mostrar botões que dariam erro)
  function aplicarPermissoes() {
    (perfil.paginas_bloqueadas || []).forEach(nome => {
      document.querySelectorAll(`a[href="${nome}"], a[href$="/${nome}"]`).forEach(a => { (a.closest("li") || a).hidden = true; });
    });
    if (perfil.pode_excluir === false) {
      document.querySelectorAll('[id^="btnExcluir"], [data-acao="excluir"]').forEach(b => { b.hidden = true; });
      document.querySelectorAll(".botoes button").forEach(b => { if (b.textContent.trim().toLowerCase() === "excluir") b.hidden = true; });
    }
  }

  // ---------- início ----------
  document.addEventListener("DOMContentLoaded", async () => {
    try {
      const resposta = await fetchOriginal(cfg.perfil);
      if (!resposta.ok) return;
      perfil = await resposta.json();
      if (!perfil.nome) return;
      aplicarPermissoes();
      const bloco = document.querySelector(".usuario");
      if (bloco) montar(bloco);
    } catch (erro) { /* a página continua funcionando sem o menu */ }
  });
})();
