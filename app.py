import streamlit as st
import sqlite3
import pandas as pd
from datetime import datetime, date
from dateutil.relativedelta import relativedelta

# =========================================================
# CONFIGURAÇÃO E ESTILO
# =========================================================
st.set_page_config(page_title="Finanças Pro", page_icon="💸", layout="wide")

DB_NAME = "financeiro_pro_v4.db"
BANCOS = ["Banco do Brasil", "Banrisul", "Nubank", "Itaú", "Flash (VA)"]
CATEGORIAS = ["Salário", "Alimentação", "Mercado", "Transporte", "Moradia", "Lazer", "Saúde", "Assinaturas", "Dívidas", "Outros"]

st.markdown("""
<style>
    .main .block-container { padding: 1rem 0.5rem; }
    .card {
        background: #ffffff; border: 1px solid #e2e8f0;
        border-radius: 12px; padding: 15px; margin-bottom: 10px;
        box-shadow: 0 2px 4px rgba(0,0,0,0.05);
    }
    .status-pago { color: #059669; font-weight: bold; }
    .status-pendente { color: #ea580c; font-weight: bold; }
    .stButton>button { width: 100%; border-radius: 8px; }
    .small-text { font-size: 0.8rem; color: #64748b; }
</style>
""", unsafe_allow_html=True)

# =========================================================
# BANCO DE DADOS
# =========================================================
def get_conn(): return sqlite3.connect(DB_NAME, check_same_thread=False)

def init_db():
    conn = get_conn(); c = conn.cursor()
    # Lançamentos REAIS (afetam saldo)
    c.execute("""CREATE TABLE IF NOT EXISTS lancamentos (
        id INTEGER PRIMARY KEY AUTOINCREMENT, 
        data TEXT, descricao TEXT, tipo TEXT, categoria TEXT, 
        banco TEXT, valor REAL)""")
    
    # Contas PREVISTAS / DÍVIDAS
    c.execute("""CREATE TABLE IF NOT EXISTS contas_previstas (
        id INTEGER PRIMARY KEY AUTOINCREMENT, 
        descricao TEXT, categoria TEXT, valor REAL, 
        data_vencimento TEXT, status TEXT DEFAULT 'Pendente')""")
    
    # Orçamentos (Metas)
    c.execute("CREATE TABLE IF NOT EXISTS orcamentos (categoria TEXT PRIMARY KEY, meta REAL)")
    conn.commit(); conn.close()

# --- Helpers de Dados ---
def db_execute(query, params=()):
    conn = get_conn(); c = conn.cursor()
    c.execute(query, params); conn.commit(); conn.close()

# =========================================================
# LOGICA DE NEGÓCIO
# =========================================================

def pagar_conta(id_conta, banco, data_pagamento):
    conn = get_conn(); c = conn.cursor()
    conta = c.execute("SELECT descricao, categoria, valor FROM contas_previstas WHERE id=?", (id_conta,)).fetchone()
    if conta:
        desc, cat, valor = conta
        # 1. Cria o lançamento real
        c.execute("INSERT INTO lancamentos (data, descricao, tipo, categoria, banco, valor) VALUES (?,?,?,?,?,?)",
                  (data_pagamento, f"PAGTO: {desc}", "Despesa", cat, banco, valor))
        # 2. Marca a conta como paga
        c.execute("UPDATE contas_previstas SET status='Pago' WHERE id=?", (id_conta,))
    conn.commit(); conn.close()

# =========================================================
# INTERFACE
# =========================================================

def main():
    init_db()
    st.title("💸 Gestão Financeira")

    # 1. RESUMO DE SALDO (REAL vs PROJETADO)
    conn = get_conn()
    df_lan = pd.read_sql_query("SELECT * FROM lancamentos", conn)
    df_prev = pd.read_sql_query("SELECT * FROM contas_previstas WHERE status='Pendente'", conn)
    conn.close()

    saldo_atual = df_lan[df_lan['tipo']=='Receita']['valor'].sum() - df_lan[df_lan['tipo']=='Despesa']['valor'].sum()
    dividas_aberto = df_prev['valor'].sum()
    saldo_projetado = saldo_atual - dividas_aberto

    c1, c2, c3 = st.columns(3)
    c1.metric("Saldo em Conta", f"R$ {saldo_atual:,.2f}")
    c2.metric("Contas a Pagar", f"R$ {dividas_aberto:,.2f}", delta_color="inverse")
    c3.metric("Projeção Final", f"R$ {saldo_projetado:,.2f}")

    st.divider()

    # 2. ENTRADAS E AGENDAMENTOS (Ações)
    with st.expander("➕ Novo Lançamento / Conta / TRF"):
        t1, t2, t3 = st.tabs(["💰 Receita Real", "📝 Conta a Pagar", "📲 Transferência"])
        
        with t1:
            with st.form("f_rec", clear_on_submit=True):
                col_a, col_b = st.columns(2)
                dat = col_a.date_input("Data Recebimento", date.today())
                val = col_b.number_input("Valor R$", min_value=0.0)
                desc = st.text_input("Descrição (Ex: Salário)")
                ban = st.selectbox("Banco destino", BANCOS)
                if st.form_submit_button("Registrar Entrada"):
                    db_execute("INSERT INTO lancamentos (data, descricao, tipo, categoria, banco, valor) VALUES (?,?,'Receita',?,?,?)",
                               (dat.isoformat(), desc, "Salário", ban, val))
                    st.rerun()

        with t2:
            with st.form("f_prev", clear_on_submit=True):
                col_a, col_b = st.columns(2)
                venc = col_a.date_input("Vencimento", date.today())
                val_p = col_b.number_input("Valor R$", min_value=0.0, key="v_p")
                desc_p = st.text_input("O que é? (Ex: Aluguel, Internet)")
                cat_p = st.selectbox("Categoria", CATEGORIAS)
                recorr = st.checkbox("É recorrente? (Lançar para 12 meses)")
                if st.form_submit_button("Agendar Conta"):
                    meses = 12 if recorr else 1
                    for i in range(meses):
                        data_v = (venc + relativedelta(months=i)).isoformat()
                        db_execute("INSERT INTO contas_previstas (descricao, categoria, valor, data_vencimento) VALUES (?,?,?,?)",
                                   (f"{desc_p} {i+1 if recorr else ''}", cat_p, val_p, data_v))
                    st.rerun()

        with t3:
            with st.form("f_trf"):
                v_trf = st.number_input("Valor", min_value=0.0)
                o = st.selectbox("Origem", BANCOS)
                d = st.selectbox("Destino", [b for b in BANCOS if b != o])
                if st.form_submit_button("Transferir"):
                    dt = date.today().isoformat()
                    db_execute("INSERT INTO lancamentos (data, descricao, tipo, categoria, banco, valor) VALUES (?,?,'Despesa','Transferência',?,?)", (dt, f"TRF para {d}", o, v_trf))
                    db_execute("INSERT INTO lancamentos (data, descricao, tipo, categoria, banco, valor) VALUES (?,?,'Receita','Transferência',?,?)", (dt, f"TRF de {o}", d, v_trf))
                    st.rerun()

    st.divider()

    # 3. CONTAS EM ABERTO (Onde você paga)
    st.subheader("🗓️ Contas a Pagar (Pendentes)")
    if df_prev.empty:
        st.info("Nenhuma conta pendente! 🎉")
    else:
        for _, row in df_prev.iterrows():
            with st.container():
                st.markdown(f"""
                <div class="card">
                    <div style="display: flex; justify-content: space-between;">
                        <b>{row['descricao']}</b>
                        <span class="status-pendente">R$ {row['valor']:,.2f}</span>
                    </div>
                    <div class="small-text">Vencimento: {row['data_vencimento']} | {row['categoria']}</div>
                </div>
                """, unsafe_allow_html=True)
                
                # Botão de Pagamento lateralizado
                col_btn1, col_btn2 = st.columns([2, 1])
                banco_pagto = col_btn1.selectbox("Pagar com:", BANCOS, key=f"b_{row['id']}")
                if col_btn2.button("✔ Pagar", key=f"btn_{row['id']}"):
                    pagar_conta(row['id'], banco_pagto, date.today().isoformat())
                    st.success("Conta paga!")
                    st.rerun()

    st.divider()

    # 4. ORÇAMENTO (METAS)
    st.subheader("📊 Orçamento vs Realizado")
    # Configurar metas rápida
    with st.expander("Configurar Metas por Categoria"):
        c_m, v_m = st.columns(2)
        cat_meta = c_m.selectbox("Categoria", CATEGORIAS, key="cat_meta")
        val_meta = v_m.number_input("Meta Mensal R$", min_value=0.0)
        if st.button("Salvar Meta"):
            db_execute("INSERT OR REPLACE INTO orcamentos VALUES (?,?)", (cat_meta, val_meta))
            st.rerun()

    conn = get_conn()
    df_orc = pd.read_sql_query("SELECT * FROM orcamentos", conn)
    inicio_mes = date.today().replace(day=1).isoformat()
    df_gastos_mes = pd.read_sql_query("SELECT categoria, valor FROM lancamentos WHERE tipo='Despesa' AND categoria != 'Transferência' AND data >= ?", conn, params=(inicio_mes,))
    conn.close()

    if not df_orc.empty:
        for _, m in df_orc.iterrows():
            realizado = df_gastos_mes[df_gastos_mes['categoria'] == m['categoria']]['valor'].sum()
            restante = m['meta'] - realizado
            st.write(f"**{m['categoria']}**")
            col_o1, col_o2 = st.columns([3, 1])
            col_o1.progress(min(realizado/m['meta'], 1.0) if m['meta'] > 0 else 0)
            col_o2.write(f"{realizado:,.0f}/{m['meta']:,.0f}")
    
    st.divider()

    # 5. HISTÓRICO DE SALDO POR BANCO
    with st.expander("🏦 Saldo Detalhado por Banco"):
        for b in BANCOS:
            s = df_lan[(df_lan['banco']==b) & (df_lan['tipo']=='Receita')]['valor'].sum() - \
                df_lan[(df_lan['banco']==b) & (df_lan['tipo']=='Despesa')]['valor'].sum()
            st.write(f"{b}: **R$ {s:,.2f}**")

if __name__ == "__main__":
    main()
    
