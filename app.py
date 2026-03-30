import streamlit as st
import sqlite3
import pandas as pd
from datetime import datetime, date
import plotly.express as px
from dateutil.relativedelta import relativedelta

# =========================================================
# CONFIG
# =========================================================
DB_NAME = "financeiro.db"

st.set_page_config(
    page_title="Financeiro Pessoal V3",
    page_icon="💰",
    layout="wide",
    initial_sidebar_state="collapsed"
)

# =========================================================
# CSS (MOBILE + VISUAL MELHORADO)
# =========================================================
st.markdown("""
<style>
    .main > div {
        padding-top: 1rem;
        padding-bottom: 3rem;
    }

    .block-container {
        padding-top: 1rem !important;
        padding-bottom: 4rem !important;
        padding-left: 0.8rem !important;
        padding-right: 0.8rem !important;
        max-width: 1200px;
    }

    h1, h2, h3 {
        letter-spacing: -0.5px;
    }

    .card-metric {
        background: linear-gradient(135deg, #111827 0%, #1f2937 100%);
        padding: 1rem;
        border-radius: 18px;
        border: 1px solid rgba(255,255,255,0.08);
        box-shadow: 0 8px 25px rgba(0,0,0,0.12);
        margin-bottom: 0.8rem;
    }

    .card-light {
        background: rgba(255,255,255,0.03);
        padding: 0.9rem;
        border-radius: 16px;
        border: 1px solid rgba(255,255,255,0.06);
        margin-bottom: 0.6rem;
    }

    .small-label {
        font-size: 0.8rem;
        opacity: 0.75;
        margin-bottom: 0.2rem;
    }

    .big-number {
        font-size: 1.4rem;
        font-weight: 700;
    }

    .launch-card {
        background: rgba(255,255,255,0.02);
        border: 1px solid rgba(255,255,255,0.06);
        border-radius: 16px;
        padding: 0.8rem;
        margin-bottom: 0.7rem;
    }

    .divider-soft {
        height: 1px;
        background: rgba(255,255,255,0.06);
        margin: 0.7rem 0;
        border-radius: 999px;
    }

    @media (max-width: 768px) {
        .block-container {
            padding-left: 0.5rem !important;
            padding-right: 0.5rem !important;
        }
    }
</style>
""", unsafe_allow_html=True)

# =========================================================
# DB HELPERS
# =========================================================
def get_conn():
    return sqlite3.connect(DB_NAME, check_same_thread=False)

def execute(query, params=()):
    conn = get_conn()
    cur = conn.cursor()
    cur.execute(query, params)
    conn.commit()
    conn.close()

def fetch_all(query, params=()):
    conn = get_conn()
    df = pd.read_sql_query(query, conn, params=params)
    conn.close()
    return df

def init_db():
    conn = get_conn()
    cur = conn.cursor()

    cur.execute("""
    CREATE TABLE IF NOT EXISTS contas (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        nome TEXT NOT NULL,
        tipo TEXT NOT NULL
    )
    """)

    cur.execute("""
    CREATE TABLE IF NOT EXISTS lancamentos (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        data TEXT NOT NULL,
        descricao TEXT NOT NULL,
        valor REAL NOT NULL,
        tipo TEXT NOT NULL,
        categoria TEXT,
        conta_id INTEGER,
        forma_pagamento TEXT,
        observacao TEXT,
        parcelamento_id INTEGER,
        parcela_atual INTEGER,
        total_parcelas INTEGER,
        FOREIGN KEY (conta_id) REFERENCES contas(id)
    )
    """)

    cur.execute("""
    CREATE TABLE IF NOT EXISTS dividas (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        descricao TEXT NOT NULL,
        valor_total REAL NOT NULL,
        valor_pago REAL NOT NULL DEFAULT 0,
        vencimento TEXT,
        status TEXT NOT NULL DEFAULT 'Aberta',
        conta_id INTEGER,
        observacao TEXT,
        FOREIGN KEY (conta_id) REFERENCES contas(id)
    )
    """)

    cur.execute("""
    CREATE TABLE IF NOT EXISTS parcelamentos (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        descricao TEXT NOT NULL,
        valor_total REAL NOT NULL,
        valor_parcela REAL NOT NULL,
        total_parcelas INTEGER NOT NULL,
        parcelas_lancadas INTEGER NOT NULL DEFAULT 0,
        data_primeira_parcela TEXT NOT NULL,
        categoria TEXT,
        conta_id INTEGER,
        observacao TEXT,
        ativo INTEGER NOT NULL DEFAULT 1,
        FOREIGN KEY (conta_id) REFERENCES contas(id)
    )
    """)

    conn.commit()
    conn.close()

    seed_contas()

def seed_contas():
    df = fetch_all("SELECT * FROM contas")
    if df.empty:
        contas_padrao = [
            ("Nubank", "Banco"),
            ("Inter", "Banco"),
            ("Caixa", "Banco"),
            ("Cartão Nubank", "Cartão"),
            ("Cartão Inter", "Cartão")
        ]
        for nome, tipo in contas_padrao:
            execute("INSERT INTO contas (nome, tipo) VALUES (?, ?)", (nome, tipo))

# =========================================================
# UTILITÁRIOS
# =========================================================
def br_money(v):
    try:
        return f"R$ {v:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")
    except:
        return "R$ 0,00"

def to_date_str(d):
    if isinstance(d, str):
        return d
    return d.strftime("%Y-%m-%d")

def parse_date(d):
    if isinstance(d, date):
        return d
    return datetime.strptime(d, "%Y-%m-%d").date()

def get_month_range(year, month):
    start = date(year, month, 1)
    if month == 12:
        end = date(year + 1, 1, 1) - relativedelta(days=1)
    else:
        end = date(year, month + 1, 1) - relativedelta(days=1)
    return start, end

def get_contas():
    return fetch_all("SELECT * FROM contas ORDER BY tipo, nome")

def get_conta_map():
    contas = get_contas()
    if contas.empty:
        return {}
    return dict(zip(contas["id"], contas["nome"]))

def get_conta_options():
    contas = get_contas()
    if contas.empty:
        return {}
    return {f"{row['nome']} ({row['tipo']})": row["id"] for _, row in contas.iterrows()}

# =========================================================
# QUERIES / REPOSITÓRIO
# =========================================================
def get_lancamentos():
    return fetch_all("""
        SELECT l.*, c.nome as conta_nome, c.tipo as conta_tipo
        FROM lancamentos l
        LEFT JOIN contas c ON l.conta_id = c.id
        ORDER BY date(l.data) DESC, l.id DESC
    """)

def get_dividas():
    return fetch_all("""
        SELECT d.*, c.nome as conta_nome, c.tipo as conta_tipo
        FROM dividas d
        LEFT JOIN contas c ON d.conta_id = c.id
        ORDER BY d.status, date(d.vencimento) ASC
    """)

def get_parcelamentos():
    return fetch_all("""
        SELECT p.*, c.nome as conta_nome, c.tipo as conta_tipo
        FROM parcelamentos p
        LEFT JOIN contas c ON p.conta_id = c.id
        ORDER BY p.ativo DESC, p.id DESC
    """)

def filtrar_lancamentos(df, filtro_tipo, mes_ano, periodo_inicio, periodo_fim):
    if df.empty:
        return df

    df = df.copy()
    df["data_dt"] = pd.to_datetime(df["data"])

    if filtro_tipo == "Mês":
        if mes_ano:
            y, m = map(int, mes_ano.split("-"))
            inicio, fim = get_month_range(y, m)
            df = df[(df["data_dt"].dt.date >= inicio) & (df["data_dt"].dt.date <= fim)]
    elif filtro_tipo == "Período":
        if periodo_inicio and periodo_fim:
            df = df[(df["data_dt"].dt.date >= periodo_inicio) & (df["data_dt"].dt.date <= periodo_fim)]

    return df.drop(columns=["data_dt"], errors="ignore")

def gerar_parcelas_futuras(parcelamento_id):
    p = fetch_all("SELECT * FROM parcelamentos WHERE id = ?", (parcelamento_id,))
    if p.empty:
        return

    p = p.iloc[0]
    if p["ativo"] != 1:
        return

    # remove parcelas antigas deste parcelamento para recriar tudo limpo
    execute("DELETE FROM lancamentos WHERE parcelamento_id = ?", (parcelamento_id,))

    data_base = parse_date(p["data_primeira_parcela"])

    for i in range(1, int(p["total_parcelas"]) + 1):
        data_parcela = data_base + relativedelta(months=i - 1)
        execute("""
            INSERT INTO lancamentos (
                data, descricao, valor, tipo, categoria, conta_id, forma_pagamento,
                observacao, parcelamento_id, parcela_atual, total_parcelas
            )
            VALUES (?, ?, ?, 'Despesa', ?, ?, 'Cartão', ?, ?, ?, ?)
        """, (
            to_date_str(data_parcela),
            p["descricao"],
            float(p["valor_parcela"]),
            p["categoria"],
            int(p["conta_id"]) if pd.notna(p["conta_id"]) else None,
            p["observacao"],
            int(parcelamento_id),
            i,
            int(p["total_parcelas"])
        ))

    execute("""
        UPDATE parcelamentos
        SET parcelas_lancadas = ?
        WHERE id = ?
    """, (int(p["total_parcelas"]), parcelamento_id))

# =========================================================
# COMPONENTES UI
# =========================================================
def section_title(title, emoji=""):
    st.markdown(f"## {emoji} {title}")

def metric_card(label, value):
    st.markdown(f"""
    <div class="card-metric">
        <div class="small-label">{label}</div>
        <div class="big-number">{value}</div>
    </div>
    """, unsafe_allow_html=True)

# =========================================================
# FORMS
# =========================================================
def form_novo_lancamento():
    with st.expander("➕ Novo lançamento", expanded=False):
        contas_options = get_conta_options()
        col1, col2 = st.columns(2)

        with col1:
            data_l = st.date_input("Data", value=date.today(), key="novo_lanc_data")
            descricao = st.text_input("Descrição", key="novo_lanc_desc")
            valor = st.number_input("Valor", min_value=0.0, step=0.01, format="%.2f", key="novo_lanc_valor")
            tipo = st.selectbox("Tipo", ["Receita", "Despesa"], key="novo_lanc_tipo")

        with col2:
            categoria = st.text_input("Categoria", key="novo_lanc_cat")
            conta_nome = st.selectbox("Conta / Banco / Cartão", list(contas_options.keys()), key="novo_lanc_conta")
            forma = st.selectbox("Forma de pagamento", ["Pix", "Débito", "Crédito", "Dinheiro", "Transferência", "Boleto", "Outro"], key="novo_lanc_forma")
            observacao = st.text_area("Observação", key="novo_lanc_obs")

        if st.button("Salvar lançamento", use_container_width=True):
            if not descricao.strip() or valor <= 0:
                st.warning("Preencha descrição e valor corretamente.")
            else:
                conta_id = contas_options.get(conta_nome)
                execute("""
                    INSERT INTO lancamentos (
                        data, descricao, valor, tipo, categoria, conta_id, forma_pagamento, observacao
                    )
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """, (
                    to_date_str(data_l), descricao.strip(), float(valor), tipo, categoria.strip(),
                    conta_id, forma, observacao.strip()
                ))
                st.success("Lançamento salvo com sucesso!")
                st.rerun()

def form_nova_divida():
    with st.expander("📌 Nova dívida", expanded=False):
        contas_options = get_conta_options()
        col1, col2 = st.columns(2)

        with col1:
            descricao = st.text_input("Descrição da dívida", key="div_desc")
            valor_total = st.number_input("Valor total", min_value=0.0, step=0.01, format="%.2f", key="div_total")
            valor_pago = st.number_input("Valor já pago", min_value=0.0, step=0.01, format="%.2f", key="div_pago")

        with col2:
            vencimento = st.date_input("Vencimento", value=date.today(), key="div_venc")
            conta_nome = st.selectbox("Conta relacionada", list(contas_options.keys()), key="div_conta")
            observacao = st.text_area("Observação", key="div_obs")

        if st.button("Salvar dívida", use_container_width=True):
            if not descricao.strip() or valor_total <= 0:
                st.warning("Preencha a descrição e o valor total.")
            else:
                conta_id = contas_options.get(conta_nome)
                status = "Quitada" if valor_pago >= valor_total else "Aberta"
                execute("""
                    INSERT INTO dividas (
                        descricao, valor_total, valor_pago, vencimento, status, conta_id, observacao
                    )
                    VALUES (?, ?, ?, ?, ?, ?, ?)
                """, (
                    descricao.strip(), float(valor_total), float(valor_pago),
                    to_date_str(vencimento), status, conta_id, observacao.strip()
                ))
                st.success("Dívida salva com sucesso!")
                st.rerun()

def form_novo_parcelamento():
    with st.expander("💳 Novo parcelamento no cartão", expanded=False):
        contas = get_contas()
        cartoes = contas[contas["tipo"] == "Cartão"]
        if cartoes.empty:
            st.warning("Cadastre pelo menos uma conta do tipo Cartão.")
            return

        opcoes_cartao = {f"{row['nome']} ({row['tipo']})": row["id"] for _, row in cartoes.iterrows()}

        col1, col2 = st.columns(2)

        with col1:
            descricao = st.text_input("Descrição da compra parcelada", key="parc_desc")
            valor_total = st.number_input("Valor total da compra", min_value=0.0, step=0.01, format="%.2f", key="parc_total")
            total_parcelas = st.number_input("Número de parcelas", min_value=2, step=1, key="parc_n")

        with col2:
            data_primeira = st.date_input("Data da 1ª parcela", value=date.today(), key="parc_data")
            categoria = st.text_input("Categoria", key="parc_cat")
            cartao_nome = st.selectbox("Cartão", list(opcoes_cartao.keys()), key="parc_cartao")
            observacao = st.text_area("Observação", key="parc_obs")

        if st.button("Salvar parcelamento", use_container_width=True):
            if not descricao.strip() or valor_total <= 0 or total_parcelas < 2:
                st.warning("Preencha corretamente os dados do parcelamento.")
            else:
                valor_parcela = float(valor_total) / int(total_parcelas)
                conta_id = opcoes_cartao.get(cartao_nome)

                conn = get_conn()
                cur = conn.cursor()
                cur.execute("""
                    INSERT INTO parcelamentos (
                        descricao, valor_total, valor_parcela, total_parcelas,
                        parcelas_lancadas, data_primeira_parcela, categoria, conta_id,
                        observacao, ativo
                    )
                    VALUES (?, ?, ?, ?, 0, ?, ?, ?, ?, 1)
                """, (
                    descricao.strip(),
                    float(valor_total),
                    valor_parcela,
                    int(total_parcelas),
                    to_date_str(data_primeira),
                    categoria.strip(),
                    conta_id,
                    observacao.strip()
                ))
                parcelamento_id = cur.lastrowid
                conn.commit()
                conn.close()

                gerar_parcelas_futuras(parcelamento_id)
                st.success("Parcelamento salvo com todas as parcelas futuras!")
                st.rerun()

# =========================================================
# DASHBOARD
# =========================================================
def render_dashboard():
    section_title("Resumo Financeiro", "📊")

    df = get_lancamentos()
    if df.empty:
        st.info("Ainda não há lançamentos cadastrados.")
        return

    receitas = df[df["tipo"] == "Receita"]["valor"].sum()
    despesas = df[df["tipo"] == "Despesa"]["valor"].sum()
    saldo = receitas - despesas

    c1, c2, c3 = st.columns(3)
    with c1:
        metric_card("Receitas", br_money(receitas))
    with c2:
        metric_card("Despesas", br_money(despesas))
    with c3:
        metric_card("Saldo", br_money(saldo))

    st.markdown("### 💳 Saldo por banco/cartão")

    if not df.empty:
        agrupado = df.groupby(["conta_nome", "tipo"])["valor"].sum().reset_index()
        # saldo por conta: receita positiva, despesa negativa
        df_aux = df.copy()
        df_aux["valor_sinal"] = df_aux.apply(lambda x: x["valor"] if x["tipo"] == "Receita" else -x["valor"], axis=1)
        saldo_conta = df_aux.groupby("conta_nome")["valor_sinal"].sum().reset_index().sort_values("valor_sinal", ascending=False)

        if not saldo_conta.empty:
            for _, row in saldo_conta.iterrows():
                st.markdown(f"""
                <div class="card-light">
                    <b>{row['conta_nome']}</b><br>
                    Saldo: <b>{br_money(row['valor_sinal'])}</b>
                </div>
                """, unsafe_allow_html=True)

            fig = px.bar(
                saldo_conta,
                x="conta_nome",
                y="valor_sinal",
                title="Saldo por conta"
            )
            fig.update_layout(height=350, margin=dict(l=10, r=10, t=50, b=10))
            st.plotly_chart(fig, use_container_width=True)

    st.markdown("### 📈 Despesas por categoria")
    despesas_df = df[df["tipo"] == "Despesa"]
    if not despesas_df.empty and despesas_df["categoria"].notna().any():
        cat = despesas_df.groupby("categoria")["valor"].sum().reset_index()
        fig = px.pie(cat, names="categoria", values="valor")
        fig.update_layout(height=380, margin=dict(l=10, r=10, t=10, b=10))
        st.plotly_chart(fig, use_container_width=True)
    else:
        st.info("Sem despesas por categoria para exibir.")

# =========================================================
# LANÇAMENTOS
# =========================================================
def render_lancamentos():
    section_title("Lançamentos", "🧾")

    form_novo_lancamento()

    df = get_lancamentos()
    if df.empty:
        st.info("Nenhum lançamento cadastrado.")
        return

    st.markdown("### 🔎 Filtros")
    c1, c2, c3 = st.columns([1,1,1])

    with c1:
        filtro_tipo = st.selectbox("Filtrar por", ["Todos", "Mês", "Período"], key="filtro_lanc_tipo")

    mes_ano = None
    periodo_inicio = None
    periodo_fim = None

    with c2:
        if filtro_tipo == "Mês":
            hoje = date.today()
            mes_ano = st.text_input("Mês (YYYY-MM)", value=hoje.strftime("%Y-%m"), key="filtro_mes")
        elif filtro_tipo == "Período":
            periodo_inicio = st.date_input("Data inicial", value=date.today().replace(day=1), key="filtro_inicio")

    with c3:
        if filtro_tipo == "Período":
            periodo_fim = st.date_input("Data final", value=date.today(), key="filtro_fim")

    df_filtrado = filtrar_lancamentos(df, filtro_tipo, mes_ano, periodo_inicio, periodo_fim)

    receitas = df_filtrado[df_filtrado["tipo"] == "Receita"]["valor"].sum()
    despesas = df_filtrado[df_filtrado["tipo"] == "Despesa"]["valor"].sum()
    saldo = receitas - despesas

    mc1, mc2, mc3 = st.columns(3)
    with mc1:
        metric_card("Receitas filtradas", br_money(receitas))
    with mc2:
        metric_card("Despesas filtradas", br_money(despesas))
    with mc3:
        metric_card("Saldo filtrado", br_money(saldo))

    st.markdown("### 📋 Lista de lançamentos")

    contas_options = get_conta_options()
    conta_reverse = {v: k for k, v in contas_options.items()}

    for _, row in df_filtrado.iterrows():
        with st.container():
            c1, c2 = st.columns([6, 1])

            with c1:
                parcela_txt = ""
                if pd.notna(row["parcelamento_id"]) and pd.notna(row["parcela_atual"]) and pd.notna(row["total_parcelas"]):
                    parcela_txt = f" | Parcela {int(row['parcela_atual'])}/{int(row['total_parcelas'])}"

                st.markdown(f"""
                <div class="launch-card">
                    <b>{row['descricao']}</b><br>
                    {row['data']} | {row['tipo']} | <b>{br_money(row['valor'])}</b><br>
                    Categoria: {row['categoria'] if pd.notna(row['categoria']) else '-'}<br>
                    Conta: {row['conta_nome'] if pd.notna(row['conta_nome']) else '-'}{parcela_txt}
                </div>
                """, unsafe_allow_html=True)

            with c2:
                if st.button("✏️", key=f"edit_lanc_btn_{row['id']}", use_container_width=True):
                    st.session_state[f"edit_lanc_open_{row['id']}"] = not st.session_state.get(f"edit_lanc_open_{row['id']}", False)

            if st.session_state.get(f"edit_lanc_open_{row['id']}", False):
                with st.expander(f"Editar lançamento #{row['id']}", expanded=True):
                    colA, colB = st.columns(2)

                    with colA:
                        nova_data = st.date_input(
                            "Data",
                            value=parse_date(row["data"]),
                            key=f"el_data_{row['id']}"
                        )
                        nova_desc = st.text_input(
                            "Descrição",
                            value=row["descricao"],
                            key=f"el_desc_{row['id']}"
                        )
                        novo_valor = st.number_input(
                            "Valor",
                            min_value=0.0,
                            step=0.01,
                            format="%.2f",
                            value=float(row["valor"]),
                            key=f"el_valor_{row['id']}"
                        )

                    with colB:
                        novo_tipo = st.selectbox(
                            "Tipo",
                            ["Receita", "Despesa"],
                            index=0 if row["tipo"] == "Receita" else 1,
                            key=f"el_tipo_{row['id']}"
                        )
                        nova_cat = st.text_input(
                            "Categoria",
                            value=row["categoria"] if pd.notna(row["categoria"]) else "",
                            key=f"el_cat_{row['id']}"
                        )
                        conta_atual_label = conta_reverse.get(row["conta_id"], list(contas_options.keys())[0] if contas_options else None)
                        nova_conta = st.selectbox(
                            "Conta",
                            list(contas_options.keys()),
                            index=list(contas_options.keys()).index(conta_atual_label) if conta_atual_label in list(contas_options.keys()) else 0,
                            key=f"el_conta_{row['id']}"
                        )

                    nova_forma = st.selectbox(
                        "Forma de pagamento",
                        ["Pix", "Débito", "Crédito", "Dinheiro", "Transferência", "Boleto", "Outro"],
                        index=["Pix", "Débito", "Crédito", "Dinheiro", "Transferência", "Boleto", "Outro"].index(row["forma_pagamento"]) if row["forma_pagamento"] in ["Pix", "Débito", "Crédito", "Dinheiro", "Transferência", "Boleto", "Outro"] else 0,
                        key=f"el_forma_{row['id']}"
                    )
                    nova_obs = st.text_area(
                        "Observação",
                        value=row["observacao"] if pd.notna(row["observacao"]) else "",
                        key=f"el_obs_{row['id']}"
                    )

                    b1, b2 = st.columns(2)

                    with b1:
                        if st.button("💾 Salvar", key=f"save_lanc_{row['id']}", use_container_width=True):
                            execute("""
                                UPDATE lancamentos
                                SET data = ?, descricao = ?, valor = ?, tipo = ?, categoria = ?, conta_id = ?, forma_pagamento = ?, observacao = ?
                                WHERE id = ?
                            """, (
                                to_date_str(nova_data), nova_desc.strip(), float(novo_valor), novo_tipo,
                                nova_cat.strip(), contas_options.get(nova_conta), nova_forma, nova_obs.strip(), int(row["id"])
                            ))
                            st.success("Lançamento atualizado!")
                            st.rerun()

                    with b2:
                        if st.button("🗑️ Excluir", key=f"del_lanc_{row['id']}", use_container_width=True):
                            execute("DELETE FROM lancamentos WHERE id = ?", (int(row["id"]),))
                            st.success("Lançamento excluído!")
                            st.rerun()

# =========================================================
# DÍVIDAS
# =========================================================
def render_dividas():
    section_title("Dívidas", "📌")

    form_nova_divida()

    df = get_dividas()
    if df.empty:
        st.info("Nenhuma dívida cadastrada.")
        return

    contas_options = get_conta_options()
    conta_reverse = {v: k for k, v in contas_options.items()}

    for _, row in df.iterrows():
        restante = float(row["valor_total"]) - float(row["valor_pago"])

        c1, c2 = st.columns([6, 1])

        with c1:
            st.markdown(f"""
            <div class="launch-card">
                <b>{row['descricao']}</b><br>
                Total: <b>{br_money(row['valor_total'])}</b> | Pago: <b>{br_money(row['valor_pago'])}</b> | Restante: <b>{br_money(restante)}</b><br>
                Vencimento: {row['vencimento'] if pd.notna(row['vencimento']) else '-'} | Status: <b>{row['status']}</b><br>
                Conta: {row['conta_nome'] if pd.notna(row['conta_nome']) else '-'}
            </div>
            """, unsafe_allow_html=True)

        with c2:
            if st.button("✏️", key=f"edit_div_btn_{row['id']}", use_container_width=True):
                st.session_state[f"edit_div_open_{row['id']}"] = not st.session_state.get(f"edit_div_open_{row['id']}", False)

        if st.session_state.get(f"edit_div_open_{row['id']}", False):
            with st.expander(f"Editar dívida #{row['id']}", expanded=True):
                colA, colB = st.columns(2)

                with colA:
                    nova_desc = st.text_input("Descrição", value=row["descricao"], key=f"ed_desc_{row['id']}")
                    novo_total = st.number_input("Valor total", min_value=0.0, step=0.01, format="%.2f", value=float(row["valor_total"]), key=f"ed_total_{row['id']}")
                    novo_pago = st.number_input("Valor pago", min_value=0.0, step=0.01, format="%.2f", value=float(row["valor_pago"]), key=f"ed_pago_{row['id']}")

                with colB:
                    novo_venc = st.date_input("Vencimento", value=parse_date(row["vencimento"]) if pd.notna(row["vencimento"]) else date.today(), key=f"ed_venc_{row['id']}")
                    conta_atual_label = conta_reverse.get(row["conta_id"], list(contas_options.keys())[0] if contas_options else None)
                    nova_conta = st.selectbox(
                        "Conta",
                        list(contas_options.keys()),
                        index=list(contas_options.keys()).index(conta_atual_label) if conta_atual_label in list(contas_options.keys()) else 0,
                        key=f"ed_conta_{row['id']}"
                    )
                    nova_obs = st.text_area("Observação", value=row["observacao"] if pd.notna(row["observacao"]) else "", key=f"ed_obs_{row['id']}")

                novo_status = "Quitada" if novo_pago >= novo_total and novo_total > 0 else "Aberta"

                b1, b2 = st.columns(2)

                with b1:
                    if st.button("💾 Salvar", key=f"save_div_{row['id']}", use_container_width=True):
                        execute("""
                            UPDATE dividas
                            SET descricao = ?, valor_total = ?, valor_pago = ?, vencimento = ?, status = ?, conta_id = ?, observacao = ?
                            WHERE id = ?
                        """, (
                            nova_desc.strip(), float(novo_total), float(novo_pago), to_date_str(novo_venc),
                            novo_status, contas_options.get(nova_conta), nova_obs.strip(), int(row["id"])
                        ))
                        st.success("Dívida atualizada!")
                        st.rerun()

                with b2:
                    if st.button("🗑️ Excluir", key=f"del_div_{row['id']}", use_container_width=True):
                        execute("DELETE FROM dividas WHERE id = ?", (int(row["id"]),))
                        st.success("Dívida excluída!")
                        st.rerun()

# =========================================================
# PARCELAMENTOS
# =========================================================
def render_parcelamentos():
    section_title("Parcelamentos", "💳")

    form_novo_parcelamento()

    df = get_parcelamentos()
    if df.empty:
        st.info("Nenhum parcelamento cadastrado.")
        return

    contas = get_contas()
    cartoes = contas[contas["tipo"] == "Cartão"]
    opcoes_cartao = {f"{row['nome']} ({row['tipo']})": row["id"] for _, row in cartoes.iterrows()}
    cartao_reverse = {v: k for k, v in opcoes_cartao.items()}

    for _, row in df.iterrows():
        restantes = int(row["total_parcelas"]) - int(row["parcelas_lancadas"])
        status = "Ativo" if int(row["ativo"]) == 1 else "Encerrado"

        c1, c2 = st.columns([6, 1])

        with c1:
            st.markdown(f"""
            <div class="launch-card">
                <b>{row['descricao']}</b><br>
                Total: <b>{br_money(row['valor_total'])}</b> | Parcela: <b>{br_money(row['valor_parcela'])}</b><br>
                Parcelas: <b>{int(row['total_parcelas'])}</b> | Lançadas: <b>{int(row['parcelas_lancadas'])}</b> | Restantes: <b>{restantes if restantes > 0 else 0}</b><br>
                Cartão: {row['conta_nome'] if pd.notna(row['conta_nome']) else '-'} | Status: <b>{status}</b>
            </div>
            """, unsafe_allow_html=True)

        with c2:
            if st.button("✏️", key=f"edit_parc_btn_{row['id']}", use_container_width=True):
                st.session_state[f"edit_parc_open_{row['id']}"] = not st.session_state.get(f"edit_parc_open_{row['id']}", False)

        if st.session_state.get(f"edit_parc_open_{row['id']}", False):
            with st.expander(f"Editar parcelamento #{row['id']}", expanded=True):
                colA, colB = st.columns(2)

                with colA:
                    nova_desc = st.text_input("Descrição", value=row["descricao"], key=f"ep_desc_{row['id']}")
                    novo_total = st.number_input("Valor total", min_value=0.0, step=0.01, format="%.2f", value=float(row["valor_total"]), key=f"ep_total_{row['id']}")
                    novo_n = st.number_input("Total de parcelas", min_value=2, step=1, value=int(row["total_parcelas"]), key=f"ep_n_{row['id']}")

                with colB:
                    nova_data = st.date_input("Data da 1ª parcela", value=parse_date(row["data_primeira_parcela"]), key=f"ep_data_{row['id']}")
                    nova_cat = st.text_input("Categoria", value=row["categoria"] if pd.notna(row["categoria"]) else "", key=f"ep_cat_{row['id']}")
                    cartao_atual = cartao_reverse.get(row["conta_id"], list(opcoes_cartao.keys())[0] if opcoes_cartao else None)
                    novo_cartao = st.selectbox(
                        "Cartão",
                        list(opcoes_cartao.keys()),
                        index=list(opcoes_cartao.keys()).index(cartao_atual) if cartao_atual in list(opcoes_cartao.keys()) else 0,
                        key=f"ep_cartao_{row['id']}"
                    )

                nova_obs = st.text_area("Observação", value=row["observacao"] if pd.notna(row["observacao"]) else "", key=f"ep_obs_{row['id']}")
                novo_ativo = st.selectbox("Status", ["Ativo", "Encerrado"], index=0 if int(row["ativo"]) == 1 else 1, key=f"ep_status_{row['id']}")

                st.warning("Ao salvar, o app recria TODAS as parcelas desse parcelamento. Isso é ideal para corrigir parcelamento completo.")

                b1, b2, b3 = st.columns(3)

                with b1:
                    if st.button("💾 Salvar e recriar parcelas", key=f"save_parc_{row['id']}", use_container_width=True):
                        valor_parcela = float(novo_total) / int(novo_n)
                        ativo_int = 1 if novo_ativo == "Ativo" else 0

                        execute("""
                            UPDATE parcelamentos
                            SET descricao = ?, valor_total = ?, valor_parcela = ?, total_parcelas = ?,
                                parcelas_lancadas = 0, data_primeira_parcela = ?, categoria = ?, conta_id = ?,
                                observacao = ?, ativo = ?
                            WHERE id = ?
                        """, (
                            nova_desc.strip(), float(novo_total), valor_parcela, int(novo_n),
                            to_date_str(nova_data), nova_cat.strip(), opcoes_cartao.get(novo_cartao),
                            nova_obs.strip(), ativo_int, int(row["id"])
                        ))

                        if ativo_int == 1:
                            gerar_parcelas_futuras(int(row["id"]))
                        else:
                            execute("DELETE FROM lancamentos WHERE parcelamento_id = ?", (int(row["id"]),))

                        st.success("Parcelamento atualizado com sucesso!")
                        st.rerun()

                with b2:
                    if st.button("⛔ Encerrar", key=f"encerrar_parc_{row['id']}", use_container_width=True):
                        execute("UPDATE parcelamentos SET ativo = 0 WHERE id = ?", (int(row["id"]),))
                        st.success("Parcelamento encerrado!")
                        st.rerun()

                with b3:
                    if st.button("🗑️ Excluir", key=f"del_parc_{row['id']}", use_container_width=True):
                        execute("DELETE FROM lancamentos WHERE parcelamento_id = ?", (int(row["id"]),))
                        execute("DELETE FROM parcelamentos WHERE id = ?", (int(row["id"]),))
                        st.success("Parcelamento excluído!")
                        st.rerun()

# =========================================================
# MAIN APP
# =========================================================
def main():
    init_db()

    st.title("💰 Financeiro Pessoal V3 Final")
    st.caption("Controle financeiro com lançamentos, dívidas, parcelamentos e visão por banco/cartão.")

    tabs = st.tabs([
        "📊 Dashboard",
        "🧾 Lançamentos",
        "📌 Dívidas",
        "💳 Parcelamentos"
    ])

    with tabs[0]:
        render_dashboard()

    with tabs[1]:
        render_lancamentos()

    with tabs[2]:
        render_dividas()

    with tabs[3]:
        render_parcelamentos()

if __name__ == "__main__":
    main()
