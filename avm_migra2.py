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
import requests  # Para descargar los archivos TopoJSON desde la URL

# --- Librerías para Visualización Geoespacial ---

# 1. Para mapas INTERACTIVOS y captura de clics (reemplaza a Plotly para mapas interactivos)
import folium
from streamlit_folium import st_folium
from shapely.geometry import Point, MultiPoint  # Utilidades para geometrías

# 2. Para gráficos ESTÁTICOS (barras, torta, etc.) y mapas para informes
#    Esta combinación reemplaza a Plotly para mayor estabilidad y capturas confiables.
import matplotlib.pyplot as plt
import seaborn as sns

# --- Librería para la Carga de Datos Optimizada ---

# Para convertir los archivos TopoJSON (más ligeros) a GeoDataFrames en memoria
import topojson as tp

# --- Configuración de Estilo para los Gráficos (Opcional pero Recomendado) ---
# Esto le dará a tus gráficos de Matplotlib un aspecto más moderno y limpio.
sns.set_theme(
    style="whitegrid", 
    rc={"figure.figsize": (10, 6), "axes.titlesize": 16, "axes.labelsize": 12}
)


# CARGA DE DATOS 

# La configuración de la página y el título se mantienen
st.set_page_config(page_title="AVM Bogotá APP", page_icon="🏠", layout="centered")

st.title("🏠 AVM Bogotá - Análisis de Manzanas")

# --- Función cacheada para la carga de datos (VERSIÓN OPTIMIZADA CON TOPOJSON) ---
@st.cache_data
def cargar_datasets():
    """
    Carga los datasets desde un repositorio de GitHub.
    Utiliza archivos TopoJSON para una transferencia de datos más rápida y eficiente,
    y los convierte a GeoDataFrames para su uso en la aplicación.
    """
    datasets = {
        "localidades": "https://github.com/andres-fuentex/tfm-avm-bogota/raw/main/datos_visualizacion/datos_geograficos_topo/dim_localidad.json",
        "areas": "https://github.com/andres-fuentex/tfm-avm-bogota/raw/main/datos_visualizacion/datos_geograficos_topo/dim_area.json",
        "manzanas": "https://github.com/andres-fuentex/tfm-avm-bogota/raw/main/datos_visualizacion/datos_geograficos_topo/tabla_hechos.json",
        "transporte": "https://github.com/andres-fuentex/tfm-avm-bogota/raw/main/datos_visualizacion/datos_geograficos_topo/dim_transporte.json",
        "colegios": "https://github.com/andres-fuentex/tfm-avm-bogota/raw/main/datos_visualizacion/datos_geograficos_topo/dim_colegios.json"
    }

    dataframes = {}
    total = len(datasets)
    progress_bar = st.progress(0, text="Iniciando carga de datos...")

    for idx, (nombre, url) in enumerate(datasets.items(), start=1):
        progress_text = f"Cargando {nombre} ({idx}/{total})..."
        progress_bar.progress(int((idx / total) * 100), text=progress_text)
        
        try:
            # 1. Descargar el archivo TopoJSON usando requests
            response = requests.get(url)
            response.raise_for_status()  # Lanza un error si la descarga falla
            
            # 2. Parsear el contenido a un diccionario de Python
            topo_data = response.json()
            
            # 3. Convertir el objeto TopoJSON a un GeoDataFrame
            #    Extraemos el nombre de la capa principal del archivo.
            layer_name = list(topo_data['objects'].keys())[0]
            gdf = tp.GeoDataFrame.from_feature(topo_data, layer_name)
            
            # Asignar un CRS si no se infiere correctamente (WGS84 es estándar)
            if gdf.crs is None:
                gdf.set_crs(epsg=4326, inplace=True)

            dataframes[nombre] = gdf

        except requests.exceptions.RequestException as e:
            st.error(f"Error de red al cargar '{nombre}': {e}")
            return None # Detiene la ejecución si un archivo no se puede descargar
        except Exception as e:
            st.error(f"Error al procesar el archivo '{nombre}': {e}")
            return None

    progress_bar.empty() # Limpia la barra de progreso al finalizar
    return dataframes


# --- Control de flujo ---
# Esta parte del código no necesita cambios y funcionará igual
if "step" not in st.session_state:
    st.session_state.step = 1

# El Bloque 1 de la interfaz de usuario tampoco necesita cambios
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
            for nombre, df in dataframes.items():
                st.session_state[nombre] = df
            st.session_state.step = 2
            st.rerun()
    else:
        st.error("❌ No se pudieron cargar los datos. Por favor, recarga la página o contacta al administrador.")

# --- Bloque 2: Selección de Localidad ---
elif st.session_state.step == 2:
    st.header("🌆 Selección de Localidad")
    st.markdown("Haz clic en la localidad del mapa que te interesa analizar.")

    # Los datos ya están cargados en st.session_state
    localidades_gdf = st.session_state.localidades

    # --- Creación del Mapa Interactivo con Folium ---
    # Calcular centro y límites para la vista inicial del mapa
    bounds = localidades_gdf.total_bounds
    center = [(bounds[1] + bounds[3]) / 2, (bounds[0] + bounds[2]) / 2]

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
        # El resaltado al pasar el ratón es clave para una buena experiencia de usuario
        highlight_function=lambda feature: {
            "weight": 3, 
            "color": "#e30613", 
            "fillOpacity": 0.6
        },
        # El tooltip da información instantánea antes del clic
        tooltip=folium.GeoJsonTooltip(
            fields=["nombre_localidad"], 
            aliases=["Localidad:"],
            labels=True,
            sticky=True
        )
    ).add_to(mapa)

    # --- Renderizado del Mapa y Captura de la Interacción ---
    # Pedimos que nos devuelva las propiedades del objeto clickeado
    map_data = st_folium(mapa, width=700, height=500, returned_objects=["last_object_clicked_properties"])

    # --- Lógica de Selección y Confirmación ---
    # Obtenemos directamente las propiedades del polígono en el que se hizo clic
    if map_data and map_data.get("last_object_clicked_properties"):
        clicked_localidad_name = map_data["last_object_clicked_properties"].get("nombre_localidad")
        st.session_state.localidad_clic = clicked_localidad_name

    # Si se ha seleccionado una localidad, mostrarla y permitir la confirmación
    if "localidad_clic" in st.session_state:
        st.text_input("✅ Localidad seleccionada", value=st.session_state.localidad_clic, disabled=True)
        if st.button("✅ Confirmar y Continuar"):
            # Guardar la selección final y pasar al siguiente paso
            st.session_state.localidad_sel = st.session_state.localidad_clic
            st.session_state.step = 3
            st.rerun()

    if st.button("🔄 Volver al Inicio"):
        # Limpiar estado para evitar selecciones residuales
        if "localidad_clic" in st.session_state:
            del st.session_state.localidad_clic
        st.session_state.step = 1
        st.rerun()

    # Mensaje de ayuda si aún no se ha seleccionado nada
    if "localidad_clic" not in st.session_state:
        st.info("Selecciona una localidad en el mapa y confírmala para continuar.")
    
    # --- Bloque 3: Selección de Manzana con Clic Directo ---
elif st.session_state.step == 3:
    st.subheader(f"🏘️ Análisis y Selección de Manzana en {st.session_state.localidad_sel}")

    # --- 1. Preparación de Datos ---
    # Cargar los GeoDataFrames necesarios desde el estado de la sesión
    localidades = st.session_state.localidades
    areas = st.session_state.areas
    manzanas = st.session_state.manzanas
    localidad_sel = st.session_state.localidad_sel
    
    # Filtrar las manzanas por la localidad seleccionada
    cod_localidad = localidades.loc[localidades["nombre_localidad"] == localidad_sel, "num_localidad"].iloc[0]
    manzanas_localidad_sel = manzanas[manzanas["num_localidad"] == cod_localidad].copy()

    # Manejar caso en que no hay manzanas para la localidad
    if manzanas_localidad_sel.empty:
        st.warning("⚠️ No se encontraron manzanas para la localidad seleccionada.")
        if st.button("🔙 Volver a Selección de Localidad"):
            st.session_state.step = 2
            st.rerun()
    else:
        # Enriquecer manzanas con información de uso del suelo (POT)
        areas_sel = areas[areas["num_localidad"] == cod_localidad].copy()
        if not areas_sel.empty:
            manzanas_localidad_sel = manzanas_localidad_sel.merge(
                areas_sel[["id_area", "uso_pot_simplificado"]], on="id_area", how="left"
            )
        manzanas_localidad_sel["uso_pot_simplificado"] = manzanas_localidad_sel["uso_pot_simplificado"].fillna("Sin clasificación")

        # Crear una paleta de colores para los diferentes usos del suelo
        usos_unicos = manzanas_localidad_sel["uso_pot_simplificado"].unique()
        # Usaremos una paleta de colores de Seaborn, que es robusta
        palette = sns.color_palette("viridis", n_colors=len(usos_unicos)).as_hex()
        color_map = {uso: color for uso, color in zip(usos_unicos, palette)}
        if "Sin clasificación" not in color_map:
            color_map["Sin clasificación"] = "#808080" # Gris para lo no clasificado

        # --- 2. Creación del Mapa Interactivo ---
        st.markdown("""
        ### 🖱️ Haz clic sobre una manzana para seleccionarla
        - La manzana **se resaltará en rojo** al pasar el ratón sobre ella.
        - **Usa el zoom** para acercarte y seleccionar con mayor precisión.
        """)

        # Centrar el mapa en las manzanas de la localidad
        bounds = manzanas_localidad_sel.total_bounds
        center = [(bounds[1] + bounds[3]) / 2, (bounds[0] + bounds[2]) / 2]
        
        mapa_manzanas = folium.Map(location=center, tiles="CartoDB positron", zoom_start=13)

        # Añadir las manzanas al mapa con estilo y funcionalidad
        geo_manzanas = folium.GeoJson(
            manzanas_localidad_sel,
            style_function=lambda feature: {
                "fillColor": color_map.get(feature["properties"]["uso_pot_simplificado"], "#808080"),
                "color": "black",
                "weight": 1,
                "fillOpacity": 0.6,
            },
            highlight_function=lambda x: {"weight": 3, "color": "#e30613", "fillOpacity": 0.8},
            tooltip=folium.GeoJsonTooltip(
                fields=["id_manzana_unif", "uso_pot_simplificado"],
                aliases=["ID Manzana:", "Uso POT:"],
                style=("background-color: white; color: #333333; font-family: arial; font-size: 12px; padding: 10px;")
            )
        ).add_to(mapa_manzanas)

        # Ajustar el zoom del mapa para que todas las manzanas sean visibles
        mapa_manzanas.fit_bounds(geo_manzanas.get_bounds())

        # --- 3. Renderizado y Captura del Clic ---
        map_data = st_folium(mapa_manzanas, width=700, height=500, returned_objects=["last_object_clicked_properties"])

        # --- 4. Lógica de Confirmación ---
        if map_data and map_data.get("last_object_clicked_properties"):
            manzana_clic_id = map_data["last_object_clicked_properties"].get("id_manzana_unif")
            # Guardar la selección del clic en el estado de la sesión
            st.session_state.manzana_clic = manzana_clic_id

        # Mostrar la selección y el botón de confirmar
        if "manzana_clic" in st.session_state:
            st.text_input("✅ Manzana seleccionada (ID):", value=st.session_state.manzana_clic, disabled=True)
            if st.button("✅ Confirmar Manzana y Continuar"):
                # Al confirmar, guardar los datos necesarios para los siguientes pasos
                st.session_state.manzana_sel = st.session_state.manzana_clic
                st.session_state.manzanas_localidad_sel = manzanas_localidad_sel
                st.session_state.color_map = color_map
                
                st.session_state.step = 4
                st.rerun()
        else:
            st.info("Haz clic en una manzana del mapa para empezar.")

        # --- 5. Navegación ---
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

    # Para añadir el mapa base, es posible que necesites instalar: pip install contextily
    import contextily as cx

    # --- 1. Carga y Filtrado de Datos ---
    # Los datos ya están en el estado de la sesión
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
        # --- 2. Preparación de Geometrías para el Contexto de TRANSPORTE ---
        st.markdown("""
        ### 🚇 Contexto de Transporte
        Se muestra un buffer de **800 metros** alrededor de la manzana, resaltando las estaciones de TransMilenio cercanas (puntos rojos).
        """)

        # Reproyectar a un CRS local para un buffer preciso (SIRGAS / Bogotá Zona)
        manzana_proj = manzana_sel_gdf.to_crs(epsg=3116)
        
        # Crear el buffer de 800m
        buffer_transporte_proj = manzana_proj.buffer(800)
        
        # Obtener los puntos de las estaciones de transporte
        id_combi = manzana_proj["id_combi_acceso"].iloc[0]
        multipunto_transporte = transporte.loc[transporte["id_combi_acceso"] == id_combi, "geometry"].iloc[0]
        puntos_transporte_gdf = gpd.GeoDataFrame(geometry=list(multipunto_transporte.geoms), crs=transporte.crs)
        puntos_transporte_proj = puntos_transporte_gdf.to_crs(epsg=3116)

        # Reproyectar todo a Web Mercator (EPSG:3857) para poder usar el mapa base
        manzana_web_mercator = manzana_proj.to_crs(epsg=3857)
        buffer_transporte_web_mercator = buffer_transporte_proj.to_crs(epsg=3857)
        puntos_transporte_web_mercator = puntos_transporte_proj.to_crs(epsg=3857)

        # --- Creación del Mapa Estático (Transporte) ---
        fig_transporte, ax_transporte = plt.subplots(figsize=(10, 10))
        
        # Dibujar las capas: primero el buffer, luego la manzana, luego los puntos
        buffer_transporte_web_mercator.plot(ax=ax_transporte, color='red', alpha=0.1, edgecolor='red', linewidth=1)
        manzana_web_mercator.plot(ax=ax_transporte, color='green', alpha=0.5, edgecolor='darkgreen', linewidth=2)
        puntos_transporte_web_mercator.plot(ax=ax_transporte, marker='o', color='red', markersize=50, edgecolor='black')

        # Añadir el mapa base de OpenStreetMap
        cx.add_basemap(ax_transporte, crs=manzana_web_mercator.crs.to_string(), source=cx.providers.CartoDB.Positron)
        
        # Limpiar y ajustar el gráfico
        ax_transporte.set_title(f"Contexto de Transporte para la Manzana {id_manzana}")
        ax_transporte.set_axis_off()
        
        # Mostrar el gráfico en Streamlit
        st.pyplot(fig_transporte)
        
        # Guardar la imagen en el buffer para el informe
        buffer_img_transporte = BytesIO()
        fig_transporte.savefig(buffer_img_transporte, format='png', bbox_inches='tight', dpi=150)

        # --- 3. Preparación de Geometrías para el Contexto EDUCATIVO ---
        st.markdown("""
        ### 🏫 Contexto Educativo
        Se muestra un buffer de **1000 metros** alrededor de la manzana, resaltando los colegios cercanos (puntos azules).
        """)

        # Crear el buffer de 1000m (usando la manzana ya proyectada)
        buffer_colegios_proj = manzana_proj.buffer(1000)
        
        # Obtener los puntos de los colegios
        id_colegios = manzana_proj["id_com_colegios"].iloc[0]
        puntos_colegios_gdf = colegios[colegios["id_com_colegios"] == id_colegios]
        
        # Reproyectar todo a Web Mercator para el mapa
        buffer_colegios_web_mercator = buffer_colegios_proj.to_crs(epsg=3857)
        puntos_colegios_web_mercator = puntos_colegios_gdf.to_crs(epsg=3857)

        # --- Creación del Mapa Estático (Colegios) ---
        fig_colegios, ax_colegios = plt.subplots(figsize=(10, 10))

        buffer_colegios_web_mercator.plot(ax=ax_colegios, color='blue', alpha=0.1, edgecolor='blue', linewidth=1)
        manzana_web_mercator.plot(ax=ax_colegios, color='green', alpha=0.5, edgecolor='darkgreen', linewidth=2)
        if not puntos_colegios_web_mercator.empty:
            puntos_colegios_web_mercator.plot(ax=ax_colegios, marker='^', color='blue', markersize=50, edgecolor='black')

        cx.add_basemap(ax_colegios, crs=manzana_web_mercator.crs.to_string(), source=cx.providers.CartoDB.Positron)
        ax_colegios.set_title(f"Contexto Educativo para la Manzana {id_manzana}")
        ax_colegios.set_axis_off()
        st.pyplot(fig_colegios)

        buffer_img_colegios = BytesIO()
        fig_colegios.savefig(buffer_img_colegios, format='png', bbox_inches='tight', dpi=150)
        
        # --- 4. Navegación ---
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
            if st.button("➡️ Continuar al Análisis Comparativo"):
                # Guardar los buffers de imagen para el informe final
                st.session_state.buffer_transporte = buffer_img_transporte
                st.session_state.buffer_colegios = buffer_img_colegios
                st.session_state.manzana_seleccionada_df = manzana_sel_gdf # Guardar el GDF para el siguiente paso
                st.session_state.step = 5
                st.rerun()
        # --- Bloque 5: Análisis Comparativo y Proyección del Valor m² ---
elif st.session_state.step == 5:
    st.subheader("📊 Análisis Comparativo y Proyección del Valor m²")

    # --- 1. Carga y Preparación de Datos ---
    # Cargar datos desde el estado de la sesión
    localidades = st.session_state.localidades
    manzanas_localidad_sel = st.session_state.manzanas_localidad_sel.copy()
    color_map = st.session_state.color_map
    manzana_id = st.session_state.manzana_sel
    
    # Filtrar la manzana específica que se está analizando
    manzana_sel = manzanas_localidad_sel[manzanas_localidad_sel["id_manzana_unif"] == manzana_id]
    valor_manzana = manzana_sel["valor_m2"].iloc[0]
    cod_localidad = manzana_sel["num_localidad"].iloc[0]
    nombre_localidad = localidades.loc[localidades["num_localidad"] == cod_localidad, "nombre_localidad"].iloc[0]

    # --- 2. Gráfico de Barras: Comparativo de Valor m² ---
    st.markdown("### 📈 Comparativo de valor m²")
    
    # Calcular promedios para la comparación
    id_area_manzana = manzana_sel["id_area"].iloc[0]
    manzanas_area = manzanas_localidad_sel[manzanas_localidad_sel["id_area"] == id_area_manzana]
    promedio_area = manzanas_area["valor_m2"].mean() if not manzanas_area.empty else 0

    buffer_300 = manzana_sel.to_crs(epsg=3116).buffer(300).to_crs(manzanas_localidad_sel.crs)
    manzanas_buffer = manzanas_localidad_sel[manzanas_localidad_sel.geometry.intersects(buffer_300.iloc[0])]
    promedio_buffer = manzanas_buffer["valor_m2"].mean() if not manzanas_buffer.empty else 0
    
    # Crear el gráfico con Matplotlib
    fig_bar, ax_bar = plt.subplots(figsize=(10, 5))
    labels = ["Manzana Seleccionada", "Promedio Área POT", "Promedio 300m"]
    valores = [valor_manzana, promedio_area, promedio_buffer]
    bars = ax_bar.bar(labels, valores, color=["#1f77b4", "#aec7e8", "#ff7f0e"])

    # Añadir etiquetas y formato
    ax_bar.set_title("Comparativo de Valor del Metro Cuadrado")
    ax_bar.set_ylabel("Valor (COP)")
    ax_bar.yaxis.set_major_formatter(plt.FuncFormatter(lambda x, p: f"${x:,.0f}"))
    ax_bar.bar_label(bars, fmt=lambda x: f'${x:,.0f}', padding=3) # Etiquetas sobre las barras
    
    st.pyplot(fig_bar)

    # Guardar en buffer para el informe
    buffer_valorm2 = BytesIO()
    fig_bar.savefig(buffer_valorm2, format='png', bbox_inches='tight')
    st.session_state.buffer_valorm2 = buffer_valorm2

    # --- 3. Gráfico de Torta: Distribución de Usos POT ---
    st.markdown("### 🥧 Distribución de usos POT en un radio de 500m")

    buffer_uso = manzana_sel.to_crs(epsg=3116).buffer(500).to_crs(manzanas_localidad_sel.crs)
    manzanas_buffer_uso = manzanas_localidad_sel[manzanas_localidad_sel.geometry.intersects(buffer_uso.iloc[0])]
    conteo_uso = manzanas_buffer_uso["uso_pot_simplificado"].value_counts().reset_index()
    conteo_uso.columns = ["uso", "cantidad"]

    if not conteo_uso.empty:
        fig_pie, ax_pie = plt.subplots()
        colores_pie = [color_map.get(uso, "#808080") for uso in conteo_uso["uso"]]
        ax_pie.pie(conteo_uso["cantidad"], labels=conteo_uso["uso"], autopct='%1.1f%%', startangle=90, colors=colores_pie)
        ax_pie.axis('equal')  # Asegura que el gráfico sea un círculo
        ax_pie.set_title(f"Distribución de Usos POT (Buffer 500m)")
        st.pyplot(fig_pie)
        
        buffer_dist_pot = BytesIO()
        fig_pie.savefig(buffer_dist_pot, format='png', bbox_inches='tight')
        st.session_state.buffer_dist_pot = buffer_dist_pot
    else:
        st.warning("⚠️ No se encontraron manzanas con clasificación POT dentro del buffer de 500m.")

    # --- 4. Gráfico de Líneas: Proyección del Valor ---
    st.markdown("### 📈 Proyección del valor m² para los próximos años")

    serie_proyeccion = manzana_sel[["valor_m2", "valor_2025_s1", "valor_2025_s2", "valor_2026_s1", "valor_2026_s2"]].iloc[0].values
    fechas = ["2024-S2", "2025-S1", "2025-S2", "2026-S1", "2026-S2"]
    
    if not any(pd.isna(serie_proyeccion)):
        fig_line, ax_line = plt.subplots(figsize=(10, 5))
        ax_line.plot(fechas, serie_proyeccion, marker='o', linestyle='-', color='royalblue')
        
        # Añadir etiquetas de texto para cada punto
        for i, txt in enumerate(serie_proyeccion):
            ax_line.annotate(f"${txt:,.0f}", (fechas[i], serie_proyeccion[i]), textcoords="offset points", xytext=(0,10), ha='center')

        ax_line.set_title(f"Evolución Proyectada del Valor m² - Manzana {manzana_id}")
        ax_line.set_ylabel("Valor (COP)")
        ax_line.set_xlabel("Periodo")
        ax_line.grid(True, which='both', linestyle='--', linewidth=0.5)
        ax_line.yaxis.set_major_formatter(plt.FuncFormatter(lambda x, p: f"${x:,.0f}"))
        
        st.pyplot(fig_line)

        buffer_proyeccion = BytesIO()
        fig_line.savefig(buffer_proyeccion, format='png', bbox_inches='tight')
        st.session_state.buffer_proyeccion = buffer_proyeccion
    else:
        st.warning("⚠️ La información de proyección del valor m² no está completa para esta manzana.")

    # --- 5. Guardado de Datos para el Informe y Navegación ---
    st.session_state.nombre_localidad = nombre_localidad
    st.session_state.promedio_area = promedio_area
    st.session_state.promedio_buffer = promedio_buffer
    st.session_state.uso_pot_mayoritario = conteo_uso.iloc[0]["uso"] if not conteo_uso.empty else "Sin clasificación POT"
    
    # Crear la ficha de datos para el informe (esto no cambia)
    st.session_state.ficha_estilizada = pd.DataFrame({
        "ID Manzana": [manzana_id], "Localidad": [nombre_localidad],
        "Estrato": [manzana_sel["estrato"].values[0]], "Valor m²": [f"${valor_manzana:,.0f}"],
        "Prom. Área POT": [f"${promedio_area:,.0f}"], "Prom. 300m": [f"${promedio_buffer:,.0f}"],
        "Rentabilidad": [manzana_sel["rentabilidad"].values[0]]
    })

    st.markdown("---")
    col1, col2 = st.columns(2)
    with col1:
        if st.button("🔙 Volver al Análisis de Transporte y Educación"):
            st.session_state.step = 4
            st.rerun()
    with col2:
        if st.button("➡️ Continuar al Análisis de Seguridad"):
            st.session_state.step = 6
            st.rerun()

    # --- Bloque 6: Contexto de Seguridad por Localidad ---
elif st.session_state.step == 6:
    st.subheader("🔎 Contexto de Seguridad por Localidad")

    # --- 1. Preparación de Datos ---
    localidades = st.session_state.localidades
    # Necesitamos el cod_loc de la manzana seleccionada para saber qué localidad resaltar
    manzanas_localidad = st.session_state.manzanas_localidad_sel
    manzana_sel = manzanas_localidad[manzanas_localidad["id_manzana_unif"] == st.session_state.manzana_sel]

    if manzana_sel.empty:
        st.warning("⚠️ No se encontró información de la manzana seleccionada.")
        if st.button("🔙 Volver al Bloque Anterior"):
            st.session_state.step = 5
            st.rerun()
    else:
        cod_loc_actual = manzana_sel["num_localidad"].iloc[0]
        nombre_loc_actual = localidades.loc[localidades["num_localidad"] == cod_loc_actual, "nombre_localidad"].iloc[0]

        df_seguridad = localidades[["nombre_localidad", "cantidad_delitos", "nivel_riesgo_delictivo"]].copy()
        df_seguridad = df_seguridad.sort_values("cantidad_delitos", ascending=False)
        
        # --- 2. Creación del Gráfico de Barras con Matplotlib/Seaborn ---
        fig_seg, ax_seg = plt.subplots(figsize=(10, 8)) # Un poco más alto para que quepan todas las localidades

        # Crear una paleta de colores: un color para la localidad seleccionada, otro para el resto
        colores = ['#008000' if x == nombre_loc_actual else '#d3d3d3' for x in df_seguridad["nombre_localidad"]]

        # Usar Seaborn para un gráfico de barras horizontal más sencillo de crear
        sns.barplot(
            x="cantidad_delitos", 
            y="nombre_localidad", 
            data=df_seguridad, 
            palette=colores,
            ax=ax_seg
        )

        # Añadir etiqueta de texto solo para la barra resaltada
        riesgo_actual = df_seguridad.loc[df_seguridad['nombre_localidad'] == nombre_loc_actual, 'nivel_riesgo_delictivo'].iloc[0]
        valor_actual = df_seguridad.loc[df_seguridad['nombre_localidad'] == nombre_loc_actual, 'cantidad_delitos'].iloc[0]
        
        # Encontrar la posición de la barra para anotar el texto
        y_pos = df_seguridad['nombre_localidad'].tolist().index(nombre_loc_actual)
        ax_seg.text(valor_actual + 50, y_pos, f'Riesgo: {riesgo_actual}', 
                    verticalalignment='center',
                    fontweight='bold',
                    color='#008000')

        # --- 3. Estilo y Formato del Gráfico ---
        ax_seg.set_title("Contexto de Seguridad por Localidad\n(Fuente: Secretaría Distrital de Seguridad)", pad=20)
        ax_seg.set_xlabel("Cantidad de Delitos Reportados")
        ax_seg.set_ylabel("") # Quitar la etiqueta del eje Y
        ax_seg.xaxis.set_major_formatter(plt.FuncFormatter(lambda x, p: f"{x:,.0f}"))
        ax_seg.grid(axis='y', linestyle='', alpha=0) # Quitar las líneas de la cuadrícula vertical
        ax_seg.grid(axis='x', linestyle='--', alpha=0.7) # Mantener las horizontales
        
        plt.tight_layout() # Ajusta el gráfico para que no se corten las etiquetas
        st.pyplot(fig_seg)

        # Guardar en buffer para el informe
        buffer_seguridad = BytesIO()
        fig_seg.savefig(buffer_seguridad, format='png', bbox_inches='tight')
        st.session_state.buffer_seguridad = buffer_seguridad
        
        # Guardar el DataFrame para el informe final
        st.session_state.df_seguridad = df_seguridad
        if "nombre_localidad" not in st.session_state:
            st.session_state.nombre_localidad = nombre_loc_actual

        # --- 4. Navegación ---
        col1, col2, col3 = st.columns(3)
        with col1:
            if st.button("🔙 Volver al Análisis Comparativo"):
                st.session_state.step = 5
                st.rerun()
        with col2:
            if st.button("➡️ Finalizar y Descargar Informe"):
                st.session_state.step = 7
                st.rerun()
        with col3:
            if st.button("🔄 Reiniciar App"):
                # Limpiar todo el estado de la sesión para un reinicio completo
                for key in list(st.session_state.keys()):
                    del st.session_state[key]
                st.rerun()

                # --- Bloque 7: Generación del Informe Ejecutivo ---
elif st.session_state.step == 7:
    st.subheader("📑 Generación del Informe Ejecutivo")

    # --- 1. Generación del Mapa de Manzanas para el Informe (con GeoPandas/Matplotlib) ---
    # Este es el único gráfico que se genera en este bloque.
    with st.spinner('Preparando mapa final de manzanas para el informe...'):
        import contextily as cx

        manzanas_localidad = st.session_state.manzanas_localidad_sel.copy()
        color_map = st.session_state.color_map
        manzana_id_sel = st.session_state.manzana_sel
        
        # Mapa con todas las manzanas de la localidad
        fig_manzanas, ax_manzanas = plt.subplots(figsize=(10, 10))
        
        manzanas_localidad_web_mercator = manzanas_localidad.to_crs(epsg=3857)
        manzanas_localidad_web_mercator.plot(
            ax=ax_manzanas,
            # Asignar color según el uso POT usando el color_map
            color=manzanas_localidad_web_mercator['uso_pot_simplificado'].map(color_map),
            edgecolor='black',
            linewidth=0.5,
            alpha=0.6
        )
        
        # Resaltar la manzana seleccionada con un borde más grueso
        manzana_sel_web_mercator = manzanas_localidad_web_mercator[manzanas_localidad_web_mercator['id_manzana_unif'] == manzana_id_sel]
        manzana_sel_web_mercator.plot(
            ax=ax_manzanas,
            edgecolor='red',
            linewidth=2.5,
            facecolor='none' # Hacemos el relleno transparente para solo mostrar el borde
        )

        cx.add_basemap(ax_manzanas, crs=manzanas_localidad_web_mercator.crs.to_string(), source=cx.providers.CartoDB.Positron)
        ax_manzanas.set_title(f"Manzanas de la Localidad {st.session_state.nombre_localidad}\n(Seleccionada en rojo)")
        ax_manzanas.set_axis_off()
        plt.tight_layout()

        # Guardar en buffer para el informe
        buffer_manzanas = BytesIO()
        fig_manzanas.savefig(buffer_manzanas, format='png', bbox_inches='tight', dpi=150)
        st.session_state.buffer_manzanas = buffer_manzanas

    # --- 2. Generación del Informe HTML ---
    # Esta parte del código es principalmente la misma, ya que solo consume los buffers
    # de imagen que hemos ido guardando en st.session_state.
    with st.spinner('📝 Generando informe HTML...'):
        # Cargar datos necesarios del estado de la sesión
        manzana_id = st.session_state.manzana_sel
        manzana_sel = st.session_state.manzanas_localidad_sel[
            st.session_state.manzanas_localidad_sel["id_manzana_unif"] == manzana_id
        ]

        if manzana_sel.empty:
            st.error("❌ No se encontró la información de la manzana. Por favor, reinicia el proceso.")
        else:
            # Todas tus variables de texto (texto0, texto1, ..., texto6) permanecen sin cambios.
            # ... (código para definir estrato, colegios, estaciones, etc.)
            # ... (código para definir texto0, texto1, etc.)
            
            # La función para codificar a Base64 no cambia
            def buffer_a_base64(buffer):
                buffer.seek(0)
                return base64.b64encode(buffer.read()).decode('utf-8')

            # Obtener todas las imágenes codificadas desde los buffers guardados
            img_colegios_base64 = buffer_a_base64(st.session_state.buffer_colegios)
            img_transporte_base64 = buffer_a_base64(st.session_state.buffer_transporte)
            img_distribucion_base64 = buffer_a_base64(st.session_state.buffer_dist_pot)
            img_valorm2_base64 = buffer_a_base64(st.session_state.buffer_valorm2)
            img_seguridad_base64 = buffer_a_base64(st.session_state.buffer_seguridad)
            img_proyeccion_base64 = buffer_a_base64(st.session_state.buffer_proyeccion)
            
            # La nueva imagen del mapa de manzanas
            img_manzanas_base64 = buffer_a_base64(st.session_state.buffer_manzanas)
            
            # (OJO: Asegúrate de tener un `buffer_localidad` guardado si quieres usarlo)
            # Para mantener la compatibilidad, podemos generar este mapa aquí también.
            # Creemos el mapa de la localidad aquí para no depender de bloques anteriores.
            fig_loc, ax_loc = plt.subplots(figsize=(10,8))
            localidades_mercator = st.session_state.localidades.to_crs(epsg=3857)
            localidades_mercator.plot(ax=ax_loc, edgecolor='black', color='lightgray')
            loc_actual_mercator = localidades_mercator[localidades_mercator['nombre_localidad'] == st.session_state.nombre_localidad]
            loc_actual_mercator.plot(ax=ax_loc, edgecolor='red', color='red', alpha=0.5)
            cx.add_basemap(ax_loc, crs=localidades_mercator.crs.to_string(), source=cx.providers.CartoDB.Positron)
            ax_loc.set_title(f"Ubicación de la Localidad: {st.session_state.nombre_localidad}")
            ax_loc.set_axis_off()
            buffer_localidad_final = BytesIO()
            fig_loc.savefig(buffer_localidad_final, format='png', bbox_inches='tight')
            img_localidad_base64 = buffer_a_base64(buffer_localidad_final)


            # La ficha estilizada no cambia
            html_ficha = st.session_state.ficha_estilizada.to_html(index=False, classes='dataframe')
            
            # El contenido del HTML no cambia, solo las variables de imagen que se le pasan
            titulo = "Informe de Análisis de Inversión Inmobiliaria"
            html_content = f"""
            <!DOCTYPE html> ... (tu HTML completo) ... </html>
            """
            # Asegúrate de que las variables de imagen como {img_manzanas_base64} estén en tu string HTML.
            
            st.session_state.informe_html = html_content

    st.success("✅ Informe generado correctamente con la nueva pila de visualización.")

    st.download_button(
        label="📥 Descargar Informe (HTML)",
        data=st.session_state.informe_html,
        file_name="Informe_Valorizacion_Inmobiliaria.html",
        mime="text/html"
    )

    # --- Navegación Final ---
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