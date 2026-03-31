import streamlit as st
import sqlite3
import pandas as pd
from datetime import datetime, date
from dateutil.relativedelta import relativedelta
import calendar

# =========================================================
# CONFIGURAÇÃO E ESTILO
# =========================================================
st.set_page_config(page_title="Finanças Pro V6", page_icon="💸", layout="wide")

DB_NAME = "financeiro_pro_v6.db"
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

    .origem-manual {
        color: #1d4ed8;
        font-weight: 600;
    }
    .origem-fixa {
        color: #7c3aed;
        font-weight: 600;
    }

    .small-text { font-size: 0.85rem; color: #64748b; }
    .stButton>button { border-radius: 8px; }
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

    # Lançamentos REAIS
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

    # Contas previstas / mensais (manuais ou geradas por fixa)
    c.execute("""
        CREATE TABLE IF NOT EXISTS contas_previstas (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            descricao TEXT,
            categoria TEXT,
            valor REAL,
            data_vencimento TEXT,
            status TEXT DEFAULT 'Pendente',
            banco_pagamento TEXT,
            data_pagamento TEXT,
            origem TEXT DEFAULT 'Manual',
            fixa_id INTEGER
        )
    """)

    # Contas fixas (modelo)
    c.execute("""
        CREATE TABLE IF NOT EXISTS contas_fixas (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            descricao TEXT,
            categoria TEXT,
            valor REAL,
            dia_vencimento INTEGER,
            data_inicio TEXT,
            ativa INTEGER DEFAULT 1
        )
    """)

    # Orçamentos
    c.execute("""
        CREATE TABLE IF NOT EXISTS orcamentos (
            categoria TEXT PRIMARY KEY,
            meta REAL
        )
    """)

    conn.commit()

    # Migrações simples
    migracoes = [
        "ALTER TABLE contas_previstas ADD COLUMN banco_pagamento TEXT",
        "ALTER TABLE contas_previstas ADD COLUMN data_pagamento TEXT",
        "ALTER TABLE contas_previstas ADD COLUMN origem TEXT DEFAULT 'Manual'",
        "ALTER TABLE contas_previstas ADD COLUMN fixa_id INTEGER"
    ]

    for sql in migracoes:
        try:
            c.execute(sql)
            conn.commit()
        except:
            pass

    conn.close()

# =========================================================
# DB HELPERS
# =========================================================
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

def db_fetch_one(query, params=()):
    conn = get_conn()
    c = conn.cursor()
    row = c.execute(query, params).fetchone()
    conn.close()
    return row

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
    return {banco: calcular_saldo_por_banco(df_lan, banco) for banco in BANCOS}

def status_conta(data_vencimento_str, status):
    if status == "Pago":
        return "Pago"
    venc = datetime.strptime(data_vencimento_str, "%Y-%m-%d").date()
    if venc < date.today():
        return "Atrasado"
    return "Pendente"

def data_valida_mes(ano, mes, dia):
    ultimo_dia = calendar.monthrange(ano, mes)[1]
    dia_ajustado = min(dia, ultimo_dia)
    return date(ano, mes, dia_ajustado)

# =========================================================
# GERAÇÃO AUTOMÁTICA DE CONTAS FIXAS
# =========================================================
def gerar_contas_fixas_automaticamente():
    """
    Gera contas mensais para:
    - mês atual
    - mês anterior
    - próximo mês
    Isso ajuda a manter a lista sempre pronta e evita duplicação.
    """
    conn = get_conn()
    c = conn.cursor()

    fixas = c.execute("""
        SELECT id, descricao, categoria, valor, dia_vencimento, data_inicio, ativa
        FROM contas_fixas
        WHERE ativa = 1
    """).fetchall()

    hoje = date.today()
    meses_para_gerar = [
        (hoje - relativedelta(months=1)).replace(day=1),
        hoje.replace(day=1),
        (hoje + relativedelta(months=1)).replace(day=1),
    ]

    for fixa in fixas:
        fixa_id, desc, cat, valor, dia_venc, data_inicio_str, ativa = fixa
        data_inicio = datetime.strptime(data_inicio_str, "%Y-%m-%d").date()

        for base_mes in meses_para_gerar:
            if base_mes < data_inicio.replace(day=1):
                continue

            venc = data_valida_mes(base_mes.year, base_mes.month, dia_venc)
            venc_str = venc.isoformat()

            # verifica se já existe conta gerada para essa fixa nesse mês
            existe = c.execute("""
                SELECT id FROM contas_previstas
                WHERE fixa_id = ?
                  AND strftime('%Y-%m', data_vencimento) = strftime('%Y-%m', ?)
            """, (fixa_id, venc_str)).fetchone()

            if not existe:
                c.execute("""
                    INSERT INTO contas_previstas (
                        descricao, categoria, valor, data_vencimento,
                        status, origem, fixa_id
                    )
                    VALUES (?, ?, ?, ?, 'Pendente', 'Fixa', ?)
                """, (desc, cat, valor, venc_str, fixa_id))

    conn.commit()
    conn.close()

# =========================================================
# REGRAS DE NEGÓCIO
# =========================================================
def pagar_conta(id_conta, banco, data_pagamento):
    conn = get_conn()
    c = conn.cursor()

    conta = c.execute("""
        SELECT descricao, categoria, valor, status
        FROM contas_previstas
        WHERE id = ?
    """, (id_conta,)).fetchone()

    if not conta:
        conn.close()
        return False, "Conta não encontrada."

    desc, cat, valor, status = conta

    if status == "Pago":
        conn.close()
        return False, "Essa conta já está paga."

    # Permite saldo negativo
    c.execute("""
        INSERT INTO lancamentos (data, descricao, tipo, categoria, banco, valor)
        VALUES (?, ?, 'Despesa', ?, ?, ?)
    """, (data_pagamento, f"PAGTO: {desc}", cat, banco, valor))

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

def desfazer_pagamento(id_conta):
    conn = get_conn()
    c = conn.cursor()

    conta = c.execute("""
        SELECT descricao, categoria, valor, status, banco_pagamento, data_pagamento
        FROM contas_previstas
        WHERE id=?
    """, (id_conta,)).fetchone()

    if not conta:
        conn.close()
        return False, "Conta não encontrada."

    desc, cat, valor, status, banco_pagamento, data_pagamento = conta

    if status != "Pago":
        conn.close()
        return False, "Essa conta não está paga."

    # remove um lançamento compatível (o mais recente)
    lanc = c.execute("""
        SELECT id FROM lancamentos
        WHERE descricao = ?
          AND tipo = 'Despesa'
          AND categoria = ?
          AND banco = ?
          AND valor = ?
        ORDER BY id DESC
        LIMIT 1
    """, (f"PAGTO: {desc}", cat, banco_pagamento, valor)).fetchone()

    if lanc:
        c.execute("DELETE FROM lancamentos WHERE id = ?", (lanc[0],))

    c.execute("""
        UPDATE contas_previstas
        SET status='Pendente',
            banco_pagamento=NULL,
            data_pagamento=NULL
        WHERE id=?
    """, (id_conta,))

    conn.commit()
    conn.close()
    return True, "Pagamento desfeito com sucesso."

def excluir_conta(id_conta):
    conn = get_conn()
    c = conn.cursor()

    conta = c.execute("""
        SELECT descricao, categoria, valor, status, banco_pagamento
        FROM contas_previstas
        WHERE id=?
    """, (id_conta,)).fetchone()

    if not conta:
        conn.close()
        return False, "Conta não encontrada."

    desc, cat, valor, status, banco_pagamento = conta

    # se estiver paga, remove um lançamento correspondente
    if status == "Pago" and banco_pagamento:
        lanc = c.execute("""
            SELECT id FROM lancamentos
            WHERE descricao = ?
              AND tipo = 'Despesa'
              AND categoria = ?
              AND banco = ?
              AND valor = ?
            ORDER BY id DESC
            LIMIT 1
        """, (f"PAGTO: {desc}", cat, banco_pagamento, valor)).fetchone()

        if lanc:
            c.execute("DELETE FROM lancamentos WHERE id = ?", (lanc[0],))

    c.execute("DELETE FROM contas_previstas WHERE id = ?", (id_conta,))
    conn.commit()
    conn.close()
    return True, "Conta excluída com sucesso."

def atualizar_conta_prevista(
    id_conta, descricao, categoria, valor, data_vencimento,
    status, banco_pagamento=None, data_pagamento=None
):
    conn = get_conn()
    c = conn.cursor()

    # busca estado anterior
    antiga = c.execute("""
        SELECT descricao, categoria, valor, status, banco_pagamento
        FROM contas_previstas
        WHERE id=?
    """, (id_conta,)).fetchone()

    if not antiga:
        conn.close()
        return False, "Conta não encontrada."

    desc_ant, cat_ant, val_ant, status_ant, banco_ant = antiga

    # Se estava paga, remove lançamento antigo antes de atualizar
    if status_ant == "Pago" and banco_ant:
        lanc = c.execute("""
            SELECT id FROM lancamentos
            WHERE descricao = ?
              AND tipo = 'Despesa'
              AND categoria = ?
              AND banco = ?
              AND valor = ?
            ORDER BY id DESC
            LIMIT 1
        """, (f"PAGTO: {desc_ant}", cat_ant, banco_ant, val_ant)).fetchone()

        if lanc:
            c.execute("DELETE FROM lancamentos WHERE id = ?", (lanc[0],))

    # atualiza conta
    c.execute("""
        UPDATE contas_previstas
        SET descricao=?,
            categoria=?,
            valor=?,
            data_vencimento=?,
            status=?,
            banco_pagamento=?,
            data_pagamento=?
        WHERE id=?
    """, (
        descricao, categoria, valor, data_vencimento,
        status, banco_pagamento, data_pagamento, id_conta
    ))

    # Se após edição estiver paga, recria lançamento
    if status == "Pago" and banco_pagamento and data_pagamento:
        c.execute("""
            INSERT INTO lancamentos (data, descricao, tipo, categoria, banco, valor)
            VALUES (?, ?, 'Despesa', ?, ?, ?)
        """, (data_pagamento, f"PAGTO: {descricao}", categoria, banco_pagamento, valor))

    conn.commit()
    conn.close()
    return True, "Conta atualizada com sucesso."

def excluir_conta_fixa(id_fixa):
    conn = get_conn()
    c = conn.cursor()

    # remove apenas o modelo fixo (não apaga as contas já geradas)
    c.execute("DELETE FROM contas_fixas WHERE id = ?", (id_fixa,))
    conn.commit()
    conn.close()
    return True, "Conta fixa removida. As contas já geradas permanecem."

def atualizar_conta_fixa(id_fixa, descricao, categoria, valor, dia_vencimento, data_inicio, ativa):
    conn = get_conn()
    c = conn.cursor()
    c.execute("""
        UPDATE contas_fixas
        SET descricao=?,
            categoria=?,
            valor=?,
            dia_vencimento=?,
            data_inicio=?,
            ativa=?
        WHERE id=?
    """, (descricao, categoria, valor, dia_vencimento, data_inicio, ativa, id_fixa))
    conn.commit()
    conn.close()
    return True, "Conta fixa atualizada com sucesso."

# =========================================================
# UI COMPONENTS
# =========================================================
def render_saldos(df_lan):
    st.subheader("🏦 Saldo por Banco")
    saldos = calcular_saldos(df_lan)
    cols = st.columns(len(BANCOS))

    for i, banco in enumerate(BANCOS):
        saldo = saldos[banco]
        if saldo > 0:
            classe = "saldo-positivo"
        elif saldo < 0:
            classe = "saldo-negativo"
        else:
            classe = "saldo-neutro"

        cols[i].markdown(f"""
        <div class="{classe}">
            <div style="font-size:0.9rem;">{banco}</div>
            <div style="font-size:1.1rem;">{format_brl(saldo)}</div>
        </div>
        """, unsafe_allow_html=True)

def render_card_conta(row):
    status_visual = status_conta(row["data_vencimento"], row["status"])

    if status_visual == "Pago":
        classe = "status-pago"
    elif status_visual == "Atrasado":
        classe = "status-atrasado"
    else:
        classe = "status-pendente"

    origem = row["origem"] if pd.notna(row["origem"]) else "Manual"
    origem_classe = "origem-fixa" if origem == "Fixa" else "origem-manual"

    st.markdown(f"""
    <div class="card">
        <div style="display:flex; justify-content:space-between; align-items:center;">
            <div>
                <div><b>{row['descricao']}</b></div>
                <div class="small-text">
                    Categoria: {row['categoria']}<br>
                    Vencimento: {row['data_vencimento']}<br>
                    Origem: <span class="{origem_classe}">{origem}</span>
                </div>
            </div>
            <div style="text-align:right;">
                <div class="{classe}">{format_brl(row['valor'])}</div>
                <div class="{classe}">{status_visual}</div>
            </div>
        </div>
    </div>
    """, unsafe_allow_html=True)

# =========================================================
# APP
# =========================================================
def main():
    init_db()
    gerar_contas_fixas_automaticamente()

    st.title("💸 Gestão Financeira Pessoal — V6 Completa")

    # -----------------------------------------------------
    # CARREGAR DADOS
    # -----------------------------------------------------
    df_lan = db_fetch_df("SELECT * FROM lancamentos ORDER BY data DESC, id DESC")
    df_prev = db_fetch_df("SELECT * FROM contas_previstas ORDER BY data_vencimento ASC, id ASC")
    df_fixas = db_fetch_df("SELECT * FROM contas_fixas ORDER BY descricao ASC")
    df_orc = db_fetch_df("SELECT * FROM orcamentos")

    if df_lan.empty:
        df_lan = pd.DataFrame(columns=["id", "data", "descricao", "tipo", "categoria", "banco", "valor"])

    if df_prev.empty:
        df_prev = pd.DataFrame(columns=[
            "id", "descricao", "categoria", "valor", "data_vencimento", "status",
            "banco_pagamento", "data_pagamento", "origem", "fixa_id"
        ])

    if df_fixas.empty:
        df_fixas = pd.DataFrame(columns=[
            "id", "descricao", "categoria", "valor", "dia_vencimento", "data_inicio", "ativa"
        ])

    # -----------------------------------------------------
    # RESUMO
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

    render_saldos(df_lan)
    st.divider()

    # -----------------------------------------------------
    # NOVOS CADASTROS
    # -----------------------------------------------------
    with st.expander("➕ Novo Lançamento / Conta / Conta Fixa / Transferência", expanded=False):
        t1, t2, t3, t4 = st.tabs([
            "💰 Receita Real",
            "📝 Conta Avulsa",
            "🔁 Conta Fixa",
            "📲 Transferência"
        ])

        # Receita
        with t1:
            with st.form("f_rec", clear_on_submit=True):
                col_a, col_b = st.columns(2)
                dat = col_a.date_input("Data do recebimento", date.today())
                val = col_b.number_input("Valor R$", min_value=0.0, step=0.01)
                desc = st.text_input("Descrição (Ex: Salário, Freelance)")
                ban = st.selectbox("Banco de destino", BANCOS)

                if st.form_submit_button("Registrar Entrada"):
                    if not desc.strip():
                        st.warning("Informe uma descrição.")
                    elif val <= 0:
                        st.warning("Informe um valor maior que zero.")
                    else:
                        db_execute("""
                            INSERT INTO lancamentos (data, descricao, tipo, categoria, banco, valor)
                            VALUES (?, ?, 'Receita', ?, ?, ?)
                        """, (dat.isoformat(), desc.strip(), "Salário", ban, val))
                        st.success("Receita registrada!")
                        st.rerun()

        # Conta avulsa
        with t2:
            with st.form("f_prev", clear_on_submit=True):
                col_a, col_b = st.columns(2)
                venc = col_a.date_input("Vencimento", date.today())
                val_p = col_b.number_input("Valor R$", min_value=0.0, step=0.01, key="v_p")
                desc_p = st.text_input("Descrição da conta")
                cat_p = st.selectbox("Categoria", CATEGORIAS, key="cat_avulsa")
                recorr = st.checkbox("Gerar 12 meses (recorrência manual)")

                if st.form_submit_button("Salvar Conta Avulsa"):
                    if not desc_p.strip():
                        st.warning("Informe a descrição.")
                    elif val_p <= 0:
                        st.warning("Informe um valor maior que zero.")
                    else:
                        meses = 12 if recorr else 1
                        for i in range(meses):
                            data_v = (venc + relativedelta(months=i)).isoformat()
                            sufixo = f" ({i+1}/{meses})" if recorr else ""
                            db_execute("""
                                INSERT INTO contas_previstas (
                                    descricao, categoria, valor, data_vencimento, origem
                                )
                                VALUES (?, ?, ?, ?, 'Manual')
                            """, (f"{desc_p.strip()}{sufixo}", cat_p, val_p, data_v))
                        st.success("Conta(s) salva(s)!")
                        st.rerun()

        # Conta fixa
        with t3:
            with st.form("f_fixa", clear_on_submit=True):
                desc_f = st.text_input("Descrição da conta fixa")
                col_f1, col_f2, col_f3 = st.columns(3)
                cat_f = col_f1.selectbox("Categoria", CATEGORIAS, key="cat_fixa")
                val_f = col_f2.number_input("Valor R$", min_value=0.0, step=0.01, key="val_fixa")
                dia_f = col_f3.number_input("Dia vencimento", min_value=1, max_value=31, step=1, value=10)

                data_inicio_f = st.date_input("Início da recorrência", date.today().replace(day=1))
                ativa_f = st.checkbox("Ativa", value=True)

                if st.form_submit_button("Salvar Conta Fixa"):
                    if not desc_f.strip():
                        st.warning("Informe a descrição.")
                    elif val_f <= 0:
                        st.warning("Informe um valor maior que zero.")
                    else:
                        db_execute("""
                            INSERT INTO contas_fixas (
                                descricao, categoria, valor, dia_vencimento, data_inicio, ativa
                            )
                            VALUES (?, ?, ?, ?, ?, ?)
                        """, (
                            desc_f.strip(), cat_f, val_f, int(dia_f),
                            data_inicio_f.isoformat(), 1 if ativa_f else 0
                        ))
                        st.success("Conta fixa salva!")
                        st.rerun()

        # Transferência
        with t4:
            with st.form("f_trf", clear_on_submit=True):
                v_trf = st.number_input("Valor da transferência", min_value=0.0, step=0.01)
                o = st.selectbox("Origem", BANCOS, key="origem_trf")
                d = st.selectbox("Destino", [b for b in BANCOS if b != o], key="destino_trf")

                if st.form_submit_button("Transferir"):
                    if v_trf <= 0:
                        st.warning("Informe um valor maior que zero.")
                    else:
                        dt = date.today().isoformat()

                        db_execute("""
                            INSERT INTO lancamentos (data, descricao, tipo, categoria, banco, valor)
                            VALUES (?, ?, 'Despesa', 'Transferência', ?, ?)
                        """, (dt, f"TRF para {d}", o, v_trf))

                        db_execute("""
                            INSERT INTO lancamentos (data, descricao, tipo, categoria, banco, valor)
                            VALUES (?, ?, 'Receita', 'Transferência', ?, ?)
                        """, (dt, f"TRF de {o}", d, v_trf))

                        st.success("Transferência realizada!")
                        st.rerun()

    st.divider()

    # -----------------------------------------------------
    # CONTAS DO MÊS
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

    m1, m2, m3 = st.columns(3)
    m1.metric("Total do mês", format_brl(total_mes))
    m2.metric("Pendente", format_brl(total_pendente_mes))
    m3.metric("Pago", format_brl(total_pago_mes))

    if df_mes.empty:
        st.info("Nenhuma conta cadastrada para este mês.")
    else:
        for _, row in df_mes.iterrows():
            render_card_conta(row)

            # AÇÕES RÁPIDAS
            cA, cB, cC = st.columns([2, 1, 1])

            # PAGAR / DESFAZER
            if row["status"] == "Pendente":
                banco_pagto = cA.selectbox(
                    f"Banco para pagar - {row['descricao']}",
                    BANCOS,
                    key=f"banco_pagto_{row['id']}",
                    label_visibility="collapsed"
                )
                if cB.button("✔ Pagar", key=f"btn_pagar_{row['id']}"):
                    sucesso, msg = pagar_conta(row["id"], banco_pagto, date.today().isoformat())
                    if sucesso:
                        st.success(msg)
                        st.rerun()
                    else:
                        st.error(msg)
            else:
                banco_info = row["banco_pagamento"] if pd.notna(row["banco_pagamento"]) else "-"
                data_info = row["data_pagamento"] if pd.notna(row["data_pagamento"]) else "-"
                cA.caption(f"Pago em: {data_info} | Banco: {banco_info}")

                if cB.button("↩️ Desfazer", key=f"btn_desfazer_{row['id']}"):
                    sucesso, msg = desfazer_pagamento(row["id"])
                    if sucesso:
                        st.success(msg)
                        st.rerun()
                    else:
                        st.error(msg)

            # EXCLUIR
            if cC.button("🗑 Excluir", key=f"btn_excluir_{row['id']}"):
                sucesso, msg = excluir_conta(row["id"])
                if sucesso:
                    st.success(msg)
                    st.rerun()
                else:
                    st.error(msg)

            # EDIÇÃO DA CONTA
            with st.expander(f"✏️ Editar conta: {row['descricao']}", expanded=False):
                with st.form(f"form_edit_conta_{row['id']}"):
                    e1, e2 = st.columns(2)
                    desc_e = e1.text_input("Descrição", value=row["descricao"], key=f"desc_{row['id']}")
                    cat_e = e2.selectbox(
                        "Categoria", CATEGORIAS,
                        index=CATEGORIAS.index(row["categoria"]) if row["categoria"] in CATEGORIAS else 0,
                        key=f"cat_{row['id']}"
                    )

                    e3, e4 = st.columns(2)
                    val_e = e3.number_input(
                        "Valor R$",
                        min_value=0.0,
                        step=0.01,
                        value=float(row["valor"]),
                        key=f"val_{row['id']}"
                    )
                    venc_e = e4.date_input(
                        "Vencimento",
                        value=pd.to_datetime(row["data_vencimento"]).date(),
                        key=f"venc_{row['id']}"
                    )

                    status_opts = ["Pendente", "Pago"]
                    status_atual = row["status"] if row["status"] in status_opts else "Pendente"

                    e5, e6 = st.columns(2)
                    status_e = e5.selectbox(
                        "Status",
                        status_opts,
                        index=status_opts.index(status_atual),
                        key=f"status_{row['id']}"
                    )

                    banco_atual = row["banco_pagamento"] if pd.notna(row["banco_pagamento"]) and row["banco_pagamento"] in BANCOS else BANCOS[0]
                    banco_e = e6.selectbox(
                        "Banco pagamento (se pago)",
                        BANCOS,
                        index=BANCOS.index(banco_atual),
                        key=f"banco_edit_{row['id']}"
                    )

                    data_pagto_default = (
                        pd.to_datetime(row["data_pagamento"]).date()
                        if pd.notna(row["data_pagamento"])
                        else date.today()
                    )
                    data_pagto_e = st.date_input(
                        "Data pagamento (se pago)",
                        value=data_pagto_default,
                        key=f"data_pagto_{row['id']}"
                    )

                    if st.form_submit_button("Salvar alterações"):
                        banco_final = banco_e if status_e == "Pago" else None
                        data_final = data_pagto_e.isoformat() if status_e == "Pago" else None

                        sucesso, msg = atualizar_conta_prevista(
                            row["id"],
                            desc_e.strip(),
                            cat_e,
                            val_e,
                            venc_e.isoformat(),
                            status_e,
                            banco_final,
                            data_final
                        )
                        if sucesso:
                            st.success(msg)
                            st.rerun()
                        else:
                            st.error(msg)

            st.markdown("---")

    # -----------------------------------------------------
    # CONTAS FIXAS (MODELOS) - TODAS EDITÁVEIS
    # -----------------------------------------------------
    st.subheader("🔁 Contas Fixas (Modelos)")
    st.caption("As contas fixas geram automaticamente contas mensais. O modelo e as contas geradas são editáveis.")

    if df_fixas.empty:
        st.info("Nenhuma conta fixa cadastrada.")
    else:
        for _, fixa in df_fixas.iterrows():
            ativa_txt = "Ativa" if int(fixa["ativa"]) == 1 else "Inativa"

            st.markdown(f"""
            <div class="card">
                <div style="display:flex; justify-content:space-between; align-items:center;">
                    <div>
                        <div><b>{fixa['descricao']}</b></div>
                        <div class="small-text">
                            Categoria: {fixa['categoria']}<br>
                            Valor padrão: {format_brl(fixa['valor'])}<br>
                            Dia vencimento: {int(fixa['dia_vencimento'])}<br>
                            Início: {fixa['data_inicio']}
                        </div>
                    </div>
                    <div style="text-align:right;">
                        <div class="origem-fixa">{ativa_txt}</div>
                    </div>
                </div>
            </div>
            """, unsafe_allow_html=True)

            cfx1, cfx2 = st.columns([3, 1])
            with cfx1.expander(f"✏️ Editar conta fixa: {fixa['descricao']}", expanded=False):
                with st.form(f"form_edit_fixa_{fixa['id']}"):
                    fx1, fx2 = st.columns(2)
                    desc_fx = fx1.text_input("Descrição", value=fixa["descricao"], key=f"desc_fx_{fixa['id']}")
                    cat_fx = fx2.selectbox(
                        "Categoria",
                        CATEGORIAS,
                        index=CATEGORIAS.index(fixa["categoria"]) if fixa["categoria"] in CATEGORIAS else 0,
                        key=f"cat_fx_{fixa['id']}"
                    )

                    fx3, fx4 = st.columns(2)
                    val_fx = fx3.number_input(
                        "Valor padrão R$",
                        min_value=0.0,
                        step=0.01,
                        value=float(fixa["valor"]),
                        key=f"val_fx_{fixa['id']}"
                    )
                    dia_fx = fx4.number_input(
                        "Dia vencimento",
                        min_value=1,
                        max_value=31,
                        step=1,
                        value=int(fixa["dia_vencimento"]),
                        key=f"dia_fx_{fixa['id']}"
                    )

                    data_inicio_fx = st.date_input(
                        "Data início",
                        value=pd.to_datetime(fixa["data_inicio"]).date(),
                        key=f"inicio_fx_{fixa['id']}"
                    )

                    ativa_fx = st.checkbox(
                        "Ativa",
                        value=(int(fixa["ativa"]) == 1),
                        key=f"ativa_fx_{fixa['id']}"
                    )

                    if st.form_submit_button("Salvar conta fixa"):
                        sucesso, msg = atualizar_conta_fixa(
                            fixa["id"],
                            desc_fx.strip(),
                            cat_fx,
                            val_fx,
                            int(dia_fx),
                            data_inicio_fx.isoformat(),
                            1 if ativa_fx else 0
                        )
                        if sucesso:
                            st.success(msg)
                            st.rerun()
                        else:
                            st.error(msg)

            if cfx2.button("🗑 Excluir fixa", key=f"del_fixa_{fixa['id']}"):
                sucesso, msg = excluir_conta_fixa(fixa["id"])
                if sucesso:
                    st.success(msg)
                    st.rerun()
                else:
                    st.error(msg)

            st.markdown("---")

    # -----------------------------------------------------
    # PRÓXIMAS CONTAS
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
            mostrar_fut = df_futuras.copy()
            mostrar_fut["valor"] = mostrar_fut["valor"].apply(format_brl)
            st.dataframe(
                mostrar_fut[["descricao", "categoria", "valor", "data_vencimento", "status", "origem"]],
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
    with st.expander("🧾 Histórico Completo de Contas"):
        if df_prev.empty:
            st.info("Nenhuma conta cadastrada.")
        else:
            mostrar = df_prev.copy()
            mostrar["valor"] = mostrar["valor"].apply(format_brl)
            st.dataframe(
                mostrar[[
                    "descricao", "categoria", "valor", "data_vencimento",
                    "status", "banco_pagamento", "data_pagamento", "origem", "fixa_id"
                ]].sort_values(by=["data_vencimento"], ascending=False),
                use_container_width=True
            )

if __name__ == "__main__":
    main()
