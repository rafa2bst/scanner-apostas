import streamlit as st
import requests
import pandas as pd
from datetime import datetime, timedelta
from supabase import create_client, Client

# Configurações da página
st.set_page_config(
    page_title="Scanner de Apostas - Login",
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
        st.error("Erro nas credenciais do Supabase. Verifique os Secrets no Streamlit Cloud.")
        return None

supabase = init_supabase()

# ----- SISTEMA DE AUTENTICAÇÃO -----
if "user" not in st.session_state:
    st.session_state.user = None

def fazer_login(email, password):
    try:
        res = supabase.auth.sign_in_with_password({"email": email, "password": password})
        st.session_state.user = res.user
        st.success("Login realizado com sucesso!")
        st.rerun()
    except Exception as e:
        st.error("Erro ao fazer login: E-mail ou senha incorretos.")

def fazer_logout():
    supabase.auth.sign_out()
    st.session_state.user = None
    st.rerun()

# Barra Lateral - Tela de Login
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
    st.info("Por favor, faça login na barra lateral esquerda para acessar o scanner de jogos.")
    st.stop() # Interrompe a execução do restante da página

# ----- CONTEÚDO PROTEGIDO (EXIBIDO APENAS APÓS LOGIN) -----

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

def salvar_no_supabase(df_jogos):
    registros = []
    for item in df_jogos.to_dict(orient="records"):
        registros.append({
            "data": item["Data"],
            "pais": item["País"],
            "liga": item["Liga"],
            "horario": item["Horário"],
            "status": item["Status"],
            "mandante": item["Mandante"],
            "placar": item["Placar"],
            "visitante": item["Visitante"]
        })

    try:
        supabase.table("jogos").insert(registros).execute()
        st.success(f"✅ {len(registros)} jogos salvos no banco com sucesso!")
    except Exception as e:
        st.error(f"Erro ao salvar: {e}")

def buscar_do_supabase():
    try:
        res = supabase.table("jogos").select("*").order("created_at", desc=True).execute()
        return res.data
    except Exception as e:
        st.error(f"Erro ao buscar dados: {e}")
        return []

# ----- INTERFACE PRINCIPAL -----
st.title("⚽ Grade de Jogos - Área do Usuário")

aba1, aba2 = st.tabs(["📅 Jogos da API", "💾 Salvos no Supabase"])

with aba1:
    st.markdown("Selecione **até 3 datas** para consultar os jogos:")
    hoje = datetime.now()
    dias_disponiveis = [hoje + timedelta(days=i) for i in range(7)]

    opcoes_datas = {
        d.strftime("%Y-%m-%d"): f"{d.strftime('%d/%m/%Y')} ({'Hoje' if i==0 else 'Amanhã' if i==1 else d.strftime('%a')})"
        for i, d in enumerate(dias_disponiveis)
    }

    datas_selecionadas = st.multiselect(
        "Datas:",
        options=list(opcoes_datas.keys()),
        default=list(opcoes_datas.keys())[:3],
        format_func=lambda x: opcoes_datas[x],
        max_selections=3
    )

    if st.button("Atualizar Busca"):
        st.cache_data.clear()

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

            if st.button("💾 Salvar Tabela no Supabase"):
                salvar_no_supabase(df_fil)

with aba2:
    st.subheader("Registros Gravados no Supabase")
    if st.button("Carregar Dados do Banco"):
        dados_bd = buscar_do_supabase()
        if dados_bd:
            df_bd = pd.DataFrame(dados_bd)
            st.dataframe(df_bd[['data', 'pais', 'liga', 'horario', 'status', 'mandante', 'placar', 'visitante']], use_container_width=True)
        else:
            st.info("Nenhum registro encontrado.")