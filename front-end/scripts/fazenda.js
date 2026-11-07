const API = "";   // mesma origem: a API e o front saem do mesmo servidor
const $ = id => document.getElementById(id);

async function api(caminho) {
  const resposta = await fetch(API + caminho);
  const dados = await resposta.json().catch(() => ({}));
  if (!resposta.ok) throw new Error(dados.detail || `Erro ${resposta.status}`);
  return dados;
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

function tempoDeExistencia(iso) {
  const inicio = new Date(iso);
  if (!iso || isNaN(inicio)) return null;
  const anos = Math.floor((Date.now() - inicio) / (365.25 * 24 * 3600 * 1000));
  return anos < 1 ? "menos de 1 ano" : `${anos} ${anos === 1 ? "ano" : "anos"}`;
}

// ---------- Fazenda e totais ----------
async function carregarFazenda() {
  try {
    await FW_CONFIG.pronto;
    const dados = await api("/detalhesFazenda");

    const t = dados.totais;
    $("totAnimais").textContent = t.animais;
    $("totFuncionarios").textContent = t.funcionarios;
    $("totMaquinas").textContent = t.maquinas;
    $("totProdutos").textContent = t.produtos;
    $("totLotes").textContent = t.lotes;

    const f = dados.fazenda;
    if (!f) {
      $("tituloFazenda").textContent = "Nenhuma fazenda cadastrada";
      return;
    }

    $("tituloFazenda").textContent = f.nome_fazenda;
    $("subFazenda").textContent = f.dono ? `Propriedade de ${f.dono}` : "Visão geral e últimas movimentações.";

    // logo: imagem se carregar, senão a inicial do nome
    const logo = $("logoFazenda");
    logo.textContent = f.nome_fazenda.charAt(0).toUpperCase();
    const pref = FW_CONFIG.get();
    const origemLogo = pref.tem_logo ? `/api/configuracoes/logo?v=${pref.logo_versao}` : f.logo_fazenda;   // o enviado em Configurações vale mais
    if (origemLogo) {
      const img = new Image();
      img.alt = "";
      img.onload = () => { logo.textContent = ""; logo.appendChild(img); };
      img.src = origemLogo;
    }

    const existencia = tempoDeExistencia(f.data_fundacao);
    const campos = [
      ["Nome", f.nome_fazenda],
      ["Proprietário", f.dono || "-"],
      ["Telefone", f.telefone || "-"],
      ["E-mail", f.email || "-"],
      ["Tamanho", FW_CONFIG.area(f.tamanho)],
      ["Endereço", f.endereco || "-"],
      ["Fundação", formatarData(f.data_fundacao) + (existencia ? ` (${existencia})` : "")]
    ];
    $("dadosFazenda").innerHTML = "";
    campos.forEach(([rotulo, valor]) => {
      const dt = document.createElement("dt");
      const dd = document.createElement("dd");
      dt.textContent = rotulo;
      dd.textContent = valor;
      $("dadosFazenda").append(dt, dd);
    });
  } catch (erro) {
    console.error("Falha ao carregar a fazenda:", erro);
    $("tituloFazenda").textContent = "Não foi possível carregar a fazenda";
  }
}

// ---------- Últimas movimentações ----------
async function carregarLogs() {
  const corpo = $("corpoLogs");
  try {
    const dados = await api("/ultimosLogs?limite=5");
    corpo.innerHTML = "";
    if (dados.logs.length === 0) {
      corpo.innerHTML = '<tr><td class="vazio" colspan="4">Nenhuma movimentação registrada ainda.</td></tr>';
      return;
    }
    dados.logs.forEach(l => {
      const tr = document.createElement("tr");
      [formatarDataHora(l.data_hora), l.usuario || "-", l.acao || "-", l.descricao || "-"].forEach((valor, i) => {
        const td = document.createElement("td");
        td.textContent = valor;
        if (i === 3) td.className = "esq";
        tr.appendChild(td);
      });
      corpo.appendChild(tr);
    });
  } catch (erro) {
    console.error("Falha ao carregar logs:", erro);
  }
}

carregarFazenda();
carregarLogs();