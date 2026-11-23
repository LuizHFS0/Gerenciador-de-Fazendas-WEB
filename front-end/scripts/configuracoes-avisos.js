// Configurações > Avisos > Bezerros: quando avisar e o protocolo de tarefas de manejo.
// Carregue DEPOIS de configuracoes.js (usa o $ e o api definidos lá).
(function () {
  const CAMPOS = {
    aviso_dias_amarelo: "av_amarelo", aviso_dias_laranja: "av_laranja", aviso_dias_parto: "av_parto",
    gestacao_dias: "av_gestacao", diagnostico_dias: "av_diagnostico", secagem_dias_antes: "av_secagem"
  };
  const TIPOS = { geral: "Marca como feita", vacina: "Registra vacina", pesagem: "Pode registrar peso" };
  const SEXOS = { todos: "Todos", "Fêmea": "Só fêmeas", Macho: "Só machos" };
  const JSON_CAB = { "Content-Type": "application/json" };

  let protocolo = [];
  let editando = null;          // id da tarefa aberta no modal (null = tarefa nova)

  const el = (tag, classe, texto) => {
    const e = document.createElement(tag);
    if (classe) e.className = classe;
    if (texto !== undefined) e.textContent = texto;
    return e;
  };

  function aviso(elemento, texto, outro) {
    elemento.textContent = texto;
    elemento.hidden = false;
    if (outro) outro.hidden = true;
  }

  function limpar(...elementos) { elementos.forEach(e => { e.hidden = true; }); }

  // ---------- quando avisar ----------
  function preencherAjustes(config) {
    Object.entries(CAMPOS).forEach(([chave, campo]) => { $(campo).value = config[chave]; });
  }

  $("formAvisos").addEventListener("submit", async e => {
    e.preventDefault();
    limpar($("msgAvisosOk"), $("msgAvisosErro"));
    const corpo = {};
    Object.entries(CAMPOS).forEach(([chave, campo]) => { corpo[chave] = $(campo).value === "" ? null : Number($(campo).value); });
    $("btnSalvarAvisos").disabled = true;
    try {
      await api("/api/avisos/bezerros/config", { method: "PUT", headers: JSON_CAB, body: JSON.stringify(corpo) });
      aviso($("msgAvisosOk"), "Avisos salvos.");
    } catch (erro) { aviso($("msgAvisosErro"), erro.message); }
    finally { $("btnSalvarAvisos").disabled = false; }
  });

  // ---------- protocolo ----------
  function textoQuando(t) {
    return t.dias_apos_nascimento === 0 ? "No nascimento" : `Com ${t.dias_apos_nascimento} ${t.dias_apos_nascimento === 1 ? "dia" : "dias"}`;
  }

  function textoRepete(t) {
    if (!t.repetir_a_cada_dias) return "Não repete";
    const base = `A cada ${t.repetir_a_cada_dias} ${t.repetir_a_cada_dias === 1 ? "dia" : "dias"}`;
    return t.repetir_ate_dias ? `${base}, até os ${t.repetir_ate_dias} dias` : base;
  }

  function desenharProtocolo() {
    const corpo = $("corpoProtocolo");
    corpo.innerHTML = "";
    if (protocolo.length === 0) {
      corpo.innerHTML = '<tr><td class="vazio" colspan="6">Nenhuma tarefa. Use "Adicionar tarefa" ou "Restaurar padrão".</td></tr>';
      return;
    }
    protocolo.forEach(t => {
      const tr = document.createElement("tr");
      if (!t.ativo) tr.className = "desligada";
      const tdNome = document.createElement("td");
      tdNome.append(el("strong", "", t.nome));
      if (t.orientacao) tdNome.append(el("br"), el("small", "", t.orientacao));
      const tdSit = document.createElement("td");
      tdSit.appendChild(el("span", "selo" + (t.ativo ? " feita" : " dispensada"), t.ativo ? "Ligada" : "Desligada"));
      const acoes = el("div", "acoes-linha");
      const editar = el("button", "secundario", "Editar");
      editar.type = "button";
      editar.addEventListener("click", () => abrirModal(t));
      const alternar = el("button", "secundario", t.ativo ? "Desligar" : "Ligar");
      alternar.type = "button";
      alternar.addEventListener("click", () => alternarTarefa(t));
      acoes.append(editar, alternar);
      const tdAcoes = document.createElement("td");
      tdAcoes.appendChild(acoes);
      tr.append(tdNome);
      [`${textoQuando(t)}`, textoRepete(t), SEXOS[t.so_sexo] || t.so_sexo].forEach(v => {
        const td = document.createElement("td");
        td.textContent = v;
        tr.appendChild(td);
      });
      tr.append(tdSit, tdAcoes);
      corpo.appendChild(tr);
    });
  }

  async function carregar() {
    limpar($("msgProtocoloErro"));
    try {
      const dados = await api("/api/avisos/bezerros");
      preencherAjustes(dados.config);
      protocolo = dados.protocolo;
      desenharProtocolo();
    } catch (erro) { aviso($("msgProtocoloErro"), "Não foi possível carregar os avisos: " + erro.message); }
  }

  async function alternarTarefa(t) {
    limpar($("msgProtocoloOk"), $("msgProtocoloErro"));
    try {
      await api(`/api/avisos/bezerros/protocolo/${t.id}`, { method: "PUT", headers: JSON_CAB, body: JSON.stringify({ ativo: !t.ativo }) });
      await carregar();
      aviso($("msgProtocoloOk"), t.ativo ? `"${t.nome}" desligada para os próximos bezerros.` : `"${t.nome}" ligada para os próximos bezerros.`);
    } catch (erro) { aviso($("msgProtocoloErro"), erro.message); }
  }

  // ---------- modal da tarefa ----------
  const modal = $("modalTarefaProtocolo");

  function abrirModal(t) {
    editando = t ? t.id : null;
    $("formTarefaProtocolo").reset();
    $("tpTitulo").textContent = t ? "Editar tarefa" : "Adicionar tarefa";
    if (t) {
      $("tpNome").value = t.nome;
      $("tpDias").value = t.dias_apos_nascimento;
      $("tpSexo").value = t.so_sexo;
      $("tpRepetir").value = t.repetir_a_cada_dias ?? "";
      $("tpAte").value = t.repetir_ate_dias ?? "";
      $("tpTipo").value = t.tipo;
      $("tpOrient").value = t.orientacao || "";
    }
    modal.querySelector(".erro").hidden = true;
    modal.showModal();
  }

  modal.querySelector("[data-fechar-tp]").addEventListener("click", () => modal.close());
  $("btnNovaTarefa").addEventListener("click", () => abrirModal(null));

  $("formTarefaProtocolo").addEventListener("submit", async e => {
    e.preventDefault();
    const numero = id => ($(id).value === "" ? null : Number($(id).value));
    const corpo = {
      nome: $("tpNome").value.trim(), dias_apos_nascimento: numero("tpDias"), so_sexo: $("tpSexo").value,
      repetir_a_cada_dias: numero("tpRepetir"), repetir_ate_dias: numero("tpAte"),
      tipo: $("tpTipo").value, orientacao: $("tpOrient").value.trim()
    };
    try {
      if (editando) await api(`/api/avisos/bezerros/protocolo/${editando}`, { method: "PUT", headers: JSON_CAB, body: JSON.stringify(corpo) });
      else await api("/api/avisos/bezerros/protocolo", { method: "POST", headers: JSON_CAB, body: JSON.stringify(corpo) });
      modal.close();
      await carregar();
      aviso($("msgProtocoloOk"), editando ? "Tarefa salva. Vale para os próximos bezerros." : "Tarefa adicionada. Vale para os próximos bezerros.");
    } catch (erro) {
      const p = modal.querySelector(".erro");
      p.textContent = erro.message;
      p.hidden = false;
    }
  });

  // ---------- aplicar aos atuais e restaurar ----------
  $("btnAplicarAtuais").addEventListener("click", async () => {
    limpar($("msgProtocoloOk"), $("msgProtocoloErro"));
    if (!confirm("Criar as tarefas que ainda estão por vir para os bezerros que já nasceram? O que já passou não vira pendência.")) return;
    try {
      const r = await api("/api/avisos/bezerros/aplicar-aos-atuais", { method: "POST", headers: JSON_CAB, body: "{}" });
      aviso($("msgProtocoloOk"), r.message);
    } catch (erro) { aviso($("msgProtocoloErro"), erro.message); }
  });

  $("btnRestaurar").addEventListener("click", async () => {
    limpar($("msgProtocoloOk"), $("msgProtocoloErro"));
    if (!confirm("Restaurar o protocolo e os ajustes de aviso para o padrão? As tarefas que você criou ficam desligadas (não são apagadas).")) return;
    try {
      await api("/api/avisos/bezerros/restaurar-padrao", { method: "POST", headers: JSON_CAB, body: "{}" });
      await carregar();
      aviso($("msgProtocoloOk"), "Padrão restaurado.");
    } catch (erro) { aviso($("msgProtocoloErro"), erro.message); }
  });

  carregar();
})();
