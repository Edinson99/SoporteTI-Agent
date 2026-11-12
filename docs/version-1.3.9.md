# Version 1.3.9

## Recuperacion semantica local

- Se agrega busqueda hibrida opt-in: conserva las coincidencias por palabras
  clave y suma articulos candidatos por similitud semantica.
- La codificacion usa localmente
  `sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2` mediante
  FastEmbed. El modelo se descarga al equipo la primera vez; las consultas y la
  base de conocimiento no se envian a un servicio de embeddings.
- FastEmbed se declara por separado en `requirements-semantic.txt` para no
  agregar una dependencia pesada a los despliegues AWS/Lambda existentes; en
  Lambda se conserva la busqueda lexica.
- La funcion esta desactivada por defecto para preservar el comportamiento y
  el inicio sin descarga. Se habilita con `SOPORTE_SEMANTIC_SEARCH=true`.
- El umbral inicial de similitud es `0.65`; debe reevaluarse con consultas
  representativas de la organizacion antes de habilitar la funcion en
  produccion.
- El diagnostico muestra si la evidencia procede de palabras clave o de
  similitud semantica. La similitud es una pista de recuperacion, no una
  confirmacion de causa raiz.
- Se amplian las frases de recuperacion para distinguir el acceso a la red
  corporativa desde fuera de la oficina y las consultas sobre equipos que
  responden muy despacio.

La API publica esta version como `1.3.9`. Se mantienen la busqueda lexica
existente, el contrato de respuesta y el flujo de escalamiento humano.
