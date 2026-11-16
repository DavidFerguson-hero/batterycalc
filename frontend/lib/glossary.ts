/**
 * Plain-English definitions shown by <Term>. Keep each one to a sentence or two,
 * written for someone who has never thought about their electricity tariff.
 */
export const GLOSSARY = {
  kwh: {
    label: "kWh",
    definition:
      "A kilowatt-hour: the unit your electricity is measured and charged in. Boiling a full kettle uses about a tenth of one; a typical home uses about 2,700 a year.",
  },
  epc: {
    label: "EPC",
    definition:
      "Energy Performance Certificate: the official rating (A to G) of how energy efficient a home is. Most homes sold or rented in the last ten years have one.",
  },
  tariff: {
    label: "tariff",
    definition:
      "The price plan you're on with your energy supplier: what you pay for each kWh, and a daily standing charge.",
  },
  time_of_use: {
    label: "time-of-use tariff",
    definition:
      "A tariff where electricity costs less at certain times, usually overnight. A battery can charge when it's cheap and power your home when it's dear.",
  },
  standing_charge: {
    label: "standing charge",
    definition: "A fixed daily amount you pay for your electricity supply, however much you use.",
  },
  payback: {
    label: "payback",
    definition:
      "How many years the battery takes to save as much as it cost to buy and fit. After that, the savings are yours to keep.",
  },
  warranty: {
    label: "warranty",
    definition:
      "How long the manufacturer guarantees the battery, usually 10 years. We call a battery worth it if it pays back well within this.",
  },
  inverter: {
    label: "inverter",
    definition:
      "The box that converts the battery's power into the kind your home uses. It usually needs replacing once during a battery's life.",
  },
  half_hourly: {
    label: "half-hourly data",
    definition:
      "A record from your smart meter of how much electricity you used in every half-hour. Most suppliers let you download it from your online account.",
  },
  export: {
    label: "export",
    definition: "Electricity you send back to the grid, for example from solar panels, which your supplier pays you for.",
  },
} as const satisfies Record<string, { label: string; definition: string }>;

export type GlossaryKey = keyof typeof GLOSSARY;
