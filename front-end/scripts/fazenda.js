const API = "http://127.0.0.1:8000";
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
    if (f.logo_fazenda) {
      const img = new Image();
      img.alt = "";
      img.onload = () => { logo.textContent = ""; logo.appendChild(img); };
      img.src = f.logo_fazenda;
    }

    const existencia = tempoDeExistencia(f.data_fundacao);
    const campos = [
      ["Nome", f.nome_fazenda],
      ["Proprietário", f.dono || "-"],
      ["Tamanho", f.tamanho == null ? "-" : `${Number(f.tamanho).toLocaleString("pt-BR")} ha`],
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