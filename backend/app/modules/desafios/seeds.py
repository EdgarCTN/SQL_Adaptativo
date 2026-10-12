"""Seeds idempotentes de los 6 desafíos del MVP (2 por dificultad).

Dominios: biblioteca, gimnasio y tienda de música (el cuestionario usa clientes/pedidos/productos).
Formato guardado:
- errores_tipicos: [{"descripcion", "ejemplo"}]  (el ejemplo es una consulta que debe FALLAR)
- ayudas_respaldo: {"AY1".."AY4": {"mensaje", "codigo_sql"|None}}
El tiempo de referencia sale de reglas.json (tiempo_referencia_seg).
"""
import logging

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.reglas import cargar_reglas
from app.modules.desafios.models import Concepto, Desafio

log = logging.getLogger("app.seeds")


def _ay(mensaje: str, codigo: str | None = None) -> dict:
    return {"mensaje": mensaje, "codigo_sql": codigo}


DESAFIOS: list[dict] = [
    # ------------------------------------------------------------------ D1 filtrado
    {
        "titulo": "Novelas recientes con copias disponibles",
        "concepto": "filtrado",
        "dificultad": "D1",
        "enunciado": (
            "La biblioteca quiere destacar sus novelas más nuevas. Escribe una consulta que devuelva "
            "el título y el año de los libros del género 'Novela' publicados desde el año 2010 "
            "(inclusive) y que tengan al menos una copia disponible."
        ),
        "recursos": [
            "WHERE filtra las filas que cumplen una condición.",
            "AND exige que se cumplan todas las condiciones; OR basta con una.",
            "Los textos van entre comillas simples, por ejemplo 'Novela'.",
        ],
        "esquema": (
            "CREATE TABLE libros (\n"
            "  id_libro INTEGER PRIMARY KEY,\n"
            "  titulo TEXT NOT NULL,\n"
            "  autor TEXT NOT NULL,\n"
            "  genero TEXT NOT NULL,\n"
            "  anio INTEGER NOT NULL,\n"
            "  copias_disponibles INTEGER NOT NULL\n"
            ");"
        ),
        "datos": """
INSERT INTO libros VALUES
 (1,'La casa de papel y tinta','Marta Ríos','Novela',2015,3),
 (2,'Ecos del Rímac','Luis Paredes','Novela',2010,1),
 (3,'El jardín quieto','Ana Soto','Novela',2009,2),
 (4,'Noches de Cusco','Jorge Vega','Novela',2018,0),
 (5,'Historia mínima del Perú','Carla Ruiz','Historia',2016,4),
 (6,'Cartas al sur','Elena Maita','Novela',2021,2),
 (7,'Ensayos de lluvia','Pablo Quispe','Ensayo',2012,5),
 (8,'El último tranvía','Raúl Díaz','Novela',2005,1),
 (9,'Mar de fondo','Sofía Luna','Novela',2012,0),
 (10,'Poemas de bolsillo','Inés Calle','Poesía',2019,6),
 (11,'La biblioteca ciega','Diego Alva','Novela',2023,1),
 (12,'Cuentos de la selva','Rosa Tello','Cuentos',2011,2);
""",
        "solucion": (
            "SELECT titulo, anio\nFROM libros\n"
            "WHERE genero = 'Novela'\n  AND anio >= 2010\n  AND copias_disponibles > 0;"
        ),
        "errores": [
            (
                "Mezclar AND y OR sin paréntesis: AND se evalúa primero y la condición queda distinta a la pedida.",
                "SELECT titulo, anio FROM libros WHERE genero = 'Novela' OR anio >= 2010 AND copias_disponibles > 0;",
            ),
            (
                "Usar > en vez de >=: «desde 2010» incluye el año 2010.",
                "SELECT titulo, anio FROM libros WHERE genero = 'Novela' AND anio > 2010 AND copias_disponibles > 0;",
            ),
            (
                "Olvidar la condición de disponibilidad: aparecen libros sin copias.",
                "SELECT titulo, anio FROM libros WHERE genero = 'Novela' AND anio >= 2010;",
            ),
        ],
        "ayudas": {
            "AY1": _ay(
                "Antes de escribir, piensa en las condiciones que debe cumplir cada libro: ¿cuántas son? "
                "¿Tienen que cumplirse todas a la vez o basta con una? Fíjate también en si «desde 2010» "
                "incluye o no ese año, y en qué columna te dice si quedan copias."
            ),
            "AY2": _ay(
                "Un ejemplo en otro contexto: para listar las mascotas de una veterinaria que son perros, "
                "tienen 3 años o más y están vacunadas, todas las condiciones se combinan con AND dentro de "
                "un único WHERE. Adáptalo a las columnas de libros.",
                "SELECT nombre, edad\nFROM mascotas\nWHERE especie = 'Perro'\n  AND edad >= 3\n  AND vacunada = 1;",
            ),
            "AY3": _ay(
                "Completa los espacios en blanco (___) con la columna, el operador o el valor que corresponde.",
                "SELECT titulo, ___\nFROM libros\nWHERE genero = ___\n  AND anio ___ 2010\n  AND copias_disponibles ___ 0;",
            ),
            "AY4": _ay(
                "Se filtra con un solo WHERE que une tres condiciones con AND: el género es 'Novela', el año "
                "es 2010 o posterior (>= incluye el 2010) y las copias disponibles son mayores que 0. "
                "Se seleccionan solo titulo y anio, como pide el enunciado.",
                "SELECT titulo, anio\nFROM libros\nWHERE genero = 'Novela'\n  AND anio >= 2010\n  AND copias_disponibles > 0;",
            ),
        },
    },
    # ------------------------------------------------------------------ D1 ordenamiento
    {
        "titulo": "Clases del gimnasio por cupo",
        "concepto": "ordenamiento",
        "dificultad": "D1",
        "enunciado": (
            "El gimnasio quiere publicar su cartelera. Escribe una consulta que devuelva el nombre y el "
            "cupo de todas las clases, de mayor a menor cupo. Si dos clases tienen el mismo cupo, "
            "ordénalas alfabéticamente por nombre (de la A a la Z)."
        ),
        "recursos": [
            "ORDER BY ordena el resultado; ASC es ascendente (por defecto) y DESC descendente.",
            "Puedes ordenar por varias columnas separadas por comas: la primera tiene prioridad.",
        ],
        "esquema": (
            "CREATE TABLE clases (\n"
            "  id_clase INTEGER PRIMARY KEY,\n"
            "  nombre TEXT NOT NULL,\n"
            "  instructor TEXT NOT NULL,\n"
            "  dia TEXT NOT NULL,\n"
            "  cupo INTEGER NOT NULL\n"
            ");"
        ),
        "datos": """
INSERT INTO clases VALUES
 (1,'Zumba','Carla','Lunes',25),
 (2,'Aerobox','Mateo','Martes',25),
 (3,'Yoga','Lucía','Lunes',15),
 (4,'Pilates','Lucía','Miércoles',15),
 (5,'Spinning','Mateo','Jueves',30),
 (6,'Crossfit','Diego','Viernes',20),
 (7,'Funcional','Diego','Sábado',10),
 (8,'Baile','Carla','Miércoles',15);
""",
        "solucion": "SELECT nombre, cupo\nFROM clases\nORDER BY cupo DESC, nombre ASC;",
        "errores": [
            (
                "Olvidar DESC: el orden por defecto es ascendente (menor a mayor).",
                "SELECT nombre, cupo FROM clases ORDER BY cupo, nombre;",
            ),
            (
                "Invertir la prioridad de las columnas: primero se ordena por nombre y el cupo casi no influye.",
                "SELECT nombre, cupo FROM clases ORDER BY nombre, cupo DESC;",
            ),
            (
                "No desempatar: con el mismo cupo, el orden de las clases queda sin criterio.",
                "SELECT nombre, cupo FROM clases ORDER BY cupo DESC;",
            ),
        ],
        "ayudas": {
            "AY1": _ay(
                "Piensa en dos criterios de orden: ¿cuál va primero y en qué sentido (de mayor a menor o al "
                "revés)? ¿Qué criterio se usa solo cuando el primero empata? Recuerda que el sentido de cada "
                "criterio se indica por separado."
            ),
            "AY2": _ay(
                "Un ejemplo en otro contexto: para listar ciudades de la más poblada a la menos poblada, y "
                "desempatar por nombre, se escriben ambos criterios en el ORDER BY separados por coma, cada "
                "uno con su propio sentido.",
                "SELECT nombre, poblacion\nFROM ciudades\nORDER BY poblacion DESC, nombre ASC;",
            ),
            "AY3": _ay(
                "Completa los espacios en blanco (___) con las columnas y los sentidos de orden.",
                "SELECT nombre, cupo\nFROM clases\nORDER BY ___ ___, ___ ___;",
            ),
            "AY4": _ay(
                "El ORDER BY lleva dos criterios: cupo DESC (de mayor a menor) y, para los empates, "
                "nombre ASC (alfabético). La coma separa los criterios y el primero tiene prioridad.",
                "SELECT nombre, cupo\nFROM clases\nORDER BY cupo DESC, nombre ASC;",
            ),
        },
    },
    # ------------------------------------------------------------------ D2 join
    {
        "titulo": "Préstamos pendientes de devolución",
        "concepto": "join",
        "dificultad": "D2",
        "enunciado": (
            "La biblioteca necesita saber qué libros siguen prestados. Escribe una consulta que devuelva, "
            "para cada préstamo que aún no se devolvió (fecha_devolucion vacía), el nombre del socio y el "
            "título del libro, en ese orden."
        ),
        "recursos": [
            "JOIN ... ON une dos tablas usando una condición entre columnas relacionadas.",
            "Para unir tres tablas se encadenan dos JOIN, cada uno con su propio ON.",
            "Para comprobar si un valor está vacío se usa IS NULL (no = NULL).",
        ],
        "esquema": (
            "CREATE TABLE socios (\n"
            "  id_socio INTEGER PRIMARY KEY,\n"
            "  nombre TEXT NOT NULL,\n"
            "  carrera TEXT NOT NULL\n"
            ");\n"
            "CREATE TABLE libros (\n"
            "  id_libro INTEGER PRIMARY KEY,\n"
            "  titulo TEXT NOT NULL,\n"
            "  autor TEXT NOT NULL\n"
            ");\n"
            "CREATE TABLE prestamos (\n"
            "  id_prestamo INTEGER PRIMARY KEY,\n"
            "  id_socio INTEGER NOT NULL REFERENCES socios(id_socio),\n"
            "  id_libro INTEGER NOT NULL REFERENCES libros(id_libro),\n"
            "  fecha_prestamo TEXT NOT NULL,\n"
            "  fecha_devolucion TEXT\n"
            ");"
        ),
        "datos": """
INSERT INTO socios VALUES
 (1,'Valeria Campos','Ingeniería'),
 (2,'Andrés Mejía','Derecho'),
 (3,'Camila Torres','Medicina'),
 (4,'Bruno Salas','Arquitectura');
INSERT INTO libros VALUES
 (1,'Pedro Páramo','Juan Rulfo'),
 (2,'Rayuela','Julio Cortázar'),
 (3,'Conversación en La Catedral','Mario Vargas Llosa'),
 (4,'Cien años de soledad','Gabriel García Márquez'),
 (5,'El Aleph','Jorge Luis Borges');
INSERT INTO prestamos VALUES
 (1,1,2,'2025-09-01','2025-09-15'),
 (2,1,4,'2025-10-02',NULL),
 (3,2,1,'2025-09-20',NULL),
 (4,2,3,'2025-10-05','2025-10-12'),
 (5,3,3,'2025-10-10',NULL),
 (6,3,1,'2025-08-01','2025-08-20'),
 (7,1,1,'2025-10-15',NULL);
""",
        "solucion": (
            "SELECT s.nombre, l.titulo\nFROM prestamos p\n"
            "JOIN socios s ON s.id_socio = p.id_socio\n"
            "JOIN libros l ON l.id_libro = p.id_libro\n"
            "WHERE p.fecha_devolucion IS NULL;"
        ),
        "errores": [
            (
                "Comparar con = NULL: ningún valor es igual a NULL, así que no devuelve filas.",
                "SELECT s.nombre, l.titulo FROM prestamos p JOIN socios s ON s.id_socio = p.id_socio "
                "JOIN libros l ON l.id_libro = p.id_libro WHERE p.fecha_devolucion = NULL;",
            ),
            (
                "Unir con columnas que no se corresponden (id_socio con id_libro): los nombres salen cruzados.",
                "SELECT s.nombre, l.titulo FROM prestamos p JOIN socios s ON s.id_socio = p.id_libro "
                "JOIN libros l ON l.id_libro = p.id_libro WHERE p.fecha_devolucion IS NULL;",
            ),
            (
                "Olvidar la condición ON: cada préstamo se combina con todos los socios y libros (producto cartesiano).",
                "SELECT s.nombre, l.titulo FROM prestamos p JOIN socios s JOIN libros l "
                "WHERE p.fecha_devolucion IS NULL;",
            ),
        ],
        "ayudas": {
            "AY1": _ay(
                "Los datos que necesitas están repartidos en tres tablas. Piensa cuál es la tabla «central» que "
                "relaciona a las otras dos y qué columna comparten cada par de tablas. Después decide cómo "
                "reconocer un préstamo que no se devolvió: ¿qué valor tiene esa fecha?"
            ),
            "AY2": _ay(
                "Un ejemplo en otro contexto: en un colegio, para mostrar el nombre del estudiante y el curso "
                "de cada matrícula activa, la tabla de matrículas se une con estudiantes y con cursos, cada "
                "unión con su propio ON, y luego se filtra.",
                "SELECT e.nombre, c.titulo\nFROM matriculas m\nJOIN estudiantes e ON e.id_estudiante = m.id_estudiante\n"
                "JOIN cursos c ON c.id_curso = m.id_curso\nWHERE m.baja IS NULL;",
            ),
            "AY3": _ay(
                "Completa los espacios en blanco (___) con las tablas, columnas y la condición del filtro.",
                "SELECT s.nombre, l.titulo\nFROM prestamos p\nJOIN socios s ON s.id_socio = p.___\n"
                "JOIN libros l ON l.id_libro = p.___\nWHERE p.fecha_devolucion ___;",
            ),
            "AY4": _ay(
                "Se parte de prestamos (la tabla que relaciona socios y libros). El primer JOIN une con socios "
                "por id_socio y el segundo con libros por id_libro. El filtro IS NULL deja solo los préstamos "
                "sin fecha de devolución.",
                "SELECT s.nombre, l.titulo\nFROM prestamos p\nJOIN socios s ON s.id_socio = p.id_socio\n"
                "JOIN libros l ON l.id_libro = p.id_libro\nWHERE p.fecha_devolucion IS NULL;",
            ),
        },
    },
    # ------------------------------------------------------------------ D2 having
    {
        "titulo": "Instructores con más de 40 asistentes en octubre",
        "concepto": "having",
        "dificultad": "D2",
        "enunciado": (
            "El gimnasio premiará a los instructores con mayor asistencia. Escribe una consulta que devuelva "
            "el instructor y el total de asistentes de sus sesiones realizadas en octubre de 2025 "
            "(las fechas son texto 'AAAA-MM-DD'), mostrando solo a quienes sumaron más de 40 asistentes "
            "en ese mes."
        ),
        "recursos": [
            "GROUP BY agrupa las filas; SUM, COUNT y AVG resumen cada grupo.",
            "WHERE filtra filas antes de agrupar; HAVING filtra los grupos ya resumidos.",
            "Las funciones de agregación no pueden usarse en WHERE.",
        ],
        "esquema": (
            "CREATE TABLE sesiones_clase (\n"
            "  id_sesion INTEGER PRIMARY KEY,\n"
            "  instructor TEXT NOT NULL,\n"
            "  clase TEXT NOT NULL,\n"
            "  fecha TEXT NOT NULL,\n"
            "  asistentes INTEGER NOT NULL\n"
            ");"
        ),
        "datos": """
INSERT INTO sesiones_clase VALUES
 (1,'Carla','Zumba','2025-10-03',15),
 (2,'Carla','Baile','2025-10-10',12),
 (3,'Carla','Zumba','2025-10-24',18),
 (4,'Carla','Zumba','2025-09-12',20),
 (5,'Mateo','Spinning','2025-10-06',20),
 (6,'Mateo','Aerobox','2025-10-20',20),
 (7,'Mateo','Spinning','2025-09-15',25),
 (8,'Diego','Crossfit','2025-10-01',6),
 (9,'Diego','Funcional','2025-10-08',7),
 (10,'Diego','Crossfit','2025-10-15',8),
 (11,'Diego','Funcional','2025-10-22',9),
 (12,'Diego','Crossfit','2025-10-29',5),
 (13,'Diego','Crossfit','2025-09-10',30),
 (14,'Lucía','Yoga','2025-10-07',22),
 (15,'Lucía','Pilates','2025-10-21',25),
 (16,'Lucía','Yoga','2025-11-02',10);
""",
        "solucion": (
            "SELECT instructor, SUM(asistentes) AS total\nFROM sesiones_clase\n"
            "WHERE fecha >= '2025-10-01' AND fecha < '2025-11-01'\n"
            "GROUP BY instructor\nHAVING SUM(asistentes) > 40;"
        ),
        "errores": [
            (
                "Usar una función de agregación en WHERE: los totales solo existen después de agrupar; se usa HAVING.",
                "SELECT instructor, SUM(asistentes) FROM sesiones_clase WHERE fecha >= '2025-10-01' "
                "AND fecha < '2025-11-01' AND SUM(asistentes) > 40 GROUP BY instructor;",
            ),
            (
                "Olvidar filtrar por octubre: se suman las asistencias de todos los meses.",
                "SELECT instructor, SUM(asistentes) FROM sesiones_clase GROUP BY instructor HAVING SUM(asistentes) > 40;",
            ),
            (
                "Contar sesiones en lugar de sumar asistentes: COUNT(*) cuenta filas, no personas.",
                "SELECT instructor, SUM(asistentes) FROM sesiones_clase WHERE fecha >= '2025-10-01' "
                "AND fecha < '2025-11-01' GROUP BY instructor HAVING COUNT(*) > 3;",
            ),
        ],
        "ayudas": {
            "AY1": _ay(
                "Hay dos filtros distintos: uno sobre las filas individuales (el mes de la sesión) y otro sobre "
                "el resultado ya sumado por instructor (más de 40). Pregúntate cuál ocurre antes de agrupar y "
                "cuál después, y qué cláusula corresponde a cada uno."
            ),
            "AY2": _ay(
                "Un ejemplo en otro contexto: en un restaurante, para ver qué meseros acumularon más de 100 "
                "en propinas durante el mes de marzo, primero se filtra el mes con WHERE, luego se agrupa por "
                "mesero y por último se filtra el total con HAVING.",
                "SELECT mesero, SUM(propina) AS total\nFROM cuentas\nWHERE fecha >= '2025-03-01' AND fecha < '2025-04-01'\n"
                "GROUP BY mesero\nHAVING SUM(propina) > 100;",
            ),
            "AY3": _ay(
                "Completa los espacios en blanco (___) con las cláusulas y la función que faltan.",
                "SELECT instructor, SUM(asistentes) AS total\nFROM sesiones_clase\n___ fecha >= '2025-10-01' AND fecha < '2025-11-01'\n"
                "___ BY instructor\n___ SUM(asistentes) > 40;",
            ),
            "AY4": _ay(
                "WHERE se queda con las sesiones de octubre; GROUP BY instructor suma las asistencias de cada "
                "uno; HAVING SUM(asistentes) > 40 conserva solo a los instructores cuyo total supera 40 "
                "(40 exactamente no alcanza).",
                "SELECT instructor, SUM(asistentes) AS total\nFROM sesiones_clase\n"
                "WHERE fecha >= '2025-10-01' AND fecha < '2025-11-01'\nGROUP BY instructor\nHAVING SUM(asistentes) > 40;",
            ),
        },
    },
    # ------------------------------------------------------------------ D3 subconsulta
    {
        "titulo": "Álbumes más caros que el promedio de su género",
        "concepto": "subconsulta",
        "dificultad": "D3",
        "enunciado": (
            "Una tienda de música quiere revisar sus precios. Escribe una consulta que devuelva el título, "
            "el género y el precio de los álbumes cuyo precio es estrictamente mayor que el precio promedio "
            "de los álbumes de su mismo género."
        ),
        "recursos": [
            "Una subconsulta es un SELECT dentro de otro, entre paréntesis.",
            "Una subconsulta correlacionada usa una columna de la consulta exterior (por ejemplo, a.genero).",
            "Si la subconsulta se compara con un operador como >, debe devolver un único valor.",
        ],
        "esquema": (
            "CREATE TABLE albumes (\n"
            "  id_album INTEGER PRIMARY KEY,\n"
            "  titulo TEXT NOT NULL,\n"
            "  artista TEXT NOT NULL,\n"
            "  genero TEXT NOT NULL,\n"
            "  precio REAL NOT NULL\n"
            ");"
        ),
        "datos": """
INSERT INTO albumes VALUES
 (1,'Cielo Rojo','Los Andes','Rock',30.0),
 (2,'Ruta Eléctrica','Fuego Sur','Rock',50.0),
 (3,'Eco Urbano','Los Andes','Rock',40.0),
 (4,'Tormenta','Fuego Sur','Rock',60.0),
 (5,'Azul Medianoche','Trío Lima','Jazz',20.0),
 (6,'Contratiempo','Nora Vidal','Jazz',35.0),
 (7,'Sala 9','Trío Lima','Jazz',20.0),
 (8,'Neón','Mía','Pop',20.0),
 (9,'Verano','Mía','Pop',30.0),
 (10,'Latido','Dani K','Pop',40.0),
 (11,'Sabor Ahora','Orquesta Calle 8','Salsa',70.0);
""",
        "solucion": (
            "SELECT a.titulo, a.genero, a.precio\nFROM albumes a\n"
            "WHERE a.precio > (\n  SELECT AVG(b.precio)\n  FROM albumes b\n  WHERE b.genero = a.genero\n);"
        ),
        "errores": [
            (
                "Comparar con el promedio de toda la tienda en vez del de su género: falta relacionar la subconsulta con la fila exterior.",
                "SELECT titulo, genero, precio FROM albumes WHERE precio > (SELECT AVG(precio) FROM albumes);",
            ),
            (
                "Usar >= en vez de >: un álbum con precio igual al promedio no es «mayor» que el promedio.",
                "SELECT a.titulo, a.genero, a.precio FROM albumes a WHERE a.precio >= "
                "(SELECT AVG(b.precio) FROM albumes b WHERE b.genero = a.genero);",
            ),
            (
                "La subconsulta devuelve varias filas (un precio por álbum) en lugar de un solo promedio.",
                "SELECT a.titulo, a.genero, a.precio FROM albumes a WHERE a.precio > "
                "(SELECT b.precio FROM albumes b WHERE b.genero = a.genero);",
            ),
        ],
        "ayudas": {
            "AY1": _ay(
                "Para cada álbum necesitas un valor de comparación distinto: el promedio de su propio género. "
                "Pregúntate: ¿cómo puede la subconsulta saber de qué género es el álbum que se está revisando? "
                "¿Cuántos valores debe devolver para poder compararse con el precio?"
            ),
            "AY2": _ay(
                "Un ejemplo en otro contexto: en una cadena de tiendas, para listar los productos cuyo stock "
                "está por debajo del mínimo registrado en su propia bodega, la subconsulta usa la bodega del "
                "producto de la consulta exterior para devolver un único valor.",
                "SELECT p.nombre\nFROM productos p\nWHERE p.stock < (\n  SELECT MIN(b.stock_minimo)\n  FROM bodegas b\n  WHERE b.id_bodega = p.id_bodega\n);",
            ),
            "AY3": _ay(
                "Completa los espacios en blanco (___) con la función y la columna que relacionan la subconsulta "
                "con el álbum de la consulta exterior.",
                "SELECT a.titulo, a.genero, a.precio\nFROM albumes a\nWHERE a.precio > (\n  SELECT ___(b.precio)\n  FROM albumes b\n  WHERE b.genero = a.___\n);",
            ),
            "AY4": _ay(
                "La subconsulta calcula AVG(b.precio) solo entre los álbumes b del mismo género que el álbum a "
                "de la consulta exterior (b.genero = a.genero). Devuelve un único valor por álbum, y la "
                "consulta exterior conserva los que lo superan estrictamente.",
                "SELECT a.titulo, a.genero, a.precio\nFROM albumes a\nWHERE a.precio > (\n  SELECT AVG(b.precio)\n  FROM albumes b\n  WHERE b.genero = a.genero\n);",
            ),
        },
    },
    # ------------------------------------------------------------------ D3 funciones_ventana
    {
        "titulo": "Ventas acumuladas por género y mes",
        "concepto": "funciones_ventana",
        "dificultad": "D3",
        "enunciado": (
            "La tienda de música quiere ver cómo crecen sus ventas durante 2025. Escribe una consulta que "
            "devuelva, para cada fila de ventas_mensuales, cuatro columnas: género, mes, unidades y las "
            "unidades acumuladas del género desde enero hasta ese mes (inclusive). Ordena el resultado por "
            "género y luego por mes. No debe haber una fila por grupo: se conservan todas las filas."
        ),
        "recursos": [
            "Una función de ventana calcula un valor sobre un conjunto de filas sin colapsarlas: SUM(...) OVER (...).",
            "PARTITION BY divide las filas en grupos independientes dentro de la ventana.",
            "ORDER BY dentro de OVER define el orden en que se acumula.",
        ],
        "esquema": (
            "CREATE TABLE ventas_mensuales (\n"
            "  id_registro INTEGER PRIMARY KEY,\n"
            "  genero TEXT NOT NULL,\n"
            "  mes TEXT NOT NULL,\n"
            "  unidades INTEGER NOT NULL\n"
            ");"
        ),
        "datos": """
INSERT INTO ventas_mensuales VALUES
 (1,'Rock','2025-01',120),
 (2,'Jazz','2025-01',40),
 (3,'Rock','2025-02',90),
 (4,'Jazz','2025-02',55),
 (5,'Rock','2025-03',150),
 (6,'Jazz','2025-03',35),
 (7,'Rock','2025-04',110),
 (8,'Jazz','2025-04',60);
""",
        "solucion": (
            "SELECT genero, mes, unidades,\n"
            "       SUM(unidades) OVER (PARTITION BY genero ORDER BY mes) AS acumulado\n"
            "FROM ventas_mensuales\nORDER BY genero, mes;"
        ),
        "errores": [
            (
                "Omitir PARTITION BY: el acumulado mezcla los géneros en lugar de reiniciarse en cada uno.",
                "SELECT genero, mes, unidades, SUM(unidades) OVER (ORDER BY mes) AS acumulado "
                "FROM ventas_mensuales ORDER BY genero, mes;",
            ),
            (
                "Omitir ORDER BY dentro de OVER: cada fila muestra el total del género, no el acumulado hasta ese mes.",
                "SELECT genero, mes, unidades, SUM(unidades) OVER (PARTITION BY genero) AS acumulado "
                "FROM ventas_mensuales ORDER BY genero, mes;",
            ),
            (
                "Usar GROUP BY en lugar de una ventana: la suma queda por grupo y no acumula entre meses.",
                "SELECT genero, mes, unidades, SUM(unidades) AS acumulado FROM ventas_mensuales "
                "GROUP BY genero, mes ORDER BY genero, mes;",
            ),
        ],
        "ayudas": {
            "AY1": _ay(
                "Necesitas conservar todas las filas y, a la vez, calcular un total que va creciendo. Piensa en "
                "dos preguntas: ¿cada cuánto debe reiniciarse el acumulado (en qué grupo)? y ¿en qué orden se "
                "van sumando las filas dentro de ese grupo? Esas respuestas definen la ventana."
            ),
            "AY2": _ay(
                "Un ejemplo en otro contexto: en un colegio, para numerar a los estudiantes de cada curso según "
                "su nota sin colapsar las filas, la ventana se divide por curso (PARTITION BY) y se ordena por "
                "nota (ORDER BY dentro de OVER).",
                "SELECT curso, estudiante, nota,\n       RANK() OVER (PARTITION BY curso ORDER BY nota DESC) AS posicion\nFROM calificaciones;",
            ),
            "AY3": _ay(
                "Completa los espacios en blanco (___) con la columna que reinicia el acumulado y la que define "
                "el orden dentro de la ventana.",
                "SELECT genero, mes, unidades,\n       SUM(unidades) OVER (PARTITION BY ___ ORDER BY ___) AS acumulado\nFROM ventas_mensuales\nORDER BY genero, mes;",
            ),
            "AY4": _ay(
                "SUM(unidades) OVER (...) suma sin colapsar filas. PARTITION BY genero reinicia el acumulado en "
                "cada género y ORDER BY mes hace que cada fila sume desde el primer mes hasta el suyo. El ORDER "
                "BY final ordena el resultado por género y mes.",
                "SELECT genero, mes, unidades,\n       SUM(unidades) OVER (PARTITION BY genero ORDER BY mes) AS acumulado\nFROM ventas_mensuales\nORDER BY genero, mes;",
            ),
        },
    },
]


def _tiempo_referencia() -> dict | None:
    try:
        tiempos = cargar_reglas()["tiempo_referencia_seg"]
        return {k: int(v) for k, v in tiempos.items()}
    except (OSError, ValueError, KeyError, TypeError):
        log.warning("No se pudo leer tiempo_referencia_seg de reglas.json; no se siembran los desafíos.")
        return None


def sembrar_desafios(db: Session) -> None:
    """Idempotente: un desafío ya existente (mismo título) no se modifica."""
    tiempos = _tiempo_referencia()
    if tiempos is None:
        return
    conceptos = {c.codigo: c.id for c in db.scalars(select(Concepto))}
    existentes = set(db.scalars(select(Desafio.titulo)))
    for d in DESAFIOS:
        if d["titulo"] in existentes:
            continue
        if d["concepto"] not in conceptos or d["dificultad"] not in tiempos:
            log.warning("Desafío %r omitido: concepto o tiempo de referencia no disponible.", d["titulo"])
            continue
        db.add(
            Desafio(
                titulo=d["titulo"],
                enunciado=d["enunciado"],
                recursos=d["recursos"],
                concepto_id=conceptos[d["concepto"]],
                dificultad=d["dificultad"],
                esquema_sql=d["esquema"],
                sandbox_setup_sql=d["esquema"] + "\n" + d["datos"].strip(),
                solucion_referencia=d["solucion"],
                errores_tipicos=[{"descripcion": desc, "ejemplo": ej} for desc, ej in d["errores"]],
                ayudas_respaldo=d["ayudas"],
                tiempo_referencia_seg=tiempos[d["dificultad"]],
                activo=True,
            )
        )
    db.commit()
