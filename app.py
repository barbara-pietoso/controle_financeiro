import streamlit as st
import sqlite3
import pandas as pd
from datetime import date, datetime
from dateutil.relativedelta import relativedelta

# =========================================================
# CONFIGURAÇÃO
# =========================================================
st.set_page_config(page_title="Finanças Pro V7", page_icon="💳", layout="wide")

DB_NAME = "financeiro_pro_v7.db"

BANCOS = ["Banco do Brasil", "Banrisul", "Nubank", "Itaú", "Flash (VA)"]
CATEGORIAS = [
    "Salário", "Alimentação", "Mercado", "Transporte", "Moradia",
    "Lazer", "Saúde", "Assinaturas", "Dívidas", "Educação", "Outros"
]

# =========================================================
# ESTILO
# =========================================================
st.markdown("""
<style>
    .main .block-container { padding: 1rem 0.7rem; }
    .card {
        background: #ffffff;
        border: 1px solid #e2e8f0;
        border-radius: 12px;
        padding: 14px;
        margin-bottom: 10px;
        box-shadow: 0 2px 6px rgba(0,0,0,0.04);
    }
    .status-pago { color: #059669; font-weight: 700; }
    .status-pendente { color: #ea580c; font-weight: 700; }
    .status-negativo { color: #dc2626; font-weight: 700; }
    .small-text { font-size: 0.85rem; color: #64748b; }
    .stButton>button { border-radius: 8px; }
</style>
""", unsafe_allow_html=True)

# =========================================================
# HELPERS
# =========================================================
def format_brl(v):
    return f"R$ {v:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")

def get_conn():
    return sqlite3.connect(DB_NAME, check_same_thread=False)

def db_execute(query, params=()):
    conn = get_conn()
    c = conn.cursor()
    c.execute(query, params)
    conn.commit()
    conn.close()

def db_executemany(query, seq):
    conn = get_conn()
    c = conn.cursor()
    c.executemany(query, seq)
    conn.commit()
    conn.close()

def query_df(query, params=()):
    conn = get_conn()
    df = pd.read_sql_query(query, conn, params=params)
    conn.close()
    return df

def safe_float(x):
    try:
        return float(x)
    except:
        return 0.0

def month_start(d=None):
    d = d or date.today()
    return d.replace(day=1)

def month_end(d=None):
    d = d or date.today()
    first = d.replace(day=1)
    return first + relativedelta(months=1) - relativedelta(days=1)

def parse_date(s):
    return datetime.strptime(s, "%Y-%m-%d").date()

# =========================================================
# BANCO DE DADOS
# =========================================================
def init_db():
    conn = get_conn()
    c = conn.cursor()

    # Lançamentos reais
    c.execute("""
    CREATE TABLE IF NOT EXISTS lancamentos (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        data TEXT,
        descricao TEXT,
        tipo TEXT,              -- Receita / Despesa
        categoria TEXT,
        banco TEXT,
        valor REAL
    )
    """)

    # Contas previstas / contas a pagar
    c.execute("""
    CREATE TABLE IF NOT EXISTS contas_previstas (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        descricao TEXT,
        categoria TEXT,
        valor REAL,
        data_vencimento TEXT,
        status TEXT DEFAULT 'Pendente', -- Pendente / Pago
        banco_pagamento TEXT,
        data_pagamento TEXT
    )
    """)

    # Metas por categoria
    c.execute("""
    CREATE TABLE IF NOT EXISTS orcamentos (
        categoria TEXT PRIMARY KEY,
        meta REAL
    )
    """)

    # Cartões
    c.execute("""
    CREATE TABLE IF NOT EXISTS cartoes (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        nome TEXT UNIQUE,
        banco_padrao TEXT,
        fechamento_dia INTEGER,   -- ex 25
        vencimento_dia INTEGER,   -- ex 05
        limite REAL DEFAULT 0
    )
    """)

    # Compras no cartão (cabeçalho)
    c.execute("""
    CREATE TABLE IF NOT EXISTS compras_cartao (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        data_compra TEXT,
        descricao TEXT,
        categoria TEXT,
        cartao_id INTEGER,
        valor_total REAL,
        parcelas INTEGER DEFAULT 1,
        observacao TEXT,
        FOREIGN KEY(cartao_id) REFERENCES cartoes(id)
    )
    """)

    # Parcelas geradas da compra
    c.execute("""
    CREATE TABLE IF NOT EXISTS parcelas_cartao (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        compra_id INTEGER,
        cartao_id INTEGER,
        parcela_num INTEGER,
        total_parcelas INTEGER,
        valor_parcela REAL,
        competencia_fatura TEXT,      -- YYYY-MM (mês da fatura)
        vencimento_fatura TEXT,       -- data de vencimento da fatura
        status TEXT DEFAULT 'Aberta', -- Aberta / Paga
        fatura_id INTEGER,
        FOREIGN KEY(compra_id) REFERENCES compras_cartao(id),
        FOREIGN KEY(cartao_id) REFERENCES cartoes(id)
    )
    """)

    # Faturas
    c.execute("""
    CREATE TABLE IF NOT EXISTS faturas_cartao (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        cartao_id INTEGER,
        competencia TEXT,             -- YYYY-MM
        vencimento TEXT,
        valor_total REAL DEFAULT 0,
        status TEXT DEFAULT 'Aberta', -- Aberta / Paga
        banco_pagamento TEXT,
        data_pagamento TEXT,
        UNIQUE(cartao_id, competencia),
        FOREIGN KEY(cartao_id) REFERENCES cartoes(id)
    )
    """)

    conn.commit()
    conn.close()

# =========================================================
# REGRAS DE NEGÓCIO
# =========================================================
def get_saldos_por_banco():
    df = query_df("SELECT banco, tipo, valor FROM lancamentos")
    saldos = {b: 0.0 for b in BANCOS}
    if not df.empty:
        for b in BANCOS:
            receitas = df[(df["banco"] == b) & (df["tipo"] == "Receita")]["valor"].sum()
            despesas = df[(df["banco"] == b) & (df["tipo"] == "Despesa")]["valor"].sum()
            saldos[b] = float(receitas - despesas)
    return saldos

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

def estorno_pagamento_conta(id_conta):
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

    desc, cat, valor, status, banco_pag, data_pag = conta

    if status != "Pago":
        conn.close()
        return False, "A conta não está paga."

    # Remove 1 lançamento correspondente mais recente
    lanc = c.execute("""
        SELECT id FROM lancamentos
        WHERE descricao=? AND tipo='Despesa' AND categoria=? AND banco=? AND valor=?
        ORDER BY id DESC
        LIMIT 1
    """, (f"PAGTO: {desc}", cat, banco_pag, valor)).fetchone()

    if lanc:
        c.execute("DELETE FROM lancamentos WHERE id=?", (lanc[0],))

    c.execute("""
        UPDATE contas_previstas
        SET status='Pendente',
            banco_pagamento=NULL,
            data_pagamento=NULL
        WHERE id=?
    """, (id_conta,))

    conn.commit()
    conn.close()
    return True, "Pagamento estornado com sucesso."

def calcular_competencia_e_vencimento(data_compra, fechamento_dia, vencimento_dia):
    """
    Regra:
    - Se compra <= dia de fechamento => entra na fatura do mês atual
    - Se compra > fechamento => entra na fatura do próximo mês
    - Vencimento é no mês seguinte ao da competência, no dia de vencimento
    """
    d = parse_date(data_compra)

    if d.day <= fechamento_dia:
        competencia_date = d.replace(day=1)
    else:
        competencia_date = (d.replace(day=1) + relativedelta(months=1))

    # vencimento = mês seguinte da competência
    venc_base = competencia_date + relativedelta(months=1)
    ultimo_dia = month_end(venc_base).day
    dia_venc = min(vencimento_dia, ultimo_dia)
    vencimento = venc_base.replace(day=dia_venc)

    competencia = competencia_date.strftime("%Y-%m")
    return competencia, vencimento.isoformat()

def garantir_fatura(cartao_id, competencia, vencimento):
    conn = get_conn()
    c = conn.cursor()

    fat = c.execute("""
        SELECT id FROM faturas_cartao
        WHERE cartao_id=? AND competencia=?
    """, (cartao_id, competencia)).fetchone()

    if fat:
        fatura_id = fat[0]
    else:
        c.execute("""
            INSERT INTO faturas_cartao (cartao_id, competencia, vencimento, valor_total, status)
            VALUES (?, ?, ?, 0, 'Aberta')
        """, (cartao_id, competencia, vencimento))
        fatura_id = c.lastrowid

    conn.commit()
    conn.close()
    return fatura_id

def recalcular_fatura(fatura_id):
    conn = get_conn()
    c = conn.cursor()

    fatura = c.execute("""
        SELECT id, status FROM faturas_cartao WHERE id=?
    """, (fatura_id,)).fetchone()

    if not fatura:
        conn.close()
        return

    total = c.execute("""
        SELECT COALESCE(SUM(valor_parcela), 0)
        FROM parcelas_cartao
        WHERE fatura_id=?
    """, (fatura_id,)).fetchone()[0]

    c.execute("""
        UPDATE faturas_cartao
        SET valor_total=?
        WHERE id=?
    """, (total, fatura_id))

    conn.commit()
    conn.close()

def recalcular_todas_faturas():
    df = query_df("SELECT id FROM faturas_cartao")
    for _, row in df.iterrows():
        recalcular_fatura(int(row["id"]))

def cadastrar_compra_cartao(data_compra, descricao, categoria, cartao_id, valor_total, parcelas, observacao=""):
    conn = get_conn()
    c = conn.cursor()

    cartao = c.execute("""
        SELECT fechamento_dia, vencimento_dia
        FROM cartoes
        WHERE id=?
    """, (cartao_id,)).fetchone()

    if not cartao:
        conn.close()
        return False, "Cartão não encontrado."

    fechamento_dia, vencimento_dia = cartao

    c.execute("""
        INSERT INTO compras_cartao (data_compra, descricao, categoria, cartao_id, valor_total, parcelas, observacao)
        VALUES (?, ?, ?, ?, ?, ?, ?)
    """, (data_compra, descricao, categoria, cartao_id, valor_total, parcelas, observacao))
    compra_id = c.lastrowid

    valor_parcela = round(valor_total / parcelas, 2)
    valores = [valor_parcela] * parcelas
    diferenca = round(valor_total - sum(valores), 2)
    valores[-1] = round(valores[-1] + diferenca, 2)

    parcelas_rows = []
    faturas_para_recalcular = set()

    data_base = parse_date(data_compra)

    for i in range(parcelas):
        data_parcela_compra = (data_base + relativedelta(months=i)).isoformat()
        competencia, vencimento = calcular_competencia_e_vencimento(
            data_parcela_compra, fechamento_dia, vencimento_dia
        )
        fatura_id = garantir_fatura(cartao_id, competencia, vencimento)
        faturas_para_recalcular.add(fatura_id)

        parcelas_rows.append((
            compra_id, cartao_id, i + 1, parcelas, valores[i],
            competencia, vencimento, "Aberta", fatura_id
        ))

    c.executemany("""
        INSERT INTO parcelas_cartao (
            compra_id, cartao_id, parcela_num, total_parcelas,
            valor_parcela, competencia_fatura, vencimento_fatura,
            status, fatura_id
        )
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
    """, parcelas_rows)

    conn.commit()
    conn.close()

    for fid in faturas_para_recalcular:
        recalcular_fatura(fid)

    return True, "Compra no cartão cadastrada com sucesso."

def excluir_compra_cartao(compra_id):
    conn = get_conn()
    c = conn.cursor()

    faturas = c.execute("""
        SELECT DISTINCT fatura_id FROM parcelas_cartao WHERE compra_id=?
    """, (compra_id,)).fetchall()

    c.execute("DELETE FROM parcelas_cartao WHERE compra_id=?", (compra_id,))
    c.execute("DELETE FROM compras_cartao WHERE id=?", (compra_id,))

    conn.commit()
    conn.close()

    for f in faturas:
        if f[0]:
            recalcular_fatura(f[0])

def pagar_fatura(fatura_id, banco, data_pagamento):
    conn = get_conn()
    c = conn.cursor()

    fatura = c.execute("""
        SELECT f.id, f.cartao_id, f.competencia, f.vencimento, f.valor_total, f.status, c.nome
        FROM faturas_cartao f
        JOIN cartoes c ON c.id = f.cartao_id
        WHERE f.id=?
    """, (fatura_id,)).fetchone()

    if not fatura:
        conn.close()
        return False, "Fatura não encontrada."

    _, cartao_id, competencia, vencimento, valor_total, status, nome_cartao = fatura

    if status == "Paga":
        conn.close()
        return False, "Essa fatura já está paga."

    # Permite saldo negativo
    c.execute("""
        INSERT INTO lancamentos (data, descricao, tipo, categoria, banco, valor)
        VALUES (?, ?, 'Despesa', 'Cartão de Crédito', ?, ?)
    """, (data_pagamento, f"FATURA {nome_cartao} {competencia}", banco, valor_total))

    c.execute("""
        UPDATE faturas_cartao
        SET status='Paga',
            banco_pagamento=?,
            data_pagamento=?
        WHERE id=?
    """, (banco, data_pagamento, fatura_id))

    c.execute("""
        UPDATE parcelas_cartao
        SET status='Paga'
        WHERE fatura_id=?
    """, (fatura_id,))

    conn.commit()
    conn.close()
    return True, "Fatura paga com sucesso."

def estornar_pagamento_fatura(fatura_id):
    conn = get_conn()
    c = conn.cursor()

    fatura = c.execute("""
        SELECT f.id, f.competencia, f.valor_total, f.status, f.banco_pagamento, c.nome
        FROM faturas_cartao f
        JOIN cartoes c ON c.id = f.cartao_id
        WHERE f.id=?
    """, (fatura_id,)).fetchone()

    if not fatura:
        conn.close()
        return False, "Fatura não encontrada."

    _, competencia, valor_total, status, banco_pagamento, nome_cartao = fatura

    if status != "Paga":
        conn.close()
        return False, "A fatura não está paga."

    lanc = c.execute("""
        SELECT id FROM lancamentos
        WHERE descricao=? AND tipo='Despesa' AND categoria='Cartão de Crédito' AND banco=? AND valor=?
        ORDER BY id DESC
        LIMIT 1
    """, (f"FATURA {nome_cartao} {competencia}", banco_pagamento, valor_total)).fetchone()

    if lanc:
        c.execute("DELETE FROM lancamentos WHERE id=?", (lanc[0],))

    c.execute("""
        UPDATE faturas_cartao
        SET status='Aberta',
            banco_pagamento=NULL,
            data_pagamento=NULL
        WHERE id=?
    """, (fatura_id,))

    c.execute("""
        UPDATE parcelas_cartao
        SET status='Aberta'
        WHERE fatura_id=?
    """, (fatura_id,))

    conn.commit()
    conn.close()
    return True, "Pagamento da fatura estornado com sucesso."

# =========================================================
# UI DE EDIÇÃO GENÉRICA
# =========================================================
def editor_lancamentos():
    st.subheader("✏️ Editar / Excluir Lançamentos Reais")
    df = query_df("SELECT * FROM lancamentos ORDER BY data DESC, id DESC")
    if df.empty:
        st.info("Sem lançamentos ainda.")
        return

    for _, row in df.iterrows():
        with st.expander(f"#{int(row['id'])} | {row['data']} | {row['descricao']} | {format_brl(row['valor'])}"):
            with st.form(f"edit_lanc_{int(row['id'])}"):
                c1, c2, c3 = st.columns(3)
                data_e = c1.date_input("Data", parse_date(row["data"]), key=f"ld_{row['id']}")
                desc_e = c2.text_input("Descrição", row["descricao"], key=f"l_desc_{row['id']}")
                tipo_e = c3.selectbox("Tipo", ["Receita", "Despesa"], index=0 if row["tipo"] == "Receita" else 1, key=f"l_tipo_{row['id']}")

                c4, c5, c6 = st.columns(3)
                cat_e = c4.text_input("Categoria", row["categoria"], key=f"l_cat_{row['id']}")
                banco_e = c5.selectbox("Banco", BANCOS, index=BANCOS.index(row["banco"]) if row["banco"] in BANCOS else 0, key=f"l_banco_{row['id']}")
                valor_e = c6.number_input("Valor", min_value=0.0, value=float(row["valor"]), step=0.01, key=f"l_val_{row['id']}")

                s1, s2 = st.columns(2)
                if s1.form_submit_button("💾 Salvar Alterações"):
                    db_execute("""
                        UPDATE lancamentos
                        SET data=?, descricao=?, tipo=?, categoria=?, banco=?, valor=?
                        WHERE id=?
                    """, (data_e.isoformat(), desc_e, tipo_e, cat_e, banco_e, valor_e, int(row["id"])))
                    st.success("Lançamento atualizado.")
                    st.rerun()

                if s2.form_submit_button("🗑 Excluir"):
                    db_execute("DELETE FROM lancamentos WHERE id=?", (int(row["id"]),))
                    st.success("Lançamento excluído.")
                    st.rerun()

def editor_contas_previstas():
    st.subheader("📝 Editar / Excluir Contas Previstas")
    df = query_df("SELECT * FROM contas_previstas ORDER BY data_vencimento ASC, id ASC")
    if df.empty:
        st.info("Sem contas previstas.")
        return

    for _, row in df.iterrows():
        status = "🟢 Pago" if row["status"] == "Pago" else "🟠 Pendente"
        with st.expander(f"#{int(row['id'])} | {row['descricao']} | {format_brl(row['valor'])} | {row['data_vencimento']} | {status}"):
            with st.form(f"edit_prev_{int(row['id'])}"):
                c1, c2, c3 = st.columns(3)
                desc_e = c1.text_input("Descrição", row["descricao"], key=f"p_desc_{row['id']}")
                cat_e = c2.selectbox("Categoria", CATEGORIAS, index=CATEGORIAS.index(row["categoria"]) if row["categoria"] in CATEGORIAS else len(CATEGORIAS)-1, key=f"p_cat_{row['id']}")
                val_e = c3.number_input("Valor", min_value=0.0, value=float(row["valor"]), step=0.01, key=f"p_val_{row['id']}")

                c4, c5 = st.columns(2)
                venc_e = c4.date_input("Vencimento", parse_date(row["data_vencimento"]), key=f"p_venc_{row['id']}")
                status_e = c5.selectbox("Status", ["Pendente", "Pago"], index=0 if row["status"] == "Pendente" else 1, key=f"p_status_{row['id']}")

                st.caption("⚠️ Se mudar para 'Pago' manualmente aqui, isso NÃO cria lançamento automático. Para registrar no saldo, use o botão 'Pagar' na lista de contas.")

                s1, s2 = st.columns(2)
                if s1.form_submit_button("💾 Salvar Alterações"):
                    db_execute("""
                        UPDATE contas_previstas
                        SET descricao=?, categoria=?, valor=?, data_vencimento=?, status=?
                        WHERE id=?
                    """, (desc_e, cat_e, val_e, venc_e.isoformat(), status_e, int(row["id"])))
                    st.success("Conta prevista atualizada.")
                    st.rerun()

                if s2.form_submit_button("🗑 Excluir"):
                    if row["status"] == "Pago":
                        st.warning("Se quiser remover uma conta paga, idealmente estorne antes para não deixar lançamento solto.")
                    db_execute("DELETE FROM contas_previstas WHERE id=?", (int(row["id"]),))
                    st.success("Conta prevista excluída.")
                    st.rerun()

def editor_cartoes():
    st.subheader("💳 Editar / Excluir Cartões")
    df = query_df("SELECT * FROM cartoes ORDER BY nome")
    if df.empty:
        st.info("Nenhum cartão cadastrado.")
        return

    for _, row in df.iterrows():
        with st.expander(f"#{int(row['id'])} | {row['nome']}"):
            with st.form(f"edit_card_{int(row['id'])}"):
                c1, c2 = st.columns(2)
                nome_e = c1.text_input("Nome do cartão", row["nome"], key=f"card_nome_{row['id']}")
                banco_e = c2.selectbox("Banco padrão pagador", BANCOS, index=BANCOS.index(row["banco_padrao"]) if row["banco_padrao"] in BANCOS else 0, key=f"card_banco_{row['id']}")

                c3, c4, c5 = st.columns(3)
                fechamento_e = c3.number_input("Dia fechamento", min_value=1, max_value=31, value=int(row["fechamento_dia"]), key=f"card_fech_{row['id']}")
                venc_e = c4.number_input("Dia vencimento", min_value=1, max_value=31, value=int(row["vencimento_dia"]), key=f"card_venc_{row['id']}")
                limite_e = c5.number_input("Limite", min_value=0.0, value=float(row["limite"]), step=0.01, key=f"card_lim_{row['id']}")

                s1, s2 = st.columns(2)
                if s1.form_submit_button("💾 Salvar Alterações"):
                    try:
                        db_execute("""
                            UPDATE cartoes
                            SET nome=?, banco_padrao=?, fechamento_dia=?, vencimento_dia=?, limite=?
                            WHERE id=?
                        """, (nome_e, banco_e, int(fechamento_e), int(venc_e), limite_e, int(row["id"])))
                        st.success("Cartão atualizado.")
                        st.rerun()
                    except Exception as e:
                        st.error(f"Erro ao atualizar cartão: {e}")

                if s2.form_submit_button("🗑 Excluir"):
                    st.warning("⚠️ Excluir cartão com compras/faturas vinculadas pode deixar histórico inconsistente. Faça isso apenas se tiver certeza.")
                    db_execute("DELETE FROM cartoes WHERE id=?", (int(row["id"]),))
                    st.success("Cartão excluído.")
                    st.rerun()

def editor_compras_cartao():
    st.subheader("🛒 Editar / Excluir Compras no Cartão")
    df = query_df("""
        SELECT cc.*, c.nome as nome_cartao
        FROM compras_cartao cc
        JOIN cartoes c ON c.id = cc.cartao_id
        ORDER BY cc.data_compra DESC, cc.id DESC
    """)
    if df.empty:
        st.info("Sem compras no cartão.")
        return

    cartoes_df = query_df("SELECT * FROM cartoes ORDER BY nome")
    if cartoes_df.empty:
        st.warning("Cadastre cartões primeiro.")
        return

    cartoes_map = {int(r["id"]): r["nome"] for _, r in cartoes_df.iterrows()}
    cartoes_ids = list(cartoes_map.keys())

    for _, row in df.iterrows():
        titulo = f"#{int(row['id'])} | {row['data_compra']} | {row['descricao']} | {row['nome_cartao']} | {format_brl(row['valor_total'])} | {int(row['parcelas'])}x"
        with st.expander(titulo):
            st.warning("⚠️ Se alterar valor, parcelas, data ou cartão, as parcelas/faturas precisam ser recriadas. Use 'Regravar compra' abaixo.")

            with st.form(f"edit_compra_{int(row['id'])}"):
                c1, c2, c3 = st.columns(3)
                data_e = c1.date_input("Data da compra", parse_date(row["data_compra"]), key=f"cp_data_{row['id']}")
                desc_e = c2.text_input("Descrição", row["descricao"], key=f"cp_desc_{row['id']}")
                cat_e = c3.selectbox("Categoria", CATEGORIAS, index=CATEGORIAS.index(row["categoria"]) if row["categoria"] in CATEGORIAS else len(CATEGORIAS)-1, key=f"cp_cat_{row['id']}")

                idx_cartao = cartoes_ids.index(int(row["cartao_id"])) if int(row["cartao_id"]) in cartoes_ids else 0
                c4, c5, c6 = st.columns(3)
                cartao_e_id = c4.selectbox(
                    "Cartão",
                    options=cartoes_ids,
                    format_func=lambda x: cartoes_map[x],
                    index=idx_cartao,
                    key=f"cp_card_{row['id']}"
                )
                val_e = c5.number_input("Valor total", min_value=0.0, value=float(row["valor_total"]), step=0.01, key=f"cp_val_{row['id']}")
                parc_e = c6.number_input("Parcelas", min_value=1, max_value=36, value=int(row["parcelas"]), key=f"cp_parc_{row['id']}")

                obs_e = st.text_input("Observação", row["observacao"] if row["observacao"] else "", key=f"cp_obs_{row['id']}")

                s1, s2 = st.columns(2)
                if s1.form_submit_button("♻️ Regravar compra (recria parcelas/faturas)"):
                    # Excluir e recriar
                    compra_id = int(row["id"])
                    excluir_compra_cartao(compra_id)
                    ok, msg = cadastrar_compra_cartao(
                        data_e.isoformat(), desc_e, cat_e, int(cartao_e_id),
                        float(val_e), int(parc_e), obs_e
                    )
                    if ok:
                        st.success("Compra regravada com sucesso.")
                    else:
                        st.error(msg)
                    st.rerun()

                if s2.form_submit_button("🗑 Excluir Compra"):
                    excluir_compra_cartao(int(row["id"]))
                    st.success("Compra excluída.")
                    st.rerun()

# =========================================================
# APP
# =========================================================
def main():
    init_db()
    recalcular_todas_faturas()

    st.title("💸 Finanças Pro V7 — Cartão + Parcelamento + Fatura Automática")

    # -----------------------------------------------------
    # DADOS BASE
    # -----------------------------------------------------
    df_lan = query_df("SELECT * FROM lancamentos")
    df_prev_pend = query_df("""
        SELECT * FROM contas_previstas
        WHERE status='Pendente'
        ORDER BY data_vencimento ASC, id ASC
    """)
    df_prev_all = query_df("SELECT * FROM contas_previstas")
    df_cartoes = query_df("SELECT * FROM cartoes ORDER BY nome")
    df_faturas = query_df("""
        SELECT f.*, c.nome as nome_cartao, c.banco_padrao
        FROM faturas_cartao f
        JOIN cartoes c ON c.id = f.cartao_id
        ORDER BY f.vencimento ASC, f.id ASC
    """)

    # -----------------------------------------------------
    # RESUMO
    # -----------------------------------------------------
    saldo_atual = 0.0
    if not df_lan.empty:
        saldo_atual = df_lan[df_lan["tipo"] == "Receita"]["valor"].sum() - df_lan[df_lan["tipo"] == "Despesa"]["valor"].sum()

    contas_pendentes = 0.0 if df_prev_pend.empty else df_prev_pend["valor"].sum()

    faturas_abertas = 0.0
    if not df_faturas.empty:
        faturas_abertas = df_faturas[df_faturas["status"] == "Aberta"]["valor_total"].sum()

    saldo_projetado = saldo_atual - contas_pendentes - faturas_abertas

    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Saldo Atual", format_brl(saldo_atual))
    c2.metric("Contas a Pagar", format_brl(contas_pendentes), delta_color="inverse")
    c3.metric("Faturas Abertas", format_brl(faturas_abertas), delta_color="inverse")
    c4.metric("Projeção Final", format_brl(saldo_projetado))

    st.divider()

    # -----------------------------------------------------
    # CADASTROS / AÇÕES
    # -----------------------------------------------------
    with st.expander("➕ Novo Lançamento / Conta / Transferência / Cartão / Compra"):
        t1, t2, t3, t4, t5 = st.tabs([
            "💰 Receita/Despesa Real",
            "📝 Conta a Pagar",
            "📲 Transferência",
            "💳 Cartões",
            "🛒 Compra no Cartão"
        ])

        # -----------------------------
        # T1 - Lançamento real
        # -----------------------------
        with t1:
            with st.form("f_lanc_real", clear_on_submit=True):
                c1, c2, c3 = st.columns(3)
                data_l = c1.date_input("Data", date.today())
                tipo_l = c2.selectbox("Tipo", ["Receita", "Despesa"])
                valor_l = c3.number_input("Valor R$", min_value=0.0, step=0.01)

                c4, c5, c6 = st.columns(3)
                desc_l = c4.text_input("Descrição")
                cat_l = c5.selectbox("Categoria", CATEGORIAS)
                banco_l = c6.selectbox("Banco", BANCOS)

                if st.form_submit_button("Registrar Lançamento"):
                    if valor_l <= 0:
                        st.warning("Informe um valor maior que zero.")
                    else:
                        db_execute("""
                            INSERT INTO lancamentos (data, descricao, tipo, categoria, banco, valor)
                            VALUES (?, ?, ?, ?, ?, ?)
                        """, (data_l.isoformat(), desc_l, tipo_l, cat_l, banco_l, valor_l))
                        st.success("Lançamento registrado.")
                        st.rerun()

        # -----------------------------
        # T2 - Conta prevista
        # -----------------------------
        with t2:
            with st.form("f_prev", clear_on_submit=True):
                c1, c2, c3 = st.columns(3)
                venc = c1.date_input("Vencimento", date.today())
                val_p = c2.number_input("Valor R$", min_value=0.0, step=0.01)
                cat_p = c3.selectbox("Categoria", CATEGORIAS, key="cat_prev")

                desc_p = st.text_input("Descrição (Ex: Aluguel, Internet, Luz)")
                recorr = st.checkbox("É recorrente? (lançar por vários meses)")
                qtd_meses = 12
                if recorr:
                    qtd_meses = st.number_input("Quantos meses?", min_value=1, max_value=60, value=12)

                if st.form_submit_button("Agendar Conta"):
                    if val_p <= 0:
                        st.warning("Informe um valor maior que zero.")
                    elif not desc_p.strip():
                        st.warning("Informe uma descrição.")
                    else:
                        meses = int(qtd_meses) if recorr else 1
                        for i in range(meses):
                            data_v = (venc + relativedelta(months=i)).isoformat()
                            sufixo = f" ({i+1}/{meses})" if recorr and meses > 1 else ""
                            db_execute("""
                                INSERT INTO contas_previstas (descricao, categoria, valor, data_vencimento)
                                VALUES (?, ?, ?, ?)
                            """, (f"{desc_p}{sufixo}", cat_p, val_p, data_v))
                        st.success("Conta(s) agendada(s).")
                        st.rerun()

        # -----------------------------
        # T3 - Transferência
        # -----------------------------
        with t3:
            with st.form("f_trf", clear_on_submit=True):
                c1, c2, c3 = st.columns(3)
                v_trf = c1.number_input("Valor", min_value=0.0, step=0.01)
                o = c2.selectbox("Origem", BANCOS)
                d = c3.selectbox("Destino", [b for b in BANCOS if b != o])

                if st.form_submit_button("Transferir"):
                    if v_trf <= 0:
                        st.warning("Informe um valor maior que zero.")
                    else:
                        dt = date.today().isoformat()

                        # Permite saldo negativo
                        db_execute("""
                            INSERT INTO lancamentos (data, descricao, tipo, categoria, banco, valor)
                            VALUES (?, ?, 'Despesa', 'Transferência', ?, ?)
                        """, (dt, f"TRF para {d}", o, v_trf))

                        db_execute("""
                            INSERT INTO lancamentos (data, descricao, tipo, categoria, banco, valor)
                            VALUES (?, ?, 'Receita', 'Transferência', ?, ?)
                        """, (dt, f"TRF de {o}", d, v_trf))

                        st.success("Transferência realizada.")
                        st.rerun()

        # -----------------------------
        # T4 - Cartões
        # -----------------------------
        with t4:
            with st.form("f_cartao", clear_on_submit=True):
                c1, c2 = st.columns(2)
                nome_c = c1.text_input("Nome do cartão (Ex: Nubank Roxinho)")
                banco_padrao = c2.selectbox("Banco pagador padrão", BANCOS)

                c3, c4, c5 = st.columns(3)
                fechamento = c3.number_input("Dia de fechamento", min_value=1, max_value=31, value=25)
                vencimento = c4.number_input("Dia de vencimento", min_value=1, max_value=31, value=5)
                limite = c5.number_input("Limite (opcional)", min_value=0.0, step=0.01)

                if st.form_submit_button("Cadastrar Cartão"):
                    if not nome_c.strip():
                        st.warning("Informe o nome do cartão.")
                    else:
                        try:
                            db_execute("""
                                INSERT INTO cartoes (nome, banco_padrao, fechamento_dia, vencimento_dia, limite)
                                VALUES (?, ?, ?, ?, ?)
                            """, (nome_c.strip(), banco_padrao, int(fechamento), int(vencimento), limite))
                            st.success("Cartão cadastrado.")
                            st.rerun()
                        except Exception as e:
                            st.error(f"Erro ao cadastrar cartão: {e}")

        # -----------------------------
        # T5 - Compra no cartão
        # -----------------------------
        with t5:
            if df_cartoes.empty:
                st.info("Cadastre um cartão primeiro.")
            else:
                cartoes_map = {int(r["id"]): r["nome"] for _, r in df_cartoes.iterrows()}
                cartoes_ids = list(cartoes_map.keys())

                with st.form("f_compra_cartao", clear_on_submit=True):
                    c1, c2, c3 = st.columns(3)
                    data_compra = c1.date_input("Data da compra", date.today())
                    desc_compra = c2.text_input("Descrição da compra")
                    cat_compra = c3.selectbox("Categoria", CATEGORIAS, key="cat_compra")

                    c4, c5, c6 = st.columns(3)
                    cartao_id = c4.selectbox(
                        "Cartão",
                        options=cartoes_ids,
                        format_func=lambda x: cartoes_map[x]
                    )
                    valor_compra = c5.number_input("Valor total", min_value=0.0, step=0.01)
                    parcelas = c6.number_input("Parcelas", min_value=1, max_value=36, value=1)

                    obs = st.text_input("Observação (opcional)")

                    if st.form_submit_button("Registrar Compra no Cartão"):
                        if valor_compra <= 0:
                            st.warning("Informe um valor maior que zero.")
                        elif not desc_compra.strip():
                            st.warning("Informe a descrição da compra.")
                        else:
                            ok, msg = cadastrar_compra_cartao(
                                data_compra.isoformat(),
                                desc_compra.strip(),
                                cat_compra,
                                int(cartao_id),
                                float(valor_compra),
                                int(parcelas),
                                obs
                            )
                            if ok:
                                st.success(msg)
                            else:
                                st.error(msg)
                            st.rerun()

    st.divider()

    # -----------------------------------------------------
    # CONTAS PENDENTES
    # -----------------------------------------------------
    st.subheader("🗓️ Contas a Pagar (Pendentes)")
    if df_prev_pend.empty:
        st.info("Nenhuma conta pendente 🎉")
    else:
        for _, row in df_prev_pend.iterrows():
            with st.container():
                st.markdown(f"""
                <div class="card">
                    <div style="display:flex; justify-content:space-between; gap:10px;">
                        <b>{row['descricao']}</b>
                        <span class="status-pendente">{format_brl(row['valor'])}</span>
                    </div>
                    <div class="small-text">Vencimento: {row['data_vencimento']} | Categoria: {row['categoria']}</div>
                </div>
                """, unsafe_allow_html=True)

                c1, c2 = st.columns([2, 1])
                banco_pagto = c1.selectbox("Pagar com:", BANCOS, key=f"b_{row['id']}")
                if c2.button("✔ Pagar", key=f"btn_{row['id']}"):
                    ok, msg = pagar_conta(int(row["id"]), banco_pagto, date.today().isoformat())
                    if ok:
                        st.success(msg)
                    else:
                        st.error(msg)
                    st.rerun()

    st.divider()

    # -----------------------------------------------------
    # FATURAS DE CARTÃO
    # -----------------------------------------------------
    st.subheader("💳 Faturas de Cartão")
    if df_faturas.empty:
        st.info("Nenhuma fatura gerada ainda.")
    else:
        for _, row in df_faturas.iterrows():
            status_css = "status-pago" if row["status"] == "Paga" else "status-pendente"
            with st.container():
                st.markdown(f"""
                <div class="card">
                    <div style="display:flex; justify-content:space-between; gap:10px;">
                        <b>{row['nome_cartao']} — Fatura {row['competencia']}</b>
                        <span class="{status_css}">{format_brl(row['valor_total'])}</span>
                    </div>
                    <div class="small-text">
                        Vencimento: {row['vencimento']} | Status: {row['status']} | Banco padrão: {row['banco_padrao']}
                    </div>
                </div>
                """, unsafe_allow_html=True)

                if row["status"] == "Aberta":
                    c1, c2 = st.columns([2, 1])
                    banco_fat = c1.selectbox(
                        "Pagar fatura com:",
                        BANCOS,
                        index=BANCOS.index(row["banco_padrao"]) if row["banco_padrao"] in BANCOS else 0,
                        key=f"fat_b_{row['id']}"
                    )
                    if c2.button("💸 Pagar Fatura", key=f"fat_btn_{row['id']}"):
                        ok, msg = pagar_fatura(int(row["id"]), banco_fat, date.today().isoformat())
                        if ok:
                            st.success(msg)
                        else:
                            st.error(msg)
                        st.rerun()
                else:
                    c1, c2 = st.columns([2, 1])
                    c1.write(f"Pago em {row['data_pagamento']} via {row['banco_pagamento']}")
                    if c2.button("↩️ Estornar Fatura", key=f"est_fat_{row['id']}"):
                        ok, msg = estornar_pagamento_fatura(int(row["id"]))
                        if ok:
                            st.success(msg)
                        else:
                            st.error(msg)
                        st.rerun()

                with st.expander(f"Ver parcelas da fatura #{int(row['id'])}"):
                    df_parc = query_df("""
                        SELECT p.*, cc.descricao, cc.categoria
                        FROM parcelas_cartao p
                        JOIN compras_cartao cc ON cc.id = p.compra_id
                        WHERE p.fatura_id=?
                        ORDER BY p.id ASC
                    """, (int(row["id"]),))
                    if df_parc.empty:
                        st.info("Sem parcelas nessa fatura.")
                    else:
                        st.dataframe(df_parc[[
                            "descricao", "categoria", "parcela_num", "total_parcelas",
                            "valor_parcela", "competencia_fatura", "vencimento_fatura", "status"
                        ]], use_container_width=True)

    st.divider()

    # -----------------------------------------------------
    # ORÇAMENTO
    # -----------------------------------------------------
    st.subheader("📊 Orçamento vs Realizado (mês atual)")
    with st.expander("Configurar Metas por Categoria"):
        c1, c2 = st.columns(2)
        cat_meta = c1.selectbox("Categoria", CATEGORIAS, key="cat_meta")
        val_meta = c2.number_input("Meta Mensal R$", min_value=0.0, step=0.01)

        if st.button("Salvar Meta"):
            db_execute("""
                INSERT OR REPLACE INTO orcamentos (categoria, meta)
                VALUES (?, ?)
            """, (cat_meta, val_meta))
            st.success("Meta salva.")
            st.rerun()

    df_orc = query_df("SELECT * FROM orcamentos")
    inicio_mes = month_start().isoformat()
    fim_mes = month_end().isoformat()

    df_gastos_mes = query_df("""
        SELECT categoria, valor
        FROM lancamentos
        WHERE tipo='Despesa'
          AND categoria NOT IN ('Transferência')
          AND data >= ?
          AND data <= ?
    """, (inicio_mes, fim_mes))

    if df_orc.empty:
        st.info("Nenhuma meta cadastrada.")
    else:
        for _, m in df_orc.iterrows():
            realizado = 0.0
            if not df_gastos_mes.empty:
                realizado = df_gastos_mes[df_gastos_mes["categoria"] == m["categoria"]]["valor"].sum()
            meta = safe_float(m["meta"])
            progresso = min(realizado / meta, 1.0) if meta > 0 else 0

            st.write(f"**{m['categoria']}**")
            c1, c2 = st.columns([4, 1])
            c1.progress(progresso)
            c2.write(f"{format_brl(realizado)} / {format_brl(meta)}")

    st.divider()

    # -----------------------------------------------------
    # SALDO POR BANCO
    # -----------------------------------------------------
    st.subheader("🏦 Saldo Detalhado por Banco")
    saldos = get_saldos_por_banco()
    cols = st.columns(len(BANCOS))
    for i, b in enumerate(BANCOS):
        saldo = saldos.get(b, 0.0)
        if saldo < 0:
            cols[i].markdown(f"**{b}**\n\n<span class='status-negativo'>{format_brl(saldo)}</span>", unsafe_allow_html=True)
        else:
            cols[i].markdown(f"**{b}**\n\n<span class='status-pago'>{format_brl(saldo)}</span>", unsafe_allow_html=True)

    st.divider()

    # -----------------------------------------------------
    # EDIÇÃO COMPLETA
    # -----------------------------------------------------
    with st.expander("✏️ Área de Edição Completa (tudo editável)"):
        e1, e2, e3, e4 = st.tabs([
            "Lançamentos Reais",
            "Contas Previstas",
            "Cartões",
            "Compras no Cartão"
        ])

        with e1:
            editor_lancamentos()

        with e2:
            editor_contas_previstas()

        with e3:
            editor_cartoes()

        with e4:
            editor_compras_cartao()

    st.divider()

    # -----------------------------------------------------
    # HISTÓRICOS / TABELAS
    # -----------------------------------------------------
    with st.expander("📚 Histórico Geral"):
        h1, h2, h3, h4 = st.tabs([
            "Lançamentos",
            "Contas Previstas",
            "Faturas",
            "Parcelas"
        ])

        with h1:
            df = query_df("SELECT * FROM lancamentos ORDER BY data DESC, id DESC")
            st.dataframe(df, use_container_width=True)

        with h2:
            df = query_df("SELECT * FROM contas_previstas ORDER BY data_vencimento ASC, id ASC")
            st.dataframe(df, use_container_width=True)

        with h3:
            df = query_df("""
                SELECT f.*, c.nome as nome_cartao
                FROM faturas_cartao f
                JOIN cartoes c ON c.id = f.cartao_id
                ORDER BY f.vencimento DESC, f.id DESC
            """)
            st.dataframe(df, use_container_width=True)

        with h4:
            df = query_df("""
                SELECT p.*, cc.descricao, c.nome as nome_cartao
                FROM parcelas_cartao p
                JOIN compras_cartao cc ON cc.id = p.compra_id
                JOIN cartoes c ON c.id = p.cartao_id
                ORDER BY p.vencimento_fatura DESC, p.id DESC
            """)
            st.dataframe(df, use_container_width=True)

if __name__ == "__main__":
    main()
