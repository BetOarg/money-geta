# Transiciones por escena — borrador

El editor ofrece transición entrante por escena:
- Corte (duración 0).
- Fade, dissolve o slide (duración positiva).
- La duración no puede superar la duración de la escena.
- Los valores se validan y guardan como metadata local.

La transición aún no se dibuja ni se ejecuta en preview o render; queda preparada como dato para la siguiente integración.


La duración total del preview descuenta los solapamientos de las transiciones no-cut; la primera escena no admite transición entrante.
