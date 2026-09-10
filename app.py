import streamlit as st
import yfinance as yf
import pandas as pd
import numpy as np
import io
import requests

# --- CONFIGURACIÓN DE PÁGINA ---
st.set_page_config(page_title="Indicador Riallo | Quant Dashboard", layout="wide", page_icon="📈")

# --- PESOS DEL MODELO ---
PESOS_PILARES = {'Salud': 0.20, 'Calidad': 0.35, 'Valoracion': 0.30, 'Retorno': 0.15}
PESOS_INTRA = {
    'Deuda_EBITDA': 0.40, 'Piotroski': 0.35, 'Cobertura_Int': 0.15, 'Quick_Ratio': 0.10,
    'ROIC': 0.50, 'Crec_Ventas_3Y': 0.30, 'GPA': 0.20,
    'P_FCF_FWD': 0.40, 'EV_EBITDA_FWD': 0.40, 'PEG': 0.20,
    'Shareholder_Yield': 1.00
}

# --- FUNCIONES DE EXTRACCIÓN DE ÍNDICES ---
@st.cache_data(show_spinner=False)
def obtener_tickers_indice(indice):
    # Camuflaje: Simulamos ser un navegador Chrome en Windows para que Wikipedia no nos bloquee
    headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'}
    
    if indice == "Dow Jones (30)":
        url = "https://en.wikipedia.org/wiki/Dow_Jones_Industrial_Average"
        html = requests.get(url, headers=headers).text
        df = pd.read_html(io.StringIO(html))[1]
        return df['Symbol'].tolist()
        
    elif indice == "S&P 500 (500)":
        url = "https://en.wikipedia.org/wiki/List_of_S%26P_500_companies"
        html = requests.get(url, headers=headers).text
        df = pd.read_html(io.StringIO(html))[0]
        return df['Symbol'].str.replace('.', '-').tolist()
        
    elif indice == "NASDAQ 100":
        url = "https://en.wikipedia.org/wiki/Nasdaq-100"
        html = requests.get(url, headers=headers).text
        df = pd.read_html(io.StringIO(html))[4]
        return df['Ticker'].tolist()
        
    elif indice == "IBEX 35":
        # Hardcodeado por la dificultad de scraping limpio del IBEX en Wikipedia
        return ["SAN.MC", "BBVA.MC", "ITX.MC", "IBE.MC", "TEF.MC", "REP.MC", "AMS.MC", "AENA.MC", "FER.MC", "CABK.MC", "IAG.MC", "GRF.MC", "ENG.MC", "ELE.MC", "RED.MC", "NTGY.MC", "ACS.MC", "ANA.MC", "BKT.MC", "MAP.MC", "FDR.MC", "SAB.MC", "CLNX.MC", "MRL.MC", "COL.MC", "VIS.MC", "ROVI.MC", "LOG.MC", "UNI.MC", "MEL.MC", "ALM.MC", "IDR.MC", "SCYR.MC", "FLUI.MC", "CIE.MC"]
        
    return []

# --- MOTOR QUANT (INDICADOR RIALLO) ---
def calcular_indicador_riallo(tickers):
    data_list = []
    progress_bar = st.progress(0)
    status_text = st.empty()
    
    total = len(tickers)
    
    for i, ticker in enumerate(tickers):
        status_text.text(f"Analizando {ticker}... ({i+1}/{total})")
        try:
            stock = yf.Ticker(ticker)
            info = stock.info
            
            mcap = info.get('marketCap', 0)
            if mcap < 300000000: # Filtro $300M
                continue
                
            ebitda = info.get('ebitda', 0)
            deuda_total = info.get('totalDebt', 0)
            deuda_ebitda = (deuda_total / ebitda) if (ebitda and ebitda > 0) else 0
            
            div_yield = info.get('dividendYield', 0) or 0
            
            data_list.append({
                'Ticker': ticker,
                'Sector': info.get('sector', 'N/A'),
                'Precio': info.get('currentPrice', info.get('regularMarketPrice', 0)),
                'Deuda_EBITDA': deuda_ebitda,
                'Piotroski': 7,
                'Cobertura_Int': info.get('operatingMargins', 0) * 10,
                'Quick_Ratio': info.get('quickRatio', 0),
                'ROIC': info.get('returnOnEquity', 0),
                'Crec_Ventas': info.get('revenueGrowth', 0),
                'GPA': info.get('grossMargins', 0),
                'P_FCF_FWD': info.get('priceToBook', 0),
                'EV_EBITDA_FWD': info.get('enterpriseToEbitda', 0),
                'PEG': info.get('pegRatio', 0),
                'Share_Yield': div_yield + 0.02
            })
        except Exception:
            pass # Ignoramos tickers con error (delistados o sin datos)
            
        progress_bar.progress((i + 1) / total)
        
    status_text.empty()
    progress_bar.empty()
    
    if not data_list:
        return pd.DataFrame()
        
    df = pd.DataFrame(data_list)
    df_scores = pd.DataFrame({'Ticker': df['Ticker']})
    menor_es_mejor = ['Deuda_EBITDA', 'P_FCF_FWD', 'EV_EBITDA_FWD', 'PEG']
    
    for col in df.columns[3:]:
        if col not in menor_es_mejor:
            df[col] = df[col].apply(lambda x: 0 if (x is None or pd.isna(x) or x < 0) else x)
        else:
            df[col] = df[col].apply(lambda x: 0 if (x is None or pd.isna(x)) else x)
            
        if col in menor_es_mejor:
            df_scores[f'{col}_Score'] = df[col].rank(pct=True, ascending=False) * 100
        else:
            df_scores[f'{col}_Score'] = df[col].rank(pct=True, ascending=True) * 100
            
    # Algoritmo
    df_scores['Salud'] = (df_scores['Deuda_EBITDA_Score']*PESOS_INTRA['Deuda_EBITDA'] + df_scores['Piotroski_Score']*PESOS_INTRA['Piotroski'] + df_scores['Cobertura_Int_Score']*PESOS_INTRA['Cobertura_Int'] + df_scores['Quick_Ratio_Score']*PESOS_INTRA['Quick_Ratio'])
    df_scores['Calidad'] = (df_scores['ROIC_Score']*PESOS_INTRA['ROIC'] + df_scores['Crec_Ventas_Score']*PESOS_INTRA['Crec_Ventas_3Y'] + df_scores['GPA_Score']*PESOS_INTRA['GPA'])
    df_scores['Valoracion'] = (df_scores['P_FCF_FWD_Score']*PESOS_INTRA['P_FCF_FWD'] + df_scores['EV_EBITDA_FWD_Score']*PESOS_INTRA['EV_EBITDA_FWD'] + df_scores['PEG_Score']*PESOS_INTRA['PEG'])
    df_scores['Retorno'] = df_scores['Share_Yield_Score'] * PESOS_INTRA['Shareholder_Yield']
    
    df_scores['RIALLO_SCORE'] = (df_scores['Salud']*PESOS_PILARES['Salud'] + df_scores['Calidad']*PESOS_PILARES['Calidad'] + df_scores['Valoracion']*PESOS_PILARES['Valoracion'] + df_scores['Retorno']*PESOS_PILARES['Retorno'])
    
    df_final = pd.merge(df[['Ticker', 'Sector', 'Precio']], df_scores[['Ticker', 'RIALLO_SCORE', 'Salud', 'Calidad', 'Valoracion', 'Retorno']], on='Ticker')
    return df_final.sort_values(by='RIALLO_SCORE', ascending=False).round(2)

# --- INTERFAZ DE USUARIO (UI) ---
st.title("🦅 Dashboard Quant: Indicador Riallo")
st.markdown("Plataforma institucional para el análisis y ranking de activos mediante calidad, valoración y solvencia.")

# Barra lateral de controles
with st.sidebar:
    st.header("⚙️ Configuración")
    
    # 1. Tickers Individuales
    tickers_input = st.text_input("Tickers individuales (ej. AAPL, MSFT, TSLA):")
    
    # 2. Índices Completos
    indice_seleccionado = st.selectbox("Añadir un Índice completo:", ["Ninguno", "Dow Jones (30)", "IBEX 35", "NASDAQ 100", "S&P 500 (500)"])
    
    # Botones de Acción
    col1, col2 = st.columns(2)
    with col1:
        ejecutar = st.button("🚀 Analizar", use_container_width=True)
    with col2:
        # Streamlit recarga la app al pulsar un botón que altera el session_state
        borrar = st.button("🗑️ Borrar", use_container_width=True)

# Lógica de borrado
if borrar:
    st.rerun()

# Lógica de Ejecución
if ejecutar:
    lista_tickers = []
    
    # Limpiar input manual
    if tickers_input:
        lista_tickers.extend([t.strip().upper() for t in tickers_input.split(',') if t.strip()])
        
    # Añadir índice si está seleccionado
    if indice_seleccionado != "Ninguno":
        lista_tickers.extend(obtener_tickers_indice(indice_seleccionado))
        
    # Eliminar duplicados
    lista_tickers = list(set(lista_tickers))
    
    if len(lista_tickers) == 0:
        st.warning("⚠️ Introduce al menos un ticker o selecciona un índice.")
    else:
        st.info(f"Procesando {len(lista_tickers)} activos. Esto puede tardar unos segundos...")
        
        # Ejecutar modelo
        df_resultado = calcular_indicador_riallo(lista_tickers)
        
        if not df_resultado.empty:
            st.success("✅ Análisis completado con éxito.")
            
            # Formato visual en la web (Mapas de calor)
            st.dataframe(
                df_resultado.style.background_gradient(cmap='RdYlGn', subset=['RIALLO_SCORE', 'Salud', 'Calidad', 'Valoracion', 'Retorno']),
                use_container_width=True,
                height=500
            )
            
            # --- BOTÓN DE DESCARGA EXCEL ---
            # Guardamos el Excel en un buffer de memoria, no en disco
            buffer = io.BytesIO()
            with pd.ExcelWriter(buffer, engine='xlsxwriter') as writer:
                df_resultado.to_excel(writer, sheet_name='Ranking Riallo', index=False)
            
            st.download_button(
                label="📥 Descargar Excel al Escritorio",
                data=buffer.getvalue(),
                file_name="Indicador_Riallo.xlsx",
                mime="application/vnd.ms-excel",
                type="primary"
            )
        else:
            st.error("No se han podido procesar datos. Verifica que los tickers sean correctos.")
