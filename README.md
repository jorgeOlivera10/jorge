# Calculadora AWS - Arquitectura Desacoplada

Este proyecto es una modernización de la "Calculadora AWS" original, migrada de una aplicación de escritorio local (SPA monolítica) a una arquitectura desacoplada lista para la nube.

## Cambios Principales (v2.0.0)

- **Backend (Python/FastAPI):** Toda la lógica de negocio, validaciones Regex y algoritmos de cálculo de cableado se han extraído a Python.
- **Frontend:** Refactorizado para actuar como orquestador de UI, comunicándose con el backend mediante una API REST.
- **Exportación Excel:** Ahora se procesa en el servidor (backend) para garantizar máxima compatibilidad y formato profesional.
- **Contenedorización:** Incluye `Dockerfile` configurado para despliegue inmediato en Google Cloud Run (Puerto 8080).

## Estructura del Proyecto

- `/backend`: Código fuente de la API FastAPI.
- `/frontend`: Archivos estáticos (HTML, CSS, JS) servidos por el backend.
- `Dockerfile`: Configuración del contenedor.
- `requirements.txt`: Dependencias de Python.

## Ejecución Local

1. Crear entorno virtual: `python -m venv venv`
2. Activar entorno: `.\venv\Scripts\activate`
3. Instalar dependencias: `pip install -r requirements.txt`
4. Ejecutar servidor: `uvicorn backend.main:app --reload --port 8080`

Acceder a `http://127.0.0.1:8080`.

## Despliegue en Google Cloud Run

El contenedor está diseñado para ser desplegado directamente en Cloud Run. Asegúrate de configurar las variables de entorno necesarias si se requieren en el futuro.
