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
import streamlit.components.v1 as components
import json
import pydeck as pdk

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

# --- Bloque 2: Selección de Localidad ---
elif st.session_state.step == 2:
    st.header("🌆 Selección de Localidad")
    st.markdown("Haz clic en la localidad que te interesa:")

    localidades = st.session_state.localidades
    if localidades is None:
        st.error("❌ No se cargaron los datos de las localidades. Por favor, reinicia la aplicación.")
        st.stop()

    bounds = localidades.total_bounds
    center = [(bounds[1] + bounds[3]) / 2, (bounds[0] + bounds[2]) / 2]

    mapa = folium.Map(location=center, zoom_start=11, tiles="CartoDB positron")

    folium.GeoJson(
        localidades,
        style_function=lambda feature: {"fillColor": "#3388ff", "color": "black", "weight": 1, "fillOpacity": 0.2},
        highlight_function=lambda feature: {"weight": 2, "color": "red"},
        tooltip=folium.GeoJsonTooltip(fields=["nombre_localidad"], labels=False)
    ).add_to(mapa)

    result = st_folium(mapa, width=700, height=500, returned_objects=["last_clicked"])

    clicked = result.get("last_clicked")
    if clicked and "lat" in clicked and "lng" in clicked:
        punto = Point(clicked["lng"], clicked["lat"])
        for _, row in st.session_state.localidades.iterrows():
            if row["geometry"].contains(punto):
                st.session_state.localidad_clic = row["nombre_localidad"]
                break
        else:
            st.session_state.localidad_clic = None
            st.warning("⚠️ No se encontró ninguna localidad en la ubicación seleccionada.") # Mensaje mejorado
    else:
        st.session_state.localidad_clic = None

    if "localidad_clic" in st.session_state and st.session_state.localidad_clic:
        st.text_input("✅ Localidad seleccionada", value=st.session_state.localidad_clic, disabled=True)
        if st.button("✅ Confirmar selección"):
            st.session_state.localidad_sel = st.session_state.localidad_clic
            st.session_state.step = 3
            st.rerun()

    if st.button("🔄 Volver al Inicio"):
        st.session_state.step = 1
        st.rerun()

    if "localidad_sel" not in st.session_state:
        st.info("Selecciona una localidad y confírmala para continuar.")

# --- Bloque 3: Selección de Manzana ---
# --- Bloque 3: Selección de Manzana ---
# --- Bloque 3: Selección de Manzana ---


# --- Bloque 3: Selección de Manzana ---
elif st.session_state.step == 3:
    st.subheader(f"🏘️ Análisis y Selección de Manzana en {st.session_state.localidad_sel}")

    localidades = st.session_state.localidades
    areas = st.session_state.areas
    manzanas = st.session_state.manzanas
    localidad_sel = st.session_state.localidad_sel

    # 1. Filtrar Manzanas por Localidad
    cod_localidad_series = localidades[localidades["nombre_localidad"] == localidad_sel]["num_localidad"]
    if cod_localidad_series.empty:
        st.error(f"No se pudo encontrar el código para la localidad '{localidad_sel}'.")
        st.stop()
    cod_localidad = cod_localidad_series.values[0]
    manzanas_localidad_sel = manzanas[manzanas["num_localidad"] == cod_localidad].copy()

    if manzanas_localidad_sel.empty:
        st.warning("⚠️ No se encontraron manzanas para la localidad seleccionada.")
        st.stop()

    # 2. Enriquecer con información de áreas (usos de suelo)
    areas_sel = areas[areas["num_localidad"] == cod_localidad]
    if not areas_sel.empty:
        manzanas_localidad_sel = manzanas_localidad_sel.merge(
            areas_sel[["id_area", "uso_pot_simplificado"]], on="id_area", how="left"
        )
    manzanas_localidad_sel["uso_pot_simplificado"] = manzanas_localidad_sel["uso_pot_simplificado"].fillna("Sin clasificación")

    # 3. Mapa de Colores para Usos de Suelo
    usos_unicos = manzanas_localidad_sel["uso_pot_simplificado"].unique()
    palette = px.colors.qualitative.Plotly
    color_map = {uso: palette[i % len(palette)] for i, uso in enumerate(usos_unicos)}
    color_map["Sin clasificación"] = "#808080"  # Gris para "Sin clasificación"
    st.session_state.color_map = color_map

    # 4. Preparar los datos para pydeck
    manzanas_localidad_sel['fill_color'] = manzanas_localidad_sel['uso_pot_simplificado'].map(color_map)
    manzanas_localidad_sel['line_color'] = "#000000"  # Color del borde

    # Convertir GeoDataFrame a formato que pydeck pueda usar
    geojson = json.loads(manzanas_localidad_sel.to_json())

    # 5. Crear la capa GeoJsonLayer
    geojson_layer = pdk.Layer(
        "GeoJsonLayer",
        data=geojson,
        get_fill_color="feature.properties.fill_color ? hexToRgb(feature.properties.fill_color) : [128, 128, 128]",
        get_line_color="feature.properties.line_color ? hexToRgb(feature.properties.line_color) : [0, 0, 0]",
        get_line_width=1,
        pickable=True,
        auto_highlight=True,
        tooltip={
            "html": "Manzana: {properties.id_manzana_unif}<br>Uso POT: {properties.uso_pot_simplificado}",
            "style": {
                "backgroundColor": "steelblue",
                "color": "white",
                "fontFamily": '"Helvetica Neue", Arial, sans-serif',
                "fontSize": "12px",
                "padding": "4px",
            },
        },
    )

    # 6. Calcular el viewport
    bounds = manzanas_localidad_sel.total_bounds
    view_state = pdk.ViewState(
        latitude=(bounds[1] + bounds[3]) / 2,
        longitude=(bounds[0] + bounds[2]) / 2,
        zoom=12,
        pitch=0,
    )

    # 7. Renderizar el mapa con st.pydeck_chart
    st.pydeck_chart(pdk.Deck(
        map_style="carto-positron",
        layers=[geojson_layer],
        initial_view_state=view_state,
    ))

    # 8. Confirmación manual (el usuario copia el valor)
    st.markdown("""
        ### 🖱️ Haz clic sobre la manzana y copia el código
        - Pasa el ratón sobre la manzana para ver su ID.
        - **Copia el ID** y pégalo en el campo de texto de abajo.
    """)
    manzana_input = st.text_input("✅ Pega aquí el código de la manzana seleccionada para confirmar:")

    if st.button("✅ Confirmar Manzana Seleccionada"):
        if manzana_input:
            st.session_state.manzana_sel = manzana_input
            st.session_state.manzanas_localidad_sel = manzanas_localidad_sel
            st.session_state.step = 4
            st.rerun()
        else:
            st.warning("Debes pegar el código de la manzana seleccionada.")

    col1, col2 = st.columns(2)
    with col1:
        if st.button("🔙 Volver a Selección de Localidad"):
            st.session_state.step = 2
            st.rerun()
    with col2:
        if st.button("🔄 Volver al Inicio"):
            st.session_state.step = 1
            st.rerun()

    # Funciones auxiliares (van fuera del bloque elif)
def hexToRgb(hex_color):
    hex_color = hex_color.lstrip('#')
    return tuple(int(hex_color[i:i+2], 16) for i in (0, 2, 4))