import streamlit as st
import pandas as pd
from datetime import date
from database import criar_tabela, inserir_lancamento, listar_lancamentos, excluir_lancamento

# Configuração da página
st.set_page_config(page_title="App Financeiro", page_icon="💰", layout="wide")

# Criar tabela ao iniciar
criar_tabela()

# Título
st.title("💰 App Financeiro Pessoal")
st.markdown("Controle de receitas e despesas com banco de dados SQLite")

# Sidebar - novo lançamento
st.sidebar.header("➕ Novo Lançamento")

with st.sidebar.form("form_lancamento"):
    data = st.date_input("Data", value=date.today())
    tipo = st.selectbox("Tipo", ["Receita", "Despesa"])
    categoria = st.selectbox(
        "Categoria",
        ["Salário", "Alimentação", "Transporte", "Lazer", "Moradia", "Saúde", "Educação", "Outros"]
    )
    descricao = st.text_input("Descrição")
    valor = st.number_input("Valor", min_value=0.0, format="%.2f")
    enviar = st.form_submit_button("Salvar")

    if enviar:
        inserir_lancamento(str(data), tipo, categoria, descricao, valor)
        st.sidebar.success("Lançamento salvo com sucesso!")
        st.rerun()

# Buscar dados
df = listar_lancamentos()

# Tratamento
if not df.empty:
    df["valor"] = pd.to_numeric(df["valor"], errors="coerce").fillna(0)
    df["data"] = pd.to_datetime(df["data"], errors="coerce")

# Métricas
if not df.empty:
    receitas = df[df["tipo"] == "Receita"]["valor"].sum()
    despesas = df[df["tipo"] == "Despesa"]["valor"].sum()
    saldo = receitas - despesas
else:
    receitas = despesas = saldo = 0

# Formatação BRL
def formatar_brl(valor):
    return f"R$ {valor:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")

# Cards
col1, col2, col3 = st.columns(3)
col1.metric("💵 Receitas", formatar_brl(receitas))
col2.metric("💸 Despesas", formatar_brl(despesas))
col3.metric("📊 Saldo", formatar_brl(saldo))

# Tabela de lançamentos
st.subheader("📋 Lançamentos")

if not df.empty:
    st.dataframe(
        df[["id", "data", "tipo", "categoria", "descricao", "valor"]],
        use_container_width=True
    )

    # Excluir lançamento
    st.subheader("🗑️ Excluir lançamento")
    id_excluir = st.selectbox("Selecione o ID para excluir", df["id"].tolist())

    if st.button("Excluir"):
        excluir_lancamento(id_excluir)
        st.success(f"Lançamento {id_excluir} excluído com sucesso!")
        st.rerun()

else:
    st.info("Nenhum lançamento cadastrado ainda.")

# Gráfico de despesas por categoria
st.subheader("📈 Despesas por Categoria")

if not df.empty:
    despesas_cat = df[df["tipo"] == "Despesa"].groupby("categoria")["valor"].sum()

    if not despesas_cat.empty:
        st.bar_chart(despesas_cat)
    else:
        st.info("Ainda não há despesas para exibir no gráfico.")
