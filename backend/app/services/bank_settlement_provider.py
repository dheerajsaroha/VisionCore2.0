"""
bank_settlement_provider.py — Pluggable Bank Settlement Provider Abstraction
Sprint 8 — Automated Payroll Settlement Engine Integration

Architecture:
  BaseBankSettlementProvider (ABC)
   ├── SandboxBankProvider        (safe dev/test mock — never real transfers)
   ├── GenericCSVBankProvider     (generates NACHA-style CSV)
   └── GenericJSONBankProvider    (generates structured JSON payload)

CRITICAL DISCLAIMER:
  SandboxBankProvider and file-based providers do NOT initiate real bank transfers.
  Real bank integration requires a licensed payment provider and is NOT implemented here.
  Production deployments MUST replace SandboxBankProvider with a certified integration.
"""
from __future__ import annotations

import csv
import io
import json
import logging
import uuid
from abc import ABC, abstractmethod
from decimal import Decimal
from typing import Any, Optional

logger = logging.getLogger(__name__)


class BaseBankSettlementProvider(ABC):
    """Abstract base for bank settlement providers."""

    provider_id: str = "base"
    provider_name: str = "Base Provider"

    @abstractmethod
    def disburse(
        self,
        employee_id: int,
        amount: Decimal,
        currency: str,
        bank_account_id: Optional[int],
        settlement_id: int,
        **kwargs: Any,
    ) -> str:
        """
        Disburse payment to one employee.
        Returns a transaction reference string.
        Raises RuntimeError on failure.
        """

    @abstractmethod
    def generate_batch_file(
        self,
        items: list[dict[str, Any]],
        settlement_id: int,
        currency: str = "INR",
    ) -> tuple[str, bytes]:
        """
        Generate a bank batch file payload.
        Returns (filename, file_bytes).
        """

    def health_check(self) -> dict:
        return {"provider": self.provider_id, "status": "ok"}


# ── Sandbox Provider ───────────────────────────────────────────────────────────

class SandboxBankProvider(BaseBankSettlementProvider):
    """
    Safe development/test mock provider.
    Simulates success with a synthetic transaction reference.
    NEVER initiates real bank transfers.
    """
    provider_id = "sandbox"
    provider_name = "VisionCore Sandbox Bank (Mock — No Real Transfers)"

    def disburse(
        self,
        employee_id: int,
        amount: Decimal,
        currency: str,
        bank_account_id: Optional[int],
        settlement_id: int,
        **kwargs: Any,
    ) -> str:
        ref = f"SANDBOX-{settlement_id}-EMP{employee_id}-{uuid.uuid4().hex[:8].upper()}"
        logger.info("[SANDBOX] Simulated disburse: employee=%s, amount=%s %s, ref=%s", employee_id, amount, currency, ref)
        return ref

    def generate_batch_file(
        self, items: list[dict[str, Any]], settlement_id: int, currency: str = "INR"
    ) -> tuple[str, bytes]:
        payload = {
            "provider": "sandbox",
            "settlement_id": settlement_id,
            "currency": currency,
            "total_items": len(items),
            "items": items,
            "disclaimer": "SANDBOX ONLY — NOT A REAL BANK FILE",
        }
        filename = f"settlement_{settlement_id}_sandbox.json"
        return filename, json.dumps(payload, indent=2, default=str).encode("utf-8")


# ── Generic CSV Provider ───────────────────────────────────────────────────────

class GenericCSVBankProvider(BaseBankSettlementProvider):
    """
    Generates a generic CSV bank settlement file.
    Compatible with many bank EFT/NEFT import formats.
    Does NOT transmit the file — caller handles upload.
    """
    provider_id = "generic_csv"
    provider_name = "Generic CSV Bank Provider"

    def disburse(
        self,
        employee_id: int,
        amount: Decimal,
        currency: str,
        bank_account_id: Optional[int],
        settlement_id: int,
        **kwargs: Any,
    ) -> str:
        ref = f"CSV-{settlement_id}-EMP{employee_id}-{uuid.uuid4().hex[:8].upper()}"
        logger.info("[CSV Provider] Item queued: employee=%s, amount=%s, ref=%s", employee_id, amount, ref)
        return ref

    def generate_batch_file(
        self, items: list[dict[str, Any]], settlement_id: int, currency: str = "INR"
    ) -> tuple[str, bytes]:
        output = io.StringIO()
        writer = csv.writer(output)
        writer.writerow(["settlement_id", "employee_id", "amount", "currency", "account_masked", "bank_name", "reference", "status"])
        for item in items:
            writer.writerow([
                settlement_id,
                item.get("employee_id", ""),
                item.get("amount", ""),
                currency,
                item.get("account_masked", "****"),
                item.get("bank_name", ""),
                item.get("reference", ""),
                item.get("status", ""),
            ])
        filename = f"settlement_{settlement_id}_bank.csv"
        return filename, output.getvalue().encode("utf-8")


# ── Generic JSON Provider ──────────────────────────────────────────────────────

class GenericJSONBankProvider(BaseBankSettlementProvider):
    """
    Generates a structured JSON payment instruction file.
    Suitable for API-based bank integrations.
    Does NOT transmit to any bank — caller handles API call.
    """
    provider_id = "generic_json"
    provider_name = "Generic JSON Bank Provider"

    def disburse(
        self,
        employee_id: int,
        amount: Decimal,
        currency: str,
        bank_account_id: Optional[int],
        settlement_id: int,
        **kwargs: Any,
    ) -> str:
        ref = f"JSON-{settlement_id}-EMP{employee_id}-{uuid.uuid4().hex[:8].upper()}"
        logger.info("[JSON Provider] Payment instruction created: employee=%s, amount=%s, ref=%s", employee_id, amount, ref)
        return ref

    def generate_batch_file(
        self, items: list[dict[str, Any]], settlement_id: int, currency: str = "INR"
    ) -> tuple[str, bytes]:
        payload = {
            "schema_version": "1.0",
            "settlement_id": settlement_id,
            "currency": currency,
            "generated_at": __import__("datetime").datetime.utcnow().isoformat() + "Z",
            "payment_instructions": items,
        }
        filename = f"settlement_{settlement_id}_instructions.json"
        return filename, json.dumps(payload, indent=2, default=str).encode("utf-8")


# ── Provider Registry ──────────────────────────────────────────────────────────

_PROVIDERS: dict[str, BaseBankSettlementProvider] = {
    "sandbox":      SandboxBankProvider(),
    "generic_csv":  GenericCSVBankProvider(),
    "generic_json": GenericJSONBankProvider(),
}


def get_provider(provider_id: str) -> BaseBankSettlementProvider:
    """Return the provider for a given provider_id, defaulting to sandbox."""
    provider = _PROVIDERS.get(provider_id)
    if not provider:
        logger.warning("Unknown bank provider '%s', falling back to sandbox.", provider_id)
        return _PROVIDERS["sandbox"]
    return provider


def list_providers() -> list[dict]:
    return [{"id": p.provider_id, "name": p.provider_name} for p in _PROVIDERS.values()]
