import React from "react";
import { AppLayout } from "../components/layout/AppLayout";
import { HeroSection } from "../components/landing/HeroSection";
import { ProductPreview } from "../components/landing/ProductPreview";
import { PlatformOverview } from "../components/landing/PlatformOverview";
import { CapabilityGrid } from "../components/landing/CapabilityGrid";
import { AISection } from "../components/landing/AISection";
import { SecurityEnterpriseSection } from "../components/landing/SecurityEnterpriseSection";
import { PricingSection } from "../components/landing/PricingSection";
import { CTASection } from "../components/landing/CTASection";

/**
 * Public landing page.
 *
 * Only sections describing what the platform actually does are rendered.
 * The integrations matrix was removed: none of the advertised identity
 * providers, HR/payroll connectors or kiosk hardware are implemented
 * server-side, so publishing them on a public page would be false advertising.
 *
 * Pricing is rendered from the live plan catalog (GET /public/plans) rather
 * than hardcoded figures, so it cannot drift from what the backend enforces.
 */
export default function LandingPage() {
  return (
    <AppLayout>
      <div className="min-h-screen bg-gray-950 text-gray-100 font-sans selection:bg-indigo-500 selection:text-white">
        {/* Hero Section */}
        <HeroSection />

        {/* Interactive Product Preview */}
        <ProductPreview />

        {/* Platform Overview & Data Flow Architecture */}
        <PlatformOverview />

        {/* Capability Suite Grid */}
        <CapabilityGrid />

        {/* Dedicated AI & Copilot Section */}
        <AISection />

        {/* Security, RBAC & Multi-Tenancy */}
        <SecurityEnterpriseSection />

        {/* Pricing — rendered from the enforced plan catalog */}
        <PricingSection />

        {/* Final Conversion CTA */}
        <CTASection />
      </div>
    </AppLayout>
  );
}
