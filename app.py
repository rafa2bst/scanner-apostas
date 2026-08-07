import google.generativeai as genai
import streamlit as st

# Configura a IA
genai.configure(api_key=st.secrets["GEMINI_API_KEY"])


def gerar_analise_completa(dados_partida):
    """Envia os dados reais da partida obtidos da API para a IA gerar o relatório de 13 pontos."""

    prompt = f"""
    Você é um analista tático e estatístico profissional de futebol.
    Analise a seguinte partida entre {dados_partida["mandante"]} x {dados_partida["visitante"]}:

    - Campeonato: {dados_partida["liga"]} ({dados_partida["pais"]})
    - Data e Horário: {dados_partida["data"]} às {dados_partida["horario"]}
    - Escalação Mandante: {dados_partida.get("escalacao_home", "Não confirmada")}
    - Escalação Visitante: {dados_partida.get("escalacao_away", "Não confirmada")}
    - Histórico H2H e Estatísticas Recentes: {dados_partida.get("stats_recentes", "Sem dados")}

    Gere uma análise estruturada exatamente com os 13 tópicos abaixo:
    1- Momento das equipes
    2- Necessidade do resultado (Must Win)
    3- Análise da formação (com escalação confirmada)
    4- Linha de frente e desfalques de impacto
    5- Mando de campo
    6- Métricas de Expectativa (xG / xGA / Média de gols)
    7- Confrontos diretos (H2H)
    8- Estilo de jogo das equipes
    9- Extra campo e bastidores
    10- Fator clima e gramado
    11- Perfil do Árbitro
    12- Curiosidades / Última hora
    13- Padrão mais recorrente das equipes

    No final, responda diretamente:
    - Resultado mais provável
    - Expectativa de gols
    - Mercado mais seguro
    - Nível de confiança de 0 a 10 (com justificativa)
    """

    model = genai.GenerativeModel("gemini-2.5-flash")
    response = model.generate_content(prompt)
    return response.text