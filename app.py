import streamlit as st
import pandas as pd
import sqlite3
from datetime import date

# =========================
# CONFIG
# =========================
st.set_page_config(page_title="Controle Financeiro", page_icon="💰", layout="wide")

# =========================
# BANCO DE DADOS
# =========================
DB_NAME = "financeiro.db"

def conectar():
    return sqlite3.connect(DB_NAME, check_same_thread=False)

def criar_tabelas():
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

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS dividas (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            nome_pessoa TEXT NOT NULL,
            descricao TEXT,
            valor_total REAL NOT NULL,
            valor_restante REAL NOT NULL,
            data_criacao TEXT NOT NULL,
            status TEXT NOT NULL
        )
    """)

    conn.commit()
    conn.close()

# =========================
# FUNÇÕES Lançamentos
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
    try:
        df = pd.read_sql_query("SELECT * FROM lancamentos ORDER BY data DESC, id DESC", conn)
    except:
        df = pd.DataFrame(columns=["id", "data", "tipo", "categoria", "descricao", "valor"])
    conn.close()
    return df

def excluir_lancamento(id_lancamento):
    conn = conectar()
    cursor = conn.cursor()
    cursor.execute("DELETE FROM lancamentos WHERE id = ?", (id_lancamento,))
    conn.commit()
    conn.close()

# =========================
# FUNÇÕES Dívidas
# =========================
def inserir_divida(nome_pessoa, descricao, valor_total, data_criacao):
    conn = conectar()
    cursor = conn.cursor()
    cursor.execute("""
        INSERT INTO dividas (nome_pessoa, descricao, valor_total, valor_restante, data_criacao, status)
        VALUES (?, ?, ?, ?, ?, ?)
    """, (nome_pessoa, descricao, valor_total, valor_total, data_criacao, "Aberta"))
    conn.commit()
    conn.close()

def listar_dividas():
    conn = conectar()
    try:
        df = pd.read_sql_query("SELECT * FROM dividas ORDER BY status ASC, data_criacao DESC, id DESC", conn)
    except:
        df = pd.DataFrame(columns=["id", "nome_pessoa", "descricao", "valor_total", "valor_restante", "data_criacao", "status"])
    conn.close()
    return df

def pagar_divida(id_divida, valor_pagamento, data_pagamento):
    conn = conectar()
    cursor = conn.cursor()

    cursor.execute("SELECT valor_restante, nome_pessoa FROM dividas WHERE id = ?", (id_divida,))
    resultado = cursor.fetchone()

    if resultado:
        valor_restante_atual, nome_pessoa = resultado
        novo_valor_restante = max(valor_restante_atual - valor_pagamento, 0)
        novo_status = "Quitada" if novo_valor_restante == 0 else "Aberta"

        cursor.execute("""
            UPDATE dividas
            SET valor_restante = ?, status = ?
            WHERE id = ?
        """, (novo_valor_restante, novo_status, id_divida))

        # Registra como despesa automaticamente
        cursor.execute("""
            INSERT INTO lancamentos (data, tipo, categoria, descricao, valor)
            VALUES (?, ?, ?, ?, ?)
        """, (
            data_pagamento,
            "Despesa",
            "Pagamento de Dívida",
            f"Pagamento de dívida para {nome_pessoa}",
            valor_pagamento
        ))

    conn.commit()
    conn.close()

def excluir_divida(id_divida):
    conn = conectar()
    cursor = conn.cursor()
    cursor.execute("DELETE FROM dividas WHERE id = ?", (id_divida,))
    conn.commit()
    conn.close()

# =========================
# UTILITÁRIOS
# =========================
def formatar_brl(valor):
    return f"R$ {valor:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")

CATEGORIAS_RECEITA = ["Salário", "Freela", "Show"]
CATEGORIAS_DESPESA = [
    "Alimentação",
    "Transporte",
    "Moradia",
    "Saúde",
    "Educação",
    "Lazer",
    "Assinaturas",
    "Compras",
    "Contas Fixas",
    "Outros",
    "Pagamento de Dívida"
]

# =========================
# INICIALIZAÇÃO
# =========================
criar_tabelas()

# =========================
# TÍTULO
# =========================
st.title("💰 Controle Financeiro")
st.caption("Entradas, despesas e controle de dívidas em uma única página")

# =========================
# CARREGAR DADOS
# =========================
df = listar_lancamentos()
df_dividas = listar_dividas()

if not df.empty:
    df["valor"] = pd.to_numeric(df["valor"], errors="coerce").fillna(0)
    df["data"] = pd.to_datetime(df["data"], errors="coerce")

if not df_dividas.empty:
    if "valor_total" in df_dividas.columns:
        df_dividas["valor_total"] = pd.to_numeric(df_dividas["valor_total"], errors="coerce").fillna(0)
    if "valor_restante" in df_dividas.columns:
        df_dividas["valor_restante"] = pd.to_numeric(df_dividas["valor_restante"], errors="coerce").fillna(0)

# =========================
# MÉTRICAS
# =========================
receitas = df[df["tipo"] == "Receita"]["valor"].sum() if not df.empty else 0
despesas = df[df["tipo"] == "Despesa"]["valor"].sum() if not df.empty else 0
saldo = receitas - despesas
dividas_abertas = df_dividas[df_dividas["status"] == "Aberta"]["valor_restante"].sum() if not df_dividas.empty and "status" in df_dividas.columns else 0

m1, m2, m3, m4 = st.columns(4)
m1.metric("Entradas", formatar_brl(receitas))
m2.metric("Despesas", formatar_brl(despesas))
m3.metric("Saldo Atual", formatar_brl(saldo))
m4.metric("Dívidas em Aberto", formatar_brl(dividas_abertas))

st.divider()

# =========================
# FORMULÁRIOS
# =========================
col_esq, col_dir = st.columns([1, 1])

# ---------- NOVO LANÇAMENTO ----------
with col_esq:
    st.subheader("➕ Novo Lançamento")

    data_lanc = st.date_input("Data", value=date.today(), key="data_lanc")
    tipo = st.selectbox("Tipo", ["Receita", "Despesa"], key="tipo_lanc")

    categorias = CATEGORIAS_RECEITA if tipo == "Receita" else CATEGORIAS_DESPESA
    categoria = st.selectbox("Categoria", categorias, key="categoria_lanc")

    descricao = st.text_input("Descrição", key="descricao_lanc")
    valor = st.number_input("Valor (R$)", min_value=0.0, format="%.2f", key="valor_lanc")

    if st.button("Salvar Lançamento", use_container_width=True):
        if valor > 0:
            inserir_lancamento(str(data_lanc), tipo, categoria, descricao, valor)
            st.success("Lançamento salvo com sucesso!")
            st.rerun()
        else:
            st.warning("Informe um valor maior que zero.")

# ---------- NOVA DÍVIDA ----------
with col_dir:
    st.subheader("🤝 Nova Dívida")

    nome_pessoa = st.text_input("Pessoa para quem você deve", key="nome_divida")
    desc_divida = st.text_input("Descrição da dívida", key="desc_divida")
    valor_divida = st.number_input("Valor total da dívida (R$)", min_value=0.0, format="%.2f", key="valor_divida")
    data_divida = st.date_input("Data da dívida", value=date.today(), key="data_divida")

    if st.button("Salvar Dívida", use_container_width=True):
        if nome_pessoa.strip() and valor_divida > 0:
            inserir_divida(nome_pessoa.strip(), desc_divida, valor_divida, str(data_divida))
            st.success("Dívida cadastrada com sucesso!")
            st.rerun()
        else:
            st.warning("Preencha o nome da pessoa e um valor maior que zero.")

st.divider()

# =========================
# PAGAR DÍVIDA
# =========================
st.subheader("💸 Pagar Dívida")

dividas_abertas_df = pd.DataFrame()
if not df_dividas.empty and "status" in df_dividas.columns:
    dividas_abertas_df = df_dividas[df_dividas["status"] == "Aberta"].copy()

if not dividas_abertas_df.empty:
    opcoes_dividas = {}
    for _, row in dividas_abertas_df.iterrows():
        nome = row["nome_pessoa"] if "nome_pessoa" in row.index else "Sem nome"
        restante = row["valor_restante"] if "valor_restante" in row.index else 0
        opcoes_dividas[f'ID {row["id"]} - {nome} | Restante: {formatar_brl(restante)}'] = row["id"]

    col1, col2, col3 = st.columns([2, 1, 1])

    with col1:
        divida_selecionada = st.selectbox("Selecione a dívida", list(opcoes_dividas.keys()))
    with col2:
        valor_pagamento = st.number_input("Valor do pagamento", min_value=0.0, format="%.2f", key="valor_pagamento")
    with col3:
        data_pagamento = st.date_input("Data do pagamento", value=date.today(), key="data_pagamento")

    if st.button("Registrar Pagamento", use_container_width=True):
        id_divida = opcoes_dividas[divida_selecionada]
        if valor_pagamento > 0:
            pagar_divida(id_divida, valor_pagamento, str(data_pagamento))
            st.success("Pagamento registrado! Também entrou automaticamente como despesa.")
            st.rerun()
        else:
            st.warning("Informe um valor maior que zero.")
else:
    st.info("Não há dívidas abertas no momento.")

st.divider()

# =========================
# GRÁFICOS
# =========================
g1, g2 = st.columns(2)

with g1:
    st.subheader("📊 Gastos por Categoria")
    if not df.empty:
        despesas_df = df[df["tipo"] == "Despesa"]
        if not despesas_df.empty:
            gastos_categoria = despesas_df.groupby("categoria")["valor"].sum().sort_values(ascending=False)
            st.bar_chart(gastos_categoria)
        else:
            st.info("Sem despesas cadastradas.")
    else:
        st.info("Sem lançamentos cadastrados.")

with g2:
    st.subheader("📈 Entradas x Despesas")
    resumo = pd.DataFrame({
        "Tipo": ["Entradas", "Despesas"],
        "Valor": [receitas, despesas]
    }).set_index("Tipo")
    st.bar_chart(resumo)

st.divider()

# =========================
# TABELA RESUMO GERAL
# =========================
st.subheader("📋 Relação Geral: Entradas, Despesas e Dívidas")

resumo_geral = pd.DataFrame({
    "Indicador": ["Total de Entradas", "Total de Despesas", "Saldo Atual", "Dívidas em Aberto"],
    "Valor": [receitas, despesas, saldo, dividas_abertas]
})
resumo_geral["Valor Formatado"] = resumo_geral["Valor"].apply(formatar_brl)

st.dataframe(
    resumo_geral[["Indicador", "Valor Formatado"]],
    use_container_width=True,
    hide_index=True
)

st.divider()

# =========================
# TABELA DE LANÇAMENTOS
# =========================
st.subheader("🧾 Lançamentos")

if not df.empty:
    df_exibir = df.copy()
    df_exibir["data"] = df_exibir["data"].dt.strftime("%d/%m/%Y")
    df_exibir["valor"] = df_exibir["valor"].apply(formatar_brl)

    st.dataframe(
        df_exibir[["id", "data", "tipo", "categoria", "descricao", "valor"]],
        use_container_width=True,
        hide_index=True
    )

    ids_lanc = df["id"].tolist()
    id_excluir_lanc = st.selectbox("Selecione o ID do lançamento para excluir", ids_lanc, key="excluir_lanc")

    if st.button("Excluir Lançamento"):
        excluir_lancamento(id_excluir_lanc)
        st.success("Lançamento excluído com sucesso!")
        st.rerun()
else:
    st.info("Nenhum lançamento cadastrado.")

st.divider()

# =========================
# TABELA DE DÍVIDAS
# =========================
st.subheader("🤝 Dívidas")

if not df_dividas.empty:
    df_dividas_exibir = df_dividas.copy()

    if "data_criacao" in df_dividas_exibir.columns:
        df_dividas_exibir["data_criacao"] = pd.to_datetime(df_dividas_exibir["data_criacao"], errors="coerce").dt.strftime("%d/%m/%Y")

    if "valor_total" in df_dividas_exibir.columns:
        df_dividas_exibir["valor_total"] = df_dividas_exibir["valor_total"].apply(formatar_brl)

    if "valor_restante" in df_dividas_exibir.columns:
        df_dividas_exibir["valor_restante"] = df_dividas_exibir["valor_restante"].apply(formatar_brl)

    colunas_dividas = [c for c in ["id", "nome_pessoa", "descricao", "valor_total", "valor_restante", "data_criacao", "status"] if c in df_dividas_exibir.columns]

    st.dataframe(
        df_dividas_exibir[colunas_dividas],
        use_container_width=True,
        hide_index=True
    )

    ids_div = df_dividas["id"].tolist()
    id_excluir_div = st.selectbox("Selecione o ID da dívida para excluir", ids_div, key="excluir_div")

    if st.button("Excluir Dívida"):
        excluir_divida(id_excluir_div)
        st.success("Dívida excluída com sucesso!")
        st.rerun()
else:
    st.info("Nenhuma dívida cadastrada.")
