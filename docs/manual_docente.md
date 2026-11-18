# Manual del docente

Tu cuenta la crea el administrador (página **Usuarios**). Al iniciar sesión entras al **Banco de desafíos**; el menú tiene **Banco de desafíos**, **Reportes** y **Perfil**. No ves estudiantes individuales: solo datos agregados.

## 1. Banco de desafíos
La lista muestra título, concepto, dificultad (D1 a D3), tiempo de referencia y estado, con filtros por concepto, dificultad y estado (**Activos**, **Desactivados**, **Todos**) y búsqueda por título. Cada fila permite editar, **Activar** o **Desactivar** y **Eliminar**.
- **Desactivar** oculta el desafío a los estudiantes pero conserva su historial: úsalo en lugar de borrar. Si alguien lo tenía en curso, verá que ya no está disponible.
- **Eliminar** solo aparece en los desafíos sin sesiones («Sin sesiones» en la lista); uno que ya se usó solo se desactiva.

## 2. Crear o editar un desafío
Pulsa **Nuevo desafío** y completa las secciones:
1. **Datos generales:** título (único), concepto, dificultad, enunciado, recursos (uno por línea) y tiempo de referencia (vacío = el de la dificultad).
2. **Base de datos y solución:** el **esquema** (los `CREATE TABLE` que ve el estudiante), los **datos de prueba (setup)** y la **solución de referencia**. Ni el setup ni la solución se muestran al estudiante.
3. **Errores típicos:** exactamente 3, cada uno con descripción y una consulta de ejemplo que debe **fallar**.
4. **Ayudas de respaldo (AY1 a AY4):** se usan cuando la IA no responde o su respuesta no pasa los controles. AY1 sin código; AY2 con un ejemplo de **otras tablas y otro dominio**; AY3 con al menos dos `___`; AY4 con la solución explicada.

**Vista previa** muestra cómo lo verá el estudiante. **Validar sin guardar** ejecuta los controles; **Crear desafío** o **Guardar cambios** los ejecuta y guarda solo si todo pasa. Los problemas salen junto al campo que hay que corregir.

**Buenas prácticas de contenido:** un dominio distinto al del cuestionario de diagnóstico; datos que distingan una consulta correcta de una casi correcta; el enunciado fija el orden de las columnas; si el orden importa, la solución lleva `ORDER BY` que desempate.

Si cambias la solución o el setup de un desafío que ya se usó, se pide confirmación (**Guardar de todos modos**): los resultados ya registrados no cambian, solo cómo se evalúan los intentos futuros.

## 3. Reportes
**Reportes** muestra, para un rango de fechas: uso por semana, desempeño por concepto y dificultad, distribución del nivel de ayuda, ayudas por tipo y valoraciones, retiros y refuerzos, y los indicadores de **¿Funciona el retiro de la ayuda?** (conceptos que llegan a nivel 0 sin recaída, desafíos hasta el primer retiro, proporción de aciertos sin ayuda, activaciones de las reglas de dependencia y de ensayo y error, y precisión del nivel inicial).
- Todo es agregado y con seudónimos. Los grupos de **menos de 3 estudiantes** salen como «Oculto» para que nadie sea identificable (umbral provisional).
- **Descargar datos seudonimizados (CSV)** baja intentos, ayudas, cambios de nivel o indicadores, o todo en un ZIP. Los archivos no llevan nombres, correos ni el código de los estudiantes. Trátalos como datos de investigación y no los subas al repositorio.
- Con pocos estudiantes, interpreta con cautela: los porcentajes sobre grupos pequeños cambian mucho con un solo caso.
