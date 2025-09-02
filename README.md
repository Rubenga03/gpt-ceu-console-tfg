# gpt-ceu-console-tfg
# GPT-CEU Console – TFG Rubén García

Consola de IA integrada con GPT-CEU para gestionar y explotar datos académicos (Excel/CSV) con
respuestas estructuradas en JSON listas para visualización. Incluye templates (`matriculados`, `tasas`)
y consultas sin template.

## ✨ Objetivos
- Unificar acceso a fuentes heterogéneas.
- Automatizar selección de archivos y preprocesado (filtros/desambiguación).
- Devolver JSON auditable para gráficas interactivas (hover/tooltips).
- Reducir latencia mediante reutilización/warm-up (medición pareada).

## 🗺️ Arquitectura (resumen)
flowchart LR
  U["Usuario GPT-CEU"]
  FE["Front-end GPT-CEU"]
  AF["Azure Function<br/>(consola IA)"]
  OA["Assistant + PandasAI"]
  B[("Azure Blob<br/>(Excel/CSV)")]
  J["JSON<br/>(datos + metadata)"]
  G["Gráfica interactiva"]

  U --> FE
  FE --> AF
  AF --> OA
  OA <--> B
  AF --> J
  J --> G
  G --> FE
  FE --> U

