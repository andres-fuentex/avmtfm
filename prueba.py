import streamlit as st
import geopandas as gpd
import requests  # Importar requests
import folium
from streamlit_folium import st_folium
from shapely.geometry import Point


st.set_page_config(page_title="AVM Bogotá APP", page_icon="🏠", layout="centered")
st.title("🏠 AVM Bogotá - Análisis de Manzanas")

# --- Función cacheada para la carga de datos (con manejo de errores) ---
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
        try:
            # Usar requests para obtener el contenido y manejar errores de red
            response = requests.get(url, timeout=10)  # Timeout de 10 segundos
            response.raise_for_status()  # Lanza una excepción para códigos de error HTTP
            dataframes[nombre] = gpd.read_file(response.text)
        except requests.exceptions.RequestException as e:
            st.error(f"Error al cargar {nombre} desde la URL: {e}")
            return None  # Detener la carga si hay un error
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
    else:
        st.error("❌ Error al cargar los datasets. Por favor, revise las URLs o la conexión a Internet.")

        # --- Bloque 2: Selección de Localidad ---
elif st.session_state.step == 2:
    st.header("🌆 Selección de Localidad")
    st.markdown("Haz clic en la localidad que te interesa:")

    localidades = st.session_state.localidades  # Obtener el GeoDataFrame
    if localidades is None:
        st.error("❌ No se cargaron los datos de las localidades. Por favor, reinicia la aplicación.")
        st.stop()

    bounds = localidades.total_bounds
    center = [(bounds[1] + bounds[3]) / 2, (bounds[0] + bounds[2]) / 2]

    mapa = folium.Map(location=center, zoom_start=10, tiles="CartoDB positron")

    folium.GeoJson(
        localidades,
        style_function=lambda feature: {
            "fillColor": "#3388ff",
            "color": "black",
            "weight": 1,
            "fillOpacity": 0.4,  # Aumentar la opacidad
        },
        highlight_function=lambda feature: {
            "weight": 3,
            "color": "red",
        },
        tooltip=folium.GeoJsonTooltip(fields=["nombre_localidad"], aliases=["Localidad:"], labels=True, sticky=True) # Tooltip mejorado
    ).add_to(mapa)

    result = st_folium(mapa, width=700, height=500, returned_objects=["last_object_clicked"])

    # Almacenar la localidad clicada en el estado de la sesión
    if result and result.get("last_object_clicked"):
        clicked = result["last_object_clicked"]
        st.session_state.localidad_clic = clicked.get("properties", {}).get("nombre_localidad")

    # Mostrar la localidad seleccionada y el botón de confirmar
    if "localidad_clic" in st.session_state:
        st.text_input("✅ Localidad seleccionada", value=st.session_state.localidad_clic, disabled=True)
        if st.button("✅ Confirmar selección"):
            st.session_state.localidad_sel = st.session_state.localidad_clic
            st.session_state.step = 3
            st.rerun()

    # Botón para volver al inicio
    if st.button("🔄 Volver al Inicio"):
        st.session_state.step = 1
        st.rerun()

    # Mensaje informativo
    if "localidad_sel" not in st.session_state:
        st.info("Selecciona una localidad en el mapa y confírmala para continuar.")

        # --- Bloque 3: Selección de Manzana ---
elif st.session_state.step == 3:
    st.header(f"🏘️ Paso 2: Selección de Manzana en {st.session_state.localidad_sel}")

    localidades = st.session_state.localidades
    areas = st.session_state.areas
    manzanas = st.session_state.manzanas
    localidad_sel = st.session_state.localidad_sel

    # --- 1. Filtrar Manzanas por Localidad ---
    cod_localidad_series = localidades[localidades["nombre_localidad"] == localidad_sel]["num_localidad"]
    if cod_localidad_series.empty:
        st.error(f"No se encontró el código para la localidad '{localidad_sel}'.")
        st.stop()
    cod_localidad = cod_localidad_series.values[0]
    manzanas_localidad_sel = manzanas[manzanas["num_localidad"] == cod_localidad].copy()

    if manzanas_localidad_sel.empty:
        st.warning("⚠️ No se encontraron manzanas para la localidad seleccionada.")
        st.stop()

    # --- 2. Enriquecer con información de áreas (usos de suelo) ---
    areas_sel = areas[areas["num_localidad"] == cod_localidad]
    if not areas_sel.empty:
        manzanas_localidad_sel = manzanas_localidad_sel.merge(
            areas_sel[["id_area", "uso_pot_simplificado"]], on="id_area", how="left"
        )
    manzanas_localidad_sel["uso_pot_simplificado"] = manzanas_localidad_sel["uso_pot_simplificado"].fillna("Sin clasificación")

    # --- 3. Mapa de Colores para Usos de Suelo ---
    usos_unicos = manzanas_localidad_sel["uso_pot_simplificado"].unique()
    palette = px.colors.qualitative.Plotly
    color_map = {uso: palette[i % len(palette)] for i, uso in enumerate(usos_unicos)}
    color_map["Sin clasificación"] = "#808080"  # Gris para "Sin clasificación"
    st.session_state.color_map = color_map

    # --- 4. Crear el Mapa con Folium ---
    st.markdown("### 🖱️ Haz clic sobre una manzana para seleccionarla")
    bounds = manzanas_localidad_sel.total_bounds
    center = [(bounds[1] + bounds[3]) / 2, (bounds[0] + bounds[2]) / 2]
    
    mapa_manzanas = folium.Map(location=center, tiles="CartoDB positron", zoom_start=14)

    folium.GeoJson(
        manzanas_localidad_sel,
        style_function=lambda feature: {
            "fillColor": color_map.get(feature["properties"]["uso_pot_simplificado"], "#808080"),
            "color": "black",
            "weight": 1,
            "fillOpacity": 0.6,
        },
        highlight_function=lambda x: {"weight": 3, "color": "#e30613", "fillOpacity": 0.8},
        tooltip=folium.GeoJsonTooltip(fields=["id_manzana_unif", "uso_pot_simplificado"], aliases=["ID Manzana:", "Uso POT:"])
    ).add_to(mapa_manzanas)
    
    mapa_manzanas.fit_bounds(folium.GeoJson(manzanas_localidad_sel).get_bounds())

    # --- 5. Capturar la Interacción del Usuario ---
    map_data = st_folium(
        mapa_manzanas,
        width=700,
        height=500,
        returned_objects=["last_object_clicked"],
    )

    # --- 6. Mostrar Información y Confirmar la Selección ---
    if map_data and map_data.get("last_object_clicked"):
        props = map_data["last_object_clicked"].get("properties", {})
        st.session_state.manzana_clic = props.get("id_manzana_unif")

    if "manzana_clic" in st.session_state and st.session_state.manzana_clic:
        st.text_input("✅ Manzana seleccionada (ID):", value=st.session_state.manzana_clic, disabled=True)
        if st.button("✅ Confirmar Manzana y Continuar"):
            st.session_state.manzana_sel = st.session_state.manzana_clic
            # Almacenar datos para los siguientes pasos
            st.session_state.manzanas_localidad_sel = manzanas_localidad_sel
            st.session_state.step = 4
            st.rerun()
    else:
        st.info("Haz clic en una manzana del mapa para empezar.")

    # --- 7. Botones de Navegación ---
    col1, col2 = st.columns(2)
    with col1:
        if st.button("🔙 Volver a Selección de Localidad"):
            st.session_state.step = 2
            st.rerun()
    with col2:
        if st.button("🔄 Volver al Inicio"):
            st.session_state.step = 1
            st.rerun()