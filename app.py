import streamlit as st
import requests
import pandas as pd
from datetime import datetime, timedelta

# Configurações da página
st.set_page_config(
    page_title="Grade de Jogos - Múltiplas Datas",
    page_icon="⚽",
    layout="wide"
)

# Configurações da API
API_KEY = "17948bfd5d3ed61ae0cb0aa7a97f5e09"
BASE_URL = "https://v3.football.api-sports.io"
HEADERS = {"x-apisports-key": API_KEY}

STATUS_MAP = {
    'NS': 'Não Iniciado',
    '1H': '1º Tempo',
    'HT': 'Intervalo',
    '2H': '2º Tempo',
    'FT': 'Encerrado',
    'AET': 'Prorrogação',
    'PEN': 'Pênaltis',
    'P': 'Adiado',
    'CANC': 'Cancelado'
}

@st.cache_data(ttl=3600)
def carregar_jogos_por_data(data_alvo):
    """Busca todos os jogos do mundo para uma data específica (1 requisição)."""
    url = f"{BASE_URL}/fixtures?date={data_alvo}"
    try:
        response = requests.get(url, headers=HEADERS)
        if response.status_code != 200:
            return []

        dados = response.json()
        if dados.get('errors') and len(dados['errors']) > 0:
            return []

        partidas = dados.get('response', [])
        lista_jogos = []

        for fixture in partidas:
            status_code = fixture['fixture']['status']['short']
            status_extenso = STATUS_MAP.get(status_code, status_code)
            
            gols_home = fixture['goals']['home'] if fixture['goals']['home'] is not None else '-'
            gols_away = fixture['goals']['away'] if fixture['goals']['away'] is not None else '-'
            placar = f"{gols_home} x {gols_away}" if status_code != 'NS' else "v"

            # Formata a data para exibição (DD/MM/YYYY)
            data_formatada = datetime.strptime(data_alvo, "%Y-%m-%d").strftime("%d/%m/%Y")

            lista_jogos.append({
                "Data": data_formatada,
                "País": fixture['league']['country'],
                "Liga": fixture['league']['name'],
                "Horário": fixture['fixture']['date'][11:16],
                "Status": status_extenso,
                "Mandante": fixture['teams']['home']['name'],
                "Placar": placar,
                "Visitante": fixture['teams']['away']['name']
            })

        return lista_jogos
    except Exception:
        return []

# ----- INTERFACE -----
st.title("📅 Grade de Jogos — Múltiplas Datas")
st.markdown("Selecione **até 3 datas** na barra lateral para carregar a grade completa de jogos.")

# Opções de datas (Hoje e os próximos 6 dias)
hoje = datetime.now()
dias_disponiveis = [hoje + timedelta(days=i) for i in range(7)]

# Cria um dicionário com rótulos amigáveis ("2026-08-08": "08/08/2026 (Amanhã)")
opcoes_datas = {
    d.strftime("%Y-%m-%d"): f"{d.strftime('%d/%m/%Y')} ({'Hoje' if i==0 else 'Amanhã' if i==1 else d.strftime('%a')})"
    for i, d in enumerate(dias_disponiveis)
}

# Seletor de no máximo 3 datas
datas_selecionadas = st.sidebar.multiselect(
    "Selecione no máximo 3 datas:",
    options=list(opcoes_datas.keys()),
    default=list(opcoes_datas.keys())[:3], # Por padrão seleciona Hoje, Amanhã e Depois
    format_func=lambda x: opcoes_datas[x],
    max_selections=3
)

if st.sidebar.button("Atualizar Jogos"):
    st.cache_data.clear()

st.divider()

if not datas_selecionadas:
    st.warning("⚠️ Escolha pelo menos 1 data na barra lateral esquerda.")
else:
    todos_jogos = []
    
    with st.spinner(f"Buscando partidas para {len(datas_selecionadas)} data(s)..."):
        for data in datas_selecionadas:
            jogos_da_data = carregar_jogos_por_data(data)
            todos_jogos.extend(jogos_da_data)

    if todos_jogos:
        df = pd.DataFrame(todos_jogos)

        # Filtros no topo da tabela
        col1, col2, col3, col4 = st.columns([1, 1, 1, 2])

        with col1:
            datas_unicas = ["Todas"] + sorted(list(df["Data"].unique()))
            data_filtro = st.selectbox("Filtrar Data", datas_unicas)

        with col2:
            paises = ["Todos"] + sorted(list(df["País"].unique()))
            pais_selecionado = st.selectbox("Filtrar País", paises)

        with col3:
            if pais_selecionado != "Todos":
                ligas_disponiveis = ["Todas"] + sorted(list(df[df["País"] == pais_selecionado]["Liga"].unique()))
            else:
                ligas_disponiveis = ["Todas"] + sorted(list(df["Liga"].unique()))
            liga_selecionada = st.selectbox("Filtrar Liga", ligas_disponiveis)

        with col4:
            termo_busca = st.text_input("Buscar Time", placeholder="Digite o nome de um time...")

        # Aplicação dos Filtros
        df_filtrado = df.copy()

        if data_filtro != "Todas":
            df_filtrado = df_filtrado[df_filtrado["Data"] == data_filtro]

        if pais_selecionado != "Todos":
            df_filtrado = df_filtrado[df_filtrado["País"] == pais_selecionado]

        if liga_selecionada != "Todas":
            df_filtrado = df_filtrado[df_filtrado["Liga"] == liga_selecionada]

        if termo_busca:
            df_filtrado = df_filtrado[
                df_filtrado["Mandante"].str.contains(termo_busca, case=False, na=False) |
                df_filtrado["Visitante"].str.contains(termo_busca, case=False, na=False)
            ]

        st.caption(f"Exibindo **{len(df_filtrado)}** de **{len(df)}** partidas carregadas.")

        # Exibição da tabela
        st.dataframe(
            df_filtrado,
            use_container_width=True,
            column_config={
                "Data": st.column_config.TextColumn("Data", width="small"),
                "Horário": st.column_config.TextColumn("Horário", width="small"),
                "Status": st.column_config.TextColumn("Status", width="medium"),
                "Placar": st.column_config.TextColumn("Placar", width="small"),
            }
        )
    else:
        st.info("Nenhuma partida encontrada para a(s) data(s) selecionada(s).")