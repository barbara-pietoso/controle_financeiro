import streamlit as st
import pandas as pd
import sqlite3
from datetime import date

# ==========================================
# CONFIGURAÇÃO DA PÁGINA
# ==========================================
st.set_page_config(
    page_title="Controle Financeiro",
    page_icon="💰",
    layout="wide"
)

# ==========================================
# ESTILO (MELHOR PARA CELULAR)
# ==========================================
st.markdown("""
<style>
    .main > div {
        padding-top: 1rem;
        padding-bottom: 2rem;
    }

    .block-container {
        padding-top: 1rem !important;
        padding-left: 1rem !important;
        padding-right: 1rem !important;
        max-width: 1100px;
    }

    div[data-testid="stMetric"] {
        background-color: #f7f7f7;
        border: 1px solid #e5e7eb;
        padding: 12px;
        border-radius: 10px;
    }

    .stButton > button {
        width: 100%;
        border-radius: 8px;
        height: 42px;
        font-weight: 600;
    }

    .stTextInput > div > div > input,
    .stNumberInput input,
    .stDateInput input {
        border-radius: 8px;
    }

    /* Melhor leitura em telas pequenas */
    @media (max-width: 768px) {
        .block-container {
            padding-left: 0.7rem !important;
            padding-right: 0.7rem !important;
        }
    }
</style>
""", unsafe_allow_html=True)

# ==========================================
# BANCO
# ==========================================
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

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS cartao (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            nome_cartao TEXT NOT NULL,
            limite_total REAL NOT NULL,
            limite_usado REAL NOT NULL DEFAULT 0
        )
    """)

    conn.commit()
    conn.close()

# ==========================================
# MIGRAÇÃO SIMPLES (evita quebrar com banco antigo)
# ==========================================
def garantir_colunas_dividas():
    conn = conectar()
    cursor = conn.cursor()

    cursor.execute("PRAGMA table_info(dividas)")
    colunas = [col[1] for col in cursor.fetchall()]

    if len(colunas) > 0:
        if "nome_pessoa" not in colunas:
            cursor.execute("ALTER TABLE dividas ADD COLUMN nome_pessoa TEXT DEFAULT 'Sem nome'")
        if "descricao" not in colunas:
            cursor.execute("ALTER TABLE dividas ADD COLUMN descricao TEXT DEFAULT ''")
        if "valor_total" not in colunas:
            cursor.execute("ALTER TABLE dividas ADD COLUMN valor_total REAL DEFAULT 0")
        if "valor_restante" not in colunas:
            cursor.execute("ALTER TABLE dividas ADD COLUMN valor_restante REAL DEFAULT 0")
        if "data_criacao" not in colunas:
            cursor.execute("ALTER TABLE dividas ADD COLUMN data_criacao TEXT DEFAULT ''")
        if "status" not in colunas:
            cursor.execute("ALTER TABLE dividas ADD COLUMN status TEXT DEFAULT 'Aberta'")

    conn.commit()
    conn.close()

# ==========================================
# FUNÇÕES - LANÇAMENTOS
# ==========================================
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

# ==========================================
# FUNÇÕES - DÍVIDAS
# ==========================================
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
        valor_pagamento_real = min(valor_pagamento, valor_restante_atual)
        novo_valor_restante = max(valor_restante_atual - valor_pagamento_real, 0)
        novo_status = "Quitada" if novo_valor_restante == 0 else "Aberta"

        cursor.execute("""
            UPDATE dividas
            SET valor_restante = ?, status = ?
            WHERE id = ?
        """, (novo_valor_restante, novo_status, id_divida))

        # Entra automaticamente como despesa
        cursor.execute("""
            INSERT INTO lancamentos (data, tipo, categoria, descricao, valor)
            VALUES (?, ?, ?, ?, ?)
        """, (
            data_pagamento,
            "Despesa",
            "Pagamento de Dívida",
            f"Pagamento de dívida para {nome_pessoa}",
            valor_pagamento_real
        ))

    conn.commit()
    conn.close()

def excluir_divida(id_divida):
    conn = conectar()
    cursor = conn.cursor()
    cursor.execute("DELETE FROM dividas WHERE id = ?", (id_divida,))
    conn.commit()
    conn.close()

# ==========================================
# FUNÇÕES - CARTÃO
# ==========================================
def inserir_cartao(nome_cartao, limite_total):
    conn = conectar()
    cursor = conn.cursor()
    cursor.execute("""
        INSERT INTO cartao (nome_cartao, limite_total, limite_usado)
        VALUES (?, ?, 0)
    """, (nome_cartao, limite_total))
    conn.commit()
    conn.close()

def listar_cartoes():
    conn = conectar()
    try:
        df = pd.read_sql_query("SELECT * FROM cartao ORDER BY id DESC", conn)
    except:
        df = pd.DataFrame(columns=["id", "nome_cartao", "limite_total", "limite_usado"])
    conn.close()
    return df

def usar_cartao(id_cartao, valor_compra, descricao_compra, data_compra):
    conn = conectar()
    cursor = conn.cursor()

    cursor.execute("SELECT nome_cartao, limite_total, limite_usado FROM cartao WHERE id = ?", (id_cartao,))
    resultado = cursor.fetchone()

    if resultado:
        nome_cartao, limite_total, limite_usado = resultado
        novo_usado = limite_usado + valor_compra

        if novo_usado <= limite_total:
            cursor.execute("""
                UPDATE cartao
                SET limite_usado = ?
                WHERE id = ?
            """, (novo_usado, id_cartao))

            cursor.execute("""
                INSERT INTO lancamentos (data, tipo, categoria, descricao, valor)
                VALUES (?, ?, ?, ?, ?)
            """, (
                data_compra,
                "Despesa",
                "Cartão",
                f"{descricao_compra} ({nome_cartao})",
                valor_compra
            ))
            conn.commit()
            conn.close()
            return True, "Compra registrada no cartão!"
        else:
            conn.close()
            return False, "Compra excede o limite disponível."

    conn.close()
    return False, "Cartão não encontrado."

def pagar_fatura_cartao(id_cartao, valor_pagamento):
    conn = conectar()
    cursor = conn.cursor()

    cursor.execute("SELECT limite_usado, nome_cartao FROM cartao WHERE id = ?", (id_cartao,))
    resultado = cursor.fetchone()

    if resultado:
        limite_usado, nome_cartao = resultado
        pagamento_real = min(valor_pagamento, limite_usado)
        novo_usado = max(limite_usado - pagamento_real, 0)

        cursor.execute("""
            UPDATE cartao
            SET limite_usado = ?
            WHERE id = ?
        """, (novo_usado, id_cartao))

        conn.commit()
        conn.close()
        return True, f"Pagamento da fatura do cartão {nome_cartao} registrado!"
    
    conn.close()
    return False, "Cartão não encontrado."

# ==========================================
# UTILITÁRIOS
# ==========================================
def formatar_brl(valor):
    try:
        return f"R$ {float(valor):,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")
    except:
        return "R$ 0,00"

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
    "Pagamento de Dívida",
    "Cartão"
]

# ==========================================
# INICIAR
# ==========================================
criar_tabelas()
garantir_colunas_dividas()

# ==========================================
# TÍTULO
# ==========================================
st.title("💰 Controle Financeiro")
st.caption("Versão simples, organizada e melhor para celular")

# ==========================================
# CARREGAR DADOS
# ==========================================
df = listar_lancamentos()
df_dividas = listar_dividas()
df_cartoes = listar_cartoes()

if not df.empty:
    df["valor"] = pd.to_numeric(df["valor"], errors="coerce").fillna(0)
    df["data"] = pd.to_datetime(df["data"], errors="coerce")

if not df_dividas.empty:
    for col in ["valor_total", "valor_restante"]:
        if col in df_dividas.columns:
            df_dividas[col] = pd.to_numeric(df_dividas[col], errors="coerce").fillna(0)

if not df_cartoes.empty:
    for col in ["limite_total", "limite_usado"]:
        if col in df_cartoes.columns:
            df_cartoes[col] = pd.to_numeric(df_cartoes[col], errors="coerce").fillna(0)

# ==========================================
# RESUMO
# ==========================================
receitas = df[df["tipo"] == "Receita"]["valor"].sum() if not df.empty else 0
despesas = df[df["tipo"] == "Despesa"]["valor"].sum() if not df.empty else 0
saldo = receitas - despesas
dividas_abertas = df_dividas[df_dividas["status"] == "Aberta"]["valor_restante"].sum() if not df_dividas.empty and "status" in df_dividas.columns else 0
cartao_usado = df_cartoes["limite_usado"].sum() if not df_cartoes.empty else 0

m1, m2 = st.columns(2)
with m1:
    st.metric("Entradas", formatar_brl(receitas))
with m2:
    st.metric("Despesas", formatar_brl(despesas))

m3, m4 = st.columns(2)
with m3:
    st.metric("Saldo", formatar_brl(saldo))
with m4:
    st.metric("Dívidas em Aberto", formatar_brl(dividas_abertas))

if not df_cartoes.empty:
    st.metric("Uso total do Cartão", formatar_brl(cartao_usado))

st.divider()

# ==========================================
# NOVO LANÇAMENTO
# ==========================================
st.subheader("➕ Novo Lançamento")

data_lanc = st.date_input("Data", value=date.today(), key="data_lanc")
tipo = st.selectbox("Tipo", ["Receita", "Despesa"], key="tipo_lanc")

categorias = CATEGORIAS_RECEITA if tipo == "Receita" else CATEGORIAS_DESPESA
categoria = st.selectbox("Categoria", categorias, key="categoria_lanc")

descricao = st.text_input("Descrição", key="descricao_lanc")
valor = st.number_input("Valor (R$)", min_value=0.0, format="%.2f", key="valor_lanc")

if st.button("Salvar Lançamento"):
    if valor > 0:
        inserir_lancamento(str(data_lanc), tipo, categoria, descricao, valor)
        st.success("Lançamento salvo com sucesso!")
        st.rerun()
    else:
        st.warning("Informe um valor maior que zero.")

st.divider()

# ==========================================
# GRÁFICOS
# ==========================================
st.subheader("📊 Gráficos")

# Entradas x Despesas
resumo_grafico = pd.DataFrame({
    "Tipo": ["Entradas", "Despesas"],
    "Valor": [receitas, despesas]
}).set_index("Tipo")
st.bar_chart(resumo_grafico)

# Gastos por categoria
st.markdown("**Gastos por categoria**")
if not df.empty:
    despesas_df = df[df["tipo"] == "Despesa"]
    if not despesas_df.empty:
        gastos_categoria = despesas_df.groupby("categoria")["valor"].sum().sort_values(ascending=False)
        st.bar_chart(gastos_categoria)
    else:
        st.info("Sem despesas cadastradas ainda.")
else:
    st.info("Sem lançamentos cadastrados ainda.")

st.divider()

# ==========================================
# TABELA RESUMO
# ==========================================
st.subheader("📋 Relação Geral")

resumo_geral = pd.DataFrame({
    "Indicador": [
        "Total de Entradas",
        "Total de Despesas",
        "Saldo Atual",
        "Dívidas em Aberto",
        "Uso Total do Cartão"
    ],
    "Valor": [
        receitas,
        despesas,
        saldo,
        dividas_abertas,
        cartao_usado
    ]
})
resumo_geral["Valor"] = resumo_geral["Valor"].apply(formatar_brl)

st.dataframe(resumo_geral, use_container_width=True, hide_index=True)

st.divider()

# ==========================================
# LANÇAMENTOS
# ==========================================
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

    id_excluir_lanc = st.selectbox(
        "Selecione o ID do lançamento para excluir",
        df["id"].tolist(),
        key="excluir_lanc"
    )

    if st.button("Excluir Lançamento"):
        excluir_lancamento(id_excluir_lanc)
        st.success("Lançamento excluído com sucesso!")
        st.rerun()
else:
    st.info("Nenhum lançamento cadastrado.")

st.divider()

# ==========================================
# CARTÃO (ANTES DAS DÍVIDAS)
# ==========================================
st.subheader("💳 Cartão")

# Cadastro de cartão
with st.expander("Cadastrar cartão", expanded=False):
    nome_cartao = st.text_input("Nome do cartão", key="nome_cartao")
    limite_cartao = st.number_input("Limite total (R$)", min_value=0.0, format="%.2f", key="limite_cartao")

    if st.button("Salvar Cartão"):
        if nome_cartao.strip() and limite_cartao > 0:
            inserir_cartao(nome_cartao.strip(), limite_cartao)
            st.success("Cartão cadastrado com sucesso!")
            st.rerun()
        else:
            st.warning("Preencha o nome e um limite maior que zero.")

# Tabela de cartões
if not df_cartoes.empty:
    st.markdown("**Cartões cadastrados**")
    df_cartoes_exibir = df_cartoes.copy()
    df_cartoes_exibir["disponivel"] = df_cartoes_exibir["limite_total"] - df_cartoes_exibir["limite_usado"]
    df_cartoes_exibir["limite_total"] = df_cartoes_exibir["limite_total"].apply(formatar_brl)
    df_cartoes_exibir["limite_usado"] = df_cartoes_exibir["limite_usado"].apply(formatar_brl)
    df_cartoes_exibir["disponivel"] = df_cartoes_exibir["disponivel"].apply(formatar_brl)

    st.dataframe(
        df_cartoes_exibir[["id", "nome_cartao", "limite_total", "limite_usado", "disponivel"]],
        use_container_width=True,
        hide_index=True
    )

    # Usar cartão
    with st.expander("Registrar compra no cartão", expanded=False):
        opcoes_cartao = {
            f'ID {row["id"]} - {row["nome_cartao"]}': row["id"]
            for _, row in df_cartoes.iterrows()
        }

        cartao_selecionado = st.selectbox("Selecione o cartão", list(opcoes_cartao.keys()), key="cartao_compra")
        data_compra = st.date_input("Data da compra", value=date.today(), key="data_compra")
        descricao_compra = st.text_input("Descrição da compra", key="descricao_compra")
        valor_compra = st.number_input("Valor da compra (R$)", min_value=0.0, format="%.2f", key="valor_compra")

        if st.button("Registrar Compra no Cartão"):
            if valor_compra > 0:
                ok, msg = usar_cartao(
                    opcoes_cartao[cartao_selecionado],
                    valor_compra,
                    descricao_compra,
                    str(data_compra)
                )
                if ok:
                    st.success(msg)
                    st.rerun()
                else:
                    st.warning(msg)
            else:
                st.warning("Informe um valor maior que zero.")

    # Pagar fatura
    with st.expander("Pagar fatura do cartão", expanded=False):
        cartao_fatura = st.selectbox("Selecione o cartão para pagar fatura", list(opcoes_cartao.keys()), key="cartao_fatura")
        valor_fatura = st.number_input("Valor do pagamento da fatura (R$)", min_value=0.0, format="%.2f", key="valor_fatura")

        if st.button("Pagar Fatura"):
            if valor_fatura > 0:
                ok, msg = pagar_fatura_cartao(opcoes_cartao[cartao_fatura], valor_fatura)
                if ok:
                    st.success(msg)
                    st.rerun()
                else:
                    st.warning(msg)
            else:
                st.warning("Informe um valor maior que zero.")
else:
    st.info("Nenhum cartão cadastrado ainda.")

st.divider()

# ==========================================
# DÍVIDAS (TUDO NO FINAL)
# ==========================================
st.subheader("🤝 Dívidas")

# NOVA DÍVIDA
with st.expander("Cadastrar nova dívida", expanded=False):
    nome_pessoa = st.text_input("Pessoa para quem você deve", key="nome_divida")
    desc_divida = st.text_input("Descrição da dívida", key="desc_divida")
    valor_divida = st.number_input("Valor total da dívida (R$)", min_value=0.0, format="%.2f", key="valor_divida")
    data_divida = st.date_input("Data da dívida", value=date.today(), key="data_divida")

    if st.button("Salvar Dívida"):
        if nome_pessoa.strip() and valor_divida > 0:
            inserir_divida(nome_pessoa.strip(), desc_divida, valor_divida, str(data_divida))
            st.success("Dívida cadastrada com sucesso!")
            st.rerun()
        else:
            st.warning("Preencha o nome da pessoa e um valor maior que zero.")

# PAGAR DÍVIDA
dividas_abertas_df = pd.DataFrame()
if not df_dividas.empty and "status" in df_dividas.columns:
    dividas_abertas_df = df_dividas[df_dividas["status"] == "Aberta"].copy()

if not dividas_abertas_df.empty:
    with st.expander("Registrar pagamento de dívida", expanded=False):
        opcoes_dividas = {}
        for _, row in dividas_abertas_df.iterrows():
            nome = row["nome_pessoa"] if "nome_pessoa" in row.index else "Sem nome"
            restante = row["valor_restante"] if "valor_restante" in row.index else 0
            opcoes_dividas[f'ID {row["id"]} - {nome} | Restante: {formatar_brl(restante)}'] = row["id"]

        divida_selecionada = st.selectbox("Selecione a dívida", list(opcoes_dividas.keys()), key="divida_pagamento")
        valor_pagamento = st.number_input("Valor do pagamento", min_value=0.0, format="%.2f", key="valor_pagamento")
        data_pagamento = st.date_input("Data do pagamento", value=date.today(), key="data_pagamento")

        if st.button("Registrar Pagamento da Dívida"):
            id_divida = opcoes_dividas[divida_selecionada]
            if valor_pagamento > 0:
                pagar_divida(id_divida, valor_pagamento, str(data_pagamento))
                st.success("Pagamento registrado! Também entrou como despesa.")
                st.rerun()
            else:
                st.warning("Informe um valor maior que zero.")
else:
    st.info("Não há dívidas abertas no momento.")

# TABELA DE DÍVIDAS
if not df_dividas.empty:
    st.markdown("**Lista de dívidas**")

    df_dividas_exibir = df_dividas.copy()

    if "data_criacao" in df_dividas_exibir.columns:
        df_dividas_exibir["data_criacao"] = pd.to_datetime(
            df_dividas_exibir["data_criacao"], errors="coerce"
        ).dt.strftime("%d/%m/%Y")

    if "valor_total" in df_dividas_exibir.columns:
        df_dividas_exibir["valor_total"] = df_dividas_exibir["valor_total"].apply(formatar_brl)

    if "valor_restante" in df_dividas_exibir.columns:
        df_dividas_exibir["valor_restante"] = df_dividas_exibir["valor_restante"].apply(formatar_brl)

    st.dataframe(
        df_dividas_exibir[["id", "nome_pessoa", "descricao", "valor_total", "valor_restante", "data_criacao", "status"]],
        use_container_width=True,
        hide_index=True
    )

    id_excluir_div = st.selectbox(
        "Selecione o ID da dívida para excluir",
        df_dividas["id"].tolist(),
        key="excluir_div"
    )

    if st.button("Excluir Dívida"):
        excluir_divida(id_excluir_div)
        st.success("Dívida excluída com sucesso!")
        st.rerun()

    # Gráfico de dívidas abertas
    if "status" in df_dividas.columns and "nome_pessoa" in df_dividas.columns and "valor_restante" in df_dividas.columns:
        abertas = df_dividas[df_dividas["status"] == "Aberta"]
        if not abertas.empty:
            st.markdown("**Dívidas abertas por pessoa**")
            graf_dividas = abertas.groupby("nome_pessoa")["valor_restante"].sum().sort_values(ascending=False)
            st.bar_chart(graf_dividas)
else:
    st.info("Nenhuma dívida cadastrada.")
