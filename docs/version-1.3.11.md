# Version 1.3.11

## Feedback minimo de utilidad

- El chat permite marcar como util o no util la guia principal de una respuesta.
- Las valoraciones se guardan en SQLite local en
  `data/feedback.sqlite3`, configurable con `SOPORTE_FEEDBACK_DB`.
- Solo se almacenan el identificador de guia, el voto y la fecha UTC. No se
  persisten preguntas, conversaciones, usuario, contacto ni texto libre.
- Los votos con mas de 180 dias se eliminan al guardar una valoracion o
  consultar `GET /api/feedback/summary`.
- El resumen devuelve conteos agregados por guia y tanto la escritura como la
  consulta requieren loopback.
- Las valoraciones orientan la revision humana; no cambian ni publican guias
  automaticamente.

La API publica esta version como `1.3.11`. Se mantienen el contrato del chat,
la recuperacion lexica predeterminada y el caracter optativo de la busqueda
semantica.
