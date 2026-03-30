import streamlit as st
import sqlite3
import pandas as pd
from datetime import datetime, date
from dateutil.relativedelta import relativedelta

# =========================================================
# CONFIG
# =========================================================
st.set_page_config(
    page_title="Finanças app",
    page_icon="💸",
    layout="wide",
)

DB_NAME = "financeiro.db"

BANCOS = [
    "Banco do Brasil",
    "Banrisul",
    "Nubank",
    "Itaú",
    "Flash (Vale Alimentação)"
]

TIPOS = ["Receita", "Despesa"]

CATEGORIAS = [
    "Salário",
    "Freela",
    "Alimentação",
    "Mercado",
    "Transporte",
    "Combustível",
    "Moradia",
    "Lazer",
    "Saúde",
    "Educação",
    "Assinaturas",
    "Fatura Cartão",
    "Outros",
]

# =========================================================
# ESTILO / CSS MOBILE FIRST
# =========================================================
st.markdown("""
<style>
    .main > div {
        padding-top: 1rem;
        padding-bottom: 2rem;
    }

    .block-container {
        padding-top: 1rem;
        padding-bottom: 2rem;
        padding-left: 1rem;
        padding-right: 1rem;
        max-width: 1400px;
    }

    .title-card {
        background: linear-gradient(135deg, #0f172a, #1e3a8a);
        padding: 1.2rem 1.4rem;
        border-radius: 18px;
        color: white;
        margin-bottom: 1rem;
        box-shadow: 0 8px 24px rgba(0,0,0,0.18);
    }

    .section-card {
        background: #ffffff;
        border-radius: 18px;
        padding: 1rem;
        box-shadow: 0 6px 18px rgba(15,23,42,0.08);
        border: 1px solid #e5e7eb;
        margin-bottom: 1rem;
    }

    .metric-card {
        background: white;
        border-radius: 18px;
        padding: 1rem;
        box-shadow: 0 6px 18px rgba(15,23,42,0.08);
        border: 1px solid #e5e7eb;
        text-align: center;
    }

    .small-muted {
        color: #6b7280;
        font-size: 0.85rem;
    }

    .launch-row {
        background: #ffffff;
        border: 1px solid #e5e7eb;
        border-radius: 16px;
        padding: 0.7rem 0.9rem;
        margin-bottom: 0.6rem;
        box-shadow: 0 4px 12px rgba(15,23,42,0.05);
    }

    .stButton>button {
        border-radius: 12px !important;
        font-weight: 600 !important;
    }

    .stDownloadButton>button {
        border-radius: 12px !important;
    }

    @media (max-width: 768px) {
        .block-container {
            padding-left: 0.6rem;
            padding-right: 0.6rem;
        }
    }
</style>
""", unsafe_allow_html=True)

# =========================================================
# DB
# =========================================================
def get_conn():
    return sqlite3.connect(DB_NAME, check_same_thread=False)

def init_db():
    conn = get_conn()
    c = conn.cursor()

    c.execute("""
        CREATE TABLE IF NOT EXISTS lancamentos (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            data TEXT NOT NULL,
            descricao TEXT NOT NULL,
            tipo TEXT NOT NULL,
            categoria TEXT NOT NULL,
            banco TEXT NOT NULL,
            valor REAL NOT NULL,
            observacao TEXT,
            origem TEXT DEFAULT 'manual',
            grupo_parcelamento TEXT
        )
    """)

    c.execute("""
        CREATE TABLE IF NOT EXISTS dividas (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            descricao TEXT NOT NULL,
            banco TEXT NOT NULL,
            categoria TEXT NOT NULL,
            valor_total REAL NOT NULL,
            parcelas INTEGER NOT NULL,
            parcela_atual INTEGER NOT NULL,
            valor_parcela REAL NOT NULL,
            data_primeira_parcela TEXT NOT NULL,
            observacao TEXT,
            grupo_parcelamento TEXT
        )
    """)

    conn.commit()
    conn.close()

# =========================================================
# HELPERS
# =========================================================
def br_money(v):
    return f"R$ {v:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")

def to_date(text):
    return datetime.strptime(text, "%Y-%m-%d").date()

def month_bounds(ref_date):
    first = ref_date.replace(day=1)
    next_month = first + relativedelta(months=1)
    last = next_month - relativedelta(days=1)
    return first, last

def get_period_filter():
    st.markdown("### 🔎 Filtros")
    c1, c2, c3 = st.columns([1, 1, 1])

    today = date.today()
    current_month_start, current_month_end = month_bounds(today)

    with c1:
        filter_mode = st.radio(
            "Modo de filtro",
            ["Mês", "Período"],
            horizontal=True,
            key="filter_mode"
        )

    if filter_mode == "Mês":
        with c2:
            ano = st.number_input("Ano", min_value=2020, max_value=2100, value=today.year, step=1)
        with c3:
            mes = st.selectbox(
                "Mês",
                options=list(range(1, 13)),
                index=today.month - 1,
                format_func=lambda x: [
                    "Janeiro", "Fevereiro", "Março", "Abril", "Maio", "Junho",
                    "Julho", "Agosto", "Setembro", "Outubro", "Novembro", "Dezembro"
                ][x - 1]
            )
        start = date(int(ano), int(mes), 1)
        end = start + relativedelta(months=1) - relativedelta(days=1)
    else:
        with c2:
            start = st.date_input("Data inicial", value=current_month_start, key="period_start")
        with c3:
            end = st.date_input("Data final", value=current_month_end, key="period_end")

    if start > end:
        st.warning("A data inicial não pode ser maior que a data final.")
        return None, None

    return start, end

# =========================================================
# CRUD LANCAMENTOS
# =========================================================
def add_lancamento(data, descricao, tipo, categoria, banco, valor, observacao="", origem="manual", grupo_parcelamento=None):
    conn = get_conn()
    c = conn.cursor()
    c.execute("""
        INSERT INTO lancamentos (data, descricao, tipo, categoria, banco, valor, observacao, origem, grupo_parcelamento)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
    """, (data, descricao, tipo, categoria, banco, valor, observacao, origem, grupo_parcelamento))
    conn.commit()
    conn.close()

def update_lancamento(lanc_id, data, descricao, tipo, categoria, banco, valor, observacao):
    conn = get_conn()
    c = conn.cursor()
    c.execute("""
        UPDATE lancamentos
        SET data=?, descricao=?, tipo=?, categoria=?, banco=?, valor=?, observacao=?
        WHERE id=?
    """, (data, descricao, tipo, categoria, banco, valor, observacao, lanc_id))
    conn.commit()
    conn.close()

def delete_lancamento(lanc_id):
    conn = get_conn()
    c = conn.cursor()
    c.execute("DELETE FROM lancamentos WHERE id=?", (lanc_id,))
    conn.commit()
    conn.close()

def get_lancamentos():
    conn = get_conn()
    df = pd.read_sql_query("SELECT * FROM lancamentos ORDER BY data DESC, id DESC", conn)
    conn.close()
    return df

def get_lancamentos_periodo(start, end):
    conn = get_conn()
    df = pd.read_sql_query("""
        SELECT * FROM lancamentos
        WHERE date(data) BETWEEN date(?) AND date(?)
        ORDER BY data DESC, id DESC
    """, conn, params=(start.isoformat(), end.isoformat()))
    conn.close()
    return df

# =========================================================
# CRUD DIVIDAS / PARCELAMENTOS
# =========================================================
def add_divida(descricao, banco, categoria, valor_total, parcelas, data_primeira_parcela, observacao=""):
    grupo = f"PARC_{datetime.now().strftime('%Y%m%d%H%M%S%f')}"
    valor_parcela = round(valor_total / parcelas, 2)

    conn = get_conn()
    c = conn.cursor()

    c.execute("""
        INSERT INTO dividas (
            descricao, banco, categoria, valor_total, parcelas, parcela_atual,
            valor_parcela, data_primeira_parcela, observacao, grupo_parcelamento
        )
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    """, (
        descricao, banco, categoria, valor_total, parcelas, 1,
        valor_parcela, data_primeira_parcela, observacao, grupo
    ))
    conn.commit()
    conn.close()

    # Gera parcelas futuras em lançamentos
    for i in range(parcelas):
        data_parcela = to_date(data_primeira_parcela) + relativedelta(months=i)
        desc = f"{descricao} ({i+1}/{parcelas})"
        add_lancamento(
            data=data_parcela.isoformat(),
            descricao=desc,
            tipo="Despesa",
            categoria=categoria,
            banco=banco,
            valor=valor_parcela,
            observacao=f"Parcelamento: {descricao}",
            origem="parcelado",
            grupo_parcelamento=grupo
        )

def get_dividas():
    conn = get_conn()
    df = pd.read_sql_query("SELECT * FROM dividas ORDER BY id DESC", conn)
    conn.close()
    return df

def update_divida(divida_id, descricao, banco, categoria, valor_total, parcelas, data_primeira_parcela, observacao):
    """
    Edita a dívida base.
    """
    valor_parcela = round(valor_total / parcelas, 2)

    conn = get_conn()
    c = conn.cursor()

    # buscar grupo
    row = c.execute("SELECT grupo_parcelamento FROM dividas WHERE id=?", (divida_id,)).fetchone()
    if not row:
        conn.close()
        return

    grupo = row[0]

    c.execute("""
        UPDATE dividas
        SET descricao=?, banco=?, categoria=?, valor_total=?, parcelas=?,
            valor_parcela=?, data_primeira_parcela=?, observacao=?
        WHERE id=?
    """, (
        descricao, banco, categoria, valor_total, parcelas,
        valor_parcela, data_primeira_parcela, observacao, divida_id
    ))

    conn.commit()
    conn.close()

def delete_divida(divida_id):
    conn = get_conn()
    c = conn.cursor()

    row = c.execute("SELECT grupo_parcelamento FROM dividas WHERE id=?", (divida_id,)).fetchone()
    if row:
        grupo = row[0]
        c.execute("DELETE FROM lancamentos WHERE grupo_parcelamento=?", (grupo,))

    c.execute("DELETE FROM dividas WHERE id=?", (divida_id,))
    conn.commit()
    conn.close()

def rebuild_parcelamento_completo(divida_id, descricao, banco, categoria, valor_total, parcelas, data_primeira_parcela, observacao):
    """
    Edita parcelamento completo:
    - atualiza dívida
    - apaga parcelas antigas
    - recria parcelas futuras
    """
    conn = get_conn()
    c = conn.cursor()

    row = c.execute("SELECT grupo_parcelamento FROM dividas WHERE id=?", (divida_id,)).fetchone()
    if not row:
        conn.close()
        return

    grupo = row[0]

    # remove lançamentos antigos do parcelamento
    c.execute("DELETE FROM lancamentos WHERE grupo_parcelamento=?", (grupo,))

    valor_parcela = round(valor_total / parcelas, 2)

    c.execute("""
        UPDATE dividas
        SET descricao=?, banco=?, categoria=?, valor_total=?, parcelas=?,
            parcela_atual=1, valor_parcela=?, data_primeira_parcela=?, observacao=?
        WHERE id=?
    """, (
        descricao, banco, categoria, valor_total, parcelas,
        valor_parcela, data_primeira_parcela, observacao, divida_id
    ))

    conn.commit()
    conn.close()

    # recria parcelas
    for i in range(parcelas):
        data_parcela = to_date(data_primeira_parcela) + relativedelta(months=i)
        desc = f"{descricao} ({i+1}/{parcelas})"
        add_lancamento(
            data=data_parcela.isoformat(),
            descricao=desc,
            tipo="Despesa",
            categoria=categoria,
            banco=banco,
            valor=valor_parcela,
            observacao=f"Parcelamento: {descricao}",
            origem="parcelado",
            grupo_parcelamento=grupo
        )

# =========================================================
# CÁLCULOS
# =========================================================
def calc_resumo(df):
    receitas = df[df["tipo"] == "Receita"]["valor"].sum() if not df.empty else 0
    despesas = df[df["tipo"] == "Despesa"]["valor"].sum() if not df.empty else 0
    saldo = receitas - despesas
    return receitas, despesas, saldo

def calc_saldo_por_banco(df):
    if df.empty:
        return pd.DataFrame(columns=["banco", "receitas", "despesas", "saldo"])

    receitas = df[df["tipo"] == "Receita"].groupby("banco")["valor"].sum().reset_index()
    receitas.columns = ["banco", "receitas"]

    despesas = df[df["tipo"] == "Despesa"].groupby("banco")["valor"].sum().reset_index()
    despesas.columns = ["banco", "despesas"]

    merged = pd.merge(receitas, despesas, on="banco", how="outer").fillna(0)
    merged["saldo"] = merged["receitas"] - merged["despesas"]
    merged = merged.sort_values("saldo", ascending=False)
    return merged

def calc_categoria_despesas(df):
    if df.empty:
        return pd.DataFrame(columns=["categoria", "valor"])
    d = df[df["tipo"] == "Despesa"].groupby("categoria")["valor"].sum().reset_index()
    d = d.sort_values("valor", ascending=False)
    return d

# =========================================================
# UI COMPONENTS
# =========================================================
def header():
    st.markdown("""
    <div class="title-card">
        <h1 style="margin:0;">💸 Finançasapp</h1>
        <p style="margin:0.35rem 0 0 0; opacity:0.9;">
            Controle completo de lançamentos, parcelamentos, dívidas e saldos por banco/cartão
        </p>
    </div>
    """, unsafe_allow_html=True)

def form_novo_lancamento():
    with st.expander("➕ Novo lançamento", expanded=False):
        with st.form("form_lancamento"):
            c1, c2 = st.columns(2)
            with c1:
                data_lanc = st.date_input("Data", value=date.today())
                descricao = st.text_input("Descrição")
                tipo = st.selectbox("Tipo", TIPOS)
                categoria = st.selectbox("Categoria", CATEGORIAS)
            with c2:
                banco = st.selectbox("Banco/Cartão", BANCOS)
                valor = st.number_input("Valor", min_value=0.0, step=0.01, format="%.2f")
                observacao = st.text_area("Observação", height=100)

            submitted = st.form_submit_button("Salvar lançamento", use_container_width=True)
            if submitted:
                if not descricao.strip():
                    st.warning("Informe a descrição.")
                elif valor <= 0:
                    st.warning("Informe um valor maior que zero.")
                else:
                    add_lancamento(
                        data_lanc.isoformat(),
                        descricao.strip(),
                        tipo,
                        categoria,
                        banco,
                        float(valor),
                        observacao.strip()
                    )
                    st.success("Lançamento salvo com sucesso!")
                    st.rerun()

def form_nova_divida():
    with st.expander("💳 Nova dívida / parcelamento", expanded=False):
        with st.form("form_divida"):
            c1, c2 = st.columns(2)

            with c1:
                descricao = st.text_input("Descrição da compra / dívida")
                banco = st.selectbox("Banco/Cartão da dívida", BANCOS, key="div_banco")
                categoria = st.selectbox("Categoria da dívida", CATEGORIAS, key="div_cat")

            with c2:
                valor_total = st.number_input("Valor total", min_value=0.0, step=0.01, format="%.2f", key="div_valor")
                parcelas = st.number_input("Quantidade de parcelas", min_value=1, max_value=120, step=1, value=1)
                data_primeira = st.date_input("Data da 1ª parcela", value=date.today(), key="div_data")

            observacao = st.text_area("Observação", height=100, key="div_obs")

            submitted = st.form_submit_button("Salvar dívida / parcelamento", use_container_width=True)
            if submitted:
                if not descricao.strip():
                    st.warning("Informe a descrição.")
                elif valor_total <= 0:
                    st.warning("Informe um valor total maior que zero.")
                else:
                    add_divida(
                        descricao=descricao.strip(),
                        banco=banco,
                        categoria=categoria,
                        valor_total=float(valor_total),
                        parcelas=int(parcelas),
                        data_primeira_parcela=data_primeira.isoformat(),
                        observacao=observacao.strip()
                    )
                    st.success("Dívida/parcelamento salvo com sucesso!")
                    st.rerun()

def render_metricas(df_periodo):
    receitas, despesas, saldo = calc_resumo(df_periodo)

    c1, c2, c3 = st.columns(3)
    with c1:
        st.markdown('<div class="metric-card">', unsafe_allow_html=True)
        st.metric("💰 Receitas", br_money(receitas))
        st.markdown('</div>', unsafe_allow_html=True)

    with c2:
        st.markdown('<div class="metric-card">', unsafe_allow_html=True)
        st.metric("💸 Despesas", br_money(despesas))
        st.markdown('</div>', unsafe_allow_html=True)

    with c3:
        st.markdown('<div class="metric-card">', unsafe_allow_html=True)
        st.metric("📊 Saldo", br_money(saldo))
        st.markdown('</div>', unsafe_allow_html=True)

def render_saldo_bancos(df_periodo):
    st.markdown("### 🏦 Saldo por banco/cartão")
    saldos = calc_saldo_por_banco(df_periodo)

    if saldos.empty:
        st.info("Sem dados no período para exibir saldos por banco/cartão.")
        return

    for _, row in saldos.iterrows():
        with st.container():
            st.markdown('<div class="section-card">', unsafe_allow_html=True)
            c1, c2, c3, c4 = st.columns([2.2, 1, 1, 1])
            c1.markdown(f"**{row['banco']}**")
            c2.markdown(f"Receitas: **{br_money(row['receitas'])}**")
            c3.markdown(f"Despesas: **{br_money(row['despesas'])}**")
            c4.markdown(f"Saldo: **{br_money(row['saldo'])}**")
            st.markdown('</div>', unsafe_allow_html=True)

def render_lancamentos(df_periodo):
    st.markdown("### 📋 Lançamentos do período")

    if df_periodo.empty:
        st.info("Nenhum lançamento encontrado no período.")
        return

    for _, row in df_periodo.iterrows():
        lanc_id = int(row["id"])
        edit_key = f"edit_lanc_{lanc_id}"

        if edit_key not in st.session_state:
            st.session_state[edit_key] = False

        st.markdown('<div class="launch-row">', unsafe_allow_html=True)
        c1, c2, c3 = st.columns([7, 1, 1])

        with c1:
            st.markdown(
                f"**{row['descricao']}**  \n"
                f"<span class='small-muted'>{row['data']} • {row['tipo']} • {row['categoria']} • {row['banco']}</span>  \n"
                f"**{br_money(row['valor'])}**",
                unsafe_allow_html=True
            )

        with c2:
            if st.button("✏️", key=f"btn_edit_l_{lanc_id}", use_container_width=True):
                st.session_state[edit_key] = not st.session_state[edit_key]

        with c3:
            if st.button("🗑️", key=f"btn_del_l_{lanc_id}", use_container_width=True):
                delete_lancamento(lanc_id)
                st.success("Lançamento excluído.")
                st.rerun()

        st.markdown('</div>', unsafe_allow_html=True)

        if st.session_state[edit_key]:
            with st.expander(f"Editar lançamento #{lanc_id}", expanded=True):
                with st.form(f"form_edit_l_{lanc_id}"):
                    ec1, ec2 = st.columns(2)
                    with ec1:
                        nova_data = st.date_input("Data", value=to_date(row["data"]), key=f"ed_data_{lanc_id}")
                        nova_desc = st.text_input("Descrição", value=row["descricao"], key=f"ed_desc_{lanc_id}")
                        novo_tipo = st.selectbox("Tipo", TIPOS, index=TIPOS.index(row["tipo"]), key=f"ed_tipo_{lanc_id}")
                        nova_cat = st.selectbox("Categoria", CATEGORIAS, index=CATEGORIAS.index(row["categoria"]) if row["categoria"] in CATEGORIAS else len(CATEGORIAS)-1, key=f"ed_cat_{lanc_id}")
                    with ec2:
                        novo_banco = st.selectbox("Banco", BANCOS, index=BANCOS.index(row["banco"]) if row["banco"] in BANCOS else 0, key=f"ed_banco_{lanc_id}")
                        novo_valor = st.number_input("Valor", min_value=0.0, value=float(row["valor"]), step=0.01, format="%.2f", key=f"ed_valor_{lanc_id}")
                        nova_obs = st.text_area("Observação", value=row["observacao"] if pd.notna(row["observacao"]) else "", key=f"ed_obs_{lanc_id}")

                    s1, s2 = st.columns(2)
                    with s1:
                        salvar = st.form_submit_button("Salvar alterações", use_container_width=True)
                    with s2:
                        cancelar = st.form_submit_button("Cancelar", use_container_width=True)

                    if salvar:
                        update_lancamento(
                            lanc_id=lanc_id,
                            data=nova_data.isoformat(),
                            descricao=nova_desc.strip(),
                            tipo=novo_tipo,
                            categoria=nova_cat,
                            banco=novo_banco,
                            valor=float(novo_valor),
                            observacao=nova_obs.strip()
                        )
                        st.session_state[edit_key] = False
                        st.success("Lançamento atualizado.")
                        st.rerun()

                    if cancelar:
                        st.session_state[edit_key] = False
                        st.rerun()

def render_dividas():
    st.markdown("### 💳 Dívidas / Parcelamentos")

    df = get_dividas()
    if df.empty:
        st.info("Nenhuma dívida/parcelamento cadastrado.")
        return

    for _, row in df.iterrows():
        div_id = int(row["id"])
        edit_key = f"edit_div_{div_id}"
        rebuild_key = f"rebuild_div_{div_id}"

        if edit_key not in st.session_state:
            st.session_state[edit_key] = False
        if rebuild_key not in st.session_state:
            st.session_state[rebuild_key] = False

        parcelas = int(row["parcelas"])
        valor_total = float(row["valor_total"])
        valor_parcela = float(row["valor_parcela"])

        st.markdown('<div class="launch-row">', unsafe_allow_html=True)
        c1, c2, c3, c4 = st.columns([6, 1, 1, 1])

        with c1:
            st.markdown(
                f"**{row['descricao']}**  \n"
                f"<span class='small-muted'>{row['banco']} • {row['categoria']} • {parcelas}x de {br_money(valor_parcela)}</span>  \n"
                f"**Total: {br_money(valor_total)}**",
                unsafe_allow_html=True
            )

        with c2:
            if st.button("✏️", key=f"btn_edit_d_{div_id}", use_container_width=True):
                st.session_state[edit_key] = not st.session_state[edit_key]

        with c3:
            if st.button("🔁", key=f"btn_rebuild_d_{div_id}", use_container_width=True):
                st.session_state[rebuild_key] = not st.session_state[rebuild_key]

        with c4:
            if st.button("🗑️", key=f"btn_del_d_{div_id}", use_container_width=True):
                delete_divida(div_id)
                st.success("Dívida/parcelamento excluído (incluindo parcelas futuras).")
                st.rerun()

        st.markdown('</div>', unsafe_allow_html=True)

        # Edita somente o registro da dívida
        if st.session_state[edit_key]:
            with st.expander(f"Editar dívida #{div_id}", expanded=True):
                with st.form(f"form_edit_d_{div_id}"):
                    ec1, ec2 = st.columns(2)
                    with ec1:
                        nova_desc = st.text_input("Descrição", value=row["descricao"], key=f"div_desc_{div_id}")
                        novo_banco = st.selectbox("Banco", BANCOS, index=BANCOS.index(row["banco"]) if row["banco"] in BANCOS else 0, key=f"div_banco_{div_id}")
                        nova_cat = st.selectbox("Categoria", CATEGORIAS, index=CATEGORIAS.index(row["categoria"]) if row["categoria"] in CATEGORIAS else len(CATEGORIAS)-1, key=f"div_cat_{div_id}")
                    with ec2:
                        novo_total = st.number_input("Valor total", min_value=0.0, value=float(row["valor_total"]), step=0.01, format="%.2f", key=f"div_total_{div_id}")
                        novas_parcelas = st.number_input("Parcelas", min_value=1, max_value=120, value=int(row["parcelas"]), step=1, key=f"div_parc_{div_id}")
                        nova_data = st.date_input("1ª parcela", value=to_date(row["data_primeira_parcela"]), key=f"div_data_{div_id}")

                    nova_obs = st.text_area("Observação", value=row["observacao"] if pd.notna(row["observacao"]) else "", key=f"div_obs_{div_id}")

                    s1, s2 = st.columns(2)
                    with s1:
                        salvar = st.form_submit_button("Salvar dívida", use_container_width=True)
                    with s2:
                        cancelar = st.form_submit_button("Cancelar", use_container_width=True)

                    if salvar:
                        update_divida(
                            divida_id=div_id,
                            descricao=nova_desc.strip(),
                            banco=novo_banco,
                            categoria=nova_cat,
                            valor_total=float(novo_total),
                            parcelas=int(novas_parcelas),
                            data_primeira_parcela=nova_data.isoformat(),
                            observacao=nova_obs.strip()
                        )
                        st.session_state[edit_key] = False
                        st.success("Dívida atualizada (sem recriar parcelas).")
                        st.rerun()

                    if cancelar:
                        st.session_state[edit_key] = False
                        st.rerun()

        # Recria parcelamento inteiro
        if st.session_state[rebuild_key]:
            with st.expander(f"Editar parcelamento completo #{div_id}", expanded=True):
                st.warning("⚠️ Isso apaga as parcelas antigas e recria todas do zero.")
                with st.form(f"form_rebuild_d_{div_id}"):
                    ec1, ec2 = st.columns(2)
                    with ec1:
                        nova_desc = st.text_input("Descrição", value=row["descricao"], key=f"rb_desc_{div_id}")
                        novo_banco = st.selectbox("Banco", BANCOS, index=BANCOS.index(row["banco"]) if row["banco"] in BANCOS else 0, key=f"rb_banco_{div_id}")
                        nova_cat = st.selectbox("Categoria", CATEGORIAS, index=CATEGORIAS.index(row["categoria"]) if row["categoria"] in CATEGORIAS else len(CATEGORIAS)-1, key=f"rb_cat_{div_id}")
                    with ec2:
                        novo_total = st.number_input("Valor total", min_value=0.0, value=float(row["valor_total"]), step=0.01, format="%.2f", key=f"rb_total_{div_id}")
                        novas_parcelas = st.number_input("Parcelas", min_value=1, max_value=120, value=int(row["parcelas"]), step=1, key=f"rb_parc_{div_id}")
                        nova_data = st.date_input("1ª parcela", value=to_date(row["data_primeira_parcela"]), key=f"rb_data_{div_id}")

                    nova_obs = st.text_area("Observação", value=row["observacao"] if pd.notna(row["observacao"]) else "", key=f"rb_obs_{div_id}")

                    s1, s2 = st.columns(2)
                    with s1:
                        salvar = st.form_submit_button("Recriar parcelamento completo", use_container_width=True)
                    with s2:
                        cancelar = st.form_submit_button("Cancelar", use_container_width=True)

                    if salvar:
                        rebuild_parcelamento_completo(
                            divida_id=div_id,
                            descricao=nova_desc.strip(),
                            banco=novo_banco,
                            categoria=nova_cat,
                            valor_total=float(novo_total),
                            parcelas=int(novas_parcelas),
                            data_primeira_parcela=nova_data.isoformat(),
                            observacao=nova_obs.strip()
                        )
                        st.session_state[rebuild_key] = False
                        st.success("Parcelamento recriado com sucesso.")
                        st.rerun()

                    if cancelar:
                        st.session_state[rebuild_key] = False
                        st.rerun()

def render_categoria_despesas(df_periodo):
    st.markdown("### 📊 Despesas por categoria")
    cat_df = calc_categoria_despesas(df_periodo)

    if cat_df.empty:
        st.info("Sem despesas no período.")
        return

    chart_df = cat_df.set_index("categoria")
    st.bar_chart(chart_df["valor"])

    st.dataframe(
        cat_df.assign(valor=cat_df["valor"].apply(br_money)),
        use_container_width=True,
        hide_index=True
    )

# =========================================================
# APP
# =========================================================
def main():
    init_db()
    header()

    # Sidebar
    st.sidebar.title("⚙️ Navegação")
    page = st.sidebar.radio(
        "Ir para:",
        ["Dashboard", "Lançamentos", "Dívidas / Parcelamentos"]
    )

    if page == "Dashboard":
        start, end = get_period_filter()
        if not start or not end:
            return

        df_periodo = get_lancamentos_periodo(start, end)

        st.markdown(f"#### Período selecionado: **{start.strftime('%d/%m/%Y')}** até **{end.strftime('%d/%m/%Y')}**")
        render_metricas(df_periodo)
        st.markdown("---")
        render_saldo_bancos(df_periodo)
        st.markdown("---")
        render_categoria_despesas(df_periodo)
        st.markdown("---")
        render_lancamentos(df_periodo)

    elif page == "Lançamentos":
        form_novo_lancamento()
        st.markdown("---")
        start, end = get_period_filter()
        if not start or not end:
            return
        df_periodo = get_lancamentos_periodo(start, end)
        render_metricas(df_periodo)
        st.markdown("---")
        render_lancamentos(df_periodo)

    elif page == "Dívidas / Parcelamentos":
        form_nova_divida()
        st.markdown("---")
        render_dividas()

if __name__ == "__main__":
    main()
