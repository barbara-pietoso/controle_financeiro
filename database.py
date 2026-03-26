import sqlite3
import pandas as pd

DB_NAME = "financeiro.db"

def conectar():
    return sqlite3.connect(DB_NAME, check_same_thread=False)

def criar_tabelas():
    conn = conectar()
    cursor = conn.cursor()

    # -----------------------------
    # TABELA DE LANÇAMENTOS
    # -----------------------------
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

    # -----------------------------
    # TABELA DE DÍVIDAS
    # -----------------------------
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS dividas (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            credor TEXT NOT NULL,
            descricao TEXT,
            valor_total REAL NOT NULL,
            valor_restante REAL NOT NULL,
            data_criacao TEXT NOT NULL,
            status TEXT NOT NULL DEFAULT 'Aberta'
        )
    """)

    # -----------------------------
    # TABELA DE PAGAMENTOS DE DÍVIDAS
    # -----------------------------
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS pagamentos_dividas (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            divida_id INTEGER NOT NULL,
            data_pagamento TEXT NOT NULL,
            valor_pago REAL NOT NULL,
            observacao TEXT,
            FOREIGN KEY (divida_id) REFERENCES dividas (id)
        )
    """)

    conn.commit()
    conn.close()

# =========================================================
# LANÇAMENTOS
# =========================================================
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
    df = pd.read_sql_query("""
        SELECT * FROM lancamentos
        ORDER BY data DESC, id DESC
    """, conn)
    conn.close()
    return df

def buscar_lancamento_por_id(id_lancamento):
    conn = conectar()
    cursor = conn.cursor()
    cursor.execute("""
        SELECT id, data, tipo, categoria, descricao, valor
        FROM lancamentos
        WHERE id = ?
    """, (id_lancamento,))
    row = cursor.fetchone()
    conn.close()
    return row

def atualizar_lancamento(id_lancamento, data, tipo, categoria, descricao, valor):
    conn = conectar()
    cursor = conn.cursor()
    cursor.execute("""
        UPDATE lancamentos
        SET data = ?, tipo = ?, categoria = ?, descricao = ?, valor = ?
        WHERE id = ?
    """, (data, tipo, categoria, descricao, valor, id_lancamento))
    conn.commit()
    conn.close()

def excluir_lancamento(id_lancamento):
    conn = conectar()
    cursor = conn.cursor()
    cursor.execute("DELETE FROM lancamentos WHERE id = ?", (id_lancamento,))
    conn.commit()
    conn.close()

# =========================================================
# DÍVIDAS
# =========================================================
def inserir_divida(credor, descricao, valor_total, data_criacao):
    conn = conectar()
    cursor = conn.cursor()
    cursor.execute("""
        INSERT INTO dividas (credor, descricao, valor_total, valor_restante, data_criacao, status)
        VALUES (?, ?, ?, ?, ?, 'Aberta')
    """, (credor, descricao, valor_total, valor_total, data_criacao))
    conn.commit()
    conn.close()

def listar_dividas():
    conn = conectar()
    df = pd.read_sql_query("""
        SELECT * FROM dividas
        ORDER BY 
            CASE WHEN status = 'Aberta' THEN 0 ELSE 1 END,
            data_criacao DESC,
            id DESC
    """, conn)
    conn.close()
    return df

def listar_dividas_abertas():
    conn = conectar()
    df = pd.read_sql_query("""
        SELECT * FROM dividas
        WHERE valor_restante > 0
        ORDER BY data_criacao DESC, id DESC
    """, conn)
    conn.close()
    return df

def buscar_divida_por_id(divida_id):
    conn = conectar()
    cursor = conn.cursor()
    cursor.execute("""
        SELECT id, credor, descricao, valor_total, valor_restante, data_criacao, status
        FROM dividas
        WHERE id = ?
    """, (divida_id,))
    row = cursor.fetchone()
    conn.close()
    return row

def atualizar_divida(divida_id, credor, descricao, valor_total, valor_restante, data_criacao):
    status = "Quitada" if valor_restante <= 0 else "Aberta"

    conn = conectar()
    cursor = conn.cursor()
    cursor.execute("""
        UPDATE dividas
        SET credor = ?, descricao = ?, valor_total = ?, valor_restante = ?, data_criacao = ?, status = ?
        WHERE id = ?
    """, (credor, descricao, valor_total, valor_restante, data_criacao, status, divida_id))
    conn.commit()
    conn.close()

def excluir_divida(divida_id):
    conn = conectar()
    cursor = conn.cursor()

    # Apaga histórico vinculado
    cursor.execute("DELETE FROM pagamentos_dividas WHERE divida_id = ?", (divida_id,))

    # Apaga dívida
    cursor.execute("DELETE FROM dividas WHERE id = ?", (divida_id,))

    conn.commit()
    conn.close()

def registrar_pagamento_divida(divida_id, data_pagamento, valor_pago, observacao=""):
    conn = conectar()
    cursor = conn.cursor()

    cursor.execute("""
        SELECT credor, valor_restante, status
        FROM dividas
        WHERE id = ?
    """, (divida_id,))
    resultado = cursor.fetchone()

    if not resultado:
        conn.close()
        return False, "Dívida não encontrada."

    credor, valor_restante, status = resultado

    if status == "Quitada" or valor_restante <= 0:
        conn.close()
        return False, "Essa dívida já está quitada."

    if valor_pago <= 0:
        conn.close()
        return False, "O valor pago deve ser maior que zero."

    if valor_pago > valor_restante:
        conn.close()
        return False, f"O pagamento não pode ser maior que o valor restante (R$ {valor_restante:.2f})."

    # Salva histórico do pagamento
    cursor.execute("""
        INSERT INTO pagamentos_dividas (divida_id, data_pagamento, valor_pago, observacao)
        VALUES (?, ?, ?, ?)
    """, (divida_id, data_pagamento, valor_pago, observacao))

    novo_valor_restante = round(valor_restante - valor_pago, 2)
    novo_status = "Quitada" if novo_valor_restante <= 0 else "Aberta"

    # Atualiza dívida
    cursor.execute("""
        UPDATE dividas
        SET valor_restante = ?, status = ?
        WHERE id = ?
    """, (max(novo_valor_restante, 0), novo_status, divida_id))

    # Cria despesa automática
    descricao_lanc = f"Pagamento de dívida - {credor}"
    if observacao:
        descricao_lanc += f" ({observacao})"

    cursor.execute("""
        INSERT INTO lancamentos (data, tipo, categoria, descricao, valor)
        VALUES (?, 'Despesa', 'Pagamento de Dívida', ?, ?)
    """, (data_pagamento, descricao_lanc, valor_pago))

    conn.commit()
    conn.close()

    return True, "Pagamento registrado com sucesso!"

def listar_pagamentos_dividas():
    conn = conectar()
    df = pd.read_sql_query("""
        SELECT 
            p.id,
            p.divida_id,
            d.credor,
            d.descricao AS descricao_divida,
            p.data_pagamento,
            p.valor_pago,
            p.observacao
        FROM pagamentos_dividas p
        INNER JOIN dividas d ON p.divida_id = d.id
        ORDER BY p.data_pagamento DESC, p.id DESC
    """, conn)
    conn.close()
    return df
