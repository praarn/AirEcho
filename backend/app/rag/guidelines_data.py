"""Bundled guideline corpus.

These are short, faithful paraphrases of publicly published guidance so a fresh
clone is demoable offline. `source_url` points at the authoritative document;
replace `chunk_text` with verbatim passages (and keep the citations) if you index
the real PDFs. Every numeric threshold the advisory layer is allowed to state
must trace back to one of these chunks.
"""

from __future__ import annotations

GUIDELINES: list[dict] = [
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
    {
        "title": "CPCB National Air Quality Index — category summary",
        "publisher": "CPCB",
        "source_url": "https://cpcb.nic.in/National-Air-Quality-Index/",
        "sections": [
            (
                "CPCB NAQI §Categories",
                "India's National Air Quality Index has six categories: Good (0–50), "
                "Satisfactory (51–100), Moderate (101–200), Poor (201–300), Very Poor "
                "(301–400) and Severe (401–500). The index is the worst sub-index across "
                "eight pollutants, with PM2.5 and PM10 requiring a 24-hour average.",
            ),
            (
                "CPCB NAQI §Health statements — Moderate",
                "In the Moderate category (AQI 101–200) CPCB notes possible breathing "
                "discomfort for people with lung disease such as asthma, and discomfort "
                "for people with heart disease, children and older adults.",
            ),
            (
                "CPCB NAQI §Health statements — Poor and worse",
                "In the Poor category (AQI 201–300) CPCB notes breathing discomfort for "
                "most people on prolonged exposure. Very Poor (301–400) may cause "
                "respiratory illness on prolonged exposure; Severe (401–500) affects "
                "healthy people and seriously impacts those with existing disease. CPCB "
                "advises reducing prolonged or heavy outdoor exertion in these "
                "categories.",
            ),
            (
                "CPCB NAQI §PM2.5 breakpoints",
                "CPCB's 24-hour PM2.5 sub-index breakpoints are 0–30 (Good), 31–60 "
                "(Satisfactory), 61–90 (Moderate), 91–120 (Poor), 121–250 (Very Poor) "
                "and above 250 (Severe), in µg/m³.",
            ),
        ],
    },
]
