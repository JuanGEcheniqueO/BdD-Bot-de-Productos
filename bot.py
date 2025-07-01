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
AGREGAR_NOMBRE, AGREGAR_PRECIO, AGREGAR_STOCK, AGREGAR_DESC = range(4)

def obtener_productos():
    conn = mysql.connector.connect(**DB_CONFIG)
    cursor = conn.cursor()
    cursor.execute("SELECT nombre, precio, descripcion FROM productos")
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

def buscar_productos_por_nombre(termino):
    conn = mysql.connector.connect(**DB_CONFIG)
    cursor = conn.cursor()
    cursor.execute(
        "SELECT nombre, precio, descripcion FROM productos WHERE LOWER(nombre) LIKE %s",
        (f"%{termino.lower()}%",)
    )
    resultados = cursor.fetchall()
    conn.close()
    return resultados

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
            f"• /agregar <nombre> <precio> <stock> <descripción> – Agregar nuevo producto."
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

    mensaje = "📦 Nuestros productos disponibles:\n\n"
    for nombre, precio, descripcion in obtener_productos():
        mensaje += f"🛍️ *{nombre}*\n💲 ${precio:,.2f}\n📘 {descripcion}\n\n"

    keyboard = InlineKeyboardMarkup([
        [InlineKeyboardButton("🛒 Hacer pedido", callback_data="iniciar_pedido")]
    ])

    await update.message.reply_text(mensaje, reply_markup=keyboard)

async def buscar(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not context.args:
        await update.message.reply_text("📌 Usá: /buscar <nombre del producto>")
        return

    termino = ' '.join(context.args).strip()
    resultados = buscar_productos_por_nombre(termino)

    if resultados:
        mensaje = f"🔎 Resultados para: *{termino}*\n\n"
        for nombre, precio, descripcion in resultados:
            mensaje += f"• *{nombre}*\n  💲 ${precio:,.2f}\n  📘 {descripcion}\n\n"
        try:
            ultimo_id = context.user_data.get("ultimo_boton_id")
            if ultimo_id:
                await update.message.bot.delete_message(chat_id=update.effective_chat.id, message_id=ultimo_id)
        except:
            pass
        keyboard = InlineKeyboardMarkup([
            [InlineKeyboardButton("🛒 Hacer pedido", callback_data="iniciar_pedido")]
        ])
        sent_message = await update.message.reply_text(mensaje, parse_mode="Markdown", reply_markup=keyboard)

        context.user_data["ultimo_boton_id"] = sent_message.message_id
    else:
        await update.message.reply_text("❌ No se encontraron productos con ese nombre.")

async def agregar_producto(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    _, rol = obtener_rol_usuario(user_id)

    if rol != "Administrador":
        await update.message.reply_text("⛔ Solo los administradores pueden agregar productos.")
        return ConversationHandler.END

    await update.message.reply_text("📦 Ingresá el *nombre* del producto:", parse_mode="Markdown")
    return AGREGAR_NOMBRE

async def agregar_nombre(update: Update, context: ContextTypes.DEFAULT_TYPE):
    nombre = update.message.text.strip()
    context.user_data["nuevo_producto"] = {"nombre": nombre}

    conn = mysql.connector.connect(**DB_CONFIG)
    cursor = conn.cursor()
    cursor.execute("SELECT id FROM productos WHERE nombre = %s", (nombre,))
    if cursor.fetchone():
        await update.message.reply_text("❗ Ya existe un producto con ese nombre.")
        conn.close()
        return ConversationHandler.END

    conn.close()
    await update.message.reply_text("💲 Ingresá el *precio* del producto:", parse_mode="Markdown")
    return AGREGAR_PRECIO

async def agregar_precio(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        precio = float(update.message.text.replace(",", "."))
        context.user_data["nuevo_producto"]["precio"] = precio
        await update.message.reply_text("🔢 Ingresá el *stock disponible* (cantidad):", parse_mode="Markdown")
        return AGREGAR_STOCK
    except ValueError:
        await update.message.reply_text("❌ El precio debe ser un número. Intentá de nuevo:")
        return AGREGAR_PRECIO
    
async def agregar_stock(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        stock = int(update.message.text)
        context.user_data["nuevo_producto"]["stock"] = stock
        await update.message.reply_text("📝 Ingresá una *descripción breve* del producto:", parse_mode="Markdown")
        return AGREGAR_DESC
    except ValueError:
        await update.message.reply_text("❌ El stock debe ser un número entero. Intentá de nuevo:")
        return AGREGAR_STOCK

async def agregar_descripcion(update: Update, context: ContextTypes.DEFAULT_TYPE):
    descripcion = update.message.text.strip()
    prod = context.user_data["nuevo_producto"]
    prod["descripcion"] = descripcion

    conn = mysql.connector.connect(**DB_CONFIG)
    cursor = conn.cursor()
    cursor.execute("""
        INSERT INTO productos (nombre, precio, stock, descripcion)
        VALUES (%s, %s, %s, %s)
    """, (prod["nombre"], prod["precio"], prod["stock"], prod["descripcion"]))
    conn.commit()
    conn.close()

    await update.message.reply_text(f"✅ Producto agregado correctamente:\n\n"
                                    f"🛍️ {prod['nombre']}\n"
                                    f"💲 ${prod['precio']:,.2f}\n"
                                    f"🔢 Stock: {prod['stock']}\n"
                                    f"📘 {prod['descripcion']}",
                                    parse_mode="Markdown")
    return ConversationHandler.END

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

    cursor.execute("SELECT id, stock FROM productos WHERE nombre = %s", (producto,))
    resultado = cursor.fetchone()

    if not resultado:
        await update.message.reply_text("❌ El producto no existe en nuestra base de datos.")
        context.user_data["pedido_en_progreso"] = False
        conn.close()
        return ConversationHandler.END

    producto_id, stock_disponible = resultado

    cursor.execute("SELECT id FROM usuarios WHERE id_telegram = %s", (user_id,))
    usuario = cursor.fetchone()[0]

    if not usuario:
        await update.message.reply_text("❌ No se encontró tu usuario en la base de datos.")
        context.user_data["pedido_en_progreso"] = False
        conn.close()
        return ConversationHandler.END

    usuario_id = usuario

    if stock_disponible > 0:
        
        cursor.execute("UPDATE productos SET stock = stock - 1 WHERE nombre = %s", (producto,))

        cursor.execute("""
            INSERT INTO pedidos (usuario_id, nombre_cliente, producto_id, producto, direccion)
            VALUES (%s, %s, %s, %s, %s)
        """, (usuario_id, nombre, producto_id, producto, direccion))
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

    conv_agregar = ConversationHandler(
        entry_points=[CommandHandler("agregar", agregar_producto)],
        states={
            AGREGAR_NOMBRE: [MessageHandler(filters.TEXT & ~filters.COMMAND, agregar_nombre)],
            AGREGAR_PRECIO: [MessageHandler(filters.TEXT & ~filters.COMMAND, agregar_precio)],
            AGREGAR_STOCK: [MessageHandler(filters.TEXT & ~filters.COMMAND, agregar_stock)],
            AGREGAR_DESC: [MessageHandler(filters.TEXT & ~filters.COMMAND, agregar_descripcion)],
        },
        fallbacks=[],
    )
    app.add_handler(conv_agregar)

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
