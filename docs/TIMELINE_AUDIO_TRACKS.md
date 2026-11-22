# Pistas de audio — borrador

Esta etapa introduce pistas de audio separadas en el timeline:
- música, narración, efectos o ambiente
- fuente local opcional, sin descargas
- posición, duración, volumen y fade-in/fade-out
- validación de rutas, valores finitos y límites de fades
- el modelo es metadata de borrador, sin playback ni render

La integración con sincronización audiovisual, renderizador, waveform, preview de mezcla y export sigue pendiente.


La composición de preview mezcla pistas locales con volumen, delay y fades. La mezcla se rellena con silencio y se limita a la duración calculada del video, para que pistas más cortas no trunquen el preview y pistas más largas no lo extiendan.
