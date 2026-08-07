import streamlit as st
import pandas as pd
import requests
import cloudscraper
from datetime import datetime

# ==========================================
# CONFIGURAÇÕES DA PÁGINA
# ==========================================
st.set_page_config(
    page_title="Scanner de Apostas - v1.2",
    page_icon="⚽",
    layout="wide",
    initial_sidebar_state="expanded"
)

# ==========================================
# CONTROLE DE VERSÃO DO APLICATIVO
# ==========================================
APP_VERSION = "v1.2"

# ==========================================
# CONFIGURAÇÕES DE API / SUPABASE / SECRETS
# ==========================================
# Busca chave de secrets do Streamlit ou usa fallback para testes
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
    st.session_state['autenticado'] = True  # Altere para False se usar controle de login
if 'usuario' not in st.session_state:
    st.session_state['usuario'] = "rafael.andrade.sa@gmail.com"
if 'pagina_atual' not in st.session_state:
    st.session_state['pagina_atual'] = "Historico"

# ==========================================
# FUNÇÃO DE BUSCA DOS ÚLTIMOS 10 JOGOS (HÍBRIDA)
# ==========================================
@st.cache_data(ttl=300)
def carregar_ultimos_10_jogos(nome_time):
    """
    Tenta buscar os últimos 10 jogos no Sofascore via cloudscraper.
    Se falhar ou for bloqueado, busca via API-Sports como fallback.
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
            index=1
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
    st.info("Em breve: Lista automatizada das partidas selecionadas para a rodada.")

# TELA 2: HISTÓRICO DOS ÚLTIMOS 10 JOGOS
elif "Histórico" in opcao:
    st.title("📊 Histórico dos ÚLTIMOS 10 JOGOS das Equipes")
    
    col_data, col_jogo = st.columns([1, 2])
    
    with col_data:
        data_selecionada = st.selectbox(
            "Escolha a data do confronto:",
            ["07/08/2026 (Hoje)", "Amanhã", "Próxima Rodada"]
        )
        
    with col_jogo:
        partida_selecionada = st.selectbox(
            "Selecione a partida para visualizar o histórico:",
            [
                "Cruz Azul x Philadelphia Union (Leagues Cup)",
                "Flamengo x Palmeiras (Brasileirão)",
                "Real Madrid x Barcelona (La Liga)"
            ]
        )

    # Extrai os nomes dos times
    times = partida_selecionada.split(" x ")
    time_mandante = times[0].strip()
    time_visitante = times[1].split("(")[0].strip() if len(times) > 1 else ""

    if st.button("🔎 Carregar Histórico Atualizado", type="primary"):
        st.session_state['carregou_historico'] = True

    if st.session_state.get('carregou_historico', True):
        c1, c2 = st.columns(2)
        
        # Histórico Mandante
        with c1:
            st.subheader(f"🏠 {time_mandante} - ÚLTIMOS 10 JOGOS")
            with st.spinner(f"Buscando histórico do {time_mandante}..."):
                dados_m = carregar_ultimos_10_jogos(time_mandante)
                if dados_m:
                    df_m = pd.DataFrame(dados_m)
                    st.dataframe(df_m, use_container_width=True, hide_index=True)
                else:
                    st.warning("Histórico não encontrado.")

        # Histórico Visitante
        with c2:
            st.subheader(f"🚀 {time_visitante} - ÚLTIMOS 10 JOGOS")
            with st.spinner(f"Buscando histórico do {time_visitante}..."):
                dados_v = carregar_ultimos_10_jogos(time_visitante)
                if dados_v:
                    df_v = pd.DataFrame(dados_v)
                    st.dataframe(df_v, use_container_width=True, hide_index=True)
                else:
                    st.warning("Histórico não encontrado.")

# TELA 3: ANÁLISE PRÉ-JOGO (IA)
elif "Análise" in opcao:
    st.header("🔍 Análise Tática Pré-Jogo (IA Gemini)")
    st.info("Módulo de geração automática de relatórios táticos em 13 tópicos.")

# TELA 4: BANCO DE DADOS SUPABASE
elif "Banco de Dados" in opcao:
    st.header("💾 Registro no Supabase")
    st.info("Módulo de consulta e persistência das análises no banco de dados.")