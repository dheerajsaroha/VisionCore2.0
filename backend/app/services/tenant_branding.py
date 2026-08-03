"""
tenant_branding.py — White-Label Tenant Branding Service
Sprint 6 — Phase B: Enterprise Multi-Tenant SaaS Completion

Extended white-label branding capabilities:
- Logo management (URL, favicon, login page image)
- Color scheme (primary, secondary, accent, background, text)
- Typography (font family, heading font)
- Custom CSS and JavaScript injection
- Custom domain mapping
- Custom email templates (sender, logo, footer, colors)
- Login page customization (title, subtitle, background)
- Custom footer text and links
- Locale overrides
- Branding preview and export/import

No frozen modules are modified.
"""
from __future__ import annotations

import json
import logging
from datetime import datetime, timezone
from typing import Optional
from uuid import UUID

from sqlalchemy.orm import Session

from app.db.models.all_models import Organization
from app.services.config_center import config_center
from app.services.audit_service import audit_service

logger = logging.getLogger(__name__)


# Default branding configuration
DEFAULT_BRANDING = {
    # Logo
    "logo_url": "",
    "logo_dark_mode_url": "",
    "favicon_url": "",
    "login_page_image_url": "",
    "login_page_logo_url": "",

    # Colors
    "primary_color": "#4F46E5",        # Indigo-600
    "secondary_color": "#7C3AED",      # Violet-600
    "accent_color": "#10B981",          # Emerald-500
    "background_color": "#FFFFFF",
    "surface_color": "#F9FAFB",
    "text_color": "#111827",
    "text_secondary_color": "#6B7280",
    "border_color": "#E5E7EB",
    "success_color": "#10B981",
    "warning_color": "#F59E0B",
    "error_color": "#EF4444",
    "info_color": "#3B82F6",

    # Typography
    "font_family": "Inter, system-ui, sans-serif",
    "heading_font_family": "Inter, system-ui, sans-serif",
    "font_size_base": "16px",
    "font_size_heading": "24px",

    # Custom CSS/JS
    "custom_css": "",
    "custom_js": "",
    "custom_head_html": "",

    # Login Page
    "login_title": "Sign in to your account",
    "login_subtitle": "Welcome back! Please enter your credentials.",
    "login_background_color": "#F9FAFB",
    "login_primary_button_color": "#4F46E5",
    "login_primary_button_text_color": "#FFFFFF",
    "login_show_remember_me": True,
    "login_show_forgot_password": True,
    "login_show_social_login": False,
    "login_custom_html": "",

    # Footer
    "footer_text": "Powered by VisionCore v2.0",
    "footer_links": [],
    "footer_show_powered_by": True,
    "footer_copyright_text": "",

    # Email
    "email_sender_name": "",
    "email_sender_logo_url": "",
    "email_footer_text": "",
    "email_primary_color": "",
    "email_background_color": "",

    # Locale
    "locale_overrides": {},

    # Domain
    "custom_domain": "",
    "custom_domain_verified": False,
}


# Branding config key prefix
BRANDING_PREFIX = "branding."


class TenantBrandingService:
    """
    White-label tenant branding service.

    Allows each tenant to customize:
    - Logo, colors, typography
    - Login page, footer, email templates
    - Custom CSS/JS
    - Custom domain
    - Locale overrides
    """

    # ──────────────────────────────────────────────────────────────────────
    #  Get/Set Branding
    # ──────────────────────────────────────────────────────────────────────

    def get_branding(self, org_id: UUID) -> dict:
        """Get the full branding configuration for a tenant."""
        org_id_str = str(org_id)
        branding = {}

        # Start with defaults
        for key, default in DEFAULT_BRANDING.items():
            config_key = f"{BRANDING_PREFIX}{key}"
            value = config_center.get(config_key, org_id=org_id_str, default=default)
            branding[key] = value

        return branding

    def get_branding_value(self, org_id: UUID, key: str, default: any = None) -> any:
        """Get a single branding value."""
        config_key = f"{BRANDING_PREFIX}{key}"
        return config_center.get(
            config_key,
            org_id=str(org_id),
            default=default if default is not None else DEFAULT_BRANDING.get(key),
        )

    def update_branding(
        self,
        db: Session,
        org_id: UUID,
        branding_data: dict,
        updated_by: Optional[int] = None,
    ) -> dict:
        """Update branding configuration for a tenant."""
        org_id_str = str(org_id)

        # Validate and set each branding value
        updated_count = 0
        for key, value in branding_data.items():
            if key in DEFAULT_BRANDING:
                config_key = f"{BRANDING_PREFIX}{key}"
                config_center.set(config_key, value, org_id=org_id_str)
                updated_count += 1
            else:
                logger.warning(f"Unknown branding key: {key}")

        # Audit
        audit_service.record(
            module="branding",
            action="branding_updated",
            entity_type="organization",
            entity_id=org_id_str,
            summary=f"Branding updated: {updated_count} values changed",
            details={"updated_keys": list(branding_data.keys())},
            actor_user_id=updated_by,
            organization_id=org_id_str,
        )

        logger.info(f"Branding updated for org {org_id_str}: {updated_count} values")
        return self.get_branding(org_id)

    def reset_branding(
        self,
        db: Session,
        org_id: UUID,
        updated_by: Optional[int] = None,
    ) -> dict:
        """Reset branding to defaults for a tenant."""
        org_id_str = str(org_id)

        for key in DEFAULT_BRANDING:
            config_key = f"{BRANDING_PREFIX}{key}"
            config_center.reset(config_key, org_id=org_id_str)

        # Audit
        audit_service.record(
            module="branding",
            action="branding_reset",
            entity_type="organization",
            entity_id=org_id_str,
            summary="Branding reset to defaults",
            actor_user_id=updated_by,
            organization_id=org_id_str,
        )

        logger.info(f"Branding reset to defaults for org {org_id_str}")
        return self.get_branding(org_id)

    # ──────────────────────────────────────────────────────────────────────
    #  Branding Preview
    # ──────────────────────────────────────────────────────────────────────

    def get_branding_preview(self, org_id: UUID) -> dict:
        """Get a preview of the branding for a tenant."""
        branding = self.get_branding(org_id)

        # Generate a preview CSS
        preview_css = f"""
        :root {{
            --primary: {branding.get('primary_color', '#4F46E5')};
            --secondary: {branding.get('secondary_color', '#7C3AED')};
            --accent: {branding.get('accent_color', '#10B981')};
            --background: {branding.get('background_color', '#FFFFFF')};
            --surface: {branding.get('surface_color', '#F9FAFB')};
            --text: {branding.get('text_color', '#111827')};
            --text-secondary: {branding.get('text_secondary_color', '#6B7280')};
            --border: {branding.get('border_color', '#E5E7EB')};
            --font-family: {branding.get('font_family', 'Inter, system-ui, sans-serif')};
            --heading-font: {branding.get('heading_font_family', 'Inter, system-ui, sans-serif')};
        }}
        """

        preview = {
            "organization_id": str(org_id),
            "branding": branding,
            "preview_css": preview_css,
            "has_logo": bool(branding.get("logo_url")),
            "has_custom_css": bool(branding.get("custom_css")),
            "has_custom_domain": bool(branding.get("custom_domain")),
            "is_default": self._is_default_branding(branding),
        }

        return preview

    def _is_default_branding(self, branding: dict) -> bool:
        """Check if branding is still at defaults."""
        for key, default in DEFAULT_BRANDING.items():
            if branding.get(key) != default:
                return False
        return True

    # ──────────────────────────────────────────────────────────────────────
    #  Branding Export/Import
    # ──────────────────────────────────────────────────────────────────────

    def export_branding(self, org_id: UUID) -> dict:
        """Export branding configuration as a JSON profile."""
        branding = self.get_branding(org_id)
        return {
            "version": "1.0",
            "exported_at": datetime.now(timezone.utc).isoformat(),
            "organization_id": str(org_id),
            "branding": branding,
        }

    def import_branding(
        self,
        db: Session,
        org_id: UUID,
        profile: dict,
        updated_by: Optional[int] = None,
    ) -> dict:
        """Import a branding configuration profile."""
        branding_data = profile.get("branding", {})
        if not isinstance(branding_data, dict):
            raise ValueError("Invalid branding profile: 'branding' must be a dict")

        return self.update_branding(db, org_id, branding_data, updated_by=updated_by)

    # ──────────────────────────────────────────────────────────────────────
    #  Custom Domain
    # ──────────────────────────────────────────────────────────────────────

    def set_custom_domain(
        self,
        db: Session,
        org_id: UUID,
        domain: str,
        updated_by: Optional[int] = None,
    ) -> dict:
        """Set a custom domain for a tenant."""
        # Validate domain format
        if domain and not self._validate_domain(domain):
            raise ValueError(f"Invalid domain format: {domain}")

        config_center.set(
            f"{BRANDING_PREFIX}custom_domain",
            domain,
            org_id=str(org_id),
        )
        config_center.set(
            f"{BRANDING_PREFIX}custom_domain_verified",
            False,
            org_id=str(org_id),
        )

        # Audit
        audit_service.record(
            module="branding",
            action="domain_set",
            entity_type="organization",
            entity_id=str(org_id),
            summary=f"Custom domain set: {domain}",
            actor_user_id=updated_by,
            organization_id=str(org_id),
        )

        logger.info(f"Custom domain set for org {org_id}: {domain}")
        return self.get_branding(org_id)

    def verify_domain(
        self,
        db: Session,
        org_id: UUID,
        domain: str,
        verified: bool = True,
        updated_by: Optional[int] = None,
    ) -> dict:
        """Mark a custom domain as verified."""
        config_center.set(
            f"{BRANDING_PREFIX}custom_domain_verified",
            verified,
            org_id=str(org_id),
        )

        audit_service.record(
            module="branding",
            action="domain_verified",
            entity_type="organization",
            entity_id=str(org_id),
            summary=f"Domain {'verified' if verified else 'unverified'}: {domain}",
            actor_user_id=updated_by,
            organization_id=str(org_id),
        )

        return self.get_branding(org_id)

    @staticmethod
    def _validate_domain(domain: str) -> bool:
        """Basic domain validation."""
        import re
        pattern = r"^([a-zA-Z0-9]([a-zA-Z0-9\-]{0,61}[a-zA-Z0-9])?\.)+[a-zA-Z]{2,}$"
        return bool(re.match(pattern, domain))

    # ──────────────────────────────────────────────────────────────────────
    #  Branding for Login Page
    # ──────────────────────────────────────────────────────────────────────

    def get_login_page_config(self, org_id: Optional[UUID] = None) -> dict:
        """Get login page branding configuration."""
        if org_id:
            branding = self.get_branding(org_id)
        else:
            branding = DEFAULT_BRANDING.copy()

        return {
            "logo_url": branding.get("login_page_logo_url") or branding.get("logo_url", ""),
            "title": branding.get("login_title", "Sign in to your account"),
            "subtitle": branding.get("login_subtitle", "Welcome back!"),
            "background_color": branding.get("login_background_color", "#F9FAFB"),
            "primary_button_color": branding.get("login_primary_button_color", "#4F46E5"),
            "primary_button_text_color": branding.get("login_primary_button_text_color", "#FFFFFF"),
            "show_remember_me": branding.get("login_show_remember_me", True),
            "show_forgot_password": branding.get("login_show_forgot_password", True),
            "show_social_login": branding.get("login_show_social_login", False),
            "custom_html": branding.get("login_custom_html", ""),
            "custom_css": branding.get("custom_css", ""),
            "custom_js": branding.get("custom_js", ""),
            "font_family": branding.get("font_family", "Inter, system-ui, sans-serif"),
            "custom_head_html": branding.get("custom_head_html", ""),
            "favicon_url": branding.get("favicon_url", ""),
            "footer_text": branding.get("footer_text", ""),
            "primary_color": branding.get("primary_color", "#4F46E5"),
        }


# Singleton
tenant_branding_service = TenantBrandingService()
