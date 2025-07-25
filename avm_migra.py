# ==============================================================================
# BLOQUE 0: CONFIGURACIÓN INICIAL E IMPORTACIÓN DE LIBRERÍAS
# ==============================================================================

# --- Librerías estándar de Python ---
from io import BytesIO
import base64
import json

# --- Librerías principales para la aplicación y manipulación de datos ---
import streamlit as st
import pandas as pd
import geopandas as gpd
import requests  # Para descargar los archivos TopoJSON desde la URL

# --- Librerías para Visualización Geoespacial ---

# 1. Para mapas INTERACTIVOS y captura de clics
import folium
from streamlit_folium import st_folium
from shapely.geometry import Point, MultiPoint  # Utilidades para geometrías

# 2. Para gráficos ESTÁTICOS (barras, torta, etc.) y mapas para informes
#    Configuramos el backend 'Agg' para entornos sin interfaz gráfica (ej. Streamlit Cloud)
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import seaborn as sns

# --- Librería para la Carga de Datos Optimizada ---
# Para convertir los archivos TopoJSON a GeoDataFrames en memoria
import topojson as tp

# --- Configuración de Estilo para los Gráficos ---
sns.set_theme(
    style="whitegrid",
    rc={"figure.figsize": (10, 6), "axes.titlesize": 16, "axes.labelsize": 12},
)

# --- Configuración de la página ---
st.set_page_config(page_title="AVM Bogotá APP",
                   page_icon="🏠",
                   layout="centered")
st.title("🏠 AVM Bogotá - Análisis de Manzanas")

# --- Función cacheada para la carga de datos (versión optimizada) ---
@st.cache_data(ttl=3600)  # se cachea durante una hora
def cargar_datasets():
    """
    Descarga los datasets desde un repositorio de GitHub (formato TopoJSON),
    los convierte a GeoDataFrame y los devuelve en un diccionario.
    """
    datasets = {
        "localidades": "https://github.com/andres-fuentex/tfm-avm-bogota/raw/main/datos_visualizacion/datos_geograficos_topo/dim_localidad.json",
        "areas":       "https://github.com/andres-fuentex/tfm-avm-bogota/raw/main/datos_visualizacion/datos_geograficos_topo/dim_area.json",
        "manzanas":    "https://github.com/andres-fuentex/tfm-avm-bogota/raw/main/datos_visualizacion/datos_geograficos_topo/tabla_hechos.json",
        "transporte":  "https://github.com/andres-fuentex/tfm-avm-bogota/raw/main/datos_visualizacion/datos_geograficos_topo/dim_transporte.json",
        "colegios":    "https://github.com/andres-fuentex/tfm-avm-bogota/raw/main/datos_visualizacion/datos_geograficos_topo/dim_colegios.json",
    }

    dataframes = {}
    total = len(datasets)
    progress_bar = st.progress(0)
    progress_msg = st.empty()

    for idx, (nombre, url) in enumerate(datasets.items(), start=1):
        # Actualizar texto y porcentaje de progreso
        progress_msg.text(f"Cargando {nombre} ({idx}/{total})...")
        progress_bar.progress(idx / total)

        try:
            # 1. Descargar el archivo TopoJSON
            resp = requests.get(url, timeout=30)
            resp.raise_for_status()
            topo_data = resp.json()

            # 2. Extraer el nombre de la capa principal
            capa = list(topo_data['objects'].keys())[0]

            # 3. Convertir TopoJSON a GeoDataFrame usando topojson.Topology
            topology = tp.Topology(topo_data, object_name=capa)
            gdf = topology.to_gdf()

            # 4. Asegurar que tenga CRS; si no, asignar WGS84
            if gdf.crs is None:
                gdf.set_crs(epsg=4326, inplace=True)

            dataframes[nombre] = gdf

        except Exception as e:
            st.error(f"Error al cargar '{nombre}': {e}")
            return None

    # Limpiar barra y mensaje al finalizar
    progress_bar.empty()
    progress_msg.empty()
    return dataframes
