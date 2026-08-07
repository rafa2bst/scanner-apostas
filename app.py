import streamlit as st
import requests
import pandas as pd
from datetime import datetime, timedelta
import cloudscraper
from bs4 import BeautifulSoup
from supabase import create_client, Client
import google.generativeai as genai

# ==========================================
# CONTROLE DE VERSÃO DO APLICATIVO
# ==========================================
APP_VERSION = "v1.1"

# Configurações da página
st.set_page_config(
    page_title=f"Scanner de Apostas - Painel ({APP_VERSION})",
    page_icon="⚽",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Conexão com o Supabase
@st.cache_resource
def init_supabase():
    try:
        url = st.secrets["SUPABASE_URL"]
        key = st.secrets["SUPABASE_KEY"]
        return create_client(url, key)
    except Exception:
        st.error("Erro nas credenciais do Supabase nos Secrets.")
        return None

supabase = init_supabase()

# Configuração da IA Gemini
try:
    genai.configure(api_key=st.secrets["GEMINI_API_KEY"])
except Exception:
    st.error("Erro na chave GEMINI_API_KEY nos Secrets.")

# ----- SISTEMA DE AUTENTICAÇÃO -----
if "user" not in st.session_state:
    st.session_state.user = None

def fazer_login(email, password):
    try:
        res = supabase.auth.sign_in_with_password({"email": email, "password": password})
        st.session_state.user = res.user
        st.success("Login realizado com sucesso!")
        st.rerun()
    except Exception:
        st.error("Erro ao fazer login: E-mail ou senha incorretos.")

def fazer_logout():
    if supabase:
        supabase.auth.sign_out()
    st.session_state.user = None
    st.rerun()

# ----- TELA DE LOGIN SE NÃO ESTIVER AUTENTICADO -----
if st.session_state.user is None:
    st.sidebar.title(f"🔐 Área Restrita ({APP_VERSION})")
    st.sidebar.subheader("Acesse sua conta")
    email_input = st.sidebar.text_input("E-mail")
    senha_input = st.sidebar.text_input("Senha", type="password")
    
    if st.sidebar.button("Entrar"):
        if email_input and senha_input:
            fazer_login(email_input, senha_input)
        else:
            st.sidebar.warning("Preencha e-mail e senha.")
            
    st.title(f"🔒 Acesso Restrito - {APP_VERSION}")
    st.info("Por favor, faça login na barra lateral para acessar o scanner.")
    st.stop()

# ----- MENU LATERAL (HAMBÚRGUER COM IDENTIFICADOR DE VERSÃO) -----
st.sidebar.title(f"☰ Menu ({APP_VERSION})")
st.sidebar.caption(f"👤 Conectado: **{st.session_state.user.email}**")

menu_opcao = st.sidebar.radio(
    "Navegação:",
    [
        "📅 Grade Geral de Jogos", 
        "📊 Histórico & Estatísticas (10 Jogos)", 
        "🔍 Análise Pré-Jogo (IA)", 
        "💾 Banco de Dados Supabase"
    ]
)

st.sidebar.divider()

if st.sidebar.button("🔄 Atualizar Dados Agora"):
    st.cache_data.clear()
    st.sidebar.success("Cache limpo! Recarregando...")
    st.rerun()

if st.sidebar.button("🚪 Sair (Logout)"):
    fazer_logout()

# Rodapé do menu com indicação da versão
st.sidebar.caption(f"⚙️ Painel de Apostas - Versão **{APP_VERSION}**")

# Configurações da API de Futebol
API_KEY = "17948bfd5d3ed61ae0cb0aa7a97f5e09"
BASE_URL = "https://v3.football.api-sports.io"
HEADERS = {"x-apisports-key": API_KEY}

STATUS_MAP = {
    'NS': 'Não Iniciado', '1H': '1º Tempo', 'HT': 'Intervalo',
    '2H': '2º Tempo', 'FT': 'Encerrado', 'AET': 'Prorrogação',
    'PEN': 'Pênaltis', 'P': 'Adiado', 'CANC': 'Cancelado'
}

# Carregamento da grade geral pela API-Sports
@st.cache_data(ttl=300)
def carregar_jogos_por_data(data_alvo):
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
            data_formatada = datetime.strptime(data_alvo, "%Y-%m-%d").strftime("%d/%m/%Y")

            lista_jogos.append({
                "ID_Partida": fixture['fixture']['id'],
                "ID_Mandante": fixture['teams']['home']['id'],
                "ID_Visitante": fixture['teams']['away']['id'],
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

# FUNÇÃO HÍBRIDA DE HISTÓRICO: Sofascore + Flashscore (Com Fallback)
@st.cache_data(ttl=300)
def carregar_ultimos_10_jogos(nome_time):
    headers_sofa = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
    }
    
    # 1. TENTATIVA VIA SOFASCORE
    try:
        url_busca = f"https://api.sofascore.com/api/v1/search/all?q={nome_time}"
        res_busca = requests.get(url_busca, headers=headers_sofa, timeout=5)
        
        if res_busca.status_code == 200:
            results = res_busca.json().get('results', [])
            sofa_team_id = None
            
            for item in results:
                if item.get('type') == 'team':
                    sofa_team_id = item['entity']['id']
                    break
            
            if sofa_team_id:
                url_events = f"https://api.sofascore.com/api/v1/team/{sofa_team_id}/events/last/0"
                res_events = requests.get(url_events, headers=headers_sofa, timeout=5)
                
                if res_events.status_code == 200:
                    events = res_events.json().get('events', [])
                    historico = []
                    
                    for ev in events[:10]:
                        gols_h = ev.get('homeScore', {}).get('current', 0)
                        gols_a = ev.get('awayScore', {}).get('current', 0)
                        data_dt = datetime.fromtimestamp(ev['startTimestamp']).strftime('%d/%m/%Y')
                        
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

    # 2. TENTATIVA VIA FLASHSCORE (Fallback)
    try:
        scraper = cloudscraper.create_scraper()
        url_flash = f"https://www.flashscore.com.br/busca/?q={nome_time}"
        res_flash = scraper.get(url_flash, timeout=8)
        
        if res_flash.status_code == 200:
            soup = BeautifulSoup(res_flash.text, 'html.parser')
            return []
    except Exception:
        pass

    return []

def gerar_analise_ia(dados_jogo, hist_home, hist_away):
    prompt = f"""
    Você é um especialista tático e estatístico em apostas esportivas.
    Analise a partida a seguir: {dados_jogo["Mandante"]} x {dados_jogo["Visitante"]}
    - Campeonato: {dados_jogo["Liga"]} ({dados_jogo["País"]})
    - Data/Horário: {dados_jogo["Data"]} às {dados_jogo["Horário"]}
    - Status: {dados_jogo["Status"]}

    Últimos 10 jogos do Mandante ({dados_jogo["Mandante"]}):
    {hist_home}

    Últimos 10 jogos do Visitante ({dados_jogo["Visitante"]}):
    {hist_away}

    Gere uma análise minuciosa estruturada estritamente nos 13 tópicos abaixo:
    1- Momento das equipes
    2- Necessidade do resultado (Must Win)
    3- Análise da formação e prováveis escalações
    4- Linha de frente e desfalques de impacto
    5- Mando de campo
    6- Métricas de Expectativa (xG / xGA / Média de gols)
    7- Confrontos diretos (H2H)
    8- Estilo de jogo de cada equipe
    9- Extra campo e bastidores
    10- Fator clima e gramado
    11- Perfil do Árbitro
    12- Curiosidades e notícias de última hora
    13- Padrão mais recorrente das equipes

    No final, obrigatoriamente responda:
    1- Resultado mais provável
    2- Expectativa de gols
    3- Mercado mais seguro
    4- Nível de confiança de 0 a 10 (justificado)
    """
    model = genai.GenerativeModel("gemini-1.5-flash")
    response = model.generate_content(prompt)
    return response.text

# ----- CARREGAMENTO DINÂMICO DE DATAS -----
hoje = datetime.now()
dias_disponiveis = [hoje + timedelta(days=i) for i in range(7)]
opcoes_datas = {
    d.strftime("%Y-%m-%d"): f"{d.strftime('%d/%m/%Y')} ({'Hoje' if i==0 else 'Amanhã' if i==1 else d.strftime('%a')})"
    for i, d in enumerate(dias_disponiveis)
}

# ==========================================
# PÁGINA 1: GRADE GERAL DE JOGOS
# ==========================================
if menu_opcao == "📅 Grade Geral de Jogos":
    st.title("⚽ Grade Geral de Jogos")
    
    datas_selecionadas = st.multiselect(
        "Selecione as datas para consultar:",
        options=list(opcoes_datas.keys()),
        default=list(opcoes_datas.keys())[:2],
        format_func=lambda x: opcoes_datas[x],
        max_selections=3
    )

    if datas_selecionadas:
        todos_jogos = []
        with st.spinner("Buscando partidas mais recentes..."):
            for data in datas_selecionadas:
                todos_jogos.extend(carregar_jogos_por_data(data))

        if todos_jogos:
            df = pd.DataFrame(todos_jogos)

            col1, col2, col3 = st.columns(3)
            with col1:
                pais_sel = st.selectbox("País", ["Todos"] + sorted(list(df["País"].unique())))
            with col2:
                liga_sel = st.selectbox("Liga", ["Todas"] + sorted(list(df["Liga"].unique())))
            with col3:
                busca = st.text_input("Time", placeholder="Nome do time...")

            df_fil = df.copy()
            if pais_sel != "Todos":
                df_fil = df_fil[df_fil["País"] == pais_sel]
            if liga_sel != "Todas":
                df_fil = df_fil[df_fil["Liga"] == liga_sel]
            if busca:
                df_fil = df_fil[
                    df_fil["Mandante"].str.contains(busca, case=False, na=False) |
                    df_fil["Visitante"].str.contains(busca, case=False, na=False)
                ]

            st.dataframe(df_fil[["Data", "Horário", "País", "Liga", "Mandante", "Placar", "Visitante", "Status"]], use_container_width=True)

# ==========================================
# PÁGINA 2: HISTÓRICO DOS ÚLTIMOS 10 JOGOS
# ==========================================
elif menu_opcao == "📊 Histórico & Estatísticas (10 Jogos)":
    st.title("📊 Histórico dos ÚLTIMOS 10 JOGOS das Equipes")

    data_sel = st.selectbox("Escolha a data do confronto:", list(opcoes_datas.keys()), format_func=lambda x: opcoes_datas[x])
    
    with st.spinner("Buscando jogos da data selecionada..."):
        jogos_data = carregar_jogos_por_data(data_sel)

    if jogos_data:
        df_j = pd.DataFrame(jogos_data)
        lista_opcoes = [f"{row['Mandante']} x {row['Visitante']} ({row['Liga']})" for _, row in df_j.iterrows()]
        
        partida_sel = st.selectbox("Selecione a partida para visualizar o histórico:", lista_opcoes)
        
        if st.button("🔎 Carregar Histórico Atualizado"):
            idx = lista_opcoes.index(partida_sel)
            jogo_info = df_j.iloc[idx]
            
            col_a, col_b = st.columns(2)
            
            with col_a:
                st.subheader(f"🏠 {jogo_info['Mandante']} - ÚLTIMOS 10 JOGOS")
                with st.spinner(f"Buscando jogos recentes de {jogo_info['Mandante']}..."):
                    h_mandante = carregar_ultimos_10_jogos(jogo_info['Mandante'])
                    if h_mandante:
                        st.dataframe(pd.DataFrame(h_mandante), use_container_width=True)
                    else:
                        st.info("Histórico não encontrado.")

            with col_b:
                st.subheader(f"🚀 {jogo_info['Visitante']} - ÚLTIMOS 10 JOGOS")
                with st.spinner(f"Buscando jogos recentes de {jogo_info['Visitante']}..."):
                    h_visitante = carregar_ultimos_10_jogos(jogo_info['Visitante'])
                    if h_visitante:
                        st.dataframe(pd.DataFrame(h_visitante), use_container_width=True)
                    else:
                        st.info("Histórico não encontrado.")
    else:
        st.info("Nenhuma partida encontrada nesta data.")

# ==========================================
# PÁGINA 3: ANÁLISE PRÉ-JOGO COM IA
# ==========================================
elif menu_opcao == "🔍 Análise Pré-Jogo (IA)":
    st.title("🔍 Análise Completa de Partida com Inteligência Artificial")

    data_a = st.selectbox("Data da partida:", list(opcoes_datas.keys()), format_func=lambda x: opcoes_datas[x])
    
    with st.spinner("Carregando jogos..."):
        jogos_a = carregar_jogos_por_data(data_a)

    if jogos_a:
        df_ia = pd.DataFrame(jogos_a)
        lista_ia = [f"{row['Mandante']} x {row['Visitante']} ({row['Liga']})" for _, row in df_ia.iterrows()]
        
        partida_ia = st.selectbox("Escolha o jogo para gerar a análise de 13 pontos:", lista_ia)
        
        if st.button("🤖 Gerar Relatório Tático com IA"):
            idx = lista_ia.index(partida_ia)
            jogo_dados = df_ia.iloc[idx].to_dict()
            
            with st.spinner("Buscando dados recentes e gerando análise..."):
                h_mand = carregar_ultimos_10_jogos(jogo_dados['Mandante'])
                h_vis = carregar_ultimos_10_jogos(jogo_dados['Visitante'])
                
                relatorio = gerar_analise_ia(jogo_dados, h_mand, h_vis)
                st.markdown("---")
                st.markdown(relatorio)
    else:
        st.info("Nenhum jogo encontrado para esta data.")

# ==========================================
# PÁGINA 4: BANCO SUPABASE
# ==========================================
elif menu_opcao == "💾 Banco de Dados Supabase":
    st.title("💾 Registros no Banco Supabase")
    st.info("Espaço reservado para consulta de relatórios e palpites salvos.")