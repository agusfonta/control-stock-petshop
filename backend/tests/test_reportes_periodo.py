"""Zona horaria, periodo y calculos puros de reportes (C-14 task 2.2, RED-first).

Cubre D5 (dia local con bordes calculados en Python y comparados en UTC),
D6 (resolucion del periodo) y las funciones puras de D7/D9/D10. Sin base de
datos: todo es calculo sobre fechas y Decimal.
"""

from datetime import date, datetime, timezone
from decimal import Decimal

import pytest
from pydantic import ValidationError

AR_ZONA_POR_DEFECTO = "America/Argentina/Buenos_Aires"
HOY = date(2026, 10, 6)


@pytest.fixture
def hoy_fijo(monkeypatch):
    """Fija el reloj del servicio en 2026-10-06 (mediodia UTC)."""
    from app.services import reportes

    monkeypatch.setattr(
        reportes, "_ahora_utc", lambda: datetime(2026, 10, 6, 12, 0, tzinfo=timezone.utc)
    )


# --- Setting reportes_tz ---


def test_reportes_tz_default_es_buenos_aires() -> None:
    from app.core.config import Settings

    settings = Settings(_env_file=None, secret_key="test-only-ephemeral-key")
    assert settings.reportes_tz == AR_ZONA_POR_DEFECTO


def test_reportes_tz_configurable_por_env() -> None:
    from app.core.config import Settings

    settings = Settings(
        _env_file=None, secret_key="test-only-ephemeral-key", reportes_tz="UTC"
    )
    assert settings.reportes_tz == "UTC"


@pytest.mark.parametrize("zona", ["Mars/Olympus_Mons", "", "ART"])
def test_reportes_tz_invalida_falla_al_construir_settings(zona: str) -> None:
    from app.core.config import Settings

    with pytest.raises(ValidationError):
        Settings(_env_file=None, secret_key="test-only-ephemeral-key", reportes_tz=zona)


# --- bordes_utc (D5) ---


def test_bordes_utc_de_un_dia_arranca_a_las_03z() -> None:
    from app.services.reportes import bordes_utc

    inicio, fin = bordes_utc(date(2026, 10, 5), date(2026, 10, 5))
    assert inicio == datetime(2026, 10, 5, 3, 0, tzinfo=timezone.utc)
    assert fin == datetime(2026, 10, 6, 3, 0, tzinfo=timezone.utc)
    assert inicio.utcoffset() == timezone.utc.utcoffset(None)


def test_bordes_utc_de_un_periodo_incluye_ambos_dias() -> None:
    from app.services.reportes import bordes_utc

    inicio, fin = bordes_utc(date(2026, 10, 1), date(2026, 10, 6))
    assert inicio == datetime(2026, 10, 1, 3, 0, tzinfo=timezone.utc)
    assert fin == datetime(2026, 10, 7, 3, 0, tzinfo=timezone.utc)


def test_bordes_utc_respeta_la_zona_configurada(monkeypatch) -> None:
    """Con otra zona (UTC) el dia local coincide con el dia UTC."""
    from app.core import config
    from app.services import reportes

    en_utc = config.Settings(
        _env_file=None, secret_key="test-only-ephemeral-key", reportes_tz="UTC"
    )
    monkeypatch.setattr(reportes, "get_settings", lambda: en_utc)
    inicio, fin = reportes.bordes_utc(date(2026, 10, 5), date(2026, 10, 5))
    assert inicio == datetime(2026, 10, 5, 0, 0, tzinfo=timezone.utc)
    assert fin == datetime(2026, 10, 6, 0, 0, tzinfo=timezone.utc)


# --- hoy() (D5) ---


def test_hoy_es_la_fecha_local_no_la_utc(monkeypatch) -> None:
    from app.services import reportes

    monkeypatch.setattr(
        reportes, "_ahora_utc", lambda: datetime(2026, 10, 7, 1, 0, tzinfo=timezone.utc)
    )
    assert reportes.hoy() == date(2026, 10, 6)


def test_hoy_cambia_de_dia_a_las_03z(monkeypatch) -> None:
    from app.services import reportes

    monkeypatch.setattr(
        reportes, "_ahora_utc", lambda: datetime(2026, 10, 7, 3, 0, tzinfo=timezone.utc)
    )
    assert reportes.hoy() == date(2026, 10, 7)


# --- resolver_periodo (D6) ---


def test_periodo_sin_bordes_son_los_ultimos_30_dias_con_hoy(hoy_fijo) -> None:
    from app.services.reportes import resolver_periodo

    assert resolver_periodo(None, None) == (date(2026, 9, 7), HOY)


def test_periodo_solo_desde_llega_hasta_hoy(hoy_fijo) -> None:
    from app.services.reportes import resolver_periodo

    assert resolver_periodo(date(2026, 10, 1), None) == (date(2026, 10, 1), HOY)


def test_periodo_solo_hasta_arranca_29_dias_antes(hoy_fijo) -> None:
    from app.services.reportes import resolver_periodo

    assert resolver_periodo(None, date(2026, 9, 30)) == (
        date(2026, 9, 1),
        date(2026, 9, 30),
    )


def test_periodo_de_un_solo_dia_es_valido(hoy_fijo) -> None:
    from app.services.reportes import resolver_periodo

    assert resolver_periodo(HOY, HOY) == (HOY, HOY)


def test_periodo_invertido_es_error(hoy_fijo) -> None:
    from app.services.reportes import PeriodoInvalido, resolver_periodo

    with pytest.raises(PeriodoInvalido):
        resolver_periodo(date(2026, 10, 6), date(2026, 10, 1))


def test_periodo_solo_desde_posterior_a_hoy_es_invertido(hoy_fijo) -> None:
    """Con solo `desde` futuro, `hasta` = hoy queda antes: error, no vacio."""
    from app.services.reportes import PeriodoInvalido, resolver_periodo

    with pytest.raises(PeriodoInvalido):
        resolver_periodo(date(2026, 10, 7), None)


def test_periodo_de_367_dias_es_error_y_de_366_es_valido(hoy_fijo) -> None:
    from app.services.reportes import PeriodoInvalido, resolver_periodo

    hasta = date(2026, 10, 6)
    # 366 dias inclusive: 2025-10-06 .. 2026-10-06
    assert resolver_periodo(date(2025, 10, 6), hasta) == (date(2025, 10, 6), hasta)
    with pytest.raises(PeriodoInvalido):
        resolver_periodo(date(2025, 10, 5), hasta)


def test_periodo_solo_desde_muy_antiguo_supera_el_maximo(hoy_fijo) -> None:
    from app.services.reportes import PeriodoInvalido, resolver_periodo

    with pytest.raises(PeriodoInvalido):
        resolver_periodo(date(2020, 1, 1), None)


# --- ticket_promedio (D7) ---


def test_ticket_promedio_redondea_a_centavos() -> None:
    from app.services.reportes import ticket_promedio

    assert ticket_promedio(Decimal("300.01"), 3) == Decimal("100.00")


def test_ticket_promedio_mitad_hacia_arriba() -> None:
    """50.005 va a 50.01 (el redondeo bancario daria 50.00)."""
    from app.services.reportes import ticket_promedio

    assert ticket_promedio(Decimal("100.01"), 2) == Decimal("50.01")


def test_ticket_promedio_sin_ventas_es_cero() -> None:
    from app.services.reportes import ticket_promedio

    assert ticket_promedio(Decimal("0"), 0) == Decimal("0.00")


# --- venta_diaria (D9) ---


def test_venta_diaria_a_centavos_mitad_hacia_arriba() -> None:
    from app.services.reportes import venta_diaria

    assert venta_diaria(60, 30) == Decimal("2.00")
    assert venta_diaria(1, 30) == Decimal("0.03")  # 0.0333...
    assert venta_diaria(1, 8) == Decimal("0.13")  # 0.125 sube
    assert venta_diaria(0, 30) == Decimal("0.00")


# --- cobertura_dias (D9) ---


def test_cobertura_dias_stock_10_y_60_unidades_en_30_dias() -> None:
    from app.services.reportes import cobertura_dias

    assert cobertura_dias(10, 60, 30) == 5


def test_cobertura_dias_stock_agotado_con_ventas_es_cero() -> None:
    from app.services.reportes import cobertura_dias

    assert cobertura_dias(0, 60, 30) == 0


def test_cobertura_dias_sin_ventas_es_none() -> None:
    from app.services.reportes import cobertura_dias

    assert cobertura_dias(10, 0, 30) is None
    assert cobertura_dias(0, 0, 30) is None


def test_cobertura_dias_trunca_en_vez_de_redondear() -> None:
    """19 u de stock a 300 u/30 d = 1,9 dias se informa como 1 (conservador)."""
    from app.services.reportes import cobertura_dias

    assert cobertura_dias(19, 300, 30) == 1
    assert cobertura_dias(3, 1, 30) == 90


# --- margen_pct (D10) ---


def test_margen_pct_es_markup_sobre_costo_con_4_decimales() -> None:
    from app.services.reportes import margen_pct

    assert margen_pct(Decimal("1000"), Decimal("2000")) == Decimal("0.5000")
    assert margen_pct(Decimal("1"), Decimal("3")) == Decimal("0.3333")
    assert margen_pct(Decimal("2"), Decimal("3")) == Decimal("0.6667")


def test_margen_pct_mitad_hacia_arriba() -> None:
    from app.services.reportes import margen_pct

    assert margen_pct(Decimal("1"), Decimal("20000")) == Decimal("0.0001")


def test_margen_pct_con_costo_cero_es_none() -> None:
    from app.services.reportes import margen_pct

    assert margen_pct(Decimal("0"), Decimal("0")) is None
    assert margen_pct(Decimal("500"), Decimal("0")) is None


def test_margen_pct_negativo_cuando_se_vende_bajo_costo() -> None:
    from app.services.reportes import margen_pct

    assert margen_pct(Decimal("-500"), Decimal("2000")) == Decimal("-0.2500")
