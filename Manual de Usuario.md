# Manual de Usuario: Anti Gravity - Calculadora de Cableado AWS

![Portada](file:///g:/Mi%20unidad/Anti%20Gravity/Portada.png)

## 1. Introducción
La herramienta **Anti Gravity** representa un hito en nuestra forma de trabajar dentro de los datacenters de AWS. Combina la precisión técnica de nuestros ingenieros de proyectos con la agilidad de una interfaz inteligente para transformar, en solo unos clics, complejos documentos SOW en cálculos de cableado exactos, profesionales y listos para su ejecución.

Su funcionamiento se basa en la interpretación de parámetros físicos reales que, gracias a un diseño robusto, activan las reglas de diseño, avenidas y distancias normativas de Amazon previamente definidas en el sistema.

Este es el fruto de un trabajo conjunto, de la experiencia acumulada en campo y del compromiso de quienes han hecho posible llevar la automatización a nuestro día a día. Ahora está en tus manos aprovechar todo su potencial para garantizar despliegues impecables y optimizar cada metro de infraestructura.

---

## 2. Contexto de Uso: Departamento de Proyectos
Dentro del flujo de trabajo habitual del **Departamento de Proyectos**, el uso de esta herramienta se sitúa en una fase crítica tras la recepción de la documentación técnica oficial.

### 2.1. Recepción y Análisis del SOW
El ingeniero de proyectos recibe los documentos **SOW (Scope of Work)**, los cuales detallan los requerimientos específicos de conectividad para el despliegue. A partir de esta documentación, el ingeniero debe realizar las siguientes tareas de interpretación:
1.  **Identificación de Racks**: Localizar el binomio compuesto por el **Rack de Origen** y el **Rack de Destino**.
2.  **Determinación de la Ruta (Path)**: Interpretar según el diseño de red cuál es el camino físico que debe seguir el cableado (A, B, C o D) a través de las avenidas del datacenter.

### 2.2. Hacia el Cálculo de Materiales
Una vez definidos los puntos de conexión y la ruta lógica, el ingeniero se enfrenta al resto de variables físicas: alturas de bandejas, márgenes de seguridad y las particularidades arquitectónicas de cada serie (ZAZ6X o ZAZ7X). El paso siguiente es la ejecución del cálculo preciso del cableado necesario.

---

## 3. Estructura de la Interfaz
Para facilitar la navegación, la aplicación presenta un diseño visual dividido en dos zonas claramente diferenciadas por colores:

*   **Zona Azul (Guía y Contexto)**: Situada en el lateral izquierdo de cada sección, esta área actúa como un asistente permanente. Indica el paso del flujo en el que te encuentras, explica qué información se requiere e incluye consejos técnicos para asegurar que los datos introducidos son correctos.
*   **Zona Blanca (Área de Trabajo)**: Es el núcleo operativo de la herramienta. Aquí es donde se introducen los binomios, se configuran los parámetros (Path, Tier, Redondeo) y se visualizan los resultados finales. Es la zona interactiva donde se realiza la magia técnica.

---

## 4. Guía de Uso del Programa

La aplicación sigue un flujo lineal dividido en tres fases principales.

### Paso 1: Entrada de Datos (Input)
En este bloque se traslada la información del SOW al entorno digital.
*   **Inserción de Binomios**: Pegue los racks directamente. El sistema procesa múltiples líneas si el origen y el destino están separados por espacio, tabulador o coma.
*   **Botón "Analizar Racks"**: Valida la nomenclatura y detecta la serie del datacenter.
*   **Funciones Auxiliares**:
    *   **Cargar Ejemplo**: Introduce automáticamente un conjunto de datos de prueba que incluye diversos casos (conexiones normales, directas e inter-hall) para familiarizarse con la herramienta.
    *   **Limpiar**: Resetea completamente la aplicación, borrando el texto y ocultando las secciones de configuración y resultados.

### Paso 2: Configuración y Parametrización
Aquí se definen las variables que afectarán a la medición final.
*   **Selección de Path**: Asigne la ruta (A, B, C o D) definida en el análisis del SOW.
*   **Gestión de Inter-Hall**: Para racks en pabellones distintos, introduzca manualmente la distancia de transición.
*   **Asignación de Bandeja (Tier)**: Selección del nivel de bandeja (Tier 3, 4 o 5).
*   **Configuración de Redondeo**: Permite ajustar el resultado final según las necesidades de suministro:
    *   **Sin redondeo**: Muestra la medida exacta con dos decimales.
    *   **Cada 2m / 5m**: Redondea el total **hacia arriba** (al alza) al múltiplo más cercano de 2 o 5 metros, asegurando que nunca falte cable.
*   **Edición Masiva**: Seleccione varios binomios y aplique configuraciones comunes desde la barra superior.

### Paso 3: Resultados y Exportación
Tras hacer clic en **"Calcular"**, el programa genera el desglose final.
*   **Métricas Detalladas**: Visualización de metros en cada tramo (vertical inicial, horizontal, vertical final, bandeja y el margen de seguridad de 0.6m).
*   **Resumen Ejecutivo**: La barra superior muestra el total acumulado y la media por binomio.
*   **Exportación**:
    *   **Copiar al Portapapeles**: Copia los datos en formato tabular para pegar en Excel.
    *   **Exportar a Excel**: Genera un archivo `.xlsx` listo para adjuntar a la documentación del proyecto.

---

## 5. Lógica de Cálculo y Especificaciones Técnicas

Fórmula aplicada:
> **Total = Distancia Vertical + Recorrido Horizontal + Factor de Bandeja + Margen de Seguridad**

### Parámetros de Medición:
*   **Verticalidad**: 0.3m por fila.
*   **Entrada a Avenidas**: 1.2m por cada transición.
*   **Segmentación Horizontal**:
    *   2m (columnas pares) / 3m (columnas impares).
    *   Salto crítico de 6m (ZAZ6X: Col 26-27 | ZAZ7X: Col 18-19).

---

## 6. Gestión de Errores e Incongruencias

*   **Conflictos de Serie**: Alerta si se mezclan racks de distintas familias (6X vs 7X).
*   **Validación de Formato**: El sistema impide avanzar si el nombre del rack no cumple el estándar AWS.
*   **Rutas Obligatorias**: Salvo en conexiones directas, el cálculo requiere que se haya seleccionado un Path válido.

---
*© 2026 Gotor Comunicaciones — Departamento de Proyectos.*
