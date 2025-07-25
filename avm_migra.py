# ==============================================================================
# BLOQUE 0: CONFIGURACIÓN INICIAL E IMPORTACIÓN DE LIBRERÍAS
# ==============================================================================

# --- Librerías estándar de Python ---
from io import BytesIO
import base64

# --- Librerías principales para la aplicación y manipulación de datos ---
import streamlit as st
import pandas as pd
import geopandas as gpd
import requests

# --- Librerías para Visualización Geoespacial ---
import folium
from streamlit_folium import st_folium
from shapely.geometry import Point, MultiPoint
import matplotlib.pyplot as plt
import seaborn as sns
import contextily as cx

# --- Librería para la Carga de Datos Optimizada ---
import topojson as tp

# --- Configuración de Estilo para los Gráficos ---
sns.set_theme(
    style="whitegrid",
    rc={"figure.figsize": (10, 6), "axes.titlesize": 16, "axes.labelsize": 12}
)


# ==============================================================================
# BLOQUE DE CONFIGURACIÓN Y CARGA DE DATOS
# ==============================================================================

st.set_page_config(page_title="AVM Bogotá APP", page_icon="🏠", layout="centered")

st.title("🏠 AVM Bogotá - Análisis de Manzanas")

@st.cache_data
def cargar_datasets():
    """
    Descarga y procesa los datasets geoespaciales desde GitHub.
    Usa TopoJSON para polígonos y GeoJSON para puntos, optimizando la carga.
    """
    datasets = {
        "localidades": "https://github.com/andres-fuentex/tfm-avm-bogota/raw/main/datos_visualizacion/datos_geograficos_topo/dim_localidad.json",
        "areas": "https://github.com/andres-fuentex/tfm-avm-bogota/raw/main/datos_visualizacion/datos_geograficos_topo/dim_area.json",
        "manzanas": "https://github.com/andres-fuentex/tfm-avm-bogota/raw/main/datos_visualizacion/datos_geograficos_topo/tabla_hechos.json",
        "transporte": "https://github.com/andres-fuentex/tfm-avm-bogota/raw/main/datos_visualizacion/datos_geograficos_geo/dim_transporte.geojson",
        "colegios": "https://github.com/andres-fuentex/tfm-avm-bogota/raw/main/datos_visualizacion/datos_geograficos_geo/dim_colegios.geojson",
    }

    dataframes = {}
    total = len(datasets)
    progress_bar = st.progress(0, text="Iniciando carga de datos...")
    
    for idx, (nombre, url) in enumerate(datasets.items(), start=1):
        progress_text = f"Cargando {nombre} ({idx}/{total})…"
        progress_bar.progress(idx / total, text=progress_text)
        
        try:
            resp = requests.get(url, timeout=30)
            resp.raise_for_status()

            if nombre in ("transporte", "colegios"):
                gdf = gpd.read_file(BytesIO(resp.content))
            else:
                topo_data = resp.json()
                layer_name = list(topo_data["objects"].keys())[0]
                topology = tp.Topology(topo_data, object_name=layer_name)
                gdf = topology.to_gdf()

            if gdf.crs is None:
                gdf.set_crs(epsg=4326, inplace=True)

            dataframes[nombre] = gdf

        except requests.exceptions.RequestException as e:
            st.error(f"Error de red al descargar '{nombre}': {e}")
            return None
        except Exception as e:
            st.error(f"Error al procesar el archivo '{nombre}': {e}")
            return None

    progress_bar.empty()
    return dataframes


# ==============================================================================
# CONTROLADOR DE FLUJO DE LA APLICACIÓN
# ==============================================================================

if "step" not in st.session_state:
    st.session_state.step = 1

# --- Bloque 1: Bienvenida y Carga de Datos ---
if st.session_state.step == 1:
    st.markdown("## Bienvenido al Análisis de Valorización de Manzanas de Bogotá")
    st.markdown("Esta aplicación utiliza datos abiertos para el análisis de inversión inmobiliaria. Haga clic en 'Iniciar Análisis' para comenzar.")

    if st.button("Iniciar Análisis"):
        with st.spinner('Cargando datasets optimizados... Esto puede tardar un momento.'):
            dataframes = cargar_datasets()

        if dataframes:
            st.success('✅ Todos los datos han sido cargados correctamente.')
            for nombre, df in dataframes.items():
                st.session_state[nombre] = df
            st.session_state.step = 2
            st.rerun()
        else:
            st.error("❌ No se pudieron cargar los datos. Por favor, recarga la página o contacta al administrador.")

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


# --- Bloque 3: Selección de Manzana ---
elif st.session_state.step == 3:
    st.header(f"🏘️ Paso 2: Selección de Manzana en {st.session_state.localidad_sel}")

    localidades = st.session_state.localidades
    areas = st.session_state.areas
    manzanas = st.session_state.manzanas
    localidad_sel = st.session_state.localidad_sel
    
    localidad_info = localidades[localidades["nombre_localidad"] == localidad_sel]
    if localidad_info.empty:
        st.error(f"No se encontró información para la localidad '{localidad_sel}'. Por favor, vuelva a intentarlo.")
        if st.button("🔙 Volver a Selección de Localidad"):
            st.session_state.step = 2
            st.rerun()
    else:
        cod_localidad = localidad_info["num_localidad"].iloc[0]
        manzanas_localidad_sel = manzanas[manzanas["num_localidad"] == cod_localidad].copy()

        if manzanas_localidad_sel.empty:
            st.warning("⚠️ No se encontraron manzanas para la localidad seleccionada.")
        else:
            if "areas" in st.session_state and not areas.empty:
                areas_sel = areas[areas["num_localidad"] == cod_localidad]
                if not areas_sel.empty:
                    manzanas_localidad_sel = manzanas_localidad_sel.merge(
                        areas_sel[["id_area", "uso_pot_simplificado"]], on="id_area", how="left"
                    )
            manzanas_localidad_sel["uso_pot_simplificado"] = manzanas_localidad_sel["uso_pot_simplificado"].fillna("Sin clasificación")

            usos_unicos = manzanas_localidad_sel["uso_pot_simplificado"].unique()
            palette = sns.color_palette("viridis", n_colors=len(usos_unicos)).as_hex()
            color_map = {uso: color for uso, color in zip(usos_unicos, palette)}
            color_map["Sin clasificación"] = "#808080"

            st.markdown("### 🖱️ Haz clic sobre una manzana para seleccionarla")
            bounds = manzanas_localidad_sel.total_bounds
            center = [(bounds[1] + bounds[3]) / 2, (bounds[0] + bounds[2]) / 2]
            
            mapa_manzanas = folium.Map(location=center, tiles="CartoDB positron", zoom_start=14)

            geo_manzanas = folium.GeoJson(
                manzanas_localidad_sel,
                style_function=lambda feature: {"fillColor": color_map.get(feature["properties"]["uso_pot_simplificado"], "#808080"), "color": "black", "weight": 1, "fillOpacity": 0.6},
                highlight_function=lambda x: {"weight": 3, "color": "#e30613", "fillOpacity": 0.8},
                tooltip=folium.GeoJsonTooltip(fields=["id_manzana_unif", "uso_pot_simplificado"], aliases=["ID Manzana:", "Uso POT:"])
            ).add_to(mapa_manzanas)
            
            mapa_manzanas.fit_bounds(geo_manzanas.get_bounds())

            map_data = st_folium(mapa_manzanas, width=700, height=500, returned_objects=["last_object_clicked"])

            if map_data and map_data.get("last_object_clicked"):
                props = map_data["last_object_clicked"].get("properties", {})
                st.session_state.manzana_clic = props.get("id_manzana_unif")

            if "manzana_clic" in st.session_state and st.session_state.manzana_clic:
                st.text_input("✅ Manzana seleccionada (ID):", value=st.session_state.manzana_clic, disabled=True)
                if st.button("✅ Confirmar Manzana y Continuar"):
                    st.session_state.manzana_sel = st.session_state.manzana_clic
                    st.session_state.manzanas_localidad_sel = manzanas_localidad_sel
                    st.session_state.color_map = color_map
                    st.session_state.step = 4
                    st.rerun()
            else:
                st.info("Haz clic en una manzana del mapa para empezar.")

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
    st.header("🗺️ Paso 3: Análisis Contextual de la Manzana")

    manzanas = st.session_state.manzanas
    transporte = st.session_state.transporte
    colegios = st.session_state.colegios
    id_manzana = st.session_state.manzana_sel
    
    manzana_sel_gdf = manzanas[manzanas["id_manzana_unif"] == id_manzana]

    if manzana_sel_gdf.empty:
        st.warning("⚠️ No se encontraron datos para la manzana seleccionada.")
    else:
        st.markdown("### 🚇 Contexto de Transporte (Buffer 800m)")
        
        manzana_proj = manzana_sel_gdf.to_crs(epsg=3116)
        buffer_transporte_proj = manzana_proj.buffer(800)
        
        manzana_web_mercator = manzana_proj.to_crs(epsg=3857)
        buffer_transporte_web_mercator = buffer_transporte_proj.to_crs(epsg=3857)
        
        id_combi = manzana_proj["id_combi_acceso"].iloc[0]
        puntos_transporte_gdf = gpd.GeoDataFrame()
        
        if pd.notna(id_combi):
            multipunto_transporte_series = transporte.loc[transporte["id_combi_acceso"] == id_combi, "geometry"]
            if not multipunto_transporte_series.empty:
                multipunto_transporte = multipunto_transporte_series.iloc[0]
                puntos_transporte_gdf = gpd.GeoDataFrame(geometry=list(multipunto_transporte.geoms), crs=transporte.crs)
        
        puntos_transporte_web_mercator = puntos_transporte_gdf.to_crs(epsg=3857)

        fig_transporte, ax_transporte = plt.subplots(figsize=(10, 10))
        buffer_transporte_web_mercator.plot(ax=ax_transporte, color='red', alpha=0.1, edgecolor='red', linewidth=1)
        manzana_web_mercator.plot(ax=ax_transporte, color='green', alpha=0.5, edgecolor='darkgreen', linewidth=2)
        if not puntos_transporte_web_mercator.empty:
            puntos_transporte_web_mercator.plot(ax=ax_transporte, marker='o', color='red', markersize=50, edgecolor='black')

        cx.add_basemap(ax_transporte, crs=manzana_web_mercator.crs.to_string(), source=cx.providers.CartoDB.Positron)
        ax_transporte.set_title(f"Contexto de Transporte para la Manzana {id_manzana}")
        ax_transporte.set_axis_off()
        plt.tight_layout()
        st.pyplot(fig_transporte)
        
        buffer_img_transporte = BytesIO()
        fig_transporte.savefig(buffer_img_transporte, format='png', bbox_inches='tight', dpi=150)
        st.session_state.buffer_transporte = buffer_img_transporte

        st.markdown("### 🏫 Contexto Educativo (Buffer 1000m)")
        buffer_colegios_proj = manzana_proj.buffer(1000)
        buffer_colegios_web_mercator = buffer_colegios_proj.to_crs(epsg=3857)

        id_colegios = manzana_proj["id_com_colegios"].iloc[0]
        puntos_colegios_gdf = gpd.GeoDataFrame()
        if pd.notna(id_colegios):
            puntos_colegios_gdf = colegios[colegios["id_com_colegios"] == id_colegios]

        puntos_colegios_web_mercator = puntos_colegios_gdf.to_crs(epsg=3857)

        fig_colegios, ax_colegios = plt.subplots(figsize=(10, 10))
        buffer_colegios_web_mercator.plot(ax=ax_colegios, color='blue', alpha=0.1, edgecolor='blue', linewidth=1)
        manzana_web_mercator.plot(ax=ax_colegios, color='green', alpha=0.5, edgecolor='darkgreen', linewidth=2)
        if not puntos_colegios_web_mercator.empty:
            puntos_colegios_web_mercator.plot(ax=ax_colegios, marker='^', color='blue', markersize=50, edgecolor='black')

        cx.add_basemap(ax_colegios, crs=manzana_web_mercator.crs.to_string(), source=cx.providers.CartoDB.Positron)
        ax_colegios.set_title(f"Contexto Educativo para la Manzana {id_manzana}")
        ax_colegios.set_axis_off()
        plt.tight_layout()
        st.pyplot(fig_colegios)

        buffer_img_colegios = BytesIO()
        fig_colegios.savefig(buffer_img_colegios, format='png', bbox_inches='tight', dpi=150)
        st.session_state.buffer_colegios = buffer_img_colegios
        
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
    st.header("📊 Paso 4: Análisis Comparativo y Proyección")

    localidades = st.session_state.localidades
    manzanas_localidad_sel = st.session_state.manzanas_localidad_sel.copy()
    manzana_id = st.session_state.manzana_sel
    
    manzana_sel = manzanas_localidad_sel[manzanas_localidad_sel["id_manzana_unif"] == manzana_id]

    if manzana_sel.empty:
        st.error("Error crítico: No se pudo recuperar la información de la manzana seleccionada.")
        if st.button("🔙 Volver"):
            st.session_state.step = 3
            st.rerun()
    else:
        valor_manzana = manzana_sel["valor_m2"].iloc[0]
        cod_localidad = manzana_sel["num_localidad"].iloc[0]
        nombre_localidad = localidades.loc[localidades["num_localidad"] == cod_localidad, "nombre_localidad"].iloc[0]

        st.markdown("### 📈 Comparativo de valor del metro cuadrado")
        
        id_area_manzana = manzana_sel["id_area"].iloc[0]
        manzanas_area = manzanas_localidad_sel[manzanas_localidad_sel["id_area"] == id_area_manzana]
        promedio_area = manzanas_area["valor_m2"].mean() if not manzanas_area.empty else 0

        buffer_300 = manzana_sel.to_crs(epsg=3116).buffer(300).to_crs(epsg=4326)[0]
        manzanas_buffer = manzanas_localidad_sel[manzanas_localidad_sel.geometry.intersects(buffer_300)]
        promedio_buffer = manzanas_buffer["valor_m2"].mean() if not manzanas_buffer.empty else 0
        
        fig_bar, ax_bar = plt.subplots(figsize=(10, 5))
        data_comp = pd.DataFrame({
            "Etiqueta": ["Manzana Seleccionada", "Promedio Área POT", "Promedio Vecindario (300m)"],
            "Valor": [valor_manzana, promedio_area, promedio_buffer]
        })
        bars = sns.barplot(x="Etiqueta", y="Valor", data=data_comp, ax=ax_bar, palette="viridis")

        ax_bar.set_title("Comparativo de Valor del Metro Cuadrado")
        ax_bar.set_ylabel("Valor (COP)")
        ax_bar.set_xlabel("")
        ax_bar.yaxis.set_major_formatter(plt.FuncFormatter(lambda x, p: f"${x:,.0f}"))
        ax_bar.bar_label(bars, fmt=lambda x: f'${x:,.0f}', padding=3)
        plt.tight_layout()
        st.pyplot(fig_bar)
        
        buffer_valorm2 = BytesIO()
        fig_bar.savefig(buffer_valorm2, format='png', bbox_inches='tight')
        st.session_state.buffer_valorm2 = buffer_valorm2

        st.markdown("### 🥧 Distribución de usos POT en un radio de 500m")
        buffer_uso = manzana_sel.to_crs(epsg=3116).buffer(500).to_crs(epsg=4326)[0]
        manzanas_buffer_uso = manzanas_localidad_sel[manzanas_localidad_sel.geometry.intersects(buffer_uso)]
        conteo_uso = manzanas_buffer_uso["uso_pot_simplificado"].value_counts().reset_index()
        conteo_uso.columns = ["uso", "cantidad"]

        if not conteo_uso.empty:
            color_map = st.session_state.color_map
            fig_pie, ax_pie = plt.subplots()
            colores_pie = [color_map.get(uso, "#808080") for uso in conteo_uso["uso"]]
            ax_pie.pie(conteo_uso["cantidad"], labels=conteo_uso["uso"], autopct='%1.1f%%', startangle=90, colors=colores_pie)
            ax_pie.axis('equal')
            ax_pie.set_title("Distribución de Usos POT (Buffer 500m)")
            st.pyplot(fig_pie)
            
            buffer_dist_pot = BytesIO()
            fig_pie.savefig(buffer_dist_pot, format='png', bbox_inches='tight')
            st.session_state.buffer_dist_pot = buffer_dist_pot
        else:
            st.warning("⚠️ No se encontraron manzanas con clasificación POT dentro del buffer de 500m.")
            conteo_uso = pd.DataFrame([{"uso": "N/A", "cantidad": 0}])

        st.markdown("### 💹 Proyección del valor m² para los próximos años")
        proyeccion_cols = ["valor_m2", "valor_2025_s1", "valor_2025_s2", "valor_2026_s1", "valor_2026_s2"]
        serie_proyeccion = manzana_sel[proyeccion_cols].iloc[0]
        
        if not serie_proyeccion.isnull().any():
            fechas = ["2024-S2", "2025-S1", "2025-S2", "2026-S1", "2026-S2"]
            fig_line, ax_line = plt.subplots(figsize=(10, 5))
            ax_line.plot(fechas, serie_proyeccion, marker='o', linestyle='-', color='royalblue')
            
            for i, txt in enumerate(serie_proyeccion):
                ax_line.annotate(f"${txt:,.0f}", (fechas[i], serie_proyeccion[i]), textcoords="offset points", xytext=(0,10), ha='center')

            ax_line.set_title(f"Evolución Proyectada del Valor m² - Manzana {manzana_id}")
            ax_line.set_ylabel("Valor (COP)")
            ax_line.set_xlabel("Periodo")
            ax_line.grid(True, which='both', linestyle='--', linewidth=0.5)
            ax_line.yaxis.set_major_formatter(plt.FuncFormatter(lambda x, p: f"${x:,.0f}"))
            plt.tight_layout()
            st.pyplot(fig_line)

            buffer_proyeccion = BytesIO()
            fig_line.savefig(buffer_proyeccion, format='png', bbox_inches='tight')
            st.session_state.buffer_proyeccion = buffer_proyeccion
        else:
            st.warning("⚠️ La información de proyección del valor m² no está completa para esta manzana.")

        st.session_state.nombre_localidad = nombre_localidad
        st.session_state.ficha_estilizada = pd.DataFrame({
            "ID Manzana": [manzana_id], "Localidad": [nombre_localidad],
            "Estrato": [manzana_sel["estrato"].values[0]], "Valor m²": [f"${valor_manzana:,.0f}"],
            "Prom. Área POT": [f"${promedio_area:,.0f}"], "Prom. 300m": [f"${promedio_buffer:,.0f}"],
            "Uso Mayoritario (500m)": [conteo_uso.iloc[0]["uso"]]
        })

        st.markdown("---")
        col1, col2 = st.columns(2)
        with col1:
            if st.button("🔙 Volver al Análisis Espacial"):
                st.session_state.step = 4
                st.rerun()
        with col2:
            if st.button("➡️ Continuar al Análisis de Seguridad"):
                st.session_state.step = 6
                st.rerun()


# --- Bloque 6: Contexto de Seguridad por Localidad ---
elif st.session_state.step == 6:
    st.header("🔎 Paso 5: Contexto de Seguridad")

    localidades = st.session_state.localidades
    cod_loc_actual = st.session_state.manzanas_localidad_sel["num_localidad"].iloc[0]
    nombre_loc_actual = st.session_state.nombre_localidad
    
    df_seguridad = localidades[["nombre_localidad", "cantidad_delitos", "nivel_riesgo_delictivo"]].copy().sort_values("cantidad_delitos", ascending=False)
    
    st.markdown("### 🔪 Cantidad de Delitos Reportados por Localidad")
    fig_seg, ax_seg = plt.subplots(figsize=(10, 8))

    colores = ['#e30613' if x == nombre_loc_actual else '#d3d3d3' for x in df_seguridad["nombre_localidad"]]
    
    sns.barplot(x="cantidad_delitos", y="nombre_localidad", data=df_seguridad, palette=colores, ax=ax_seg)
    
    riesgo_actual_series = df_seguridad.loc[df_seguridad['nombre_localidad'] == nombre_loc_actual, 'nivel_riesgo_delictivo']
    if not riesgo_actual_series.empty:
        riesgo_actual = riesgo_actual_series.iloc[0]
        valor_actual = df_seguridad.loc[df_seguridad['nombre_localidad'] == nombre_loc_actual, 'cantidad_delitos'].iloc[0]
        y_pos = df_seguridad['nombre_localidad'].tolist().index(nombre_loc_actual)
        ax_seg.text(valor_actual, y_pos, f' {riesgo_actual}', verticalalignment='center', fontweight='bold', color='black', backgroundcolor='#FFFFFFCC')

    ax_seg.set_title("Contexto de Seguridad por Localidad\n(Fuente: Secretaría Distrital de Seguridad)", pad=20)
    ax_seg.set_xlabel("Cantidad de Delitos Reportados")
    ax_seg.set_ylabel("")
    ax_seg.xaxis.set_major_formatter(plt.FuncFormatter(lambda x, p: f"{x:,.0f}"))
    ax_seg.grid(axis='x', linestyle='--', alpha=0.7)
    
    plt.tight_layout()
    st.pyplot(fig_seg)

    buffer_seguridad = BytesIO()
    fig_seg.savefig(buffer_seguridad, format='png', bbox_inches='tight')
    st.session_state.buffer_seguridad = buffer_seguridad
    
    col1, col2, col3 = st.columns(3)
    with col1:
        if st.button("🔙 Volver al Análisis Comparativo"):
            st.session_state.step = 5
            st.rerun()
    with col2:
        if st.button("➡️ Finalizar y Generar Informe"):
            st.session_state.step = 7
            st.rerun()
    with col3:
        if st.button("🔄 Reiniciar App"):
            for key in list(st.session_state.keys()):
                if key != 'step':
                    del st.session_state[key]
            st.session_state.step = 1
            st.rerun()


# --- Bloque 7: Generación del Informe Ejecutivo ---
elif st.session_state.step == 7:
    st.header("📑 Paso Final: Informe Ejecutivo")

    required_buffers = ['buffer_colegios', 'buffer_transporte', 'buffer_valorm2', 'buffer_seguridad']
    # Opcionales, no detienen el informe
    if 'buffer_dist_pot' not in st.session_state:
        st.session_state.buffer_dist_pot = BytesIO() # Buffer vacío si no se generó
    if 'buffer_proyeccion' not in st.session_state:
        st.session_state.buffer_proyeccion = BytesIO() # Buffer vacío si no se generó

    if not all(key in st.session_state for key in required_buffers):
        st.error("Faltan datos para generar el informe. Por favor, reinicie el proceso.")
        if st.button("🔄 Reiniciar"):
            st.session_state.step = 1
            st.rerun()
    else:
        with st.spinner('📝 Generando informe HTML...'):
            def buffer_a_base64(buffer):
                buffer.seek(0)
                img_bytes = buffer.read()
                if not img_bytes:
                    return "" # Retorna string vacío si el buffer no tiene contenido
                return base64.b64encode(img_bytes).decode('utf-8')

            img_colegios_base64 = buffer_a_base64(st.session_state.buffer_colegios)
            img_transporte_base64 = buffer_a_base64(st.session_state.buffer_transporte)
            img_distribucion_base64 = buffer_a_base64(st.session_state.buffer_dist_pot)
            img_valorm2_base64 = buffer_a_base64(st.session_state.buffer_valorm2)
            img_seguridad_base64 = buffer_a_base64(st.session_state.buffer_seguridad)
            img_proyeccion_base64 = buffer_a_base64(st.session_state.buffer_proyeccion)
            
            html_ficha = st.session_state.ficha_estilizada.to_html(index=False, classes='dataframe', justify='center')

            def create_card(title, img_base64):
                if img_base64:
                    return f"""
                    <div class="card">
                        <h2>{title}</h2>
                        <img src="data:image/png;base64,{img_base64}">
                    </div>"""
                return ""

            html_content = f"""
            <!DOCTYPE html>
            <html lang="es">
            <head>
                <meta charset="UTF-8">
                <title>Informe de Análisis Inmobiliario</title>
                <style>
                    body {{ font-family: Arial, sans-serif; margin: 40px; color: #333; }}
                    h1, h2 {{ color: #003366; border-bottom: 2px solid #003366; padding-bottom: 10px;}}
                    h1 {{ text-align: center; }}
                    .dataframe {{ border-collapse: collapse; width: 90%; margin: 20px auto; border: 1px solid #ccc; font-size: 1.1em; }}
                    .dataframe th, .dataframe td {{ padding: 12px; text-align: center; border-bottom: 1px solid #ddd; }}
                    .dataframe th {{ background-color: #f2f2f2; }}
                    .container {{ display: grid; grid-template-columns: repeat(auto-fit, minmax(400px, 1fr)); gap: 25px; margin-top: 30px; }}
                    .card {{ border: 1px solid #eee; padding: 20px; box-shadow: 0 4px 8px rgba(0,0,0,0.1); border-radius: 8px; text-align: center; }}
                    .card img {{ max-width: 100%; height: auto; border-radius: 4px; margin-top: 15px; }}
                </style>
            </head>
            <body>
                <h1>Informe de Análisis de Inversión Inmobiliaria</h1>
                <h2>Manzana ID: {st.session_state.manzana_sel}</h2>
                
                <h2>Ficha Resumen de la Manzana</h2>
                {html_ficha}
                
                <div class="container">
                    {create_card("Proyección de Valor", img_proyeccion_base64)}
                    {create_card("Comparativo de Valor m²", img_valorm2_base64)}
                    {create_card("Contexto de Transporte (800m)", img_transporte_base64)}
                    {create_card("Contexto Educativo (1000m)", img_colegios_base64)}
                    {create_card("Distribución Usos POT (500m)", img_distribucion_base64)}
                    {create_card("Contexto de Seguridad Localidad", img_seguridad_base64)}
                </div>
            </body>
            </html>
            """
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
            st.rerun()