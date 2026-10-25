"""Seeds idempotentes de los desafíos (6 del MVP + 4 de la entrega 3A + 3 de la entrega 3B = 13).

Los 3 de la 3B son segundos desafíos de filtrado (D2), ordenamiento (D2) y join (D1), con una dificultad
distinta a la del primero de su concepto, para que R8 pueda ofrecer uno más básico cuando sea posible.

Dominios: biblioteca, gimnasio, tienda de música, academia de cocina, festival de cine, club de
senderismo, cooperativa de café, clínica veterinaria, torneo de ajedrez y aeropuerto (el cuestionario
usa clientes/pedidos/productos).
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
    # ------------------------------------------------------------------ D1 conteo_agregacion
    {
        "titulo": "Resumen de inscripciones pagadas del taller",
        "concepto": "conteo_agregacion",
        "dificultad": "D1",
        "enunciado": (
            "Una academia de cocina quiere un resumen rápido de sus inscripciones ya pagadas (las que "
            "tienen fecha_pago registrada). Escribe una consulta que devuelva una sola fila con tres "
            "columnas, en este orden: la cantidad de inscripciones pagadas, el ingreso total (suma de "
            "precio) y el precio promedio de esas inscripciones."
        ),
        "recursos": [
            "COUNT cuenta filas, SUM suma una columna numérica, AVG calcula el promedio, MAX y MIN dan el mayor y el menor.",
            "Una consulta con funciones de agregación y sin GROUP BY devuelve una sola fila que resume todas las filas elegidas.",
            "WHERE se aplica antes de calcular la agregación; IS NOT NULL detecta valores presentes.",
        ],
        "esquema": (
            "CREATE TABLE inscripciones (\n"
            "  id_inscripcion INTEGER PRIMARY KEY,\n"
            "  participante TEXT NOT NULL,\n"
            "  taller TEXT NOT NULL,\n"
            "  precio INTEGER NOT NULL,\n"
            "  fecha_pago TEXT\n"
            ");"
        ),
        "datos": """
INSERT INTO inscripciones VALUES
 (1,'Marisol Vega','Panadería',80,'2025-09-02'),
 (2,'Hugo Prado','Cocina criolla',120,'2025-09-03'),
 (3,'Teresa Luna','Pastelería',100,NULL),
 (4,'Iván Cano','Panadería',80,'2025-09-10'),
 (5,'Noelia Rey','Pastelería',100,'2025-09-11'),
 (6,'Óscar Mena','Cocina criolla',120,NULL),
 (7,'Lidia Soto','Pastelería',100,'2025-09-14'),
 (8,'Ramiro Paz','Panadería',80,NULL),
 (9,'Gladys Ortiz','Cocina criolla',120,'2025-09-18'),
 (10,'Félix Arce','Pastelería',100,'2025-09-20');
""",
        "solucion": (
            "SELECT COUNT(*) AS inscripciones_pagadas,\n"
            "       SUM(precio) AS ingreso_total,\n"
            "       AVG(precio) AS precio_promedio\n"
            "FROM inscripciones\n"
            "WHERE fecha_pago IS NOT NULL;"
        ),
        "errores": [
            (
                "Olvidar el WHERE: se cuentan, suman y promedian también las inscripciones sin pago.",
                "SELECT COUNT(*), SUM(precio), AVG(precio) FROM inscripciones;",
            ),
            (
                "Contar solo las fechas de pago (COUNT ignora los vacíos) pero sumar y promediar sin filtrar: "
                "las tres columnas no hablan del mismo conjunto de filas.",
                "SELECT COUNT(fecha_pago), SUM(precio), AVG(precio) FROM inscripciones;",
            ),
            (
                "Usar MAX en lugar de AVG: devuelve el precio más alto, no el promedio.",
                "SELECT COUNT(*), SUM(precio), MAX(precio) FROM inscripciones WHERE fecha_pago IS NOT NULL;",
            ),
        ],
        "ayudas": {
            "AY1": _ay(
                "Se piden tres resúmenes de un mismo grupo de filas: cuántas hay, cuánto suman y cuánto vale "
                "una en promedio. Piensa primero qué filas deben entrar en los tres cálculos (¿cómo se "
                "reconoce una inscripción pagada?) y, después, qué función resume cada columna. Como todo "
                "se resume en un solo grupo, el resultado es una única fila."
            ),
            "AY2": _ay(
                "Un ejemplo en otro contexto: en un taller mecánico, para resumir las reparaciones ya "
                "entregadas (cuántas son y cuánto costaron en total y en promedio), el filtro de las "
                "entregadas se aplica en un único WHERE y las tres funciones de agregación van juntas en "
                "el SELECT, sin agrupar.",
                "SELECT COUNT(*) AS entregadas,\n       SUM(costo) AS costo_total,\n       AVG(costo) AS costo_promedio\n"
                "FROM reparaciones\nWHERE fecha_entrega IS NOT NULL;",
            ),
            "AY3": _ay(
                "Completa los espacios en blanco (___) con las funciones de agregación y la condición del filtro.",
                "SELECT ___(*) AS inscripciones_pagadas,\n       ___(precio) AS ingreso_total,\n"
                "       ___(precio) AS precio_promedio\nFROM inscripciones\nWHERE fecha_pago ___;",
            ),
            "AY4": _ay(
                "El WHERE deja solo las inscripciones con fecha de pago (IS NOT NULL). Sobre esas filas, "
                "COUNT(*) las cuenta, SUM(precio) suma lo recaudado y AVG(precio) calcula el precio "
                "promedio. Sin GROUP BY, el resultado es una sola fila con las tres columnas en el orden pedido.",
                "SELECT COUNT(*) AS inscripciones_pagadas,\n       SUM(precio) AS ingreso_total,\n"
                "       AVG(precio) AS precio_promedio\nFROM inscripciones\nWHERE fecha_pago IS NOT NULL;",
            ),
        },
    },
    # ------------------------------------------------------------------ D2 group_by
    {
        "titulo": "Funciones realizadas por sala del festival",
        "concepto": "group_by",
        "dificultad": "D2",
        "enunciado": (
            "Un festival de cine quiere comparar sus salas. Escribe una consulta que devuelva, para cada "
            "sala, el número de funciones realizadas y el total de entradas vendidas en esas funciones "
            "(las funciones canceladas no cuentan), en este orden de columnas: sala, funciones, entradas. "
            "Ordena de mayor a menor total de entradas; si dos salas empatan, ordénalas por nombre de sala "
            "(de la A a la Z)."
        ),
        "recursos": [
            "GROUP BY agrupa las filas que comparten el mismo valor y produce una fila por grupo.",
            "En un SELECT con GROUP BY, cada columna debe ser una de las agrupadas o estar resumida con COUNT, SUM, AVG...",
            "WHERE filtra las filas antes de agrupar; ORDER BY puede usar el nombre (alias) de una columna calculada.",
        ],
        "esquema": (
            "CREATE TABLE funciones (\n"
            "  id_funcion INTEGER PRIMARY KEY,\n"
            "  pelicula TEXT NOT NULL,\n"
            "  sala TEXT NOT NULL,\n"
            "  estado TEXT NOT NULL,\n"
            "  entradas_vendidas INTEGER NOT NULL\n"
            ");"
        ),
        "datos": """
INSERT INTO funciones VALUES
 (1,'Luz de otoño','Sala Azul','Realizada',90),
 (2,'Sombras en el puerto','Sala Azul','Realizada',70),
 (3,'Luz de otoño','Sala Azul','Cancelada',40),
 (4,'Las dos orillas','Sala Roja','Realizada',80),
 (5,'Sombras en el puerto','Sala Roja','Realizada',70),
 (6,'Las dos orillas','Sala Roja','Cancelada',55),
 (7,'Luz de otoño','Sala Verde','Realizada',150),
 (8,'Cartas sin sello','Sala Verde','Cancelada',30),
 (9,'Cartas sin sello','Sala Dorada','Realizada',60),
 (10,'Las dos orillas','Sala Dorada','Realizada',50),
 (11,'Luz de otoño','Sala Dorada','Realizada',40),
 (12,'Cartas sin sello','Sala Azul','Realizada',20);
""",
        "solucion": (
            "SELECT sala, COUNT(*) AS funciones, SUM(entradas_vendidas) AS entradas\n"
            "FROM funciones\nWHERE estado = 'Realizada'\nGROUP BY sala\n"
            "ORDER BY entradas DESC, sala ASC;"
        ),
        "errores": [
            (
                "Olvidar GROUP BY: las funciones de agregación resumen toda la tabla en una sola fila en vez de una por sala.",
                "SELECT sala, COUNT(*) AS funciones, SUM(entradas_vendidas) AS entradas FROM funciones "
                "WHERE estado = 'Realizada' ORDER BY entradas DESC, sala ASC;",
            ),
            (
                "Agrupar por una columna distinta (pelicula): el resumen sale por película y no por sala.",
                "SELECT pelicula, COUNT(*) AS funciones, SUM(entradas_vendidas) AS entradas FROM funciones "
                "WHERE estado = 'Realizada' GROUP BY pelicula ORDER BY entradas DESC, pelicula ASC;",
            ),
            (
                "Olvidar excluir las funciones canceladas: sus entradas se suman al total de cada sala.",
                "SELECT sala, COUNT(*) AS funciones, SUM(entradas_vendidas) AS entradas FROM funciones "
                "GROUP BY sala ORDER BY entradas DESC, sala ASC;",
            ),
        ],
        "ayudas": {
            "AY1": _ay(
                "El resultado debe tener una fila por sala, no una por función. Piensa qué columna define "
                "los grupos y qué dos resúmenes necesita cada grupo. Después decide qué filas deben entrar "
                "antes de agrupar (¿cuentan las canceladas?) y cómo ordenar los grupos ya resumidos, "
                "recordando el criterio de desempate."
            ),
            "AY2": _ay(
                "Un ejemplo en otro contexto: en una empresa de transporte, para ver por ciudad de destino "
                "cuántos viajes completados hubo y cuántos pasajeros viajaron, primero se filtran los viajes "
                "completados, luego se agrupa por destino y cada grupo se resume con COUNT y SUM.",
                "SELECT destino, COUNT(*) AS viajes, SUM(pasajeros) AS total_pasajeros\nFROM viajes\n"
                "WHERE estado = 'Completado'\nGROUP BY destino\nORDER BY destino;",
            ),
            "AY3": _ay(
                "Completa los espacios en blanco (___) con la condición del filtro, la columna que forma "
                "los grupos y el criterio de orden.",
                "SELECT sala, COUNT(*) AS funciones, SUM(entradas_vendidas) AS entradas\nFROM funciones\n"
                "WHERE estado = ___\nGROUP BY ___\nORDER BY ___ DESC, sala ASC;",
            ),
            "AY4": _ay(
                "WHERE estado = 'Realizada' descarta las funciones canceladas antes de agrupar. GROUP BY sala "
                "crea un grupo por sala, y COUNT(*) y SUM(entradas_vendidas) resumen cada grupo. Por último, "
                "ORDER BY entradas DESC ordena de mayor a menor y sala ASC desempata alfabéticamente.",
                "SELECT sala, COUNT(*) AS funciones, SUM(entradas_vendidas) AS entradas\nFROM funciones\n"
                "WHERE estado = 'Realizada'\nGROUP BY sala\nORDER BY entradas DESC, sala ASC;",
            ),
        },
    },
    # ------------------------------------------------------------------ D2 left_join
    {
        "titulo": "Guías y sus excursiones desde noviembre",
        "concepto": "left_join",
        "dificultad": "D2",
        "enunciado": (
            "Un club de senderismo quiere revisar la carga de sus guías. Escribe una consulta que devuelva "
            "el nombre de cada guía y la ruta de sus excursiones programadas desde el 2025-11-01 (inclusive; "
            "las fechas son texto 'AAAA-MM-DD'). Todos los guías deben aparecer: si un guía no tiene "
            "excursiones en ese periodo, debe salir una sola vez con la ruta vacía (NULL). Columnas: nombre "
            "y ruta, en ese orden. Ordena por nombre del guía y luego por ruta."
        ),
        "recursos": [
            "JOIN solo conserva las filas que tienen pareja en ambas tablas; LEFT JOIN conserva todas las de la tabla izquierda.",
            "Cuando no hay pareja, las columnas de la tabla derecha salen como NULL.",
            "Una condición en el ON limita las filas que se unen; una condición en el WHERE filtra el resultado final.",
        ],
        "esquema": (
            "CREATE TABLE guias (\n"
            "  id_guia INTEGER PRIMARY KEY,\n"
            "  nombre TEXT NOT NULL\n"
            ");\n"
            "CREATE TABLE excursiones (\n"
            "  id_excursion INTEGER PRIMARY KEY,\n"
            "  id_guia INTEGER NOT NULL REFERENCES guias(id_guia),\n"
            "  ruta TEXT NOT NULL,\n"
            "  fecha TEXT NOT NULL,\n"
            "  cupo INTEGER NOT NULL\n"
            ");"
        ),
        "datos": """
INSERT INTO guias VALUES
 (1,'Alicia Huamán'),
 (2,'Bruno Cárdenas'),
 (3,'Carmen Ledesma'),
 (4,'Darío Pinto'),
 (5,'Elsa Tapia');
INSERT INTO excursiones VALUES
 (1,1,'Cordillera Blanca','2025-11-08',12),
 (2,1,'Lomas de Lachay','2025-12-06',8),
 (3,2,'Laguna Humantay','2025-10-18',15),
 (4,2,'Valle de Lares','2025-11-22',10),
 (5,3,'Cañón de Cotahuasi','2025-09-27',6),
 (6,5,'Laguna Humantay','2025-11-01',14),
 (7,1,'Valle de Lares','2025-10-31',9);
""",
        "solucion": (
            "SELECT g.nombre, e.ruta\nFROM guias g\n"
            "LEFT JOIN excursiones e ON e.id_guia = g.id_guia AND e.fecha >= '2025-11-01'\n"
            "ORDER BY g.nombre, e.ruta;"
        ),
        "errores": [
            (
                "Usar JOIN en lugar de LEFT JOIN: los guías sin excursiones en el periodo desaparecen del resultado.",
                "SELECT g.nombre, e.ruta FROM guias g JOIN excursiones e ON e.id_guia = g.id_guia "
                "AND e.fecha >= '2025-11-01' ORDER BY g.nombre, e.ruta;",
            ),
            (
                "Poner el filtro de fecha en el WHERE: elimina las filas con ruta NULL y el LEFT JOIN pierde su efecto.",
                "SELECT g.nombre, e.ruta FROM guias g LEFT JOIN excursiones e ON e.id_guia = g.id_guia "
                "WHERE e.fecha >= '2025-11-01' ORDER BY g.nombre, e.ruta;",
            ),
            (
                "Poner la tabla de guías a la derecha del LEFT JOIN: se conservan las excursiones, no los guías.",
                "SELECT g.nombre, e.ruta FROM excursiones e LEFT JOIN guias g ON g.id_guia = e.id_guia "
                "WHERE e.fecha >= '2025-11-01' ORDER BY g.nombre, e.ruta;",
            ),
        ],
        "ayudas": {
            "AY1": _ay(
                "La clave está en qué tabla debe conservar todas sus filas aunque no encuentre pareja. "
                "Pregúntate cuál es esa tabla y en qué posición de la unión debe ir. Luego piensa dónde "
                "colocar la condición de la fecha: ¿antes de unir, para limitar qué excursiones se emparejan, "
                "o después, sobre el resultado ya unido? Fíjate qué pasaría con un guía sin excursiones "
                "en cada caso."
            ),
            "AY2": _ay(
                "Un ejemplo en otro contexto: en una escuela, para listar todos los profesores con los "
                "cursos que dictan este año, incluidos los que no dictan ninguno, la tabla de profesores va "
                "a la izquierda y la condición del año se escribe en el ON de la unión.",
                "SELECT pr.nombre, c.titulo\nFROM profesores pr\n"
                "LEFT JOIN cursos c ON c.id_profesor = pr.id_profesor AND c.anio = 2025\nORDER BY pr.nombre;",
            ),
            "AY3": _ay(
                "Completa los espacios en blanco (___) con el tipo de unión y con la condición de fecha, que va dentro del ON.",
                "SELECT g.nombre, e.ruta\nFROM guias g\n___ excursiones e ON e.id_guia = g.id_guia AND e.fecha ___ '2025-11-01'\n"
                "ORDER BY g.nombre, e.ruta;",
            ),
            "AY4": _ay(
                "La tabla guias va a la izquierda y se une con LEFT JOIN, así que ningún guía se pierde. "
                "La condición e.fecha >= '2025-11-01' está en el ON: limita qué excursiones se emparejan "
                "sin descartar guías, que quedan con ruta NULL si no tienen ninguna. El ORDER BY ordena por "
                "guía y luego por ruta.",
                "SELECT g.nombre, e.ruta\nFROM guias g\nLEFT JOIN excursiones e ON e.id_guia = g.id_guia AND e.fecha >= '2025-11-01'\n"
                "ORDER BY g.nombre, e.ruta;",
            ),
        },
    },
    # ------------------------------------------------------------------ D3 join_agregacion
    {
        "titulo": "Pagos de la cooperativa de café por región en octubre",
        "concepto": "join_agregacion",
        "dificultad": "D3",
        "enunciado": (
            "Una cooperativa de café quiere conocer lo que pagó en octubre de 2025 (las fechas son texto "
            "'AAAA-MM-DD'). Escribe una consulta que devuelva, para cada región con entregas ese mes, "
            "cuántos productores distintos entregaron café y el total pagado (kilos multiplicados por "
            "precio_kilo de cada entrega, sumados). Columnas: region, productores, total_pagado. "
            "Ordena de mayor a menor total pagado; si dos regiones empatan, por nombre de región (A a Z)."
        ),
        "recursos": [
            "JOIN une cada productor con sus entregas; después GROUP BY resume las filas unidas por grupo.",
            "COUNT(*) cuenta filas unidas; COUNT(DISTINCT columna) cuenta valores distintos de esa columna.",
            "Dentro de una agregación se pueden usar expresiones, por ejemplo SUM(a * b).",
        ],
        "esquema": (
            "CREATE TABLE productores (\n"
            "  id_productor INTEGER PRIMARY KEY,\n"
            "  nombre TEXT NOT NULL,\n"
            "  region TEXT NOT NULL\n"
            ");\n"
            "CREATE TABLE entregas (\n"
            "  id_entrega INTEGER PRIMARY KEY,\n"
            "  id_productor INTEGER NOT NULL REFERENCES productores(id_productor),\n"
            "  fecha TEXT NOT NULL,\n"
            "  kilos INTEGER NOT NULL,\n"
            "  precio_kilo INTEGER NOT NULL\n"
            ");"
        ),
        "datos": """
INSERT INTO productores VALUES
 (1,'Rosa Quispe','Cusco'),
 (2,'Luis Mamani','Cusco'),
 (3,'Ana Flores','Junín'),
 (4,'Mario Pérez','Junín'),
 (5,'Julia Díaz','Junín'),
 (6,'Pedro Rojas','Cajamarca'),
 (7,'Sara Vela','Cajamarca'),
 (8,'Tomás Ruiz','San Martín');
INSERT INTO entregas VALUES
 (1,1,'2025-10-03',100,20),
 (2,1,'2025-10-17',80,22),
 (3,2,'2025-10-10',60,20),
 (4,3,'2025-10-05',120,18),
 (5,3,'2025-10-19',90,18),
 (6,4,'2025-10-12',70,25),
 (7,5,'2025-09-28',200,18),
 (8,6,'2025-10-08',150,20),
 (9,6,'2025-11-02',100,20),
 (10,7,'2025-10-25',70,28),
 (11,8,'2025-09-15',80,21),
 (12,2,'2025-09-30',50,20),
 (13,5,'2025-10-28',30,18);
""",
        "solucion": (
            "SELECT p.region,\n"
            "       COUNT(DISTINCT p.id_productor) AS productores,\n"
            "       SUM(e.kilos * e.precio_kilo) AS total_pagado\n"
            "FROM productores p\n"
            "JOIN entregas e ON e.id_productor = p.id_productor\n"
            "WHERE e.fecha >= '2025-10-01' AND e.fecha < '2025-11-01'\n"
            "GROUP BY p.region\n"
            "ORDER BY total_pagado DESC, p.region ASC;"
        ),
        "errores": [
            (
                "Contar con COUNT(*): cuenta entregas, no productores; un productor con dos entregas se cuenta dos veces.",
                "SELECT p.region, COUNT(*) AS productores, SUM(e.kilos * e.precio_kilo) AS total_pagado "
                "FROM productores p JOIN entregas e ON e.id_productor = p.id_productor "
                "WHERE e.fecha >= '2025-10-01' AND e.fecha < '2025-11-01' "
                "GROUP BY p.region ORDER BY total_pagado DESC, p.region ASC;",
            ),
            (
                "Agrupar por el nombre del productor en lugar de por la región: sale una fila por productor.",
                "SELECT p.nombre, COUNT(DISTINCT p.id_productor) AS productores, SUM(e.kilos * e.precio_kilo) AS total_pagado "
                "FROM productores p JOIN entregas e ON e.id_productor = p.id_productor "
                "WHERE e.fecha >= '2025-10-01' AND e.fecha < '2025-11-01' "
                "GROUP BY p.nombre ORDER BY total_pagado DESC, p.nombre ASC;",
            ),
            (
                "Olvidar el filtro de octubre: se cuentan y pagan también las entregas de otros meses.",
                "SELECT p.region, COUNT(DISTINCT p.id_productor) AS productores, SUM(e.kilos * e.precio_kilo) AS total_pagado "
                "FROM productores p JOIN entregas e ON e.id_productor = p.id_productor "
                "GROUP BY p.region ORDER BY total_pagado DESC, p.region ASC;",
            ),
        ],
        "ayudas": {
            "AY1": _ay(
                "Los datos de región y de kilos y precios están en tablas distintas, así que primero hay que "
                "unirlas; después se resume por región. Piensa en tres cosas: qué columna une las dos tablas, "
                "qué columna define los grupos y qué debe contar exactamente «productores»: ¿filas unidas o "
                "personas distintas? Para el total pagado, recuerda que cada entrega tiene su propio precio."
            ),
            "AY2": _ay(
                "Un ejemplo en otro contexto: en una escuela, para saber por curso cuántos estudiantes "
                "distintos rindieron examen en junio y cuántos puntos sumaron en total, se unen estudiantes "
                "con exámenes, se filtra el mes, se agrupa por curso y se cuentan estudiantes sin repetir.",
                "SELECT e.curso, COUNT(DISTINCT e.id_estudiante) AS estudiantes, SUM(x.puntos) AS total_puntos\n"
                "FROM estudiantes e\nJOIN examenes x ON x.id_estudiante = e.id_estudiante\n"
                "WHERE x.fecha >= '2025-06-01' AND x.fecha < '2025-07-01'\nGROUP BY e.curso\nORDER BY e.curso;",
            ),
            "AY3": _ay(
                "Completa los espacios en blanco (___) con la forma de contar productores sin repetirlos y "
                "con la columna que forma los grupos.",
                "SELECT p.region,\n       COUNT(___ p.id_productor) AS productores,\n"
                "       SUM(e.kilos * e.precio_kilo) AS total_pagado\nFROM productores p\n"
                "JOIN entregas e ON e.id_productor = p.id_productor\n"
                "WHERE e.fecha >= '2025-10-01' AND e.fecha < '2025-11-01'\nGROUP BY ___\n"
                "ORDER BY total_pagado DESC, p.region ASC;",
            ),
            "AY4": _ay(
                "El JOIN une cada productor con sus entregas y el WHERE conserva solo las de octubre. "
                "GROUP BY p.region crea un grupo por región; COUNT(DISTINCT p.id_productor) cuenta cada "
                "productor una sola vez aunque haya entregado varias veces, y SUM(e.kilos * e.precio_kilo) "
                "suma lo pagado en cada entrega. El ORDER BY ordena por total y desempata por región.",
                "SELECT p.region,\n       COUNT(DISTINCT p.id_productor) AS productores,\n"
                "       SUM(e.kilos * e.precio_kilo) AS total_pagado\nFROM productores p\n"
                "JOIN entregas e ON e.id_productor = p.id_productor\n"
                "WHERE e.fecha >= '2025-10-01' AND e.fecha < '2025-11-01'\nGROUP BY p.region\n"
                "ORDER BY total_pagado DESC, p.region ASC;",
            ),
        },
    },
    # ------------------------------------------------------------------ D2 filtrado (2.º, entrega 3B)
    {
        "titulo": "Citas veterinarias de perros y gatos del tercer trimestre",
        "concepto": "filtrado",
        "dificultad": "D2",
        "enunciado": (
            "La clínica veterinaria revisa su facturación del tercer trimestre. Escribe una consulta que "
            "devuelva la mascota, la fecha y el costo de las citas que cumplan todo esto: la mascota es un "
            "perro o un gato, la cita ya fue atendida, su fecha está entre el 2025-07-01 y el 2025-09-30 "
            "(ambas fechas incluidas) y el costo es de 80 o más. Las columnas van en ese orden."
        ),
        "recursos": [
            "IN ('a', 'b') comprueba si un valor está en una lista; equivale a varias comparaciones con OR.",
            "BETWEEN x AND y incluye los dos extremos del rango.",
            "AND se evalúa antes que OR: si mezclas ambos, usa paréntesis para dejar clara la intención.",
        ],
        "esquema": (
            "CREATE TABLE citas (\n"
            "  id_cita INTEGER PRIMARY KEY,\n"
            "  mascota TEXT NOT NULL,\n"
            "  especie TEXT NOT NULL,\n"
            "  motivo TEXT NOT NULL,\n"
            "  fecha TEXT NOT NULL,\n"
            "  estado TEXT NOT NULL,\n"
            "  costo INTEGER NOT NULL\n"
            ");"
        ),
        "datos": """
INSERT INTO citas VALUES
 (1,'Luna','Perro','Vacunación','2025-07-01','Atendida',80),
 (2,'Michi','Gato','Control','2025-07-15','Atendida',60),
 (3,'Rocky','Perro','Cirugía','2025-08-10','Atendida',350),
 (4,'Nala','Gato','Esterilización','2025-09-30','Atendida',120),
 (5,'Toby','Perro','Control','2025-09-12','Cancelada',90),
 (6,'Pelusa','Conejo','Control','2025-08-05','Atendida',100),
 (7,'Simba','Gato','Vacunación','2025-10-02','Atendida',85),
 (8,'Coco','Loro','Revisión','2025-07-20','Atendida',150),
 (9,'Max','Perro','Limpieza dental','2025-06-28','Atendida',200),
 (10,'Kira','Perro','Control','2025-08-22','Pendiente',95),
 (11,'Mía','Gato','Vacunación','2025-09-05','Atendida',80),
 (12,'Bruno','Perro','Radiografía','2025-09-18','Atendida',140),
 (13,'Cleo','Gato','Control','2025-08-30','Cancelada',70),
 (14,'Thor','Perro','Control','2025-07-08','Atendida',45);
""",
        "solucion": (
            "SELECT mascota, fecha, costo\nFROM citas\n"
            "WHERE especie IN ('Perro', 'Gato')\n"
            "  AND estado = 'Atendida'\n"
            "  AND fecha BETWEEN '2025-07-01' AND '2025-09-30'\n"
            "  AND costo >= 80;"
        ),
        "errores": [
            (
                "Mezclar OR con AND sin paréntesis: AND se evalúa primero, así que todos los perros pasan "
                "sin cumplir las demás condiciones.",
                "SELECT mascota, fecha, costo FROM citas WHERE especie = 'Perro' OR especie = 'Gato' "
                "AND estado = 'Atendida' AND fecha BETWEEN '2025-07-01' AND '2025-09-30' AND costo >= 80;",
            ),
            (
                "Usar > y < en las fechas: las citas del 2025-07-01 y del 2025-09-30 quedan fuera, pero el "
                "enunciado las incluye.",
                "SELECT mascota, fecha, costo FROM citas WHERE especie IN ('Perro', 'Gato') "
                "AND estado = 'Atendida' AND fecha > '2025-07-01' AND fecha < '2025-09-30' AND costo >= 80;",
            ),
            (
                "Excluir solo las citas canceladas (<> 'Cancelada'): las citas pendientes todavía no se "
                "atendieron y no deben contarse.",
                "SELECT mascota, fecha, costo FROM citas WHERE especie IN ('Perro', 'Gato') "
                "AND estado <> 'Cancelada' AND fecha BETWEEN '2025-07-01' AND '2025-09-30' AND costo >= 80;",
            ),
        ],
        "ayudas": {
            "AY1": _ay(
                "Hay cuatro condiciones y todas deben cumplirse a la vez. Anota cada una por separado: sobre "
                "qué columna actúa y si el límite se incluye o no. Fíjate en que «perro o gato» es una sola "
                "condición sobre la especie; piensa cómo expresarla sin que afecte a las demás."
            ),
            "AY2": _ay(
                "Un ejemplo en otro contexto: en un colegio, para listar las notas de Álgebra o Física "
                "aprobadas (14 o más) rendidas durante el primer semestre, se agrupa la lista de cursos con "
                "IN, el rango de fechas con BETWEEN y el resto con AND.",
                "SELECT alumno, curso, nota\nFROM notas\nWHERE curso IN ('Álgebra', 'Física')\n"
                "  AND fecha BETWEEN '2025-03-01' AND '2025-07-15'\n  AND nota >= 14;",
            ),
            "AY3": _ay(
                "Completa los espacios en blanco (___) con los valores que faltan en las condiciones.",
                "SELECT mascota, fecha, costo\nFROM citas\nWHERE especie IN ('Perro', ___)\n"
                "  AND estado = ___\n  AND fecha BETWEEN '2025-07-01' AND ___\n  AND costo >= 80;",
            ),
            "AY4": _ay(
                "Se filtra la tabla citas con cuatro condiciones unidas por AND: la especie dentro de la lista "
                "('Perro', 'Gato'), el estado igual a 'Atendida', la fecha dentro del rango con BETWEEN (que "
                "incluye ambos extremos) y el costo mayor o igual a 80.",
                "SELECT mascota, fecha, costo\nFROM citas\nWHERE especie IN ('Perro', 'Gato')\n"
                "  AND estado = 'Atendida'\n  AND fecha BETWEEN '2025-07-01' AND '2025-09-30'\n  AND costo >= 80;",
            ),
        },
    },
    # ------------------------------------------------------------------ D2 ordenamiento (2.º, entrega 3B)
    {
        "titulo": "Podio del torneo de ajedrez del colegio",
        "concepto": "ordenamiento",
        "dificultad": "D2",
        "enunciado": (
            "El colegio publica el podio de su torneo de ajedrez. Escribe una consulta que devuelva el "
            "nombre, el club y los puntos de los 5 mejores jugadores. Se ordena de mayor a menor puntaje; "
            "si dos jugadores empatan en puntos, va primero quien jugó menos partidas; si aún empatan, se "
            "ordenan alfabéticamente por nombre (de la A a la Z). Las columnas van en ese orden."
        ),
        "recursos": [
            "ORDER BY admite varias columnas: la primera tiene prioridad y cada una tiene su propio ASC o DESC.",
            "LIMIT n devuelve solo las primeras n filas del resultado ya ordenado.",
            "Puedes ordenar por una columna aunque no la muestres en el SELECT.",
        ],
        "esquema": (
            "CREATE TABLE jugadores (\n"
            "  id_jugador INTEGER PRIMARY KEY,\n"
            "  nombre TEXT NOT NULL,\n"
            "  club TEXT NOT NULL,\n"
            "  puntos REAL NOT NULL,\n"
            "  partidas INTEGER NOT NULL\n"
            ");"
        ),
        "datos": """
INSERT INTO jugadores VALUES
 (1,'Sofía Quispe','Torre Blanca',7.5,9),
 (2,'Diego Paredes','Alfil Negro',7.5,8),
 (3,'Lucía Ramos','Torre Blanca',6.5,9),
 (4,'Mateo Flores','Caballo Real',8.0,9),
 (5,'Valentina Rojas','Alfil Negro',6.5,7),
 (6,'Gabriel Núñez','Caballo Real',6.5,7),
 (7,'Renata Cruz','Torre Blanca',5.5,8),
 (8,'Joaquín Vega','Alfil Negro',6.5,9),
 (9,'Daniela Huamán','Caballo Real',4.0,6);
""",
        "solucion": (
            "SELECT nombre, club, puntos\nFROM jugadores\n"
            "ORDER BY puntos DESC, partidas ASC, nombre ASC\nLIMIT 5;"
        ),
        "errores": [
            (
                "Poner el nombre antes que las partidas: el primer desempate pasa a ser el alfabeto y cambia "
                "quién entra al podio entre los de 6.5 puntos.",
                "SELECT nombre, club, puntos FROM jugadores ORDER BY puntos DESC, nombre, partidas LIMIT 5;",
            ),
            (
                "Ordenar las partidas de mayor a menor: el desempate favorece a quien jugó más, y el "
                "enunciado pide lo contrario.",
                "SELECT nombre, club, puntos FROM jugadores "
                "ORDER BY puntos DESC, partidas DESC, nombre LIMIT 5;",
            ),
            (
                "Olvidar LIMIT: la consulta devuelve a los 9 jugadores en vez de solo los 5 mejores.",
                "SELECT nombre, club, puntos FROM jugadores ORDER BY puntos DESC, partidas, nombre;",
            ),
        ],
        "ayudas": {
            "AY1": _ay(
                "Primero decide cuántos criterios de orden hay y cuál tiene prioridad sobre cuál. Para cada uno "
                "piensa si debe ir de mayor a menor o de menor a mayor: «jugó menos partidas» no se ordena igual "
                "que «tiene más puntos». Después piensa cómo quedarte solo con los primeros 5 resultados."
            ),
            "AY2": _ay(
                "Un ejemplo en otro contexto: en una liga de fútbol, para mostrar los 3 primeros de la tabla se "
                "ordena por puntos de mayor a menor, luego por diferencia de goles de mayor a menor y, si aún "
                "empatan, por nombre del equipo; al final se limita a 3 filas.",
                "SELECT equipo, puntos\nFROM clasificacion\nORDER BY puntos DESC, diferencia_gol DESC, equipo ASC\nLIMIT 3;",
            ),
            "AY3": _ay(
                "Completa los espacios en blanco (___) con el sentido de cada criterio y la cantidad de filas.",
                "SELECT nombre, club, puntos\nFROM jugadores\nORDER BY puntos ___, partidas ___, nombre\nLIMIT ___;",
            ),
            "AY4": _ay(
                "Se ordena por puntos de mayor a menor (DESC); a igualdad de puntos, por partidas de menor a "
                "mayor (ASC, porque gana quien jugó menos) y, si aún hay empate, por nombre. LIMIT 5 conserva "
                "solo las 5 primeras filas del resultado ya ordenado.",
                "SELECT nombre, club, puntos\nFROM jugadores\nORDER BY puntos DESC, partidas ASC, nombre ASC\nLIMIT 5;",
            ),
        },
    },
    # ------------------------------------------------------------------ D1 join (2.º, entrega 3B)
    {
        "titulo": "Pantalla de salidas del aeropuerto con su aerolínea",
        "concepto": "join",
        "dificultad": "D1",
        "enunciado": (
            "El aeropuerto prepara la pantalla de salidas. Escribe una consulta que devuelva, para cada vuelo, "
            "su código, su destino y el nombre de su aerolínea, en ese orden."
        ),
        "recursos": [
            "JOIN ... ON une dos tablas usando una condición entre columnas relacionadas.",
            "Un alias (por ejemplo vuelos v) acorta el nombre de la tabla; úsalo para indicar de qué tabla "
            "viene cada columna.",
            "La columna que apunta a otra tabla (clave foránea) se compara con la clave primaria de esa tabla.",
        ],
        "esquema": (
            "CREATE TABLE aerolineas (\n"
            "  id_aerolinea INTEGER PRIMARY KEY,\n"
            "  nombre TEXT NOT NULL,\n"
            "  pais TEXT NOT NULL\n"
            ");\n"
            "CREATE TABLE vuelos (\n"
            "  id_vuelo INTEGER PRIMARY KEY,\n"
            "  codigo TEXT NOT NULL,\n"
            "  id_aerolinea INTEGER NOT NULL REFERENCES aerolineas(id_aerolinea),\n"
            "  destino TEXT NOT NULL,\n"
            "  hora_salida TEXT NOT NULL\n"
            ");"
        ),
        "datos": """
INSERT INTO aerolineas VALUES
 (1,'Andes Air','Perú'),
 (2,'Pacífico Jet','Chile'),
 (3,'Cóndor Express','Perú'),
 (4,'Altiplano Aéreo','Bolivia');
INSERT INTO vuelos VALUES
 (1,'PJ101',2,'Cusco','06:30'),
 (2,'AN205',1,'Arequipa','07:15'),
 (3,'CE310',3,'Piura','08:00'),
 (4,'AN311',1,'Iquitos','09:20'),
 (5,'PJ118',2,'Tacna','10:45'),
 (6,'AN402',1,'Trujillo','12:10'),
 (7,'CE415',3,'Cusco','13:35');
""",
        "solucion": (
            "SELECT v.codigo, v.destino, a.nombre\nFROM vuelos v\n"
            "JOIN aerolineas a ON a.id_aerolinea = v.id_aerolinea;"
        ),
        "errores": [
            (
                "Olvidar la condición ON: cada vuelo se combina con todas las aerolíneas (producto cartesiano).",
                "SELECT v.codigo, v.destino, a.nombre FROM vuelos v JOIN aerolineas a;",
            ),
            (
                "Unir columnas que no se corresponden (id_aerolinea con id_vuelo): a varios vuelos les toca "
                "una aerolínea que no es la suya.",
                "SELECT v.codigo, v.destino, a.nombre FROM vuelos v "
                "JOIN aerolineas a ON a.id_aerolinea = v.id_vuelo;",
            ),
            (
                "Mostrar el número de la aerolínea en lugar de su nombre: el dato ya está en vuelos y el JOIN "
                "no se aprovecha.",
                "SELECT v.codigo, v.destino, v.id_aerolinea FROM vuelos v "
                "JOIN aerolineas a ON a.id_aerolinea = v.id_aerolinea;",
            ),
        ],
        "ayudas": {
            "AY1": _ay(
                "El código y el destino están en una tabla y el nombre de la aerolínea en otra. Piensa qué "
                "columna de vuelos señala a qué aerolínea pertenece cada vuelo y con qué columna de aerolineas "
                "coincide. Esa coincidencia es la condición que une las dos tablas."
            ),
            "AY2": _ay(
                "Un ejemplo en otro contexto: en un taller mecánico, para mostrar la placa de cada reparación "
                "junto al nombre del mecánico que la hizo, se une reparaciones con mecánicos por la columna que "
                "los relaciona.",
                "SELECT r.placa, m.nombre\nFROM reparaciones r\nJOIN mecanicos m ON m.id_mecanico = r.id_mecanico;",
            ),
            "AY3": _ay(
                "Completa los espacios en blanco (___) con las columnas que relacionan las dos tablas.",
                "SELECT v.codigo, v.destino, a.nombre\nFROM vuelos v\nJOIN aerolineas a ON a.___ = v.___;",
            ),
            "AY4": _ay(
                "Se parte de vuelos y se une con aerolineas comparando la clave primaria de la aerolínea con la "
                "columna id_aerolinea de cada vuelo. Así, cada fila trae el código y el destino del vuelo "
                "junto al nombre de su aerolínea.",
                "SELECT v.codigo, v.destino, a.nombre\nFROM vuelos v\nJOIN aerolineas a ON a.id_aerolinea = v.id_aerolinea;",
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
