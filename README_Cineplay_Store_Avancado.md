# Cineplay Store - Bot Telegram Avançado

## Arquivos
- `cineplay_store_bot_avancado.py`
- `requirements.txt`
- `.env.example`

## Recursos desta versão
- `/adm` com menu administrativo
- adicionar produto
- editar produto
- desativar produto
- alterar estoque
- editar textos do bot
- ver usuários
- aprovar/rejeitar saldo
- ajustar saldo manualmente
- broadcast
- estatísticas
- SQLite

## Instalação
```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

## Configuração
```bash
export BOT_TOKEN="SEU_TOKEN"
export ADMIN_IDS="SEU_ID"
```

## Execução
```bash
python cineplay_store_bot_avancado.py
```

## Comandos
- `/start`
- `/adm`
- `/cancel`

## Observação
Este é um template de loja digital genérica e legítima.
Não inclui automação de pagamento nem fluxos para venda de acessos não autorizados.
