"""
Cineplay Store - Bot Telegram Avançado
======================================
Template avançado de loja digital genérica com painel /adm.

Recursos:
- Menu principal
- Perfil, compras, saldo, indicação
- Catálogo e busca
- Compra por ID com saldo interno
- Solicitação de saldo manual
- Painel admin com fluxos conversacionais:
    - Gerenciar produtos
    - Editar textos
    - Ver usuários
    - Aprovar/rejeitar solicitações de saldo
    - Broadcast
    - Configurações
- Persistência SQLite

Observação:
Este template é genérico para loja digital legítima.
Não inclui automação para venda de acessos não autorizados nem pagamento automático.
"""

from __future__ import annotations

import logging
import os
import sqlite3
from contextlib import closing
from pathlib import Path
from typing import Optional

from telegram import ReplyKeyboardMarkup, ReplyKeyboardRemove, Update
from telegram.constants import ParseMode
from telegram.ext import (
    Application,
    CommandHandler,
    ContextTypes,
    MessageHandler,
    filters,
)

DB_PATH = Path("cineplay_store_avancado.db")
BOT_TITLE = "Cineplay Store"

logging.basicConfig(
    format="%(asctime)s | %(name)s | %(levelname)s | %(message)s",
    level=logging.INFO,
)
logger = logging.getLogger(__name__)


# =========================
# DATABASE
# =========================

def get_conn() -> sqlite3.Connection:
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def init_db() -> None:
    with closing(get_conn()) as conn:
        cur = conn.cursor()

        cur.execute(
            """
            CREATE TABLE IF NOT EXISTS users (
                user_id INTEGER PRIMARY KEY,
                username TEXT,
                first_name TEXT,
                balance REAL NOT NULL DEFAULT 0,
                referrals INTEGER NOT NULL DEFAULT 0,
                referred_by INTEGER,
                is_banned INTEGER NOT NULL DEFAULT 0,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
            """
        )

        cur.execute(
            """
            CREATE TABLE IF NOT EXISTS products (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL,
                price REAL NOT NULL,
                category TEXT NOT NULL,
                stock INTEGER NOT NULL DEFAULT 0,
                description TEXT DEFAULT '',
                active INTEGER NOT NULL DEFAULT 1,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
            """
        )

        cur.execute(
            """
            CREATE TABLE IF NOT EXISTS purchases (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                product_id INTEGER NOT NULL,
                product_name TEXT NOT NULL,
                price REAL NOT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
            """
        )

        cur.execute(
            """
            CREATE TABLE IF NOT EXISTS balance_requests (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                amount REAL NOT NULL,
                method TEXT DEFAULT 'manual',
                note TEXT DEFAULT '',
                status TEXT NOT NULL DEFAULT 'pending',
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                processed_at TIMESTAMP
            )
            """
        )

        cur.execute(
            """
            CREATE TABLE IF NOT EXISTS bot_texts (
                key TEXT PRIMARY KEY,
                value TEXT NOT NULL
            )
            """
        )

        conn.commit()

    seed_defaults()


def seed_defaults() -> None:
    with closing(get_conn()) as conn:
        cur = conn.cursor()

        defaults = {
            "welcome_text": (
                "💗 *Bem-vindo à Cineplay Store!*\n\n"
                "Aqui você encontra produtos digitais legítimos com organização, suporte e praticidade.\n\n"
                "✨ Recursos do bot:\n"
                "• Catálogo de produtos\n"
                "• Perfil do cliente\n"
                "• Saldo interno\n"
                "• Busca de produtos\n"
                "• Ranking\n"
                "• Indicação\n\n"
                "Escolha uma opção no menu abaixo."
            ),
            "support_text": (
                "👩🏻‍💻 *SUPORTE*\n\n"
                "Horário padrão:\n"
                "• Segunda a sexta: 14h às 22h\n"
                "• Sábado: 14h às 18h\n"
                "• Domingo/feriado: sem atendimento\n\n"
                "Prazo médio: 24h a 48h."
            ),
            "terms_text": (
                "⚠️ *TERMOS*\n\n"
                "• Leia a descrição do produto antes de comprar.\n"
                "• Não há reembolso após entrega do serviço/produto.\n"
                "• O comprador deve fornecer informações corretas.\n"
                "• Use apenas de forma autorizada e legal.\n"
                "• O catálogo deve conter apenas itens permitidos."
            ),
            "deposit_text": (
                "💸 *ADICIONAR SALDO*\n\n"
                "Envie assim:\n"
                "`saldo 25`\n\n"
                "Depois confirme manualmente no seu processo interno."
            ),
            "idle_text": (
                "✨ Confira nosso catálogo quando quiser. Estamos por aqui."
            ),
        }

        for key, value in defaults.items():
            cur.execute(
                "INSERT OR IGNORE INTO bot_texts (key, value) VALUES (?, ?)",
                (key, value),
            )

        product_count = cur.execute("SELECT COUNT(*) FROM products").fetchone()[0]
        if product_count == 0:
            cur.executemany(
                """
                INSERT INTO products (name, price, category, stock, description, active)
                VALUES (?, ?, ?, ?, ?, 1)
                """,
                [
                    ("Plano Básico Mensal", 19.90, "Planos", 10, "Plano básico mensal."),
                    ("Plano Premium Mensal", 39.90, "Planos", 8, "Plano premium mensal."),
                    ("Gift Card R$25", 25.00, "Gift Cards", 15, "Cartão-presente digital."),
                    ("Gift Card R$50", 50.00, "Gift Cards", 10, "Cartão-presente digital."),
                    ("Suporte Prioritário", 9.90, "Serviços", 50, "Fila preferencial."),
                ],
            )

        conn.commit()


# =========================
# HELPERS
# =========================

def is_admin(user_id: int) -> bool:
    raw = os.getenv("ADMIN_IDS", "")
    admins = {int(x.strip()) for x in raw.split(",") if x.strip().isdigit()}
    return user_id in admins


def money(v: float) -> str:
    return f"R${v:.2f}"


def main_keyboard() -> ReplyKeyboardMarkup:
    return ReplyKeyboardMarkup(
        [
            ["✨ COMPRAR PRODUTOS ✨"],
            ["💗 PERFIL 💗", "💸 ADICIONAR SALDO 💸"],
            ["🔎 PESQUISAR PRODUTO"],
            ["👩🏻‍💻 SUPORTE", "⚠️ TERMOS ⚠️"],
            ["🏆 RANKING", "🎁 INDICAR AMIGO"],
            ["↩️ VOLTAR AO INÍCIO"],
        ],
        resize_keyboard=True,
    )


def admin_keyboard() -> ReplyKeyboardMarkup:
    return ReplyKeyboardMarkup(
        [
            ["📦 GERENCIAR PRODUTOS", "💰 SOLICITAÇÕES DE SALDO"],
            ["📝 EDITAR TEXTOS", "👥 VER USUÁRIOS"],
            ["📣 BROADCAST", "⚙️ CONFIGURAÇÕES"],
            ["💳 AJUSTAR SALDO", "📊 ESTATÍSTICAS"],
            ["🚪 SAIR DO ADMIN"],
        ],
        resize_keyboard=True,
    )


def product_manage_keyboard() -> ReplyKeyboardMarkup:
    return ReplyKeyboardMarkup(
        [
            ["➕ ADICIONAR PRODUTO", "📋 LISTAR PRODUTOS"],
            ["✏️ EDITAR PRODUTO", "🗑️ DESATIVAR PRODUTO"],
            ["📦 ALTERAR ESTOQUE", "🔙 VOLTAR ADMIN"],
        ],
        resize_keyboard=True,
    )


def texts_keyboard() -> ReplyKeyboardMarkup:
    return ReplyKeyboardMarkup(
        [
            ["✍️ BOAS-VINDAS", "✍️ SUPORTE"],
            ["✍️ TERMOS", "✍️ DEPÓSITO"],
            ["✍️ MENSAGEM OCIOSA", "🔙 VOLTAR ADMIN"],
        ],
        resize_keyboard=True,
    )


def settings_keyboard() -> ReplyKeyboardMarkup:
    return ReplyKeyboardMarkup(
        [
            ["👁️ VER TEXTOS", "🧹 LIMPAR ESTADO"],
            ["🔙 VOLTAR ADMIN"],
        ],
        resize_keyboard=True,
    )


def set_state(context: ContextTypes.DEFAULT_TYPE, state: Optional[str]) -> None:
    context.user_data["state"] = state


def get_state(context: ContextTypes.DEFAULT_TYPE) -> Optional[str]:
    return context.user_data.get("state")


def clear_state(context: ContextTypes.DEFAULT_TYPE) -> None:
    keys = [
        "state",
        "edit_product_id",
        "edit_text_key",
        "pending_user_id",
        "pending_product_id",
        "pending_action",
    ]
    for k in keys:
        context.user_data.pop(k, None)


def get_text_value(key: str) -> str:
    with closing(get_conn()) as conn:
        row = conn.execute("SELECT value FROM bot_texts WHERE key = ?", (key,)).fetchone()
        return row["value"] if row else ""


def update_text_value(key: str, value: str) -> None:
    with closing(get_conn()) as conn:
        conn.execute(
            """
            INSERT INTO bot_texts (key, value) VALUES (?, ?)
            ON CONFLICT(key) DO UPDATE SET value = excluded.value
            """,
            (key, value),
        )
        conn.commit()


def ensure_user(user_id: int, username: str | None, first_name: str | None) -> None:
    with closing(get_conn()) as conn:
        cur = conn.cursor()
        row = cur.execute("SELECT user_id FROM users WHERE user_id = ?", (user_id,)).fetchone()
        if row:
            cur.execute(
                "UPDATE users SET username = ?, first_name = ? WHERE user_id = ?",
                (username, first_name, user_id),
            )
        else:
            cur.execute(
                """
                INSERT INTO users (user_id, username, first_name)
                VALUES (?, ?, ?)
                """,
                (user_id, username, first_name),
            )
        conn.commit()


# =========================
# USER DATA
# =========================

def register_referral(new_user_id: int, referrer_id: int) -> bool:
    if new_user_id == referrer_id:
        return False

    with closing(get_conn()) as conn:
        cur = conn.cursor()
        user = cur.execute("SELECT referred_by FROM users WHERE user_id = ?", (new_user_id,)).fetchone()
        ref = cur.execute("SELECT user_id FROM users WHERE user_id = ?", (referrer_id,)).fetchone()

        if not user or not ref or user["referred_by"] is not None:
            return False

        cur.execute("UPDATE users SET referred_by = ? WHERE user_id = ?", (referrer_id, new_user_id))
        cur.execute("UPDATE users SET referrals = referrals + 1 WHERE user_id = ?", (referrer_id,))
        conn.commit()
        return True


def get_user(user_id: int) -> Optional[sqlite3.Row]:
    with closing(get_conn()) as conn:
        return conn.execute("SELECT * FROM users WHERE user_id = ?", (user_id,)).fetchone()


def add_balance_request(user_id: int, amount: float, note: str = "") -> None:
    with closing(get_conn()) as conn:
        conn.execute(
            "INSERT INTO balance_requests (user_id, amount, note) VALUES (?, ?, ?)",
            (user_id, amount, note),
        )
        conn.commit()


def add_balance(user_id: int, amount: float) -> None:
    with closing(get_conn()) as conn:
        conn.execute("UPDATE users SET balance = balance + ? WHERE user_id = ?", (amount, user_id))
        conn.commit()


def set_balance(user_id: int, amount: float) -> None:
    with closing(get_conn()) as conn:
        conn.execute("UPDATE users SET balance = ? WHERE user_id = ?", (amount, user_id))
        conn.commit()


def get_purchase_stats(user_id: int) -> dict:
    with closing(get_conn()) as conn:
        total_items = conn.execute(
            "SELECT COUNT(*) FROM purchases WHERE user_id = ?", (user_id,)
        ).fetchone()[0]
        total_spent = conn.execute(
            "SELECT COALESCE(SUM(price), 0) FROM purchases WHERE user_id = ?", (user_id,)
        ).fetchone()[0]
        return {"count": total_items, "spent": float(total_spent or 0)}


def get_purchase_history(user_id: int, limit: int = 8) -> list[sqlite3.Row]:
    with closing(get_conn()) as conn:
        return conn.execute(
            """
            SELECT product_name, price, created_at
            FROM purchases
            WHERE user_id = ?
            ORDER BY id DESC
            LIMIT ?
            """,
            (user_id, limit),
        ).fetchall()


# =========================
# PRODUCTS
# =========================

def list_active_products() -> list[sqlite3.Row]:
    with closing(get_conn()) as conn:
        return conn.execute(
            """
            SELECT * FROM products
            WHERE active = 1
            ORDER BY category, price, name
            """
        ).fetchall()


def list_all_products() -> list[sqlite3.Row]:
    with closing(get_conn()) as conn:
        return conn.execute(
            "SELECT * FROM products ORDER BY id DESC"
        ).fetchall()


def search_products(term: str) -> list[sqlite3.Row]:
    q = f"%{term.lower()}%"
    with closing(get_conn()) as conn:
        return conn.execute(
            """
            SELECT * FROM products
            WHERE active = 1 AND (
                LOWER(name) LIKE ? OR
                LOWER(category) LIKE ? OR
                LOWER(description) LIKE ?
            )
            ORDER BY price, name
            """,
            (q, q, q),
        ).fetchall()


def get_product(product_id: int) -> Optional[sqlite3.Row]:
    with closing(get_conn()) as conn:
        return conn.execute("SELECT * FROM products WHERE id = ?", (product_id,)).fetchone()


def create_product(name: str, price: float, category: str, stock: int, description: str) -> None:
    with closing(get_conn()) as conn:
        conn.execute(
            """
            INSERT INTO products (name, price, category, stock, description, active)
            VALUES (?, ?, ?, ?, ?, 1)
            """,
            (name, price, category, stock, description),
        )
        conn.commit()


def update_product_field(product_id: int, field: str, value) -> None:
    allowed = {"name", "price", "category", "stock", "description", "active"}
    if field not in allowed:
        raise ValueError("Campo inválido.")
    with closing(get_conn()) as conn:
        conn.execute(f"UPDATE products SET {field} = ? WHERE id = ?", (value, product_id))
        conn.commit()


def purchase_product(user_id: int, product_id: int) -> tuple[bool, str]:
    with closing(get_conn()) as conn:
        cur = conn.cursor()
        user = cur.execute("SELECT * FROM users WHERE user_id = ?", (user_id,)).fetchone()
        product = cur.execute(
            "SELECT * FROM products WHERE id = ? AND active = 1", (product_id,)
        ).fetchone()

        if not user or not product:
            return False, "Produto ou usuário não encontrado."
        if product["stock"] <= 0:
            return False, "Produto sem estoque."
        if float(user["balance"]) < float(product["price"]):
            return False, "Saldo insuficiente."

        cur.execute(
            "UPDATE users SET balance = balance - ? WHERE user_id = ?",
            (product["price"], user_id),
        )
        cur.execute(
            "UPDATE products SET stock = stock - 1 WHERE id = ?",
            (product_id,),
        )
        cur.execute(
            """
            INSERT INTO purchases (user_id, product_id, product_name, price)
            VALUES (?, ?, ?, ?)
            """,
            (user_id, product_id, product["name"], product["price"]),
        )
        conn.commit()

        return True, (
            "✅ Compra aprovada.\n\n"
            f"Produto: {product['name']}\n"
            f"Valor: {money(product['price'])}\n"
            "O item foi registrado no histórico."
        )


# =========================
# ADMIN DATA
# =========================

def get_pending_balance_requests(limit: int = 20) -> list[sqlite3.Row]:
    with closing(get_conn()) as conn:
        return conn.execute(
            """
            SELECT * FROM balance_requests
            WHERE status = 'pending'
            ORDER BY id ASC
            LIMIT ?
            """,
            (limit,),
        ).fetchall()


def process_balance_request(request_id: int, approve: bool) -> tuple[bool, str]:
    with closing(get_conn()) as conn:
        cur = conn.cursor()
        row = cur.execute(
            "SELECT * FROM balance_requests WHERE id = ?",
            (request_id,),
        ).fetchone()

        if not row:
            return False, "Solicitação não encontrada."
        if row["status"] != "pending":
            return False, "Essa solicitação já foi processada."

        if approve:
            cur.execute(
                "UPDATE users SET balance = balance + ? WHERE user_id = ?",
                (row["amount"], row["user_id"]),
            )
            cur.execute(
                """
                UPDATE balance_requests
                SET status = 'approved', processed_at = CURRENT_TIMESTAMP
                WHERE id = ?
                """,
                (request_id,),
            )
            conn.commit()
            return True, f"✅ Solicitação {request_id} aprovada."
        else:
            cur.execute(
                """
                UPDATE balance_requests
                SET status = 'rejected', processed_at = CURRENT_TIMESTAMP
                WHERE id = ?
                """,
                (request_id,),
            )
            conn.commit()
            return True, f"❌ Solicitação {request_id} rejeitada."


def get_users(limit: int = 20) -> list[sqlite3.Row]:
    with closing(get_conn()) as conn:
        return conn.execute(
            """
            SELECT *
            FROM users
            ORDER BY created_at DESC
            LIMIT ?
            """,
            (limit,),
        ).fetchall()


def get_admin_stats() -> dict:
    with closing(get_conn()) as conn:
        users = conn.execute("SELECT COUNT(*) FROM users").fetchone()[0]
        products = conn.execute("SELECT COUNT(*) FROM products WHERE active = 1").fetchone()[0]
        pending = conn.execute(
            "SELECT COUNT(*) FROM balance_requests WHERE status = 'pending'"
        ).fetchone()[0]
        purchases = conn.execute("SELECT COUNT(*) FROM purchases").fetchone()[0]
        revenue = conn.execute("SELECT COALESCE(SUM(price), 0) FROM purchases").fetchone()[0]
        return {
            "users": users,
            "products": products,
            "pending": pending,
            "purchases": purchases,
            "revenue": float(revenue or 0),
        }


# =========================
# COMMANDS
# =========================

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not update.message or not update.effective_user:
        return

    user = update.effective_user
    ensure_user(user.id, user.username, user.first_name)
    clear_state(context)

    if context.args:
        try:
            ref_id = int(context.args[0])
            if register_referral(user.id, ref_id):
                await update.message.reply_text("🎁 Indicação registrada com sucesso.")
        except ValueError:
            pass

    await update.message.reply_text(
        get_text_value("welcome_text"),
        parse_mode=ParseMode.MARKDOWN,
        reply_markup=main_keyboard(),
    )


async def adm(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not update.message or not update.effective_user:
        return
    if not is_admin(update.effective_user.id):
        await update.message.reply_text("Acesso negado.")
        return

    clear_state(context)
    await update.message.reply_text(
        "🔧 *PAINEL ADMIN ATIVADO*\n\nEscolha uma opção abaixo.",
        parse_mode=ParseMode.MARKDOWN,
        reply_markup=admin_keyboard(),
    )


async def cancel(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not update.message:
        return
    clear_state(context)
    await update.message.reply_text(
        "Operação cancelada.",
        reply_markup=main_keyboard(),
    )


# =========================
# USER FEATURES
# =========================

async def show_profile(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not update.message or not update.effective_user:
        return

    uid = update.effective_user.id
    ensure_user(uid, update.effective_user.username, update.effective_user.first_name)

    user = get_user(uid)
    if not user:
        await update.message.reply_text("Perfil não encontrado.")
        return

    stats = get_purchase_stats(uid)
    history = get_purchase_history(uid, 5)
    history_text = "\n".join(
        f"• {h['product_name']} — {money(h['price'])} ({h['created_at']})"
        for h in history
    ) or "Nenhuma compra."

    username = f"@{user['username']}" if user["username"] else "não definido"
    invite = f"https://t.me/{context.bot.username}?start={uid}" if context.bot.username else "indisponível"

    text = (
        "💗 *SEU PERFIL*\n\n"
        f"• Nome: {user['first_name'] or 'não definido'}\n"
        f"• Username: {username}\n"
        f"• ID: `{uid}`\n"
        f"• Saldo: *{money(user['balance'])}*\n"
        f"• Indicações: *{user['referrals']}*\n"
        f"• Link de indicação: {invite}\n\n"
        f"🛒 *Compras*\n"
        f"• Itens comprados: {stats['count']}\n"
        f"• Total gasto: {money(stats['spent'])}\n\n"
        f"🧾 *Últimas compras*\n{history_text}"
    )
    await update.message.reply_text(
        text,
        parse_mode=ParseMode.MARKDOWN,
        disable_web_page_preview=True,
    )


async def show_catalog(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not update.message:
        return

    rows = list_active_products()
    if not rows:
        await update.message.reply_text("Nenhum produto disponível.")
        return

    lines = ["✨ *CATÁLOGO*\n", "Para comprar, envie: `comprar ID`\n"]
    last_cat = None
    for p in rows:
        if p["category"] != last_cat:
            last_cat = p["category"]
            lines.append(f"\n📂 *{last_cat}*")
        lines.append(
            f"ID {p['id']} — *{p['name']}* | {money(p['price'])} | estoque: {p['stock']}"
        )

    text = "\n".join(lines)
    for chunk in [text[i:i+3500] for i in range(0, len(text), 3500)]:
        await update.message.reply_text(chunk, parse_mode=ParseMode.MARKDOWN)


async def search_catalog(update: Update, context: ContextTypes.DEFAULT_TYPE, term: str) -> None:
    if not update.message:
        return

    results = search_products(term)
    if not results:
        await update.message.reply_text("Nenhum resultado encontrado.")
        return

    lines = [f"🔎 *Resultados para:* `{term}`\n", "Para comprar, envie: `comprar ID`\n"]
    for p in results:
        lines.append(
            f"ID {p['id']} — *{p['name']}* | {money(p['price'])} | estoque: {p['stock']}"
        )
    await update.message.reply_text("\n".join(lines), parse_mode=ParseMode.MARKDOWN)


async def request_balance(update: Update, context: ContextTypes.DEFAULT_TYPE, amount: float) -> None:
    if not update.message or not update.effective_user:
        return
    add_balance_request(update.effective_user.id, amount)
    await update.message.reply_text(
        f"✅ Solicitação criada para *{money(amount)}*.\n"
        "Um administrador precisa aprovar manualmente.",
        parse_mode=ParseMode.MARKDOWN,
    )


async def buy_product(update: Update, context: ContextTypes.DEFAULT_TYPE, product_id: int) -> None:
    if not update.message or not update.effective_user:
        return
    ok, msg = purchase_product(update.effective_user.id, product_id)
    await update.message.reply_text(msg)


async def show_ranking(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not update.message:
        return

    with closing(get_conn()) as conn:
        rows = conn.execute(
            """
            SELECT u.first_name, u.username, COUNT(p.id) AS total, COALESCE(SUM(p.price), 0) AS spent
            FROM users u
            LEFT JOIN purchases p ON p.user_id = u.user_id
            GROUP BY u.user_id
            ORDER BY total DESC, spent DESC
            LIMIT 10
            """
        ).fetchall()

    if not rows:
        await update.message.reply_text("Ainda não há ranking.")
        return

    lines = ["🏆 *RANKING*\n"]
    for i, row in enumerate(rows, start=1):
        name = row["first_name"] or (f"@{row['username']}" if row["username"] else "Usuário")
        lines.append(f"{i}. {name} — {row['total']} compras — {money(row['spent'])}")

    await update.message.reply_text("\n".join(lines), parse_mode=ParseMode.MARKDOWN)


async def show_referral(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not update.message or not update.effective_user:
        return
    bot_username = context.bot.username or "seu_bot"
    link = f"https://t.me/{bot_username}?start={update.effective_user.id}"
    await update.message.reply_text(
        "🎁 *INDICAR AMIGO*\n\n"
        f"Seu link:\n{link}",
        parse_mode=ParseMode.MARKDOWN,
        disable_web_page_preview=True,
    )


# =========================
# ADMIN PANELS
# =========================

async def admin_products_menu(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not update.message:
        return
    clear_state(context)
    await update.message.reply_text(
        "📦 *GERENCIAR PRODUTOS*\nEscolha uma ação.",
        parse_mode=ParseMode.MARKDOWN,
        reply_markup=product_manage_keyboard(),
    )


async def admin_texts_menu(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not update.message:
        return
    clear_state(context)
    await update.message.reply_text(
        "📝 *EDITAR TEXTOS*\nEscolha qual texto deseja alterar.",
        parse_mode=ParseMode.MARKDOWN,
        reply_markup=texts_keyboard(),
    )


async def admin_settings_menu(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not update.message:
        return
    clear_state(context)
    await update.message.reply_text(
        "⚙️ *CONFIGURAÇÕES*",
        parse_mode=ParseMode.MARKDOWN,
        reply_markup=settings_keyboard(),
    )


async def admin_list_products(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not update.message:
        return
    rows = list_all_products()
    if not rows:
        await update.message.reply_text("Nenhum produto cadastrado.")
        return

    lines = ["📋 *PRODUTOS CADASTRADOS*\n"]
    for p in rows[:80]:
        status = "ativo" if p["active"] else "inativo"
        lines.append(
            f"ID {p['id']} | {p['name']} | {money(p['price'])} | estoque {p['stock']} | {status}"
        )

    await update.message.reply_text("\n".join(lines), parse_mode=ParseMode.MARKDOWN)


async def admin_start_add_product(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not update.message:
        return
    set_state(context, "admin_add_product")
    await update.message.reply_text(
        "Envie o produto assim:\n"
        "`Nome | 19.90 | Categoria | 10 | Descrição`",
        parse_mode=ParseMode.MARKDOWN,
        reply_markup=ReplyKeyboardRemove(),
    )


async def admin_start_edit_product(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not update.message:
        return
    set_state(context, "admin_edit_product_select")
    await update.message.reply_text(
        "Envie o ID do produto que deseja editar.",
        reply_markup=ReplyKeyboardRemove(),
    )


async def admin_start_disable_product(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not update.message:
        return
    set_state(context, "admin_disable_product")
    await update.message.reply_text(
        "Envie o ID do produto para desativar.",
        reply_markup=ReplyKeyboardRemove(),
    )


async def admin_start_stock(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not update.message:
        return
    set_state(context, "admin_stock")
    await update.message.reply_text(
        "Envie assim:\n`ID | novo_estoque`",
        parse_mode=ParseMode.MARKDOWN,
        reply_markup=ReplyKeyboardRemove(),
    )


async def admin_show_users(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not update.message:
        return
    rows = get_users(25)
    if not rows:
        await update.message.reply_text("Nenhum usuário ainda.")
        return

    lines = ["👥 *ÚLTIMOS USUÁRIOS*\n"]
    for row in rows:
        uname = f"@{row['username']}" if row["username"] else "sem username"
        lines.append(
            f"• {row['first_name'] or 'Sem nome'} | {uname} | ID `{row['user_id']}` | saldo {money(row['balance'])}"
        )
    await update.message.reply_text("\n".join(lines), parse_mode=ParseMode.MARKDOWN)


async def admin_show_balance_requests(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not update.message:
        return
    rows = get_pending_balance_requests()
    if not rows:
        await update.message.reply_text("Nenhuma solicitação pendente.")
        return

    lines = ["💰 *SOLICITAÇÕES PENDENTES*\n"]
    for row in rows:
        lines.append(
            f"ID {row['id']} | usuário `{row['user_id']}` | {money(row['amount'])} | {row['created_at']}"
        )
    lines.append("\nAprovar: `aprovar ID`\nRejeitar: `rejeitar ID`")
    await update.message.reply_text("\n".join(lines), parse_mode=ParseMode.MARKDOWN)


async def admin_start_adjust_balance(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not update.message:
        return
    set_state(context, "admin_adjust_balance")
    await update.message.reply_text(
        "Envie assim:\n`user_id | +10`\nou\n`user_id | =100`",
        parse_mode=ParseMode.MARKDOWN,
        reply_markup=ReplyKeyboardRemove(),
    )


async def admin_start_broadcast(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not update.message:
        return
    set_state(context, "admin_broadcast")
    await update.message.reply_text(
        "Envie a mensagem que será enviada para todos os usuários.",
        reply_markup=ReplyKeyboardRemove(),
    )


async def admin_stats(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not update.message:
        return
    s = get_admin_stats()
    text = (
        "📊 *ESTATÍSTICAS*\n\n"
        f"• Usuários: {s['users']}\n"
        f"• Produtos ativos: {s['products']}\n"
        f"• Solicitações pendentes: {s['pending']}\n"
        f"• Compras registradas: {s['purchases']}\n"
        f"• Receita registrada: {money(s['revenue'])}"
    )
    await update.message.reply_text(text, parse_mode=ParseMode.MARKDOWN)


# =========================
# STATE HANDLERS
# =========================

async def handle_admin_state(update: Update, context: ContextTypes.DEFAULT_TYPE, text: str) -> bool:
    state = get_state(context)
    if not state:
        return False

    if not update.message:
        return True

    if state == "admin_add_product":
        parts = [p.strip() for p in text.split("|")]
        if len(parts) != 5:
            await update.message.reply_text("Formato inválido. Use:\n`Nome | 19.90 | Categoria | 10 | Descrição`", parse_mode=ParseMode.MARKDOWN)
            return True
        try:
            name = parts[0]
            price = float(parts[1].replace(",", "."))
            category = parts[2]
            stock = int(parts[3])
            description = parts[4]
        except ValueError:
            await update.message.reply_text("Preço ou estoque inválido.")
            return True

        create_product(name, price, category, stock, description)
        clear_state(context)
        await update.message.reply_text("✅ Produto adicionado.", reply_markup=product_manage_keyboard())
        return True

    if state == "admin_edit_product_select":
        if not text.isdigit():
            await update.message.reply_text("Envie um ID numérico.")
            return True

        product = get_product(int(text))
        if not product:
            await update.message.reply_text("Produto não encontrado.")
            return True

        context.user_data["edit_product_id"] = int(text)
        set_state(context, "admin_edit_product_value")
        await update.message.reply_text(
            "Envie assim:\n`campo | novo valor`\n\nCampos permitidos:\nname\nprice\ncategory\ndescription",
            parse_mode=ParseMode.MARKDOWN,
        )
        return True

    if state == "admin_edit_product_value":
        product_id = context.user_data.get("edit_product_id")
        if not product_id:
            clear_state(context)
            await update.message.reply_text("Estado perdido. Tente novamente.", reply_markup=product_manage_keyboard())
            return True

        parts = [p.strip() for p in text.split("|", 1)]
        if len(parts) != 2:
            await update.message.reply_text("Use: `campo | novo valor`", parse_mode=ParseMode.MARKDOWN)
            return True

        field, value = parts
        if field not in {"name", "price", "category", "description"}:
            await update.message.reply_text("Campo inválido.")
            return True

        if field == "price":
            try:
                value = float(value.replace(",", "."))
            except ValueError:
                await update.message.reply_text("Preço inválido.")
                return True

        update_product_field(product_id, field, value)
        clear_state(context)
        await update.message.reply_text("✅ Produto atualizado.", reply_markup=product_manage_keyboard())
        return True

    if state == "admin_disable_product":
        if not text.isdigit():
            await update.message.reply_text("Envie um ID numérico.")
            return True
        product = get_product(int(text))
        if not product:
            await update.message.reply_text("Produto não encontrado.")
            return True
        update_product_field(int(text), "active", 0)
        clear_state(context)
        await update.message.reply_text("✅ Produto desativado.", reply_markup=product_manage_keyboard())
        return True

    if state == "admin_stock":
        parts = [p.strip() for p in text.split("|")]
        if len(parts) != 2 or not parts[0].isdigit():
            await update.message.reply_text("Use: `ID | novo_estoque`", parse_mode=ParseMode.MARKDOWN)
            return True
        try:
            pid = int(parts[0])
            stock = int(parts[1])
        except ValueError:
            await update.message.reply_text("Dados inválidos.")
            return True
        if not get_product(pid):
            await update.message.reply_text("Produto não encontrado.")
            return True
        update_product_field(pid, "stock", stock)
        clear_state(context)
        await update.message.reply_text("✅ Estoque alterado.", reply_markup=product_manage_keyboard())
        return True

    if state == "admin_adjust_balance":
        parts = [p.strip() for p in text.split("|")]
        if len(parts) != 2 or not parts[0].isdigit():
            await update.message.reply_text("Use: `user_id | +10` ou `user_id | =100`", parse_mode=ParseMode.MARKDOWN)
            return True

        user_id = int(parts[0])
        op = parts[1].replace(",", ".")
        user = get_user(user_id)
        if not user:
            await update.message.reply_text("Usuário não encontrado.")
            return True

        try:
            if op.startswith("+") or op.startswith("-"):
                value = float(op)
                add_balance(user_id, value)
            elif op.startswith("="):
                value = float(op[1:])
                set_balance(user_id, value)
            else:
                await update.message.reply_text("Use +valor, -valor ou =valor.")
                return True
        except ValueError:
            await update.message.reply_text("Valor inválido.")
            return True

        clear_state(context)
        new_user = get_user(user_id)
        await update.message.reply_text(
            f"✅ Saldo atualizado.\nNovo saldo: {money(new_user['balance'])}",
            reply_markup=admin_keyboard(),
        )
        return True

    if state == "admin_broadcast":
        msg = text.strip()
        if len(msg) < 2:
            await update.message.reply_text("Mensagem muito curta.")
            return True

        sent = 0
        failed = 0
        with closing(get_conn()) as conn:
            users = conn.execute("SELECT user_id FROM users WHERE is_banned = 0").fetchall()

        for row in users:
            try:
                await context.bot.send_message(chat_id=row["user_id"], text=msg)
                sent += 1
            except Exception:
                failed += 1

        clear_state(context)
        await update.message.reply_text(
            f"📣 Broadcast concluído.\nEnviadas: {sent}\nFalhas: {failed}",
            reply_markup=admin_keyboard(),
        )
        return True

    if state == "admin_edit_text":
        key = context.user_data.get("edit_text_key")
        if not key:
            clear_state(context)
            await update.message.reply_text("Estado perdido.", reply_markup=admin_keyboard())
            return True
        update_text_value(key, text)
        clear_state(context)
        await update.message.reply_text("✅ Texto atualizado.", reply_markup=texts_keyboard())
        return True

    return False


# =========================
# ROUTER
# =========================

async def handle_text(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not update.message or not update.effective_user:
        return

    user = update.effective_user
    text = update.message.text.strip()
    ensure_user(user.id, user.username, user.first_name)

    if await handle_admin_state(update, context, text):
        return

    if text == "/start":
        await start(update, context)
        return

    if text == "↩️ VOLTAR AO INÍCIO":
        clear_state(context)
        await update.message.reply_text("🏠 Início.", reply_markup=main_keyboard())
        return

    # user menu
    if text == "💗 PERFIL 💗":
        await show_profile(update, context)
        return
    if text == "✨ COMPRAR PRODUTOS ✨":
        await show_catalog(update, context)
        return
    if text == "💸 ADICIONAR SALDO 💸":
        await update.message.reply_text(get_text_value("deposit_text"), parse_mode=ParseMode.MARKDOWN)
        return
    if text == "👩🏻‍💻 SUPORTE":
        await update.message.reply_text(get_text_value("support_text"), parse_mode=ParseMode.MARKDOWN)
        return
    if text == "⚠️ TERMOS ⚠️":
        await update.message.reply_text(get_text_value("terms_text"), parse_mode=ParseMode.MARKDOWN)
        return
    if text == "🏆 RANKING":
        await show_ranking(update, context)
        return
    if text == "🎁 INDICAR AMIGO":
        await show_referral(update, context)
        return
    if text == "🔎 PESQUISAR PRODUTO":
        await update.message.reply_text("Envie assim: `pesquisar premium`", parse_mode=ParseMode.MARKDOWN)
        return
    if text.lower().startswith("pesquisar "):
        await search_catalog(update, context, text[10:].strip())
        return
    if text.lower().startswith("saldo "):
        try:
            amount = float(text.split(maxsplit=1)[1].replace(",", "."))
            if amount <= 0:
                raise ValueError
        except Exception:
            await update.message.reply_text("Use: `saldo 25`", parse_mode=ParseMode.MARKDOWN)
            return
        await request_balance(update, context, amount)
        return
    if text.lower().startswith("comprar "):
        try:
            product_id = int(text.split(maxsplit=1)[1])
        except Exception:
            await update.message.reply_text("Use: `comprar 1`", parse_mode=ParseMode.MARKDOWN)
            return
        await buy_product(update, context, product_id)
        return

    # admin-only menu
    if is_admin(user.id):
        if text == "🚪 SAIR DO ADMIN":
            clear_state(context)
            await update.message.reply_text("Admin fechado.", reply_markup=main_keyboard())
            return
        if text == "📦 GERENCIAR PRODUTOS":
            await admin_products_menu(update, context)
            return
        if text == "📝 EDITAR TEXTOS":
            await admin_texts_menu(update, context)
            return
        if text == "👥 VER USUÁRIOS":
            await admin_show_users(update, context)
            return
        if text == "💰 SOLICITAÇÕES DE SALDO":
            await admin_show_balance_requests(update, context)
            return
        if text == "📣 BROADCAST":
            await admin_start_broadcast(update, context)
            return
        if text == "⚙️ CONFIGURAÇÕES":
            await admin_settings_menu(update, context)
            return
        if text == "💳 AJUSTAR SALDO":
            await admin_start_adjust_balance(update, context)
            return
        if text == "📊 ESTATÍSTICAS":
            await admin_stats(update, context)
            return

        # admin products submenu
        if text == "➕ ADICIONAR PRODUTO":
            await admin_start_add_product(update, context)
            return
        if text == "📋 LISTAR PRODUTOS":
            await admin_list_products(update, context)
            return
        if text == "✏️ EDITAR PRODUTO":
            await admin_start_edit_product(update, context)
            return
        if text == "🗑️ DESATIVAR PRODUTO":
            await admin_start_disable_product(update, context)
            return
        if text == "📦 ALTERAR ESTOQUE":
            await admin_start_stock(update, context)
            return
        if text == "🔙 VOLTAR ADMIN":
            clear_state(context)
            await update.message.reply_text("🔧 Painel admin.", reply_markup=admin_keyboard())
            return

        # admin text edits
        if text == "✍️ BOAS-VINDAS":
            context.user_data["edit_text_key"] = "welcome_text"
            set_state(context, "admin_edit_text")
            await update.message.reply_text("Envie o novo texto de boas-vindas.", reply_markup=ReplyKeyboardRemove())
            return
        if text == "✍️ SUPORTE":
            context.user_data["edit_text_key"] = "support_text"
            set_state(context, "admin_edit_text")
            await update.message.reply_text("Envie o novo texto de suporte.", reply_markup=ReplyKeyboardRemove())
            return
        if text == "✍️ TERMOS":
            context.user_data["edit_text_key"] = "terms_text"
            set_state(context, "admin_edit_text")
            await update.message.reply_text("Envie o novo texto de termos.", reply_markup=ReplyKeyboardRemove())
            return
        if text == "✍️ DEPÓSITO":
            context.user_data["edit_text_key"] = "deposit_text"
            set_state(context, "admin_edit_text")
            await update.message.reply_text("Envie o novo texto de depósito/saldo.", reply_markup=ReplyKeyboardRemove())
            return
        if text == "✍️ MENSAGEM OCIOSA":
            context.user_data["edit_text_key"] = "idle_text"
            set_state(context, "admin_edit_text")
            await update.message.reply_text("Envie a nova mensagem ociosa.", reply_markup=ReplyKeyboardRemove())
            return

        # settings
        if text == "👁️ VER TEXTOS":
            txt = (
                "👁️ *TEXTOS ATUAIS*\n\n"
                f"*Boas-vindas:*\n{get_text_value('welcome_text')}\n\n"
                f"*Suporte:*\n{get_text_value('support_text')}\n\n"
                f"*Termos:*\n{get_text_value('terms_text')}\n\n"
                f"*Depósito:*\n{get_text_value('deposit_text')}\n\n"
                f"*Mensagem ociosa:*\n{get_text_value('idle_text')}"
            )
            await update.message.reply_text(txt, parse_mode=ParseMode.MARKDOWN)
            return
        if text == "🧹 LIMPAR ESTADO":
            clear_state(context)
            await update.message.reply_text("Estado limpo.", reply_markup=settings_keyboard())
            return

        # approve/reject
        if text.lower().startswith("aprovar "):
            try:
                req_id = int(text.split(maxsplit=1)[1])
            except Exception:
                await update.message.reply_text("Use: `aprovar ID`", parse_mode=ParseMode.MARKDOWN)
                return
            ok, msg = process_balance_request(req_id, True)
            await update.message.reply_text(msg)
            return

        if text.lower().startswith("rejeitar "):
            try:
                req_id = int(text.split(maxsplit=1)[1])
            except Exception:
                await update.message.reply_text("Use: `rejeitar ID`", parse_mode=ParseMode.MARKDOWN)
                return
            ok, msg = process_balance_request(req_id, False)
            await update.message.reply_text(msg)
            return

    await update.message.reply_text("Não entendi. Use o menu ou envie /start.")


# =========================
# MAIN
# =========================

def main() -> None:
    token = os.getenv("BOT_TOKEN")
    if not token:
        raise RuntimeError("Defina BOT_TOKEN no ambiente.")

    init_db()

    app = Application.builder().token(token).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("adm", adm))
    app.add_handler(CommandHandler("cancel", cancel))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_text))

    logger.info("Bot iniciado.")
    app.run_polling(drop_pending_updates=True)


if __name__ == "__main__":
    main()
