from openai import OpenAI
import blobs
import logging
import time
import os
import shutil

class AgenteOpenAI:
    def __init__(self, api_key):
        self.api_key = api_key
        self.assistant_id = None
        self.client = OpenAI(api_key=api_key,default_headers={"OpenAI-Beta": "assistants=v2"})
    def crear_asistente_file_search(self, nombre, instrucciones, modelo):
        assistant = self.client.beta.assistants.create(
        name=nombre,
        instructions=instrucciones,
        model=modelo,
        tools=[{"type": "file_search"}],
        )
    def get_or_create_thread(self,user_mail,thread_name,json_usuario)->str:
        """
        Get or create a thread of Messages/content.

        This function reads a JSON file to get the ID of an existing thread. If the thread ID is not found, a new thread is created
        using the `client.beta.threads.create()` method. The ID of the new thread is then returned.

        :return: The ID of the thread.
        :rtype: str
        """
        logging.info(f"thread_name: {thread_name}")
        try:
            
            thread_id = json_usuario.coger_el_thread_id(thread_name)
            if thread_id=="":
                thread = self.client.beta.threads.create()
                thread_id = thread.id
        except:
            thread_id=None

        if  thread_id == None:
            thread = self.client.beta.threads.create()
            thread_id = thread.id
            

        return thread_id

    def crear_vector_archivo_y_subir_archivo(self,archivo,carpeta,nombre)->str:
        
        vector_store = self.client.beta.vector_stores.create(name=nombre)
        archivo= blobs.descargar_archivo_blob("pdfsceu/"+carpeta,archivo)
        
 
        # Ready the files for upload to OpenAI 
        file_paths = [archivo]
        file_streams = [open(path, "rb") for path in file_paths]
        file_batch =self.client.vector_stores.file_batches.upload_and_poll(
        vector_store_id=vector_store.id, files=file_streams
        )
        self.client.vector_stores.update(
                vector_store_id=vector_store.id,
               expires_after={
	    "anchor": "last_active_at",
	    "days": 365
        }
            )
        return vector_store.id

    def mensaje_archivo_code_interpreter_sin_citas(self,thread_id,assistant_id,nombre_archivo,mensaje,path_archivo):
        # Descargar el archivo del blob y subirlo al thread al crear el mensaje
        archivo = blobs.descargar_archivo_blob(path_archivo, nombre_archivo)
    
        # Preparar el archivo para subirlo a OpenAI
        file_path = archivo
        file = self.client.files.create(
            file=open(file_path, "rb"),
            purpose="assistants"
        )
    
        # Crear un mensaje con el archivo adjunto y la herramienta de búsqueda de archivos
        message = self.client.beta.threads.messages.create(
            thread_id=thread_id,
            role="user",
            content=mensaje,
            attachments=[
                {
                    "file_id": file.id,
                    "tools": [{"type": "code_interpreter"}]
                }
            ]
        )
    
        # Crear y esperar a que el run esté en estado terminal
        run = self.client.beta.threads.runs.create_and_poll(
            thread_id=thread_id,
            assistant_id=assistant_id
        )
    
        logging.info(f"file_path: {file_path}")

    
        # Obtener el vector store ID del thread
        thread = self.client.beta.threads.retrieve(thread_id=thread_id)
        vector_id = thread.tool_resources.code_interpreter.file_ids
        logging.info(f"vector_id: {vector_id}")
        # Recuperar los mensajes asociados al run
        messages = list(self.client.beta.threads.messages.list(thread_id=thread_id, run_id=run.id))
        self.eliminar_carpeta_temporalarch(file_path)
        # Procesar la respuesta del asistente para eliminar las citas
        for message in messages:
            if message.role == "assistant":
                message_content = message.content[0].text
                annotations = message_content.annotations
                citations = []
                for index, annotation in enumerate(annotations):
                    # Reemplazar el texto de la cita en el mensaje por un marcador vacío
                    message_content.value = message_content.value.replace(annotation.text, "")
                    if file_citation := getattr(annotation, "file_citation", None):
                        cited_file = self.client.files.retrieve(file_citation.file_id)
                        citations.append(f"[{index}] {cited_file.filename}")
                respuesta = message_content.value.strip()
                return respuesta, vector_id

        return None, 0
    def eliminar_carpeta_temporalarch(self,ruta_carpeta):
        directorio = os.path.dirname(ruta_carpeta)
        # Verificar si el directorio existe y eliminarlo con shutil.rmtree()
        if os.path.exists(directorio):
            shutil.rmtree(directorio)
    def mensaje_archivos(self, thread_id, assistant_id, correos, mensaje) -> str:
        # Descargar los archivos del blob y preparar las rutas locales
        archivos = []
        for correo in correos:
            archivos.append(blobs.descargar_archivo_blob("pdfsceu",f"AsignacionBecas/{correo}.pdf"))
        archivos_locales = archivos
 
        # Preparar los archivos para subir a OpenAI
        attachments = []
        try:
            for archivo_local in archivos_locales:
                with open(archivo_local, "rb") as file_stream:
                    file = self.client.files.create(file=file_stream, purpose="assistants")
                    attachments.append({
                    "file_id": file.id,
                    "tools": [{"type": "file_search"}]
                })
 
        # Crear el mensaje con los archivos adjuntos
            message = self.client.beta.threads.messages.create(
                thread_id=thread_id, role="user", content=mensaje, attachments=attachments
            )
 
        # Iniciar el proceso de ejecución en el thread
            self.client.beta.threads.runs.create_and_poll(
                thread_id=thread_id, assistant_id=assistant_id
            )
 
            # Eliminar los archivos temporales
            for archivo_local in archivos_locales:
                self.eliminar_carpeta_temporalarch(archivo_local)
 
        # Obtener el vector store ID del thread
            thread = self.client.beta.threads.retrieve(thread_id=thread_id)
            vector_id = thread.tool_resources.file_search.vector_store_ids[0]
 
        # Obtener la respuesta más reciente del asistente
            response = self.client.beta.threads.messages.list(thread_id=thread_id)
            for message in response.data:
                if message.role == "assistant":
                    respuesta = message.content[0].text.value
                    return respuesta, vector_id
        except Exception as e:
            logging.error(f"Error al procesar los archivos: {e}")
        return None, 0
    def mensaje_archivo_sin_citas(self,thread_id,assistant_id,archivo,mensaje,asinatura):
        # Descargar el archivo del blob y subirlo al thread al crear el mensaje
        archivo = blobs.descargar_archivo_blob(asinatura, archivo)
    
        # Preparar el archivo para subirlo a OpenAI
        file_path = archivo
        file = self.client.files.create(
            file=open(file_path, "rb"),
            purpose="assistants"
        )
    
        # Crear un mensaje con el archivo adjunto y la herramienta de búsqueda de archivos
        message = self.client.beta.threads.messages.create(
            thread_id=thread_id,
            role="user",
            content=mensaje,
            attachments=[
                {
                    "file_id": file.id,
                    "tools": [{"type": "file_search"}]
                }
            ]
        )
    
        # Crear y esperar a que el run esté en estado terminal
        run = self.client.beta.threads.runs.create_and_poll(
            thread_id=thread_id,
            assistant_id=assistant_id
        )
    
        logging.info(f"file_path: {file_path}")
        self.eliminar_carpeta_temporalarch(file_path)
    
        # Obtener el vector store ID del thread
        thread = self.client.beta.threads.retrieve(thread_id=thread_id)
        vector_id = thread.tool_resources.file_search.vector_store_ids[0]
        self.client.vector_stores.update(
                vector_store_id=vector_id,
               expires_after={
	    "anchor": "last_active_at",
	    "days": 365
        }
            )
        # Recuperar los mensajes asociados al run
        messages = list(self.client.beta.threads.messages.list(thread_id=thread_id, run_id=run.id))
    
        # Procesar la respuesta del asistente para eliminar las citas
        for message in messages:
            if message.role == "assistant":
                message_content = message.content[0].text
                annotations = message_content.annotations
                citations = []
                for index, annotation in enumerate(annotations):
                    # Reemplazar el texto de la cita en el mensaje por un marcador vacío
                    message_content.value = message_content.value.replace(annotation.text, "")
                    if file_citation := getattr(annotation, "file_citation", None):
                        cited_file = self.client.files.retrieve(file_citation.file_id)
                        citations.append(f"[{index}] {cited_file.filename}")
                respuesta = message_content.value.strip()
                return respuesta, vector_id
    
        return None, 0
    def mensaje_archivo(self,thread_id,assistant_id,archivo,mensaje,asinatura)->str:
        # Coge el archivo del blob  y lo sube al thread al crear el mensaje
        archivo= blobs.descargar_archivo_blob(asinatura,archivo)
        
 
        # Ready the files for upload to OpenAI 
        file_path = archivo
        file = self.client.files.create(
        file=open(file_path, "rb"), purpose="assistants"
            )
        message=self.client.beta.threads.messages.create(thread_id=thread_id, role="user", content=mensaje, attachments= [
        { "file_id": file.id, "tools": [{"type": "file_search"}] }
      ])
        self.client.beta.threads.runs.create_and_poll(
        thread_id=thread_id, assistant_id=assistant_id
        )
        logging.info(f"file_path: {file_path}")
        self.eliminar_carpeta_temporalarch(file_path)
        #coger el vector store id
        thread=self.client.beta.threads.retrieve(thread_id=thread_id)
        vector_id=thread.tool_resources.file_search.vector_store_ids[0]
        self.client.vector_stores.update(
                vector_store_id=vector_id,
               expires_after={
	    "anchor": "last_active_at",
	    "days": 365
        }
            )
        # Retrieve the latest response
        response = self.client.beta.threads.messages.list(thread_id=thread_id)
        for message in response:
            if message.role == "assistant":
                message_content = message.content[0].text
                annotations = message_content.annotations
                citations = []
                for index, annotation in enumerate(annotations):
                    # Reemplazar el texto de la cita en el mensaje por un marcador vacío
                    message_content.value = message_content.value.replace(annotation.text, "")
                    if file_citation := getattr(annotation, "file_citation", None):
                        cited_file = self.client.files.retrieve(file_citation.file_id)
                        citations.append(f"[{index}] {cited_file.filename}")
                respuesta = message_content.value.strip()
                return respuesta, vector_id

                
        return None, 0
    def actualizar_vector_store(self,vector_store_id,carpeta,nombre_archivo):
    
        # Paso 1: Obtener los archivos actuales del almacén vectorial
        vector_store =self.client.beta.vector_stores.retrieve(id=vector_store_id)
        archivos_actuales = vector_store['files']

        # Paso 2: Eliminar los archivos existentes del almacén vectorial
        for archivo in archivos_actuales:
            self.client.beta.vector_stores.delete(
                vector_store_id=vector_store_id,
                file_id=archivo['id']
            )

        # Esperar un momento para asegurar que los archivos se eliminen correctamente
        time.sleep(2)
        archivo=blobs.descargar_archivo_blob("pdfsceu/"+carpeta,nombre_archivo)

        file_paths = [archivo]
        file_streams = [open(path, "rb") for path in file_paths]
        self.client.vector_stores.update(
                vector_store_id=vector_store_id,
               expires_after={
	    "anchor": "last_active_at",
	    "days": 365
        }
            )
        file_batch =self.client.vector_stores.file_batches.upload_and_poll(
        vector_store_id=vector_store_id, files=file_streams
        )
        print(f"El almacén vectorial {vector_store_id} ha sido actualizado con el nuevo archivo.")
    def display_chat_history(self, thread_id)->list:
        """
        Retrieves and displays the chat history for a given thread ID.

        Args:
            thread_id (str): The ID of the thread to retrieve chat history for.

        Returns:
            None
        """
        conversacion=[]
        response = self.client.beta.threads.messages.list(thread_id=thread_id)
        for message in reversed(response.data):
            role = message.role
            message_text = message.content[0].text.value
            #Fix this silly mistake
            conversacion.append(f"{role}: {message_text}")
        return conversacion
 
    def enviar_mensaje_sin_archivo(self,thread_id,assistant_id, mensaje)->str:
        
        self.client.beta.threads.messages.create(thread_id=thread_id, role="user", content=mensaje)
        
        run = self.client.beta.threads.runs.create_and_poll(
        thread_id=thread_id, assistant_id=assistant_id
        )


        # Wait for the assistant's response
        #self.wait_for_assistant(thread_id, assistant_id)

        # Retrieve the latest response
        response = self.client.beta.threads.messages.list(thread_id=thread_id)
        for message in response:
            if message.role == "assistant":
                message_content = message.content[0].text
                annotations = message_content.annotations
                citations = []
                for index, annotation in enumerate(annotations):
                    # Reemplazar el texto de la cita en el mensaje por un marcador vacío
                    message_content.value = message_content.value.replace(annotation.text, "")
                    if file_citation := getattr(annotation, "file_citation", None):
                        cited_file = self.client.files.retrieve(file_citation.file_id)
                        citations.append(f"[{index}] {cited_file.filename}")
                respuesta = message_content.value.strip()
                return respuesta

                
        return None, 0
    def enviar_mensaje_vectore_storage(self, thread_id, assistant_id, mensaje, vector_id) -> str:
        # Crear un mensaje en el hilo existente
        self.client.beta.threads.messages.create(
            thread_id=thread_id,
            role="user",
            content=mensaje
            )

        # Actualizar el hilo para adjuntar el almacén vectorial
        self.client.beta.threads.update(
        thread_id=thread_id,
        tool_resources={
            "file_search": {
                "vector_store_ids": [vector_id]
                }
            }
        )

    # Ejecutar el asistente en el hilo
        self.client.beta.threads.runs.create_and_poll(
        thread_id=thread_id,
        assistant_id=assistant_id
        )

    # Recuperar los mensajes del hilo
        response = self.client.beta.threads.messages.list(thread_id=thread_id)
        for message in response:
            if message.role == "assistant":
                message_content = message.content[0].text
                annotations = message_content.annotations
                citations = []
                for index, annotation in enumerate(annotations):
                    # Reemplazar el texto de la cita en el mensaje por un marcador vacío
                    message_content.value = message_content.value.replace(annotation.text, "")
                    if file_citation := getattr(annotation, "file_citation", None):
                        cited_file = self.client.files.retrieve(file_citation.file_id)
                        citations.append(f"[{index}] {cited_file.filename}")
                respuesta = message_content.value.strip()
                return respuesta

        return None
    def wait_for_assistant(self,thread_id, assistant_id):
        """
        Wait for the assistant to complete or fail a run in a given thread.

        Args:
            thread_id (str): The ID of the thread to check for runs.
            assistant_id (str): The ID of the assistant to wait for.

        Returns:
            None
        """
       

        while True:
            
            runs = self.client.beta.threads.runs.list(thread_id)
            latest_run = runs.data[0]
            if latest_run.status in ["completed", "failed"]:
                break

            time.sleep(0.1)
