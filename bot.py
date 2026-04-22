import telebot
import json
import random
from telebot.types import ReplyKeyboardMarkup

TOKEN = "COLOQUE_SEU_TOKEN_AQUI"

bot = telebot.TeleBot(TOKEN)

ARQ_USERS = "usuarios.json"
ARQ_PROD = "produtos.json"

SUPORTE = "@SeuContato"
PIX = "81996075639"

ADMIN_ID = 123456789


def carregar(arq):
    try:
        with open(arq,"r") as f:
            return json.load(f)
    except:
        return {}

def salvar(arq,data):
    with open(arq,"w") as f:
        json.dump(data,f,indent=4)

usuarios = carregar(ARQ_USERS)
produtos = carregar(ARQ_PROD)


def menu():
    kb = ReplyKeyboardMarkup(resize_keyboard=True)
    kb.add("✨ COMPRAR CONTAS ✨")
    kb.add("💗 PERFIL 💗","💸 ADICIONAR SALDO 💸")
    kb.add("🔎 PESQUISAR PRODUTO")
    kb.add("👩‍💻 SUPORTE","⚠ TERMOS ⚠")
    kb.add("🎰 ROLETA","🏆 RANKING")
    return kb


@bot.message_handler(commands=['start'])
def start(msg):

    uid = str(msg.chat.id)

    if uid not in usuarios:

        usuarios[uid] = {
            "nome":msg.from_user.first_name,
            "saldo":0,
            "compras":0
        }

        salvar(ARQ_USERS,usuarios)

    u = usuarios[uid]

    texto = f"""
📌 SUAS INFORMAÇÕES

🎀 Nome: {u["nome"]}
🆔 ID: {uid}

💰 Saldo: R${u["saldo"]}
🛒 Compras: {u["compras"]}

💗 Bem vindo à CinePlay Store
"""

    bot.send_message(uid,texto,reply_markup=menu())


# PERFIL
@bot.message_handler(func=lambda m: m.text=="💗 PERFIL 💗")
def perfil(msg):

    uid=str(msg.chat.id)
    u=usuarios[uid]

    bot.send_message(uid,f"""
👤 PERFIL

Nome: {u["nome"]}
ID: {uid}

💰 Saldo: R${u["saldo"]}
🛒 Compras: {u["compras"]}
""",reply_markup=menu())


# ADICIONAR SALDO
@bot.message_handler(func=lambda m: m.text=="💸 ADICIONAR SALDO 💸")
def addsaldo(msg):

    bot.send_message(msg.chat.id,f"""
💳 PAGAMENTO PIX

Envie o valor que deseja pagar para:

{PIX}

Depois envie o comprovante ao suporte.
""",reply_markup=menu())


# CATÁLOGO
@bot.message_handler(func=lambda m: m.text=="✨ COMPRAR CONTAS ✨")
def catalogo(msg):

    if not produtos:

        bot.send_message(msg.chat.id,"Nenhum produto disponível.",reply_markup=menu())
        return

    texto="🛒 CATÁLOGO\n\n"

    for p in produtos:

        texto+=f"{p} - R${produtos[p]['preco']}\n"

    texto+="\nDigite o nome do produto para comprar."

    bot.send_message(msg.chat.id,texto,reply_markup=menu())


# COMPRAR
@bot.message_handler(func=lambda m: m.text in produtos)
def comprar(msg):

    uid=str(msg.chat.id)
    prod=msg.text

    preco=produtos[prod]["preco"]

    if usuarios[uid]["saldo"] < preco:

        bot.send_message(uid,"❌ Saldo insuficiente.",reply_markup=menu())
        return

    usuarios[uid]["saldo"]-=preco
    usuarios[uid]["compras"]+=1

    salvar(ARQ_USERS,usuarios)

    conta=random.choice(produtos[prod]["contas"])

    bot.send_message(uid,f"""
✅ COMPRA REALIZADA

Produto: {prod}

Login entregue:
{conta}

💰 Saldo restante: R${usuarios[uid]["saldo"]}
""",reply_markup=menu())


# PESQUISA
@bot.message_handler(func=lambda m: m.text=="🔎 PESQUISAR PRODUTO")
def pesquisar(msg):

    bot.send_message(msg.chat.id,"Digite o nome do produto:",reply_markup=menu())


# SUPORTE
@bot.message_handler(func=lambda m: m.text=="👩‍💻 SUPORTE")
def suporte(msg):

    bot.send_message(msg.chat.id,f"Suporte: {SUPORTE}",reply_markup=menu())


# TERMOS
@bot.message_handler(func=lambda m: m.text=="⚠ TERMOS ⚠")
def termos(msg):

    bot.send_message(msg.chat.id,"Sem reembolso após entrega.",reply_markup=menu())


# ROLETA
@bot.message_handler(func=lambda m: m.text=="🎰 ROLETA")
def roleta(msg):

    uid=str(msg.chat.id)

    if random.randint(1,5)==3:

        premio=5
        usuarios[uid]["saldo"]+=premio
        salvar(ARQ_USERS,usuarios)

        bot.send_message(uid,f"🎉 Você ganhou R${premio}!",reply_markup=menu())

    else:

        bot.send_message(uid,"❌ Não ganhou dessa vez.",reply_markup=menu())


# RANKING
@bot.message_handler(func=lambda m: m.text=="🏆 RANKING")
def ranking(msg):

    top=sorted(usuarios.items(), key=lambda x:x[1]["compras"], reverse=True)

    texto="🏆 RANKING\n\n"

    for i,u in enumerate(top[:5],start=1):

        texto+=f"{i}. {u[1]['nome']} - {u[1]['compras']} compras\n"

    bot.send_message(msg.chat.id,texto,reply_markup=menu())


bot.polling()
