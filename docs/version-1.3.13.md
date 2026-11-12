# Version 1.3.13

## Recuperacion de parafrasis de soporte

- Se amplian las frases de recuperacion para consultas sobre acceso a cuentas,
  microfono en videollamadas, VPN desde casa, impresoras y proyectores.
- Se agregan pruebas deterministas para las cinco consultas que fallaban en el
  benchmark sintetico.
- En el conjunto actual, la busqueda lexica obtiene 21/22 aciertos @1 y la
  hibrida 22/22; la cobertura hibrida @3 es 22/22, con 0/3 falsos positivos
  en consultas sin guia.

El grupo de parafrasis obtiene 15/16 con busqueda lexica y 16/16 con busqueda
hibrida. El conjunto es sintetico y pequeño, por lo que no certifica calidad
general. La busqueda semantica permanece optativa.
