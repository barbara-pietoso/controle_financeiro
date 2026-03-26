import sqlite3
import pandas as pd

DB_NAME = "financeiro.db"

def conectar():
    return sqlite3.connect(DB_NAME, check_same_thread=False)

def criar_tabela():
    conn = conectar()
    cursor = conn.cursor()
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS lancamentos (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            data TEXT NOT NULL,
            tipo TEXT NOT NULL,
            categoria TEXT NOT NULL,
            descricao TEXT,
            valor REAL NOT NULL
        )
    """)
    conn.commit()
    conn.close()

def inserir_lancamento(data, tipo, categoria, descricao, valor):
    conn = conectar()
    cursor = conn.cursor()
    cursor.execute("""
        INSERT INTO lancamentos (data, tipo, categoria, descricao, valor)
        VALUES (?, ?, ?, ?, ?)
    """, (data, tipo, categoria, descricao, valor))
    conn.commit()
    conn.close()

def listar_lancamentos():
    conn = conectar()
    df = pd.read_sql_query("SELECT * FROM lancamentos ORDER BY data DESC", conn)
    conn.close()
    return df

def excluir_lancamento(id_lancamento):
    conn = conectar()
    cursor = conn.cursor()
    cursor.execute("DELETE FROM lancamentos WHERE id = ?", (id_lancamento,))
    conn.commit()
    conn.close()
