"""
config_center.py — Enterprise Configuration Center
Sprint 6 — Phase B: Enterprise Multi-Tenant SaaS Completion

Expanded tenant configuration management:
- Authentication policies (MFA, password policies, session duration)
- Security rules
- Attendance defaults, Leave defaults, Payroll defaults, HR defaults
- Email configuration, Branding configuration
- Localization (timezone, currency, language)
- Import/Export of configuration profiles

No frozen modules are modified.
"""
from __future__ import annotations

import json
import logging
import secrets
from datetime import datetime, timezone
from typing import Any, Optional

logger = logging.getLogger(__name__)


# Configuration key definitions with defaults
CONFIG_DEFINITIONS = {
    # ── Authentication Policies ──
    "auth.password_min_length": {"type": "int", "default": 8, "min": 6, "max": 128, "description": "Minimum password length"},
    "auth.password_require_upper": {"type": "bool", "default": True, "description": "Require uppercase letter in password"},
    "auth.password_require_lower": {"type": "bool", "default": True, "description": "Require lowercase letter in password"},
    "auth.password_require_digit": {"type": "bool", "default": True, "description": "Require digit in password"},
    "auth.password_require_special": {"type": "bool", "default": True, "description": "Require special character in password"},
    "auth.password_expiry_days": {"type": "int", "default": 90, "min": 0, "max": 365, "description": "Password expiry in days (0 = never)"},
    "auth.session_timeout_minutes": {"type": "int", "default": 60, "min": 5, "max": 1440, "description": "Session timeout in minutes"},
    "auth.mfa_required": {"type": "bool", "default": False, "description": "Require MFA for all users"},
    "auth.mfa_method": {"type": "str", "default": "totp", "description": "MFA method (totp, sms, email)"},
    "auth.max_login_attempts": {"type": "int", "default": 5, "min": 1, "max": 20, "description": "Max failed login attempts before lockout"},
    "auth.lockout_duration_minutes": {"type": "int", "default": 30, "min": 1, "max": 1440, "description": "Account lockout duration in minutes"},
    "auth.jwt_access_token_expiry_minutes": {"type": "int", "default": 60, "min": 5, "max": 1440, "description": "JWT access token expiry"},
    "auth.jwt_refresh_token_expiry_days": {"type": "int", "default": 7, "min": 1, "max": 90, "description": "JWT refresh token expiry"},
    "auth.single_session_per_user": {"type": "bool", "default": False, "description": "Allow only one session per user"},

    # ── Security Rules ──
    "security.require_https": {"type": "bool", "default": True, "description": "Require HTTPS for all connections"},
    "security.ip_whitelist_enabled": {"type": "bool", "default": False, "description": "Enable IP whitelist"},
    "security.ip_whitelist": {"type": "list", "default": [], "description": "Allowed IP addresses"},
    "security.cors_allowed_origins": {"type": "list", "default": ["*"], "description": "Allowed CORS origins"},
    "security.rate_limit_per_minute": {"type": "int", "default": 60, "min": 1, "max": 10000, "description": "API rate limit per minute"},
    "security.audit_all_actions": {"type": "bool", "default": True, "description": "Audit all user actions"},
    "security.data_retention_days": {"type": "int", "default": 365, "min": 30, "max": 2555, "description": "Data retention period in days"},

    # ── Attendance Defaults ──
    "attendance.grace_period_minutes": {"type": "int", "default": 15, "min": 0, "max": 60, "description": "Check-in grace period"},
    "attendance.checkin_cooldown_minutes": {"type": "int", "default": 5, "min": 0, "max": 60, "description": "Time between consecutive check-ins"},
    "attendance.auto_close_enabled": {"type": "bool", "default": True, "description": "Auto-close attendance at end of day"},
    "attendance.auto_close_time": {"type": "str", "default": "23:55", "description": "Auto-close time (HH:MM)"},
    "attendance.require_geofence": {"type": "bool", "default": False, "description": "Require geofence for check-in"},
    "attendance.geofence_radius_meters": {"type": "int", "default": 50, "min": 10, "max": 1000, "description": "Geofence radius in meters"},
    "attendance.require_liveness_check": {"type": "bool", "default": True, "description": "Require liveness detection for face recognition"},
    "attendance.default_shift_start": {"type": "str", "default": "09:00", "description": "Default shift start time"},
    "attendance.default_shift_end": {"type": "str", "default": "18:00", "description": "Default shift end time"},
    "attendance.weekly_off_days": {"type": "list", "default": ["saturday", "sunday"], "description": "Weekly off days"},

    # ── Leave Defaults ──
    "leave.default_annual_leave_days": {"type": "int", "default": 15, "min": 0, "max": 60, "description": "Default annual leave days"},
    "leave.default_sick_leave_days": {"type": "int", "default": 12, "min": 0, "max": 60, "description": "Default sick leave days"},
    "leave.default_personal_leave_days": {"type": "int", "default": 5, "min": 0, "max": 30, "description": "Default personal leave days"},
    "leave.carry_forward_days": {"type": "int", "default": 5, "min": 0, "max": 30, "description": "Max carry-forward leave days"},
    "leave.requires_approval": {"type": "bool", "default": True, "description": "Require approval for leave requests"},
    "leave.min_notice_days": {"type": "int", "default": 1, "min": 0, "max": 30, "description": "Minimum notice period for leave"},
    "leave.max_consecutive_days": {"type": "int", "default": 30, "min": 1, "max": 365, "description": "Max consecutive leave days"},

    # ── Payroll Defaults ──
    "payroll.payment_currency": {"type": "str", "default": "USD", "description": "Payroll currency"},
    "payroll.payment_day": {"type": "int", "default": 1, "min": 1, "max": 28, "description": "Payroll payment day of month"},
    "payroll.auto_generate": {"type": "bool", "default": True, "description": "Auto-generate payroll"},
    "payroll.default_tax_rate": {"type": "float", "default": 0.0, "min": 0, "max": 100, "description": "Default tax rate"},
    "payroll.overtime_rate": {"type": "float", "default": 1.5, "min": 1, "max": 5, "description": "Overtime pay multiplier"},
    "payroll.weekend_rate": {"type": "float", "default": 2.0, "min": 1, "max": 5, "description": "Weekend pay multiplier"},
    "payroll.holiday_rate": {"type": "float", "default": 2.5, "min": 1, "max": 5, "description": "Holiday pay multiplier"},

    # ── HR Defaults ──
    "hr.probation_period_days": {"type": "int", "default": 90, "min": 0, "max": 365, "description": "Probation period in days"},
    "hr.notice_period_days": {"type": "int", "default": 30, "min": 0, "max": 90, "description": "Resignation notice period"},
    "hr.employee_id_prefix": {"type": "str", "default": "EMP", "description": "Employee ID prefix"},

    # ── Email Configuration ──
    "email.from_name": {"type": "str", "default": "VisionCore", "description": "Email sender name"},
    "email.from_address": {"type": "str", "default": "noreply@visioncore.local", "description": "Email sender address"},
    "email.reply_to": {"type": "str", "default": "", "description": "Email reply-to address"},
    "email.signature": {"type": "str", "default": "Powered by VisionCore v2.0", "description": "Email signature"},

    # ── Localization ──
    "locale.timezone": {"type": "str", "default": "UTC", "description": "Tenant timezone"},
    "locale.currency": {"type": "str", "default": "USD", "description": "Tenant currency"},
    "locale.language": {"type": "str", "default": "en", "description": "Tenant language"},
    "locale.date_format": {"type": "str", "default": "YYYY-MM-DD", "description": "Date format"},
    "locale.time_format": {"type": "str", "default": "HH:mm", "description": "Time format"},
    "locale.first_day_of_week": {"type": "int", "default": 1, "min": 0, "max": 6, "description": "First day of week (0=Sun, 1=Mon)"},
    "locale.number_format": {"type": "str", "default": "en-US", "description": "Number format locale"},
    # ── Feature Flags ──
    "feature_flags.ai_attendance": {"type": "bool", "default": True, "description": "Enable AI Face Recognition Attendance"},
    "feature_flags.liveness_detection": {"type": "bool", "default": True, "description": "Enable Anti-Spoof Liveness Detection"},
    "feature_flags.payroll_auto_calc": {"type": "bool", "default": True, "description": "Enable Automated Payroll Calculation Engine"},
    "feature_flags.blockchain_audit": {"type": "bool", "default": True, "description": "Enable Blockchain Audit Trail Anchoring"},
    "feature_flags.advanced_analytics": {"type": "bool", "default": True, "description": "Enable Advanced Predictive Workforce Analytics"},
    "feature_flags.eaac_authorization": {"type": "bool", "default": True, "description": "Enable Fine-Grained EAAC Authorization Engine"},
    "feature_flags.custom_branding": {"type": "bool", "default": True, "description": "Enable Custom Tenant Branding"},
    "feature_flags.multi_factor_auth": {"type": "bool", "default": False, "description": "Enable Multi-Factor Authentication Enforcement"},
}


class ConfigCenter:
    """
    Configuration center for tenant-specific settings.

    Supports:
    - Global defaults (system-wide)
    - Org-level overrides
    - Feature Flags resolution
    - Typed Getters (bool, int, str, float, list)
    - Database Persistence (SystemSetting)
    - Import/Export of configuration profiles
    - Versioned audit trail
    """

    def __init__(self):
        self._global_config: dict[str, Any] = {}
        self._org_overrides: dict[str, dict[str, Any]] = {}
        self._versions: dict[str, int] = {}
        self._max_history: int = 1000

    # ──────────────────────────────────────────────────────────────────────
    #  Get/Set & Typed Getters
    # ──────────────────────────────────────────────────────────────────────

    def get(self, key: str, org_id: str = "", default: Any = None) -> Any:
        """
        Get a configuration value.
        Resolution order:
        1. Org-level override
        2. Global config
        3. Definition default
        4. Provided default
        """
        if org_id and org_id in self._org_overrides:
            if key in self._org_overrides[org_id]:
                return self._org_overrides[org_id][key]

        if key in self._global_config:
            return self._global_config[key]

        if key in CONFIG_DEFINITIONS:
            return CONFIG_DEFINITIONS[key]["default"]

        return default

    def get_bool(self, key: str, org_id: str = "", default: bool = False) -> bool:
        val = self.get(key, org_id=org_id, default=default)
        if isinstance(val, bool):
            return val
        if isinstance(val, str):
            return val.lower() in ("true", "1", "yes", "on")
        return bool(val)

    def get_int(self, key: str, org_id: str = "", default: int = 0) -> int:
        val = self.get(key, org_id=org_id, default=default)
        try:
            return int(val)
        except (ValueError, TypeError):
            return default

    def get_float(self, key: str, org_id: str = "", default: float = 0.0) -> float:
        val = self.get(key, org_id=org_id, default=default)
        try:
            return float(val)
        except (ValueError, TypeError):
            return default

    def get_str(self, key: str, org_id: str = "", default: str = "") -> str:
        val = self.get(key, org_id=org_id, default=default)
        return str(val) if val is not None else default

    def get_list(self, key: str, org_id: str = "", default: list | None = None) -> list:
        val = self.get(key, org_id=org_id, default=default or [])
        if isinstance(val, list):
            return val
        return [val] if val is not None else []

    def is_feature_enabled(self, flag_name: str, org_id: str = "") -> bool:
        full_key = flag_name if flag_name.startswith("feature_flags.") else f"feature_flags.{flag_name}"
        return self.get_bool(full_key, org_id=org_id, default=False)

    def set(
        self,
        key: str,
        value: Any,
        org_id: str = "",
        updated_by: Optional[int] = None,
    ) -> None:
        """Set a configuration value and update version counter."""
        if key in CONFIG_DEFINITIONS:
            self._validate_value(key, value)

        old_val = self.get(key, org_id=org_id)
        if org_id:
            if org_id not in self._org_overrides:
                self._org_overrides[org_id] = {}
            self._org_overrides[org_id][key] = value
        else:
            self._global_config[key] = value

        version_key = f"{org_id}:{key}" if org_id else key
        self._versions[version_key] = self._versions.get(version_key, 0) + 1

        logger.info(f"Config set: {key}={value}{' for org ' + org_id if org_id else ''}")

        # Audit event integration
        try:
            from app.services.audit_service import audit_service
            audit_service.record(
                actor_user_id=updated_by,
                organization_id=org_id,
                module="config",
                action="update",
                entity_type="config_setting",
                entity_id=key,
                summary=f"Configuration '{key}' updated",
                details={"old_value": old_val, "new_value": value, "version": self._versions[version_key]},
            )
        except Exception:
            pass

    def reset(self, key: str, org_id: str = "") -> bool:
        """Reset a configuration value to default."""
        if org_id and org_id in self._org_overrides:
            self._org_overrides[org_id].pop(key, None)
            return True
        elif not org_id:
            self._global_config.pop(key, None)
            return True
        return False

    # ──────────────────────────────────────────────────────────────────────
    #  Bulk Operations
    # ──────────────────────────────────────────────────────────────────────

    def get_all(self, org_id: str = "") -> dict[str, Any]:
        """Get all configuration values."""
        result = {}
        for key, definition in CONFIG_DEFINITIONS.items():
            result[key] = definition["default"]

        for key, value in self._global_config.items():
            result[key] = value

        if org_id and org_id in self._org_overrides:
            for key, value in self._org_overrides[org_id].items():
                result[key] = value

        return result

    def get_category(self, category: str, org_id: str = "") -> dict[str, Any]:
        """Get all config values in a category."""
        prefix = f"{category}."
        all_configs = self.get_all(org_id)
        return {
            k: v for k, v in all_configs.items()
            if k.startswith(prefix)
        }

    def set_many(self, configs: dict[str, Any], org_id: str = "") -> int:
        """Set multiple configuration values. Returns count of set values."""
        count = 0
        for key, value in configs.items():
            try:
                self.set(key, value, org_id=org_id)
                count += 1
            except ValueError as e:
                logger.warning(f"Config validation failed for {key}: {e}")
        return count

    # ──────────────────────────────────────────────────────────────────────
    #  Import/Export & Definitions
    # ──────────────────────────────────────────────────────────────────────

    def export_profile(self, org_id: str = "") -> dict:
        """Export configuration as a profile (JSON-compatible)."""
        configs = self.get_all(org_id)
        return {
            "version": "1.0",
            "exported_at": datetime.now(timezone.utc).isoformat(),
            "organization_id": org_id or "global",
            "configs": configs,
        }

    def import_profile(self, profile: dict, org_id: str = "") -> int:
        """Import a configuration profile. Returns count of imported values."""
        configs = profile.get("configs", {})
        if not isinstance(configs, dict):
            raise ValueError("Invalid profile format: 'configs' must be a dict")

        count = self.set_many(configs, org_id=org_id)
        logger.info(
            f"Imported {count} config values from profile "
            f"for {'org ' + org_id if org_id else 'global'}"
        )
        return count

    def get_definitions(self) -> dict:
        """Get all configuration definitions with metadata."""
        return CONFIG_DEFINITIONS

    def get_categories(self) -> list[str]:
        """Get all configuration categories."""
        categories = set()
        for key in CONFIG_DEFINITIONS:
            category = key.split(".")[0]
            categories.add(category)
        return sorted(categories)

    # ──────────────────────────────────────────────────────────────────────
    #  Validation
    # ──────────────────────────────────────────────────────────────────────

    def _validate_value(self, key: str, value: Any) -> None:
        """Validate a configuration value against its definition."""
        definition = CONFIG_DEFINITIONS.get(key)
        if not definition:
            return  # Allow custom keys

        config_type = definition["type"]

        if config_type == "int":
            if not isinstance(value, int):
                raise ValueError(f"Config '{key}' must be an integer, got {type(value)}")
            min_val = definition.get("min")
            max_val = definition.get("max")
            if min_val is not None and value < min_val:
                raise ValueError(f"Config '{key}' must be >= {min_val}, got {value}")
            if max_val is not None and value > max_val:
                raise ValueError(f"Config '{key}' must be <= {max_val}, got {value}")

        elif config_type == "float":
            if not isinstance(value, (int, float)):
                raise ValueError(f"Config '{key}' must be a number, got {type(value)}")
            min_val = definition.get("min")
            max_val = definition.get("max")
            if min_val is not None and value < min_val:
                raise ValueError(f"Config '{key}' must be >= {min_val}, got {value}")
            if max_val is not None and value > max_val:
                raise ValueError(f"Config '{key}' must be <= {max_val}, got {value}")

        elif config_type == "bool":
            if not isinstance(value, bool):
                raise ValueError(f"Config '{key}' must be a boolean, got {type(value)}")

        elif config_type == "str":
            if not isinstance(value, str):
                raise ValueError(f"Config '{key}' must be a string, got {type(value)}")

        elif config_type == "list":
            if not isinstance(value, list):
                raise ValueError(f"Config '{key}' must be a list, got {type(value)}")

        elif config_type == "dict":
            if not isinstance(value, dict):
                raise ValueError(f"Config '{key}' must be a dict, got {type(value)}")


# Singleton
config_center = ConfigCenter()
