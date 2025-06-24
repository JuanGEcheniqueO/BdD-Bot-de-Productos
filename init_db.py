import mysql.connector

DB_CONFIG = {
    'host': 'localhost',
    'user': 'root',
    'password': 'ejg22186768@',
    'database': 'bot_productos',
    'port': 3306
}

conn = mysql.connector.connect(**DB_CONFIG)
cursor = conn.cursor()


cursor.execute("""
CREATE TABLE IF NOT EXISTS productos (
    id INT AUTO_INCREMENT PRIMARY KEY,
    nombre VARCHAR(100) NOT NULL,
    precio DECIMAL(10,2) NOT NULL
)
""")

cursor.execute("""
CREATE TABLE IF NOT EXISTS usuarios (
    id_telegram BIGINT PRIMARY KEY,
    nombre VARCHAR(100),
    es_admin TINYINT(1)
)
""")

productos = [
    ('Samsung Galaxy A14', 259000,),
    ('Notebook Lenovo IdeaPad 1 Ryzen 5', 520000,),
    ('Auriculares JBL 510BT', 57999)
]

cursor.executemany("""
INSERT INTO productos (nombre, precio) VALUES (%s, %s)
""", productos)

cursor.execute("""
INSERT IGNORE INTO usuarios (id_telegram, nombre, es_admin) VALUES (%s, %s, %s)
""", (7798286164, 'Juan', 1))

conn.commit()
conn.close()
print("Base de datos inicializada.")
