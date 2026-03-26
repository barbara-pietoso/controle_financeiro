import sqlite3
import pandas as pd

DB_NAME = "financeiro.db"

# =========================
# CONEXÃO
# =========================
def conectar():
    return sqlite3.connect(DB_NAME, check_same_thread=False)

# =========================
# CRIAR TABELAS
# =========================
def criar_tabelas():
    conn = conectar()
    cursor = conn.cursor()

    # Tabela de lançamentos
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

    # Tabela de dívidas
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS dividas (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            nome_pessoa TEXT NOT NULL,
            data_criacao TEXT NOT NULL,
            descricao TEXT,
            valor_total REAL NOT NULL,
            valor_restante REAL NOT NULL
        )
    """)

    conn.commit()
    conn.close()

# =========================
# LANÇAMENTOS
# =========================
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
    df = pd.read_sql_query("SELECT * FROM lancamentos ORDER BY data DESC, id DESC", conn)
    conn.close()
    return df

def excluir_lancamento(id_lancamento):
    conn = conectar()
    cursor = conn.cursor()

    cursor.execute("DELETE FROM lancamentos WHERE id = ?", (id_lancamento,))

    conn.commit()
    conn.close()

# =========================
# DÍVIDAS
# =========================
def inserir_divida(nome_pessoa, data_criacao, descricao, valor_total):
    conn = conectar()
    cursor = conn.cursor()

    cursor.execute("""
        INSERT INTO dividas (nome_pessoa, data_criacao, descricao, valor_total, valor_restante)
        VALUES (?, ?, ?, ?, ?)
    """, (nome_pessoa, data_criacao, descricao, valor_total, valor_total))

    conn.commit()
    conn.close()

def listar_dividas():
    conn = conectar()
    df = pd.read_sql_query("SELECT * FROM dividas ORDER BY data_criacao DESC, id DESC", conn)
    conn.close()
    return df

def excluir_divida(id_divida):
    conn = conectar()
    cursor = conn.cursor()

    cursor.execute("DELETE FROM dividas WHERE id = ?", (id_divida,))

    conn.commit()
    conn.close()

# =========================
# PAGAMENTO DE DÍVIDA
# =========================
def pagar_divida(id_divida, valor_pagamento, data_pagamento, observacao=""):
    conn = conectar()
    cursor = conn.cursor()

    # Buscar dívida
    cursor.execute("""
        SELECT id, nome_pessoa, valor_restante
        FROM dividas
        WHERE id = ?
    """, (id_divida,))
    resultado = cursor.fetchone()

    if not resultado:
        conn.close()
        return False, "Dívida não encontrada."

    _, nome_pessoa, valor_restante = resultado

    if valor_pagamento <= 0:
        conn.close()
        return False, "O valor do pagamento precisa ser maior que zero."

    if valor_pagamento > valor_restante:
        conn.close()
        return False, f"O pagamento não pode ser maior que o valor restante ({valor_restante:.2f})."

    novo_valor_restante = valor_restante - valor_pagamento

    # Atualiza a dívida
    cursor.execute("""
        UPDATE dividas
        SET valor_restante = ?
        WHERE id = ?
    """, (novo_valor_restante, id_divida))

    # Cria lançamento automático como despesa
    descricao_lanc = f"Pagamento de dívida - {nome_pessoa}"
    if observacao:
        descricao_lanc += f" ({observacao})"

    cursor.execute("""
        INSERT INTO lancamentos (data, tipo, categoria, descricao, valor)
        VALUES (?, ?, ?, ?, ?)
    """, (
        data_pagamento,
        "Despesa",
        "Pagamento de Dívida",
        descricao_lanc,
        valor_pagamento
    ))

    conn.commit()
    conn.close()

    if novo_valor_restante == 0:
        return True, "Pagamento registrado. Dívida quitada com sucesso."
    else:
        return True, f"Pagamento registrado. Valor restante: R$ {novo_valor_restante:.2f}"
