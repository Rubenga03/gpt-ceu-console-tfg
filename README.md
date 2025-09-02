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
```mermaid
flowchart LR
  U[Usuario GPT-CEU]
  FE[Front-end GPT-CEU]
  AF[Azure Function - consola IA]
  OA[Assistant + PandasAI]
  B[Azure Blob: Excel/CSV]
  J[JSON: datos + metadata]
  G[Gráfica interactiva]

  U --> FE
  FE --> AF
  AF --> OA
  OA <--> B
  AF --> J
  J --> G
  G --> FE
  FE --> U

  FE --> U

