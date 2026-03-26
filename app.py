import streamlit as st
import pandas as pd
from datetime import date, datetime
from database import (
    criar_tabelas,
    inserir_lancamento,
    listar_lancamentos,
    buscar_lancamento_por_id,
    atualizar_lancamento,
    excluir_lancamento,
    inserir_divida,
    listar_dividas,
    listar_dividas_abertas,
    buscar_divida_por_id,
    atualizar_divida,
    excluir_divida,
    registrar_pagamento_divida,
    listar_pagamentos_dividas
)

# =========================================================
# CONFIG
# =========================================================
st.set_page_config(
    page_title="App Financeiro",
    page_icon="💰",
    layout="wide"
)

criar_tabelas()

# =========================================================
# CONSTANTES
# =========================================================
TIPOS_ENTRADA = ["Salário", "Freela", "Show"]

CATEGORIAS_DESPESA = [
    "Alimentação",
    "Transporte",
    "Moradia",
    "Contas Fixas",
    "Lazer",
    "Saúde",
    "Educação",
    "Cartão de Crédito",
    "Compras",
    "Outros"
]

# =========================================================
# FUNÇÕES AUXILIARES
# =========================================================
def formatar_brl(valor):
    return f"R$ {valor:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")

def parse_data(valor):
    if pd.isna(valor) or valor is None or valor == "":
        return date.today()
    try:
        return pd.to_datetime(valor).date()
    except:
        return date.today()

def estilo_personalizado():
    st.markdown("""
        <style>
        .block-container {
            padding-top: 1.2rem;
            padding-bottom: 2rem;
        }

        .titulo-app {
            font-size: 2.2rem;
            font-weight: 800;
            margin-bottom: 0.3rem;
        }

        .subtitulo-app {
            color: #6b7280;
            margin-bottom: 1rem;
        }

        .caixa-secao {
            padding: 1rem;
            border: 1px solid rgba(128,128,128,0.2);
            border-radius: 16px;
            margin-bottom: 1rem;
            background: rgba(250,250,250,0.7);
        }

        .stMetric {
            border: 1px solid rgba(128,128,128,0.15);
            border-radius: 16px;
            padding: 0.5rem;
            background: rgba(250,250,250,0.7);
        }

        hr {
            margin-top: 1rem !important;
            margin-bottom: 1rem !important;
        }
        </style>
    """, unsafe_allow_html=True)

def carregar_dados():
    df_lanc = listar_lancamentos()
    df_dividas = listar_dividas()
    df_dividas_abertas = listar_dividas_abertas()
    df_pagamentos = listar_pagamentos_dividas()

    if not df_lanc.empty:
        df_lanc["valor"] = pd.to_numeric(df_lanc["valor"], errors="coerce").fillna(0)
        df_lanc["data"] = pd.to_datetime(df_lanc["data"], errors="coerce")

    if not df_dividas.empty:
        df_dividas["valor_total"] = pd.to_numeric(df_dividas["valor_total"], errors="coerce").fillna(0)
        df_dividas["valor_restante"] = pd.to_numeric(df_dividas["valor_restante"], errors="coerce").fillna(0)
        df_dividas["data_criacao"] = pd.to_datetime(df_dividas["data_criacao"], errors="coerce")

    if not df_pagamentos.empty:
        df_pagamentos["valor_pago"] = pd.to_numeric(df_pagamentos["valor_pago"], errors="coerce").fillna(0)
        df_pagamentos["data_pagamento"] = pd.to_datetime(df_pagamentos["data_pagamento"], errors="coerce")

    return df_lanc, df_dividas, df_dividas_abertas, df_pagamentos

# =========================================================
# ESTILO
# =========================================================
estilo_personalizado()

# =========================================================
# HEADER
# =========================================================
st.markdown('<div class="titulo-app">💰 App Financeiro Pessoal</div>', unsafe_allow_html=True)
st.markdown('<div class="subtitulo-app">Controle de entradas, despesas e dívidas em uma única tela</div>', unsafe_allow_html=True)

# =========================================================
# DADOS
# =========================================================
df_lanc, df_dividas, df_dividas_abertas, df_pagamentos = carregar_dados()

# =========================================================
# CÁLCULOS GERAIS
# =========================================================
if not df_lanc.empty:
    total_entradas = df_lanc[df_lanc["tipo"] == "Entrada"]["valor"].sum()
    total_despesas = df_lanc[df_lanc["tipo"] == "Despesa"]["valor"].sum()
else:
    total_entradas = 0
    total_despesas = 0

saldo_atual = total_entradas - total_despesas

if not df_dividas.empty:
    total_dividas_abertas = df_dividas["valor_restante"].sum()
    total_dividas = df_dividas["valor_total"].sum()
    total_pago_dividas = total_dividas - total_dividas_abertas
else:
    total_dividas_abertas = 0
    total_dividas = 0
    total_pago_dividas = 0

# =========================================================
# RESUMO FINANCEIRO
# =========================================================
st.subheader("📊 Resumo Financeiro")

m1, m2, m3, m4, m5 = st.columns(5)
m1.metric("💵 Entradas", formatar_brl(total_entradas))
m2.metric("💸 Despesas", formatar_brl(total_despesas))
m3.metric("📈 Saldo Atual", formatar_brl(saldo_atual))
m4.metric("📌 Dívidas em Aberto", formatar_brl(total_dividas_abertas))
m5.metric("🧾 Total Pago em Dívidas", formatar_brl(total_pago_dividas))

st.divider()

# =========================================================
# FORMULÁRIOS PRINCIPAIS
# =========================================================
col_form1, col_form2 = st.columns(2)

# -------------------------
# NOVO LANÇAMENTO
# -------------------------
with col_form1:
    st.subheader("➕ Novo Lançamento")

    with st.container(border=True):
        with st.form("form_novo_lancamento"):
            data_lanc = st.date_input("Data", value=date.today(), key="novo_lanc_data")
            tipo_lanc = st.radio("Tipo", ["Entrada", "Despesa"], horizontal=True, key="novo_lanc_tipo")

            if tipo_lanc == "Entrada":
                categoria_lanc = st.selectbox("Categoria", TIPOS_ENTRADA, key="novo_lanc_cat_entrada")
                descricao_lanc = st.text_input("Descrição (opcional)", placeholder="Ex: Cachê, cliente, evento...", key="novo_lanc_desc_entrada")
            else:
                categoria_lanc = st.selectbox("Categoria", CATEGORIAS_DESPESA, key="novo_lanc_cat_despesa")
                descricao_lanc = st.text_input("Descrição (opcional)", placeholder="Ex: Mercado, aluguel, Uber...", key="novo_lanc_desc_despesa")

            valor_lanc = st.number_input("Valor", min_value=0.01, format="%.2f", key="novo_lanc_valor")

            salvar_lanc = st.form_submit_button("Salvar lançamento")

            if salvar_lanc:
                inserir_lancamento(
                    data=str(data_lanc),
                    tipo=tipo_lanc,
                    categoria=categoria_lanc,
                    descricao=descricao_lanc.strip(),
                    valor=valor_lanc
                )
                st.success("Lançamento salvo com sucesso!")
                st.rerun()

# -------------------------
# NOVA DÍVIDA
# -------------------------
with col_form2:
    st.subheader("📌 Nova Dívida")

    with st.container(border=True):
        with st.form("form_nova_divida"):
            credor = st.text_input("Credor / Pessoa", placeholder="Ex: João, Maria, Banco X")
            descricao_divida = st.text_input("Descrição", placeholder="Ex: Empréstimo, ajuda, parcela...")
            valor_total_divida = st.number_input("Valor total", min_value=0.01, format="%.2f")
            data_divida = st.date_input("Data da dívida", value=date.today(), key="nova_divida_data")

            salvar_divida = st.form_submit_button("Salvar dívida")

            if salvar_divida:
                if not credor.strip():
                    st.error("Informe o nome do credor.")
                else:
                    inserir_divida(
                        credor=credor.strip(),
                        descricao=descricao_divida.strip(),
                        valor_total=valor_total_divida,
                        data_criacao=str(data_divida)
                    )
                    st.success("Dívida cadastrada com sucesso!")
                    st.rerun()

st.divider()

# =========================================================
# PAGAMENTO DE DÍVIDA
# =========================================================
st.subheader("💳 Registrar Pagamento de Dívida")

with st.container(border=True):
    if not df_dividas_abertas.empty:
        df_dividas_abertas = df_dividas_abertas.copy()
        df_dividas_abertas["label"] = df_dividas_abertas.apply(
            lambda row: f"ID {row['id']} - {row['credor']} | Restante: {formatar_brl(row['valor_restante'])}",
            axis=1
        )

        mapa_dividas = dict(zip(df_dividas_abertas["label"], df_dividas_abertas["id"]))

        with st.form("form_pagamento_divida"):
            p1, p2, p3, p4 = st.columns(4)

            with p1:
                divida_label = st.selectbox("Dívida", list(mapa_dividas.keys()))

            with p2:
                data_pagamento = st.date_input("Data do pagamento", value=date.today(), key="pag_div_data")

            with p3:
                valor_pago = st.number_input("Valor pago", min_value=0.01, format="%.2f", key="pag_div_valor")

            with p4:
                observacao_pag = st.text_input("Observação", placeholder="Ex: 1ª parcela")

            pagar = st.form_submit_button("Registrar pagamento")

            if pagar:
                divida_id = mapa_dividas[divida_label]
                sucesso, mensagem = registrar_pagamento_divida(
                    divida_id=divida_id,
                    data_pagamento=str(data_pagamento),
                    valor_pago=valor_pago,
                    observacao=observacao_pag.strip()
                )

                if sucesso:
                    st.success(mensagem)
                    st.info("Esse pagamento foi lançado automaticamente em DESPESAS.")
                    st.rerun()
                else:
                    st.error(mensagem)
    else:
        st.info("Você não possui dívidas em aberto no momento.")

st.divider()

# =========================================================
# GRÁFICOS
# =========================================================
g1, g2 = st.columns(2)

with g1:
    st.subheader("📈 Despesas por Categoria")
    with st.container(border=True):
        if not df_lanc.empty:
            despesas_cat = df_lanc[df_lanc["tipo"] == "Despesa"].groupby("categoria")["valor"].sum()
            if not despesas_cat.empty:
                st.bar_chart(despesas_cat)
            else:
                st.info("Ainda não há despesas cadastradas.")
        else:
            st.info("Nenhum lançamento cadastrado.")

with g2:
    st.subheader("💵 Entradas por Tipo")
    with st.container(border=True):
        if not df_lanc.empty:
            entradas_cat = df_lanc[df_lanc["tipo"] == "Entrada"].groupby("categoria")["valor"].sum()
            if not entradas_cat.empty:
                st.bar_chart(entradas_cat)
            else:
                st.info("Ainda não há entradas cadastradas.")
        else:
            st.info("Nenhum lançamento cadastrado.")

st.divider()

# =========================================================
# LANÇAMENTOS - VISUALIZAR / EDITAR / EXCLUIR
# =========================================================
st.subheader("📋 Lançamentos")

with st.container(border=True):
    if not df_lanc.empty:
        # Filtros
        f1, f2, f3 = st.columns(3)

        with f1:
            filtro_tipo = st.selectbox("Filtrar por tipo", ["Todos", "Entrada", "Despesa"], key="filtro_lanc_tipo")

        with f2:
            categorias_disp = ["Todas"] + sorted(df_lanc["categoria"].dropna().unique().tolist())
            filtro_categoria = st.selectbox("Filtrar por categoria", categorias_disp, key="filtro_lanc_cat")

        with f3:
            meses_disp = ["Todos"] + sorted(df_lanc["data"].dt.strftime("%m/%Y").dropna().unique().tolist(), reverse=True)
            filtro_mes = st.selectbox("Filtrar por mês", meses_disp, key="filtro_lanc_mes")

        df_lanc_filtrado = df_lanc.copy()

        if filtro_tipo != "Todos":
            df_lanc_filtrado = df_lanc_filtrado[df_lanc_filtrado["tipo"] == filtro_tipo]

        if filtro_categoria != "Todas":
            df_lanc_filtrado = df_lanc_filtrado[df_lanc_filtrado["categoria"] == filtro_categoria]

        if filtro_mes != "Todos":
            df_lanc_filtrado = df_lanc_filtrado[df_lanc_filtrado["data"].dt.strftime("%m/%Y") == filtro_mes]

        total_filtrado = df_lanc_filtrado["valor"].sum() if not df_lanc_filtrado.empty else 0
        st.metric("Total do filtro", formatar_brl(total_filtrado))

        # Exibição formatada
        df_exibir = df_lanc_filtrado.copy()
        df_exibir["data"] = df_exibir["data"].dt.strftime("%d/%m/%Y")
        df_exibir["valor_formatado"] = df_exibir["valor"].apply(formatar_brl)

        st.dataframe(
            df_exibir[["id", "data", "tipo", "categoria", "descricao", "valor_formatado"]],
            use_container_width=True
        )

        st.markdown("### ✏️ Editar Lançamento")

        id_editar_lanc = st.selectbox("Selecione o ID do lançamento", df_lanc["id"].tolist(), key="editar_lanc_id")
        lanc = buscar_lancamento_por_id(id_editar_lanc)

        if lanc:
            _, lanc_data, lanc_tipo, lanc_categoria, lanc_descricao, lanc_valor = lanc

            with st.form("form_editar_lancamento"):
                e1, e2, e3 = st.columns(3)

                with e1:
                    nova_data_lanc = st.date_input("Data", value=parse_data(lanc_data), key="edit_lanc_data")

                with e2:
                    novo_tipo_lanc = st.selectbox(
                        "Tipo",
                        ["Entrada", "Despesa"],
                        index=0 if lanc_tipo == "Entrada" else 1,
                        key="edit_lanc_tipo"
                    )

                with e3:
                    if novo_tipo_lanc == "Entrada":
                        idx_cat = TIPOS_ENTRADA.index(lanc_categoria) if lanc_categoria in TIPOS_ENTRADA else 0
                        nova_categoria_lanc = st.selectbox("Categoria", TIPOS_ENTRADA, index=idx_cat, key="edit_lanc_cat_entrada")
                    else:
                        idx_cat = CATEGORIAS_DESPESA.index(lanc_categoria) if lanc_categoria in CATEGORIAS_DESPESA else 0
                        nova_categoria_lanc = st.selectbox("Categoria", CATEGORIAS_DESPESA, index=idx_cat, key="edit_lanc_cat_despesa")

                novo_desc_lanc = st.text_input("Descrição", value=lanc_descricao or "", key="edit_lanc_desc")
                novo_valor_lanc = st.number_input("Valor", min_value=0.01, value=float(lanc_valor), format="%.2f", key="edit_lanc_valor")

                salvar_edicao_lanc = st.form_submit_button("Salvar alterações do lançamento")

                if salvar_edicao_lanc:
                    atualizar_lancamento(
                        id_lancamento=id_editar_lanc,
                        data=str(nova_data_lanc),
                        tipo=novo_tipo_lanc,
                        categoria=nova_categoria_lanc,
                        descricao=novo_desc_lanc.strip(),
                        valor=novo_valor_lanc
                    )
                    st.success("Lançamento atualizado com sucesso!")
                    st.rerun()

        st.markdown("### 🗑️ Excluir Lançamento")
        id_excluir_lanc = st.selectbox("Selecione o ID para excluir", df_lanc["id"].tolist(), key="excluir_lanc_id")

        if st.button("Excluir lançamento"):
            excluir_lancamento(id_excluir_lanc)
            st.success(f"Lançamento {id_excluir_lanc} excluído com sucesso!")
            st.rerun()
    else:
        st.info("Nenhum lançamento cadastrado ainda.")

st.divider()

# =========================================================
# DÍVIDAS - VISUALIZAR / EDITAR / EXCLUIR
# =========================================================
st.subheader("📌 Dívidas")

d1, d2 = st.columns(2)

# -------------------------
# TABELA DE DÍVIDAS
# -------------------------
with d1:
    with st.container(border=True):
        st.markdown("### 📋 Dívidas Cadastradas")

        if not df_dividas.empty:
            df_div_exibir = df_dividas.copy()
            df_div_exibir["data_criacao"] = df_div_exibir["data_criacao"].dt.strftime("%d/%m/%Y")
            df_div_exibir["valor_total_fmt"] = df_div_exibir["valor_total"].apply(formatar_brl)
            df_div_exibir["valor_restante_fmt"] = df_div_exibir["valor_restante"].apply(formatar_brl)

            st.dataframe(
                df_div_exibir[[
                    "id", "credor", "descricao", "valor_total_fmt", "valor_restante_fmt", "data_criacao", "status"
                ]],
                use_container_width=True
            )
        else:
            st.info("Nenhuma dívida cadastrada.")

# -------------------------
# HISTÓRICO DE PAGAMENTOS
# -------------------------
with d2:
    with st.container(border=True):
        st.markdown("### 🧾 Histórico de Pagamentos")

        if not df_pagamentos.empty:
            df_pag_exibir = df_pagamentos.copy()
            df_pag_exibir["data_pagamento"] = df_pag_exibir["data_pagamento"].dt.strftime("%d/%m/%Y")
            df_pag_exibir["valor_pago_fmt"] = df_pag_exibir["valor_pago"].apply(formatar_brl)

            st.dataframe(
                df_pag_exibir[[
                    "id", "divida_id", "credor", "descricao_divida", "data_pagamento", "valor_pago_fmt", "observacao"
                ]],
                use_container_width=True
            )
        else:
            st.info("Nenhum pagamento registrado ainda.")

st.markdown("### ✏️ Editar Dívida")

with st.container(border=True):
    if not df_dividas.empty:
        id_editar_divida = st.selectbox("Selecione o ID da dívida", df_dividas["id"].tolist(), key="editar_divida_id")
        div = buscar_divida_por_id(id_editar_divida)

        if div:
            _, credor_atual, desc_atual, valor_total_atual, valor_restante_atual, data_criacao_atual, status_atual = div

            with st.form("form_editar_divida"):
                ed1, ed2, ed3 = st.columns(3)

                with ed1:
                    novo_credor = st.text_input("Credor", value=credor_atual or "")

                with ed2:
                    novo_valor_total = st.number_input("Valor total", min_value=0.01, value=float(valor_total_atual), format="%.2f")

                with ed3:
                    novo_valor_restante = st.number_input("Valor restante", min_value=0.00, value=float(valor_restante_atual), format="%.2f")

                nova_desc_divida = st.text_input("Descrição", value=desc_atual or "")
                nova_data_divida = st.date_input("Data da dívida", value=parse_data(data_criacao_atual), key="edit_divida_data")

                salvar_edicao_divida = st.form_submit_button("Salvar alterações da dívida")

                if salvar_edicao_divida:
                    if not novo_credor.strip():
                        st.error("Informe o nome do credor.")
                    elif novo_valor_restante > novo_valor_total:
                        st.error("O valor restante não pode ser maior que o valor total.")
                    else:
                        atualizar_divida(
                            divida_id=id_editar_divida,
                            credor=novo_credor.strip(),
                            descricao=nova_desc_divida.strip(),
                            valor_total=novo_valor_total,
                            valor_restante=novo_valor_restante,
                            data_criacao=str(nova_data_divida)
                        )
                        st.success("Dívida atualizada com sucesso!")
                        st.rerun()
    else:
        st.info("Nenhuma dívida cadastrada para editar.")

st.markdown("### 🗑️ Excluir Dívida")

with st.container(border=True):
    if not df_dividas.empty:
        id_excluir_divida = st.selectbox("Selecione o ID da dívida para excluir", df_dividas["id"].tolist(), key="excluir_divida_id")

        if st.button("Excluir dívida"):
            excluir_divida(id_excluir_divida)
            st.success(f"Dívida {id_excluir_divida} excluída com sucesso!")
            st.rerun()
    else:
        st.info("Nenhuma dívida cadastrada para excluir.")
