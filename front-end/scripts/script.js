function definirTexto(seletor, valor) {
  const el = document.querySelector(seletor);
  if (!el) {
    console.warn(`Elemento ${seletor} não existe no HTML`);
    return;
  }
  el.textContent = valor;
}

function formatarData(iso) {
  if (!iso || typeof iso !== "string") return "-";
  const [ano, mes, dia] = iso.slice(0, 10).split("-");
  return `${dia}/${mes}/${ano}`;
}

function formatarDataHora(texto) {
  if (!texto) return "-";
  const hora = texto.slice(11, 16);
  return hora ? `${formatarData(texto)} ${hora}` : formatarData(texto);
}

async function carregarDashboard() {
  try {
    const resposta = await fetch('/dashboard');
    if (!resposta.ok) throw new Error(`Erro ${resposta.status}`);
    const dados = await resposta.json();
    definirTexto('#animais-ativos', dados.animais_ativos);
    definirTexto('#maquinas-em-operacao', dados.maquinas_operacao);
    definirTexto('#estoque-baixo', dados.estoque_baixo);
    definirTexto('#funcionarios-ativos', dados.funcionarios_ativos);
    definirTexto('#animais-parceria', dados.animais_parceria ?? 0);
    desenharTabela();
  } catch (erro) {
    console.error('Falha ao carregar o dashboard:', erro);
  }
}

async function desenharTabela() {
  try {
    const resposta = await fetch('/obterLogsEstoque?limite=5');
    const dados = await resposta.json();
    document.getElementById("corpoTabela").innerHTML = "";

    if (dados.logs.length === 0) {
      document.getElementById("corpoTabela").innerHTML = '<tr><td class="vazio" colspan="9">Nenhuma movimentação encontrada.</td></tr>';
      return;
    }
    dados.logs.forEach(m => {
      const tr = document.createElement("tr");
      [formatarDataHora(m.data_hora), m.acao || "-", m.nome_usuario || "-", m.descricao || "-"].forEach(valor => {
          const td = document.createElement("td");
          td.textContent = valor ?? "-";
          tr.appendChild(td);
        });
      document.getElementById("corpoTabela").appendChild(tr);
    });
  } catch (erro) {
    console.error("Falha ao carregar movimentações:", erro);
  }
}

// ---------- Alertas: vacinas chegando, estoque baixo e manutenções pendentes ----------
const ALERTAS_POR_GRUPO = 3;     // o resto fica na tela de Alertas

function diasAte(iso) {
  const hoje = new Date();
  hoje.setHours(0, 0, 0, 0);
  return Math.round((new Date(iso + "T00:00:00") - hoje) / 86400000);
}

function situacao(iso) {
  const d = diasAte(iso);
  if (d < 0) return { detalhe: `vencida há ${-d} ${d === -1 ? "dia" : "dias"}`, urgente: true };
  if (d === 0) return { detalhe: "vence hoje", urgente: true };
  return { detalhe: `em ${d} ${d === 1 ? "dia" : "dias"}`, urgente: false };
}

function desenharGrupo(grupo) {
  const bloco = document.createElement("div");
  bloco.className = "grupo-alertas";

  const titulo = document.createElement("h3");
  const nome = document.createElement("span");
  nome.textContent = grupo.titulo;
  const contagem = document.createElement("span");
  contagem.className = "contagem" + (grupo.itens.some(i => i.urgente) ? " alerta" : "");
  contagem.textContent = grupo.itens.length;
  titulo.append(nome, contagem);
  bloco.appendChild(titulo);

  if (grupo.itens.length === 0) {
    const vazio = document.createElement("p");
    vazio.className = "alertas-vazio";
    vazio.textContent = grupo.vazio;
    bloco.appendChild(vazio);
    return bloco;
  }

  const lista = document.createElement("ul");
  lista.className = "alertas-lista";
  grupo.itens.slice(0, ALERTAS_POR_GRUPO).forEach(item => {
    const li = document.createElement("li");
    const link = document.createElement("a");
    link.href = item.href;
    link.textContent = item.texto;
    const detalhe = document.createElement("span");
    detalhe.className = "detalhe" + (item.urgente ? " urgente" : "");
    detalhe.textContent = item.detalhe;
    li.append(link, detalhe);
    lista.appendChild(li);
  });
  bloco.appendChild(lista);

  const restantes = grupo.itens.length - ALERTAS_POR_GRUPO;
  if (restantes > 0) {
    const mais = document.createElement("a");
    mais.className = "alertas-mais";
    mais.href = "./paginas/alertas.html";
    mais.textContent = `e mais ${restantes} — ver todos`;
    bloco.appendChild(mais);
  }
  return bloco;
}

async function carregarAlertas() {
  const area = document.getElementById("listaAlertas");
  try {
    await FW_CONFIG.pronto;
    const resposta = await fetch("/alertas");
    if (!resposta.ok) throw new Error(`Erro ${resposta.status}`);
    const dados = await resposta.json();
    const cfg = FW_CONFIG.get();      // tipos desligados em Configurações nem aparecem aqui

    // saída de lotes em parceria (prazo fixo de 7 dias; não depende dos interruptores de Configurações)
    let saidas = [];
    try {
      const r2 = await fetch("/alertasParceria");
      if (r2.ok) saidas = (await r2.json()).alertas;
    } catch (_) { /* sem alerta de parceria: o resto da tela segue normal */ }

    // bezerros: tarefas de manejo e marcos da gestação (antecedência definida em Configurações > Avisos)
    let bezerros = { tarefas: [], gestacoes: [] };
    try {
      const r3 = await fetch("/bezerros/alertas");
      if (r3.ok) bezerros = await r3.json();
    } catch (_) { /* sem aviso de bezerros: o resto da tela segue normal */ }
    const detalheDias = d => d < 0 ? `atrasada há ${-d} ${d === -1 ? "dia" : "dias"}` : d === 0 ? "hoje" : `em ${d} ${d === 1 ? "dia" : "dias"}`;
    const urgenteNivel = nivel => nivel === "urgente" || nivel === "vencida";

    const grupos = [
      { ligado: cfg.notif_vacinas, titulo: "Vacinas chegando", vazio: "Nenhuma vacina próxima.",
        itens: dados.vacinas.map(v => ({ texto: `${v.animal} · ${v.vacina}`, href: `./paginas/animal.html?id=${v.animal_id}`, ...situacao(v.proxima_dose) })) },
      { ligado: cfg.notif_estoque, titulo: "Estoque baixo", vazio: "Nenhum item abaixo do mínimo.",
        itens: dados.estoque.map(i => ({ texto: i.nome, href: `./paginas/item.html?id=${i.id}`, urgente: true,
          detalhe: `${Number(i.quantidade).toLocaleString("pt-BR")} ${i.unidade || ""} (mín. ${Number(i.estoque_minimo).toLocaleString("pt-BR")})`.replace(/\s+\(/, " (") })) },
      { ligado: cfg.notif_manutencoes, titulo: "Manutenções pendentes", vazio: "Nenhuma manutenção pendente.",
        itens: dados.manutencoes.map(m => ({ texto: m.maquina, href: `./paginas/maquina.html?id=${m.maquina_id}`, ...situacao(m.proxima_manutencao) })) }
    ].filter(g => g.ligado);

    if (saidas.length > 0) {
      grupos.push({ titulo: "Saída de lotes em parceria", vazio: "", itens: saidas.map(a => ({
        texto: `${a.lote} · ${a.parceiro || "sem parceiro"} (${a.animais} animais)`,
        href: "./paginas/animais.html",
        urgente: a.nivel === "urgente",
        detalhe: a.dias_restantes < 0 ? `saída vencida há ${-a.dias_restantes} ${a.dias_restantes === -1 ? "dia" : "dias"}`
               : a.dias_restantes === 0 ? "sai hoje"
               : `sai em ${a.dias_restantes} ${a.dias_restantes === 1 ? "dia" : "dias"}`
      })) });
    }

    if (bezerros.tarefas.length > 0) {
      grupos.push({ titulo: "Bezerros: tarefas de manejo", vazio: "", itens: bezerros.tarefas.map(t => ({
        texto: `${t.animal} · ${t.nome}`, href: `./paginas/animal.html?id=${t.animal_id}`,
        urgente: urgenteNivel(t.nivel), detalhe: detalheDias(t.dias_restantes)
      })) });
    }
    if (bezerros.gestacoes.length > 0) {
      grupos.push({ titulo: "Gestação e parto", vazio: "", itens: bezerros.gestacoes.map(g => ({
        texto: `${g.vaca} · ${g.titulo}`, href: `./paginas/bezerros.html?id=${g.vaca_id}`,
        urgente: urgenteNivel(g.nivel), detalhe: detalheDias(g.dias_restantes)
      })) });
    }

    area.innerHTML = "";
    if (grupos.length === 0) {
      area.innerHTML = '<p class="alertas-vazio">Os alertas estão desligados em Utilitários › Configurações.</p>';
      return;
    }
    grupos.forEach(g => area.appendChild(desenharGrupo(g)));
  } catch (erro) {
    console.error("Falha ao carregar alertas:", erro);
    area.innerHTML = '<p class="alertas-vazio">Não foi possível carregar os alertas.</p>';
  }
}

carregarDashboard();
carregarAlertas();
