import streamlit as st
import pandas as pd
import requests
import cloudscraper
from datetime import datetime

# ==========================================
# CONFIGURAÇÕES DA PÁGINA
# ==========================================
st.set_page_config(
    page_title="Scanner de Apostas - v1.3",
    page_icon="⚽",
    layout="wide",
    initial_sidebar_state="expanded"
)

# ==========================================
# CONTROLE DE VERSÃO DO APLICATIVO
# ==========================================
APP_VERSION = "v1.3"

# ==========================================
# CONFIGURAÇÕES DE API / SECRETS
# ==========================================
API_KEY = st.secrets.get("API_FOOTBALL_KEY", "SUA_CHAVE_API_SPORTS")
BASE_URL = "https://v3.football.api-sports.io"
HEADERS = {
    'x-rapidapi-host': "v3.football.api-sports.io",
    'x-rapidapi-key': API_KEY
}

# ==========================================
# GERENCIAMENTO DE SESSÃO / AUTENTICAÇÃO
# ==========================================
if 'autenticado' not in st.session_state:
    st.session_state['autenticado'] = True
if 'usuario' not in st.session_state:
    st.session_state['usuario'] = "rafael.andrade.sa@gmail.com"

# ==========================================
# FUNÇÃO 1: BUSCAR JOGOS DO DIA (GRADE GERAL)
# ==========================================
@st.cache_data(ttl=600)
def carregar_jogos_do_dia(data_str):
    """Busca as partidas do dia na API-Sports."""
    try:
        url = f"{BASE_URL}/fixtures?date={data_str}"
        response = requests.get(url, headers=HEADERS, timeout=8)
        
        if response.status_code == 200:
            fixtures = response.json().get('response', [])
            jogos = []
            
            for f in fixtures:
                status = f['fixture']['status']['short']
                gh = f['goals']['home']
                ga = f['goals']['away']
                placar = f"{gh} x {ga}" if gh is not None and ga is not None else "v"
                
                jogos.append({
                    "Hora": f['fixture']['date'][11:16],
                    "País": f['league']['country'],
                    "Liga": f['league']['name'],
                    "Mandante": f['teams']['home']['name'],
                    "Placar": placar,
                    "Visitante": f['teams']['away']['name'],
                    "Status": status
                })
            return pd.DataFrame(jogos)
    except Exception as e:
        st.error(f"Erro ao conectar com a API: {e}")
    return pd.DataFrame()

# ==========================================
# FUNÇÃO 2: HISTÓRICO 10 JOGOS (SOFASCORE + FALLBACK)
# ==========================================
@st.cache_data(ttl=300)
def carregar_ultimos_10_jogos(nome_time):
    """
    Tenta buscar os últimos 10 jogos no Sofascore via cloudscraper.
    Se falhar, recorre à API-Sports como garantia.
    """
    # 1. TENTATIVA VIA SOFASCORE (CLOUDSCRAPER)
    try:
        scraper = cloudscraper.create_scraper()
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
            'Accept-Language': 'pt-BR,pt;q=0.9,en-US;q=0.8,en;q=0.7'
        }
        
        url_busca = f"https://api.sofascore.com/api/v1/search/all?q={nome_time}"
        res_busca = scraper.get(url_busca, headers=headers, timeout=8)
        
        if res_busca.status_code == 200:
            results = res_busca.json().get('results', [])
            sofa_team_id = None
            
            for item in results:
                if item.get('type') == 'team':
                    sofa_team_id = item['entity']['id']
                    break
            
            if sofa_team_id:
                url_events = f"https://api.sofascore.com/api/v1/team/{sofa_team_id}/events/last/0"
                res_events = scraper.get(url_events, headers=headers, timeout=8)
                
                if res_events.status_code == 200:
                    events = res_events.json().get('events', [])
                    historico = []
                    
                    for ev in events[:10]:
                        gols_h = ev.get('homeScore', {}).get('current', 0)
                        gols_a = ev.get('awayScore', {}).get('current', 0)
                        timestamp = ev.get('startTimestamp')
                        data_dt = datetime.fromtimestamp(timestamp).strftime('%d/%m/%Y') if timestamp else 'N/A'
                        
                        historico.append({
                            "Data": data_dt,
                            "Competição": ev.get('tournament', {}).get('name', 'N/A'),
                            "Mandante": ev.get('homeTeam', {}).get('name', ''),
                            "Placar": f"{gols_h} x {gols_a}",
                            "Visitante": ev.get('awayTeam', {}).get('name', ''),
                            "Fonte": "Sofascore"
                        })
                    
                    if historico:
                        return historico
    except Exception:
        pass

    # 2. GARANTIA (FALLBACK VIA API-SPORTS)
    try:
        url_search = f"{BASE_URL}/teams?search={nome_time}"
        res_team = requests.get(url_search, headers=HEADERS, timeout=6)
        
        if res_team.status_code == 200:
            data_team = res_team.json()
            if data_team.get('response') and len(data_team['response']) > 0:
                team_id = data_team['response'][0]['team']['id']
                
                url_fix = f"{BASE_URL}/fixtures?team={team_id}&last=10"
                res_fix = requests.get(url_fix, headers=HEADERS, timeout=6)
                
                if res_fix.status_code == 200:
                    fixtures = res_fix.json().get('response', [])
                    historico = []
                    
                    for f in fixtures:
                        gh = f['goals']['home'] if f['goals']['home'] is not None else 0
                        ga = f['goals']['away'] if f['goals']['away'] is not None else 0
                        data_raw = f['fixture']['date'][:10]
                        dt = datetime.strptime(data_raw, "%Y-%m-%d").strftime("%d/%m/%Y")
                        
                        historico.append({
                            "Data": dt,
                            "Competição": f['league']['name'],
                            "Mandante": f['teams']['home']['name'],
                            "Placar": f"{gh} x {ga}",
                            "Visitante": f['teams']['away']['name'],
                            "Fonte": "API-Sports"
                        })
                    
                    if historico:
                        return historico
    except Exception:
        pass

    return []

# ==========================================
# BARRA LATERAL (MENU)
# ==========================================
with st.sidebar:
    st.title(f"☰ Menu ({APP_VERSION})")
    
    if st.session_state.get('autenticado'):
        st.caption(f"👤 Conectado:\n**{st.session_state['usuario']}**")
        st.markdown("---")
        
        st.subheader("Navegação:")
        opcao = st.radio(
            "Selecione a tela:",
            [
                "📅 Grade Geral de Jogos",
                "📊 Histórico & Estatísticas (10 Jogos)",
                "🔍 Análise Pré-Jogo (IA)",
                "💾 Banco de Dados Supabase"
            ],
            index=0
        )
        
        st.markdown("---")
        
        if st.button("🔄 Atualizar Dados Agora"):
            st.cache_data.clear()
            st.rerun()
            
        if st.button("🚪 Sair (Logout)"):
            st.session_state['autenticado'] = False
            st.rerun()
            
        st.caption(f"⚙️ Painel de Apostas - Versão {APP_VERSION}")

# ==========================================
# ROTEAMENTO DE PÁGINAS
# ==========================================

# TELA 1: GRADE GERAL DE JOGOS
if "Grade Geral" in opcao:
    st.header("📅 Grade Geral de Jogos do Dia")
    
    col_data, _ = st.columns([1, 2])
    with col_data:
        data_consulta = st.date_input("Selecione a data:", value=datetime.now())
    
    data_str = data_consulta.strftime("%Y-%m-%d")
    
    with st.spinner("Carregando grade de jogos..."):
        df_jogos = carregar_jogos_do_dia(data_str)
        
        if not df_jogos.empty:
            st.success(f"Encontrados **{len(df_jogos)}** jogos para {data_consulta.strftime('%d/%m/%Y')}:")
            
            col_f1, col_f2 = st.columns(2)
            with col_f1:
                ligas_disponiveis = ["Todas"] + sorted(list(df_jogos['Liga'].unique()))
                liga_selecionada = st.selectbox("Filtrar por Campeonato:", ligas_disponiveis)
            with col_f2:
                busca_time = st.text_input("Buscar Time:", placeholder="Digite o nome do time...")
            
            df_exibicao = df_jogos.copy()
            if liga_selecionada != "Todas":
                df_exibicao = df_exibicao[df_exibicao['Liga'] == liga_selecionada]
            if busca_time:
                df_exibicao = df_exibicao[
                    df_exibicao['Mandante'].str.contains(busca_time, case=False, na=False) |
                    df_exibicao['Visitante'].str.contains(busca_time, case=False, na=False)
                ]
                
            st.dataframe(df_exibicao, use_container_width=True, hide_index=True)
        else:
            st.warning("Nenhum jogo encontrado para esta data ou chave de API não configurada.")

# TELA 2: HISTÓRICO DOS ÚLTIMOS 10 JOGOS
elif "Histórico" in opcao:
    st.title("📊 Histórico dos ÚLTIMOS 10 JOGOS das Equipes")
    
    col_input, col_btn = st.columns([3, 1])
    with col_input:
        time_pesquisado = st.text_input("Digite o nome do time:", value="Cruz Azul")
    
    if st.button("🔎 Buscar Histórico de 10 Jogos", type="primary"):
        if time_pesquisado:
            with st.spinner(f"Buscando histórico recente de {time_pesquisado}..."):
                dados = carregar_ultimos_10_jogos(time_pesquisado)
                if dados:
                    df_h = pd.DataFrame(dados)
                    st.dataframe(df_h, use_container_width=True, hide_index=True)
                else:
                    st.warning("Histórico não encontrado.")
        else:
            st.info("Digite o nome de uma equipe para realizar a consulta.")

# TELA 3: ANÁLISE PRÉ-JOGO (IA)
elif "Análise" in opcao:
    st.header("🔍 Análise Tática Pré-Jogo (IA Gemini)")
    st.info("Módulo de geração automática de relatórios táticos em 13 tópicos.")

# TELA 4: BANCO DE DADOS SUPABASE
elif "Banco de Dados" in opcao:
    st.header("💾 Registro no Supabase")
    st.info("Módulo de consulta e persistência das análises no banco de dados.")