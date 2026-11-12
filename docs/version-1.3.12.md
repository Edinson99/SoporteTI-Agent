# Version 1.3.12

## Recuperacion de consultas sobre macros de Excel

- Se amplian las frases de recuperacion de la guia para libros XLSM y Excel que
  deja de responder, se congela o tarda al ejecutar una macro.
- Se agregan seis consultas sinteticas al benchmark y pruebas de recuperacion
  deterministas para esas variantes.
- Las seis consultas nuevas recuperan la guia esperada en primera posicion con
  busqueda lexica e hibrida. En el conjunto ampliado, la recuperacion hibrida
  obtiene 17/22 en primera posicion y 18/22 en los tres primeros; el resultado
  del grupo anterior de parafrasis permanece en 11/16.
- Se conserva la guia existente y sus precauciones: no habilitar macros de
  fuentes no confiables ni debilitar politicas de seguridad.

La API publica esta version como `1.3.12`. La busqueda semantica sigue siendo
optativa y el benchmark sintetico no certifica la calidad general de
recuperacion.
