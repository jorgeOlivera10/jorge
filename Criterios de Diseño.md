# CONTEXTO

Cuando amazon hace un centro de datos, necesita cablearlo y para ello genera unos documentos llamados SOW (Scope of Work) con los que el ingeniero debe interpretar cuál es el rack de origen desde donde se debe empezar a cablear, y cuál es el rack de destino hasta donde se debe cablear.

Una vez tenemos identificados el rack de origen y el rack de destino, necesitamos calcular cuántos metros de cable necesitamos para cada binomio de racks.

1. # NOMENCLATURA DE RACKS

Cada rack se identifica mediante una nomenclatura específica, compuesta por las siguientes partes: 

**Ciudad \+ Serie \+ ”.” \+ Hall \+ “-” \+ Columna \+ “-” \+ Fila**

**Ciudad:** Es la ciudad donde se encuentra el centro de datos, en nuestro caso siempre va a ser Zaragoza, que se representa por ZAZ.

* Zaragoza \= Se representa con un “ZAZ”  
  **Serie:** Es la serie de centro de datos.

* Serie 60: Puede ir del 60 hasta el 69\.  
* Serie 70: Puede ir del 60 hasta el 79\.  
* Serie 80: Puede ir del 80 hasta el 89\.  
  **Hall:** Es el pabellón dentro del centro de datos.

* Pabellón 1: Se representa con un “01-01”.  
* Pabellón 2: Se representa con un “01-02”.  
  **Columna:** Es la columna de racks. Sería la coordenada “x” donde está el rack indicado.

  **Fila:** Es la fila donde está el rack indicado. Sería la coordenada “y” donde está el rack indicado.

Vamos a poner un ejemplo: **ZAZ61.01-02-006-74**.

* La primera parte, **ZAZ**, indica que el centro de datos está en Zaragoza.  
* La segunda parte, **61**, indica que es de la serie 60\.  
* A continuación, **01-02** identifica que está en el Pabellón 2\.  
* Después, el valor **006** representa la columna de racks en la que se encuentra el rack indicado, en este caso en la columna 6\.  
* Por último, el número **74** representa la fila de racks en la que se encuentra el rack indicado, en este caso, la fila 74\.

2. # FUNCIONAMIENTO DE LOS planos

Los planos son esenciales para identificar la posición de los racks y empezar a calcular los metros de cable que se necesitan. A los planos relativos a la Serie 60 del centro de datos de Zaragoza les llamaremos ZAZ6X, y a los de la Serie 70 ZAZ7X.

## **CONCEPTOS BÁSICOS**

Para entender cómo funciona un plano es necesario tener claros unos conceptos básicos que explicamos a continuación.

* **Datacenter:** Es el edificio de AWS en el que se encuentran todos los racks.

* **Avenida:** Son los pasillos horizontales dentro del datacenter por los que se puede pasar el cableado.

* **Path:** Es el camino completo que sigue el cableado desde el punto de origen hasta el punto de destino.

* **Tier:** Es el nivel físico de las bandejas.

En los centros ZAZ6X existen **dos Avenidas:**

* **Avenida A**: situada en la parte superior del Datacenter (fila 10).  
* **Avenida B**: situada en la parte inferior del Datacenter (fila 95).

Y por lo tanto en los centros **ZAZ6X** existen dos posibles “PATH”:

* **PATH A**: el cable sube hacia la Avenida A.  
* **PATH B**: el cable baja hacia la Avenida B.

En los centros ZAZ7X existen **cuatro Avenidas**:

* **Avenida A**: situada en la parte superior del Datacenter (fila 10).  
* **Avenida B**: situada en la fila 37\.  
* **Avenida C**: situada en la fila 67\.  
* **Avenida D**: situada en la parte inferior del Datacenter (fila 95).

Y por lo tanto en los centros ZAZ7X existen cuatro posibles “PATH”:

* **PATH A**: el cable sube hacia la Avenida A.  
* **PATH B**: el cable va hacia la Avenida B.  
* **PATH C:** el cable va hacia la avenida C.  
* **PATH D:** el cable baja hacia la Avenida D.

3. # MEDIDAS DE LOS PLANOS

## **ZAZ6X:** 

Coordenada Y: 

* Desde la fila 11 hasta la fila 94 hay racks. Hay un rack por cada fila. Cada subida o bajada entre estas filas (desplazamiento vertical) requieren 0,3m de cable.  
* Cuando pasamos del rack de la última fila (fila 11\) a la Avenida A (fila 10),  requiere 1,2m de cable.  
* Cuando pasamos del rack de la última fila (fila 94\) a la Avenida (fila 95),  requiere 1,2m de cable.

Path:

* Cuando el usuario selecciona Path A, el desplazamiento vertical (coordenada Y) es hasta llegar a la Avenida A (fila 10), desde donde iniciará su desplazamiento horizontal (coordenada X).  
* Cuando el usuario selecciona Path B, el desplazamiento vertical (coordenada Y) es hasta llegar a la Avenida B (fila 95), desde donde iniciará su desplazamiento horizontal (coordenada X).

Coordenada X:

* Desde la columna 1 hasta la 50 hay racks. Cada movimiento hacia la derecha (desplazamiento horizontal) son 2m de cable cuando el desplazamiento es hacia un número de columna par, y 3m de cable cuando el desplazamiento es hacia un número de columna impar.   
* Es decir, de la columna 1 a la 2 requieren 2m de cable; de la columna 2 a la 3 requieren 3m de cable; de la columna 3 a la 4 requieren 2m de cable; de la columna 4 a la 5 requieren 3m de cable; así hasta la 50\.  
* Hay una excepción; para pasar de la columna 26 a la 27 requieren 6m de cable.

## **ZAZ7X:**

Coordenada Y: 

* Desde la fila 11 hasta la fila 94 hay racks. Hay un rack por cada fila. Cada subida o bajada entre estas filas (desplazamiento vertical) requieren 0,3m de cable.  
* Cuando pasamos del rack de la última fila (fila 11\) a la Avenida A (fila 10),  requiere 1,2m de cable.  
* Cuando pasamos del rack de la última fila (fila 94\) a la Avenida D (fila 95),  requiere 1,2m de cable.

Path: 

* Cuando el usuario selecciona Path A, el desplazamiento vertical (coordenada Y) es hasta llegar a la Avenida A (fila 10), desde donde iniciará su desplazamiento horizontal (coordenada X).  
* Cuando el usuario selecciona Path B, el desplazamiento vertical (coordenada Y) es hasta llegar a la Avenida B (fila 37), desde donde iniciará su desplazamiento horizontal (coordenada X).  
* Cuando el usuario selecciona Path C, el desplazamiento vertical (coordenada Y) es hasta llegar a la Avenida C (fila 67), desde donde iniciará su desplazamiento horizontal (coordenada X).  
* Cuando el usuario selecciona Path D, el desplazamiento vertical (coordenada Y) es hasta llegar a la Avenida D (fila 95), desde donde iniciará su desplazamiento horizontal (coordenada X).

Coordenada X:

* Desde la columna 1 hasta la 34 hay racks. Cada movimiento hacia la derecha (desplazamiento horizontal) son 2m de cable cuando el desplazamiento es hacia un número de columna par, y 3m de cable cuando el desplazamiento es hacia un número de columna impar.   
* Es decir, de la columna 1 a la 2 requieren 2m de cable; de la columna 2 a la 3 requieren 3m de cable; de la columna 3 a la 4 requieren 2m de cable; de la columna 4 a la 5 requieren 3m de cable; así hasta la 34\.  
* Hay una excepción; para pasar de la columna 18 a la 19 requieren 6m de cable.

4. # lógica de cálculo

La lógica de cálculo del cableado se basa en los planos de ZAZ6X y ZAZ7X, mediante la siguiente fórmula:

**DISTANCIA TOTAL \= Vertical inicial \+ Horizontal \+ Vertical final \+ Bandeja \+ Margen**

* **Vertical inicial:** es la cantidad de filas que recorre al inicio de su recorrido.  
* **Horizontal:** es la cantidad de columnas que recorre una vez ha hecho su recorrido “Vertical inicial”.  
* **Vertical final:** es la cantidad de filas que recorre tras hacer su recorrido “Horizontal”.  
* **Bandeja:** es la cantidad de metros establecidos según el tipo de bandeja. Según qué bandeja seleccione el usuario, se añadirán unos metros concretos de cable:   
  * Tier 3 \= 10m de cable  
  * Tier 4 \= 15m de cable  
  * Tier 5 \= 15m de cable  
* **Margen**: Ponemos siempre 0,6 metros de cable adicional que sirve como margen ante posibles imprevistos.

El **Path** será seleccionado por el ingeniero en función de la interpretación de la documentación inicial del proyecto (SOW):

* En **ZAZ6X** se elegirá entre **Path A o Path B.**  
* En **ZAZ7X** se elegirá entre **Path A, B, C o D.**

## **CASOS ESPECIALES**

1. ## **Conexión Directa**

Se considera que una conexión es **DIRECTA** cuando el rack de origen y el rack de destino se encuentran en la **misma columna de racks**.

En este caso:

* No existe recorrido horizontal entre filas.  
* No es necesario utilizar path (A, B, C o D).  
* El cableado se realiza directamente en vertical dentro de la misma columna.

Por tanto, el cálculo se simplifica a:

**DISTANCIA TOTAL \= Vertical inicial \+ Bandeja \+ Margen**

2. ## **Conexiones Inter-Hall**

Pueden darse casos en los que los racks pueden estar en halls diferentes dentro del mismo datacenter. Por ejemplo:

* Origen: `ZAZ61.01-01-006-74` (Hall 1\)  
* Destino: `ZAZ61.01-02-012-45` (Hall 2\)

La distancia entre halls es variable y desconocida, por lo que en esos casos necesitaremos que el programa muestre un aviso de que se trata una conexión entre dos Hall distintos (Conexión Inter-Hall) para que el ingeniero complete manualmente los metros necesarios de cable.

5. # diseño del programa

Para llevar todo esto acabo necesitamos un programa sencillo e intuitivo que lleve a cabo los siguientes puntos básicos:

1. El ingeniero introduce el Rack de Origen y el Rack de Destino. Tiene que ser que se puedan pegar unos cuantos racks de destino y de origen de golpe, ya que en el SOW pueden pedir cablear más de 1 binomio de racks.  
2. El sistema reconoce si es un caso de ZAZ6X o ZAZ7X, además de reconocer la ubicación del rack de origen y el rack de destino.  
3. El ingeniero introduce (a continuación de cada binomio de racks) si quiere Path A o B en caso de ser ZAZ6X, o Path A, B, C o D en caso de ser ZAZ7X.  
4. El ingeniero introduce si quiere Bandeja de Tier 3, 4, o 5\.  
5. El programa calcula, por cada binomio de racks, cuántos metros de Vertical inicial, Horizontal, Vertical final, Bandeja y Margen de cable son necesarios, y al lado una columna de total.  
6. El cálculo resultante tiene que poderse copiar en el portapapeles (para poder pegar en una excel) y también se tiene que poder exportar en excel.

## **OTRAS INDICACIONES:**

Si el sistema detecta incongruencias, debe imposibilitar la opción de continuar al usuario, indicando en todo momento cuál es el error / incongruencia. Por ejemplo, si el usuario introduce un rack de origen ZAZ61 con un rack de destino ZAZ71, debe indicar que no es posible cablear un rack de la serie 7X con un rack de la serie 6X.