import os
from pandasai import Agent
from pandasai_openai import OpenAI
import pandas as pd
import io
from io import BytesIO, StringIO
from azure.storage.blob import BlobServiceClient
from dotenv import load_dotenv
load_dotenv(dotenv_path=".env.local")
import pandasai as pai
import logging

pai.config.set({
   "save_logs": False,
   "verbose": False,
   "max_retries": 3
})

api_key = os.getenv("OPENAI_API_KEY")

def get_openai_api_key():
    """Obtiene la API Key desde una variable de entorno."""
    return os.getenv("OPENAI_API_KEY")

def get_azure_connection_string():
    """Obtiene la cadena de conexión de Azure desde una variable de entorno."""
    return os.getenv("AZURE_CONNECTION_STRING")

def descargar_archivo_bytesio(container_name, blob_name):
    """Descarga un archivo desde Azure Blob Storage y lo devuelve como BytesIO."""
    connection_string = get_azure_connection_string()
    if not connection_string:
        raise ValueError("Cadena de conexión de Azure no encontrada. Configura la variable de entorno AZURE_CONNECTION_STRING.")
    
    blob_service_client = BlobServiceClient.from_connection_string(connection_string)
    blob_client = blob_service_client.get_blob_client(container_name, blob_name)
    blob_data = blob_client.download_blob()
    return BytesIO(blob_data.readall())

def cargar_excel_desde_blob(container_name, blob_name, usecols=None):
    """Descarga y carga un archivo Excel desde Azure Blob Storage en un DataFrame de Pandas con columnas específicas."""
    bytes_io = descargar_archivo_bytesio(container_name, blob_name)
    return pd.read_excel(bytes_io, usecols=usecols)

def cargar_csv_metadatos(container_name="csvexcelscuadrodemandos", blob_name="registro_excel_cuadro_mandos.csv"):
    """Carga el CSV de metadatos desde Azure Blob Storage."""
    try:
        connection_string="DefaultEndpointsProtocol=https;AccountName=datosgptai;AccountKey=kXrHjAlAGfeijCq2FvHJdbCiZfLSBnFFTY7fYWxWHJVqxBtGiJeOgfen+2mQO8cChEGzHxeQpoc++ASt9h+FQg==;EndpointSuffix=core.windows.net"
        blob_service_client = BlobServiceClient.from_connection_string(connection_string)
        container_client = blob_service_client.get_container_client(container_name)
        blob_client = container_client.get_blob_client(blob_name)
        blob_data = blob_client.download_blob()
        csv_content = blob_data.readall().decode('utf-8')
        df_metadatos = pd.read_csv(io.StringIO(csv_content), encoding='utf-8', sep=";")
        return df_metadatos
    except Exception as e:
        logging.error(f"Error al cargar el CSV de metadatos: {str(e)}")
        raise

