import streamlit as st
import requests
import pandas as pd
from datetime import datetime, timedelta

# Configurações da página
st.set_page_config(
    page_title="Grade Completa de Jogos do Dia",
    page_icon="⚽",
    layout="wide"
)

# Configurações da API
API_KEY = "17948bfd5d3ed61ae0cb0aa7a97f5e09"
BASE_URL = "https://v3.football.api-sports.io"
HEADERS = {"x-apisports-key": API_KEY}

# Mapeamento de status amigáveis
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
def carregar_todos_jogos(data_alvo):
    """Busca TODOS os jogos do mundo para a data selecionada usando apenas 1 requisição."""
    url = f"{BASE_URL}/fixtures?date={data_alvo}"
    
    try:
        response = requests.get(url, headers=HEADERS)
        if response.status_code != 200:
            st.error(f"Erro na API (HTTP {response.status_code})")
            return []

        dados = response.json()
        
        if dados.get('errors') and len(dados['errors']) > 0:
            st.warning(f"⚠️ Alerta da API: {dados['errors']}")
            return []

        partidas = dados.get('response', [])
        lista_jogos = []

        for fixture in partidas:
            status_code = fixture['fixture']['status']['short']
            status_extenso = STATUS_MAP.get(status_code, status_code)
            
            # Gols
            gols_home = fixture['goals']['home'] if fixture['goals']['home'] is not None else '-'
            gols_away = fixture['goals']['away'] if fixture['goals']['away'] is not None else '-'
            placar = f"{gols_home} x {gols_away}" if status_code != 'NS' else "v"

            lista_jogos.append({
                "País": fixture['league']['country'],
                "Liga": fixture['league']['name'],
                "Horário": fixture['fixture']['date'][11:16],
                "Status": status_extenso,
                "Mandante": fixture['teams']['home']['name'],
                "Placar": placar,
                "Visitante": fixture['teams']['away']['name']
            })

        return lista_jogos

    except Exception as e:
        st.error(f"Erro ao conectar com a API: {e}")
        return []

# ----- INTERFACE -----
st.title("📅 Grade Completa de Jogos do Dia")
st.markdown("Lista de todas as partidas agendadas no mundo todo (1 requisição por busca).")

# Barra lateral
data_selecionada = st.sidebar.date_input("Data dos jogos", datetime.now() + timedelta(days=1))

if st.sidebar.button("Atualizar Lista"):
    st.cache_data.clear()

with st.spinner("Buscando lista completa de jogos do dia..."):
    jogos = carregar_todos_jogos(str(data_selecionada))

st.divider()

if jogos:
    df = pd.DataFrame(jogos)
    
    # Filtros na Tela Principal
    col_filtro1, col_filtro2, col_filtro3 = st.columns([1, 1, 2])
    
    with col_filtro1:
        paises = ["Todos"] + sorted(list(df["País"].unique()))
        pais_selecionado = st.selectbox("Filtrar por País", paises)

    with col_filtro2:
        if pais_selecionado != "Todos":
            ligas_disponiveis = ["Todas"] + sorted(list(df[df["País"] == pais_selecionado]["Liga"].unique()))
        else:
            ligas_disponiveis = ["Todas"] + sorted(list(df["Liga"].unique()))
        liga_selecionada = st.selectbox("Filtrar por Liga", ligas_disponiveis)

    with col_filtro3:
        termo_busca = st.text_input("Buscar Time", placeholder="Digite o nome de um time...")

    # Aplicação dos filtros no dataframe
    df_filtrado = df.copy()

    if pais_selecionado != "Todos":
        df_filtrado = df_filtrado[df_filtrado["País"] == pais_selecionado]

    if liga_selecionada != "Todas":
        df_filtrado = df_filtrado[df_filtrado["Liga"] == liga_selecionada]

    if termo_busca:
        df_filtrado = df_filtrado[
            df_filtrado["Mandante"].str.contains(termo_busca, case=False, na=False) |
            df_filtrado["Visitante"].str.contains(termo_busca, case=False, na=False)
        ]

    # Métricas
    st.caption(f"Exibindo **{len(df_filtrado)}** de **{len(df)}** partidas encontradas para {data_selecionada}.")

    # Exibição da Tabela
    st.dataframe(
        df_filtrado, 
        use_container_width=True,
        column_config={
            "Horário": st.column_config.TextColumn("Horário", width="small"),
            "Status": st.column_config.TextColumn("Status", width="medium"),
            "Placar": st.column_config.TextColumn("Placar", width="small"),
        }
    )
else:
    st.info("Nenhuma partida encontrada para a data selecionada.")