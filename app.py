import streamlit as st
import sqlite3
import pandas as pd
from datetime import datetime, date
from dateutil.relativedelta import relativedelta

# =========================================================
# CONFIGURAÇÃO E ESTILO
# =========================================================
st.set_page_config(page_title="Finanças Pro", page_icon="💸", layout="wide")

DB_NAME = "financeiro_v3.db"
BANCOS = ["Banco do Brasil", "Banrisul", "Nubank", "Itaú", "Flash (VA)"]
CATEGORIAS = ["Salário", "Freela", "Alimentação", "Mercado", "Transporte", "Moradia", "Lazer", "Saúde", "Assinaturas", "Outros"]

st.markdown("""
<style>
    .main .block-container { padding: 1rem 0.5rem; }
    .metric-card {
        background: #f8fafc; border: 1px solid #e2e8f0;
        border-radius: 12px; padding: 10px; margin-bottom: 10px;
    }
    .status-pos { color: #059669; font-weight: bold; }
    .status-neg { color: #dc2626; font-weight: bold; }
    .stButton>button { width: 100%; border-radius: 10px; height: 3em; }
</style>
""", unsafe_allow_html=True)

# =========================================================
# BANCO DE DADOS (LÓGICA)
# =========================================================
def get_conn(): return sqlite3.connect(DB_NAME, check_same_thread=False)

def init_db():
    conn = get_conn(); c = conn.cursor()
    c.execute("CREATE TABLE IF NOT EXISTS lancamentos (id INTEGER PRIMARY KEY AUTOINCREMENT, data TEXT, descricao TEXT, tipo TEXT, categoria TEXT, banco TEXT, valor REAL, origem TEXT DEFAULT 'manual')")
    c.execute("CREATE TABLE IF NOT EXISTS orcamentos (categoria TEXT PRIMARY KEY, meta REAL)")
    conn.commit(); conn.close()

def add_lanc(data, desc, tipo, cat, banco, valor, origem='manual'):
    conn = get_conn(); c = conn.cursor()
    c.execute("INSERT INTO lancamentos (data, descricao, tipo, categoria, banco, valor, origem) VALUES (?,?,?,?,?,?,?)",
              (data, desc, tipo, cat, banco, valor, origem))
    conn.commit(); conn.close()

# =========================================================
# COMPONENTES DA UI
# =========================================================

def render_resumo():
    conn = get_conn()
    df = pd.read_sql_query("SELECT * FROM lancamentos", conn)
    conn.close()
    
    hoje = date.today().isoformat()
    
    # Cálculo de Saldos
    st.subheader("🏦 Meus Saldos")
    col1, col2 = st.columns(2)
    
    total_real = 0
    total_proj = 0
    
    banco_data = []
    for b in BANCOS:
        dfb = df[df['banco'] == b]
        # Real (até hoje)
        r = dfb[(dfb['tipo']=='Receita') & (dfb['data']<=hoje)]['valor'].sum() - dfb[(dfb['tipo']=='Despesa') & (dfb['data']<=hoje)]['valor'].sum()
        # Projetado (total)
        p = dfb[dfb['tipo']=='Receita']['valor'].sum() - dfb[dfb['tipo']=='Despesa']['valor'].sum()
        total_real += r
        total_proj += p
        banco_data.append({"Banco": b, "Real": r, "Projetado": p})

    with col1:
        st.markdown(f"<div class='metric-card'>Saldo Real<br><b style='font-size:1.2rem'>R$ {total_real:,.2f}</b></div>", unsafe_allow_html=True)
    with col2:
        st.markdown(f"<div class='metric-card'>Projetado<br><b style='font-size:1.2rem'>R$ {total_proj:,.2f}</b></div>", unsafe_allow_html=True)

    with st.expander("Ver detalhes por banco"):
        st.table(pd.DataFrame(banco_data).set_index("Banco"))

def render_acoes():
    st.subheader("⚡ Ações Rápidas")
    aba1, aba2, aba3 = st.tabs(["➕ Lançar", "📲 Transf.", "🔁 Recorr."])
    
    with aba1:
        with st.form("f_lanc", clear_on_submit=True):
            d1, d2 = st.columns(2)
            dat = d1.date_input("Data", date.today())
            v = d2.number_input("Valor", min_value=0.0, step=0.01)
            desc = st.text_input("Descrição")
            t = st.selectbox("Tipo", ["Despesa", "Receita"])
            c = st.selectbox("Categoria", CATEGORIAS)
            b = st.selectbox("Banco", BANCOS)
            if st.form_submit_button("Salvar"):
                add_lanc(dat.isoformat(), desc, t, c, b, v)
                st.success("Lançado!")
                st.rerun()

    with aba2:
        with st.form("f_transf", clear_on_submit=True):
            vt = st.number_input("Valor da Transferência", min_value=0.0)
            orig = st.selectbox("Sair de", BANCOS)
            dest = st.selectbox("Para", [b for b in BANCOS if b != orig])
            if st.form_submit_button("Confirmar Transferência"):
                dt = date.today().isoformat()
                add_lanc(dt, f"TRF para {dest}", "Despesa", "Transferência", orig, vt, 'trf')
                add_lanc(dt, f"TRF de {orig}", "Receita", "Transferência", dest, vt, 'trf')
                st.success("Transferência realizada!")
                st.rerun()

    with aba3:
        with st.form("f_rec", clear_on_submit=True):
            desc_r = st.text_input("Ex: Netflix, Aluguel")
            c1, c2 = st.columns(2)
            v_r = c1.number_input("Valor Mensal", min_value=0.0)
            meses = c2.number_input("Meses", min_value=1, value=12)
            cat_r = st.selectbox("Categoria ", CATEGORIAS)
            ban_r = st.selectbox("Banco ", BANCOS)
            if st.form_submit_button("Agendar Recorrência"):
                for i in range(meses):
                    d_r = (date.today() + relativedelta(months=i)).isoformat()
                    add_lanc(d_r, f"{desc_r} ({i+1}/{meses})", "Despesa", cat_r, ban_r, v_r, 'recorrente')
                st.success("Agendado!")
                st.rerun()

def render_orcamento():
    st.subheader("🎯 Orçamento do Mês")
    conn = get_conn()
    df_orc = pd.read_sql_query("SELECT * FROM orcamentos", conn)
    
    # Gasto real do mês atual
    inicio = date.today().replace(day=1).isoformat()
    fim = (date.today() + relativedelta(months=1, day=1, days=-1)).isoformat()
    df_mes = pd.read_sql_query("SELECT categoria, valor FROM lancamentos WHERE tipo='Despesa' AND data BETWEEN ? AND ?", conn, params=(inicio, fim))
    conn.close()

    with st.expander("Configurar Metas"):
        c1, c2 = st.columns(2)
        cat_m = c1.selectbox("Categoria meta", CATEGORIAS)
        val_m = c2.number_input("Meta R$", min_value=0.0)
        if st.button("Definir Meta"):
            conn = get_conn(); c = conn.cursor()
            c.execute("INSERT OR REPLACE INTO orcamentos VALUES (?,?)", (cat_m, val_m))
            conn.commit(); conn.close(); st.rerun()

    if not df_orc.empty:
        for _, row in df_orc.iterrows():
            gasto = df_mes[df_mes['categoria'] == row['categoria']]['valor'].sum()
            perc = min(gasto / row['meta'], 1.0) if row['meta'] > 0 else 0
            st.write(f"**{row['categoria']}** ({gasto:,.2f} / {row['meta']:,.2f})")
            st.progress(perc)

def render_extrato():
    st.subheader("📋 Últimos Lançamentos")
    conn = get_conn()
    df = pd.read_sql_query("SELECT * FROM lancamentos ORDER BY data DESC LIMIT 20", conn)
    conn.close()
    
    for _, row in df.iterrows():
        cor = "status-neg" if row['tipo'] == "Despesa" else "status-pos"
        simbolo = "-" if row['tipo'] == "Despesa" else "+"
        st.markdown(f"""
        <div style="border-bottom: 1px solid #eee; padding: 8px 0;">
            <small>{row['data']} | {row['banco']}</small><br>
            <div style="display: flex; justify-content: space-between;">
                <span>{row['descricao']}</span>
                <span class="{cor}">{simbolo} R$ {row['valor']:,.2f}</span>
            </div>
        </div>
        """, unsafe_allow_html=True)

# =========================================================
# APP MAIN
# =========================================================
def main():
    init_db()
    st.title("💸 Minhas Finanças")
    
    render_resumo()
    st.divider()
    render_acoes()
    st.divider()
    render_orcamento()
    st.divider()
    render_extrato()

if __name__ == "__main__":
    main()
        
