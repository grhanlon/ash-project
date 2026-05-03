/** Mirrors contagion/readthrough.py AUTO_DRIVER_LABELS for the web client. */
export const DRIVER_LABELS: Record<string, string> = {
  production_volume: "Production volume",
  mix_pricing: "Mix/pricing",
  ev_demand: "EV demand",
  warranty_quality: "Warranty/quality",
  labor_disruption: "Labor disruption",
  inventory_channel: "Inventory/channel",
  credit_rates: "Credit/rates",
  guidance_capex: "Guidance/capex",
};

export const DRIVER_KEYS = Object.keys(DRIVER_LABELS);
