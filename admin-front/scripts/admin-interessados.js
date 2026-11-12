let paginaAtual = 1, totalPaginas = 1;
const corpo = document.getElementById("corpo");
const erroPagina = document.getElementById("erroPagina");
const filtroStatus = document.getElementById("filtroStatus");

async function carregar() {
  erroPagina.hidden = true;
  corpo.replaceChildren();
  try {
    const dados = await api("/interessados?pagina=" + paginaAtual + "&por_pagina=20&status=" + encodeURIComponent(filtroStatus.value));
    totalPaginas = dados.paginas || 1;
    if (!dados.itens.length) {
      const tr = document.createElement("tr"), td = document.createElement("td");
      td.colSpan = 6; td.className = "vazio"; td.textContent = "Nenhum contato encontrado.";
      tr.append(td); corpo.append(tr);
    }
    for (const item of dados.itens) {
      const tr = document.createElement("tr");
      celula(tr, dataBR(item.criado_em));
      const pessoa = document.createElement("div"); pessoa.textContent = item.nome;
      const fazenda = document.createElement("small"); fazenda.textContent = item.fazenda || "Fazenda não informada";
      pessoa.append(fazenda); celula(tr, pessoa);
      const email = document.createElement("a"); email.href = "mailto:" + item.email; email.textContent = item.email; celula(tr, email);
      const telefone = document.createElement("a");
      telefone.href = "https://wa.me/" + String(item.telefone).replace(/\\D/g, "");
      telefone.target = "_blank"; telefone.rel = "noopener noreferrer"; telefone.textContent = item.telefone; celula(tr, telefone);
      celula(tr, item.mensagem || "-");
      const tdStatus = document.createElement("td"), select = document.createElement("select");
      for (const [valor, rotulo] of [["novo","Novo"],["contatado","Contatado"],["arquivado","Arquivado"]]) {
        const op = document.createElement("option"); op.value = valor; op.textContent = rotulo; select.append(op);
      }
      select.value = item.status;
      select.addEventListener("change", async () => {
        const anterior = item.status; select.disabled = true;
        try {
          await api("/interessados/" + item.id, {method:"PATCH",body:JSON.stringify({status:select.value})});
          item.status = select.value;
        } catch (erro) { mostrar(erroPagina, erro.message); select.value = anterior; }
        finally { select.disabled = false; }
      });
      tdStatus.append(select); tr.append(tdStatus); corpo.append(tr);
    }
    document.getElementById("infoPagina").textContent = dados.total + " contato(s)";
    document.getElementById("numeroPagina").textContent = "Página " + paginaAtual + " de " + totalPaginas;
    document.getElementById("btnAnterior").disabled = paginaAtual <= 1;
    document.getElementById("btnProxima").disabled = paginaAtual >= totalPaginas;
  } catch (erro) { mostrar(erroPagina, erro.message); }
}
document.getElementById("btnAtualizar").addEventListener("click", carregar);
document.getElementById("btnAnterior").addEventListener("click", () => { if (paginaAtual > 1) { paginaAtual--; carregar(); } });
document.getElementById("btnProxima").addEventListener("click", () => { if (paginaAtual < totalPaginas) { paginaAtual++; carregar(); } });
filtroStatus.addEventListener("change", () => { paginaAtual = 1; carregar(); });
carregar();