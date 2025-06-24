import mysql.connector
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    ApplicationBuilder,
    CommandHandler,
    ContextTypes,
    CallbackQueryHandler,
    ConversationHandler,
    MessageHandler,
    filters,
)
import logging

logging.basicConfig(level=logging.INFO)

DB_CONFIG = {
    'host': 'localhost',
    'user': 'root',
    'password': 'ejg22186768@',
    'database': 'bot_productos'
}

PEDIDO_NOMBRE, PEDIDO_DIRECCION = range(2)

def obtener_productos():
    conn = mysql.connector.connect(**DB_CONFIG)
    cursor = conn.cursor()
    cursor.execute("SELECT nombre, precio FROM productos")
    resultados = cursor.fetchall()
    conn.close()
    return resultados

def obtener_rol_usuario(id_telegram):
    conn = mysql.connector.connect(**DB_CONFIG)
    cursor = conn.cursor()
    cursor.execute("SELECT nombre, es_admin FROM usuarios WHERE id_telegram = %s", (id_telegram,))
    resultado = cursor.fetchone()
    conn.close()
    if resultado:
        nombre, es_admin = resultado
        rol = "Administrador" if es_admin else "Cliente"
        return nombre, rol
    else:
        return None, None

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    nombre_usuario = update.effective_user.first_name or "Usuario"
    nombre, rol = obtener_rol_usuario(user_id)

    if nombre is None:
        conn = mysql.connector.connect(**DB_CONFIG)
        cursor = conn.cursor()
        cursor.execute("INSERT INTO usuarios (id_telegram, nombre, es_admin) VALUES (%s, %s, 0)", (user_id, nombre_usuario))
        conn.commit()
        conn.close()
        nombre, rol = nombre_usuario, "Cliente"

    if rol == "Administrador":
        await update.message.reply_text(
            f"👋 ¡Bienvenido/a Administrador {nombre}!\n\n"
            f"📌 Comandos disponibles:\n"
            f"• /productos – Ver lista de productos.\n"
            f"• /buscar <nombre> – Buscar productos por nombre.\n"
            f"• /agregar <nombre> <precio> – Agregar nuevo producto."
        )
    else:
        await update.message.reply_text(
            f"👋 ¡Hola {nombre}!\n\n"
            f"📌 Comandos disponibles:\n"
            f"• /productos – Ver lista de productos.\n"
            f"• /buscar <nombre> – Buscar productos por nombre."
        )

async def productos(update: Update, context: ContextTypes.DEFAULT_TYPE):
    datos = obtener_productos()
    if not datos:
        await update.message.reply_text("❌ No hay productos cargados.")
        return

    mensaje = "📦 Productos disponibles:\n\n"
    for nombre, precio in datos:
        mensaje += f"• {nombre} – ${precio:,.2f}\n"

    keyboard = InlineKeyboardMarkup([
        [InlineKeyboardButton("🛒 Hacer pedido", callback_data="iniciar_pedido")]
    ])

    await update.message.reply_text(mensaje, reply_markup=keyboard)

async def buscar(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if len(context.args) == 0:
        await update.message.reply_text("📌 Usá: /buscar <nombre>")
        return

    termino = ' '.join(context.args)

    conn = mysql.connector.connect(**DB_CONFIG)
    cursor = conn.cursor()
    cursor.execute("SELECT nombre, precio FROM productos WHERE nombre LIKE %s", (f"%{termino}%",))
    resultados = cursor.fetchall()
    conn.close()

    if not resultados:
        await update.message.reply_text("❌ No se encontraron productos.")
        return

    mensaje = f"🔎 Resultados para: {termino}\n\n"
    for nombre, precio in resultados:
        mensaje += f"• {nombre} – ${precio:,.2f}\n"

    keyboard = InlineKeyboardMarkup([
        [InlineKeyboardButton("🛒 Hacer pedido", callback_data="iniciar_pedido")]
    ])
    await update.message.reply_text(mensaje, reply_markup=keyboard)

async def agregar(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    _, rol = obtener_rol_usuario(user_id)

    if rol != "Administrador":
        await update.message.reply_text("⛔ Solo los administradores pueden agregar productos.")
        return

    if len(context.args) < 2:
        await update.message.reply_text("📌 Usá: /agregar <nombre> <precio>")
        return

    nombre = ' '.join(context.args[:-1])
    try:
        precio = float(context.args[-1])
    except ValueError:
        await update.message.reply_text("❌ El precio debe ser un número.")
        return

    conn = mysql.connector.connect(**DB_CONFIG)
    cursor = conn.cursor()
    cursor.execute("INSERT INTO productos (nombre, precio) VALUES (%s, %s)", (nombre, precio))
    conn.commit()
    conn.close()

    await update.message.reply_text(f"✅ Producto agregado: {nombre} – ${precio:,.2f}")

async def manejar_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    user_id = query.from_user.id
    _, rol = obtener_rol_usuario(user_id)

    if rol != "Cliente":
        await query.edit_message_reply_markup(reply_markup=None)
        await query.message.reply_text("⛔ Solo los clientes pueden hacer pedidos.")
        return ConversationHandler.END

    if context.user_data.get("pedido_en_progreso"):
        await query.message.reply_text("⚠️ Ya estás haciendo un pedido. Por favor espera que termine el proceso.")
        return ConversationHandler.END

    context.user_data["pedido_en_progreso"] = True

    await query.edit_message_reply_markup(reply_markup=None)

    await query.message.reply_text("✏️ ¿Qué producto desea pedir?")
    return PEDIDO_NOMBRE

async def recibir_pedido(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data["producto"] = update.message.text
    await update.message.reply_text("📍 Ingresá la dirección de entrega:")
    return PEDIDO_DIRECCION

async def recibir_direccion(update: Update, context: ContextTypes.DEFAULT_TYPE):
    direccion = update.message.text
    user_id = update.effective_user.id
    nombre, _ = obtener_rol_usuario(user_id)
    producto = context.user_data.get("producto")

    conn = mysql.connector.connect(**DB_CONFIG)
    cursor = conn.cursor()

    cursor.execute("SELECT stock FROM productos WHERE nombre = %s", (producto,))
    resultado = cursor.fetchone()

    if not resultado:
        await update.message.reply_text("❌ El producto no existe en nuestra base de datos.")
        context.user_data["pedido_en_progreso"] = False
        conn.close()
        return ConversationHandler.END

    stock_disponible = resultado[0]

    if stock_disponible > 0:
        
        cursor.execute("UPDATE productos SET stock = stock - 1 WHERE nombre = %s", (producto,))

        cursor.execute("""
            INSERT INTO pedidos (id_telegram, nombre_cliente, producto, direccion)
            VALUES (%s, %s, %s, %s)
        """, (user_id, nombre, producto, direccion))
        conn.commit()
        conn.close()

        await update.message.reply_text(
            f"✅ Pedido registrado correctamente.\n"
            f"📦 Producto: {producto}\n"
            f"📍 Dirección: {direccion}\n\n"
            f"🚚 Su producto está por ser despachado. ¡Gracias por su compra!"
        )
    else:
        conn.close()
        await update.message.reply_text(
            f"⚠️ Disculpe, no hay stock disponible del producto '{producto}'.\n\n"
            f"📦 Puede esperar un estimado de 1 a 2 semanas o realizar otro pedido."
        )

    context.user_data["pedido_en_progreso"] = False
    return ConversationHandler.END

async def cancelar(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("🚫 Pedido cancelado.")
    return ConversationHandler.END

if __name__ == "__main__":
    app = ApplicationBuilder().token("7624201482:AAEHmF0rDeHvEN0hX3lbc36KDAWXkYOgFBI").build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("productos", productos))
    app.add_handler(CommandHandler("buscar", buscar))
    app.add_handler(CommandHandler("agregar", agregar))

    conv_handler = ConversationHandler(
        entry_points=[CallbackQueryHandler(manejar_callback)],
        states={
            PEDIDO_NOMBRE: [MessageHandler(filters.TEXT & ~filters.COMMAND, recibir_pedido)],
            PEDIDO_DIRECCION: [MessageHandler(filters.TEXT & ~filters.COMMAND, recibir_direccion)],
        },
        fallbacks=[CommandHandler("cancelar", cancelar)]
    )
    app.add_handler(conv_handler)

    app.run_polling()
