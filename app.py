import streamlit as st
import pandas as pd
from datetime import date
from database import (
    criar_tabelas,
    inserir_lancamento,
    listar_lancamentos,
    excluir_lancamento,
    inserir_divida,
    listar_dividas,
    pagar_divida,
    excluir_divida
)

# =========================
# CONFIGURAÇÃO DA PÁGINA
# =========================
st.set_page_config(
    page_title="Controle Financeiro",
    page_icon="💰",
    layout="wide"
)

# =========================
# BANCO / TABELAS
# =========================
criar_tabelas()

# =========================
# CONSTANTES
# =========================
CATEGORIAS_RECEITA = ["Salário", "Freela", "Show"]

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
    "Outros"
]

# =========================
# FUNÇÕES AUXILIARES
# =========================
def formatar_brl(valor):
    try:
        return f"R$ {float(valor):,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")
    except:
        return "R$ 0,00"

def preparar_lancamentos(df):
    if df.empty:
        return df

    df = df.copy()
    df["valor"] = pd.to_numeric(df["valor"], errors="coerce").fillna(0)
    df["data"] = pd.to_datetime(df["data"], errors="coerce")
    df["mes"] = df["data"].dt.to_period("M").astype(str)
    return df

def preparar_dividas(df):
    if df.empty:
        return df

    df = df.copy()
    df["valor_total"] = pd.to_numeric(df["valor_total"], errors="coerce").fillna(0)
    df["valor_restante"] = pd.to_numeric(df["valor_restante"], errors="coerce").fillna(0)
    df["data_criacao"] = pd.to_datetime(df["data_criacao"], errors="coerce")
    return df

def calcular_resumo(df_lanc):
    if df_lanc.empty:
        return 0.0, 0.0, 0.0, 0.0

    receitas = df_lanc[df_lanc["tipo"] == "Receita"]["valor"].sum()
    despesas = df_lanc[df_lanc["tipo"] == "Despesa"]["valor"].sum()

    # pagamentos de dívida são despesas com categoria "Pagamento de Dívida"
    pag_divida = df_lanc[
        (df_lanc["tipo"] == "Despesa") & (df_lanc["categoria"] == "Pagamento de Dívida")
    ]["valor"].sum()

    saldo = receitas - despesas
    return receitas, despesas, saldo, pag_divida

def gerar_resumo_mensal(df_lanc):
    if df_lanc.empty:
        return pd.DataFrame(columns=["Mês", "Entradas", "Despesas", "Pagamentos de Dívida", "Saldo"])

    df = df_lanc.copy()

    receitas_mensais = (
        df[df["tipo"] == "Receita"]
        .groupby("mes")["valor"]
        .sum()
        .rename("Entradas")
    )

    despesas_mensais = (
        df[df["tipo"] == "Despesa"]
        .groupby("mes")["valor"]
        .sum()
        .rename("Despesas")
    )

    dividas_mensais = (
        df[(df["tipo"] == "Despesa") & (df["categoria"] == "Pagamento de Dívida")]
        .groupby("mes")["valor"]
        .sum()
        .rename("Pagamentos de Dívida")
    )

    resumo = pd.concat([receitas_mensais, despesas_mensais, dividas_mensais], axis=1).fillna(0)
    resumo["Saldo"] = resumo["Entradas"] - resumo["Despesas"]
    resumo = resumo.reset_index().rename(columns={"mes": "Mês"})
    resumo = resumo.sort_values("Mês")
    return resumo

# =========================
# CARREGAR DADOS
# =========================
df_lanc = listar_lancamentos()
df_div = listar_dividas()

df_lanc = preparar_lancamentos(df_lanc)
df_div = preparar_dividas(df_div)

receitas, despesas, saldo, total_pag_dividas = calcular_resumo(df_lanc)
total_dividas_restantes = df_div["valor_restante"].sum() if not df_div.empty else 0.0

# =========================
# TÍTULO
# =========================
st.title("💰 Controle Financeiro")
st.caption("Entradas, despesas e dívidas em uma única página")

# =========================
# RESUMO GERAL
# =========================
st.subheader("Resumo Geral")

c1, c2, c3, c4 = st.columns(4)
c1.metric("Entradas", formatar_brl(receitas))
c2.metric("Despesas", formatar_brl(despesas))
c3.metric("Saldo", formatar_brl(saldo))
c4.metric("Dívidas Restantes", formatar_brl(total_dividas_restantes))

st.divider()

# =========================
# CADASTRO DE LANÇAMENTOS
# =========================
st.subheader("➕ Novo Lançamento")

col_a, col_b = st.columns(2)

with col_a:
    data_lanc = st.date_input("Data do lançamento", value=date.today(), key="data_lanc")
    tipo_lanc = st.selectbox("Tipo", ["Receita", "Despesa"], key="tipo_lanc")

if tipo_lanc == "Receita":
    opcoes_categoria = CATEGORIAS_RECEITA
else:
    opcoes_categoria = CATEGORIAS_DESPESA

with col_b:
    categoria_lanc = st.selectbox("Categoria", opcoes_categoria, key="categoria_lanc")

descricao_lanc = st.text_input("Descrição", key="descricao_lanc")
valor_lanc = st.number_input("Valor (R$)", min_value=0.0, format="%.2f", key="valor_lanc")

if st.button("Salvar lançamento", use_container_width=True):
    if valor_lanc <= 0:
        st.warning("Informe um valor maior que zero.")
    else:
        inserir_lancamento(
            str(data_lanc),
            tipo_lanc,
            categoria_lanc,
            descricao_lanc,
            valor_lanc
        )
        st.success("Lançamento salvo com sucesso.")
        st.rerun()

st.divider()

# =========================
# CADASTRO DE DÍVIDAS
# =========================
st.subheader("🤝 Cadastrar Dívida")

col_d1, col_d2 = st.columns(2)

with col_d1:
    nome_pessoa = st.text_input("Pessoa para quem você deve", key="nome_pessoa")
    data_divida = st.date_input("Data da dívida", value=date.today(), key="data_divida")

with col_d2:
    descricao_divida = st.text_input("Descrição da dívida", key="descricao_divida")
    valor_divida = st.number_input("Valor total da dívida (R$)", min_value=0.0, format="%.2f", key="valor_divida")

if st.button("Cadastrar dívida", use_container_width=True):
    if not nome_pessoa.strip():
        st.warning("Informe o nome da pessoa.")
    elif valor_divida <= 0:
        st.warning("Informe um valor maior que zero.")
    else:
        inserir_divida(
            nome_pessoa.strip(),
            str(data_divida),
            descricao_divida.strip(),
            valor_divida
        )
        st.success("Dívida cadastrada com sucesso.")
        st.rerun()

st.divider()

# =========================
# PAGAR DÍVIDA
# =========================
st.subheader("💸 Pagar Dívida")

dividas_abertas = pd.DataFrame()
if not df_div.empty:
    dividas_abertas = df_div[df_div["valor_restante"] > 0].copy()

if dividas_abertas.empty:
    st.info("Não há dívidas em aberto no momento.")
else:
    opcoes_dividas = {
        f'ID {row["id"]} - {row["nome_pessoa"]} | Restante: {formatar_brl(row["valor_restante"])}': row["id"]
        for _, row in dividas_abertas.iterrows()
    }

    col_p1, col_p2, col_p3 = st.columns(3)

    with col_p1:
        divida_selecionada_label = st.selectbox(
            "Selecione a dívida",
            list(opcoes_dividas.keys()),
            key="divida_selecionada"
        )
        id_divida = opcoes_dividas[divida_selecionada_label]

    with col_p2:
        data_pagamento = st.date_input("Data do pagamento", value=date.today(), key="data_pagamento")

    with col_p3:
        valor_pagamento = st.number_input("Valor pago (R$)", min_value=0.0, format="%.2f", key="valor_pagamento")

    observacao_pagamento = st.text_input(
        "Observação do pagamento (opcional)",
        key="obs_pagamento"
    )

    if st.button("Registrar pagamento da dívida", use_container_width=True):
        if valor_pagamento <= 0:
            st.warning("Informe um valor maior que zero.")
        else:
            sucesso, mensagem = pagar_divida(
                id_divida=id_divida,
                valor_pagamento=valor_pagamento,
                data_pagamento=str(data_pagamento),
                observacao=observacao_pagamento
            )

            if sucesso:
                st.success(mensagem)
                st.rerun()
            else:
                st.error(mensagem)

st.divider()

# =========================
# GRÁFICOS
# =========================
st.subheader("📊 Gráficos")

g1, g2 = st.columns(2)

with g1:
    st.markdown("**Despesas por categoria**")
    if not df_lanc.empty:
        despesas_categoria = (
            df_lanc[df_lanc["tipo"] == "Despesa"]
            .groupby("categoria")["valor"]
            .sum()
            .sort_values(ascending=False)
        )

        if not despesas_categoria.empty:
            st.bar_chart(despesas_categoria)
        else:
            st.info("Ainda não há despesas para exibir.")
    else:
        st.info("Sem dados ainda.")

with g2:
    st.markdown("**Entradas por categoria**")
    if not df_lanc.empty:
        receitas_categoria = (
            df_lanc[df_lanc["tipo"] == "Receita"]
            .groupby("categoria")["valor"]
            .sum()
            .sort_values(ascending=False)
        )

        if not receitas_categoria.empty:
            st.bar_chart(receitas_categoria)
        else:
            st.info("Ainda não há entradas para exibir.")
    else:
        st.info("Sem dados ainda.")

st.markdown("**Relação mensal: entradas x despesas x pagamentos de dívida**")
resumo_mensal = gerar_resumo_mensal(df_lanc)

if not resumo_mensal.empty:
    grafico_mensal = resumo_mensal.set_index("Mês")[["Entradas", "Despesas", "Pagamentos de Dívida"]]
    st.line_chart(grafico_mensal)
else:
    st.info("Ainda não há dados suficientes para o gráfico mensal.")

st.divider()

# =========================
# TABELA RESUMO MENSAL
# =========================
st.subheader("📅 Resumo Mensal")

if not resumo_mensal.empty:
    resumo_mensal_exib = resumo_mensal.copy()
    for col in ["Entradas", "Despesas", "Pagamentos de Dívida", "Saldo"]:
        resumo_mensal_exib[col] = resumo_mensal_exib[col].apply(formatar_brl)

    st.dataframe(resumo_mensal_exib, use_container_width=True, hide_index=True)
else:
    st.info("Nenhum dado mensal para exibir ainda.")

st.divider()

# =========================
# TABELA DE LANÇAMENTOS
# =========================
st.subheader("📋 Lançamentos")

if not df_lanc.empty:
    df_lanc_exib = df_lanc.copy()
    df_lanc_exib["data"] = df_lanc_exib["data"].dt.strftime("%d/%m/%Y")
    df_lanc_exib["valor_formatado"] = df_lanc_exib["valor"].apply(formatar_brl)

    st.dataframe(
        df_lanc_exib[["id", "data", "tipo", "categoria", "descricao", "valor_formatado"]]
        .rename(columns={
            "id": "ID",
            "data": "Data",
            "tipo": "Tipo",
            "categoria": "Categoria",
            "descricao": "Descrição",
            "valor_formatado": "Valor"
        }),
        use_container_width=True,
        hide_index=True
    )

    st.markdown("**Excluir lançamento**")
    id_lanc_excluir = st.selectbox(
        "Selecione o ID do lançamento para excluir",
        df_lanc["id"].tolist(),
        key="id_lanc_excluir"
    )

    if st.button("Excluir lançamento selecionado", use_container_width=True):
        excluir_lancamento(id_lanc_excluir)
        st.success("Lançamento excluído com sucesso.")
        st.rerun()
else:
    st.info("Nenhum lançamento cadastrado ainda.")

st.divider()

# =========================
# TABELA DE DÍVIDAS
# =========================
st.subheader("🤝 Minhas Dívidas")

if not df_div.empty:
    df_div_exib = df_div.copy()
    df_div_exib["data_criacao"] = df_div_exib["data_criacao"].dt.strftime("%d/%m/%Y")
    df_div_exib["valor_total_fmt"] = df_div_exib["valor_total"].apply(formatar_brl)
    df_div_exib["valor_restante_fmt"] = df_div_exib["valor_restante"].apply(formatar_brl)

    st.dataframe(
        df_div_exib[["id", "nome_pessoa", "data_criacao", "descricao", "valor_total_fmt", "valor_restante_fmt"]]
        .rename(columns={
            "id": "ID",
            "nome_pessoa": "Pessoa",
            "data_criacao": "Data",
            "descricao": "Descrição",
            "valor_total_fmt": "Valor Total",
            "valor_restante_fmt": "Valor Restante"
        }),
        use_container_width=True,
        hide_index=True
    )

    st.markdown("**Excluir dívida**")
    id_div_excluir = st.selectbox(
        "Selecione o ID da dívida para excluir",
        df_div["id"].tolist(),
        key="id_div_excluir"
    )

    if st.button("Excluir dívida selecionada", use_container_width=True):
        excluir_divida(id_div_excluir)
        st.success("Dívida excluída com sucesso.")
        st.rerun()
else:
    st.info("Nenhuma dívida cadastrada ainda.")
