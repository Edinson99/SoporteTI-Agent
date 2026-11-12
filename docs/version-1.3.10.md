# Version 1.3.10

## Evaluacion de recuperacion

- Se agrega un conjunto reproducible de consultas sinteticas etiquetadas para
  medir busqueda lexica, busqueda hibrida, rescates semanticos y abstenciones
  ante preguntas sin guia.
- El comando `python scripts/evaluate_retrieval.py` requiere instalar
  `requirements-semantic.txt` y descarga el modelo local la primera vez.
- La evaluacion inicial obtuvo 11/16 aciertos hibridos en la primera posicion,
  12/16 con el articulo esperado entre los tres primeros y un rescate
  semantico correcto. No hubo resultados para las 3 consultas sin guia.
- Cinco consultas de parafrasis no obtuvieron el articulo esperado en primera
  posicion; el benchmark detalla las discrepancias. La busqueda semantica sigue
  siendo opcional y no se considera calibrada para activarse en produccion.

La API publica esta version como `1.3.10`. Se mantienen sin cambios el
contrato HTTP y la busqueda lexica predeterminada.
