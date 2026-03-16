"""ChromaDB RAG setup — connectivity check and seed data for benchmark runs.

Pre-seeds NDMA disaster response guidelines and historical Indian disaster
event data into ChromaDB so that HistoricalMemory and PredictiveRisk agents
can retrieve real documents during benchmark runs.

Collections seeded:
    - ndma_guidelines: NDMA SOPs, evacuation protocols, resource deployment norms
    - historical_events: Major Indian disasters with dates, impacts, and lessons

Uses Ollama nomic-embed-text for embeddings. Never crashes — logs warnings
and returns False if ChromaDB or Ollama is unavailable.
"""

from __future__ import annotations

import logging
from typing import Any

import chromadb
import httpx

from src.shared.config import get_settings

logger = logging.getLogger("crisis.rag_setup")

# =============================================================================
# Seed Data — NDMA Guidelines (factual content from NDMA SOPs/guidelines)
# =============================================================================

NDMA_GUIDELINES: list[dict[str, Any]] = [
    {
        "id": "ndma_cyclone_evac_01",
        "text": (
            "NDMA Cyclone Management Guidelines — Evacuation Protocol. "
            "The National Disaster Management Authority mandates that state governments "
            "initiate evacuation of coastal populations within 48 hours of a cyclone "
            "landfall forecast by IMD. Priority evacuation applies to kutcha houses, "
            "thatched dwellings, and low-lying areas within 5 km of the coastline. "
            "District Collectors shall activate Cyclone Warning Centres and ensure "
            "communication through public address systems, television, All India Radio, "
            "and mobile SMS alerts via the Common Alerting Protocol (CAP). Pre-positioned "
            "cyclone shelters must accommodate at least 1,000 persons per shelter within "
            "a 2 km radius of vulnerable settlements. Evacuation routes must be marked, "
            "cleared of obstructions, and illuminated. NDRF teams shall be pre-deployed "
            "at least 24 hours before expected landfall. State Disaster Response Force "
            "(SDRF) and district administration must coordinate with Indian Navy and "
            "Coast Guard for offshore evacuation of fishing vessels. The IMD T-number "
            "and Dvorak technique classification determines the resource tier activated."
        ),
        "metadata": {
            "source": "NDMA",
            "category": "cyclone",
            "document_type": "guideline",
            "date": "2019-11-01",
        },
    },
    {
        "id": "ndma_cyclone_shelter_02",
        "text": (
            "NDMA Cyclone Shelter Standards and Management. Multi-purpose cyclone "
            "shelters (MPCS) must be designed to withstand wind speeds of 300 km/h "
            "and storm surges up to 5 metres. Each shelter must have a capacity of "
            "at least 2,000 persons with 3.5 sq metres per person. Essential provisions "
            "include emergency lighting (solar-powered with 72-hour battery backup), "
            "potable water storage (20 litres per person per day for 3 days), "
            "first aid and medical supplies, communication equipment (VHF radio and "
            "satellite phone), and separate toilet facilities for men and women. "
            "Shelters must be provisioned with dry rations for 72 hours. Animal "
            "shelters must be located adjacent to human shelters. NDMA guidelines "
            "require one cyclone shelter per 1.5 km of vulnerable coastline. Shelter "
            "management committees comprising local Panchayat members must be trained "
            "annually. Odisha's model of community-managed cyclone shelters, which "
            "proved effective during Cyclone Fani (2019), is recommended as the "
            "national standard."
        ),
        "metadata": {
            "source": "NDMA",
            "category": "cyclone",
            "document_type": "guideline",
            "date": "2020-03-15",
        },
    },
    {
        "id": "ndma_flood_response_03",
        "text": (
            "NDMA Flood Management Guidelines — Response Phase. Upon receipt of "
            "flood warnings from the Central Water Commission (CWC), District "
            "Collectors must activate the District Emergency Operations Centre (DEOC) "
            "and issue alerts through NDMA's SACHET platform. Evacuation priorities: "
            "(1) persons with disabilities and elderly, (2) women and children, "
            "(3) livestock, (4) essential documents and valuables. Flood rescue "
            "operations require NDRF teams with motorised inflatable boats (capacity "
            "12 persons), high-powered water pumps, and life-saving equipment. "
            "Each NDRF battalion maintains 18 rescue teams. The SDRF supplements "
            "with state-level assets. Community-based flood warning systems using "
            "river gauges and rain gauges must be operational in flood-prone districts. "
            "Relief camps must provide 7 sq metres per family, clean drinking water "
            "(minimum 15 litres per person per day), cooked food twice daily, and "
            "medical screening within 24 hours. Dewatering operations commence "
            "immediately after recession begins. CWC provides hourly water level "
            "bulletins for all major rivers during flood season (June-October)."
        ),
        "metadata": {
            "source": "NDMA",
            "category": "flood",
            "document_type": "guideline",
            "date": "2019-06-01",
        },
    },
    {
        "id": "ndma_flood_urban_04",
        "text": (
            "NDMA Urban Flood Management Guidelines. Urban flooding results from "
            "inadequate drainage, encroachment on natural waterways, and impervious "
            "surfaces. NDMA mandates that municipal corporations maintain stormwater "
            "drainage capacity for 50 mm/hour rainfall intensity. Pre-monsoon "
            "desilting of drains must be completed by May 31 each year. Real-time "
            "flood monitoring using Automatic Weather Stations (AWS) and water level "
            "sensors at critical underpasses and low-lying areas is mandatory. Urban "
            "Local Bodies must maintain a GIS database of flood-prone areas with "
            "census vulnerability overlay. Electric substations in flood-prone zones "
            "must be elevated or waterproofed. Emergency pumping stations with diesel "
            "backup must be operational at identified waterlogging hotspots. Traffic "
            "police coordination is required to divert vehicles from waterlogged "
            "areas. NDMA recommends adoption of sponge city concepts: permeable "
            "pavements, rainwater harvesting, retention ponds, and green roofs."
        ),
        "metadata": {
            "source": "NDMA",
            "category": "flood",
            "document_type": "guideline",
            "date": "2020-05-10",
        },
    },
    {
        "id": "ndma_earthquake_response_05",
        "text": (
            "NDMA Earthquake Management Guidelines — Immediate Response. India is "
            "divided into four seismic zones (II-V) per IS 1893. Zone V (highest risk) "
            "covers Northeast India, Jammu & Kashmir, Himachal Pradesh, Uttarakhand, "
            "parts of Gujarat (Kutch), and Andaman & Nicobar Islands. Upon occurrence "
            "of an earthquake of magnitude 5.0 or above, the National Earthquake "
            "Response is activated. NDRF deploys within 6 hours from the nearest "
            "battalion. Search and rescue operations follow the Incident Response "
            "System (IRS) protocol. Structural triage of buildings uses rapid visual "
            "screening (RVS) methodology. Hospitals activate Mass Casualty Management "
            "protocols. NDMA mandates earthquake-resistant construction as per IS 4326, "
            "IS 13920, and IS 13935. Retrofitting of lifeline structures (hospitals, "
            "schools, fire stations) is prioritized. The National Seismological Network "
            "operated by IMD provides real-time magnitude and epicentre data within "
            "5 minutes of an event."
        ),
        "metadata": {
            "source": "NDMA",
            "category": "earthquake",
            "document_type": "guideline",
            "date": "2018-09-01",
        },
    },
    {
        "id": "ndma_earthquake_sar_06",
        "text": (
            "NDMA Search and Rescue Protocol for Earthquake Response. NDRF conducts "
            "urban search and rescue (USAR) operations in three phases: (1) Surface "
            "rescue (first 6 hours) — rescuing persons visible or lightly trapped using "
            "basic tools, (2) Light rescue (6-24 hours) — using acoustic listening "
            "devices, search cameras, and pneumatic tools, (3) Heavy rescue (24-72 hours) "
            "— using concrete cutters, cranes, and heavy lifting equipment. Each NDRF "
            "team of 45 personnel carries: 4-gas detectors, thermal imaging cameras, "
            "hydraulic spreaders and cutters, shoring equipment, and medical supplies. "
            "K-9 search dog teams are deployed within 12 hours. International USAR teams "
            "are requested through INSARAG protocols if local capacity is overwhelmed. "
            "Building collapse triage follows the START protocol: Immediate (Red), "
            "Delayed (Yellow), Minor (Green), Expectant (Black). Field medical teams "
            "establish casualty collection points within 500 metres of collapsed "
            "structures. Aftershock advisories from IMD determine re-entry safety."
        ),
        "metadata": {
            "source": "NDMA",
            "category": "earthquake",
            "document_type": "guideline",
            "date": "2018-09-01",
        },
    },
    {
        "id": "ndma_heatwave_07",
        "text": (
            "NDMA Heatwave Management Guidelines. A heatwave is declared when the "
            "actual maximum temperature reaches 40 degrees Celsius in plains (30 degrees "
            "in hilly regions) and the departure from normal exceeds 4.5 degrees. "
            "Severe heatwave: departure exceeds 6.5 degrees. IMD issues colour-coded "
            "alerts: Yellow (watch), Orange (alert), Red (warning). NDMA response "
            "protocol includes: suspension of outdoor work during 12:00-15:00 hours, "
            "opening of cooling shelters with ORS distribution, increased water supply "
            "tanker deployment, hospital preparedness for heat stroke and heat exhaustion "
            "cases, special provisions for outdoor workers (construction, agriculture, "
            "traffic police). District administration must coordinate with electricity "
            "distribution companies to prevent power cuts during heatwave periods. "
            "Rajasthan, Telangana, and Andhra Pradesh Heat Action Plans serve as "
            "national models. Ahmedabad's Heat Action Plan (2013), India's first, "
            "has been credited with reducing heat-related mortality by 30-40 percent."
        ),
        "metadata": {
            "source": "NDMA",
            "category": "heatwave",
            "document_type": "guideline",
            "date": "2019-04-01",
        },
    },
    {
        "id": "ndma_landslide_08",
        "text": (
            "NDMA Landslide Risk Management Guidelines. India has identified 0.42 "
            "million sq km as landslide-prone, covering the Himalayas, Northeast India, "
            "Western Ghats, Nilgiris, and Eastern Ghats. Geological Survey of India "
            "(GSI) maintains a Landslide Susceptibility Zonation (LSZ) atlas. NDMA "
            "mandates early warning systems combining rainfall thresholds, slope "
            "stability monitoring (inclinometers), and InSAR satellite data. Rainfall "
            "intensity-duration thresholds for landslide initiation: >100 mm in 24 hours "
            "for vulnerable slopes. Evacuation triggers: visible cracks in slopes, "
            "tilting of trees or poles, sudden appearance or disappearance of springs, "
            "unusual sounds from slopes. Response protocol: establish 200-metre "
            "exclusion zone around landslide site, check for landslide dam formation "
            "on rivers (risk of GLOF — glacial lake outburst flood), deploy NDRF "
            "teams with slope stabilisation equipment. Post-event: GSI assesses slope "
            "stability for re-habitation clearance."
        ),
        "metadata": {
            "source": "NDMA",
            "category": "landslide",
            "document_type": "guideline",
            "date": "2019-07-01",
        },
    },
    {
        "id": "ndma_industrial_09",
        "text": (
            "NDMA Chemical Disaster Management Guidelines. India has 1,861 Major "
            "Accident Hazard (MAH) units under the Manufacture, Storage and Import "
            "of Hazardous Chemical Rules, 1989. NDMA mandates on-site and off-site "
            "emergency plans for all MAH units. Off-site emergency plans must include: "
            "identification of hazardous chemicals and maximum credible accident "
            "scenarios, emergency response zones (lethal, serious injury, and "
            "vulnerable zones based on ALOHA/PHAST dispersion modelling), evacuation "
            "routes away from wind direction, hospital preparedness with antidote "
            "stocks, and public warning systems (siren codes: steady tone for shelter "
            "in place, warbling tone for evacuation). NDRF has 6 Chemical, Biological, "
            "Radiological, and Nuclear (CBRN) teams. District administration maintains "
            "a chemical disaster emergency directory. Annual mock drills are mandatory "
            "for all MAH units. The Bhopal Gas Tragedy (1984) — methyl isocyanate "
            "leak from Union Carbide killing 3,787 officially (estimates up to 16,000) "
            "— remains the reference worst-case industrial disaster for India."
        ),
        "metadata": {
            "source": "NDMA",
            "category": "industrial",
            "document_type": "guideline",
            "date": "2020-01-15",
        },
    },
    {
        "id": "ndma_tsunami_10",
        "text": (
            "NDMA Tsunami Management Guidelines. The Indian Tsunami Early Warning "
            "Centre (ITEWC) at INCOIS, Hyderabad, monitors seismic activity across "
            "the Indian Ocean using a network of seismometers, DART buoys, and tide "
            "gauges. Tsunami warnings are issued within 10 minutes of a tsunamigenic "
            "earthquake (magnitude 6.5 or above in the Indian Ocean). Warning "
            "dissemination: direct alerts to coastal District Collectors, IMD, NDMA, "
            "Indian Navy, Coast Guard, and state EOCs. Coastal populations within 1 km "
            "of the shoreline must evacuate to higher ground (minimum 10 metres above "
            "sea level) or to designated tsunami shelters. Evacuation time target: 20 "
            "minutes from warning issuance to complete evacuation of high-risk zones. "
            "Vulnerable coastal states: Tamil Nadu, Andhra Pradesh, Kerala, Odisha, "
            "Gujarat, and Andaman & Nicobar Islands. Community-based tsunami "
            "preparedness programmes include biannual evacuation drills. Indian Ocean "
            "Tsunami Ready Programme (IOC-UNESCO) recognition is being pursued for "
            "all coastal districts."
        ),
        "metadata": {
            "source": "NDMA",
            "category": "tsunami",
            "document_type": "guideline",
            "date": "2018-12-01",
        },
    },
    {
        "id": "ndma_incident_response_11",
        "text": (
            "NDMA Incident Response System (IRS) Framework. India adopted the Incident "
            "Response System as the standard emergency management framework in 2010. "
            "IRS establishes a unified command structure: Responsible Officer (RO) at "
            "district level (District Collector/Magistrate), Incident Commander (IC) "
            "at the incident site, and Section Chiefs for Operations, Planning, "
            "Logistics, and Finance. The National Executive Committee (NEC) chaired "
            "by Home Secretary activates national-level response. State Executive "
            "Committee (SEC) chaired by Chief Secretary activates state response. "
            "Multi-agency coordination through the National Crisis Management Committee "
            "(NCMC) chaired by Cabinet Secretary for L3 (national) level disasters. "
            "L0 (district), L1 (state), L2 (regional), L3 (national) classification "
            "determines resource deployment scale. IRS training is mandatory for all "
            "disaster management officers. Emergency Operations Centres operate 24x7 "
            "at national (NEOC), state (SEOC), and district (DEOC) levels during "
            "disaster activation."
        ),
        "metadata": {
            "source": "NDMA",
            "category": "general",
            "document_type": "guideline",
            "date": "2019-01-01",
        },
    },
    {
        "id": "ndma_resource_deployment_12",
        "text": (
            "NDMA Resource Deployment Norms. NDRF maintains 16 battalions (12 from "
            "Border Security Force, Central Reserve Police Force, Central Industrial "
            "Security Force, Indo-Tibetan Border Police, and Sashastra Seema Bal; "
            "4 raised additionally). Each battalion has 18 specialist rescue teams "
            "of 45 personnel each, equipped for flood, earthquake, CBRN, and high-altitude "
            "rescue. Pre-positioning norms: NDRF teams deployed to probable impact zones "
            "24-48 hours before expected disaster (cyclone, flood). Indian Air Force "
            "helicopters (Mi-17, Chinook, ALH) are requisitioned for aerial rescue and "
            "supply drops. Indian Navy deploys warships with medical facilities and "
            "landing craft for coastal and island operations. Army Engineering Corps "
            "provides bridge-laying, route clearance, and construction. SDMA/SDRF "
            "resources supplement NDRF. State-wise pre-positioning plans are activated "
            "based on IMD seasonal forecast. Relief material pre-positioning includes "
            "tents (20,000), tarpaulins (50,000), blankets (100,000), water purification "
            "units, and medical kits at strategic warehouses."
        ),
        "metadata": {
            "source": "NDMA",
            "category": "general",
            "document_type": "guideline",
            "date": "2020-06-01",
        },
    },
    {
        "id": "ndma_communication_13",
        "text": (
            "NDMA Disaster Communication Guidelines. Multi-channel warning dissemination "
            "is mandatory: (1) Cell Broadcasting Service (CBS) for location-specific "
            "alerts via mobile networks, (2) Common Alerting Protocol (CAP) alerts via "
            "SACHET platform to all registered agencies, (3) All India Radio emergency "
            "broadcasts in regional languages, (4) Doordarshan emergency tickers and "
            "bulletins, (5) Social media (Twitter/X, Facebook, WhatsApp) alerts through "
            "verified government handles, (6) Public address systems in vulnerable areas, "
            "(7) Siren systems in coastal areas (tsunami/cyclone). Warning messages must "
            "be issued in English, Hindi, and the relevant state language. NDMA mandates "
            "colour-coded warning levels: Green (no action), Yellow (watch), Orange "
            "(alert/be prepared), Red (warning/take action). Community communication "
            "volunteers (Aapda Mitra) trained at gram panchayat level serve as the "
            "last-mile dissemination channel. NDMA operates a 24x7 Control Room "
            "(toll-free number 1078) and WhatsApp helpline for disaster information."
        ),
        "metadata": {
            "source": "NDMA",
            "category": "general",
            "document_type": "guideline",
            "date": "2020-08-01",
        },
    },
    {
        "id": "ndma_medical_14",
        "text": (
            "NDMA Medical Preparedness and Mass Casualty Management. District hospitals "
            "in disaster-prone areas must maintain Mass Casualty Incident (MCI) plans "
            "with surge capacity for 200 percent of normal bed strength. Trauma centres "
            "must be accessible within the golden hour (60 minutes). Mobile medical "
            "units from the National Health Mission supplement district hospital capacity. "
            "NDMA mandates: pre-positioned medical supplies for 10,000 persons for 7 "
            "days, blood bank reserves maintained at 150 percent during disaster season, "
            "telemedicine connectivity to tertiary hospitals, disease surveillance under "
            "the Integrated Disease Surveillance Programme (IDSP) activated within 24 "
            "hours of disaster onset, water quality monitoring teams deployed within "
            "48 hours, vector control measures for malaria and dengue initiated within "
            "72 hours in flood-affected areas. Mental health first aid teams from NIMHANS "
            "and state mental health authorities are deployed for psychosocial support "
            "within one week. Post-disaster epidemiological surveillance continues for "
            "30 days for waterborne diseases (cholera, typhoid, hepatitis A)."
        ),
        "metadata": {
            "source": "NDMA",
            "category": "general",
            "document_type": "guideline",
            "date": "2019-10-01",
        },
    },
    {
        "id": "ndma_drought_15",
        "text": (
            "NDMA Drought Management Guidelines. India's Drought Management framework "
            "uses the Standardised Precipitation Index (SPI) and Vegetation Condition "
            "Index (VCI) from ISRO satellites for drought declaration. District-level "
            "drought is declared when rainfall deficit exceeds 50 percent of the Long "
            "Period Average (LPA) and crop condition assessments confirm severe stress. "
            "Immediate response includes: activation of MGNREGA (Mahatma Gandhi National "
            "Rural Employment Guarantee Act) for emergency employment, cattle camps "
            "with fodder supply, drinking water supply through tankers and tube wells, "
            "mid-day meal continuation in schools, and Public Distribution System (PDS) "
            "enhancement. State governments release gratuitous relief for vulnerable "
            "populations. Long-term measures include watershed development, micro-irrigation, "
            "farm pond construction, and crop insurance activation under PMFBY (Pradhan "
            "Mantri Fasal Bima Yojana). Input subsidy for affected farmers is provided "
            "under SDRF/NDRF norms. Water conservation and rainwater harvesting are "
            "promoted through Jal Shakti Abhiyan."
        ),
        "metadata": {
            "source": "NDMA",
            "category": "drought",
            "document_type": "guideline",
            "date": "2019-05-01",
        },
    },
    {
        "id": "ndma_flood_early_warning_16",
        "text": (
            "NDMA Flood Early Warning System Protocol. The Central Water Commission "
            "(CWC) operates 1,600+ hydrological observation stations and 375 flood "
            "forecasting stations across India. Flood forecasts are issued when water "
            "levels are expected to cross the Warning Level at any station. Three levels: "
            "Warning Level (lowest), Danger Level (intermediate), Highest Flood Level "
            "(HFL, historical maximum). CWC issues 72-hour advance flood forecasts using "
            "Sacramento model, MIKE 11, and HEC-RAS hydrological models. IMD provides "
            "Quantitative Precipitation Forecasts (QPF) as input. NDMA mandates "
            "integration of CWC flood forecasts with the SACHET platform for automated "
            "alert dissemination. State Flood Control Rooms operate 24x7 during "
            "monsoon (June-October). Dam operators must follow rule curves and maintain "
            "flood cushion as per Central Water Commission guidelines. Emergency "
            "release protocols require 24-hour advance warning to downstream populations. "
            "Brahmaputra, Ganga, Mahanadi, Godavari, and Krishna river systems receive "
            "priority monitoring."
        ),
        "metadata": {
            "source": "NDMA",
            "category": "flood",
            "document_type": "guideline",
            "date": "2020-05-15",
        },
    },
]

# =============================================================================
# Seed Data — Historical Indian Disasters (factual records)
# =============================================================================

HISTORICAL_EVENTS: list[dict[str, Any]] = [
    {
        "id": "hist_odisha_1999_01",
        "text": (
            "1999 Odisha Super Cyclone. On October 29, 1999, a Super Cyclonic Storm "
            "struck Odisha with wind speeds exceeding 260 km/h — the strongest recorded "
            "tropical cyclone in the North Indian Ocean. The cyclone made landfall near "
            "Paradip, Jagatsinghpur district. Storm surge of 7-8 metres inundated areas "
            "up to 35 km inland. Official death toll: 9,887 persons (unofficial estimates "
            "15,000+). 15 million people affected across 14 districts. 1.67 million houses "
            "destroyed. 90 percent of coconut and cashew plantations destroyed. Total "
            "economic loss estimated at USD 4.5 billion. Major response failures: complete "
            "communication breakdown for 5 days, no pre-positioned relief material, "
            "delayed rescue operations. Key lessons: (1) India established NDMA and NDRF "
            "following this disaster, (2) Odisha built 879 cyclone shelters and established "
            "the Odisha State Disaster Management Authority (OSDMA) as a model for other "
            "states, (3) Improved early warning systems and community-based disaster "
            "preparedness programmes were initiated."
        ),
        "metadata": {
            "source": "historical_record",
            "category": "cyclone",
            "date": "1999-10-29",
            "location": "Odisha",
            "severity": "super_cyclone",
        },
    },
    {
        "id": "hist_bhuj_2001_02",
        "text": (
            "2001 Gujarat Earthquake (Bhuj Earthquake). On January 26, 2001 (Republic "
            "Day), a magnitude 7.7 earthquake struck Bhuj, Kutch district, Gujarat, "
            "at 08:46 IST. Focal depth: 23 km. The earthquake was felt across South "
            "Asia up to 1,000 km from the epicentre. Death toll: 20,005 persons. "
            "167,000 injured. 339,000 buildings destroyed and 783,000 damaged. "
            "Total economic loss: USD 5.5 billion. Entire towns (Bhuj, Anjar, Bhachau, "
            "Rapar) devastated with 90 percent building collapse. Key factors: "
            "unreinforced masonry buildings, poor construction quality, holiday "
            "(Republic Day) concentration of people. Response: Indian Armed Forces "
            "deployed 50,000 troops. International assistance from 40 countries. "
            "Key lessons: (1) Gujarat State Disaster Management Authority established, "
            "(2) Building code IS 1893 revised to include Seismic Zone V for Kutch, "
            "(3) Gujarat implemented 'Build Back Better' reconstruction with "
            "earthquake-resistant technology, (4) Owner-Driven Reconstruction (ODR) "
            "model adopted, (5) Earthquake engineering training for masons institutionalised."
        ),
        "metadata": {
            "source": "historical_record",
            "category": "earthquake",
            "date": "2001-01-26",
            "location": "Gujarat",
            "severity": "magnitude_7.7",
        },
    },
    {
        "id": "hist_tsunami_2004_03",
        "text": (
            "2004 Indian Ocean Tsunami — Impact on India. On December 26, 2004, a "
            "magnitude 9.1 earthquake off Sumatra generated a devastating tsunami. "
            "The tsunami struck India's eastern coast within 2 hours. Death toll in "
            "India: 10,749 persons. Worst affected: Tamil Nadu (6,065 deaths), "
            "Andaman & Nicobar Islands (3,513 deaths), Pondicherry (590 deaths), "
            "Andhra Pradesh (105 deaths), Kerala (171 deaths). 2.79 million people "
            "affected. 157,000 houses damaged. Nagapattinam district in Tamil Nadu "
            "was the worst hit mainland location with 6,000 deaths. The Car Nicobar "
            "Air Force Station was completely inundated. Key response: Indian Navy "
            "launched Operation Sea Waves (largest peacetime naval relief operation). "
            "Key lessons: (1) India established the Indian Tsunami Early Warning Centre "
            "(ITEWC) at INCOIS Hyderabad in 2007, (2) Coastal bio-shield (mangrove "
            "plantation) programmes initiated, (3) Coastal Regulation Zone rules "
            "strengthened, (4) Community-based tsunami preparedness programmes in "
            "coastal villages, (5) DART buoy network deployed in Indian Ocean."
        ),
        "metadata": {
            "source": "historical_record",
            "category": "tsunami",
            "date": "2004-12-26",
            "location": "Tamil Nadu, Andaman & Nicobar",
            "severity": "magnitude_9.1_tsunami",
        },
    },
    {
        "id": "hist_mumbai_floods_2005_04",
        "text": (
            "2005 Mumbai Floods (26 July 2005). Mumbai received 944 mm of rainfall "
            "in 24 hours on July 26, 2005 — the highest single-day rainfall ever "
            "recorded in any Indian city. The Mithi River overflowed catastrophically. "
            "Death toll: 1,094 persons. 14,000 stranded on roads and in vehicles. "
            "Traffic paralysed for 3 days. Mumbai's Chhatrapati Shivaji International "
            "Airport shut for 30 hours. Mumbai suburban rail network (carrying 7 million "
            "daily passengers) completely halted. Financial loss: USD 3.3 billion. "
            "Key failures: encroachment on Mithi River floodplain, inadequate stormwater "
            "drainage (designed for 25 mm/hour, received 40 mm/hour), absence of flood "
            "warning systems for urban areas. Response: Indian Navy and Army deployed "
            "for rescue. Key lessons: (1) Chitale Committee recommended comprehensive "
            "drainage overhaul, (2) Mithi River restoration project initiated, "
            "(3) Mumbai established Disaster Management Cell in BMC, (4) Real-time "
            "rain gauge network installed, (5) Established the precedent for urban "
            "flood management guidelines by NDMA."
        ),
        "metadata": {
            "source": "historical_record",
            "category": "flood",
            "date": "2005-07-26",
            "location": "Maharashtra",
            "severity": "extreme_urban_flood",
        },
    },
    {
        "id": "hist_kashmir_floods_2014_05",
        "text": (
            "2014 Jammu & Kashmir Floods. In September 2014, unprecedented rainfall "
            "caused the Jhelum River and its tributaries to overflow, inundating large "
            "parts of Srinagar and other areas. Death toll: 277 persons. 1.8 million "
            "people affected. One-third of Srinagar city submerged for weeks. Flood "
            "levels exceeded the 1903 record at Ram Munshi Bagh gauge. Total damage: "
            "USD 16 billion (PDNA estimate). 108,000 persons rescued by Indian Armed "
            "Forces in Operation Megh Rahat — the largest flood rescue operation by "
            "any military worldwide. Indian Air Force flew 2,788 sorties. Navy deployed "
            "MARCOS and diving teams. Key challenges: complete communication failure, "
            "road network destruction isolating Kashmir Valley, urban flooding in "
            "Srinagar due to encroachment on Dal Lake and Jhelum floodplain, disruption "
            "of all essential services for 2 weeks. Lessons: (1) Need for dedicated "
            "urban flood early warning, (2) Floodplain zoning enforcement, (3) Military "
            "rescue capacity proved essential for Kashmir geography."
        ),
        "metadata": {
            "source": "historical_record",
            "category": "flood",
            "date": "2014-09-05",
            "location": "Jammu & Kashmir",
            "severity": "extreme_flood",
        },
    },
    {
        "id": "hist_uttarakhand_2013_06",
        "text": (
            "2013 Uttarakhand Flash Floods (Kedarnath Disaster). On June 16-17, 2013, "
            "cloudburst and glacial lake outburst flood (GLOF) devastated the Kedarnath "
            "area in Uttarakhand. Chorabari Tal glacial lake breached, sending massive "
            "debris flows down the Mandakini Valley. Death toll: officially 5,748 persons "
            "(estimates up to 10,000 including missing). 4,200 villages affected. Over "
            "100,000 pilgrims were stranded in the Char Dham pilgrimage route. The "
            "Kedarnath temple survived but was buried under 2 metres of debris. "
            "70,000 persons rescued by Indian Air Force (Operation Rahat — largest "
            "helicopter rescue operation globally, 2,137 sorties). Road infrastructure "
            "completely destroyed in 5 districts. Losses: USD 3.8 billion. Key lessons: "
            "(1) GLOF monitoring and early warning systems needed for Himalayan glacial "
            "lakes, (2) Unregulated construction in river floodplains and avalanche "
            "zones, (3) Carrying capacity assessment needed for pilgrimage routes, "
            "(4) Real-time weather monitoring stations inadequate in mountainous terrain, "
            "(5) NDMA issued comprehensive landslide and GLOF guidelines subsequently."
        ),
        "metadata": {
            "source": "historical_record",
            "category": "flood",
            "date": "2013-06-16",
            "location": "Uttarakhand",
            "severity": "catastrophic_flash_flood",
        },
    },
    {
        "id": "hist_chennai_floods_2015_07",
        "text": (
            "2015 Chennai Floods. From November 8 to December 4, 2015, Chennai and "
            "adjoining districts received 1,049 mm of rainfall (November-December), "
            "three times the normal average. The Adyar, Cooum, and Kosasthalaiyar rivers "
            "overflowed. On December 1, Chembarambakkam reservoir released 29,000 cusecs "
            "without adequate warning. Death toll: 347 persons. 1.8 million people "
            "displaced. Chennai Airport shut for 11 days. Economic loss: USD 3 billion. "
            "500,000 vehicles damaged. IT corridor (Sholinganallur, OMR) submerged. "
            "Tamil Nadu lost 20 percent of paddy crop. Key failures: Chembarambakkam "
            "reservoir release without adequate downstream warning, encroachment on "
            "Pallikaranai marshland (natural flood absorber), lack of flood hazard "
            "mapping for city planning. Response: NDRF deployed 18 teams. Indian "
            "Navy and Army conducted rescue operations. Lessons: (1) Dam release "
            "protocol reform with mandatory 24-hour advance warning, (2) Urban wetland "
            "conservation critical for flood absorption, (3) Chennai Smart City flood "
            "resilience plan developed, (4) Real-time water level monitoring on all "
            "three rivers established."
        ),
        "metadata": {
            "source": "historical_record",
            "category": "flood",
            "date": "2015-12-01",
            "location": "Tamil Nadu",
            "severity": "extreme_urban_flood",
        },
    },
    {
        "id": "hist_kerala_floods_2018_08",
        "text": (
            "2018 Kerala Floods. Between August 1-19, 2018, Kerala received 758 mm "
            "of rainfall — 164 percent above normal. Described as the worst floods in "
            "Kerala since 1924. All 14 districts affected. 35 of 54 dams opened "
            "simultaneously (first time in history), including Idukki Dam. Death toll: "
            "483 persons. 1.4 million people displaced to 3,274 relief camps. 20,000 km "
            "of roads damaged. 221 bridges damaged or destroyed. Economic loss: "
            "USD 5.6 billion (Post-Disaster Needs Assessment). Fishermen rescue "
            "operations became iconic — 669 fishing boats rescued over 65,000 persons "
            "from flooded areas. Indian Armed Forces rescued 26,000 persons. IAF "
            "conducted 316 helicopter sorties. Key lessons: (1) Dam management protocols "
            "revised — staggered release mandated, (2) Fishermen boats formally "
            "integrated into state disaster response plans, (3) Kerala adopted Rebuild "
            "Kerala Initiative for climate-resilient reconstruction, (4) Real-time "
            "dam monitoring dashboard created, (5) Landslide susceptibility mapping "
            "for Western Ghats prioritised."
        ),
        "metadata": {
            "source": "historical_record",
            "category": "flood",
            "date": "2018-08-15",
            "location": "Kerala",
            "severity": "worst_in_century",
        },
    },
    {
        "id": "hist_fani_2019_09",
        "text": (
            "Cyclone Fani (2019). Extremely Severe Cyclonic Storm Fani (category "
            "equivalent to Category 4 hurricane) made landfall near Puri, Odisha on "
            "May 3, 2019 with sustained winds of 175 km/h and gusts up to 205 km/h. "
            "Fani was the strongest cyclone to hit Odisha since the 1999 Super Cyclone. "
            "Death toll: 89 persons (compared to 9,887 in 1999 — a 99 percent reduction). "
            "The dramatic reduction in casualties was attributed to Odisha's exemplary "
            "evacuation: 1.2 million persons evacuated in 48 hours to 879 cyclone "
            "shelters and 9,000 other buildings. OSDMA activated 45,000 volunteers. "
            "IMD provided accurate 72-hour track forecast. 55,000 NDRF, SDRF, and "
            "armed forces personnel pre-deployed. Power infrastructure: 200,000 electric "
            "poles damaged, restoration took 15 days. Puri district saw 95 percent "
            "tree cover loss. Economic damage: USD 8.1 billion. Fani became the "
            "international benchmark for effective cyclone evacuation and preparedness. "
            "UN praised India's zero-casualty approach as a global model."
        ),
        "metadata": {
            "source": "historical_record",
            "category": "cyclone",
            "date": "2019-05-03",
            "location": "Odisha",
            "severity": "extremely_severe",
        },
    },
    {
        "id": "hist_amphan_2020_10",
        "text": (
            "Cyclone Amphan (2020). Super Cyclonic Storm Amphan — the strongest cyclone "
            "in the Bay of Bengal since 1999 — made landfall between Digha (West Bengal) "
            "and Hatiya Island (Bangladesh) on May 20, 2020 with sustained winds of "
            "165 km/h. Amphan was the first super cyclone in the Bay of Bengal in 21 "
            "years. Death toll in India: 98 persons (West Bengal: 86, Odisha: 12). "
            "3.3 million persons evacuated from West Bengal and Odisha. Kolkata suffered "
            "severe damage: 5,000 trees uprooted, extensive roof damage, flooding in "
            "southern suburbs. Sundarbans severely impacted — saline water intrusion "
            "damaged 28,000 hectares of agricultural land. Economic loss: USD 13.2 "
            "billion (costliest cyclone in North Indian Ocean history). Power restoration "
            "in Kolkata took 7 days. Mobile networks disrupted for 5 days in Sundarbans. "
            "Key lessons: (1) Evacuation during COVID-19 lockdown required modified "
            "shelter protocols (social distancing, masks, sanitisation), (2) Kolkata's "
            "urban infrastructure vulnerability exposed, (3) Sundarbans mangrove "
            "restoration urgency highlighted."
        ),
        "metadata": {
            "source": "historical_record",
            "category": "cyclone",
            "date": "2020-05-20",
            "location": "West Bengal, Odisha",
            "severity": "super_cyclone",
        },
    },
    {
        "id": "hist_latur_1993_11",
        "text": (
            "1993 Latur Earthquake (Killari Earthquake). On September 30, 1993, a "
            "magnitude 6.2 earthquake struck Latur and Osmanabad districts in "
            "Maharashtra at 03:56 IST (while people were sleeping). Focal depth: "
            "12 km. Death toll: 9,748 persons. 30,000 injured. 52 villages destroyed, "
            "with Killari village being the epicentre where 70 percent of the population "
            "perished. 200,000 houses destroyed — primarily stone masonry with heavy "
            "stone slab roofs. The earthquake occurred in the Stable Continental Region "
            "(SCR), previously considered seismically inactive (then classified as Zone I). "
            "Response: Army deployed within 12 hours. Foreign USAR teams assisted. "
            "Key lessons: (1) India's seismic zonation map revised — Zone I eliminated "
            "entirely, Latur area upgraded to Zone III, (2) Demonstrated catastrophic "
            "vulnerability of traditional stone masonry construction, (3) Led to "
            "strengthening of Disaster Management Act preparation (eventually enacted "
            "2005), (4) Housing reconstruction used earthquake-resistant technology "
            "with cement mortar and through-stones."
        ),
        "metadata": {
            "source": "historical_record",
            "category": "earthquake",
            "date": "1993-09-30",
            "location": "Maharashtra",
            "severity": "magnitude_6.2",
        },
    },
    {
        "id": "hist_bhopal_1984_12",
        "text": (
            "1984 Bhopal Gas Tragedy. On the night of December 2-3, 1984, approximately "
            "40 tonnes of methyl isocyanate (MIC) gas leaked from the Union Carbide "
            "pesticide plant in Bhopal, Madhya Pradesh. Official immediate death toll: "
            "3,787 persons (government of Madhya Pradesh later confirmed 15,000 deaths). "
            "Affected population: 574,000 persons. Over 200,000 exposed to toxic gas. "
            "Long-term health effects: chronic respiratory illness, blindness, "
            "neurological damage, birth defects affecting second generation. The disaster "
            "occurred due to water entering MIC storage tank 610, causing exothermic "
            "reaction. Safety systems (vent gas scrubber, flare tower, refrigeration "
            "unit) were non-operational. No public warning system existed. Hospitals "
            "had no information about the gas or antidotes. Environmental contamination "
            "persists at the site. Key lessons: (1) India enacted Environment Protection "
            "Act 1986, (2) Factories Act amended 1987, (3) NDMA Chemical Disaster "
            "Management Guidelines developed, (4) Mandatory on-site and off-site "
            "emergency plans for MAH units, (5) Public liability insurance made mandatory."
        ),
        "metadata": {
            "source": "historical_record",
            "category": "industrial",
            "date": "1984-12-03",
            "location": "Madhya Pradesh",
            "severity": "catastrophic_industrial",
        },
    },
    {
        "id": "hist_bihar_earthquake_1934_13",
        "text": (
            "1934 Bihar-Nepal Earthquake. On January 15, 1934, a magnitude 8.0 earthquake "
            "struck North Bihar and Nepal, one of the most powerful earthquakes in Indian "
            "subcontinent history. Epicentre near the India-Nepal border. Death toll in "
            "India: approximately 7,253 persons. Major cities affected: Muzaffarpur, "
            "Darbhanga, Monghyr (Munger), and Patna in Bihar. Extensive liquefaction "
            "observed — sand venting and ground subsidence in alluvial Gangetic plains. "
            "Monghyr was the worst-affected Indian city with 90 percent destruction. "
            "The earthquake led to major changes in India's understanding of seismic "
            "risk in the Indo-Gangetic plain. Liquefaction hazard in alluvial soil "
            "deposits was first systematically documented. IS 1893 (Indian Standard "
            "for earthquake-resistant design) development was influenced by this event. "
            "North Bihar remains in Seismic Zone IV-V. Modern risk assessment estimates "
            "that a repeat of this earthquake would affect 50+ million people in the "
            "now densely populated Gangetic plain."
        ),
        "metadata": {
            "source": "historical_record",
            "category": "earthquake",
            "date": "1934-01-15",
            "location": "Bihar",
            "severity": "magnitude_8.0",
        },
    },
    {
        "id": "hist_kerala_2019_landslides_14",
        "text": (
            "2019 Kerala Landslides (Puthumala and Kavalappara). During the 2019 "
            "monsoon, Kerala experienced devastating landslides alongside floods. "
            "On August 8, 2019, massive landslides struck Puthumala in Wayanad "
            "district and Kavalappara in Malappuram district simultaneously. "
            "Puthumala: 17 persons killed, entire hillside collapsed burying a "
            "settlement. Kavalappara: 59 persons killed, a massive debris flow buried "
            "an entire hamlet. Combined with floods, 2019 Kerala disasters killed 121 "
            "persons. Western Ghats geological instability combined with extreme "
            "rainfall (>200 mm in 24 hours) triggered the events. Geological Survey "
            "of India identified 14,000+ landslide-prone locations in Kerala. Key "
            "lessons: (1) Gadgil Committee and Kasturirangan Committee recommendations "
            "on Western Ghats protection gained renewed relevance, (2) Kerala banned "
            "quarrying within 100 metres of landslide-prone areas, (3) NDMA recommended "
            "landslide early warning systems integrating rainfall thresholds with slope "
            "monitoring, (4) Resettlement of populations from landslide-prone zones "
            "became state policy."
        ),
        "metadata": {
            "source": "historical_record",
            "category": "landslide",
            "date": "2019-08-08",
            "location": "Kerala",
            "severity": "severe",
        },
    },
    {
        "id": "hist_heatwave_2015_15",
        "text": (
            "2015 India Heatwave. May-June 2015 saw one of India's deadliest heatwaves. "
            "Temperatures exceeded 47 degrees Celsius across Telangana, Andhra Pradesh, "
            "Odisha, and parts of Rajasthan and Uttar Pradesh. Death toll: 2,500+ "
            "persons (Andhra Pradesh: 1,636, Telangana: 585, Odisha: 241). Many victims "
            "were outdoor workers, elderly, and homeless. Khammam in Telangana recorded "
            "48 degrees Celsius. Roads melted in New Delhi. Power demand surged 20 "
            "percent above generation capacity, causing widespread blackouts. Water "
            "shortages affected 330 million people across 10 states. Key response "
            "deficiency: no Heat Action Plans existed in most states. Following this "
            "disaster: (1) Ahmedabad's Heat Action Plan (India's first, 2013) was "
            "scaled to 17 states, (2) IMD enhanced heatwave forecasting with extended "
            "range prediction, (3) NDMA issued comprehensive heatwave guidelines with "
            "colour-coded alerts, (4) Telangana and Andhra Pradesh mandated staggered "
            "work hours and water provision at public spaces, (5) National Action Plan "
            "on Heat-Related Illness developed."
        ),
        "metadata": {
            "source": "historical_record",
            "category": "heatwave",
            "date": "2015-05-25",
            "location": "Andhra Pradesh, Telangana",
            "severity": "extreme",
        },
    },
    {
        "id": "hist_assam_floods_2022_16",
        "text": (
            "2022 Assam Floods. The 2022 monsoon brought devastating floods to Assam, "
            "affecting 34 of 36 districts in multiple waves from May to August. The "
            "Brahmaputra and its tributaries (Barak, Manas, Subansiri) exceeded danger "
            "levels at multiple stations. Death toll: 197 persons across the season. "
            "9.6 million people affected — the highest in a decade. Kaziranga National "
            "Park submerged with over 150 animals (including one-horned rhinoceros) "
            "killed. 1.5 million displaced to 3,700+ relief camps. 5,000 km of roads "
            "damaged. Agricultural loss across 400,000 hectares. Assam suffers annual "
            "flooding — the Brahmaputra's braided channel system and high sediment "
            "load make structural solutions difficult. Key measures: (1) NDMA deployed "
            "26 NDRF teams, (2) Indian Army conducted Operation Jalprahar, (3) Assam "
            "State Disaster Management Authority activated community-level response, "
            "(4) Renewed focus on flood-resilient construction and raised platforms "
            "for housing, (5) Brahmaputra Board river management plan updated."
        ),
        "metadata": {
            "source": "historical_record",
            "category": "flood",
            "date": "2022-06-15",
            "location": "Assam",
            "severity": "severe_recurring",
        },
    },
    {
        "id": "hist_nepal_border_earthquake_2015_17",
        "text": (
            "2015 Nepal Earthquake — Impact on India. On April 25, 2015, a magnitude "
            "7.8 earthquake struck Nepal with its epicentre in Gorkha. While the "
            "devastation was centred in Nepal, India was significantly affected: "
            "78 deaths in India (Bihar: 56, Uttar Pradesh: 22). Strong shaking felt "
            "across North India — Delhi, Lucknow, Patna, Kolkata. Buildings damaged "
            "in Bihar's border districts. India launched Operation Maitri — the "
            "largest overseas disaster relief operation by India. Indian Air Force "
            "deployed 14 aircraft, including C-17 Globemaster III, for rescue and "
            "relief. NDRF deployed 16 teams (over 700 rescuers) to Nepal. Indian "
            "Army deployed 5,188 personnel, rescued 11,242 persons. India provided "
            "USD 1 billion in reconstruction assistance. Key lessons for India: "
            "(1) Cross-border earthquake preparedness planning needed for Himalayan "
            "states, (2) Bihar's earthquake vulnerability in Seismic Zone IV-V "
            "reconfirmed, (3) NDRF demonstrated capability for overseas deployment, "
            "(4) Hospital surge capacity planning for border districts, (5) Indo-Nepal "
            "disaster management cooperation framework strengthened."
        ),
        "metadata": {
            "source": "historical_record",
            "category": "earthquake",
            "date": "2015-04-25",
            "location": "Bihar, Uttar Pradesh",
            "severity": "magnitude_7.8",
        },
    },
]


# =============================================================================
# Embedding helper (uses Ollama directly, no EmbeddingPipeline dependency)
# =============================================================================


async def _get_embedding(text: str, ollama_host: str) -> list[float] | None:
    """Get embedding from Ollama nomic-embed-text. Returns None on failure."""
    try:
        async with httpx.AsyncClient(timeout=30.0) as client:
            resp = await client.post(
                f"{ollama_host}/api/embeddings",
                json={"model": "nomic-embed-text", "prompt": text},
            )
            resp.raise_for_status()
            return resp.json()["embedding"]
    except Exception as exc:
        logger.warning("Ollama embedding failed: %s", exc)
        return None


async def _get_embeddings_batch(
    texts: list[str], ollama_host: str
) -> list[list[float]] | None:
    """Get embeddings for a batch of texts. Returns None if any fails."""
    embeddings = []
    for text in texts:
        emb = await _get_embedding(text, ollama_host)
        if emb is None:
            return None
        embeddings.append(emb)
    return embeddings


# =============================================================================
# Core setup function
# =============================================================================


async def _seed_collection(
    client: chromadb.ClientAPI,
    collection_name: str,
    seed_data: list[dict[str, Any]],
    ollama_host: str,
) -> int:
    """Seed a single collection if empty. Returns count of documents added."""
    collection = client.get_or_create_collection(
        name=collection_name,
        metadata={"hnsw:space": "cosine"},
    )

    # Skip if collection already has data
    count = collection.count()
    if count > 0:
        logger.info(
            "Collection '%s' already has %d documents, skipping seed",
            collection_name,
            count,
        )
        return 0

    # Prepare batch data
    ids = [item["id"] for item in seed_data]
    texts = [item["text"] for item in seed_data]
    metadatas = [item["metadata"] for item in seed_data]

    # Generate embeddings
    logger.info(
        "Generating embeddings for %d documents in '%s'...",
        len(texts),
        collection_name,
    )
    embeddings = await _get_embeddings_batch(texts, ollama_host)

    if embeddings is None:
        logger.warning(
            "Failed to generate embeddings for '%s' — "
            "Ollama may be unavailable. Storing documents without embeddings.",
            collection_name,
        )
        # Store without embeddings — ChromaDB will use default embedding function
        # or the documents will at least be searchable by metadata
        collection.add(ids=ids, documents=texts, metadatas=metadatas)
        logger.info(
            "Seeded %d documents into '%s' (without custom embeddings)",
            len(ids),
            collection_name,
        )
        return len(ids)

    collection.add(
        ids=ids,
        documents=texts,
        metadatas=metadatas,
        embeddings=embeddings,
    )
    logger.info(
        "Seeded %d documents with embeddings into '%s'",
        len(ids),
        collection_name,
    )
    return len(ids)


async def ensure_rag_ready() -> bool:
    """Check ChromaDB connectivity, create collections, and seed data if empty.

    Returns True if ChromaDB is reachable and collections are ready.
    Returns False (never raises) if ChromaDB or Ollama is unavailable.
    Agents will gracefully degrade when RAG is not available.
    """
    try:
        settings = get_settings()
        chroma_host = settings.CHROMA_HOST
        chroma_port = settings.CHROMA_PORT
        ollama_host = settings.OLLAMA_HOST

        # Step 1: Check ChromaDB connectivity
        logger.info(
            "Checking ChromaDB connectivity at %s:%d...", chroma_host, chroma_port
        )
        client = chromadb.HttpClient(host=chroma_host, port=chroma_port)

        try:
            heartbeat = client.heartbeat()
            logger.info("ChromaDB is reachable (heartbeat: %s)", heartbeat)
        except Exception as exc:
            logger.warning(
                "ChromaDB is not reachable at %s:%d — RAG will be unavailable. "
                "Agents will gracefully degrade. Error: %s",
                chroma_host,
                chroma_port,
                exc,
            )
            return False

        # Step 2: Seed ndma_guidelines collection
        guidelines_count = await _seed_collection(
            client, "ndma_guidelines", NDMA_GUIDELINES, ollama_host
        )

        # Step 3: Seed historical_events collection
        events_count = await _seed_collection(
            client, "historical_events", HISTORICAL_EVENTS, ollama_host
        )

        # Step 4: Ensure other registered collections exist (empty, for future use)
        other_collections = [
            "ndma_sops",
            "state_sdma_reports",
            "ndma_annual",
            "plan_cache",
        ]
        for coll_name in other_collections:
            try:
                client.get_or_create_collection(
                    name=coll_name,
                    metadata={"hnsw:space": "cosine"},
                )
            except Exception as exc:
                logger.warning(
                    "Failed to create collection '%s': %s", coll_name, exc
                )

        logger.info(
            "RAG setup complete. Seeded: ndma_guidelines=%d, historical_events=%d",
            guidelines_count,
            events_count,
        )
        return True

    except Exception as exc:
        logger.warning(
            "RAG setup failed (non-fatal) — agents will gracefully degrade. "
            "Error: %s",
            exc,
        )
        return False
