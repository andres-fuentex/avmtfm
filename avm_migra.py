# ==============================================================================
# BLOQUE 0: CONFIGURACIÓN INICIAL E IMPORTACIÓN DE LIBRERÍAS
# ==============================================================================

from io import BytesIO
import base64

import streamlit as st
import pandas as pd
import geopandas as gpd
import requests

import folium
from streamlit_folium import st_folium
from shapely.geometry import Point, MultiPoint

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import seaborn as sns

import topojson as tp

sns.set_theme(
    style="whitegrid",
    rc={"figure.figsize": (10, 6), "axes.titlesize": 16, "axes.labelsize": 12},
)

st.set_page_config(page_title="AVM Bogotá APP",
                   page_icon="🏠",
                   layout="centered")
st.title("🏠 AVM Bogotá - Análisis de Manzanas")

# ==============================================================================
# BLOQUE 1: CARGA DE DATOS
# ==============================================================================

@st.cache_data(ttl=3600)
def cargar_datasets():
    """
    Descarga los datasets TopoJSON, los convierte a GeoDataFrame y los
    devuelve en un diccionario. Se hace un intento con Topology.to_gdf();
    si falla (p. ej. con MultiPoint), se usa tp.GeoDataFrame.from_feature().
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
        progress_msg.text(f"Cargando {nombre} ({idx}/{total})…")
        progress_bar.progress(idx / total)

        try:
            # Descargar y parsear el TopoJSON
            response = requests.get(url, timeout=30)
            response.raise_for_status()
            topo_data = response.json()

            # Nombre de la capa
            layer_name = list(topo_data["objects"].keys())[0]

            # Intento 1: Topology.to_gdf()
            try:
                topology = tp.Topology(topo_data, object_name=layer_name)
                gdf = topology.to_gdf()
            except Exception:
                # Intento 2: método from_feature() (compatibilidad con MultiPoint)
                gdf = tp.GeoDataFrame.from_feature(topo_data, layer_name)

            # Asignar CRS si es necesario
            if gdf.crs is None:
                gdf.set_crs(epsg=4326, inplace=True)

            dataframes[nombre] = gdf

        except Exception as e:
            st.error(f"Error al cargar '{nombre}': {e}")
            return None

    progress_bar.empty()
    progress_msg.empty()
    return dataframes

# ------------------------------------------------------------------------------
# Control del flujo de la aplicación
# ------------------------------------------------------------------------------
if "step" not in st.session_state:
    st.session_state.step = 1

# Paso 1: Bienvenida y carga de datos
if st.session_state.step == 1:
    st.markdown("""
    ## Bienvenido al Análisis de Valorización de Manzanas de Bogotá  
    Esta aplicación hace uso de datos abiertos tratados bajo metodologías académicas.  
    """)

    with st.spinner('Cargando datasets optimizados...'):
        dataframes = cargar_datasets()

    if dataframes:
        st.success('✅ Todos los datos han sido cargados correctamente.')
        if st.button("Iniciar Análisis"):
            for nombre, df in dataframes.items():
                st.session_state[nombre] = df
            st.session_state.step = 2
            st.rerun()
    else:
        st.error("❌ No se pudieron cargar los datos. Por favor, recarga la página o contacta al administrador.")

# Paso 2: Selección de Localidad
elif st.session_state.step == 2:
    st.header("🌆 Selección de Localidad")
    st.markdown("Haz clic en la localidad del mapa que te interesa analizar.")

    localidades_gdf = st.session_state.localidades
    bounds = localidades_gdf.total_bounds
    center = [(bounds[1] + bounds[3]) / 2, (bounds[0] + bounds[2]) / 2]

    mapa = folium.Map(location=center, zoom_start=10, tiles="CartoDB positron")

    folium.GeoJson(
        localidades_gdf,
        style_function=lambda feature: {
            "fillColor": "#2596be",
            "color": "black",
            "weight": 1,
            "fillOpacity": 0.3
        },
        highlight_function=lambda feature: {
            "weight": 3,
            "color": "#e30613",
            "fillOpacity": 0.6
        },
        tooltip=folium.GeoJsonTooltip(
            fields=["nombre_localidad"],
            aliases=["Localidad:"],
            labels=True,
            sticky=True
        )
    ).add_to(mapa)

    map_data = st_folium(mapa,
                         width=700,
                         height=500,
                         returned_objects=["last_object_clicked_properties"])

    if map_data and map_data.get("last_object_clicked_properties"):
        st.session_state.localidad_clic = map_data["last_object_clicked_properties"].get("nombre_localidad")

    if "localidad_clic" in st.session_state:
        st.text_input("✅ Localidad seleccionada",
                      value=st.session_state.localidad_clic,
                      disabled=True)
        if st.button("✅ Confirmar y Continuar"):
            st.session_state.localidad_sel = st.session_state.localidad_clic
            st.session_state.step = 3
            st.rerun()

    if st.button("🔄 Volver al Inicio"):
        for key in ("localidad_clic", "localidad_sel"):
            st.session_state.pop(key, None)
        st.session_state.step = 1
        st.rerun()

    if "localidad_clic" not in st.session_state:
        st.info("Selecciona una localidad en el mapa y confírmala para continuar.")
