const API = "http://127.0.0.1:8000";
const $ = id => document.getElementById(id);

function formatarData(iso) {
  if (!iso || typeof iso !== "string") return "-";
  const [ano, mes, dia] = iso.split("-");
  return `${dia}/${mes}/${ano}`;
}

function formatarNumero(n) {
  return n === null || n === undefined ? "-" : Number(n).toLocaleString("pt-BR");
}

// diferença em dias entre hoje e a data (negativo = vencida)
function diasAte(iso) {
  const hoje = new Date();
  hoje.setHours(0, 0, 0, 0);
  const alvo = new Date(iso + "T00:00:00");
  return Math.round((alvo - hoje) / 86400000);
}

function situacao(iso) {
  const d = diasAte(iso);
  if (d < 0) return { texto: `Vencida há ${-d} ${d === -1 ? "dia" : "dias"}`, urgente: true };
  if (d === 0) return { texto: "Vence hoje", urgente: true };
  return { texto: `Em ${d} ${d === 1 ? "dia" : "dias"}`, urgente: false };
}

// celula pode ser texto ou {texto, href, urgente}
function desenhar(corpo, linhas, colunas, vazio) {
  corpo.innerHTML = "";
  if (linhas.length === 0) {
    corpo.innerHTML = `<tr><td class="vazio" colspan="${colunas}">${vazio}</td></tr>`;
    return;
  }
  linhas.forEach(celulas => {
    const tr = document.createElement("tr");
    celulas.forEach(c => {
      const td = document.createElement("td");
      const info = typeof c === "object" && c !== null ? c : { texto: c };
      if (info.href) {
        const a = document.createElement("a");
        a.href = info.href;
        a.textContent = info.texto;
        td.appendChild(a);
      } else {
        td.textContent = info.texto ?? "-";
      }
      if (info.urgente) td.classList.add("baixo");
      tr.appendChild(td);
    });
    corpo.appendChild(tr);
  });
}

async function carregarAlertas() {
  try {
    const resposta = await fetch(`${API}/alertas`);
    if (!resposta.ok) throw new Error(`Erro ${resposta.status}`);
    const dados = await resposta.json();

    $("tituloVacinas").textContent = `Vacinas (${dados.vacinas.length})`;
    desenhar($("corpoVacinas"), dados.vacinas.map(v => {
      const s = situacao(v.proxima_dose);
      return [{ texto: v.animal, href: `animal.html?id=${v.animal_id}` }, v.vacina,
              formatarData(v.proxima_dose), { texto: s.texto, urgente: s.urgente }];
    }), 4, "Nenhuma vacina pendente.");

    $("tituloManutencoes").textContent = `Manutenções (${dados.manutencoes.length})`;
    desenhar($("corpoManutencoes"), dados.manutencoes.map(m => {
      const s = situacao(m.proxima_manutencao);
      return [{ texto: m.maquina, href: `maquina.html?id=${m.maquina_id}` },
              formatarData(m.data_manutencao), formatarData(m.proxima_manutencao),
              { texto: s.texto, urgente: s.urgente }];
    }), 4, "Nenhuma manutenção pendente.");

    $("tituloEstoque").textContent = `Estoque baixo (${dados.estoque.length})`;
    desenhar($("corpoEstoque"), dados.estoque.map(i => [
      { texto: i.nome, href: `item.html?id=${i.id}` },
      { texto: `${formatarNumero(i.quantidade)} ${i.unidade || ""}`, urgente: true },
      `${formatarNumero(i.estoque_minimo)} ${i.unidade || ""}`, i.localizacao || "-"
    ]), 4, "Nenhum item abaixo do mínimo.");
  } catch (erro) {
    console.error("Falha ao carregar alertas:", erro);
  }
}

carregarAlertas();