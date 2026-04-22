#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
NAY STORE BOT ✨💕🎀
Bot de vendas de contas de streaming para Telegram
"""

import sqlite3
import logging
import os
from datetime import datetime
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    Application, CommandHandler, CallbackQueryHandler,
    MessageHandler, filters, ContextTypes, ConversationHandler
)

# ─────────────────────────────────────────────
# CONFIGURAÇÕES — edite antes de rodar
# ─────────────────────────────────────────────
BOT_TOKEN = "8395658659:AAGuKeUDq4lMQBl8l0fqAi8jlkYxwt_vUm4"
ADMIN_IDS = [8307440223]          # coloque seu Telegram ID aqui
BOT_USERNAME = "CinePlaystore_bot"    # sem @

# ─────────────────────────────────────────────
# ESTADOS DO CONVERSATION HANDLER
# ─────────────────────────────────────────────
(
    ADMIN_MENU, ADMIN_ADD_PRODUCT, ADMIN_EDIT_PRODUCT,
    ADMIN_DEL_PRODUCT, ADMIN_ADD_SALDO, ADMIN_BROADCAST,
    ADMIN_EDIT_WELCOME, ADMIN_EDIT_SUPPORT,
    WAITING_PRODUCT_NAME, WAITING_PRODUCT_PRICE,
    WAITING_PRODUCT_DESC, WAITING_PRODUCT_LOGIN,
    WAITING_SALDO_USER, WAITING_SALDO_VALUE,
    WAITING_BROADCAST_MSG

