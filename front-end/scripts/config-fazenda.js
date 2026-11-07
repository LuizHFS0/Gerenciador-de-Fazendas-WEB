/* Preferências da fazenda (unidades, relatórios...) para as telas que precisam delas.
 *
 * Inclua DEPOIS de sessao.js e antes do script da página. Uso:
 *   await FW_CONFIG.pronto;                 // espera carregar (nunca falha: sem resposta valem os padrões)
 *   FW_CONFIG.peso(450)  ->  "450 kg" | "30 @" | "992,08 lb"      (o valor guardado é sempre em kg)
 *   FW_CONFIG.area(120)  ->  "120 ha" | "24,79 alqueire mineiro"  (o valor guardado é sempre em ha)
 *   FW_CONFIG.get()      ->  objeto com todas as preferências
 */
window.FW_CONFIG = (function () {
  "use strict";
  const PADRAO = { unidade_peso: "kg", unidade_area: "ha", relatorio_periodo_dias: 30, relatorio_logo: true, alerta_dias: 15,
                   nome_fazenda: "", tem_logo: false, logo_versao: null };
  const PESO = { kg: [1, "kg"], arroba: [1 / 15, "@"], lb: [2.2046226218, "lb"] };                       // 1 arroba = 15 kg
  const AREA = { ha: [1, "ha"], alqueire_mg: [1 / 4.84, "alqueire mineiro"], alqueire_sp: [1 / 2.42, "alqueire paulista"] };

  let dados = Object.assign({}, PADRAO);

  const pronto = fetch("/api/configuracoes/preferencias")
    .then(r => (r.ok ? r.json() : {}))
    .then(d => { dados = Object.assign({}, PADRAO, d); })
    .catch(() => {});

  function formatar(valor, tabela, unidade) {
    if (valor === null || valor === undefined || valor === "") return "-";
    const [fator, rotulo] = tabela[unidade] || tabela[Object.keys(tabela)[0]];
    return `${(Number(valor) * fator).toLocaleString("pt-BR", { maximumFractionDigits: 2 })} ${rotulo}`;
  }

  return {
    pronto,
    get: () => dados,
    peso: kg => formatar(kg, PESO, dados.unidade_peso),
    area: ha => formatar(ha, AREA, dados.unidade_area)
  };
})();
