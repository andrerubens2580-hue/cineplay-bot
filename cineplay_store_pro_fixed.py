import logging
import sqlite3
from pathlib import Path
from telegram import ReplyKeyboardMarkup, Update
from telegram.ext import Application, CommandHandler, MessageHandler, ContextTypes, filters

BOT_TOKEN = "8395658659:AAH-FWm5sg1u9TbHm5rKq_sNF57m9WCeOKU"
ADMIN_IDS = {8307440223}
DB_PATH = Path("cineplay_store.db")

MAIN_MENU = [
    ["PRODUTOS", "PESQUISAR"],
    ["PERFIL", "SALDO"],
    ["MINHAS COMPRAS", "INDICACAO"],
    ["RANKING", "SUPORTE"],
    ["TERMOS", "/adm"],
]

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")

def conn():
    c = sqlite3.connect(DB_PATH)
    c.row_factory = sqlite3.Row
    return c

def init_db():
    c = conn()
    cur = c.cursor()
    cur.execute('CREATE TABLE IF NOT EXISTS users (user_id INTEGER PRIMARY KEY, username TEXT, first_name TEXT, balance REAL NOT NULL DEFAULT 0, referrals INTEGER NOT NULL DEFAULT 0, referred_by INTEGER, created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP)')
    cur.execute('CREATE TABLE IF NOT EXISTS products (id INTEGER PRIMARY KEY AUTOINCREMENT, name TEXT NOT NULL, price REAL NOT NULL, category TEXT NOT NULL, stock INTEGER NOT NULL DEFAULT 0, description TEXT DEFAULT "", active INTEGER NOT NULL DEFAULT 1)')
    cur.execute('CREATE TABLE IF NOT EXISTS purchases (id INTEGER PRIMARY KEY AUTOINCREMENT, user_id INTEGER NOT NULL, product_id INTEGER NOT NULL, product_name TEXT NOT NULL, price REAL NOT NULL, created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP)')
    cur.execute('CREATE TABLE IF NOT EXISTS balance_requests (id INTEGER PRIMARY KEY AUTOINCREMENT, user_id INTEGER NOT NULL, amount REAL NOT NULL, status TEXT NOT NULL DEFAULT "pending", created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP)')
    c.commit()
    total = cur.execute('SELECT COUNT(*) FROM products').fetchone()[0]
    if total == 0:
        cur.executemany('INSERT INTO products (name, price, category, stock, description, active) VALUES (?, ?, ?, ?, ?, 1)', [
            ("Plano Basico", 19.90, "Planos", 10, "Plano basico mensal"),
            ("Plano Premium", 39.90, "Planos", 8, "Plano premium mensal"),
            ("Gift Card 25", 25.00, "GiftCards", 15, "Cartao presente"),
            ("Gift Card 50", 50.00, "GiftCards", 10, "Cartao presente"),
        ])
        c.commit()
    c.close()

def money(v):
    return f"R${v:.2f}"

def kb():
    return ReplyKeyboardMarkup(MAIN_MENU, resize_keyboard=True)

def ensure_user(user_id, username, first_name):
    c = conn()
    cur = c.cursor()
    row = cur.execute('SELECT user_id FROM users WHERE user_id = ?', (user_id,)).fetchone()
    if row:
        cur.execute('UPDATE users SET username = ?, first_name = ? WHERE user_id = ?', (username, first_name, user_id))
    else:
        cur.execute('INSERT INTO users (user_id, username, first_name) VALUES (?, ?, ?)', (user_id, username, first_name))
    c.commit()
    c.close()

def get_user(user_id):
    c = conn()
    row = c.execute('SELECT * FROM users WHERE user_id = ?', (user_id,)).fetchone()
    c.close()
    return row

def list_products():
    c = conn()
    rows = c.execute('SELECT * FROM products WHERE active = 1 ORDER BY category, price, name').fetchall()
    c.close()
    return rows

def search_products(term):
    q = f"%{term.lower()}%"
    c = conn()
    rows = c.execute('SELECT * FROM products WHERE active = 1 AND (LOWER(name) LIKE ? OR LOWER(category) LIKE ? OR LOWER(description) LIKE ?) ORDER BY price, name', (q, q, q)).fetchall()
    c.close()
    return rows

def get_history(user_id, limit=10):
    c = conn()
    rows = c.execute('SELECT product_name, price, created_at FROM purchases WHERE user_id = ? ORDER BY id DESC LIMIT ?', (user_id, limit)).fetchall()
    c.close()
    return rows

def add_balance_request(user_id, amount):
    c = conn()
    c.execute('INSERT INTO balance_requests (user_id, amount) VALUES (?, ?)', (user_id, amount))
    c.commit()
    c.close()

def add_balance(user_id, amount):
    c = conn()
    c.execute('UPDATE users SET balance = balance + ? WHERE user_id = ?', (amount, user_id))
    c.commit()
    c.close()

def buy(user_id, product_id):
    c = conn()
    cur = c.cursor()
    user = cur.execute('SELECT * FROM users WHERE user_id = ?', (user_id,)).fetchone()
    product = cur.execute('SELECT * FROM products WHERE id = ? AND active = 1', (product_id,)).fetchone()
    if not user or not product:
        c.close()
        return 'Usuario ou produto nao encontrado.'
    if product['stock'] <= 0:
        c.close()
        return 'Produto sem estoque.'
    if float(user['balance']) < float(product['price']):
        c.close()
        return 'Saldo insuficiente.'
    cur.execute('UPDATE users SET balance = balance - ? WHERE user_id = ?', (product['price'], user_id))
    cur.execute('UPDATE products SET stock = stock - 1 WHERE id = ?', (product_id,))
    cur.execute('INSERT INTO purchases (user_id, product_id, product_name, price) VALUES (?, ?, ?, ?)', (user_id, product_id, product['name'], product['price']))
    c.commit()
    c.close()
    return f"Compra realizada.\nProduto: {product['name']}\nValor: {money(product['price'])}"

def ranking():
    c = conn()
    rows = c.execute('SELECT u.first_name, u.username, COUNT(p.id) AS total, COALESCE(SUM(p.price), 0) AS spent FROM users u LEFT JOIN purchases p ON p.user_id = u.user_id GROUP BY u.user_id ORDER BY total DESC, spent DESC LIMIT 10').fetchall()
    c.close()
    return rows

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not update.message or not update.effective_user:
        return
    user = update.effective_user
    ensure_user(user.id, user.username, user.first_name)
    await update.message.reply_text('Bem-vindo a Cineplay Store.\nEscolha uma opcao no menu.', reply_markup=kb())

async def adm(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not update.message or not update.effective_user:
        return
    if update.effective_user.id not in ADMIN_IDS:
        await update.message.reply_text('Acesso negado.')
        return
    await update.message.reply_text('PAINEL ADM\n\n/addproduct Nome | 19.90 | Categoria | 10 | Descricao\n/addbalance user_id valor')

async def admin_addproduct(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not update.message or not update.effective_user:
        return
    if update.effective_user.id not in ADMIN_IDS:
        await update.message.reply_text('Acesso negado.')
        return
    raw = update.message.text.replace('/addproduct', '', 1).strip()
    parts = [p.strip() for p in raw.split('|')]
    if len(parts) != 5:
        await update.message.reply_text('Use: /addproduct Nome | 19.90 | Categoria | 10 | Descricao')
        return
    try:
        name = parts[0]
        price = float(parts[1].replace(',', '.'))
        category = parts[2]
        stock = int(parts[3])
        description = parts[4]
    except Exception:
        await update.message.reply_text('Dados invalidos.')
        return
    c = conn()
    c.execute('INSERT INTO products (name, price, category, stock, description, active) VALUES (?, ?, ?, ?, ?, 1)', (name, price, category, stock, description))
    c.commit()
    c.close()
    await update.message.reply_text('Produto cadastrado.')

async def admin_addbalance(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not update.message or not update.effective_user:
        return
    if update.effective_user.id not in ADMIN_IDS:
        await update.message.reply_text('Acesso negado.')
        return
    parts = update.message.text.split()
    if len(parts) != 3:
        await update.message.reply_text('Use: /addbalance user_id valor')
        return
    try:
        user_id = int(parts[1])
        amount = float(parts[2].replace(',', '.'))
    except Exception:
        await update.message.reply_text('Dados invalidos.')
        return
    add_balance(user_id, amount)
    await update.message.reply_text('Saldo adicionado.')

async def route_text(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not update.message or not update.effective_user:
        return
    text = update.message.text.strip()
    user = update.effective_user
    ensure_user(user.id, user.username, user.first_name)

    if text == 'PRODUTOS':
        rows = list_products()
        if not rows:
            await update.message.reply_text('Nenhum produto disponivel.')
            return
        lines = ['CATALOGO', 'Para comprar, envie: comprar ID', '']
        current = None
        for p in rows:
            if p['category'] != current:
                current = p['category']
                lines.append(f"[{current}]")
            lines.append(f"ID {p['id']} - {p['name']} - {money(p['price'])} - estoque {p['stock']}")
        await update.message.reply_text('\n'.join(lines))
        return

    if text == 'PESQUISAR':
        await update.message.reply_text('Use: pesquisar nome')
        return

    if text.lower().startswith('pesquisar '):
        term = text[10:].strip()
        rows = search_products(term)
        if not rows:
            await update.message.reply_text('Nenhum produto encontrado.')
            return
        lines = [f"Resultados para: {term}", '']
        for p in rows:
            lines.append(f"ID {p['id']} - {p['name']} - {money(p['price'])} - estoque {p['stock']}")
        await update.message.reply_text('\n'.join(lines))
        return

    if text == 'PERFIL':
        row = get_user(user.id)
        if not row:
            await update.message.reply_text('Perfil nao encontrado.')
            return
        hist = get_history(user.id, 5)
        hist_text = '\n'.join([f"- {h['product_name']} - {money(h['price'])}" for h in hist]) or 'Nenhuma compra.'
        username = f"@{row['username']}" if row['username'] else 'nao definido'
        await update.message.reply_text(f"PERFIL\n\nNome: {row['first_name'] or 'Nao informado'}\nUsername: {username}\nID: {user.id}\nSaldo: {money(row['balance'])}\nIndicacoes: {row['referrals']}\n\nUltimas compras:\n{hist_text}")
        return

    if text == 'SALDO':
        await update.message.reply_text('Para solicitar saldo, envie: saldo 25')
        return

    if text.lower().startswith('saldo '):
        try:
            amount = float(text.split(maxsplit=1)[1].replace(',', '.'))
            if amount <= 0:
                raise ValueError
        except Exception:
            await update.message.reply_text('Use: saldo 25')
            return
        add_balance_request(user.id, amount)
        await update.message.reply_text(f"Solicitacao criada: {money(amount)}")
        return

    if text == 'MINHAS COMPRAS':
        hist = get_history(user.id, 15)
        if not hist:
            await update.message.reply_text('Voce ainda nao fez compras.')
            return
        lines = ['MINHAS COMPRAS', '']
        for h in hist:
            lines.append(f"- {h['product_name']} - {money(h['price'])} - {h['created_at']}")
        await update.message.reply_text('\n'.join(lines))
        return

    if text == 'INDICACAO':
        bot_username = context.bot.username or 'seu_bot'
        await update.message.reply_text(f"Seu link:\nhttps://t.me/{bot_username}?start={user.id}")
        return

    if text == 'RANKING':
        rows = ranking()
        if not rows:
            await update.message.reply_text('Sem ranking ainda.')
            return
        lines = ['RANKING', '']
        for i, r in enumerate(rows, start=1):
            name = r['first_name'] or (f"@{r['username']}" if r['username'] else 'Usuario')
            lines.append(f"{i}. {name} - {r['total']} compras - {money(r['spent'])}")
        await update.message.reply_text('\n'.join(lines))
        return

    if text == 'SUPORTE':
        await update.message.reply_text('Suporte: fale com a administracao.')
        return

    if text == 'TERMOS':
        await update.message.reply_text('Leia a descricao antes de comprar.')
        return

    if text.lower().startswith('comprar '):
        try:
            product_id = int(text.split(maxsplit=1)[1])
        except Exception:
            await update.message.reply_text('Use: comprar 1')
            return
        await update.message.reply_text(buy(user.id, product_id))
        return

    await update.message.reply_text('Nao entendi. Use /start.')

def main():
    if BOT_TOKEN == 'COLE_SEU_TOKEN_AQUI':
        raise RuntimeError('Cole seu token na variavel BOT_TOKEN.')
    init_db()
    app = Application.builder().token(BOT_TOKEN).build()
    app.add_handler(CommandHandler('start', start))
    app.add_handler(CommandHandler('adm', adm))
    app.add_handler(CommandHandler('addproduct', admin_addproduct))
    app.add_handler(CommandHandler('addbalance', admin_addbalance))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, route_text))
    app.run_polling(drop_pending_updates=True)

if __name__ == '__main__':
    main()
