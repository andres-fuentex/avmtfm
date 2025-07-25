## ==============================================================================
# BLOQUE 0: CONFIGURACIÓN INICIAL E IMPORTACIÓN DE LIBRERÍAS
# ==============================================================================

# --- Librerías estándar de Python ---
from io import BytesIO
import base64

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
#    Configuramos el backend para entornos sin interfaz gráfica
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

# ==============================================================================
# BLOQUE 1: CARGA DE DATOS
# ==============================================================================

@st.cache_data(ttl=3600)
def cargar_datasets():
    """
    Descarga los datasets TopoJSON, los convierte a GeoDataFrame y los
    devuelve en un diccionario. Se usa TopoJSON para reducir el tamaño
    de transferencia y se cachean los resultados durante una hora.
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
            # 1. Descargar el TopoJSON
            response = requests.get(url, timeout=30)
            response.raise_for_status()
            topo_data = response.json()

            # 2. Extraer nombre de la capa y crear un Topology
            layer_name = list(topo_data["objects"].keys())[0]
            topology = tp.Topology(topo_data, object_name=layer_name)

            # 3. Convertir a GeoDataFrame
            gdf = topology.to_gdf()
            if gdf.crs is None:
                gdf.set_crs(epsg=4326, inplace=True)

            dataframes[nombre] = gdf

        except Exception as e:
            st.error(f"Error al cargar '{nombre}': {e}")
            return None

    progress_bar.empty()
    progress_msg.empty()
    return dataframes

# Control del flujo: inicializamos el paso actual si no existe
if "step" not in st.session_state:
    st.session_state.step = 1

# ------------------------------------------------------------------------------
# Paso 1: Bienvenida y carga de datos
# ------------------------------------------------------------------------------
if st.session_state.step == 1:
    st.markdown("""
    ## Bienvenido al Análisis de Valorización de Manzanas de Bogotá  
    Esta aplicación hace uso de datos abiertos tratados bajo metodologías académicas.  
    """)

    with st.spinner('Cargando datasets optimizados...'):
        dataframes = cargar_datasets()

    # Comprobar si la carga de datos fue exitosa
    if dataframes:
        st.success('✅ Todos los datos han sido cargados correctamente.')
        if st.button("Iniciar Análisis"):
            # Guardar los GeoDataFrames en el estado de la sesión
            for nombre, df in dataframes.items():
                st.session_state[nombre] = df
            st.session_state.step = 2
            st.rerun()
    else:
        st.error("❌ No se pudieron cargar los datos. Por favor, recarga la página o contacta al administrador.")

# ------------------------------------------------------------------------------
# Paso 2: Selección de Localidad
# ------------------------------------------------------------------------------
elif st.session_state.step == 2:
    st.header("🌆 Selección de Localidad")
    st.markdown("Haz clic en la localidad del mapa que te interesa analizar.")

    # Recuperar el GeoDataFrame de localidades desde el estado
    localidades_gdf = st.session_state.localidades

    # Calcular centro y límites para la vista inicial del mapa
    bounds = localidades_gdf.total_bounds
    center = [(bounds[1] + bounds[3]) / 2, (bounds[0] + bounds[2]) / 2]

    # Crear mapa con Folium
    mapa = folium.Map(location=center, zoom_start=10, tiles="CartoDB positron")

    # Añadir las localidades al mapa
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

    # Mostrar el mapa y capturar la interacción del clic
    map_data = st_folium(mapa,
                         width=700,
                         height=500,
                         returned_objects=["last_object_clicked_properties"])

    # Si se ha hecho clic, guardar el nombre de la localidad
    if map_data and map_data.get("last_object_clicked_properties"):
        clicked_name = map_data["last_object_clicked_properties"].get("nombre_localidad")
        st.session_state.localidad_clic = clicked_name

    # Mostrar la localidad seleccionada y ofrecer un botón de confirmación
    if "localidad_clic" in st.session_state:
        st.text_input("✅ Localidad seleccionada",
                      value=st.session_state.localidad_clic,
                      disabled=True)
        if st.button("✅ Confirmar y Continuar"):
            # Guardar la selección final y avanzar al siguiente paso
            st.session_state.localidad_sel = st.session_state.localidad_clic
            st.session_state.step = 3
            st.rerun()

    # Botón para volver al inicio
    if st.button("🔄 Volver al Inicio"):
        # Limpiar el estado relacionado con la selección
        for key in ("localidad_clic", "localidad_sel"):
            if key in st.session_state:
                del st.session_state[key]
        st.session_state.step = 1
        st.rerun()

    # Mensaje informativo si aún no se ha seleccionado nada
    if "localidad_clic" not in st.session_state:
        st.info("Selecciona una localidad en el mapa y confírmala para continuar.")

