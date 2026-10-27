"""Diagnostico guiado basado en conocimiento local y evidencia declarada."""

from __future__ import annotations

from typing import Any


_CATEGORIAS = {
    "kb_internet_001": "redes",
    "kb_vpn_001": "redes",
    "kb_acceso_cuenta_001": "cuentas",
    "kb_mfa_001": "cuentas",
    "kb_seguridad_correo_001": "ciberseguridad",
    "kb_impresora_001": "hardware",
    "kb_perifericos_001": "hardware",
    "kb_bateria_energia_001": "hardware",
    "kb_rendimiento_001": "sistemas_operativos",
    "kb_optimizacion_equipo_001": "sistemas_operativos",
    "kb_pantalla_actualizacion_001": "sistemas_operativos",
    "kb_formateo_reinstalacion_001": "sistemas_operativos",
    "kb_correo_001": "correo",
    "kb_software_001": "software",
    "kb_licencias_activacion_001": "software",
    "kb_respaldo_datos_001": "datos",
    "kb_cmd_diagnostico_001": "diagnostico",
}

_HIPOTESIS = {
    "redes": "Problema de conectividad de red o Internet",
    "cuentas": "Problema de acceso o autenticacion de la cuenta",
    "ciberseguridad": "Posible incidente de seguridad",
    "hardware": "Problema de hardware o periferico",
    "sistemas_operativos": "Problema del sistema operativo o rendimiento",
    "correo": "Problema de correo o de la aplicacion de correo",
    "software": "Problema de software o licencia",
    "datos": "Necesidad de respaldo o recuperacion de datos",
    "diagnostico": "Necesidad de recopilar datos de diagnostico",
    "general": "La incidencia requiere mas informacion",
}

_PREGUNTAS_SEGUIMIENTO = (
    ("operating_system", "¿Que sistema operativo y version utilizas?"),
    ("affected_scope", "¿Afecta solo a tu equipo o tambien a otras personas o equipos?"),
    (
        "error_message",
        "¿Que mensaje de error exacto aparece? No incluyas contrasenas ni codigos MFA.",
    ),
    ("recent_changes", "¿Que cambio ocurrio poco antes de que empezara el problema?"),
)


def obtener_preguntas_seguimiento(contexto: dict[str, Any] | None) -> list[str]:
    """Pregunta solo por los datos estructurados que aun no se proporcionaron."""
    datos = contexto or {}
    return [
        pregunta
        for campo, pregunta in _PREGUNTAS_SEGUIMIENTO
        if not _tiene_valor(datos.get(campo))
    ]


def _tiene_valor(valor: Any) -> bool:
    if isinstance(valor, str):
        return bool(valor.strip())
    return valor is not None


def diagnosticar_red(
    contexto: dict[str, Any] | None,
) -> tuple[dict[str, Any] | None, list[str]]:
    """Interpreta resultados de red proporcionados por el usuario, sin ejecutarlos."""
    comprobaciones = (contexto or {}).get("network_checks")
    if not isinstance(comprobaciones, dict):
        return None, []

    puerta = comprobaciones.get("gateway_reachable")
    dns = comprobaciones.get("dns_resolution")
    internet = comprobaciones.get("internet_reachable")
    observaciones: list[str] = []

    if type(puerta) is bool:
        observaciones.append(
            "El usuario reporta que la puerta de enlace responde."
            if puerta
            else "El usuario reporta que la puerta de enlace no responde."
        )
    if type(dns) is bool:
        observaciones.append(
            "El usuario reporta que la resolucion DNS funciona."
            if dns
            else "El usuario reporta que la resolucion DNS falla."
        )
    if type(internet) is bool:
        observaciones.append(
            "El usuario reporta acceso a Internet."
            if internet
            else "El usuario reporta que no alcanza Internet."
        )

    if puerta is False:
        causa = "La conectividad local o el acceso a la puerta de enlace podria fallar."
        confianza = 0.72
        pruebas = [
            "Comprueba si otros equipos de la misma red tienen conectividad.",
            "Solicita al soporte autorizado revisar la direccion IP y la puerta de enlace.",
        ]
    elif puerta is True and dns is False:
        causa = "La resolucion DNS podria estar fallando."
        confianza = 0.82
        pruebas = [
            "Consulta un nombre institucional mediante el DNS autorizado.",
            "Compara la resolucion con otro equipo de la misma red.",
        ]
    elif puerta is True and dns is True and internet is False:
        causa = "Podria existir un problema de salida a Internet o de ruta aguas arriba."
        confianza = 0.78
        pruebas = [
            "Compara el acceso a un servicio institucional y uno externo aprobado.",
            "Escala al equipo de redes para revisar rutas o controles perimetrales.",
        ]
    else:
        return None, observaciones

    return {
        "cause": causa,
        "confidence": confianza,
        "sources": [],
        "rationale": "Interpretacion provisional de resultados reportados por el usuario; no verificados por el servidor.",
        "tests": pruebas,
    }, observaciones


def crear_diagnostico(
    resultados: list[dict[str, Any]],
    contexto: dict[str, Any] | None,
) -> dict[str, Any]:
    """Construye hipotesis y pruebas; no confirma causas raiz."""
    hipotesis_red, evidencia_red = diagnosticar_red(contexto)
    hipotesis: list[dict[str, Any]] = []

    if hipotesis_red is not None:
        hipotesis.append(hipotesis_red)
    else:
        for resultado in resultados[:3]:
            articulo = resultado["articulo"]
            categoria = _CATEGORIAS.get(articulo["id"], "general")
            confianza = min(0.9, 0.45 + 0.12 * (resultado["puntuacion"] - 1))
            hipotesis.append(
                {
                    "cause": _HIPOTESIS[categoria],
                    "confidence": round(confianza, 2),
                    "sources": [articulo["id"]],
                    "rationale": (
                        "Coincidencia de palabras clave: "
                        + ", ".join(resultado["palabras_coincidentes"])
                        + ". Es una pista, no una causa confirmada."
                    ),
                    "tests": [
                        "Confirma si el problema se reproduce y desde cuando ocurre.",
                        "Compara el resultado con otro equipo o servicio equivalente, si esta autorizado.",
                    ],
                }
            )

    categoria = (
        "redes"
        if hipotesis_red is not None
        else (
            _CATEGORIAS.get(resultados[0]["articulo"]["id"], "general")
            if resultados
            else "general"
        )
    )
    if hipotesis_red is not None:
        resumen = f"{hipotesis_red['cause']} La causa aun no esta confirmada."
    elif hipotesis:
        resumen = (
            f"La descripcion coincide con: {hipotesis[0]['cause'].lower()}. "
            "La causa raiz aun no esta confirmada."
        )
    else:
        resumen = "No hay informacion suficiente para proponer una hipotesis segura."

    evidencia = [
        f"Palabra clave coincidente: {palabra}"
        for resultado in resultados[:3]
        for palabra in resultado["palabras_coincidentes"]
    ]
    evidencia.extend(evidencia_red)
    return {
        "category": categoria,
        "diagnosis": {
            "summary": resumen,
            "hypotheses": hipotesis,
            "tests": hipotesis[0]["tests"] if hipotesis else [],
        },
        "evidence": evidencia,
        "confidence": hipotesis[0]["confidence"] if hipotesis else 0.0,
    }


def obtener_prioridad(categoria: str) -> str:
    """Asigna prioridad de atencion; una alerta de seguridad se escala primero."""
    return "high" if categoria == "ciberseguridad" else "normal"
