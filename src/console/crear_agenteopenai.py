from agente_openai import AgenteOpenAI
import blobs
from dotenv import load_dotenv
import os
load_dotenv(dotenv_path=".env.local")
api_key = os.getenv("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")



client = AgenteOpenAI(api_key=api_key)
def mensaje_archivo_code_interpreter_sin_citas(thread_id,assistant_id,nombre_archivo,mensaje,path_archivo):
    return  client.mensaje_archivo_code_interpreter_sin_citas(thread_id,assistant_id,nombre_archivo,mensaje,path_archivo)     
def crear_recuperar_thread(user_mail,thread_name,json_usuario)->str:
    thread_id = client.get_or_create_thread(user_mail,thread_name,json_usuario)
    return thread_id
def actualizar_vectore_storage(vector_id,carpeta,nombre_archivo)->str:
    response=client.actualizar_vector_store(vector_id,carpeta,nombre_archivo)
    return response
def enviar_mensaje_vectore_storage(thread_id,assistant_id,vector_id,mensaje)->str:
    response=client.enviar_mensaje_vectore_storage(thread_id,assistant_id,mensaje,vector_id)
    return response
def crear_vector_archivo_y_subir_archivo(archivo,carpeta,nombre)->str:
    vector_store = client.crear_vector_archivo_y_subir_archivo(archivo,carpeta,nombre)
    return vector_store
def get_thread_messages(thread_id)->list:
        return  client.display_chat_history(thread_id)
def enviar_mensaje(thread_id, assistant_id, mensaje)->str:
    response=client.enviar_mensaje_sin_archivo(thread_id, assistant_id, mensaje)
    return response
def enviar_archivos(thread_id,assistant_id,archivos,mensaje)->str:
    response,vector_id=client.mensaje_archivos(thread_id,assistant_id,archivos,mensaje)
    return response,vector_id
def enviar_archivo_sin_citas(thread_id,assistant_id,archivo,mensaje,asinatura)->str:
    response,vector_id=client.mensaje_archivo_sin_citas(thread_id,assistant_id,archivo,mensaje,asinatura)
    return response,vector_id
def enviar_archivo(thread_id,assistant_id,archivo,mensaje,asinatura)->str:
    response,vector_id=client.mensaje_archivo(thread_id,assistant_id,archivo,mensaje,asinatura)
    return response,vector_id
def crear_asistente(Assistant_config)->str:
    nombre = Assistant_config["name"]
    instrucciones = Assistant_config["instructions"]
    modelo = Assistant_config["model"]
    assistant_id=client.crear_asistente_file_search( nombre, instrucciones, modelo)
    return assistant_id
def main(nombre,descproceso)->str:
    json_configuracion=blobs.cargar_conf("conf.json")
    instructions=blobs.lee_blob("promptsprocesos","desplegado/"+json_configuracion["instruciones_agent"])+"\n"+descproceso
    Customer_Service_Assistant = {
    "name":nombre,
    "instructions":instructions,
    "tools":[{"type": "file_search"}],
    "model":"gpt-4.1",
}
    assistant_id=  crear_asistente(Customer_Service_Assistant)
    
    return assistant_id
