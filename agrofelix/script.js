const toggle = document.querySelector('.menu-toggle');
const nav = document.querySelector('.nav');
toggle.addEventListener('click', () => {
  const opened = nav.classList.toggle('open');
  toggle.setAttribute('aria-expanded', String(opened));
});
nav.querySelectorAll('a').forEach(link => link.addEventListener('click', () => {
  nav.classList.remove('open');
  toggle.setAttribute('aria-expanded', 'false');
}));
document.getElementById('year').textContent = new Date().getFullYear();

// Configure o WhatsApp oficial da loja em formato internacional, somente números.
// Exemplo de formato: 5531999999999 (55 + DDD + número).
const WHATSAPP_NUMBER = 'INSIRA_SEU_NUMERO';
const whatsappLink = document.getElementById('whatsapp-link');
whatsappLink.addEventListener('click', (event) => {
  if (!/^\\d{12,13}$/.test(WHATSAPP_NUMBER)) {
    event.preventDefault();
    alert('O WhatsApp da Agrofelix ainda precisa ser configurado. Edite a variável WHATSAPP_NUMBER no arquivo script.js.');
    return;
  }
  event.preventDefault();
  const message = encodeURIComponent('Olá! Vim pelo site da Agrofelix e gostaria de informações sobre os produtos.');
  window.open(`https://wa.me/${WHATSAPP_NUMBER}?text=${message}`, '_blank', 'noopener');
});