import streamlit as st
import geopandas as gpd
import requests
import folium
from streamlit_folium import st_folium
from shapely.geometry import Point
import plotly.express as px
import plotly.graph_objects as go
import plotly.io as pio
from io import BytesIO
import base64
import time
import json

# --- Configuración de la Página ---
st.set_page_config(page_title="AVM Bogotá APP", page_icon="🏠", layout="centered")
st.title("🏠 AVM Bogotá - Análisis de Manzanas")

# --- Función cacheada para la carga de datos (con manejo de errores y reintentos) ---
@st.cache_data
def cargar_datasets():
    datasets = {
        "localidades": "https://github.com/andres-fuentex/tfm-avm-bogota/raw/main/datos_visualizacion/datos_geograficos_geo/dim_localidad.geojson",
        "areas": "https://github.com/andres-fuentex/tfm-avm-bogota/raw/main/datos_visualizacion/datos_geograficos_geo/dim_area.geojson",
        "manzanas": "https://github.com/andres-fuentex/tfm-avm-bogota/raw/main/datos_visualizacion/datos_geograficos_geo/tabla_hechos.geojson",
        "transporte": "https://github.com/andres-fuentex/tfm-avm-bogota/raw/main/datos_visualizacion/datos_geograficos_geo/dim_transporte.geojson",
        "colegios": "https://github.com/andres-fuentex/tfm-avm-bogota/raw/main/datos_visualizacion/datos_geograficos_geo/dim_colegios.geojson"
    }

    dataframes = {}
    total = len(datasets)
    progress_bar = st.progress(0, text="Iniciando carga de datos...")

    for idx, (nombre, url) in enumerate(datasets.items(), start=1):
        progress_text = f"Cargando {nombre} ({idx}/{total})..."
        progress_bar.progress(idx / total, text=progress_text)
        
        max_retries = 3
        retry_delay = 2

        for attempt in range(max_retries):
            try:
                response = requests.get(url, timeout=30)
                response.raise_for_status()
                
                # Leer el contenido como JSON usando la librería json
                geojson_data = json.loads(response.text)
                
                # Crear el GeoDataFrame desde el JSON
                dataframes[nombre] = gpd.GeoDataFrame.from_features(geojson_data["features"], crs="EPSG:4326")
                break  # Si la carga tiene éxito, salir del bucle
            
            except requests.exceptions.RequestException as e:
                st.warning(f"Intento {attempt + 1}/{max_retries} fallido al cargar {nombre}: {e}")
                if attempt < max_retries - 1:
                    time.sleep(retry_delay)  # Esperar antes de reintentar
                else:
                    st.error(f"Error al cargar {nombre} después de {max_retries} intentos: {e}")
                    return None  # Detener la carga si no se puede descargar después de varios intentos
            except json.JSONDecodeError as e:
                st.error(f"Error al decodificar JSON para {nombre}: {e}. Detalle: {e}")
                return None # No reintentar si el problema es el JSON
            except Exception as e:
                st.error(f"Error al procesar {nombre}: {e}")
                return None

    progress_bar.empty()
    return dataframes

# --- Control de flujo ---
if "step" not in st.session_state:
    st.session_state.step = 1

# --- Bloque 1: Carga de datos ---
if st.session_state.step == 1:
    st.markdown(
        """
        Bienvenido al sistema de valorización automatizada de manzanas catastrales en Bogotá.
        """
    )
    with st.spinner('Cargando datasets...'):
        dataframes = cargar_datasets()

    if dataframes:  # Verificar que la carga de datos fue exitosa
        st.success('✅ Todos los datos han sido cargados correctamente.')

        if st.button("Iniciar Análisis"):
            for nombre, df in dataframes.items():
                st.session_state[nombre] = df
            st.session_state.step = 2
            st.rerun()
    else:
        st.error("❌ Error al cargar los datasets. Por favor, revise las URLs o la conexión a Internet.")