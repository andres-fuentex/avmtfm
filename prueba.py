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
# --- Bloque 3: Selección de Manzana con Copia Manual ---
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
    manzanas_sel = manzanas[manzanas["num_localidad"] == cod_localidad].copy()

    if manzanas_sel.empty:
        st.warning("⚠️ No se encontraron manzanas para la localidad seleccionada.")
        st.stop()

    # 2. Mapa de Colores para Usos de Suelo
    areas_sel = areas[areas["num_localidad"] == cod_localidad].copy()

    if not areas_sel.empty:
        manzanas_sel = manzanas_sel.merge(
            areas_sel[["id_area", "uso_pot_simplificado"]],
            on="id_area",
            how="left"
        )
    else:
        manzanas_sel["uso_pot_simplificado"] = "Sin clasificación"

    manzanas_sel["uso_pot_simplificado"] = manzanas_sel["uso_pot_simplificado"].fillna("Sin clasificación")

    cats = manzanas_sel["uso_pot_simplificado"].unique().tolist()
    palette = px.colors.qualitative.Plotly
    color_map = {cat: palette[i % len(palette)] for i, cat in enumerate(cats)}
    if "Sin clasificación" not in color_map:
        color_map["Sin clasificación"] = "#2b2b2b"

    manzanas_sel["color"] = manzanas_sel["uso_pot_simplificado"].apply(lambda x: color_map.get(x, "#2b2b2b"))

    # 3. Construir el GeoJSON con color y preparar mapa
    manzanas_features = []
    for _, row in manzanas_sel.iterrows():
        manzanas_features.append({
            "type": "Feature",
            "geometry": json.loads(gpd.GeoSeries([row["geometry"]]).to_json())["features"][0]["geometry"],
            "properties": {
                "id_manzana_unif": row["id_manzana_unif"],
                "color": row["color"]
            }
        })

    manzanas_geojson = {
        "type": "FeatureCollection",
        "features": manzanas_features
    }

    geojson_text = json.dumps(manzanas_geojson)

    # 4. Calcular el centro del mapa
    bounds = manzanas_sel.total_bounds
    center_lat = (bounds[1] + bounds[3]) / 2
    center_lon = (bounds[0] + bounds[2]) / 2

    # 5. Inyectar HTML y JavaScript
    components.html(f"""
        <div id="map" style="height: 500px;"></div>
        <p><b>🔎 Código de la manzana seleccionada (¡copia este valor!):</b></p>
        <input type="text" id="selected_id_input" value="" style="width: 100%; padding: 5px;" readonly>

        <script src="https://unpkg.com/leaflet@1.7.1/dist/leaflet.js"></script>
        <link rel="stylesheet" href="https://unpkg.com/leaflet@1.7.1/dist/leaflet.css"/>

        <script>
            const map = L.map('map').setView([{center_lat}], [{center_lon}], 13);
            L.tileLayer('https://tile.openstreetmap.org/{{z}}/{{x}}/{{y}}.png', {{
                maxZoom: 18,
                attribution: '© OpenStreetMap contributors'
            }}).addTo(map);

            const manzanas = {geojson_text};

            function style(feature) {{
                return {{
                    fillColor: feature.properties.color,
                    weight: 1,
                    opacity: 1,
                    color: 'black',
                    fillOpacity: 0.5
                }};
            }}

            function highlightStyle() {{
                return {{
                    fillColor: 'orange',
                    weight: 2,
                    color: 'red',
                    fillOpacity: 0.7
                }};
            }}

            let selectedLayer = null;

            function onEachFeature(feature, layer) {{
                layer.on({{
                    click: function(e) {{
                        if (selectedLayer) {{
                            geojson.resetStyle(selectedLayer);
                        }}
                        selectedLayer = layer;
                        layer.setStyle(highlightStyle());
                        document.getElementById("selected_id_input").value = feature.properties.id_manzana_unif;
                    }}
                }});
                layer.bindTooltip("Manzana: " + feature.properties.id_manzana_unif);
                
            }}

            const geojson = L.geoJSON(manzanas, {{
                style: style,
                onEachFeature: onEachFeature
            }}).addTo(map);

            map.fitBounds(geojson.getBounds());
        </script>
    """, height=620)

    # Confirmación manual (el usuario copia el valor)
    manzana_input = st.text_input("✅ Pega aquí el código de la manzana seleccionada para confirmar:")

    if st.button("✅ Confirmar Manzana Seleccionada"):
        if manzana_input:
            st.session_state.manzana_sel = manzana_input
            st.session_state.manzanas_localidad_sel = manzanas_sel
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
### OJO CON ESTE CAMBIO
    st.session_state.manzanas_localidad_sel = manzanas_sel
    st.session_state.color_map = color_map