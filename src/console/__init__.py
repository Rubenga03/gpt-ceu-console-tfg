import azure.functions as func
import logging
import json
import os
from dotenv import load_dotenv
import pandasai as pai
from pandasai_openai import OpenAI
import pandas as pd
import crear_agenteopenai as openai_agent
from csvpandasai import resumir_consulta, generar_titulo_grafico, seleccionar_archivos_y_columnas_con_openai
import azuredatapandasai as AzData
from pandasai_litellm import LiteLLM
import re

# ───────────────────────────────────────────────────────────────────────────────
# 1) Cargar variables de entorno
load_dotenv(dotenv_path="/home/site/wwwroot/.env.local")

# 2) Determinar ruta base (la carpeta donde está este __init__.py)
BASE_DIR = os.path.dirname(__file__)

# 3) Leer prompt.txt **antes** de cambiar de cwd
def load_prompt():
    prompt_path = os.path.join(BASE_DIR, "prompt.txt")
    try:
        with open(prompt_path, "r", encoding="utf-8") as f:
            contenido = f.read()
            logging.info(f"PROMPT cargado correctamente ({len(contenido)} caracteres).")
            return contenido
    except Exception as e:
        logging.error(f"Error al cargar el prompt desde {prompt_path}: {e}")
        return ""

PROMPT = load_prompt()

# 4) Cambiar cwd a /tmp para procesar data
os.chdir('/tmp')

# 5) ID de tu asistente (si ya lo tienes creado)
ASSISTANT_ID = "ASSISTANT_ID"  # Reemplaza con tu ID real

# Función para crear el asistente (ejecutar una vez manualmente)
def initialize_assistant():
    global ASSISTANT_ID
    if not ASSISTANT_ID:
        ASSISTANT_ID = openai_agent.main("Asistente de Análisis de Datos", PROMPT)
        logging.info(f"Asistente creado con ID: {ASSISTANT_ID}")
    return ASSISTANT_ID

# Diccionario para almacenar el último template por thread
ultimo_template_por_thread = {}

def buscar_respuesta_previa(id_thread, consulta):
    """Busca una respuesta previa en el historial del thread"""
    try:
        messages = openai_agent.get_thread_messages(id_thread)
        for message in reversed(messages):
            if "Por favor, almacena esta respuesta:" in message:
                try:
                    json_str = re.search(r'```json\n(.*?)\n```', message, re.DOTALL).group(1)
                    respuesta_previa = json.loads(json_str)
                    if respuesta_previa["consulta"] == consulta:
                        logging.info(f"Respuesta previa encontrada para consulta: {consulta}")
                        return respuesta_previa
                except Exception as e:
                    logging.debug(f"Error al parsear mensaje del historial: {e}")
                    continue
        logging.warning(f"No se encontró respuesta previa para la consulta: {consulta}")
        return None
    except Exception as e:
        logging.error(f"Error al buscar en el historial: {e}")
        return None

def main(req: func.HttpRequest) -> func.HttpResponse:
    logging.info('Python HTTP trigger function processed a request.')

    try:
        # ─────────────── Obtener parámetros de la solicitud ──────────────────────
        user_input = req.params.get('user_input')
        user_email = req.params.get('user_email')
        id_thread = req.params.get('id_thread')
        logging.info(f"Parámetros obtenidos: user_input={user_input}, user_email={user_email}, id_thread={id_thread}")

        if not user_input:
            try:
                req_body = req.get_json()
                user_input = req_body.get('user_input')
                id_thread = req_body.get('id_thread')
                user_email = req_body.get('user_email')
                logging.info(f"Parámetros desde JSON: user_input={user_input}, user_email={user_email}, id_thread={id_thread}")
            except ValueError:
                logging.warning("No se pudo parsear el cuerpo JSON.")

        if not user_input:
            logging.info("Falta 'user_input'. Devolviendo mensaje.")
            return func.HttpResponse(
                json.dumps({"message": "Pasa 'user_input' en la query string o en el cuerpo de la solicitud."}),
                status_code=200,
                mimetype="application/json"
            )

        if not user_email:
            logging.info("Falta 'user_email'. Devolviendo error.")
            return func.HttpResponse(
                json.dumps({"error": "El parámetro 'user_email' es obligatorio."}),
                status_code=400,
                mimetype="application/json"
            )

        # ─── Inicializar el asistente si no está creado ────────────────────────────
        initialize_assistant()
        logging.info(f"Usando ASSISTANT_ID: {ASSISTANT_ID}")

        # ─── Crear o recuperar thread automáticamente si no se proporciona ─────────
        if not id_thread:
            logging.info("Creando o recuperando thread.")
            id_thread = openai_agent.crear_recuperar_thread(user_email, "Análisis de Datos", None)
            logging.info(f"Thread creado o recuperado para {user_email}: {id_thread}")
        else:
            logging.info(f"Usando thread proporcionado: {id_thread}")

        # ─── Obtener historial de mensajes del thread ───────────────────────────────
        messages = openai_agent.get_thread_messages(id_thread)
        logging.info(f"Mensajes en el thread: {len(messages)}")

        # ─── Recuperar el último template usado en este thread (si existe) ─────────
        ultimo_template = ultimo_template_por_thread.get(id_thread, None)
        logging.info(f"Último template recuperado para thread {id_thread}: {ultimo_template}")

        # ─── Enviar la consulta al asistente con contexto del último template ──────
        mensaje_enviado = f"{PROMPT}\nÚltimo template usado: {ultimo_template or 'Ninguno'}\n<CONSULTA_USUARIO>\n{user_input}\n</CONSULTA_USUARIO>"
        logging.info(f"Enviando mensaje al asistente: {mensaje_enviado}")
        response = openai_agent.enviar_mensaje(id_thread, ASSISTANT_ID, mensaje_enviado)
        logging.info(f"Respuesta cruda del asistente: {response}")

        # ─── Parsear la respuesta del asistente ────────────────────────────────
        try:
            assistant_response = json.loads(response)
            logging.info(f"Respuesta parseada del asistente: {assistant_response}")
            if "respuesta_previa" in assistant_response:
                respuestas_usuario = assistant_response["respuesta_previa"]
                logging.info(f"Reutilizando respuesta previa para la consulta: {user_input}")
            else:
                consultas = assistant_response.get("respuesta_usuario", [])
                logging.info(f"Generando nueva respuesta para la consulta: {user_input}")
        except json.JSONDecodeError as e:
            logging.error(f"Error al parsear la respuesta del asistente: {response} - {e}")
            return func.HttpResponse(
                json.dumps({"error": "Error al procesar la respuesta del asistente."}),
                status_code=500,
                mimetype="application/json"
            )

        # ─── Procesar nuevas consultas si no hay respuesta previa ──────────────────
        if "respuesta_previa" not in assistant_response:
            # ─── Cargar CSV de metadatos ───────────────────────────────────────────
            logging.info("Cargando CSV de metadatos.")
            df_metadatos = AzData.cargar_csv_metadatos()
            logging.info(f"Metadatos cargados: {df_metadatos.shape}")

            # ─── Configurar LLM de PandasAI (solo para consultas que lo requieran) ────
            api_key = AzData.get_openai_api_key()
            if not api_key:
                logging.error("API Key de OpenAI no encontrada.")
                return func.HttpResponse(
                    json.dumps({"error": "API Key de OpenAI no encontrada."}),
                    status_code=500,
                    mimetype="application/json"
                )
            llm = LiteLLM(model="o3-mini")
            pai.config.set({"llm": llm})
            logging.info("LLM de PandasAI configurado.")

            # ─── Procesar las consultas ────────────────────────────────────────────
            respuestas_usuario = []
            MAX_RETRIES = 10
            for item in consultas:
                consulta = item["consulta"]
                tipo_grafico = item["tipo_grafico"]
                template = item.get("template", "False")
                respuesta = item.get("respuesta", "")
                respuesta_corta = item.get("respuesta_corta", "")
                logging.info(f"Procesando consulta: {consulta}, tipo_grafico: {tipo_grafico}, template: {template}")

                # Si la respuesta ya viene completa del asistente (tasas de centros/titulaciones)
                if respuesta and respuesta_corta:
                    logging.info(f"Respuesta directa del asistente para consulta: {consulta}")
                    consulta_resumida = item.get("consulta_resumida", resumir_consulta(consulta, api_key))
                    titulo_grafico_item = item.get("titulo_grafico", generar_titulo_grafico(consulta, api_key))
                    grafico_conjunto = item.get("grafico_conjunto", False)

                    respuesta_completa = {
                        "consulta": consulta,
                        "respuesta": respuesta,
                        "respuesta_corta": respuesta_corta,
                        "consulta_resumida": consulta_resumida,
                        "tipo_grafico": tipo_grafico,
                        "titulo_grafico": titulo_grafico_item,
                        "grafico_conjunto": grafico_conjunto,
                        "template": template
                    }
                    respuestas_usuario.append(respuesta_completa)

                    # Almacenar la respuesta en el thread
                    json_completo = json.dumps(respuesta_completa, ensure_ascii=False)
                    mensaje_almacenamiento = f"Por favor, almacena esta respuesta: ```json\n{json_completo}\n```"
                    openai_agent.enviar_mensaje(id_thread, ASSISTANT_ID, mensaje_almacenamiento)
                    logging.info(f"Respuesta almacenada en el thread para consulta: {consulta}")
                    continue

                # Si no hay respuesta directa, procesar con PandasAI
                archivos_columnas = seleccionar_archivos_y_columnas_con_openai(consulta, df_metadatos, api_key)
                logging.info(f"Archivos y columnas seleccionados para '{consulta}': {archivos_columnas}")

                if not archivos_columnas:
                    logging.info("No se encontraron archivos relevantes.")
                    respuestas_usuario.append({
                        "consulta": consulta,
                        "respuesta": "No se encontraron archivos relevantes para la consulta.",
                        "respuesta_corta": json.dumps({"error": "No hay archivos relevantes"}, ensure_ascii=False),
                        "consulta_resumida": "No hay datos",
                        "tipo_grafico": "None",
                        "titulo_grafico": "Sin título",
                        "grafico_conjunto": False,
                        "template": template
                    })
                    continue

                dataframes = cargar_dataframes("becaai", archivos_columnas)
                if not dataframes:
                    logging.info("No se pudieron cargar los archivos seleccionados.")
                    respuestas_usuario.append({
                        "consulta": consulta,
                        "respuesta": "No se pudieron cargar los archivos seleccionados.",
                        "respuesta_corta": json.dumps({"error": "Error al cargar archivos"}, ensure_ascii=False),
                        "consulta_resumida": "Error de carga",
                        "tipo_grafico": "None",
                        "titulo_grafico": "Sin título",
                        "grafico_conjunto": False,
                        "template": template
                    })
                    continue

                sdfs = {}
                for archivo, df in dataframes.items():
                    descripcion_series = df_metadatos.loc[df_metadatos['NombreArchivo'] == archivo, 'Descripcion']
                    descripcion = descripcion_series.iloc[0] if not descripcion_series.empty else "Sin descripción"
                    sdfs[archivo] = pai.DataFrame(df, config={"llm": llm, "description": descripcion})
                    logging.info(f"SmartDataframe creado para {archivo}")

                try:
                    logging.info(f"Ejecutando PandasAI para la consulta: {consulta}")
                    response_normal = None
                    for attempt in range(MAX_RETRIES):
                        response_normal = pai.chat(consulta, *sdfs.values())
                        response_str = str(response_normal)
                        if isinstance(response_normal, pd.DataFrame) and response_normal.empty or "Empty DataFrame" in response_str or "Error" in response_str or "Required" in response_str or "keyword" in response_str or "Invalid" in response_str:
                            logging.warning(f"Intento {attempt + 1}: DataFrame vacío para la consulta: {consulta}")
                            continue
                        else:
                            break
                    else:
                        logging.error(f"Después de {MAX_RETRIES} intentos, aún se obtiene un DataFrame vacío para la consulta: {consulta}")
                        response_normal_str = "No se encontraron datos para la consulta."
                        respuesta_corta = json.dumps({"error": "No se encontraron datos"}, ensure_ascii=False)
                        respuestas_usuario.append({
                            "consulta": consulta,
                            "respuesta": response_normal_str,
                            "respuesta_corta": respuesta_corta,
                            "consulta_resumida": "No hay datos",
                            "tipo_grafico": "None",
                            "titulo_grafico": "Sin título",
                            "grafico_conjunto": False,
                            "template": template
                        })
                        continue

                    if isinstance(response_normal, (pd.DataFrame, pd.Series)):
                        response_normal_str = response_normal.to_csv(max_rows=None, max_cols=None)
                    else:
                        response_normal_str = str(response_normal)
                    logging.info(f"Respuesta de PandasAI: {response_normal_str}")

                    mensaje_tasas = f"""
                    Convierte la siguiente respuesta generada por PandasAI en un formato JSON estructurado según las reglas especificadas:
                    - Si es un archivo CSV, extrae los datos en una lista de objetos bajo la clave "data".
                    - Si es un número, usa la clave que consideres oportuna por el contexto, y si no tienes contexto, usa "result".
                    - Si es texto plano, interprétalo para crear un JSON clave-valor.
                    - Para datos de tasas académicas, usa claves como "asignatura", "tasa_rendimiento", "tasa_exito", "any_academico", etc.
                    - Si el valor de una de las tasas es 0, no debe aparecer en el JSON respuesta.
                    - Si una asignatura no aparece en todos los años académicos (2021, 2022, 2023), no debe aparecer en el JSON respuesta.
                    - Asegúrate de que los nombres de los campos estén entre comillas dobles y en castellano.
                    - Cuando representes números, represéntalos con 2 decimales como máximo, redondea si es necesario.
                    - Responde solo con el JSON, sin texto adicional.
                    Respuesta de PandasAI:
                    {response_normal_str}
                    """

                    mensaje_matriculados = f"""
                    Convierte la siguiente respuesta generada por PandasAI en un formato JSON estructurado según las reglas especificadas:
                    - Si es un archivo CSV, extrae los datos en una lista de objetos bajo la clave "data".
                    - Si es un número, usa la clave que consideres oportuna por el contexto, y si no tienes contexto, usa "result".
                    - Si es texto plano, interprétalo para crear un JSON clave-valor.
                    - Para datos de estudiantes de nuevo ingreso, usa la clave "total_nuevo_ingreso".
                    - Para datos de estudiantes matriculados por campus, usa las claves "campus" y "total_matriculados".
                    - Asegúrate de que los nombres de los campos estén entre comillas dobles y en castellano.
                    - Responde solo con el JSON, sin texto adicional.
                    Respuesta de PandasAI:
                    {response_normal_str}
                    """

                    mensaje_general = f"""
                    Convierte la siguiente respuesta generada por PandasAI en un formato JSON estructurado según las reglas especificadas:
                    - Si es un archivo CSV, extrae los datos en una lista de objetos bajo la clave "data".
                    - Si es un número, usa la clave que consideres oportuna por el contexto, y si no tienes contexto, usa "result".
                    - Si es texto plano, interprétalo para crear un JSON clave-valor.
                    - Asegúrate de que los nombres de los campos estén entre comillas dobles y en castellano.
                    - Responde solo con el JSON, sin texto adicional.
                    Respuesta de PandasAI:
                    {response_normal_str}
                    """

                    if template == "Tasas":
                        mensaje_para_asistente = mensaje_tasas
                    elif template == "Matriculados":
                        mensaje_para_asistente = mensaje_matriculados
                    else:
                        mensaje_para_asistente = mensaje_general

                    logging.info(f"Enviando mensaje al asistente para respuesta_corta: {mensaje_para_asistente}")
                    respuesta_asistente = openai_agent.enviar_mensaje(id_thread, ASSISTANT_ID, mensaje_para_asistente)

                    try:
                        respuesta_json = json.loads(respuesta_asistente.strip())
                        if "data" in respuesta_json:
                            # Si la clave "data" existe, usamos directamente su contenido (la lista)
                            respuesta_corta = respuesta_json["data"]
                        else:
                            respuesta_corta = respuesta_json
                        logging.info(f"Respuesta corta generada: {respuesta_corta}")
                    except json.JSONDecodeError as e:
                        logging.error(f"Error al parsear la respuesta del asistente: {e}. Respuesta cruda: {respuesta_asistente}")
                        respuesta_corta = {"error": "No se pudo generar respuesta_corta"}

                    consulta_resumida = item.get("consulta_resumida", resumir_consulta(consulta, api_key))
                    titulo_grafico = item.get("titulo_grafico", generar_titulo_grafico(consulta, api_key))
                    grafico_conjunto = item.get("grafico_conjunto", False)

                    respuesta_completa = {
                        "consulta": consulta,
                        "respuesta": response_normal_str,
                        "respuesta_corta": respuesta_corta,
                        "consulta_resumida": consulta_resumida,
                        "tipo_grafico": tipo_grafico,
                        "titulo_grafico": titulo_grafico,
                        "grafico_conjunto": grafico_conjunto,
                        "template": template
                    }
                    respuestas_usuario.append(respuesta_completa)

                    json_completo = json.dumps(respuesta_completa, ensure_ascii=False)
                    mensaje_almacenamiento = f"Por favor, almacena esta respuesta: ```json\n{json_completo}\n```"
                    openai_agent.enviar_mensaje(id_thread, ASSISTANT_ID, mensaje_almacenamiento)
                    logging.info(f"Respuesta almacenada en el thread para consulta: {consulta}")

                except Exception as e:
                    logging.error(f"Error al procesar la consulta {consulta}: {e}")
                    respuestas_usuario.append({
                        "consulta": consulta,
                        "respuesta": f"Error al procesar la consulta: {str(e)}",
                        "respuesta_corta": json.dumps({"error": "Error de procesamiento"}, ensure_ascii=False),
                        "consulta_resumida": "Error",
                        "tipo_grafico": "None",
                        "titulo_grafico": "Sin título",
                        "grafico_conjunto": False,
                        "template": template
                    })

            # ─── Actualizar el último template usado ───────────────────────────────
            if consultas:
                template_usado = consultas[0].get("template", "False")
                if template_usado != "False":
                    ultimo_template_por_thread[id_thread] = template_usado
                    logging.info(f"Actualizado último template para thread {id_thread}: {template_usado}")

        # ─── Construir respuesta final ─────────────────────────────────────────────
        respuesta_final = {
            "id_thread": id_thread,
            "respuesta_usuario": respuestas_usuario,
            "mensajes_previos": messages,
            "metadata": assistant_response.get("metadata", {})
        }
        logging.info(f"Respuesta final generada con {len(respuestas_usuario)} respuestas.")

        return func.HttpResponse(
            json.dumps(respuesta_final, ensure_ascii=False),
            status_code=200,
            mimetype="application/json"
        )

    except Exception as e:
        logging.error(f"Error general en la ejecución: {e}")
        return func.HttpResponse(
            json.dumps({"error": f"Error en el servidor: {str(e)}"}),
            status_code=500,
            mimetype="application/json"
        )

# Función adicional para cargar DataFrames con columnas específicas
import logging
import pandas as pd
import azuredatapandasai as AzData

# Configurar el logging (si no está configurado globalmente)
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

import logging
import pandas as pd
import unicodedata
import pandas as pd
import logging



import logging
import re
import pandas as pd
import unicodedata

import logging
import re
import pandas as pd
import unicodedata

import logging
import re
import pandas as pd
import unicodedata
from io import BytesIO
from openpyxl import load_workbook
import azuredatapandasai as AzData  # tu módulo de utilidades

def _normalize(s: str) -> str:
    """Quita tildes y diacríticos de un string, para matching."""
    return unicodedata.normalize("NFKD", s)\
                      .encode("ascii", "ignore")\
                      .decode("ascii")

def cargar_dataframes(container_name, archivos_columnas_filtros):
    """
    Carga DataFrames desde Azure Blob Storage respetando merged cells en 'Curso',
    aplica filtros insensibles a tildes y sanea la condición para DataFrame.query().
    """
    dataframes = {}

    for archivo, info in archivos_columnas_filtros.items():
        wanted_cols = info["columns"]
        raw_filter  = info.get("filter", "").strip()

        try:
            # ── 1) Descargar el blob y cargar workbook con openpyxl ──
            logging.info(f"🗂️  Descargando y leyendo '{archivo}' íntegro para merged cells")
            bytes_io = AzData.descargar_archivo_bytesio(container_name, archivo)
            wb       = load_workbook(filename=BytesIO(bytes_io.read()), data_only=True)
            sheet    = wb.active

            # ── 2) Extraer valores de la hoja en DataFrame completo ──
            rows     = list(sheet.values)
            headers  = rows[0]
            df_full  = pd.DataFrame(rows[1:], columns=headers)
            logging.info(f"   → Hoja completa: shape={df_full.shape}, cols={list(df_full.columns)}")

            # ── 3) Propagar merged cells en 'Curso' antes de recortar columnas ──
            if "Curso" in df_full.columns:
                before_na = df_full["Curso"].isna().sum()
                df_full["Curso"] = (
                    df_full["Curso"]
                    .replace("XX", pd.NA)       # tratar "XX" como NaN
                    .bfill()                     # llenar hacia arriba
                    .ffill()                     # luego hacia abajo
                )
                after_na = df_full["Curso"].isna().sum()
                logging.info(
                    f"   ↳ 'Curso' tras bfill+ffill: nulos {before_na}→{after_na}"
                )

            # ── 4) Seleccionar sólo las columnas que necesitas ──
            df = df_full[wanted_cols].copy()
            logging.info(f"   → Subset columns: shape={df.shape}, cols={list(df.columns)}")

            # ── 5) Normalizar espacios en texto ──
            for c in wanted_cols:
                if c in df.columns and df[c].dtype == object:
                    df[c] = df[c].str.strip()

            # ── 6) Si hay filtro, envolver nombres y aplicar ──
            if raw_filter:
                # a) Mapear columnas y envolver en backticks
                col_map = {}
                for c in wanted_cols:
                    norm = _normalize(c)
                    col_map[c] = c
                    if norm != c:
                        col_map[norm] = c

                cond = raw_filter
                for key in sorted(col_map, key=lambda k: -len(k)):
                    cond = cond.replace(key, f"`{col_map[key]}`")
                logging.info(f"   → Filtro raw con backticks: {cond}")

                # b) Log values únicos antes de filtrar
                mencionadas = set(re.findall(r'`([^`]+)`', cond))
                for col in mencionadas:
                    if col in df.columns:
                        uniques = df[col].dropna().unique()
                        logging.info(
                            f"   → Únicos en '{col}': {uniques[:5]}{'...' if len(uniques)>5 else ''}"
                        )

                # c) Saneamiento de literales según dtype
                cond = cond.replace(",", " and ")
                parts = [p.strip() for p in cond.split(" and ")]
                clean = []
                for p in parts:
                    m = re.match(r"^(`[^`]+`)\s*(==|!=)\s*(.+)$", p)
                    if m:
                        col_bt, op, val = m.groups()
                        val = val.strip()
                        col_name = col_bt.strip('`')
                        is_num   = pd.api.types.is_numeric_dtype(df[col_name])
                        if val.startswith('"') and val.endswith('"'):
                            safe = val
                        else:
                            if is_num and re.fullmatch(r"[-+]?\d+(\.\d+)?", val):
                                safe = val
                            else:
                                safe = f'"{val}"'
                        clean.append(f"{col_bt} {op} {safe}")
                    else:
                        clean.append(p)
                cond_final = " and ".join(clean)
                logging.info(f"   → Condición final saneada: {cond_final}")

                # d) Aplicar query()
                try:
                    df = df.query(cond_final)
                    logging.info(f"      • Tras filtro: shape={df.shape}")
                except Exception as e:
                    logging.error(f"      ⚠️ Error en query '{cond_final}': {e}")

            # ── 7) Mostrar primeras filas finales ──
            logging.info(
                f"   → Primeras filas tras procesado:\n{df.head().to_string(index=False)}"
            )

            dataframes[archivo] = df

        except Exception as e:
            logging.error(f"❌ Error al procesar '{archivo}': {e}")

    return dataframes
