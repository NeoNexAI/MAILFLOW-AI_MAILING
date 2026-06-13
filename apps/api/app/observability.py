"""Inicialización opcional de Sentry (errores), guardada por DSN.

Sin `SENTRY_DSN` configurado no se inicializa nada: cero eventos, cero red. El
import de `sentry_sdk` se hace de forma perezosa y tolerante para que la app no
dependa duramente de la librería en entornos mínimos.
"""

from __future__ import annotations

import logging

from app.config import settings

log = logging.getLogger("mailflow.observability")


def init_sentry() -> bool:
    """Inicializa Sentry si hay DSN. Devuelve True si quedó activo.

    No lanza nunca: un fallo de observabilidad no debe tumbar el servicio.
    """
    if not settings.SENTRY_DSN:
        return False
    try:
        import sentry_sdk

        sentry_sdk.init(
            dsn=settings.SENTRY_DSN,
            environment=settings.ENVIRONMENT,
            traces_sample_rate=settings.SENTRY_TRACES_SAMPLE_RATE,
        )
        log.info("Sentry inicializado (environment=%s)", settings.ENVIRONMENT)
        return True
    except Exception as exc:  # noqa: BLE001 — observabilidad nunca debe romper
        log.warning("No se pudo inicializar Sentry: %s", exc)
        return False
