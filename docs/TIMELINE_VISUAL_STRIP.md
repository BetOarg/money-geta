# Franja visual proporcional de timeline

El editor incorpora una franja horizontal desplazable con bloques que representan cada escena. El ancho del bloque refleja proporcionalmente su duración (con ancho mínimo para escenas breves). Cada bloque muestra número, descripción corta y segundos.

Al seleccionar un bloque, la escena se selecciona también en la tabla y el panel de edición. El modelo de geometría es independiente de Tkinter y tiene pruebas para escalado, separaciones, límites de duración y parámetros inválidos.

No es un preview audiovisual: no muestra fotogramas, reproducción, audio, transiciones ni render.
