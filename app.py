import streamlit as st
import sqlite3
import pandas as pd
from datetime import datetime, date
from dateutil.relativedelta import relativedelta

# =========================================================
# CONFIGURAÇÃO E ESTILO
# =========================================================
st.set_page_config(page_title="Finanças Pro", page_icon="💸", layout="wide")

DB_NAME = "financeiro_pro_v5_1.db"
BANCOS = ["Banco do Brasil", "Banrisul", "Nubank", "Itaú", "Flash (VA)"]
CATEGORIAS = [
    "Salário", "Alimentação", "Mercado", "Transporte", "Moradia",
    "Lazer", "Saúde", "Assinaturas", "Dívidas", "Outros"
]

st.markdown("""
<style>
    .main .block-container { padding: 1rem 0.8rem; }
    .card {
        background: #ffffff;
        border: 1px solid #e2e8f0;
        border-radius: 12px;
        padding: 15px;
        margin-bottom: 10px;
        box-shadow: 0 2px 4px rgba(0,0,0,0.05);
    }
    .status-pago { color: #059669; font-weight: bold; }
    .status-pendente { color: #ea580c; font-weight: bold; }
    .status-atrasado { color: #dc2626; font-weight: bold; }
    .saldo-positivo {
        padding: 12px;
        border-radius: 10px;
        background: #ecfdf5;
        border: 1px solid #a7f3d0;
        text-align: center;
        font-weight: 700;
        color: #065f46;
        margin-bottom: 8px;
    }
    .saldo-negativo {
        padding: 12px;
        border-radius: 10px;
        background: #fef2f2;
        border: 1px solid #fecaca;
        text-align: center;
        font-weight: 700;
        color: #991b1b;
        margin-bottom: 8px;
    }
    .saldo-neutro {
        padding: 12px;
        border-radius: 10px;
        background: #f8fafc;
        border: 1px solid #cbd5e1;
        text-align: center;
        font-weight: 700;
        color: #334155;
        margin-bottom: 8px;
    }
    .stButton>button { width: 100%; border-radius: 8px; }
    .small-text { font-size: 0.85rem; color: #64748b; }
</style>
""", unsafe_allow_html=True)

# =========================================================
# BANCO DE DADOS
# =========================================================
def get_conn():
    return sqlite3.connect(DB_NAME, check_same_thread=False)

def init_db():
    conn = get_conn()
    c = conn.cursor()

    # Lançamentos REAIS (afetam saldo)
    c.execute("""
        CREATE TABLE IF NOT EXISTS lancamentos (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            data TEXT,
            descricao TEXT,
            tipo TEXT,
            categoria TEXT,
            banco TEXT,
            valor REAL
        )
    """)

    # Contas PREVISTAS / DÍVIDAS
    c.execute("""
        CREATE TABLE IF NOT EXISTS contas_previstas (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            descricao TEXT,
            categoria TEXT,
            valor REAL,
            data_vencimento TEXT,
            status TEXT DEFAULT 'Pendente',
            banco_pagamento TEXT,
            data_pagamento TEXT
        )
    """)

    # Orçamentos (Metas)
    c.execute("""
        CREATE TABLE IF NOT EXISTS orcamentos (
            categoria TEXT PRIMARY KEY,
            meta REAL
        )
    """)

    conn.commit()

    # Migração simples (caso venha de versões anteriores)
    try:
        c.execute("ALTER TABLE contas_previstas ADD COLUMN banco_pagamento TEXT")
        conn.commit()
    except:
        pass

    try:
        c.execute("ALTER TABLE contas_previstas ADD COLUMN data_pagamento TEXT")
        conn.commit()
    except:
        pass

    conn.close()

def db_execute(query, params=()):
    conn = get_conn()
    c = conn.cursor()
    c.execute(query, params)
    conn.commit()
    conn.close()

def db_fetch_df(query, params=()):
    conn = get_conn()
    df = pd.read_sql_query(query, conn, params=params)
    conn.close()
    return df

# =========================================================
# HELPERS
# =========================================================
def format_brl(valor):
    return f"R$ {valor:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")

def calcular_saldo_por_banco(df_lan, banco):
    receitas = df_lan[(df_lan["banco"] == banco) & (df_lan["tipo"] == "Receita")]["valor"].sum()
    despesas = df_lan[(df_lan["banco"] == banco) & (df_lan["tipo"] == "Despesa")]["valor"].sum()
    return receitas - despesas

def calcular_saldos(df_lan):
    saldos = {}
    for banco in BANCOS:
        saldos[banco] = calcular_saldo_por_banco(df_lan, banco)
    return saldos

def status_conta(data_vencimento_str, status):
    if status == "Pago":
        return "Pago"
    venc = datetime.strptime(data_vencimento_str, "%Y-%m-%d").date()
    if venc < date.today():
        return "Atrasado"
    return "Pendente"

# =========================================================
# LÓGICA DE NEGÓCIO
# =========================================================
def pagar_conta(id_conta, banco, data_pagamento):
    conn = get_conn()
    c = conn.cursor()

    conta = c.execute("""
        SELECT descricao, categoria, valor, status
        FROM contas_previstas
        WHERE id=?
    """, (id_conta,)).fetchone()

    if not conta:
        conn.close()
        return False, "Conta não encontrada."

    desc, cat, valor, status = conta

    if status == "Pago":
        conn.close()
        return False, "Essa conta já está paga."

    # Permite pagar mesmo sem saldo suficiente
    # O saldo do banco ficará negativo automaticamente,
    # pois será registrado como despesa normalmente.

    # 1. Cria o lançamento real
    c.execute("""
        INSERT INTO lancamentos (data, descricao, tipo, categoria, banco, valor)
        VALUES (?, ?, 'Despesa', ?, ?, ?)
    """, (data_pagamento, f"PAGTO: {desc}", cat, banco, valor))

    # 2. Marca a conta como paga
    c.execute("""
        UPDATE contas_previstas
        SET status='Pago',
            banco_pagamento=?,
            data_pagamento=?
        WHERE id=?
    """, (banco, data_pagamento, id_conta))

    conn.commit()
    conn.close()

    return True, f"Conta paga com sucesso usando {banco}."

# =========================================================
# INTERFACE
# =========================================================
def main():
    init_db()
    st.title("💸 Gestão Financeira Pessoal")

    # -----------------------------------------------------
    # CARREGAMENTO DE DADOS
    # -----------------------------------------------------
    df_lan = db_fetch_df("SELECT * FROM lancamentos ORDER BY data DESC, id DESC")
    df_prev = db_fetch_df("SELECT * FROM contas_previstas ORDER BY data_vencimento ASC, id ASC")
    df_orc = db_fetch_df("SELECT * FROM orcamentos")

    # Garantia para DataFrames vazios
    if df_lan.empty:
        df_lan = pd.DataFrame(columns=["id", "data", "descricao", "tipo", "categoria", "banco", "valor"])

    if df_prev.empty:
        df_prev = pd.DataFrame(columns=[
            "id", "descricao", "categoria", "valor", "data_vencimento",
            "status", "banco_pagamento", "data_pagamento"
        ])

    # -----------------------------------------------------
    # RESUMO GERAL
    # -----------------------------------------------------
    saldo_atual = (
        df_lan[df_lan["tipo"] == "Receita"]["valor"].sum()
        - df_lan[df_lan["tipo"] == "Despesa"]["valor"].sum()
    )

    df_prev_pendente = df_prev[df_prev["status"] == "Pendente"] if not df_prev.empty else pd.DataFrame()
    dividas_aberto = df_prev_pendente["valor"].sum() if not df_prev_pendente.empty else 0.0
    saldo_projetado = saldo_atual - dividas_aberto

    c1, c2, c3 = st.columns(3)
    c1.metric("Saldo Total Atual", format_brl(saldo_atual))
    c2.metric("Contas Pendentes", format_brl(dividas_aberto), delta_color="inverse")
    c3.metric("Saldo Projetado", format_brl(saldo_projetado))

    # -----------------------------------------------------
    # SALDO POR BANCO
    # -----------------------------------------------------
    st.subheader("🏦 Saldo por Banco")
    saldos = calcular_saldos(df_lan)
    cols_bancos = st.columns(len(BANCOS))

    for i, banco in enumerate(BANCOS):
        saldo = saldos[banco]
        if saldo > 0:
            classe = "saldo-positivo"
        elif saldo < 0:
            classe = "saldo-negativo"
        else:
            classe = "saldo-neutro"

        cols_bancos[i].markdown(f"""
        <div class="{classe}">
            <div style="font-size: 0.9rem;">{banco}</div>
            <div style="font-size: 1.1rem;">{format_brl(saldo)}</div>
        </div>
        """, unsafe_allow_html=True)

    st.divider()

    # -----------------------------------------------------
    # AÇÕES: NOVO LANÇAMENTO / CONTA / TRANSFERÊNCIA
    # -----------------------------------------------------
    with st.expander("➕ Novo Lançamento / Conta / Transferência", expanded=False):
        t1, t2, t3 = st.tabs(["💰 Receita Real", "📝 Conta a Pagar", "📲 Transferência"])

        # ---------------- Receita ----------------
        with t1:
            with st.form("f_rec", clear_on_submit=True):
                col_a, col_b = st.columns(2)
                dat = col_a.date_input("Data do recebimento", date.today())
                val = col_b.number_input("Valor R$", min_value=0.0, step=0.01)
                desc = st.text_input("Descrição (Ex: Salário, Freelance)")
                ban = st.selectbox("Banco de destino", BANCOS)

                if st.form_submit_button("Registrar Entrada"):
                    if not desc.strip():
                        st.warning("Informe uma descrição para a receita.")
                    elif val <= 0:
                        st.warning("Informe um valor maior que zero.")
                    else:
                        db_execute("""
                            INSERT INTO lancamentos (data, descricao, tipo, categoria, banco, valor)
                            VALUES (?, ?, 'Receita', ?, ?, ?)
                        """, (dat.isoformat(), desc.strip(), "Salário", ban, val))
                        st.success("Receita registrada com sucesso!")
                        st.rerun()

        # ---------------- Conta a pagar ----------------
        with t2:
            with st.form("f_prev", clear_on_submit=True):
                col_a, col_b = st.columns(2)
                venc = col_a.date_input("Vencimento", date.today())
                val_p = col_b.number_input("Valor R$", min_value=0.0, step=0.01, key="v_p")
                desc_p = st.text_input("Descrição da conta (Ex: Aluguel, Internet)")
                cat_p = st.selectbox("Categoria", CATEGORIAS)
                recorr = st.checkbox("É recorrente? (Lançar para 12 meses)")

                if st.form_submit_button("Agendar Conta"):
                    if not desc_p.strip():
                        st.warning("Informe a descrição da conta.")
                    elif val_p <= 0:
                        st.warning("Informe um valor maior que zero.")
                    else:
                        meses = 12 if recorr else 1
                        for i in range(meses):
                            data_v = (venc + relativedelta(months=i)).isoformat()
                            sufixo = f" ({i+1}/{meses})" if recorr else ""
                            db_execute("""
                                INSERT INTO contas_previstas (descricao, categoria, valor, data_vencimento)
                                VALUES (?, ?, ?, ?)
                            """, (f"{desc_p.strip()}{sufixo}", cat_p, val_p, data_v))
                        st.success("Conta(s) agendada(s) com sucesso!")
                        st.rerun()

        # ---------------- Transferência ----------------
        with t3:
            with st.form("f_trf", clear_on_submit=True):
                v_trf = st.number_input("Valor da transferência", min_value=0.0, step=0.01)
                o = st.selectbox("Origem", BANCOS, key="origem_trf")
                d = st.selectbox("Destino", [b for b in BANCOS if b != o], key="destino_trf")

                if st.form_submit_button("Transferir"):
                    if v_trf <= 0:
                        st.warning("Informe um valor maior que zero.")
                    else:
                        dt = date.today().isoformat()

                        # Permite saldo negativo na origem
                        db_execute("""
                            INSERT INTO lancamentos (data, descricao, tipo, categoria, banco, valor)
                            VALUES (?, ?, 'Despesa', 'Transferência', ?, ?)
                        """, (dt, f"TRF para {d}", o, v_trf))

                        db_execute("""
                            INSERT INTO lancamentos (data, descricao, tipo, categoria, banco, valor)
                            VALUES (?, ?, 'Receita', 'Transferência', ?, ?)
                        """, (dt, f"TRF de {o}", d, v_trf))

                        st.success("Transferência realizada com sucesso!")
                        st.rerun()

    st.divider()

    # -----------------------------------------------------
    # FILTRO MENSAL DAS CONTAS
    # -----------------------------------------------------
    st.subheader("🗓️ Lista de Contas do Mês")

    hoje = date.today()
    anos_disponiveis = list(range(hoje.year - 2, hoje.year + 3))
    meses_nomes = {
        1: "Janeiro", 2: "Fevereiro", 3: "Março", 4: "Abril",
        5: "Maio", 6: "Junho", 7: "Julho", 8: "Agosto",
        9: "Setembro", 10: "Outubro", 11: "Novembro", 12: "Dezembro"
    }

    col_mes, col_ano = st.columns([2, 1])
    mes_sel = col_mes.selectbox(
        "Mês",
        options=list(meses_nomes.keys()),
        format_func=lambda x: meses_nomes[x],
        index=hoje.month - 1
    )
    ano_sel = col_ano.selectbox(
        "Ano",
        options=anos_disponiveis,
        index=anos_disponiveis.index(hoje.year)
    )

    # Filtra contas do mês/ano selecionados
    if not df_prev.empty:
        df_prev["data_vencimento_dt"] = pd.to_datetime(df_prev["data_vencimento"], errors="coerce")
        df_mes = df_prev[
            (df_prev["data_vencimento_dt"].dt.month == mes_sel) &
            (df_prev["data_vencimento_dt"].dt.year == ano_sel)
        ].copy()
        df_mes = df_mes.sort_values(by=["data_vencimento_dt", "status", "id"])
    else:
        df_mes = pd.DataFrame()

    total_mes = df_mes["valor"].sum() if not df_mes.empty else 0.0
    total_pendente_mes = df_mes[df_mes["status"] == "Pendente"]["valor"].sum() if not df_mes.empty else 0.0
    total_pago_mes = df_mes[df_mes["status"] == "Pago"]["valor"].sum() if not df_mes.empty else 0.0

    c_mes1, c_mes2, c_mes3 = st.columns(3)
    c_mes1.metric("Total de contas no mês", format_brl(total_mes))
    c_mes2.metric("Pendente no mês", format_brl(total_pendente_mes))
    c_mes3.metric("Pago no mês", format_brl(total_pago_mes))

    if df_mes.empty:
        st.info("Nenhuma conta cadastrada para este mês.")
    else:
        for _, row in df_mes.iterrows():
            status_visual = status_conta(row["data_vencimento"], row["status"])

            if status_visual == "Pago":
                classe = "status-pago"
            elif status_visual == "Atrasado":
                classe = "status-atrasado"
            else:
                classe = "status-pendente"

            with st.container():
                st.markdown(f"""
                <div class="card">
                    <div style="display:flex; justify-content:space-between; align-items:center;">
                        <div>
                            <div><b>{row['descricao']}</b></div>
                            <div class="small-text">
                                Categoria: {row['categoria']}<br>
                                Vencimento: {row['data_vencimento']}
                            </div>
                        </div>
                        <div style="text-align:right;">
                            <div class="{classe}">{format_brl(row['valor'])}</div>
                            <div class="{classe}">{status_visual}</div>
                        </div>
                    </div>
                </div>
                """, unsafe_allow_html=True)

                # Se estiver pendente, permitir pagar escolhendo o banco
                if row["status"] == "Pendente":
                    col1, col2 = st.columns([3, 1])
                    banco_pagto = col1.selectbox(
                        f"Selecionar banco para pagar: {row['descricao']}",
                        BANCOS,
                        key=f"banco_pagto_{row['id']}",
                        label_visibility="collapsed"
                    )
                    if col2.button("✔ Pagar", key=f"btn_pagar_{row['id']}"):
                        sucesso, msg = pagar_conta(row["id"], banco_pagto, date.today().isoformat())
                        if sucesso:
                            st.success(msg)
                            st.rerun()
                        else:
                            st.error(msg)

                # Se já estiver paga, mostrar banco/data
                else:
                    banco_info = row["banco_pagamento"] if pd.notna(row["banco_pagamento"]) else "-"
                    data_info = row["data_pagamento"] if pd.notna(row["data_pagamento"]) else "-"
                    st.caption(f"Pago em: {data_info} | Banco: {banco_info}")

    st.divider()

    # -----------------------------------------------------
    # PRÓXIMAS CONTAS (FUTURAS)
    # -----------------------------------------------------
    with st.expander("📅 Próximas Contas (futuras pendentes)"):
        if not df_prev.empty:
            hoje_dt = pd.Timestamp(date.today())
            df_futuras = df_prev[
                (df_prev["status"] == "Pendente") &
                (pd.to_datetime(df_prev["data_vencimento"], errors="coerce") > hoje_dt)
            ].copy()
            df_futuras = df_futuras.sort_values(by=["data_vencimento", "id"])
        else:
            df_futuras = pd.DataFrame()

        if df_futuras.empty:
            st.info("Nenhuma conta futura pendente.")
        else:
            st.dataframe(
                df_futuras[["descricao", "categoria", "valor", "data_vencimento", "status"]],
                use_container_width=True
            )

    # -----------------------------------------------------
    # ORÇAMENTO
    # -----------------------------------------------------
    st.divider()
    st.subheader("📊 Orçamento vs Realizado (mês atual)")

    with st.expander("Configurar Metas por Categoria"):
        c_m, v_m = st.columns(2)
        cat_meta = c_m.selectbox("Categoria", CATEGORIAS, key="cat_meta")
        val_meta = v_m.number_input("Meta Mensal R$", min_value=0.0, step=0.01)

        if st.button("Salvar Meta"):
            db_execute("INSERT OR REPLACE INTO orcamentos (categoria, meta) VALUES (?, ?)", (cat_meta, val_meta))
            st.success("Meta salva com sucesso!")
            st.rerun()

    inicio_mes = date.today().replace(day=1).isoformat()
    df_gastos_mes = db_fetch_df("""
        SELECT categoria, valor
        FROM lancamentos
        WHERE tipo='Despesa'
          AND categoria != 'Transferência'
          AND data >= ?
    """, (inicio_mes,))

    if not df_orc.empty:
        for _, m in df_orc.iterrows():
            realizado = df_gastos_mes[df_gastos_mes["categoria"] == m["categoria"]]["valor"].sum() if not df_gastos_mes.empty else 0.0
            meta = m["meta"] if pd.notna(m["meta"]) else 0.0
            progresso = min(realizado / meta, 1.0) if meta > 0 else 0.0

            st.write(f"**{m['categoria']}**")
            col_o1, col_o2 = st.columns([4, 1])
            col_o1.progress(progresso)
            col_o2.write(f"{format_brl(realizado)} / {format_brl(meta)}")
    else:
        st.info("Nenhuma meta cadastrada ainda.")

    # -----------------------------------------------------
    # HISTÓRICO DE LANÇAMENTOS
    # -----------------------------------------------------
    st.divider()
    with st.expander("📜 Histórico de Lançamentos"):
        if df_lan.empty:
            st.info("Nenhum lançamento registrado.")
        else:
            mostrar_lan = df_lan.sort_values(by=["data", "id"], ascending=[False, False]).copy()
            mostrar_lan["valor"] = mostrar_lan["valor"].apply(format_brl)
            st.dataframe(mostrar_lan, use_container_width=True)

    # -----------------------------------------------------
    # HISTÓRICO DE CONTAS
    # -----------------------------------------------------
    st.divider()
    with st.expander("🧾 Histórico de Contas Cadastradas"):
        if df_prev.empty:
            st.info("Nenhuma conta cadastrada.")
        else:
            mostrar = df_prev.copy()
            mostrar["valor"] = mostrar["valor"].apply(format_brl)
            st.dataframe(
                mostrar[[
                    "descricao", "categoria", "valor", "data_vencimento",
                    "status", "banco_pagamento", "data_pagamento"
                ]].sort_values(by=["data_vencimento"], ascending=False),
                use_container_width=True
            )

if __name__ == "__main__":
    main()
