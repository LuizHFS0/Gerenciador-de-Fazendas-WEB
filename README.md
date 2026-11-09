# FazendaWEB

Sistema web de gerenciamento de fazendas. A aplicação usa **FastAPI + Uvicorn** no backend, arquivos HTML/CSS/JavaScript no frontend e bancos SQLite separados por fazenda, além dos bancos administrativos.

Este guia descreve uma implantação em um servidor Linux com **Cloudflare Tunnel**. O túnel publica a aplicação sem abrir portas de entrada no roteador.

## 1. Arquitetura de publicação

\`\`\`text
Internet
   |
Cloudflare (DNS + HTTPS)
   |
Cloudflare Tunnel (cloudflared)
   |
Servidor Linux: 127.0.0.1:8000
   |
Uvicorn -> FastAPI
   |
SQLite em /srv/fazendaweb/dados
   |
Backups em /srv/fazendaweb/backups
\`\`\`

O Uvicorn deve escutar somente em \`127.0.0.1\`. Não use \`0.0.0.0\` quando o único acesso público será pelo Tunnel.

## 2. Requisitos

- Linux atualizado (Ubuntu Server recomendado).
- Python compatível com as dependências do projeto.
- Git.
- Uma conta e um domínio gerenciados pela Cloudflare.
- \`cloudflared\` instalado e autenticado na conta Cloudflare.
- Usuário Linux dedicado para executar a aplicação (não execute o serviço como \`root\`).

## 3. Preparar diretórios e usuário

Exemplo de estrutura no servidor:

- Código: \`/opt/fazendaweb/app\`
- Ambiente virtual: \`/opt/fazendaweb/venv\`
- Dados SQLite: \`/srv/fazendaweb/dados\`
- Backups: \`/srv/fazendaweb/backups\`
- Configuração: \`/etc/fazendaweb/fazendaweb.env\`

Crie o usuário e os diretórios (ajuste se já existirem):

\`\`\`bash
sudo useradd --system --home /opt/fazendaweb --shell /usr/sbin/nologin fazendaweb
sudo mkdir -p /opt/fazendaweb/app /srv/fazendaweb/dados/fazendas /srv/fazendaweb/backups /etc/fazendaweb
sudo chown -R fazendaweb:fazendaweb /opt/fazendaweb /srv/fazendaweb
sudo chmod 700 /srv/fazendaweb/dados /srv/fazendaweb/dados/fazendas /srv/fazendaweb/backups
sudo chmod 750 /etc/fazendaweb
\`\`\`

Clone o repositório em \`/opt/fazendaweb/app\` e instale as dependências dentro do ambiente virtual:

\`\`\`bash
sudo git clone https://github.com/LuizHFS0/Gerenciador-de-Fazendas-WEB.git /opt/fazendaweb/app
sudo python3 -m venv /opt/fazendaweb/venv
sudo /opt/fazendaweb/venv/bin/python -m pip install --upgrade pip
sudo /opt/fazendaweb/venv/bin/python -m pip install -r /opt/fazendaweb/app/requirements.txt
sudo chown -R fazendaweb:fazendaweb /opt/fazendaweb
\`\`\`

Se a pasta já tiver sido clonada, não execute o \`git clone\` novamente. Atualize o código com o fluxo de Git usado no seu servidor.

## 4. Configurar o ambiente de produção

Copie \`deploy/fazendaweb.env.example\` para \`/etc/fazendaweb/fazendaweb.env\` e substitua o domínio pelo seu:

\`\`\`bash
sudo cp /opt/fazendaweb/app/deploy/fazendaweb.env.example /etc/fazendaweb/fazendaweb.env
sudo nano /etc/fazendaweb/fazendaweb.env
sudo chmod 600 /etc/fazendaweb/fazendaweb.env
sudo chown root:fazendaweb /etc/fazendaweb/fazendaweb.env
\`\`\`

Variáveis principais:

- \`FAZENDAWEB_AMBIENTE=producao\`: ativa cookies Secure, HSTS e desliga a documentação automática.
- \`FAZENDAWEB_DADOS=/srv/fazendaweb/dados\`: mantém os bancos fora do repositório.
- \`FAZENDAWEB_BACKUPS=/srv/fazendaweb/backups\`: separa os backups dos bancos ativos.
- \`FAZENDAWEB_ORIGENS=https://app.seudominio.com\`: informe a origem HTTPS exata, sem barra no final. Se usar outro hostname para o painel, inclua-o separado por vírgula.
- \`FAZENDAWEB_PROXY_CONFIAVEL=1\`: habilita a leitura do IP encaminhado pelo proxy. O Uvicorn também ficará configurado para confiar somente no proxy local.

O arquivo de ambiente contém configuração de produção; não o coloque no Git nem compartilhe publicamente.

## 5. Criar a conta SuperAdmin

Com o ambiente configurado, crie a conta administrativa pelo terminal:

\`\`\`bash
cd /opt/fazendaweb/app
sudo -u fazendaweb /opt/fazendaweb/venv/bin/python superadmin_cli.py criar --usuario SEU_USUARIO --nome "Seu Nome"
\`\`\`

O programa solicitará a senha sem exibi-la. Use uma senha exclusiva e forte. O painel fica no caminho \`/admin\`.

## 6. Configurar o serviço FastAPI (systemd)

O repositório inclui o modelo \`deploy/fazendaweb.service\`. Copie-o e habilite:

\`\`\`bash
sudo cp /opt/fazendaweb/app/deploy/fazendaweb.service /etc/systemd/system/fazendaweb.service
sudo systemctl daemon-reload
sudo systemctl enable --now fazendaweb
sudo systemctl status fazendaweb
\`\`\`

O serviço usa um único worker inicialmente. Isso evita que o limitador de tentativas de login em memória seja duplicado entre processos e reduz concorrência de escrita no SQLite.

Confira a aplicação localmente:

\`\`\`bash
curl -I http://127.0.0.1:8000/front-end/login.html
\`\`\`

A rota \`/docs\` deve retornar 404 em produção.

## 7. Configurar Cloudflare Tunnel

1. No painel Cloudflare, adicione seu domínio e conclua a configuração DNS.
2. Instale o \`cloudflared\` no servidor conforme a documentação oficial da Cloudflare.
3. Autentique o servidor: \`cloudflared tunnel login\`.
4. Crie um túnel: \`cloudflared tunnel create fazendaweb\`.
5. Copie \`deploy/cloudflared-config.yml.example\` para \`/etc/cloudflared/config.yml\`.
6. Substitua o ID do túnel, o caminho do arquivo de credenciais e o hostname.
7. Crie a rota DNS: \`cloudflared tunnel route dns ID_DO_TUNEL app.seudominio.com\`.
8. Instale/habilite o serviço do Tunnel conforme a versão do \`cloudflared\` e a documentação da Cloudflare.

A origem configurada no Tunnel deve ser exatamente \`http://127.0.0.1:8000\`. Não exponha a porta 8000 diretamente na internet.

Depois de iniciar os dois serviços, valide:
- \`sudo systemctl status fazendaweb\`
- \`sudo systemctl status cloudflared\`
- Acesse \`https://app.seudominio.com/front-end/login.html\`
- Teste login, logout, painel SuperAdmin, cadastro e operações com mais de uma fazenda.

## 8. Backups SQLite

O projeto inclui \`backups.py\`. Ele cria uma cópia consistente de cada banco SQLite usando a API de backup do próprio SQLite, inclusive quando o banco está em modo WAL.

Criar backup manual:

\`\`\`bash
cd /opt/fazendaweb/app
sudo -u fazendaweb /opt/fazendaweb/venv/bin/python backups.py backup
\`\`\`

Cada execução cria uma pasta datada dentro de \`FAZENDAWEB_BACKUPS\`, com os bancos e um \`manifest.json\` contendo tamanho, SHA-256 e resultado de integridade.

Para automatizar um backup diário às 03:15, instale o serviço e o timer incluídos no repositório:

```bash
sudo cp /opt/fazendaweb/app/deploy/fazendaweb-backup.service /etc/systemd/system/
sudo cp /opt/fazendaweb/app/deploy/fazendaweb-backup.timer /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable --now fazendaweb-backup.timer
systemctl list-timers fazendaweb-backup.timer
```

Consulte a execução mais recente com `sudo journalctl -u fazendaweb-backup.service`. O timer depende de o projeto, o ambiente virtual e o arquivo de ambiente permanecerem nos locais indicados.

**Importante:** backup não é considerado confiável até que a restauração seja testada. Faça o teste em uma pasta isolada, nunca sobrescrevendo os bancos de produção. Mantenha cópias em outro disco ou em outro local físico; um backup no mesmo servidor não protege contra falha do próprio equipamento.

## 9. Verificação antes de publicar

Execute:

\`\`\`bash
cd /opt/fazendaweb/app
sudo -u fazendaweb /opt/fazendaweb/venv/bin/python verificar_producao.py
\`\`\`

O comando deve terminar sem alertas. Ele verifica modo de produção, origem HTTPS, diretórios protegidos, conta SuperAdmin e existência/idade do backup.

## 10. Testes

Instale dependências de desenvolvimento e execute:

\`\`\`bash
python -m pip install -r requirements-dev.txt
python -m pytest -q
\`\`\`

Os testes automatizados deste repositório são uma verificação inicial; ainda é necessário testar o fluxo completo em um servidor real antes de cadastrar dados reais.

## 11. Cuidados importantes

- Não versione bancos SQLite, logs, backups, arquivos \`.env\` ou credenciais do Tunnel.
- O log antigo \`dados/seguranca.log\` foi removido da versão atual do repositório. Como ele já esteve no histórico Git, a remoção do arquivo no último commit **não apaga as versões antigas do histórico**. Se o repositório continuar público e você quiser eliminar esses dados também do histórico, será necessário planejar uma limpeza do histórico Git e um force-push coordenado.
- Não rode o servidor de desenvolvimento com \`--reload\` em produção.
- Não use vários workers sem antes revisar os limitadores em memória e a estratégia de concorrência do SQLite.
- Não considere o servidor pronto apenas porque a página abre: teste autenticação, permissões, isolamento entre fazendas, backup e restauração.
- O Cloudflare Tunnel não substitui atualizações do sistema, firewall local, senhas fortes, controle de acesso e cópias externas.
