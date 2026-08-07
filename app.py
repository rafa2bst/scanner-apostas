import streamlit as st
import requests
import pandas as pd
from datetime import datetime, timedelta
from supabase import create_client, Client
import google.generativeai as genai

# Configurações da página
st.set_page_config(
    page_title="Scanner de Apostas - Análise com IA",
    page_icon="⚽",
    layout="wide"
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

# Barra Lateral - Login
st.sidebar.title("🔐 Área Restrita")

if st.session_state.user is None:
    st.sidebar.subheader("Acesse sua conta")
    email_input = st.sidebar.text_input("E-mail")
    senha_input = st.sidebar.text_input("Senha", type="password")
    
    if st.sidebar.button("Entrar"):
        if email_input and senha_input:
            fazer_login(email_input, senha_input)
        else:
            st.sidebar.warning("Preencha e-mail e senha.")
            
    st.title("🔒 Acesso Restrito")
    st.info("Por favor, faça login na barra lateral esquerda para acessar o scanner.")
    st.stop()

st.sidebar.write(f"👤 Conectado como: **{st.session_state.user.email}**")
if st.sidebar.button("Sair (Logout)"):
    fazer_logout()

# Configurações da API de Futebol
API_KEY = "17948bfd5d3ed61ae0cb0aa7a97f5e09"
BASE_URL = "https://v3.football.api-sports.io"
HEADERS = {"x-apisports-key": API_KEY}

STATUS_MAP = {
    'NS': 'Não Iniciado', '1H': '1º Tempo', 'HT': 'Intervalo',
    '2H': '2º Tempo', 'FT': 'Encerrado', 'AET': 'Prorrogação',
    'PEN': 'Pênaltis', 'P': 'Adiado', 'CANC': 'Cancelado'
}

@st.cache_data(ttl=3600)
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

# FUNÇÃO DE ANÁLISE USANDO A IA (13 PONTOS) - COM NOME DO MODELO CORRIGIDO
def gerar_analise_ia(dados_jogo):
    prompt = f"""
    Você é um especialista tático e estatístico em apostas esportivas.
    Analise a partida a seguir: {dados_jogo["Mandante"]} x {dados_jogo["Visitante"]}
    - Campeonato: {dados_jogo["Liga"]} ({dados_jogo["País"]})
    - Data/Horário: {dados_jogo["Data"]} às {dados_jogo["Horário"]}
    - Status: {dados_jogo["Status"]}

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

# ----- INTERFACE PRINCIPAL -----
st.title("⚽ Grade de Jogos & Analisador com IA")

aba1, aba2 = st.tabs(["📅 Jogos & Análise com IA", "💾 Histórico no Supabase"])

with aba1:
    hoje = datetime.now()
    dias_disponiveis = [hoje + timedelta(days=i) for i in range(7)]

    opcoes_datas = {
        d.strftime("%Y-%m-%d"): f"{d.strftime('%d/%m/%Y')} ({'Hoje' if i==0 else 'Amanhã' if i==1 else d.strftime('%a')})"
        for i, d in enumerate(dias_disponiveis)
    }

    datas_selecionadas = st.multiselect(
        "Selecione até 3 datas:",
        options=list(opcoes_datas.keys()),
        default=list(opcoes_datas.keys())[:3],
        format_func=lambda x: opcoes_datas[x],
        max_selections=3
    )

    if datas_selecionadas:
        todos_jogos = []
        with st.spinner("Buscando partidas..."):
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

            st.dataframe(df_fil, use_container_width=True)

            st.divider()

            # SEÇÃO DE GERAR ANÁLISE COM A IA
            st.subheader("🔍 Gerar Análise Pré-Jogo (13 Pontos)")
            
            lista_partidas = [f"{row['Mandante']} x {row['Visitante']} ({row['Data']})" for _, row in df_fil.iterrows()]
            
            if lista_partidas:
                partida_escolhida = st.selectbox("Escolha uma partida da lista acima:", lista_partidas)
                
                if st.button("🤖 Gerar Análise Detalhada com IA"):
                    with st.spinner("A IA está analisando os 13 pontos da partida... Aguarde uns segundos."):
                        idx = lista_partidas.index(partida_escolhida)
                        jogo_dados = df_fil.iloc[idx].to_dict()
                        
                        relatorio = gerar_analise_ia(jogo_dados)
                        st.markdown("---")
                        st.markdown(relatorio)

with aba2:
    st.subheader("Registros Salvos")
    st.info("Espaço reservado para consultar análises salvas no banco Supabase.")