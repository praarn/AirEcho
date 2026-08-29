"""Bundled guideline corpus — India-first.

These are short, faithful paraphrases of publicly published guidance so a fresh
clone is demoable offline. `source_url` points at the authoritative document;
replace `chunk_text` with verbatim passages (and keep the citations) if you index
the real PDFs. Every numeric threshold the advisory layer is allowed to state
must trace back to one of these chunks.

CPCB (Central Pollution Control Board) is the primary authority for this project
because the modelled locations are in the Delhi-NCR airshed; WHO 2021 is kept as
a secondary global reference. `GUIDELINES` is ordered CPCB-first on purpose — the
retriever has no notion of priority, but a human reading a tie does.
"""

from __future__ import annotations

GUIDELINES: list[dict] = [
    {
        "title": "CPCB National Air Quality Index (NAQI)",
        "publisher": "CPCB",
        "source_url": "https://cpcb.nic.in/National-Air-Quality-Index/",
        "sections": [
            (
                "CPCB NAQI §Categories",
                "India's National Air Quality Index has six categories: Good (0–50), "
                "Satisfactory (51–100), Moderate (101–200), Poor (201–300), Very Poor "
                "(301–400) and Severe (401–500). The overall AQI is the worst sub-index "
                "across eight pollutants (PM2.5, PM10, NO2, SO2, CO, O3, NH3, Pb); at "
                "least three pollutants must be available, one of which must be PM2.5 or "
                "PM10. PM2.5 and PM10 sub-indices use a 24-hour average.",
            ),
            (
                "CPCB NAQI §PM2.5 sub-index breakpoints",
                "CPCB's 24-hour PM2.5 concentration breakpoints (µg/m³) map to AQI as: "
                "0–30 → 0–50 (Good), 31–60 → 51–100 (Satisfactory), 61–90 → 101–200 "
                "(Moderate), 91–120 → 201–300 (Poor), 121–250 → 301–400 (Very Poor) and "
                "250+ → 401–500 (Severe). The sub-index is linearly interpolated within "
                "each band.",
            ),
            (
                "CPCB NAQI §PM10 sub-index breakpoints",
                "CPCB's 24-hour PM10 concentration breakpoints (µg/m³) map to AQI as: "
                "0–50 → 0–50, 51–100 → 51–100, 101–250 → 101–200, 251–350 → 201–300, "
                "351–430 → 301–400 and 430+ → 401–500.",
            ),
            (
                "CPCB NAQI §Health statement — Good and Satisfactory",
                "In the Good category (AQI 0–50) CPCB records minimal health impact. In "
                "Satisfactory (51–100) it notes minor breathing discomfort to sensitive "
                "people, for example people with asthma on prolonged exposure.",
            ),
            (
                "CPCB NAQI §Health statement — Moderate",
                "In the Moderate category (AQI 101–200) CPCB notes breathing discomfort "
                "for people with lung disease such as asthma, and discomfort for people "
                "with heart disease, children and older adults. Sensitive groups should "
                "limit prolonged or heavy outdoor exertion.",
            ),
            (
                "CPCB NAQI §Health statement — Poor, Very Poor, Severe",
                "In the Poor category (AQI 201–300) CPCB notes breathing discomfort for "
                "most people on prolonged exposure. Very Poor (301–400) may cause "
                "respiratory illness on prolonged exposure. Severe (401–500) affects "
                "healthy people and seriously impacts those with existing disease; CPCB "
                "advises everyone avoid outdoor physical activity and that sensitive "
                "groups remain indoors.",
            ),
        ],
    },
    {
        "title": "National Ambient Air Quality Standards (NAAQS), India",
        "publisher": "CPCB",
        "source_url": "https://cpcb.nic.in/uploads/National_Ambient_Air_Quality_Standards.pdf",
        "sections": [
            (
                "NAAQS 2009 §PM2.5",
                "India's National Ambient Air Quality Standard for PM2.5 is a 24-hour "
                "average of 60 µg/m³ and an annual average of 40 µg/m³, applicable to "
                "industrial, residential, rural and other areas. These are the legal "
                "Indian ambient limits set by CPCB under the Air Act.",
            ),
            (
                "NAAQS 2009 §PM10",
                "India's National Ambient Air Quality Standard for PM10 is a 24-hour "
                "average of 100 µg/m³ and an annual average of 60 µg/m³.",
            ),
            (
                "NAAQS 2009 §NO2 and O3",
                "The Indian standard for NO2 is a 24-hour average of 80 µg/m³ and an "
                "annual average of 40 µg/m³. For ozone the standard is 100 µg/m³ as an "
                "8-hour average and 180 µg/m³ as a 1-hour average.",
            ),
        ],
    },
    {
        "title": "Graded Response Action Plan (GRAP), Delhi-NCR",
        "publisher": "CAQM / CPCB",
        "source_url": "https://caqm.nic.in/",
        "sections": [
            (
                "GRAP §Stages",
                "The Graded Response Action Plan for Delhi-NCR is triggered on AQI "
                "bands: Stage I from AQI 201 (Poor), Stage II from AQI 301 (Very Poor), "
                "Stage III from AQI 401 (Severe) and Stage IV from AQI 450 (Severe+). "
                "Higher stages add curbs such as bans on construction, on certain diesel "
                "vehicles, and on non-essential activities.",
            ),
            (
                "GRAP §Public health advice",
                "Under GRAP Stage III and IV the authorities advise the public to "
                "minimise outdoor exposure, that children, older adults and people with "
                "respiratory or cardiac conditions avoid outdoor activity, and that "
                "schools may shift to hybrid or online classes. N95/FFP2 masks are "
                "advised outdoors when AQI is in the Severe range.",
            ),
            (
                "GRAP §Seasonal context",
                "Delhi-NCR AQI is typically worst from late October to January, when "
                "cooler temperatures, low wind and a shallow boundary layer trap "
                "pollution, compounded by paddy-stubble burning in neighbouring states "
                "and firecracker emissions around Diwali. The monsoon months (July to "
                "September) usually see the cleanest air.",
            ),
        ],
    },
    {
        "title": "WHO Global Air Quality Guidelines 2021",
        "publisher": "WHO",
        "source_url": "https://www.who.int/publications/i/item/9789240034228",
        "sections": [
            (
                "WHO AQG 2021 §Recommended levels — PM2.5",
                "For fine particulate matter (PM2.5), WHO recommends an annual mean "
                "concentration not exceeding 5 µg/m³ and a 24-hour mean not exceeding "
                "15 µg/m³ on more than 3–4 days per year. PM2.5 penetrates deep into the "
                "lungs and enters the bloodstream; long-term exposure is linked to "
                "cardiovascular and respiratory mortality and lung cancer.",
            ),
            (
                "WHO AQG 2021 §Recommended levels — PM10",
                "For coarse particulate matter (PM10), the recommended annual mean is "
                "15 µg/m³ and the 24-hour mean is 45 µg/m³. PM10 is associated with "
                "aggravation of asthma and other respiratory conditions.",
            ),
            (
                "WHO AQG 2021 §Recommended levels — NO2",
                "For nitrogen dioxide (NO2), WHO recommends an annual mean of 10 µg/m³ "
                "and a 24-hour mean of 25 µg/m³. Short-term NO2 exposure can inflame the "
                "airways and worsen symptoms in people with asthma, including cough, "
                "wheezing and reduced lung function.",
            ),
            (
                "WHO AQG 2021 §Recommended levels — Ozone",
                "For ozone (O3), the recommended 8-hour mean is 100 µg/m³, and a peak "
                "season mean of 60 µg/m³ is recommended. Elevated ozone is associated "
                "with reduced lung function, airway inflammation and increased "
                "respiratory hospital admissions, with effects greater during exercise "
                "outdoors.",
            ),
            (
                "WHO AQG 2021 §Populations at higher risk",
                "Children, older adults, pregnant people, and individuals with "
                "pre-existing respiratory or cardiovascular disease are more susceptible "
                "to air pollution health effects. On days with elevated pollution these "
                "groups may benefit from reducing strenuous outdoor activity.",
            ),
            (
                "WHO AQG 2021 §Interim targets",
                "Where guideline levels cannot yet be met, WHO defines interim targets "
                "(e.g. PM2.5 24-hour interim targets of 75, 50, 37.5 and 25 µg/m³) to "
                "support gradual, measurable reductions in exposure. Interim targets are "
                "management milestones, not safe levels.",
            ),
        ],
    },
]
