"""
localization_service.py — Enterprise Localization & Internationalization Framework
VisionCore 3.0 Enterprise Platform Services Layer

Provides:
- Multi-language translation string registry
- Organization-level and user-level locale resolution
- Currency formatting (ISO 4217 compliant)
- Number formatting with locale-specific separators
- Date/time formatting with timezone-aware output
- Locale middleware integration point
"""
from __future__ import annotations

import logging
from dataclasses import dataclass, field
from datetime import datetime, date
from typing import Any, Dict, Optional

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
#  Supported Locales & Currencies
# ---------------------------------------------------------------------------

SUPPORTED_LOCALES = {
    "en_US": {"language": "English (US)", "currency": "USD", "date_format": "%m/%d/%Y", "decimal": ".", "thousands": ","},
    "en_GB": {"language": "English (UK)", "currency": "GBP", "date_format": "%d/%m/%Y", "decimal": ".", "thousands": ","},
    "en_IN": {"language": "English (India)", "currency": "INR", "date_format": "%d/%m/%Y", "decimal": ".", "thousands": ","},
    "hi_IN": {"language": "Hindi", "currency": "INR", "date_format": "%d/%m/%Y", "decimal": ".", "thousands": ","},
    "de_DE": {"language": "German", "currency": "EUR", "date_format": "%d.%m.%Y", "decimal": ",", "thousands": "."},
    "fr_FR": {"language": "French", "currency": "EUR", "date_format": "%d/%m/%Y", "decimal": ",", "thousands": " "},
    "ja_JP": {"language": "Japanese", "currency": "JPY", "date_format": "%Y/%m/%d", "decimal": ".", "thousands": ","},
    "ar_SA": {"language": "Arabic (Saudi)", "currency": "SAR", "date_format": "%d/%m/%Y", "decimal": ".", "thousands": ","},
    "zh_CN": {"language": "Chinese (Simplified)", "currency": "CNY", "date_format": "%Y/%m/%d", "decimal": ".", "thousands": ","},
    "es_ES": {"language": "Spanish", "currency": "EUR", "date_format": "%d/%m/%Y", "decimal": ",", "thousands": "."},
}

CURRENCY_SYMBOLS: Dict[str, str] = {
    "USD": "$", "GBP": "£", "EUR": "€", "INR": "₹",
    "JPY": "¥", "SAR": "﷼", "CNY": "¥", "AED": "د.إ",
    "SGD": "S$", "AUD": "A$", "CAD": "C$",
}


# ---------------------------------------------------------------------------
#  Translation Registry Dataclass
# ---------------------------------------------------------------------------

@dataclass
class TranslationBundle:
    """A flat dictionary of translation key → localized string."""
    locale: str
    strings: Dict[str, str] = field(default_factory=dict)


class LocalizationService:
    """
    Centralized Localization & Internationalization Service.
    Consumed by all platform and business modules.
    """

    def __init__(self):
        self._org_locale: Dict[str, str] = {}       # org_id → locale code
        self._user_locale: Dict[int, str] = {}       # user_id → locale code
        self._translations: Dict[str, Dict[str, str]] = {}  # locale → {key: value}
        self._default_locale = "en_US"
        self._register_default_translations()

    # ------------------------------------------------------------------
    #  Locale Configuration
    # ------------------------------------------------------------------

    def set_org_locale(self, organization_id: str, locale: str) -> None:
        """Set the default locale for an organization."""
        if locale not in SUPPORTED_LOCALES:
            raise ValueError(f"Unsupported locale '{locale}'. Supported: {list(SUPPORTED_LOCALES.keys())}")
        self._org_locale[organization_id] = locale
        logger.info(f"Organization {organization_id} locale set to '{locale}'")

    def set_user_locale(self, user_id: int, locale: str) -> None:
        """Override locale at the individual user level."""
        if locale not in SUPPORTED_LOCALES:
            raise ValueError(f"Unsupported locale '{locale}'")
        self._user_locale[user_id] = locale

    def resolve_locale(self, organization_id: Optional[str] = None, user_id: Optional[int] = None) -> str:
        """Resolve effective locale: user > org > platform default."""
        if user_id and user_id in self._user_locale:
            return self._user_locale[user_id]
        if organization_id and organization_id in self._org_locale:
            return self._org_locale[organization_id]
        return self._default_locale

    # ------------------------------------------------------------------
    #  Translation
    # ------------------------------------------------------------------

    def register_translation(self, locale: str, key: str, value: str) -> None:
        """Register a translation string."""
        if locale not in self._translations:
            self._translations[locale] = {}
        self._translations[locale][key] = value

    def register_bundle(self, bundle: TranslationBundle) -> None:
        """Bulk-register a translation bundle."""
        for key, value in bundle.strings.items():
            self.register_translation(bundle.locale, key, value)

    def translate(
        self,
        key: str,
        locale: Optional[str] = None,
        organization_id: Optional[str] = None,
        user_id: Optional[int] = None,
        fallback: Optional[str] = None,
        **kwargs: Any,
    ) -> str:
        """Translate a key into the effective locale, with optional f-string interpolation."""
        effective_locale = locale or self.resolve_locale(organization_id, user_id)
        translations = self._translations.get(effective_locale, {})
        result = translations.get(key)

        # Fallback chain: requested locale → default locale → fallback → key itself
        if result is None:
            result = self._translations.get(self._default_locale, {}).get(key)
        if result is None:
            result = fallback or key

        # Interpolate kwargs
        if kwargs:
            try:
                result = result.format(**kwargs)
            except (KeyError, ValueError):
                pass

        return result

    # ------------------------------------------------------------------
    #  Formatting Utilities
    # ------------------------------------------------------------------

    def format_currency(
        self,
        amount: float,
        currency_code: Optional[str] = None,
        locale: Optional[str] = None,
        organization_id: Optional[str] = None,
    ) -> str:
        """Format a monetary amount using the effective locale's currency conventions."""
        effective_locale = locale or self.resolve_locale(organization_id)
        locale_config = SUPPORTED_LOCALES.get(effective_locale, SUPPORTED_LOCALES[self._default_locale])
        currency = currency_code or locale_config["currency"]
        symbol = CURRENCY_SYMBOLS.get(currency, currency)
        decimal_sep = locale_config["decimal"]
        thousands_sep = locale_config["thousands"]

        # Format number
        formatted = self._format_number(abs(amount), decimal_sep, thousands_sep, decimals=2)
        sign = "-" if amount < 0 else ""
        return f"{sign}{symbol}{formatted}"

    def format_number(
        self,
        value: float,
        decimals: int = 2,
        locale: Optional[str] = None,
        organization_id: Optional[str] = None,
    ) -> str:
        """Format a number with locale-appropriate separators."""
        effective_locale = locale or self.resolve_locale(organization_id)
        locale_config = SUPPORTED_LOCALES.get(effective_locale, SUPPORTED_LOCALES[self._default_locale])
        return self._format_number(value, locale_config["decimal"], locale_config["thousands"], decimals)

    def format_date(
        self,
        dt: Any,
        locale: Optional[str] = None,
        organization_id: Optional[str] = None,
        user_id: Optional[int] = None,
    ) -> str:
        """Format a date or datetime using the effective locale's date pattern."""
        effective_locale = locale or self.resolve_locale(organization_id, user_id)
        locale_config = SUPPORTED_LOCALES.get(effective_locale, SUPPORTED_LOCALES[self._default_locale])
        fmt = locale_config["date_format"]

        if isinstance(dt, str):
            try:
                dt = datetime.fromisoformat(dt)
            except ValueError:
                return dt
        if isinstance(dt, (datetime, date)):
            return dt.strftime(fmt)
        return str(dt)

    def get_supported_locales(self) -> Dict[str, Any]:
        """Return all supported locales and their metadata."""
        return SUPPORTED_LOCALES

    # ------------------------------------------------------------------
    #  Internal Helpers
    # ------------------------------------------------------------------

    def _format_number(self, value: float, decimal_sep: str, thousands_sep: str, decimals: int) -> str:
        """Core number formatter with custom separators."""
        if decimals == 0:
            integer_str = str(int(round(value)))
            decimal_str = ""
        else:
            parts = f"{value:.{decimals}f}".split(".")
            integer_str = parts[0]
            decimal_str = decimal_sep + parts[1] if len(parts) > 1 else ""

        # Insert thousands separator
        grouped = []
        for i, digit in enumerate(reversed(integer_str)):
            if i > 0 and i % 3 == 0:
                grouped.append(thousands_sep)
            grouped.append(digit)
        return "".join(reversed(grouped)) + decimal_str

    def _register_default_translations(self) -> None:
        """Seed platform-level English translation strings."""
        base = {
            "common.save": "Save",
            "common.cancel": "Cancel",
            "common.confirm": "Confirm",
            "common.delete": "Delete",
            "common.export": "Export",
            "common.import": "Import",
            "common.search": "Search",
            "common.filter": "Filter",
            "attendance.marked": "Attendance marked successfully",
            "leave.approved": "Leave request approved",
            "leave.rejected": "Leave request rejected",
            "payroll.generated": "Payroll generated successfully",
            "workflow.submitted": "Request submitted for approval",
            "workflow.approved": "Request has been approved",
            "workflow.rejected": "Request has been rejected",
            "auth.login_success": "Welcome back, {name}!",
            "auth.logout_success": "You have been signed out",
        }
        self.register_bundle(TranslationBundle(locale="en_US", strings=base))
        self.register_bundle(TranslationBundle(locale="en_GB", strings=base))
        self.register_bundle(TranslationBundle(locale="en_IN", strings=base))

        # Hindi basic translations
        hindi = {
            "common.save": "सहेजें",
            "common.cancel": "रद्द करें",
            "common.confirm": "पुष्टि करें",
            "attendance.marked": "उपस्थिति सफलतापूर्वक दर्ज की गई",
            "leave.approved": "छुट्टी का अनुरोध स्वीकृत हुआ",
            "auth.login_success": "स्वागत है, {name}!",
        }
        self.register_bundle(TranslationBundle(locale="hi_IN", strings=hindi))


# Singleton
localization_service = LocalizationService()
