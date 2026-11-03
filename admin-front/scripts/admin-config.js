/* Aponta o menu do usuário (sessao.js) para a API do admin. Carregue ANTES do sessao.js. */
window.FW_SESSAO_CONFIG = {
  perfil: "/admin/api/perfil",
  foto: "/admin/api/perfil/foto",
  sair: "/admin/api/logout",
  sairTodas: "/admin/api/logout-todas",
  trocarSenha: "/admin/api/trocar-senha",
  login: "/admin/login.html",
  trocaObrigatoria: null,
  cabecalhos: { "X-Requested-With": "FazendaWEB-Admin" },
  minSenha: 12
};
