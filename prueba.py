import streamlit as st
import pandas as pd
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

# --- Configuración de la Página ---
st.set_page_config(page_title="AVM Bogotá APP", page_icon="🏠", layout="centered")
st.title("🏠 AVM Bogotá - Análisis de Manzanas")

# --- Función cacheada para la carga de datos (con manejo de errores) ---
@st.cache_data
def cargar_datasets():
    """
    Descarga y procesa los datasets geoespaciales desde GitHub con barras de progreso y manejo de errores.
    """
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
            dataframes[nombre] = gpd.read_file(url)
        except Exception as e:
            st.error(f"No se pudo cargar el dataset '{nombre}' desde la URL. Error: {e}")
            return None # Detiene la ejecución si un archivo falla

    progress_bar.empty()
    return dataframes

# --- Control de flujo ---
if "step" not in st.session_state:
    st.session_state.step = 1

# --- Bloque 1: Bienvenida y Carga de datos ---
if st.session_state.step == 1:
    st.markdown("## Bienvenido al Análisis de Valorización de Manzanas de Bogotá")
    st.markdown("Esta aplicación utiliza datos abiertos para el análisis de inversión inmobiliaria. Haga clic en 'Iniciar Análisis' para comenzar.")

    if st.button("Iniciar Análisis"):
        with st.spinner('Cargando todos los datasets. Esto puede tardar un momento...'):
            dataframes = cargar_datasets()

        if dataframes:
            st.success('✅ Todos los datos han sido cargados correctamente.')
            for nombre, df in dataframes.items():
                st.session_state[nombre] = df
            st.session_state.step = 2
            st.rerun()
        else:
            st.error("❌ No se pudieron cargar los datos. Por favor, recarga la página.")

# --- Bloque 2: Selección de Localidad ---
elif st.session_state.step == 2:
    st.header("🌆 Paso 1: Selección de Localidad")
    st.markdown("Haz clic en la localidad del mapa que te interesa analizar.")

    localidades_gdf = st.session_state.localidades
    bounds = localidades_gdf.total_bounds
    center = [(bounds[1] + bounds[3]) / 2, (bounds[0] + bounds[2]) / 2]

    mapa = folium.Map(location=center, zoom_start=10, tiles="CartoDB positron")

    folium.GeoJson(
        localidades_gdf,
        style_function=lambda feature: {"fillColor": "#2596be", "color": "black", "weight": 1, "fillOpacity": 0.4},
        highlight_function=lambda feature: {"weight": 3, "color": "#e30613", "fillOpacity": 0.7},
        tooltip=folium.GeoJsonTooltip(fields=["nombre_localidad"], aliases=["Localidad:"], labels=True, sticky=True)
    ).add_to(mapa)

    map_data = st_folium(mapa, width=700, height=500, returned_objects=["last_object_clicked"])

    if map_data and map_data.get("last_object_clicked"):
        props = map_data["last_object_clicked"].get("properties", {})
        st.session_state.localidad_clic = props.get("nombre_localidad")

    if "localidad_clic" in st.session_state and st.session_state.localidad_clic:
        st.text_input("✅ Localidad seleccionada", value=st.session_state.localidad_clic, disabled=True)
        if st.button("Confirmar y Continuar"):
            st.session_state.localidad_sel = st.session_state.localidad_clic
            st.session_state.step = 3
            st.rerun()
    else:
        st.info("Selecciona una localidad en el mapa y confírmala para continuar.")

    if st.button("🔄 Volver al Inicio"):
        st.session_state.step = 1
        st.rerun()

# --- Bloque 3: Selección de Manzana con Folium (REEMPLAZO COMPLETO) ---
elif st.session_state.step == 3:
    st.header(f"🏘️ Paso 2: Selección de Manzana en {st.session_state.localidad_sel}")

    localidades = st.session_state.localidades
    areas = st.session_state.areas
    manzanas = st.session_state.manzanas
    localidad_sel = st.session_state.localidad_sel

    # Filtrar manzanas por localidad
    cod_localidad_series = localidades[localidades["nombre_localidad"] == localidad_sel]["num_localidad"]
    if cod_localidad_series.empty:
        st.error(f"No se encontró el código para la localidad '{localidad_sel}'.")
        st.stop()
    cod_localidad = cod_localidad_series.values[0]
    manzanas_localidad_sel = manzanas[manzanas["num_localidad"] == cod_localidad].copy()

    if manzanas_localidad_sel.empty:
        st.warning("⚠️ No se encontraron manzanas para la localidad seleccionada.")
        st.stop()

    # Combinar información de áreas (usos de suelo)
    areas_sel = areas[areas["num_localidad"] == cod_localidad]
    if not areas_sel.empty:
        manzanas_localidad_sel = manzanas_localidad_sel.merge(
            areas_sel[["id_area", "uso_pot_simplificado"]], on="id_area", how="left"
        )
    manzanas_localidad_sel["uso_pot_simplificado"] = manzanas_localidad_sel["uso_pot_simplificado"].fillna("Sin clasificación")

    # Crear un mapa de colores para los usos de suelo
    usos_unicos = manzanas_localidad_sel["uso_pot_simplificado"].unique()
    palette = px.colors.qualitative.Plotly
    color_map = {uso: palette[i % len(palette)] for i, uso in enumerate(usos_unicos)}
    color_map["Sin clasificación"] = "#808080"  # Gris para "Sin clasificación"

    st.markdown("### 🖱️ Haz clic sobre una manzana para seleccionarla")
    bounds = manzanas_localidad_sel.total_bounds
    center = [(bounds[1] + bounds[3]) / 2, (bounds[0] + bounds[2]) / 2]
    
    mapa_manzanas = folium.Map(location=center, tiles="CartoDB positron", zoom_start=14)

    # Añadir manzanas al mapa con colores y tooltips
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

    # Capturar la interacción del usuario
    map_data = st_folium(
        mapa_manzanas,
        width=700,
        height=500,
        returned_objects=["last_object_clicked"],
    )

    # Mostrar información de la manzana seleccionada y botón de confirmación
    if map_data and map_data.get("last_object_clicked"):
        props = map_data["last_object_clicked"].get("properties", {})
        st.session_state.manzana_clic = props.get("id_manzana_unif")

    if "manzana_clic" in st.session_state:
        st.text_input("✅ Manzana seleccionada (ID):", value=st.session_state.manzana_clic, disabled=True)
        if st.button("✅ Confirmar Manzana y Continuar"):
            st.session_state.manzana_sel = st.session_state.manzana_clic
            st.session_state.manzanas_localidad_sel = manzanas_localidad_sel
            st.session_state.color_map = color_map  # Guardar el mapa de colores
            st.session_state.step = 4
            st.rerun()
    else:
        st.info("Haz clic en una manzana del mapa para empezar.")

    # Botones de navegación
    col1, col2 = st.columns(2)
    with col1:
        if st.button("🔙 Volver a Selección de Localidad"):
            st.session_state.step = 2
            st.rerun()
    with col2:
        if st.button("🔄 Volver al Inicio"):
            st.session_state.step = 1
            st.rerun()

            # --- Bloque 4: Análisis Espacial de la Manzana Seleccionada ---
elif st.session_state.step == 4:
    st.subheader("🗺️ Análisis Contextual de la Manzana Seleccionada")

    manzanas = st.session_state.manzanas
    transporte = st.session_state.transporte
    colegios = st.session_state.colegios
    id_manzana = st.session_state.manzana_sel
    
    manzana_sel_gdf = manzanas[manzanas["id_manzana_unif"] == id_manzana]

    if manzana_sel_gdf.empty:
        st.warning("⚠️ No se encontraron datos para la manzana seleccionada.")
        if st.button("🔙 Volver a Selección de Manzana"):
            st.session_state.step = 3
            st.rerun()
    else:
        manzana_proj = manzana_sel_gdf.to_crs(epsg=3116)
        centroide = manzana_proj.geometry.centroid.to_crs(epsg=4326).iloc[0]
        lon0, lat0 = centroide.x, centroide.y

        # --- Contexto de Transporte ---
        st.markdown("### 🚇 Contexto de Transporte (Buffer 800m)")
        
        buffer_transporte_proj = manzana_proj.buffer(800)
        buffer_transporte_wgs = buffer_transporte_proj.to_crs(epsg=4326).iloc[0]
        
        fig_transporte = go.Figure(go.Scattermapbox(
            lat=list(buffer_transporte_wgs.exterior.xy[1]),
            lon=list(buffer_transporte_wgs.exterior.xy[0]),
            mode='lines', fill='toself', name='Buffer 800m',
            fillcolor='rgba(255,0,0,0.1)', line=dict(color='red')
        ))

        fig_transporte.add_trace(go.Scattermapbox(
            lat=list(manzana_sel_gdf.geometry.iloc[0].exterior.xy[1]),
            lon=list(manzana_sel_gdf.geometry.iloc[0].exterior.xy[0]),
            mode='lines', fill='toself', name='Manzana',
            fillcolor='rgba(0,128,0,0.3)', line=dict(color='darkgreen')
        ))

        id_combi = manzana_sel_gdf["id_combi_acceso"].iloc[0]
        if pd.notna(id_combi):
            multipunto = transporte.loc[transporte["id_combi_acceso"] == id_combi, "geometry"]
            if not multipunto.empty:
                puntos = list(multipunto.iloc[0].geoms)
                fig_transporte.add_trace(go.Scattermapbox(
                    lat=[p.y for p in puntos], lon=[p.x for p in puntos],
                    mode='markers', name='Estaciones', marker=dict(color='red', size=10)
                ))

        fig_transporte.update_layout(
            mapbox_style="carto-positron", mapbox_center={"lat": lat0, "lon": lon0}, mapbox_zoom=14,
            margin={"r": 0, "t": 40, "l": 0, "b": 0}, title="Contexto de Transporte"
        )
        st.plotly_chart(fig_transporte, use_container_width=True)
        st.session_state.buffer_transporte = BytesIO(pio.to_image(fig_transporte, format='png'))

        # --- Contexto Educativo ---
        st.markdown("### 🏫 Contexto Educativo (Buffer 1000m)")
        buffer_colegios_proj = manzana_proj.buffer(1000)
        buffer_colegios_wgs = buffer_colegios_proj.to_crs(epsg=4326).iloc[0]

        fig_colegios = go.Figure(go.Scattermapbox(
            lat=list(buffer_colegios_wgs.exterior.xy[1]),
            lon=list(buffer_colegios_wgs.exterior.xy[0]),
            mode='lines', fill='toself', name='Buffer 1000m',
            fillcolor='rgba(0,0,255,0.1)', line=dict(color='blue')
        ))

        fig_colegios.add_trace(go.Scattermapbox(
            lat=list(manzana_sel_gdf.geometry.iloc[0].exterior.xy[1]),
            lon=list(manzana_sel_gdf.geometry.iloc[0].exterior.xy[0]),
            mode='lines', fill='toself', name='Manzana',
            fillcolor='rgba(0,128,0,0.3)', line=dict(color='darkgreen')
        ))

        id_colegios = manzana_sel_gdf["id_com_colegios"].iloc[0]
        if pd.notna(id_colegios):
            multipunto_colegios = colegios.loc[colegios["id_com_colegios"] == id_colegios, "geometry"]
            if not multipunto_colegios.empty:
                puntos_colegios = list(multipunto_colegios.iloc[0].geoms)
                fig_colegios.add_trace(go.Scattermapbox(
                    lat=[p.y for p in puntos_colegios], lon=[p.x for p in puntos_colegios],
                    mode='markers', name='Colegios', marker=dict(color='blue', size=10)
                ))

        fig_colegios.update_layout(
            mapbox_style="carto-positron", mapbox_center={"lat": lat0, "lon": lon0}, mapbox_zoom=14,
            margin={"r": 0, "t": 40, "l": 0, "b": 0}, title="Contexto Educativo"
        )
        st.plotly_chart(fig_colegios, use_container_width=True)
        st.session_state.buffer_colegios = BytesIO(pio.to_image(fig_colegios, format='png'))

    col1, col2, col3 = st.columns(3)
    with col1:
        if st.button("🔙 Volver a Selección de Manzana"):
            st.session_state.step = 3
            st.rerun()
    with col2:
        if st.button("🔄 Volver al Inicio"):
            st.session_state.step = 1
            st.rerun()
    with col3:
        if st.button("➡️ Continuar al Análisis Comparativo", disabled=manzana_sel_gdf.empty):
            st.session_state.step = 5
            st.rerun()

            # --- Bloque 5: Análisis Comparativo y Proyección del Valor m² ---
elif st.session_state.step == 5:
    st.subheader("📊 Análisis Comparativo y Proyección del Valor m²")

    manzanas_localidad_sel = st.session_state.manzanas_localidad_sel
    manzana_id = st.session_state.manzana_sel
    manzana_sel = manzanas_localidad_sel[manzanas_localidad_sel["id_manzana_unif"] == manzana_id]

    if manzana_sel.empty:
        st.error("Error: No se encontró la manzana seleccionada. Por favor, vuelva atrás.")
    else:
        st.markdown("### 📈 Comparativo de valor m²")
        valor_manzana = manzana_sel["valor_m2"].iloc[0]
        id_area_manzana = manzana_sel["id_area"].iloc[0]
        manzanas_area = manzanas_localidad_sel[manzanas_localidad_sel["id_area"] == id_area_manzana]
        promedio_area = manzanas_area["valor_m2"].mean() if not manzanas_area.empty else 0
        buffer_300 = manzana_sel.to_crs(epsg=3116).buffer(300).to_crs(epsg=4326).iloc[0]
        manzanas_buffer = manzanas_localidad_sel[manzanas_localidad_sel.geometry.intersects(buffer_300)]
        promedio_buffer = manzanas_buffer["valor_m2"].mean() if not manzanas_buffer.empty else 0
        
        st.session_state.promedio_area = promedio_area
        st.session_state.promedio_buffer = promedio_buffer

        fig_bar = go.Figure(data=[
            go.Bar(name='Manzana Seleccionada', x=['Comparativo'], y=[valor_manzana], text=f"${valor_manzana:,.0f}"),
            go.Bar(name='Promedio Área POT', x=['Comparativo'], y=[promedio_area], text=f"${promedio_area:,.0f}"),
            go.Bar(name='Promedio Vecindario (300m)', x=['Comparativo'], y=[promedio_buffer], text=f"${promedio_buffer:,.0f}")
        ])
        fig_bar.update_traces(textposition='auto')
        fig_bar.update_layout(barmode='group', title_text='Comparativo de Valor del Metro Cuadrado', yaxis_title="Valor (COP)")
        st.plotly_chart(fig_bar, use_container_width=True)
        st.session_state.buffer_valorm2 = BytesIO(pio.to_image(fig_bar, format='png'))

        st.markdown("### 🥧 Distribución de usos POT en 500m")
        buffer_500 = manzana_sel.to_crs(epsg=3116).buffer(500).to_crs(epsg=4326).iloc[0]
        manzanas_buffer_uso = manzanas_localidad_sel[manzanas_localidad_sel.geometry.intersects(buffer_500)]
        conteo_uso = manzanas_buffer_uso["uso_pot_simplificado"].value_counts()
        
        st.session_state.uso_pot_mayoritario = conteo_uso.index[0] if not conteo_uso.empty else "Sin clasificación"

        if not conteo_uso.empty:
            fig_pie = px.pie(values=conteo_uso.values, names=conteo_uso.index, title="Distribución de Usos POT (Buffer 500m)")
            st.plotly_chart(fig_pie, use_container_width=True)
            st.session_state.buffer_dist_pot = BytesIO(pio.to_image(fig_pie, format='png'))
        else:
            st.warning("⚠️ No hay datos de uso POT en el área.")
            st.session_state.buffer_dist_pot = BytesIO()

        st.markdown("### 📈 Proyección del valor m²")
        proyeccion_cols = ["valor_m2", "valor_2025_s1", "valor_2025_s2", "valor_2026_s1", "valor_2026_s2"]
        serie_proyeccion = manzana_sel[proyeccion_cols].iloc[0]
        if not serie_proyeccion.isnull().any():
            fechas = ["2024-S2", "2025-S1", "2025-S2", "2026-S1", "2026-S2"]
            fig_line = go.Figure(go.Scatter(x=fechas, y=serie_proyeccion.values, mode='lines+markers+text', text=[f"${v:,.0f}" for v in serie_proyeccion.values], textposition="top center"))
            fig_line.update_layout(title=f"Proyección de Valor m² - Manzana {manzana_id}", yaxis_title="Valor (COP)")
            st.plotly_chart(fig_line, use_container_width=True)
            st.session_state.buffer_proyeccion = BytesIO(pio.to_image(fig_line, format='png'))
        else:
            st.warning("⚠️ No hay datos de proyección para esta manzana.")
            st.session_state.buffer_proyeccion = BytesIO()

    col1, col2 = st.columns(2)
    with col1:
        if st.button("🔙 Volver al Análisis de Transporte y Educación"):
            st.session_state.step = 4
            st.rerun()
    with col2:
        if st.button("➡️ Continuar al Análisis de Seguridad", disabled=manzana_sel.empty):
            st.session_state.step = 6
            st.rerun()

            # --- Bloque 6: Contexto de Seguridad por Localidad ---
elif st.session_state.step == 6:
    st.subheader("🔎 Contexto de Seguridad por Localidad")
    
    localidades = st.session_state.localidades
    manzana_sel = st.session_state.manzanas_localidad_sel[st.session_state.manzanas_localidad_sel["id_manzana_unif"] == st.session_state.manzana_sel]

    if manzana_sel.empty:
        st.warning("⚠️ No se encontró información de la manzana seleccionada.")
        if st.button("🔙 Volver al Bloque Anterior"):
            st.session_state.step = 5
            st.rerun()
    else:
        cod_loc_actual = manzana_sel["num_localidad"].iloc[0]
        
        # --- Comprobar si la localidad existe y obtener el nombre ---
        nombre_loc_series = localidades[localidades["num_localidad"] == cod_loc_actual]["nombre_localidad"]
        if nombre_loc_series.empty:
            st.error(f"No se encontró la localidad con código {cod_loc_actual}")
            st.stop()
        nombre_loc_actual = nombre_loc_series.iloc[0]
        st.session_state.nombre_localidad = nombre_loc_actual

        df_seguridad = localidades[["nombre_localidad", "cantidad_delitos", "nivel_riesgo_delictivo"]].copy().sort_values("cantidad_delitos", ascending=False)
        colores = ['#e30613' if x == nombre_loc_actual else '#d3d3d3' for x in df_seguridad["nombre_localidad"]]
        fig_seg = go.Figure(go.Bar(x=df_seguridad['cantidad_delitos'], y=df_seguridad['nombre_localidad'], orientation='h', marker_color=colores))
        fig_seg.update_layout(title="Cantidad de Delitos Reportados por Localidad", xaxis_title="Cantidad de Delitos", yaxis={'categoryorder':'total ascending'}, height=600)
        st.plotly_chart(fig_seg, use_container_width=True)
        st.session_state.buffer_seguridad = BytesIO(pio.to_image(fig_seg, format='png'))

    col1, col2, col3 = st.columns(3)
    with col1:
        if st.button("🔙 Volver al Análisis Comparativo"):
            st.session_state.step = 5
            st.rerun()
    with col2:
        if st.button("➡️ Finalizar y Generar Informe", disabled=manzana_sel.empty):
            st.session_state.step = 7
            st.rerun()
    with col3:
        if st.button("🔄 Reiniciar App"):
            for key in list(st.session_state.keys()):
                del st.session_state[key]
            st.rerun()

            # --- Bloque 7: Generación del Informe Ejecutivo (CON TEXTOS REINTEGRADOS) ---
elif st.session_state.step == 7:
    st.subheader("📑 Generación del Informe Ejecutivo")

    # Verificar que todos los buffers de imagen necesarios existan
    required_buffers = ['buffer_colegios', 'buffer_transporte', 'buffer_valorm2', 'buffer_seguridad', 'buffer_dist_pot', 'buffer_proyeccion']
    if not all(key in st.session_state for key in required_buffers):
        st.error("Faltan datos para generar el informe. Por favor, reinicie el proceso.")
        if st.button("🔄 Reiniciar"):
            st.session_state.step = 1
            st.rerun()
    else:
        with st.spinner('📝 Generando informe HTML...'):
            # --- 1. Recopilar todos los datos y variables para los textos ---
            manzana_id = st.session_state.manzana_sel
            manzana_sel = st.session_state.manzanas_localidad_sel[st.session_state.manzanas_localidad_sel["id_manzana_unif"] == manzana_id]

            if manzana_sel.empty:
                st.error("❌ No se encontró la información de la manzana seleccionada. Por favor vuelve y selecciona.")
                if st.button("🔙 Volver al Análisis Comparativo"):
                    st.session_state.step = 5
                    st.rerun()
            else:
                estrato = int(manzana_sel["estrato"].values[0])
                nombre_localidad = st.session_state.nombre_localidad
                colegios = int(manzana_sel["colegio_cerca"].values[0])
                estaciones = int(manzana_sel["estaciones_cerca"].values[0])

                id_area_manzana = manzana_sel["id_area"].values[0]
                area_info = st.session_state.areas[st.session_state.areas["id_area"] == id_area_manzana]
                area_pot = area_info["area_pot"].values[0] if not area_info.empty else "N/A"
                uso_pot = area_info["uso_pot_simplificado"].values[0] if not area_info.empty else "N/A"
                uso_pot_mayoritario = st.session_state.uso_pot_mayoritario
                valor_area = f"${st.session_state.promedio_area:,.0f}"

                valor_m2 = manzana_sel["valor_m2"].values[0]
                rentabilidad = manzana_sel["rentabilidad"].values[0]
                promedio_buffer = float(st.session_state.promedio_buffer)

                cod_loc = manzana_sel["num_localidad"].values[0]
                info_seguridad = st.session_state.localidades[st.session_state.localidades["num_localidad"] == cod_loc]
                if not info_seguridad.empty:
                    nivel_riesgo = info_seguridad["nivel_riesgo_delictivo"].values[0]
                    delitos = int(info_seguridad["cantidad_delitos"].values[0])
                else:
                    nivel_riesgo = "N/A"
                    delitos = 0

                v_2025_1 = manzana_sel["valor_2025_s1"].values[0]
                v_2025_2 = manzana_sel["valor_2025_s2"].values[0]
                v_2026_1 = manzana_sel["valor_2026_s1"].values[0]
                v_2026_2 = manzana_sel["valor_2026_s2"].values[0]

                # --- 2. Construir los bloques de texto ---
                texto0 = (
                    f"El presente informe ha sido generado automáticamente como parte del trabajo final del Máster en Visual Analytics y Big Data "
                    f"de la Universidad Internacional de La Rioja. Este documento es el resultado del proyecto desarrollado por "
                    f"<strong>Sergio Andrés Fuentes Gómez</strong> y <strong>Miguel Alejandro González</strong>, bajo la dirección de "
                    f"<strong>Mariana Ríos Ortegón</strong>. Forma parte de un piloto experimental orientado a la aplicación práctica de técnicas "
                    f"de análisis visual y ciencia de datos en contextos urbanos reales."
                )

                texto1 = (
                    f"De acuerdo con su selección, la manzana identificada con el código <strong>{id_manzana}</strong>, "
                    f"ubicada en la localidad <strong>{nombre_localidad}</strong>, correspondiente al <strong>estrato {estrato}</strong>, "
                    f"presenta condiciones clave para evaluar su potencial de valorización en el contexto urbano de Bogotá."
                )

                texto2 = (
                    f"Cuenta con <strong>{colegios} colegios</strong> ubicados a menos de <strong>1.000 metros</strong> y "
                    f"<strong>{estaciones} estaciones de TransMilenio</strong> a menos de <strong>500 metros</strong>. "
                    f"Estos factores evidencian su buena conectividad y acceso a servicios."
                )

                texto3 = (
                    f"Desde el punto de vista normativo, la manzana se encuentra asignada al área denominada "
                    f"<strong>{area_pot}</strong> dentro del marco del <strong>Plan de Ordenamiento Territorial (POT)</strong>. "
                    f"Su uso principal es <strong>{uso_pot}</strong>. En un radio de 500 metros, el uso predominante es "
                    f"<strong>{uso_pot_mayoritario}</strong>. El valor promedio del metro cuadrado en el área POT es de "
                    f"<strong>{valor_area}</strong>."
                )

                texto4 = (
                    f"El valor actual del metro cuadrado es de <strong>${valor_m2:,.0f}</strong>. "
                    f"El promedio en un radio de 300 metros es de <strong>${promedio_buffer:,.0f}</strong>. "
                    f"El valor promedio en el área POT es <strong>{valor_area}</strong>. La rentabilidad estimada es de "
                    f"<strong>{rentabilidad}</strong>."
                )

                texto5 = (
                    f"La localidad <strong>{nombre_localidad}</strong> presenta un nivel de riesgo <strong>{nivel_riesgo}</strong> "
                    f"con un total de <strong>{delitos} delitos</strong> reportados."
                )

                texto6 = (
                    f"Según las proyecciones, el valor del metro cuadrado podría ser:<br>"
                    f"- 2025-S1: <strong>${v_2025_1:,.0f}</strong><br>"
                    f"- 2025-S2: <strong>${v_2025_2:,.0f}</strong><br>"
                    f"- 2026-S1: <strong>${v_2026_1:,.0f}</strong><br>"
                    f"- 2026-S2: <strong>${v_2026_2:,.0f}</strong><br>"
                )

                # --- 3. Codificar imágenes y generar HTML ---
                def buffer_a_base64(buffer):
                    if buffer is None or buffer.getbuffer().nbytes == 0:
                        return ""
                    buffer.seek(0)
                    return base64.b64encode(buffer.read()).decode('utf-8')

                img_colegios_base64 = buffer_a_base64(st.session_state.buffer_colegios)
                img_transporte_base64 = buffer_a_base64(st.session_state.buffer_transporte)
                img_valorm2_base64 = buffer_a_base64(st.session_state.buffer_valorm2)
                img_seguridad_base64 = buffer_a_base64(st.session_state.buffer_seguridad)
                img_distribucion_base64 = buffer_a_base64(st.session_state.get('buffer_dist_pot'))
                img_proyeccion_base64 = buffer_a_base64(st.session_state.get('buffer_proyeccion'))

                html_ficha = pd.DataFrame({
                    "ID Manzana": [manzana_id], "Localidad": [nombre_localidad],
                    "Estrato": [estrato], "Valor m²": [f"${valor_m2:,.0f}"], "Rentabilidad": [rentabilidad]
                }).to_html(index=False, classes='dataframe')

                def create_card(title, img_base64):
                    if img_base64: return f'<div class="card"><h2>{title}</h2><img src="data:image/png;base64,{img_base64}"></div>'
                    return ""

                html_content = f"""
                <!DOCTYPE html><html lang="es"><head><meta charset="UTF-8"><title>Informe AVM</title>
                <style>
                    body {{ font-family: Arial, sans-serif; margin: 20px; background-color: #f9f9f9; }}
                    h1, h2 {{ color: #003366; }} h1 {{ text-align: center; }}
                    .dataframe {{ border-collapse: collapse; width: 90%; margin: 20px auto; border: 1px solid #ccc; }}
                    .dataframe th, .dataframe td {{ padding: 12px; text-align: left; border-bottom: 1px solid #ddd; }}
                    .container {{ display: grid; grid-template-columns: repeat(auto-fit, minmax(450px, 1fr)); gap: 25px; margin-top: 20px; }}
                    .card {{ border: 1px solid #eee; padding: 20px; box-shadow: 0 4px 8px rgba(0,0,0,0.1); border-radius: 8px; text-align: center; }}
                    .card img {{ max-width: 100%; height: auto; margin-top: 15px; }}
                    .text-block {{ text-align: justify; padding: 15px; background-color: #f8f9fa; border-left: 5px solid #0056b3; margin: 20px 0; }}
                </style></head><body>
                    <h1>Informe de Análisis de Inversión Inmobiliaria</h1>
                    <div class="text-block" style="font-size: 0.9em; text-align: center;">{texto0}</div>
                    <h2>Ficha Resumen de la Manzana</h2>{html_ficha}
                    <div class="text-block">{texto1}</div>
                    <div class="text-block">{texto2}</div>
                    <div class="container">{create_card("Contexto de Transporte", img_transporte_base64)}{create_card("Contexto Educativo", img_colegios_base64)}</div>
                    <div class="text-block">{texto3}</div>
                    <div class="container">{create_card("Distribución Usos POT (500m)", img_distribucion_base64)}</div>
                    <div class="text-block">{texto4}</div>
                    <div class="container">{create_card("Comparativo de Valor m²", img_valorm2_base64)}</div>
                    <div class="text-block">{texto5}</div>
                    <div class="container">{create_card("Contexto de Seguridad Localidad", img_seguridad_base64)}</div>
                    <div class="text-block">{texto6}</div>
                    <div class="container">{create_card("Proyección de Valor", img_proyeccion_base64)}</div>
                </body></html>"""
            st.session_state.informe_html = html_content

        st.success("✅ Informe generado correctamente.")

        st.download_button(
            label="📥 Descargar Informe (HTML)",
            data=st.session_state.informe_html,
            file_name=f"Informe_AVM_Manzana_{st.session_state.manzana_sel}.html",
            mime="text/html"
        )

    col1, col2 = st.columns(2)
    with col1:
        if st.button("🔙 Volver al Análisis de Seguridad"):
            st.session_state.step = 6
            st.rerun()
    with col2:
        if st.button("🔄 Reiniciar Aplicación"):
            for key in list(st.session_state.keys()):
                del st.session_state[key]
            st.session_state.step = 1
            st.rerun()