import streamlit as st
import sqlite3
import pandas as pd
from datetime import datetime, date
from dateutil.relativedelta import relativedelta

# =========================================================
# CONFIG
# =========================================================
st.set_page_config(
    page_title="Finanças Pro",
    page_icon="💸",
    layout="wide",
)

DB_NAME = "financeiro_v2.db"

BANCOS = ["Banco do Brasil", "Banrisul", "Nubank", "Itaú", "Flash (Vale Alimentação)"]
TIPOS = ["Receita", "Despesa", "Transferência"]
CATEGORIAS = [
    "Salário", "Freela", "Alimentação", "Mercado", "Transporte", 
    "Combustível", "Moradia", "Lazer", "Saúde", "Educação", 
    "Assinaturas", "Fatura Cartão", "Transferência", "Outros"
]

# =========================================================
# ESTILO / CSS
# =========================================================
st.markdown("""
<style>
    .metric-card {
        background: white; border-radius: 18px; padding: 15px;
        box-shadow: 0 4px 12px rgba(0,0,0,0.05); border: 1px solid #efefef;
        text-align: center;
    }
    .status-positivo { color: #16a34a; font-weight: bold; }
    .status-negativo { color: #dc2626; font-weight: bold; }
</style>
""", unsafe_allow_html=True)

# =========================================================
# DB CORE
# =========================================================
def get_conn():
    return sqlite3.connect(DB_NAME, check_same_thread=False)

def init_db():
    conn = get_conn()
    c = conn.cursor()
    # Tabela de Lançamentos
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
            grupo_id TEXT
        )
    """)
    # Tabela de Orçamentos (Metas)
    c.execute("""
        CREATE TABLE IF NOT EXISTS orcamentos (
            categoria TEXT PRIMARY KEY,
            meta REAL NOT NULL
        )
    """)
    # Tabela de Recorrências
    c.execute("""
        CREATE TABLE IF NOT EXISTS recorrencias (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            descricao TEXT,
            valor REAL,
            categoria TEXT,
            banco TEXT,
            dia_vencimento INTEGER,
            meses_duracao INTEGER
        )
    """)
    conn.commit()
    conn.close()

# =========================================================
# FUNÇÕES DE LÓGICA (BACKEND)
# =========================================================

def add_lancamento(data, descricao, tipo, categoria, banco, valor, observacao="", origem="manual", grupo_id=None):
    conn = get_conn()
    c = conn.cursor()
    c.execute("""
        INSERT INTO lancamentos (data, descricao, tipo, categoria, banco, valor, observacao, origem, grupo_id)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
    """, (data, descricao, tipo, categoria, banco, valor, observacao, origem, grupo_id))
    conn.commit()
    conn.close()

def realizar_transferencia(data, valor, origem, destino):
    grupo_id = f"TRF_{datetime.now().strftime('%Y%m%d%H%M%S')}"
    # Saída
    add_lancamento(data.isoformat(), f"TRF para {destino}", "Despesa", "Transferência", origem, valor, "Transferência enviada", "transferencia", grupo_id)
    # Entrada
    add_lancamento(data.isoformat(), f"TRF de {origem}", "Receita", "Transferência", destino, valor, "Transferência recebida", "transferencia", grupo_id)

def salvar_recorrencia(descricao, valor, categoria, banco, dia, meses):
    hoje = date.today()
    grupo_id = f"REC_{datetime.now().strftime('%Y%m%d%H%M%S')}"
    for i in range(meses):
        data_lanc = hoje.replace(day=dia) + relativedelta(months=i)
        add_lancamento(data_lanc.isoformat(), f"{descricao} (Recorrente {i+1}/{meses})", "Despesa", categoria, banco, valor, "Lançamento automático", "recorrente", grupo_id)

def set_orcamento(categoria, valor):
    conn = get_conn()
    c = conn.cursor()
    c.execute("INSERT OR REPLACE INTO orcamentos (categoria, meta) VALUES (?, ?)", (categoria, valor))
    conn.commit()
    conn.close()

def get_all_orcamentos():
    conn = get_conn()
    df = pd.read_sql_query("SELECT * FROM orcamentos", conn)
    conn.close()
    return df

# =========================================================
# CÁLCULOS DE SALDO (REAL VS PROJETADO)
# =========================================================

def get_saldos_bancos_completos():
    conn = get_conn()
    df = pd.read_sql_query("SELECT * FROM lancamentos", conn)
    conn.close()
    
    hoje = date.today().isoformat()
    
    resultados = []
    for banco in BANCOS:
        df_banco = df[df['banco'] == banco]
        
        # Saldo Real (Até hoje)
        df_real = df_banco[df_banco['data'] <= hoje]
        rec_real = df_real[df_real['tipo'] == 'Receita']['valor'].sum()
        desp_real = df_real[df_real['tipo'] == 'Despesa']['valor'].sum()
        saldo_real = rec_real - desp_real
        
        # Saldo Projetado (Tudo, incluindo futuro)
        rec_proj = df_banco[df_banco['tipo'] == 'Receita']['valor'].sum()
        desp_proj = df_banco[df_banco['tipo'] == 'Despesa']['valor'].sum()
        saldo_proj = rec_proj - desp_proj
        
        resultados.append({
            "banco": banco,
            "saldo_real": saldo_real,
            "saldo_projetado": saldo_proj
        })
    return pd.DataFrame(resultados)

# =========================================================
# INTERFACE (UI)
# =========================================================

def br_money(v):
    return f"R$ {v:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")

def main():
    init_db()
    
    st.sidebar.title("💸 Finanças Pro")
    menu = st.sidebar.radio("Navegação", ["Dashboard", "Lançamentos", "Transferência", "Recorrência", "Orçamentos"])

    # --- DASHBOARD ---
    if menu == "Dashboard":
        st.header("Resumo Patrimonial")
        
        df_saldos = get_saldos_bancos_completos()
        
        # Cards de Totais
        c1, c2 = st.columns(2)
        total_real = df_saldos['saldo_real'].sum()
        total_proj = df_saldos['saldo_projetado'].sum()
        
        c1.metric("Saldo Real Total (Hoje)", br_money(total_real))
        c2.metric("Saldo Projetado Total", br_money(total_proj), delta=br_money(total_proj - total_real))
        
        st.subheader("Saldos por Instituição")
        for _, row in df_saldos.iterrows():
            with st.container():
                col1, col2, col3 = st.columns([2, 1, 1])
                col1.markdown(f"**{row['banco']}**")
                col2.markdown(f"Real: <span class='status-positivo'>{br_money(row['saldo_real'])}</span>", unsafe_allow_html=True)
                col3.markdown(f"Projetado: {br_money(row['saldo_projetado'])}")
                st.divider()

    # --- TRANSFERÊNCIA ---
    elif menu == "Transferência":
        st.header("Transferência entre Contas")
        with st.form("form_trf"):
            c1, c2 = st.columns(2)
            origem = c1.selectbox("Sair de (Origem)", BANCOS)
            destino = c2.selectbox("Ir para (Destino)", [b for b in BANCOS if b != origem])
            valor_trf = st.number_input("Valor", min_value=0.01, step=50.0)
            data_trf = st.date_input("Data", value=date.today())
            
            if st.form_submit_button("Confirmar Transferência"):
                realizar_transferencia(data_trf, valor_trf, origem, destino)
                st.success("Transferência realizada!")

    # --- RECORRÊNCIA ---
    elif menu == "Recorrência":
        st.header("Agendar Despesas Recorrentes")
        with st.form("form_rec"):
            desc_rec = st.text_input("Descrição (Ex: Aluguel)")
            c1, c2, c3 = st.columns(3)
            val_rec = c1.number_input("Valor Mensal", min_value=0.0)
            dia_venc = c2.number_input("Dia do Vencimento", min_value=1, max_value=31, value=10)
            meses_rec = c3.number_input("Duração (Meses)", min_value=1, max_value=48, value=12)
            
            cat_rec = st.selectbox("Categoria", CATEGORIAS)
            ban_rec = st.selectbox("Banco", BANCOS)
            
            if st.form_submit_button("Gerar Lançamentos Recorrentes"):
                salvar_recorrencia(desc_rec, val_rec, cat_rec, ban_rec, dia_venc, meses_rec)
                st.success(f"Foram gerados {meses_rec} lançamentos futuros.")

    # --- ORÇAMENTOS ---
    elif menu == "Orçamentos":
        st.header("Meta Mensal por Categoria")
        
        # Configurar Meta
        with st.expander("Configurar Metas"):
            c1, c2 = st.columns(2)
            cat_meta = c1.selectbox("Categoria", CATEGORIAS)
            val_meta = c2.number_input("Valor Meta (R$)", min_value=0.0)
            if st.button("Salvar Meta"):
                set_orcamento(cat_meta, val_meta)
        
        # Visualização
        st.subheader("Acompanhamento do Mês Atual")
        hoje = date.today()
        inicio_mes = hoje.replace(day=1).isoformat()
        fim_mes = (hoje.replace(day=1) + relativedelta(months=1, days=-1)).isoformat()
        
        conn = get_conn()
        df_mes = pd.read_sql_query("SELECT categoria, valor, tipo FROM lancamentos WHERE data BETWEEN ? AND ?", conn, params=(inicio_mes, fim_mes))
        df_metas = get_all_orcamentos()
        conn.close()
        
        if not df_metas.empty:
            resumo_orc = []
            for _, m in df_metas.iterrows():
                gasto_real = df_mes[(df_mes['categoria'] == m['categoria']) & (df_mes['tipo'] == 'Despesa')]['valor'].sum()
                restante = m['meta'] - gasto_real
                resumo_orc.append({
                    "Categoria": m['categoria'],
                    "Meta": m['meta'],
                    "Gasto Real": gasto_real,
                    "Restante": restante
                })
            
            df_resumo = pd.DataFrame(resumo_orc)
            st.table(df_resumo.style.format({"Meta": br_money, "Gasto Real": br_money, "Restante": br_money}))
        else:
            st.info("Cadastre metas para visualizar o orçamento.")

    # --- LANÇAMENTOS (ADAPTADO) ---
    elif menu == "Lançamentos":
        st.header("Lançamentos Manuais")
        # Mantive a lógica original simplificada aqui para brevidade
        with st.form("novo_lan"):
            c1, c2, c3 = st.columns(3)
            data = c1.date_input("Data", date.today())
            desc = c2.text_input("Descrição")
            val = c3.number_input("Valor", min_value=0.0)
            tipo = st.selectbox("Tipo", ["Receita", "Despesa"])
            cat = st.selectbox("Categoria", CATEGORIAS)
            ban = st.selectbox("Banco", BANCOS)
            if st.form_submit_button("Salvar"):
                add_lancamento(data.isoformat(), desc, tipo, cat, ban, val)
                st.rerun()

if __name__ == "__main__":
    main()
