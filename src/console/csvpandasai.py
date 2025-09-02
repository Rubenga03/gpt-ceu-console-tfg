import os
import pandasai as pai
import pandas as pd
import io
from dotenv import load_dotenv
import logging
import json
import openai

# Cargar variables de entorno
load_dotenv()

def transformar_input(texto):
    """Transforma el texto de entrada en un formato limpio."""
    try:
        texto_limpio = texto.strip().replace("\n", " ").replace("\r", "")
        logging.info(f"Input transformado: {texto_limpio[:50]}...")
        return texto_limpio
    except Exception as e:
        logging.error(f"Error en transformar_input: {e}")
        return texto

def transformar_a_json(respuesta_html, api_key):
    """Transforma una respuesta HTML o texto a formato JSON usando OpenAI."""
    try:
        client = openai.OpenAI(api_key=api_key)
        prompt = (
            "Convierte el siguiente texto (que puede ser HTML o texto plano) en un objeto JSON. "
            "Si es una tabla HTML, extrae los datos en un formato estructurado con claves 'columns' y 'data'. "
            "Si es texto plano, devuélvelo como un objeto con una clave 'text'. "
            f"Texto: {respuesta_html}"
        )
        response = client.chat.completions.create(
            model="gpt-4.1-mini",
            messages=[{"role": "user", "content": prompt}],
            max_tokens=1000
        )
        json_str = response.choices[0].message.content.strip()
        logging.info(f"Respuesta JSON generada: {json_str[:100]}...")
        return json_str
    except Exception as e:
        logging.error(f"Error en transformar_a_json: {e}")
        return json.dumps({"error": str(e)})

def resumir_consulta(consulta, api_key):
    """Resume la consulta del usuario usando OpenAI."""
    try:
        client = openai.OpenAI(api_key=api_key)
        prompt = f"Resume la siguiente consulta en una frase corta: {consulta}"
        response = client.chat.completions.create(
            model="gpt-4.1-mini",
            messages=[{"role": "user", "content": prompt}],
            max_tokens=50
        )
        resumen = response.choices[0].message.content.strip()
        logging.info(f"Consulta resumida: {resumen}")
        return resumen
    except Exception as e:
        logging.error(f"Error en resumir_consulta: {e}")
        return "Resumen no disponible"

def determinar_tipo_grafico(consulta, api_key):
    """Determina el tipo de gráfico adecuado para la consulta."""
    try:
        client = openai.OpenAI(api_key=api_key)
        prompt = (
            "Dada la siguiente consulta, determina el tipo de gráfico más adecuado (por ejemplo, 'bar', 'line', 'pie', 'scatter', 'None'): "
            f"{consulta}"
        )
        response = client.chat.completions.create(
            model="gpt-4.1-mini",
            messages=[{"role": "user", "content": prompt}],
            max_tokens=20
        )
        tipo = response.choices[0].message.content.strip()
        logging.info(f"Tipo de gráfico determinado: {tipo}")
        return tipo
    except Exception as e:
        logging.error(f"Error en determinar_tipo_grafico: {e}")
        return "None"

def generar_titulo_grafico(consulta, api_key):
    """Genera un título para el gráfico basado en la consulta."""
    try:
        client = openai.OpenAI(api_key=api_key)
        prompt = f"Genera un título conciso y descriptivo para un gráfico basado en esta consulta: {consulta}"
        response = client.chat.completions.create(
            model="gpt-4.1-mini",
            messages=[{"role": "user", "content": prompt}],
            max_tokens=50
        )
        titulo = response.choices[0].message.content.strip()
        logging.info(f"Título generado: {titulo}")
        return titulo
    except Exception as e:
        logging.error(f"Error en generar_titulo_grafico: {e}")
        return "Sin título"

def decidir_grafico_conjunto(consulta, api_key):
    """Decide si se debe generar un gráfico conjunto para múltiples datasets."""
    try:
        client = openai.OpenAI(api_key=api_key)
        prompt = (
            "Dada esta consulta, decide si requiere un gráfico conjunto para múltiples datasets "
            "(responde 'True' o 'False'): {consulta}"
        )
        response = client.chat.completions.create(
            model="gpt-4.1-mini",
            messages=[{"role": "user", "content": prompt}],
            max_tokens=10
        )
        decision = response.choices[0].message.content.strip() == "True"
        logging.info(f"Gráfico conjunto: {decision}")
        return decision
    except Exception as e:
        logging.error(f"Error en decidir_grafico_conjunto: {e}")
        return False

def seleccionar_archivos_y_columnas_con_openai(consulta, df_metadatos, api_key):
    """Selecciona archivos, columnas y filtros relevantes para la consulta usando OpenAI."""
    try:
        client = openai.OpenAI(api_key=api_key)
        metadatos_str = df_metadatos.to_string()
        prompt = f"""
        <CONTEXTO>
        Eres un asistente encargado de seleccionar los archivos, las columnas necesarias (incluyendo las necesarias para cualquier condición de filtro) y, si aplica, una condición de filtro para las filas, del apartado <ARCHIVOS/> que mejor encajen para resolver la consulta. Devuelve los nombres de los archivos, las columnas relevantes y la condición de filtro (si necesario) en el siguiente formato: "archivo1.csv: columna1, columna2; filter: condition". Si no hay condición de filtro, omite la parte del filter.
        Puedes poner filtros a partir de las columnas que se te proporcionan, por ejemplo si una columna es "year" puedes poner un filtro como "year == 2023", basándote en la consulta. Para filtrar por el nombre de la titulacion/estudio, tienes que incluir "Grado en", por ejemplo, si se pregunta por la tasa de rendimiento de Medicina en 2023, tienes que poner que year=2023, y que Titulacion= Grado en Medicina. Si no hay columnas que puedan ser filtradas, omite la parte del filter.
        No incluyas filtros referentes a Doble Grados, ya que no se pueden filtrar por ellos. No incluyas nada acerca de ello.
        Utiliza únicamente los símbolos "==", "<", "!=" o ">". 
        No añadas ni quites tildes.
    
        </CONTEXTO>
        
        <OBJETIVO>
        Tu objetivo es seleccionar los archivos, las columnas (incluyendo las necesarias para el filtro) y una condición de filtro (si aplica) que contengan los datos necesarios para resolver la consulta del usuario: {consulta}.
        </OBJETIVO>
        
        <ARCHIVOS>
        Aquí tienes una lista de los archivos con sus descripciones y columnas:
        {metadatos_str}
        </ARCHIVOS>
        """
        response = client.chat.completions.create(
            model="gpt-4.1-mini",
            messages=[{"role": "user", "content": prompt}],
            max_tokens=200
        )
        respuesta = response.choices[0].message.content.strip()
        
        archivos_columnas_filtros = {}
        for parte in respuesta.split("\n"):
            if ":" in parte:
                archivo_part, resto = parte.split(":", 1)
                archivo = archivo_part.strip()
                if "filter:" in resto:
                    columnas_str, filter_str = resto.split("filter:", 1)
                    columnas = [col.strip().rstrip(';') for col in columnas_str.split(",") if col.strip()]
                    filter_condition = filter_str.strip()
                else:
                    columnas_str = resto
                    columnas = [col.strip().rstrip(';') for col in columnas_str.split(",") if col.strip()]
                    filter_condition = None
                archivos_columnas_filtros[archivo] = {"columns": columnas, "filter": filter_condition}
        logging.info(f"Archivos, columnas y filtros seleccionados por OpenAI: {archivos_columnas_filtros}")
        return archivos_columnas_filtros
    except Exception as e:
        logging.error(f"Error en seleccionar_archivos_y_columnas_con_openai: {e}")
        return {}
    

    
