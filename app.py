import streamlit as st
import pandas as pd
import sqlite3
import altair as alt
from datetime import date, datetime
from dateutil.relativedelta import relativedelta

# =========================================================
# CONFIG
# =========================================================
st.set_page_config(
    page_title="Finanças",
    page_icon="💰",
    layout="wide"
)

DB_NAME = "financeiro.db"

# =========================================================
# ESTILO (MOBILE FIRST)
# =========================================================
st.markdown("""
<style>
    .main > div {
        padding-top: 0.6rem;
        padding-bottom: 1.5rem;
    }

    .block-container {
        padding-top: 0.8rem !important;
        padding-left: 0.7rem !important;
        padding-right: 0.7rem !important;
        max-width: 1200px;
    }

    div[data-testid="stMetric"] {
        background: #f8fafc;
        border: 1px solid #e5e7eb;
        padding: 12px;
        border-radius: 14px;
        box-shadow: 0 1px 3px rgba(0,0,0,0.05);
    }

    .stButton > button {
        width: 100%;
        border-radius: 10px;
        min-height: 42px;
        font-weight: 600;
    }

    .card-lite {
        background: #ffffff;
        border: 1px solid #e5e7eb;
        border-radius: 14px;
        padding: 12px;
        margin-bottom: 10px;
        box-shadow: 0 1px 2px rgba(0,0,0,0.04);
    }

    .section-title {
        font-size: 1.05rem;
        font-weight: 700;
        margin-top: 0.2rem;
        margin-bottom: 0.6rem;
    }

    .small-muted {
        font-size: 0.85rem;
        color: #6b7280;
    }

    @media (max-width: 768px) {
        .block-container {
            padding-left: 0.45rem !important;
            padding-right: 0.45rem !important;
        }

        h1 {
            font-size: 1.7rem !important;
        }

        h2, h3 {
            font-size: 1.1rem !important;
        }
    }
</style>
""", unsafe_allow_html=True)

# =========================================================
# CONSTANTES
# =========================================================
CATEGORIAS_RECEITA = ["Salário", "Freela", "Show", "Outros"]
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
    "Pagamento de Dívida",
    "Cartão Parcelado",
    "Outros"
]

FORMAS_PAGAMENTO = [
    "Débito/Pix BB",
    "Crédito BB",
    "Crédito BB Parcelado",
    "Dinheiro",
    "Outro"
]

# =========================================================
# BANCO
# =========================================================
def conectar():
    return sqlite3.connect(DB_NAME, check_same_thread=False)

def criar_tabelas():
    conn = conectar()
    cursor = conn.cursor()

    # Lançamentos
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS lancamentos (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            data TEXT NOT NULL,
            tipo TEXT NOT NULL,
            categoria TEXT NOT NULL,
            descricao TEXT,
            valor REAL NOT NULL,
            banco TEXT,
            forma_pagamento TEXT,
            parcelado INTEGER DEFAULT 0,
            qtd_parcelas INTEGER DEFAULT 1,
            parcela_atual INTEGER DEFAULT 1,
            grupo_parcelado_id TEXT
        )
    """)

    # Dívidas
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

    # Parcelas futuras (agenda)
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS parcelas_futuras (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            grupo_parcelado_id TEXT NOT NULL,
            data_prevista TEXT NOT NULL,
            descricao TEXT,
            valor REAL NOT NULL,
            banco TEXT,
            forma_pagamento TEXT,
            parcela_numero INTEGER NOT NULL,
            total_parcelas INTEGER NOT NULL,
            status TEXT NOT NULL DEFAULT 'Pendente'
        )
    """)

    conn.commit()
    conn.close()

def garantir_colunas_lancamentos():
    conn = conectar()
    cursor = conn.cursor()

    cursor.execute("PRAGMA table_info(lancamentos)")
    cols = [c[1] for c in cursor.fetchall()]

    novas_colunas = {
        "parcelado": "INTEGER DEFAULT 0",
        "qtd_parcelas": "INTEGER DEFAULT 1",
        "parcela_atual": "INTEGER DEFAULT 1",
        "grupo_parcelado_id": "TEXT"
    }

    for col, tipo in novas_colunas.items():
        if col not in cols:
            cursor.execute(f"ALTER TABLE lancamentos ADD COLUMN {col} {tipo}")

    conn.commit()
    conn.close()

# =========================================================
# UTILITÁRIOS
# =========================================================
def formatar_brl(valor):
    try:
        return f"R$ {float(valor):,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")
    except:
        return "R$ 0,00"

def to_date_safe(valor):
    try:
        return pd.to_datetime(valor).date()
    except:
        return date.today()

def gerar_grupo_parcelado_id():
    return f"PARC-{datetime.now().strftime('%Y%m%d%H%M%S%f')}"

def periodo_label(df):
    if df.empty:
        return "Sem dados"
    dt_min = df["data"].min()
    dt_max = df["data"].max()
    if pd.isna(dt_min) or pd.isna(dt_max):
        return "Sem período"
    return f"{dt_min.strftime('%d/%m/%Y')} até {dt_max.strftime('%d/%m/%Y')}"

# =========================================================
# FUNÇÕES - LANÇAMENTOS
# =========================================================
def inserir_lancamento(
    data, tipo, categoria, descricao, valor, banco, forma_pagamento,
    parcelado=0, qtd_parcelas=1, parcela_atual=1, grupo_parcelado_id=None
):
    conn = conectar()
    cursor = conn.cursor()
    cursor.execute("""
        INSERT INTO lancamentos (
            data, tipo, categoria, descricao, valor, banco, forma_pagamento,
            parcelado, qtd_parcelas, parcela_atual, grupo_parcelado_id
        )
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    """, (
        data, tipo, categoria, descricao, valor, banco, forma_pagamento,
        parcelado, qtd_parcelas, parcela_atual, grupo_parcelado_id
    ))
    conn.commit()
    conn.close()

def inserir_lancamento_com_parcelas(data, tipo, categoria, descricao, valor_total, banco, forma_pagamento, qtd_parcelas):
    if qtd_parcelas <= 1:
        inserir_lancamento(
            data=data,
            tipo=tipo,
            categoria=categoria,
            descricao=descricao,
            valor=valor_total,
            banco=banco,
            forma_pagamento=forma_pagamento,
            parcelado=0,
            qtd_parcelas=1,
            parcela_atual=1,
            grupo_parcelado_id=None
        )
        return

    grupo_id = gerar_grupo_parcelado_id()
    valor_parcela = round(valor_total / qtd_parcelas, 2)

    # Ajuste da última parcela para evitar erro de centavos
    valores = [valor_parcela] * qtd_parcelas
    soma_parcial = round(sum(valores[:-1]), 2)
    valores[-1] = round(valor_total - soma_parcial, 2)

    data_base = pd.to_datetime(data)

    # 1ª parcela entra em lançamentos imediatamente
    inserir_lancamento(
        data=str(data_base.date()),
        tipo=tipo,
        categoria="Cartão Parcelado" if tipo == "Despesa" else categoria,
        descricao=f"{descricao} (1/{qtd_parcelas})",
        valor=valores[0],
        banco=banco,
        forma_pagamento=forma_pagamento,
        parcelado=1,
        qtd_parcelas=qtd_parcelas,
        parcela_atual=1,
        grupo_parcelado_id=grupo_id
    )

    # Demais vão para agenda de parcelas futuras
    conn = conectar()
    cursor = conn.cursor()

    for i in range(2, qtd_parcelas + 1):
        data_prevista = (data_base + relativedelta(months=i-1)).date()
        cursor.execute("""
            INSERT INTO parcelas_futuras (
                grupo_parcelado_id, data_prevista, descricao, valor, banco,
                forma_pagamento, parcela_numero, total_parcelas, status
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            grupo_id,
            str(data_prevista),
            descricao,
            valores[i-1],
            banco,
            forma_pagamento,
            i,
            qtd_parcelas,
            "Pendente"
        ))

    conn.commit()
    conn.close()

def processar_parcelas_vencidas():
    """Transforma parcelas futuras vencidas/em mês atual em lançamentos reais automaticamente."""
    conn = conectar()
    cursor = conn.cursor()

    hoje = date.today()

    df_parcelas = pd.read_sql_query("""
        SELECT * FROM parcelas_futuras
        WHERE status = 'Pendente'
        ORDER BY data_prevista ASC
    """, conn)

    if not df_parcelas.empty:
        for _, row in df_parcelas.iterrows():
            data_prev = to_date_safe(row["data_prevista"])
            if data_prev <= hoje:
                cursor.execute("""
                    INSERT INTO lancamentos (
                        data, tipo, categoria, descricao, valor, banco, forma_pagamento,
                        parcelado, qtd_parcelas, parcela_atual, grupo_parcelado_id
                    )
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, (
                    str(data_prev),
                    "Despesa",
                    "Cartão Parcelado",
                    f'{row["descricao"]} ({row["parcela_numero"]}/{row["total_parcelas"]})',
                    float(row["valor"]),
                    row["banco"],
                    row["forma_pagamento"],
                    1,
                    int(row["total_parcelas"]),
                    int(row["parcela_numero"]),
                    row["grupo_parcelado_id"]
                ))

                cursor.execute("""
                    UPDATE parcelas_futuras
                    SET status = 'Lançada'
                    WHERE id = ?
                """, (int(row["id"]),))

    conn.commit()
    conn.close()

def listar_lancamentos():
    conn = conectar()
    try:
        df = pd.read_sql_query("SELECT * FROM lancamentos ORDER BY data DESC, id DESC", conn)
    except:
        df = pd.DataFrame(columns=[
            "id", "data", "tipo", "categoria", "descricao", "valor", "banco", "forma_pagamento",
            "parcelado", "qtd_parcelas", "parcela_atual", "grupo_parcelado_id"
        ])
    conn.close()
    return df

def buscar_lancamento_por_id(id_lancamento):
    conn = conectar()
    try:
        df = pd.read_sql_query("SELECT * FROM lancamentos WHERE id = ?", conn, params=(id_lancamento,))
        if not df.empty:
            return df.iloc[0].to_dict()
        return None
    except:
        return None
    finally:
        conn.close()

def atualizar_lancamento(id_lancamento, data, tipo, categoria, descricao, valor, banco, forma_pagamento):
    conn = conectar()
    cursor = conn.cursor()
    cursor.execute("""
        UPDATE lancamentos
        SET data = ?, tipo = ?, categoria = ?, descricao = ?, valor = ?, banco = ?, forma_pagamento = ?
        WHERE id = ?
    """, (data, tipo, categoria, descricao, valor, banco, forma_pagamento, id_lancamento))
    conn.commit()
    conn.close()

def excluir_lancamento(id_lancamento):
    conn = conectar()
    cursor = conn.cursor()
    cursor.execute("DELETE FROM lancamentos WHERE id = ?", (id_lancamento,))
    conn.commit()
    conn.close()

# =========================================================
# FUNÇÕES - DÍVIDAS
# =========================================================
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
        df = pd.DataFrame(columns=[
            "id", "nome_pessoa", "descricao", "valor_total", "valor_restante", "data_criacao", "status"
        ])
    conn.close()
    return df

def buscar_divida_por_id(id_divida):
    conn = conectar()
    try:
        df = pd.read_sql_query("SELECT * FROM dividas WHERE id = ?", conn, params=(id_divida,))
        if not df.empty:
            return df.iloc[0].to_dict()
        return None
    except:
        return None
    finally:
        conn.close()

def atualizar_divida(id_divida, nome_pessoa, descricao, valor_total, valor_restante, data_criacao, status):
    conn = conectar()
    cursor = conn.cursor()
    cursor.execute("""
        UPDATE dividas
        SET nome_pessoa = ?, descricao = ?, valor_total = ?, valor_restante = ?, data_criacao = ?, status = ?
        WHERE id = ?
    """, (nome_pessoa, descricao, valor_total, valor_restante, data_criacao, status, id_divida))
    conn.commit()
    conn.close()

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

        cursor.execute("""
            INSERT INTO lancamentos (
                data, tipo, categoria, descricao, valor, banco, forma_pagamento,
                parcelado, qtd_parcelas, parcela_atual, grupo_parcelado_id
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, 0, 1, 1, NULL)
        """, (
            data_pagamento,
            "Despesa",
            "Pagamento de Dívida",
            f"Pagamento de dívida para {nome_pessoa}",
            valor_pagamento_real,
            "",
            ""
        ))

    conn.commit()
    conn.close()

def excluir_divida(id_divida):
    conn = conectar()
    cursor = conn.cursor()
    cursor.execute("DELETE FROM dividas WHERE id = ?", (id_divida,))
    conn.commit()
    conn.close()

# =========================================================
# FUNÇÕES - PARCELAS
# =========================================================
def listar_parcelas_futuras():
    conn = conectar()
    try:
        df = pd.read_sql_query("""
            SELECT * FROM parcelas_futuras
            ORDER BY data_prevista ASC, parcela_numero ASC
        """, conn)
    except:
        df = pd.DataFrame(columns=[
            "id", "grupo_parcelado_id", "data_prevista", "descricao", "valor",
            "banco", "forma_pagamento", "parcela_numero", "total_parcelas", "status"
        ])
    conn.close()
    return df

# =========================================================
# INICIALIZAÇÃO
# =========================================================
criar_tabelas()
garantir_colunas_lancamentos()
processar_parcelas_vencidas()

# =========================================================
# CARREGAMENTO
# =========================================================
df = listar_lancamentos()
df_dividas = listar_dividas()
df_parcelas = listar_parcelas_futuras()

if not df.empty:
    df["valor"] = pd.to_numeric(df["valor"], errors="coerce").fillna(0)
    df["data"] = pd.to_datetime(df["data"], errors="coerce")
    df["mes"] = df["data"].dt.to_period("M").astype(str)

if not df_dividas.empty:
    for col in ["valor_total", "valor_restante"]:
        df_dividas[col] = pd.to_numeric(df_dividas[col], errors="coerce").fillna(0)

if not df_parcelas.empty:
    df_parcelas["valor"] = pd.to_numeric(df_parcelas["valor"], errors="coerce").fillna(0)
    df_parcelas["data_prevista"] = pd.to_datetime(df_parcelas["data_prevista"], errors="coerce")
    df_parcelas["mes"] = df_parcelas["data_prevista"].dt.to_period("M").astype(str)

# =========================================================
# HEADER
# =========================================================
st.title("💰 Finanças")

# =========================================================
# FILTROS
# =========================================================
st.markdown('<div class="section-title">🗓️ Filtros</div>', unsafe_allow_html=True)

if not df.empty:
    meses_disponiveis = sorted(df["mes"].dropna().unique().tolist(), reverse=True)
else:
    meses_disponiveis = []

colf1, colf2, colf3 = st.columns([1, 1, 1])

with colf1:
    mes_opcoes = ["Todos"] + meses_disponiveis
    mes_selecionado = st.selectbox("Filtro por mês", mes_opcoes, key="filtro_mes")

with colf2:
    data_inicial = st.date_input(
        "Data inicial",
        value=df["data"].min().date() if not df.empty and pd.notna(df["data"].min()) else date.today().replace(day=1),
        key="filtro_data_inicial"
    )

with colf3:
    data_final = st.date_input(
        "Data final",
        value=df["data"].max().date() if not df.empty and pd.notna(df["data"].max()) else date.today(),
        key="filtro_data_final"
    )

# Aplicação dos filtros
df_filtrado = df.copy()

if not df_filtrado.empty:
    if mes_selecionado != "Todos":
        df_filtrado = df_filtrado[df_filtrado["mes"] == mes_selecionado].copy()

    df_filtrado = df_filtrado[
        (df_filtrado["data"].dt.date >= data_inicial) &
        (df_filtrado["data"].dt.date <= data_final)
    ].copy()

st.caption(f"Período aplicado: {periodo_label(df_filtrado)}")
st.divider()

# =========================================================
# RESUMO
# =========================================================
receitas = df_filtrado[df_filtrado["tipo"] == "Receita"]["valor"].sum() if not df_filtrado.empty else 0
despesas = df_filtrado[df_filtrado["tipo"] == "Despesa"]["valor"].sum() if not df_filtrado.empty else 0
saldo = receitas - despesas
dividas_abertas = df_dividas[df_dividas["status"] == "Aberta"]["valor_restante"].sum() if not df_dividas.empty else 0

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

st.divider()

# =========================================================
# NOVO LANÇAMENTO
# =========================================================
st.markdown('<div class="section-title">➕ Novo Lançamento</div>', unsafe_allow_html=True)

with st.expander("Abrir formulário de lançamento", expanded=False):
    c1, c2 = st.columns(2)
    with c1:
        data_lanc = st.date_input("Data", value=date.today(), key="data_lanc")
        tipo = st.selectbox("Tipo", ["Receita", "Despesa"], key="tipo_lanc")
        descricao = st.text_input("Descrição", key="descricao_lanc")
        valor = st.number_input("Valor total (R$)", min_value=0.0, format="%.2f", key="valor_lanc")

    with c2:
        categorias = CATEGORIAS_RECEITA if tipo == "Receita" else CATEGORIAS_DESPESA
        categoria = st.selectbox("Categoria", categorias, key="categoria_lanc")
        banco = st.text_input("Banco / Cartão / Conta", key="banco_lanc")
        forma_pagamento = st.selectbox("Forma de pagamento", FORMAS_PAGAMENTO, key="forma_pagamento_lanc")

    parcelado = False
    qtd_parcelas = 1

    if tipo == "Despesa" and forma_pagamento == "Crédito BB Parcelado":
        parcelado = st.checkbox("Lançamento parcelado?", value=True, key="parcelado_check")
        if parcelado:
            qtd_parcelas = st.number_input("Quantidade de parcelas", min_value=2, max_value=48, value=2, step=1, key="qtd_parcelas")

    if st.button("Salvar Lançamento"):
        if valor <= 0:
            st.warning("Informe um valor maior que zero.")
        else:
            if parcelado and qtd_parcelas > 1:
                inserir_lancamento_com_parcelas(
                    data=str(data_lanc),
                    tipo=tipo,
                    categoria=categoria,
                    descricao=descricao.strip() if descricao else "Compra parcelada",
                    valor_total=valor,
                    banco=banco.strip(),
                    forma_pagamento=forma_pagamento,
                    qtd_parcelas=int(qtd_parcelas)
                )
                st.success("Lançamento parcelado salvo! A primeira parcela entrou agora e as futuras foram agendadas.")
            else:
                inserir_lancamento(
                    data=str(data_lanc),
                    tipo=tipo,
                    categoria=categoria,
                    descricao=descricao.strip(),
                    valor=valor,
                    banco=banco.strip(),
                    forma_pagamento=forma_pagamento,
                    parcelado=0,
                    qtd_parcelas=1,
                    parcela_atual=1,
                    grupo_parcelado_id=None
                )
                st.success("Lançamento salvo com sucesso!")

            st.rerun()

st.divider()

# =========================================================
# GRÁFICOS
# =========================================================
st.markdown('<div class="section-title">📊 Painel Visual</div>', unsafe_allow_html=True)

resumo_grafico = pd.DataFrame({
    "Tipo": ["Entradas", "Despesas"],
    "Valor": [receitas, despesas]
})

grafico_resumo = alt.Chart(resumo_grafico).mark_bar().encode(
    x=alt.X("Tipo:N", sort=["Entradas", "Despesas"]),
    y=alt.Y("Valor:Q"),
    color=alt.Color(
        "Tipo:N",
        scale=alt.Scale(domain=["Entradas", "Despesas"], range=["#16a34a", "#dc2626"]),
        legend=None
    ),
    tooltip=["Tipo", alt.Tooltip("Valor:Q", format=",.2f")]
).properties(height=320)

st.altair_chart(grafico_resumo, use_container_width=True)

colg1, colg2 = st.columns(2)

with colg1:
    st.markdown("**Entradas e despesas por mês (geral)**")
    if not df.empty:
        mensal_tipo = df.groupby(["mes", "tipo"])["valor"].sum().reset_index()
        mensal_tipo["tipo_grafico"] = mensal_tipo["tipo"].replace({"Receita": "Entradas", "Despesa": "Despesas"})

        grafico_mensal = alt.Chart(mensal_tipo).mark_bar().encode(
            x=alt.X("mes:N", title="Mês", sort=None),
            y=alt.Y("valor:Q", title="Valor"),
            color=alt.Color(
                "tipo_grafico:N",
                scale=alt.Scale(domain=["Entradas", "Despesas"], range=["#16a34a", "#dc2626"]),
                title="Tipo"
            ),
            xOffset="tipo_grafico:N",
            tooltip=["mes", "tipo_grafico", alt.Tooltip("valor:Q", format=",.2f")]
        ).properties(height=320)

        st.altair_chart(grafico_mensal, use_container_width=True)
    else:
        st.info("Sem lançamentos cadastrados.")

with colg2:
    st.markdown("**Gastos por categoria (respeita os filtros)**")
    if not df_filtrado.empty:
        despesas_df = df_filtrado[df_filtrado["tipo"] == "Despesa"]
        if not despesas_df.empty:
            gastos_categoria = despesas_df.groupby("categoria")["valor"].sum().reset_index().sort_values("valor", ascending=False)

            grafico_categoria = alt.Chart(gastos_categoria).mark_bar().encode(
                x=alt.X("categoria:N", sort="-y", title="Categoria"),
                y=alt.Y("valor:Q", title="Valor"),
                color=alt.Color("categoria:N", legend=None),
                tooltip=["categoria", alt.Tooltip("valor:Q", format=",.2f")]
            ).properties(height=320)

            st.altair_chart(grafico_categoria, use_container_width=True)
        else:
            st.info("Sem despesas no período.")
    else:
        st.info("Sem dados no período.")

st.divider()

# =========================================================
# SALDO POR BANCO / CARTÃO
# =========================================================
st.markdown('<div class="section-title">🏦 Saldo por Banco / Cartão</div>', unsafe_allow_html=True)

if not df.empty:
    df_bancos = df.copy()
    df_bancos["banco"] = df_bancos["banco"].fillna("").replace("", "Não informado")

    entradas_banco = df_bancos[df_bancos["tipo"] == "Receita"].groupby("banco")["valor"].sum()
    despesas_banco = df_bancos[df_bancos["tipo"] == "Despesa"].groupby("banco")["valor"].sum()

    bancos_index = sorted(set(entradas_banco.index).union(set(despesas_banco.index)))

    linhas = []
    for banco_nome in bancos_index:
        ent = float(entradas_banco.get(banco_nome, 0))
        des = float(despesas_banco.get(banco_nome, 0))
        linhas.append({
            "Banco/Cartão": banco_nome,
            "Entradas": ent,
            "Despesas": des,
            "Saldo": ent - des
        })

    df_saldo_banco = pd.DataFrame(linhas).sort_values("Saldo", ascending=False)

    df_saldo_banco_exibir = df_saldo_banco.copy()
    df_saldo_banco_exibir["Entradas"] = df_saldo_banco_exibir["Entradas"].apply(formatar_brl)
    df_saldo_banco_exibir["Despesas"] = df_saldo_banco_exibir["Despesas"].apply(formatar_brl)
    df_saldo_banco_exibir["Saldo"] = df_saldo_banco_exibir["Saldo"].apply(formatar_brl)

    st.dataframe(df_saldo_banco_exibir, use_container_width=True, hide_index=True)

    graf_saldo_banco = alt.Chart(df_saldo_banco).mark_bar().encode(
        x=alt.X("Banco/Cartão:N", sort="-y"),
        y=alt.Y("Saldo:Q"),
        color=alt.Color("Banco/Cartão:N", legend=None),
        tooltip=["Banco/Cartão", alt.Tooltip("Saldo:Q", format=",.2f")]
    ).properties(height=320)

    st.altair_chart(graf_saldo_banco, use_container_width=True)
else:
    st.info("Sem dados suficientes para saldo por banco/cartão.")

st.divider()

# =========================================================
# RELAÇÃO GERAL
# =========================================================
st.markdown('<div class="section-title">📋 Relação Geral</div>', unsafe_allow_html=True)

resumo_geral = pd.DataFrame({
    "Indicador": ["Total de Entradas", "Total de Despesas", "Saldo Atual", "Dívidas em Aberto"],
    "Valor": [receitas, despesas, saldo, dividas_abertas]
})
resumo_geral["Valor"] = resumo_geral["Valor"].apply(formatar_brl)

st.dataframe(resumo_geral, use_container_width=True, hide_index=True)

st.markdown("**Resumo mensal (geral)**")
if not df.empty:
    resumo_mensal = df.groupby(["mes", "tipo"])["valor"].sum().unstack(fill_value=0).reset_index()

    if "Receita" not in resumo_mensal.columns:
        resumo_mensal["Receita"] = 0
    if "Despesa" not in resumo_mensal.columns:
        resumo_mensal["Despesa"] = 0

    resumo_mensal["Saldo"] = resumo_mensal["Receita"] - resumo_mensal["Despesa"]

    resumo_mensal = resumo_mensal.rename(columns={
        "mes": "Mês",
        "Receita": "Entradas",
        "Despesa": "Despesas"
    })

    resumo_mensal_exibir = resumo_mensal.copy()
    resumo_mensal_exibir["Entradas"] = resumo_mensal_exibir["Entradas"].apply(formatar_brl)
    resumo_mensal_exibir["Despesas"] = resumo_mensal_exibir["Despesas"].apply(formatar_brl)
    resumo_mensal_exibir["Saldo"] = resumo_mensal_exibir["Saldo"].apply(formatar_brl)

    st.dataframe(resumo_mensal_exibir, use_container_width=True, hide_index=True)
else:
    st.info("Sem dados mensais ainda.")

st.divider()

# =========================================================
# LANÇAMENTOS (LISTA + EDIÇÃO INLINE COM CANETINHA)
# =========================================================
st.markdown('<div class="section-title">🧾 Lançamentos</div>', unsafe_allow_html=True)

if "edit_lancamento_id" not in st.session_state:
    st.session_state.edit_lancamento_id = None

if not df_filtrado.empty:
    for _, row in df_filtrado.sort_values(["data", "id"], ascending=[False, False]).iterrows():
        with st.container():
            c1, c2 = st.columns([6, 1])

            with c1:
                st.markdown(f"""
                <div class="card-lite">
                    <b>ID {int(row['id'])}</b> • {row['data'].strftime('%d/%m/%Y')}<br>
                    <span class="small-muted">{row['tipo']} | {row['categoria']}</span><br>
                    <b>{formatar_brl(row['valor'])}</b><br>
                    {row['descricao'] if pd.notna(row['descricao']) and str(row['descricao']).strip() else 'Sem descrição'}<br>
                    <span class="small-muted">Banco/Conta: {row['banco'] if pd.notna(row['banco']) and str(row['banco']).strip() else 'Não informado'} | {row['forma_pagamento'] if pd.notna(row['forma_pagamento']) and str(row['forma_pagamento']).strip() else 'Não informado'}</span>
                </div>
                """, unsafe_allow_html=True)

            with c2:
                if st.button("🖊️", key=f"btn_edit_lanc_{int(row['id'])}"):
                    st.session_state.edit_lancamento_id = int(row["id"])

                if st.button("🗑️", key=f"btn_del_lanc_{int(row['id'])}"):
                    excluir_lancamento(int(row["id"]))
                    st.success("Lançamento excluído com sucesso!")
                    st.rerun()

            if st.session_state.edit_lancamento_id == int(row["id"]):
                lanc = buscar_lancamento_por_id(int(row["id"]))
                if lanc:
                    st.markdown("**Editar este lançamento**")

                    tipo_padrao = lanc["tipo"] if lanc["tipo"] in ["Receita", "Despesa"] else "Despesa"
                    data_padrao = to_date_safe(lanc["data"])

                    tipo_edit = st.selectbox(
                        "Tipo",
                        ["Receita", "Despesa"],
                        index=0 if tipo_padrao == "Receita" else 1,
                        key=f"tipo_edit_{row['id']}"
                    )

                    categorias_edit = CATEGORIAS_RECEITA if tipo_edit == "Receita" else CATEGORIAS_DESPESA
                    categoria_padrao = lanc["categoria"] if lanc["categoria"] in categorias_edit else categorias_edit[0]
                    forma_padrao = lanc["forma_pagamento"] if lanc["forma_pagamento"] in FORMAS_PAGAMENTO else FORMAS_PAGAMENTO[0]

                    e1, e2 = st.columns(2)
                    with e1:
                        data_edit = st.date_input("Data", value=data_padrao, key=f"data_edit_{row['id']}")
                        categoria_edit = st.selectbox(
                            "Categoria",
                            categorias_edit,
                            index=categorias_edit.index(categoria_padrao) if categoria_padrao in categorias_edit else 0,
                            key=f"cat_edit_{row['id']}"
                        )
                        valor_edit = st.number_input(
                            "Valor",
                            min_value=0.0,
                            value=float(lanc["valor"]),
                            format="%.2f",
                            key=f"valor_edit_{row['id']}"
                        )

                    with e2:
                        descricao_edit = st.text_input("Descrição", value=lanc["descricao"] or "", key=f"desc_edit_{row['id']}")
                        banco_edit = st.text_input("Banco/Conta", value=lanc["banco"] or "", key=f"banco_edit_{row['id']}")
                        forma_edit = st.selectbox(
                            "Forma de pagamento",
                            FORMAS_PAGAMENTO,
                            index=FORMAS_PAGAMENTO.index(forma_padrao) if forma_padrao in FORMAS_PAGAMENTO else 0,
                            key=f"forma_edit_{row['id']}"
                        )

                    a1, a2 = st.columns(2)
                    with a1:
                        if st.button("Salvar alterações", key=f"salvar_edit_{row['id']}"):
                            if valor_edit > 0:
                                atualizar_lancamento(
                                    int(row["id"]),
                                    str(data_edit),
                                    tipo_edit,
                                    categoria_edit,
                                    descricao_edit.strip(),
                                    float(valor_edit),
                                    banco_edit.strip(),
                                    forma_edit
                                )
                                st.success("Lançamento atualizado!")
                                st.session_state.edit_lancamento_id = None
                                st.rerun()
                            else:
                                st.warning("Informe um valor maior que zero.")
                    with a2:
                        if st.button("Cancelar edição", key=f"cancelar_edit_{row['id']}"):
                            st.session_state.edit_lancamento_id = None
                            st.rerun()
else:
    st.info("Nenhum lançamento no filtro selecionado.")

st.divider()

# =========================================================
# DÍVIDAS (LISTA + EDIÇÃO INLINE)
# =========================================================
st.markdown('<div class="section-title">🤝 Dívidas</div>', unsafe_allow_html=True)

if "edit_divida_id" not in st.session_state:
    st.session_state.edit_divida_id = None

with st.expander("Cadastrar nova dívida", expanded=False):
    nome_pessoa = st.text_input("Pessoa para quem você deve", key="nome_divida")
    desc_divida = st.text_input("Descrição da dívida", key="desc_divida")
    valor_divida = st.number_input("Valor total da dívida (R$)", min_value=0.0, format="%.2f", key="valor_divida")
    data_divida = st.date_input("Data da dívida", value=date.today(), key="data_divida")

    if st.button("Salvar Dívida"):
        if nome_pessoa.strip() and valor_divida > 0:
            inserir_divida(nome_pessoa.strip(), desc_divida.strip(), valor_divida, str(data_divida))
            st.success("Dívida cadastrada com sucesso!")
            st.rerun()
        else:
            st.warning("Preencha o nome da pessoa e um valor maior que zero.")

dividas_abertas_df = pd.DataFrame()
if not df_dividas.empty:
    dividas_abertas_df = df_dividas[df_dividas["status"] == "Aberta"].copy()

if not dividas_abertas_df.empty:
    with st.expander("Registrar pagamento de dívida", expanded=False):
        opcoes_dividas = {}
        for _, row in dividas_abertas_df.iterrows():
            opcoes_dividas[f'ID {row["id"]} - {row["nome_pessoa"]} | Restante: {formatar_brl(row["valor_restante"])}'] = row["id"]

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

st.markdown("**Lista de dívidas**")

if not df_dividas.empty:
    for _, row in df_dividas.iterrows():
        with st.container():
            c1, c2 = st.columns([6, 1])

            with c1:
                st.markdown(f"""
                <div class="card-lite">
                    <b>ID {int(row['id'])}</b> • {row['nome_pessoa']}<br>
                    <span class="small-muted">{to_date_safe(row['data_criacao']).strftime('%d/%m/%Y')} | {row['status']}</span><br>
                    <b>Total:</b> {formatar_brl(row['valor_total'])} &nbsp;&nbsp; <b>Restante:</b> {formatar_brl(row['valor_restante'])}<br>
                    {row['descricao'] if pd.notna(row['descricao']) and str(row['descricao']).strip() else 'Sem descrição'}
                </div>
                """, unsafe_allow_html=True)

            with c2:
                if st.button("🖊️", key=f"btn_edit_div_{int(row['id'])}"):
                    st.session_state.edit_divida_id = int(row["id"])

                if st.button("🗑️", key=f"btn_del_div_{int(row['id'])}"):
                    excluir_divida(int(row["id"]))
                    st.success("Dívida excluída com sucesso!")
                    st.rerun()

            if st.session_state.edit_divida_id == int(row["id"]):
                div = buscar_divida_por_id(int(row["id"]))
                if div:
                    st.markdown("**Editar esta dívida**")

                    d1, d2 = st.columns(2)

                    with d1:
                        nome_edit = st.text_input("Nome da pessoa", value=div["nome_pessoa"], key=f"nome_edit_div_{row['id']}")
                        total_edit = st.number_input(
                            "Valor total",
                            min_value=0.0,
                            value=float(div["valor_total"]),
                            format="%.2f",
                            key=f"total_edit_div_{row['id']}"
                        )
                        data_edit_div = st.date_input(
                            "Data da dívida",
                            value=to_date_safe(div["data_criacao"]),
                            key=f"data_edit_div_{row['id']}"
                        )

                    with d2:
                        desc_edit_div = st.text_input("Descrição", value=div["descricao"] or "", key=f"desc_edit_div_{row['id']}")
                        restante_edit = st.number_input(
                            "Valor restante",
                            min_value=0.0,
                            value=float(div["valor_restante"]),
                            format="%.2f",
                            key=f"restante_edit_div_{row['id']}"
                        )
                        status_edit = st.selectbox(
                            "Status",
                            ["Aberta", "Quitada"],
                            index=0 if div["status"] == "Aberta" else 1,
                            key=f"status_edit_div_{row['id']}"
                        )

                    b1, b2 = st.columns(2)
                    with b1:
                        if st.button("Salvar dívida", key=f"salvar_div_{row['id']}"):
                            if nome_edit.strip() and total_edit >= 0 and restante_edit >= 0:
                                atualizar_divida(
                                    int(row["id"]),
                                    nome_edit.strip(),
                                    desc_edit_div.strip(),
                                    float(total_edit),
                                    float(restante_edit),
                                    str(data_edit_div),
                                    status_edit
                                )
                                st.success("Dívida atualizada!")
                                st.session_state.edit_divida_id = None
                                st.rerun()
                            else:
                                st.warning("Confira os campos da dívida.")
                    with b2:
                        if st.button("Cancelar", key=f"cancelar_div_{row['id']}"):
                            st.session_state.edit_divida_id = None
                            st.rerun()

    abertas = df_dividas[df_dividas["status"] == "Aberta"]
    if not abertas.empty:
        st.markdown("**Dívidas abertas por pessoa**")
        graf_dividas = abertas.groupby("nome_pessoa")["valor_restante"].sum().reset_index()

        grafico_dividas = alt.Chart(graf_dividas).mark_bar().encode(
            x=alt.X("nome_pessoa:N", sort="-y", title="Pessoa"),
            y=alt.Y("valor_restante:Q", title="Valor Restante"),
            color=alt.Color("nome_pessoa:N", legend=None),
            tooltip=["nome_pessoa", alt.Tooltip("valor_restante:Q", format=",.2f")]
        ).properties(height=320)

        st.altair_chart(grafico_dividas, use_container_width=True)
else:
    st.info("Nenhuma dívida cadastrada.")

st.divider()

# =========================================================
# PARCELAS FUTURAS
# =========================================================
st.markdown('<div class="section-title">💳 Parcelas Futuras</div>', unsafe_allow_html=True)

if not df_parcelas.empty:
    pendentes = df_parcelas[df_parcelas["status"] == "Pendente"].copy()

    if not pendentes.empty:
        pendentes_exibir = pendentes.copy()
        pendentes_exibir["data_prevista"] = pendentes_exibir["data_prevista"].dt.strftime("%d/%m/%Y")
        pendentes_exibir["valor"] = pendentes_exibir["valor"].apply(formatar_brl)
        pendentes_exibir["Parcela"] = pendentes_exibir["parcela_numero"].astype(str) + "/" + pendentes_exibir["total_parcelas"].astype(str)

        st.dataframe(
            pendentes_exibir[["data_prevista", "descricao", "valor", "banco", "forma_pagamento", "Parcela", "status"]],
            use_container_width=True,
            hide_index=True
        )

        total_futuro = pendentes["valor"].sum()
        st.metric("Total de parcelas futuras pendentes", formatar_brl(total_futuro))

        pendentes_mes = pendentes.groupby("mes")["valor"].sum().reset_index()

        grafico_parcelas = alt.Chart(pendentes_mes).mark_bar().encode(
            x=alt.X("mes:N", title="Mês"),
            y=alt.Y("valor:Q", title="Valor"),
            tooltip=["mes", alt.Tooltip("valor:Q", format=",.2f")]
        ).properties(height=320)

        st.altair_chart(grafico_parcelas, use_container_width=True)
    else:
        st.info("Não há parcelas futuras pendentes.")
else:
    st.info("Nenhuma compra parcelada cadastrada ainda.")
