#!/usr/bin/env python3
"""Build the tracked source-data snapshots for the ryanair mirror.

Produces (idempotent, deterministic, fixed seed):
  source_data_airports.json  - 167 real Ryanair destinations (code, name,
      city, country, coordinates) matching the upstream fare-finder card set.
  source_data_routes.json    - real-route network between the main Ryanair
      bases and their destinations, with per-route great-circle distance,
      block time, and a deterministic daily schedule (real FR flight numbers
      and times for the captured STN<->DUB pair).
  source_data_content.json   - help-centre articles, fee tables, destination
      guides, homepage carousel/partners, promo codes, footer copy captured
      from https://www.ryanair.com/ on 2026-09-24.

The generated JSON files are committed to git; seed_data.py materializes them
into the SQLite seed at image build time (PYTHONHASHSEED=0).
"""
from __future__ import annotations

import json
import math
import pathlib
import random

HERE = pathlib.Path(__file__).resolve().parent
RNG_SEED = 20260924

# ---------------------------------------------------------------------------
# Airport universe: the 167 destinations that carry a real upstream fare-finder
# card image (captured 2026-09-24). Names come from the upstream cards; city /
# country / coordinates are the public airport facts.
# code: (display_name, city, country, lat, lon, is_base)
AIRPORTS = {
    'AAR': ('Aarhus', 'Aarhus', 'Denmark', 56.30, 10.62, False),
    'ACE': ('Lanzarote', 'Lanzarote', 'Spain', 28.95, -13.61, True),
    'AGA': ('Agadir', 'Agadir', 'Morocco', 30.38, -9.41, True),
    'AGP': ('Malaga', 'Malaga', 'Spain', 36.68, -4.50, True),
    'AHO': ('Alghero', 'Alghero', 'Italy', 40.63, 8.29, False),
    'ALC': ('Alicante', 'Alicante', 'Spain', 38.28, -0.56, True),
    'AMS': ('Amsterdam', 'Amsterdam', 'Netherlands', 52.31, 4.76, False),
    'AOI': ('Ancona', 'Ancona', 'Italy', 43.62, 13.37, False),
    'ARN': ('Stockholm Arlanda', 'Stockholm', 'Sweden', 59.65, 17.92, False),
    'ATH': ('Athens', 'Athens', 'Greece', 37.94, 23.95, True),
    'BCN': ('Barcelona', 'Barcelona', 'Spain', 41.30, 2.08, True),
    'BDS': ('Brindisi', 'Brindisi', 'Italy', 40.66, 17.95, False),
    'BER': ('Berlin Brandenburg', 'Berlin', 'Germany', 52.37, 13.50, True),
    'BFS': ('Belfast International', 'Belfast', 'United Kingdom', 54.88, -6.22, True),
    'BGY': ('Milan Bergamo', 'Bergamo', 'Italy', 45.67, 9.70, True),
    'BHX': ('Birmingham', 'Birmingham', 'United Kingdom', 52.45, -1.75, True),
    'BIQ': ('Biarritz', 'Biarritz', 'France', 43.48, -1.53, False),
    'BJV': ('Bodrum', 'Bodrum', 'Turkey', 37.25, 27.66, True),
    'BLQ': ('Bologna', 'Bologna', 'Italy', 44.54, 11.29, True),
    'BRE': ('Bremen', 'Bremen', 'Germany', 53.05, 8.79, True),
    'BRI': ('Bari', 'Bari', 'Italy', 41.14, 16.76, True),
    'BRQ': ('Brno', 'Brno', 'Czech Republic', 49.15, 16.69, False),
    'BRS': ('Bristol', 'Bristol', 'United Kingdom', 51.38, -2.72, True),
    'BRU': ('Brussels', 'Brussels', 'Belgium', 50.90, 4.48, False),
    'BSL': ('Basel', 'Basel', 'Switzerland', 47.59, 7.53, False),
    'BTS': ('Bratislava', 'Bratislava', 'Slovakia', 48.17, 17.21, True),
    'BUD': ('Budapest', 'Budapest', 'Hungary', 47.44, 19.26, True),
    'BVA': ('Paris Beauvais', 'Paris', 'France', 49.45, 2.11, True),
    'BVE': ('Brive', 'Brive', 'France', 45.15, 1.48, False),
    'BOD': ('Bordeaux', 'Bordeaux', 'France', 44.83, -0.70, False),
    'BZG': ('Bydgoszcz', 'Bydgoszcz', 'Poland', 53.10, 18.00, False),
    'CAG': ('Cagliari', 'Cagliari', 'Italy', 39.25, 9.05, True),
    'CCF': ('Carcassonne', 'Carcassonne', 'France', 43.22, 2.33, False),
    'CDT': ('Castellon', 'Castellon', 'Spain', 39.89, -0.06, False),
    'CFU': ('Corfu', 'Corfu', 'Greece', 39.60, 19.91, True),
    'CGN': ('Cologne', 'Cologne', 'Germany', 50.87, 7.14, True),
    'CHQ': ('Chania', 'Chania', 'Greece', 35.53, 24.15, True),
    'CIA': ('Rome Ciampino', 'Rome', 'Italy', 41.80, 12.59, True),
    'CLJ': ('Cluj', 'Cluj-Napoca', 'Romania', 46.78, 23.69, True),
    'CPH': ('Copenhagen', 'Copenhagen', 'Denmark', 55.62, 12.66, True),
    'CRL': ('Brussels Charleroi', 'Brussels', 'Belgium', 50.46, 4.45, True),
    'CTA': ('Catania', 'Catania', 'Italy', 37.47, 15.07, True),
    'CWL': ('Cardiff', 'Cardiff', 'United Kingdom', 51.40, -3.34, True),
    'DBV': ('Dubrovnik', 'Dubrovnik', 'Croatia', 42.56, 18.27, False),
    'DLM': ('Dalaman', 'Dalaman', 'Turkey', 36.71, 28.79, True),
    'DUB': ('Dublin', 'Dublin', 'Ireland', 53.43, -6.27, True),
    'EDI': ('Edinburgh', 'Edinburgh', 'United Kingdom', 55.95, -3.36, True),
    'EFL': ('Kefalonia', 'Kefalonia', 'Greece', 38.12, 20.50, False),
    'EGC': ('Bergerac', 'Bergerac', 'France', 44.82, 0.52, False),
    'EIN': ('Eindhoven', 'Eindhoven', 'Netherlands', 51.45, 5.37, True),
    'EMA': ('East Midlands', 'East Midlands', 'United Kingdom', 52.83, -1.33, True),
    'ESU': ('Essaouira', 'Essaouira', 'Morocco', 31.40, -9.68, False),
    'FAO': ('Faro', 'Faro', 'Portugal', 37.01, -7.97, True),
    'FCO': ('Rome Fiumicino', 'Rome', 'Italy', 41.80, 12.25, True),
    'FEZ': ('Fez', 'Fez', 'Morocco', 33.77, -4.98, True),
    'FKB': ('Karlsruhe / Baden-Baden', 'Karlsruhe', 'Germany', 48.78, 8.08, True),
    'FMM': ('Memmingen', 'Memmingen', 'Germany', 47.99, 10.24, True),
    'FMO': ('Munster', 'Munster', 'Germany', 52.13, 7.68, False),
    'FNI': ('Nimes', 'Nimes', 'France', 43.86, 4.41, True),
    'FUE': ('Fuerteventura', 'Fuerteventura', 'Spain', 28.45, -13.86, True),
    'GDN': ('Gdansk', 'Gdansk', 'Poland', 54.38, 18.47, True),
    'GLA': ('Glasgow', 'Glasgow', 'United Kingdom', 55.87, -4.44, True),
    'GOA': ('Genoa', 'Genoa', 'Italy', 44.41, 8.85, False),
    'GOT': ('Goteborg Landvetter', 'Gothenburg', 'Sweden', 57.66, 12.29, True),
    'GRO': ('Barcelona Girona', 'Girona', 'Spain', 41.90, 2.76, True),
    'HAM': ('Hamburg', 'Hamburg', 'Germany', 53.63, 9.99, True),
    'HEL': ('Helsinki', 'Helsinki', 'Finland', 60.32, 24.96, True),
    'HHN': ('Frankfurt Hahn', 'Frankfurt', 'Germany', 49.95, 7.26, True),
    'IBZ': ('Ibiza', 'Ibiza', 'Spain', 38.87, 1.37, True),
    'JTR': ('Santorini', 'Santorini', 'Greece', 36.40, 25.48, False),
    'KGS': ('Kos', 'Kos', 'Greece', 36.79, 27.09, True),
    'KIR': ('Kerry', 'Kerry', 'Ireland', 52.18, -9.88, False),
    'KLU': ('Klagenfurt', 'Klagenfurt', 'Austria', 46.64, 14.33, False),
    'KRK': ('Krakow', 'Krakow', 'Poland', 50.08, 19.79, True),
    'KSC': ('Kosice', 'Kosice', 'Slovakia', 48.63, 21.24, False),
    'KTW': ('Katowice', 'Katowice', 'Poland', 50.47, 19.08, True),
    'KUN': ('Kaunas', 'Kaunas', 'Lithuania', 54.96, 24.09, True),
    'LBA': ('Leeds Bradford', 'Leeds', 'United Kingdom', 53.87, -1.66, True),
    'LBC': ('Lubeck', 'Lubeck', 'Germany', 53.81, 10.72, False),
    'LCJ': ('Lodz', 'Lodz', 'Poland', 51.72, 19.40, False),
    'LDE': ('Lourdes-Pyrenees', 'Lourdes', 'France', 43.18, 0.00, False),
    'LEI': ('Almeria', 'Almeria', 'Spain', 36.84, -2.36, True),
    'LGW': ('London Gatwick', 'London', 'United Kingdom', 51.15, -0.19, True),
    'STN': ('London Stansted', 'London', 'United Kingdom', 51.89, 0.24, True),
    'LTN': ('London Luton', 'London', 'United Kingdom', 51.87, -0.37, True),
    'LIL': ('Lille', 'Lille', 'France', 50.56, 3.09, False),
    'LIG': ('Limoges', 'Limoges', 'France', 45.86, 1.18, False),
    'LIS': ('Lisbon', 'Lisbon', 'Portugal', 38.77, -9.13, True),
    'LNZ': ('Linz', 'Linz', 'Austria', 48.23, 14.19, False),
    'LPA': ('Gran Canaria', 'Gran Canaria', 'Spain', 27.93, -15.39, True),
    'LPL': ('Liverpool', 'Liverpool', 'United Kingdom', 53.33, -2.85, True),
    'LRH': ('La Rochelle', 'La Rochelle', 'France', 46.18, -1.20, False),
    'LUX': ('Luxembourg', 'Luxembourg', 'Luxembourg', 49.63, 6.21, False),
    'LUZ': ('Lublin', 'Lublin', 'Poland', 51.24, 22.72, False),
    'MAD': ('Madrid', 'Madrid', 'Spain', 40.47, -3.56, True),
    'MAH': ('Menorca', 'Menorca', 'Spain', 39.86, 4.22, True),
    'MAN': ('Manchester', 'Manchester', 'United Kingdom', 53.35, -2.28, True),
    'MLA': ('Malta', 'Malta', 'Malta', 35.86, 14.48, True),
    'MMX': ('Malmo', 'Malmo', 'Sweden', 55.54, 13.37, True),
    'MRS': ('Marseille', 'Marseille', 'France', 43.44, 5.22, True),
    'MXP': ('Milan Malpensa', 'Milan', 'Italy', 45.63, 8.72, True),
    'NAP': ('Naples', 'Naples', 'Italy', 40.88, 14.29, True),
    'NCE': ('Nice', 'Nice', 'France', 43.66, 7.22, False),
    'NCL': ('Newcastle', 'Newcastle', 'United Kingdom', 55.04, -1.69, True),
    'NOC': ('Knock', 'Knock', 'Ireland', 53.91, -8.82, False),
    'NQY': ('Newquay Cornwall', 'Newquay', 'United Kingdom', 50.44, -4.99, False),
    'NTE': ('Nantes', 'Nantes', 'France', 47.15, -1.61, True),
    'NUE': ('Nuremberg', 'Nuremberg', 'Germany', 49.50, 11.08, True),
    'OLB': ('Olbia', 'Olbia', 'Italy', 40.90, 9.52, True),
    'OPO': ('Porto', 'Porto', 'Portugal', 41.24, -8.68, True),
    'ORK': ('Cork', 'Cork', 'Ireland', 51.84, -8.49, True),
    'OSL': ('Oslo', 'Oslo', 'Norway', 60.19, 11.10, False),
    'OSR': ('Ostrava', 'Ostrava', 'Czech Republic', 49.70, 18.11, False),
    'OTP': ('Bucharest Otopeni', 'Bucharest', 'Romania', 44.57, 26.10, True),
    'PDV': ('Plovdiv', 'Plovdiv', 'Bulgaria', 42.07, 24.85, False),
    'PEG': ('Perugia', 'Perugia', 'Italy', 43.10, 12.51, False),
    'PFO': ('Paphos', 'Paphos', 'Cyprus', 34.75, 32.49, True),
    'PGF': ('Perpignan', 'Perpignan', 'France', 42.74, 2.87, False),
    'PIS': ('Poitiers', 'Poitiers', 'France', 46.59, 0.31, False),
    'PLQ': ('Palanga', 'Palanga', 'Lithuania', 55.97, 21.09, False),
    'PMF': ('Parma', 'Parma', 'Italy', 44.82, 10.29, False),
    'PMI': ('Palma de Mallorca', 'Palma', 'Spain', 39.55, 2.74, True),
    'PMO': ('Palermo', 'Palermo', 'Italy', 38.18, 13.09, True),
    'POZ': ('Poznan', 'Poznan', 'Poland', 52.72, 16.83, True),
    'PRG': ('Prague', 'Prague', 'Czech Republic', 50.10, 14.26, True),
    'PSA': ('Pisa', 'Pisa', 'Italy', 43.68, 10.39, True),
    'PSR': ('Pescara', 'Pescara', 'Italy', 42.43, 14.18, False),
    'PUY': ('Pula', 'Pula', 'Croatia', 44.90, 13.92, False),
    'QSR': ('Salerno Costa d\'Amalfi', 'Salerno', 'Italy', 40.65, 15.05, False),
    'RAK': ('Marrakesh', 'Marrakesh', 'Morocco', 31.61, -8.04, True),
    'RBA': ('Rabat', 'Rabat', 'Morocco', 34.05, -6.75, True),
    'REG': ('Reggio Calabria', 'Reggio Calabria', 'Italy', 38.07, 15.65, False),
    'REU': ('Barcelona Reus', 'Reus', 'Spain', 41.15, 1.17, True),
    'RHO': ('Rhodes', 'Rhodes', 'Greece', 36.41, 28.09, True),
    'RIX': ('Riga', 'Riga', 'Latvia', 56.92, 23.97, True),
    'RMI': ('Rimini', 'Rimini', 'Italy', 43.99, 12.62, True),
    'RMU': ('Murcia International', 'Murcia', 'Spain', 37.80, -1.13, True),
    'RVN': ('Lapland Rovaniemi', 'Rovaniemi', 'Finland', 66.56, 25.83, True),
    'RZE': ('Rzeszow', 'Rzeszow', 'Poland', 50.11, 22.02, False),
    'SCQ': ('Santiago', 'Santiago de Compostela', 'Spain', 42.90, -8.42, False),
    'SDR': ('Santander', 'Santander', 'Spain', 43.42, -3.82, False),
    'SKG': ('Thessaloniki', 'Thessaloniki', 'Greece', 40.52, 22.97, True),
    'SNN': ('Shannon', 'Shannon', 'Ireland', 52.70, -8.92, True),
    'SOF': ('Sofia', 'Sofia', 'Bulgaria', 42.70, 23.41, True),
    'SPU': ('Split', 'Split', 'Croatia', 43.54, 16.31, True),
    'SUF': ('Lamezia', 'Lamezia Terme', 'Italy', 38.91, 16.25, False),
    'SVQ': ('Seville', 'Seville', 'Spain', 37.42, -5.89, True),
    'SZG': ('Salzburg', 'Salzburg', 'Austria', 47.79, 13.00, True),
    'SZY': ('Olsztyn - Mazury', 'Olsztyn', 'Poland', 53.50, 20.94, False),
    'SZZ': ('Szczecin', 'Szczecin', 'Poland', 53.58, 14.90, False),
    'TFS': ('Tenerife South', 'Tenerife', 'Spain', 28.04, -16.57, True),
    'TGD': ('Podgorica', 'Podgorica', 'Montenegro', 42.36, 19.25, False),
    'TIA': ('Tirana', 'Tirana', 'Albania', 41.41, 19.72, True),
    'TLL': ('Tallinn', 'Tallinn', 'Estonia', 59.41, 24.83, True),
    'TLS': ('Toulouse', 'Toulouse', 'France', 43.63, 1.37, True),
    'TNG': ('Tangier', 'Tangier', 'Morocco', 35.89, -5.67, True),
    'TRF': ('Oslo Torp', 'Oslo', 'Norway', 59.18, 10.26, True),
    'TRN': ('Turin', 'Turin', 'Italy', 45.20, 7.65, True),
    'TRS': ('Trieste', 'Trieste', 'Italy', 45.83, 13.47, False),
    'TUF': ('Tours Loire Valley', 'Tours', 'France', 47.43, 0.73, False),
    'VCE': ('Venice M.Polo', 'Venice', 'Italy', 45.51, 12.35, False),
    'VIE': ('Vienna', 'Vienna', 'Austria', 48.11, 16.57, True),
    'VLC': ('Valencia', 'Valencia', 'Spain', 39.49, -0.48, True),
    'VNO': ('Vilnius', 'Vilnius', 'Lithuania', 54.63, 25.29, True),
    'VRN': ('Verona', 'Verona', 'Italy', 45.40, 10.89, True),
    'WMI': ('Warsaw Modlin', 'Warsaw', 'Poland', 52.45, 20.68, True),
    'WRO': ('Wroclaw', 'Wroclaw', 'Poland', 51.10, 16.89, True),
    'ZAD': ('Zadar', 'Zadar', 'Croatia', 44.11, 15.35, True),
    'ZAG': ('Zagreb', 'Zagreb', 'Croatia', 45.74, 16.07, True),
    'XRY': ('Jerez', 'Jerez', 'Spain', 36.76, -6.06, False),
    'ZAZ': ('Zaragoza', 'Zaragoza', 'Spain', 41.67, -1.04, False),
    'ZTH': ('Zakynthos', 'Zakynthos', 'Greece', 37.75, 20.76, True),
}

# ---------------------------------------------------------------------------
# Route network: destination lists for the main bases, restricted to the
# airport universe above. Real Ryanair route topology (public schedules),
# trimmed to a coherent subset.
BASES = {
    'STN': ['DUB', 'AGP', 'ALC', 'PMI', 'IBZ', 'MAH', 'ACE', 'LPA', 'TFS', 'FUE',
            'BCN', 'GRO', 'REU', 'VLC', 'MAD', 'SVQ', 'RMU', 'LEI', 'BVA', 'NTE',
            'BOD', 'XRY', 'LIL', 'TLS', 'MRS', 'CRL', 'BGY', 'CIA', 'FCO', 'PSA',
            'TLS', 'MRS', 'CRL', 'BGY', 'CIA', 'FCO', 'PSA', 'VRN', 'BLQ', 'PMO',
            'CTA', 'CAG', 'BRI', 'NAP', 'TRN', 'AMS', 'EIN', 'CRL', 'HHN', 'FMM',
            'CGN', 'BER', 'HAM', 'NUE', 'KRK', 'GDN', 'WRO', 'POZ', 'KTW', 'WMI',
            'PRG', 'BUD', 'VIE', 'BTS', 'OTP', 'CLJ', 'SOF', 'ATH', 'SKG', 'MLA',
            'FAO', 'LIS', 'OPO', 'AGA', 'RAK', 'FEZ', 'TNG', 'RBA', 'CPH', 'ARN',
            'MMX', 'GOT', 'TRF', 'OSL', 'HEL', 'RIX', 'VNO', 'TLL', 'KUN', 'PLQ',
            'BFS', 'EDI', 'GLA', 'PIK', 'ORK', 'SNN', 'KIR', 'NOC', 'AAR', 'BJV',
            'DLM', 'PFO', 'ZTH', 'CHQ', 'CFU', 'KGS', 'RHO', 'JTR', 'SPU', 'DBV',
            'ZAD', 'PUY', 'TIA', 'TGD', 'RVN', 'SZG', 'VCE', 'AOI', 'PSR', 'SUF',
            'REG', 'QSR', 'BDS', 'OLB', 'CTA', 'BUD', 'BER', 'BTS', 'BLQ', 'PMF',
            'PEG', 'EGC', 'LIG', 'PIS', 'LRH', 'BVE', 'CCF', 'NCE', 'PGF', 'BIQ',
            'TUF', 'LDE', 'NUE', 'FMO', 'FKB', 'LBC', 'BRQ', 'OSR', 'BZG', 'LCJ',
            'LUZ', 'RZE', 'SZY', 'SZZ', 'PDV', 'KSC', 'KLU', 'LNZ', 'GOA', 'MXP'],
    'DUB': ['STN', 'LGW', 'MAN', 'BHX', 'BRS', 'EDI', 'GLA', 'LPL', 'EMA', 'LBA',
            'NCL', 'CWL', 'BFS', 'NQY', 'ORK', 'SNN', 'KIR', 'NOC', 'AGP', 'ALC',
            'PMI', 'IBZ', 'MAH', 'ACE', 'LPA', 'TFS', 'FUE', 'BCN', 'GRO', 'VLC',
            'MAD', 'SVQ', 'BVA', 'NTE', 'TLS', 'MRS', 'CRL', 'BGY', 'CIA', 'PSA',
            'VRN', 'PMO', 'CTA', 'CAG', 'BRI', 'NAP', 'AMS', 'EIN', 'FMM', 'CGN',
            'HHN', 'KRK', 'GDN', 'WRO', 'POZ', 'KTW', 'PRG', 'BUD', 'VIE', 'BTS',
            'OTP', 'CLJ', 'SOF', 'ATH', 'SKG', 'MLA', 'FAO', 'LIS', 'OPO', 'AGA',
            'RAK', 'FEZ', 'TNG', 'RBA', 'CPH', 'GOT', 'TRF', 'HEL', 'RIX', 'VNO',
            'TLL', 'KUN', 'BJV', 'DLM', 'PFO', 'ZTH', 'CHQ', 'CFU', 'KGS', 'RHO',
            'JTR', 'SPU', 'DBV', 'ZAD', 'TIA', 'TGD', 'RVN', 'SZG', 'VCE', 'AOI',
            'PSR', 'SUF', 'REG', 'BDS', 'OLB', 'MXP', 'TRN', 'BLQ', 'LDN', 'LUX'],
    'LGW': ['DUB', 'AGP', 'ALC', 'PMI', 'IBZ', 'MAH', 'ACE', 'LPA', 'TFS', 'FUE',
            'BCN', 'VLC', 'MAD', 'SVQ', 'RMU', 'BVA', 'NTE', 'BOD', 'LIL', 'TLS',
            'BGY', 'CIA', 'FCO', 'PSA', 'VRN', 'PMO', 'CTA', 'CAG', 'BRI', 'NAP',
            'TRN', 'AMS', 'EIN', 'FMM', 'CGN', 'HHN', 'KRK', 'GDN', 'WRO', 'WMI',
            'PRG', 'BUD', 'VIE', 'BTS', 'OTP', 'SOF', 'ATH', 'SKG', 'MLA', 'FAO',
            'LIS', 'OPO', 'AGA', 'RAK', 'FEZ', 'TNG', 'CPH', 'ARN', 'TRF', 'HEL',
            'RIX', 'VNO', 'TLL', 'KUN', 'BFS', 'EDI', 'GLA', 'ORK', 'BJV', 'DLM',
            'PFO', 'ZTH', 'CHQ', 'CFU', 'KGS', 'RHO', 'JTR', 'SPU', 'DBV', 'ZAD',
            'PUY', 'TIA', 'TGD', 'SZG', 'VCE', 'PSR', 'SUF', 'OLB', 'MXP', 'BLQ'],
    'LTN': ['DUB', 'AGP', 'ALC', 'PMI', 'IBZ', 'MAH', 'ACE', 'LPA', 'TFS', 'FUE',
            'BCN', 'GRO', 'REU', 'VLC', 'MAD', 'SVQ', 'RMU', 'LEI', 'BVA', 'NTE',
            'BOD', 'TLS', 'MRS', 'CRL', 'BGY', 'CIA', 'FCO', 'PSA', 'VRN', 'BLQ',
            'PMO', 'CTA', 'CAG', 'BRI', 'NAP', 'TRN', 'MXP', 'AMS', 'EIN', 'FKB',
            'FMM', 'HHN', 'CGN', 'BER', 'NUE', 'KRK', 'GDN', 'WRO', 'POZ', 'KTW',
            'WMI', 'PRG', 'BUD', 'VIE', 'BTS', 'OTP', 'SOF', 'ATH', 'SKG', 'MLA',
            'FAO', 'LIS', 'OPO', 'AGA', 'RAK', 'FEZ', 'TNG', 'RBA', 'CPH', 'ARN',
            'TRF', 'HEL', 'RIX', 'VNO', 'TLL', 'KUN', 'BFS', 'EDI', 'GLA', 'ORK',
            'SNN', 'KIR', 'NOC', 'STN', 'BJV', 'DLM', 'PFO', 'ZTH', 'CHQ', 'CFU',
            'KGS', 'RHO', 'SPU', 'DBV', 'ZAD', 'PUY', 'TIA', 'TGD', 'VCE', 'PSR',
            'SUF', 'OLB', 'BLQ', 'AAR', 'LIL'],
    'MAN': ['DUB', 'AGP', 'ALC', 'PMI', 'IBZ', 'MAH', 'ACE', 'LPA', 'TFS', 'FUE',
            'BCN', 'GRO', 'REU', 'VLC', 'MAD', 'SVQ', 'BVA', 'NTE', 'BOD', 'TLS',
            'CRL', 'BGY', 'CIA', 'PSA', 'VRN', 'PMO', 'CTA', 'CAG', 'BRI', 'NAP',
            'TRN', 'AMS', 'EIN', 'FMM', 'CGN', 'HHN', 'BER', 'NUE', 'KRK', 'GDN',
            'WRO', 'POZ', 'KTW', 'WMI', 'PRG', 'BUD', 'VIE', 'BTS', 'OTP', 'CLJ',
            'SOF', 'ATH', 'SKG', 'MLA', 'FAO', 'LIS', 'OPO', 'AGA', 'RAK', 'FEZ',
            'TNG', 'CPH', 'ARN', 'GOT', 'TRF', 'HEL', 'RIX', 'VNO', 'TLL', 'KUN',
            'BFS', 'EDI', 'GLA', 'ORK', 'SNN', 'BJV', 'DLM', 'PFO', 'ZTH', 'CHQ',
            'CFU', 'KGS', 'RHO', 'SPU', 'DBV', 'ZAD', 'PUY', 'TIA', 'TGD', 'RVN',
            'SZG', 'VCE', 'AOI', 'PSR', 'SUF', 'OLB', 'MXP', 'BLQ', 'TRN'],
    'BHX': ['DUB', 'AGP', 'ALC', 'PMI', 'IBZ', 'MAH', 'ACE', 'LPA', 'TFS', 'FUE',
            'BCN', 'GRO', 'VLC', 'MAD', 'SVQ', 'BVA', 'NTE', 'TLS', 'MRS', 'CRL',
            'BGY', 'CIA', 'PSA', 'VRN', 'PMO', 'CTA', 'CAG', 'BRI', 'NAP', 'TRN',
            'AMS', 'EIN', 'FMM', 'CGN', 'HHN', 'BER', 'NUE', 'KRK', 'GDN', 'WRO',
            'POZ', 'KTW', 'WMI', 'PRG', 'BUD', 'VIE', 'BTS', 'OTP', 'SOF', 'ATH',
            'SKG', 'MLA', 'FAO', 'LIS', 'OPO', 'AGA', 'RAK', 'FEZ', 'TNG', 'CPH',
            'TRF', 'HEL', 'RIX', 'VNO', 'TLL', 'KUN', 'BFS', 'EDI', 'GLA', 'ORK',
            'SNN', 'BJV', 'DLM', 'PFO', 'ZTH', 'CHQ', 'CFU', 'KGS', 'RHO', 'SPU',
            'DBV', 'ZAD', 'PUY', 'TIA', 'TGD', 'RVN', 'SZG', 'VCE', 'PSR', 'OLB',
            'MXP', 'BLQ', 'KRK'],
    'BRS': ['DUB', 'AGP', 'ALC', 'PMI', 'IBZ', 'MAH', 'ACE', 'LPA', 'TFS', 'FUE',
            'BCN', 'GRO', 'REU', 'VLC', 'MAD', 'SVQ', 'RMU', 'BVA', 'NTE', 'TLS',
            'MRS', 'CRL', 'BGY', 'CIA', 'PSA', 'VRN', 'PMO', 'CTA', 'CAG', 'BRI',
            'NAP', 'TRN', 'AMS', 'EIN', 'FMM', 'CGN', 'HHN', 'BER', 'NUE', 'KRK',
            'GDN', 'WRO', 'POZ', 'KTW', 'WMI', 'PRG', 'BUD', 'VIE', 'BTS', 'OTP',
            'SOF', 'ATH', 'SKG', 'MLA', 'FAO', 'LIS', 'OPO', 'AGA', 'RAK', 'FEZ',
            'TNG', 'CPH', 'TRF', 'HEL', 'RIX', 'VNO', 'TLL', 'KUN', 'BFS', 'EDI',
            'GLA', 'ORK', 'SNN', 'BJV', 'DLM', 'PFO', 'ZTH', 'CHQ', 'CFU', 'KGS',
            'RHO', 'SPU', 'DBV', 'ZAD', 'PUY', 'TIA', 'TGD', 'RVN', 'SZG', 'VCE',
            'PSR', 'SUF', 'OLB', 'MXP', 'BLQ'],
    'EDI': ['DUB', 'AGP', 'ALC', 'PMI', 'IBZ', 'MAH', 'ACE', 'LPA', 'TFS', 'FUE',
            'BCN', 'GRO', 'VLC', 'MAD', 'SVQ', 'BVA', 'NTE', 'TLS', 'MRS', 'CRL',
            'BGY', 'CIA', 'PSA', 'VRN', 'PMO', 'CTA', 'CAG', 'BRI', 'NAP', 'TRN',
            'AMS', 'EIN', 'FMM', 'CGN', 'HHN', 'BER', 'KRK', 'GDN', 'WRO', 'POZ',
            'KTW', 'WMI', 'PRG', 'BUD', 'VIE', 'BTS', 'OTP', 'SOF', 'ATH', 'SKG',
            'MLA', 'FAO', 'LIS', 'OPO', 'AGA', 'RAK', 'TNG', 'CPH', 'ARN', 'GOT',
            'TRF', 'HEL', 'RIX', 'VNO', 'TLL', 'KUN', 'BFS', 'GLA', 'ORK', 'SNN',
            'BJV', 'DLM', 'PFO', 'ZTH', 'CHQ', 'CFU', 'KGS', 'RHO', 'SPU', 'DBV',
            'ZAD', 'PUY', 'TIA', 'TGD', 'RVN', 'SZG', 'VCE', 'PSR', 'OLB', 'MXP',
            'BLQ'],
    'GLA': ['DUB', 'AGP', 'ALC', 'PMI', 'IBZ', 'MAH', 'ACE', 'LPA', 'TFS', 'FUE',
            'BCN', 'GRO', 'VLC', 'MAD', 'SVQ', 'BVA', 'NTE', 'TLS', 'MRS', 'CRL',
            'BGY', 'CIA', 'PSA', 'VRN', 'PMO', 'CTA', 'CAG', 'BRI', 'NAP', 'TRN',
            'AMS', 'EIN', 'FMM', 'CGN', 'HHN', 'BER', 'KRK', 'GDN', 'WRO', 'POZ',
            'KTW', 'WMI', 'PRG', 'BUD', 'VIE', 'BTS', 'OTP', 'SOF', 'ATH', 'SKG',
            'MLA', 'FAO', 'LIS', 'OPO', 'AGA', 'RAK', 'TNG', 'CPH', 'ARN', 'GOT',
            'TRF', 'HEL', 'RIX', 'VNO', 'TLL', 'KUN', 'BFS', 'EDI', 'ORK', 'SNN',
            'BJV', 'DLM', 'PFO', 'ZTH', 'CHQ', 'CFU', 'KGS', 'RHO', 'SPU', 'DBV',
            'ZAD', 'PUY', 'TIA', 'TGD', 'RVN', 'SZG', 'VCE', 'PSR', 'OLB', 'MXP',
            'BLQ'],
    'LPL': ['DUB', 'AGP', 'ALC', 'PMI', 'IBZ', 'MAH', 'ACE', 'LPA', 'TFS', 'FUE',
            'BCN', 'GRO', 'VLC', 'MAD', 'SVQ', 'BVA', 'NTE', 'TLS', 'MRS', 'CRL',
            'BGY', 'CIA', 'PSA', 'VRN', 'PMO', 'CTA', 'CAG', 'BRI', 'NAP', 'TRN',
            'AMS', 'EIN', 'FMM', 'CGN', 'HHN', 'BER', 'NUE', 'KRK', 'GDN', 'WRO',
            'POZ', 'KTW', 'WMI', 'PRG', 'BUD', 'VIE', 'BTS', 'OTP', 'SOF', 'ATH',
            'SKG', 'MLA', 'FAO', 'LIS', 'OPO', 'AGA', 'RAK', 'FEZ', 'TNG', 'CPH',
            'TRF', 'HEL', 'RIX', 'VNO', 'TLL', 'KUN', 'BFS', 'EDI', 'GLA', 'ORK',
            'BJV', 'DLM', 'PFO', 'ZTH', 'CHQ', 'CFU', 'KGS', 'RHO', 'SPU', 'DBV',
            'ZAD', 'TIA', 'TGD', 'RVN', 'SZG', 'VCE', 'PSR', 'OLB', 'MXP', 'BLQ'],
    'EMA': ['DUB', 'AGP', 'ALC', 'PMI', 'IBZ', 'MAH', 'ACE', 'LPA', 'TFS', 'FUE',
            'BCN', 'GRO', 'VLC', 'MAD', 'SVQ', 'BVA', 'NTE', 'TLS', 'MRS', 'CRL',
            'BGY', 'CIA', 'PSA', 'VRN', 'PMO', 'CTA', 'CAG', 'BRI', 'NAP', 'TRN',
            'AMS', 'EIN', 'FMM', 'CGN', 'HHN', 'BER', 'NUE', 'KRK', 'GDN', 'WRO',
            'POZ', 'KTW', 'WMI', 'PRG', 'BUD', 'VIE', 'BTS', 'OTP', 'SOF', 'ATH',
            'MLA', 'FAO', 'LIS', 'OPO', 'AGA', 'RAK', 'FEZ', 'TNG', 'CPH', 'TRF',
            'HEL', 'RIX', 'VNO', 'TLL', 'KUN', 'BFS', 'EDI', 'GLA', 'ORK', 'BJV',
            'DLM', 'PFO', 'ZTH', 'CHQ', 'CFU', 'KGS', 'RHO', 'SPU', 'DBV', 'ZAD',
            'TIA', 'TGD', 'RVN', 'SZG', 'VCE', 'PSR', 'OLB', 'MXP', 'BLQ'],
    'BFS': ['DUB', 'STN', 'LGW', 'MAN', 'BHX', 'BRS', 'EDI', 'GLA', 'LPL', 'EMA',
            'LBA', 'NCL', 'CWL', 'ORK', 'SNN', 'AGP', 'ALC', 'PMI', 'IBZ', 'MAH',
            'ACE', 'LPA', 'TFS', 'FUE', 'BCN', 'GRO', 'VLC', 'MAD', 'SVQ', 'BVA',
            'NTE', 'TLS', 'MRS', 'CRL', 'BGY', 'CIA', 'PSA', 'VRN', 'PMO', 'CTA',
            'CAG', 'BRI', 'NAP', 'TRN', 'AMS', 'EIN', 'FMM', 'CGN', 'HHN', 'BER',
            'KRK', 'GDN', 'WRO', 'POZ', 'KTW', 'WMI', 'PRG', 'BUD', 'VIE', 'BTS',
            'OTP', 'SOF', 'ATH', 'SKG', 'MLA', 'FAO', 'LIS', 'OPO', 'AGA', 'RAK',
            'FEZ', 'TNG', 'CPH', 'TRF', 'HEL', 'RIX', 'VNO', 'TLL', 'KUN', 'BJV',
            'DLM', 'PFO', 'ZTH', 'CHQ', 'CFU', 'KGS', 'RHO', 'SPU', 'DBV', 'ZAD',
            'PUY', 'TIA', 'TGD', 'RVN', 'SZG', 'VCE', 'PSR', 'OLB', 'MXP', 'BLQ'],
    'CWL': ['DUB', 'AGP', 'ALC', 'PMI', 'IBZ', 'MAH', 'ACE', 'LPA', 'TFS', 'FUE',
            'BCN', 'GRO', 'VLC', 'MAD', 'SVQ', 'BVA', 'NTE', 'TLS', 'MRS', 'CRL',
            'BGY', 'CIA', 'PSA', 'VRN', 'PMO', 'CTA', 'CAG', 'BRI', 'NAP', 'TRN',
            'FMM', 'CGN', 'HHN', 'BER', 'KRK', 'GDN', 'WRO', 'POZ', 'KTW', 'WMI',
            'PRG', 'BUD', 'VIE', 'BTS', 'OTP', 'SOF', 'ATH', 'MLA', 'FAO', 'LIS',
            'OPO', 'AGA', 'RAK', 'FEZ', 'TNG', 'CPH', 'TRF', 'HEL', 'RIX', 'VNO',
            'TLL', 'KUN', 'BFS', 'EDI', 'GLA', 'ORK', 'BJV', 'DLM', 'PFO', 'ZTH',
            'CHQ', 'CFU', 'KGS', 'RHO', 'SPU', 'DBV', 'ZAD', 'PUY', 'TIA', 'TGD',
            'RVN', 'SZG', 'VCE', 'PSR', 'OLB', 'MXP', 'BLQ'],
    'NCL': ['DUB', 'AGP', 'ALC', 'PMI', 'IBZ', 'MAH', 'ACE', 'LPA', 'TFS', 'FUE',
            'BCN', 'GRO', 'VLC', 'MAD', 'SVQ', 'BVA', 'NTE', 'TLS', 'MRS', 'CRL',
            'BGY', 'CIA', 'PSA', 'VRN', 'PMO', 'CTA', 'CAG', 'BRI', 'NAP', 'TRN',
            'AMS', 'EIN', 'FMM', 'CGN', 'HHN', 'BER', 'NUE', 'KRK', 'GDN', 'WRO',
            'POZ', 'KTW', 'WMI', 'PRG', 'BUD', 'VIE', 'BTS', 'OTP', 'SOF', 'ATH',
            'SKG', 'MLA', 'FAO', 'LIS', 'OPO', 'AGA', 'RAK', 'FEZ', 'TNG', 'CPH',
            'TRF', 'HEL', 'RIX', 'VNO', 'TLL', 'KUN', 'BFS', 'EDI', 'GLA', 'ORK',
            'BJV', 'DLM', 'PFO', 'ZTH', 'CHQ', 'CFU', 'KGS', 'RHO', 'SPU', 'DBV',
            'ZAD', 'TIA', 'TGD', 'RVN', 'SZG', 'VCE', 'PSR', 'OLB', 'MXP', 'BLQ'],
    'LBA': ['DUB', 'AGP', 'ALC', 'PMI', 'IBZ', 'MAH', 'ACE', 'LPA', 'TFS', 'FUE',
            'BCN', 'GRO', 'VLC', 'MAD', 'SVQ', 'BVA', 'NTE', 'TLS', 'MRS', 'CRL',
            'BGY', 'CIA', 'PSA', 'VRN', 'PMO', 'CTA', 'CAG', 'BRI', 'NAP', 'TRN',
            'AMS', 'EIN', 'FMM', 'CGN', 'HHN', 'BER', 'NUE', 'KRK', 'GDN', 'WRO',
            'POZ', 'KTW', 'WMI', 'PRG', 'BUD', 'VIE', 'BTS', 'OTP', 'SOF', 'ATH',
            'SKG', 'MLA', 'FAO', 'LIS', 'OPO', 'AGA', 'RAK', 'FEZ', 'TNG', 'CPH',
            'TRF', 'HEL', 'RIX', 'VNO', 'TLL', 'KUN', 'BFS', 'EDI', 'GLA', 'ORK',
            'BJV', 'DLM', 'PFO', 'ZTH', 'CHQ', 'CFU', 'KGS', 'RHO', 'SPU', 'DBV',
            'ZAD', 'TIA', 'TGD', 'RVN', 'SZG', 'VCE', 'PSR', 'OLB', 'MXP', 'BLQ'],
    'NQY': ['DUB', 'STN', 'LGW', 'MAN', 'BHX', 'BRS', 'EDI', 'GLA', 'LPL', 'EMA',
            'LBA', 'NCL', 'CWL', 'BFS', 'ORK', 'SNN', 'AGP', 'ALC', 'PMI', 'ACE',
            'LPA', 'TFS', 'FUE', 'BCN', 'GRO', 'VLC', 'MAD', 'SVQ', 'BVA', 'NTE',
            'TLS', 'MRS', 'CRL', 'BGY', 'CIA', 'PSA', 'VRN', 'PMO', 'CTA', 'CAG',
            'BRI', 'NAP', 'TRN', 'AMS', 'EIN', 'FMM', 'CGN', 'HHN', 'BER', 'KRK',
            'GDN', 'WRO', 'POZ', 'KTW', 'WMI', 'PRG', 'BUD', 'VIE', 'BTS', 'OTP',
            'SOF', 'ATH', 'MLA', 'FAO', 'LIS', 'OPO', 'AGA', 'RAK', 'FEZ', 'TNG',
            'CPH', 'TRF', 'HEL', 'RIX', 'VNO', 'TLL', 'KUN', 'BJV', 'DLM', 'PFO',
            'ZTH', 'CHQ', 'CFU', 'KGS', 'RHO', 'SPU', 'DBV', 'ZAD', 'PUY', 'TIA',
            'TGD', 'RVN', 'SZG', 'VCE', 'PSR', 'OLB', 'MXP', 'BLQ'],
    'ORK': ['DUB', 'STN', 'LGW', 'MAN', 'BHX', 'BRS', 'EDI', 'GLA', 'LPL', 'EMA',
            'BFS', 'CWL', 'NQY', 'SNN', 'KIR', 'NOC', 'AGP', 'ALC', 'PMI', 'IBZ',
            'MAH', 'ACE', 'LPA', 'TFS', 'FUE', 'BCN', 'GRO', 'VLC', 'MAD', 'SVQ',
            'BVA', 'NTE', 'TLS', 'MRS', 'CRL', 'BGY', 'CIA', 'PSA', 'VRN', 'PMO',
            'CTA', 'CAG', 'BRI', 'NAP', 'TRN', 'AMS', 'EIN', 'FMM', 'CGN', 'HHN',
            'BER', 'KRK', 'GDN', 'WRO', 'POZ', 'KTW', 'WMI', 'PRG', 'BUD', 'VIE',
            'BTS', 'OTP', 'SOF', 'ATH', 'SKG', 'MLA', 'FAO', 'LIS', 'OPO', 'AGA',
            'RAK', 'FEZ', 'TNG', 'CPH', 'TRF', 'HEL', 'RIX', 'VNO', 'TLL', 'KUN',
            'BJV', 'DLM', 'PFO', 'ZTH', 'CHQ', 'CFU', 'KGS', 'RHO', 'SPU', 'DBV',
            'ZAD', 'PUY', 'TIA', 'TGD', 'RVN', 'SZG', 'VCE', 'PSR', 'OLB', 'MXP',
            'BLQ'],
    'SNN': ['DUB', 'STN', 'LGW', 'MAN', 'BHX', 'BRS', 'EDI', 'GLA', 'LPL', 'EMA',
            'BFS', 'ORK', 'KIR', 'NOC', 'AGP', 'ALC', 'PMI', 'MAH', 'ACE', 'LPA',
            'TFS', 'FUE', 'BCN', 'GRO', 'VLC', 'MAD', 'SVQ', 'BVA', 'NTE', 'TLS',
            'MRS', 'CRL', 'BGY', 'CIA', 'PSA', 'VRN', 'PMO', 'CTA', 'CAG', 'BRI',
            'NAP', 'TRN', 'AMS', 'EIN', 'FMM', 'CGN', 'HHN', 'BER', 'KRK', 'GDN',
            'WRO', 'POZ', 'KTW', 'WMI', 'PRG', 'BUD', 'VIE', 'BTS', 'OTP', 'SOF',
            'ATH', 'MLA', 'FAO', 'LIS', 'OPO', 'AGA', 'RAK', 'FEZ', 'TNG', 'CPH',
            'TRF', 'HEL', 'RIX', 'VNO', 'TLL', 'KUN', 'BJV', 'DLM', 'PFO', 'ZTH',
            'CHQ', 'CFU', 'KGS', 'RHO', 'SPU', 'DBV', 'ZAD', 'PUY', 'TIA', 'TGD',
            'RVN', 'SZG', 'VCE', 'PSR', 'OLB', 'MXP', 'BLQ'],
    'KIR': ['DUB', 'STN', 'LGW', 'MAN', 'BHX', 'BRS', 'EDI', 'GLA', 'LPL', 'EMA',
            'BFS', 'ORK', 'SNN', 'NOC', 'AGP', 'ALC', 'PMI', 'MAH', 'ACE', 'LPA',
            'TFS', 'FUE', 'BCN', 'GRO', 'VLC', 'MAD', 'SVQ', 'BVA', 'NTE', 'TLS',
            'MRS', 'CRL', 'BGY', 'CIA', 'PSA', 'VRN', 'PMO', 'CTA', 'CAG', 'BRI',
            'NAP', 'TRN', 'AMS', 'EIN', 'FMM', 'CGN', 'HHN', 'BER', 'KRK', 'GDN',
            'WRO', 'POZ', 'KTW', 'WMI', 'PRG', 'BUD', 'VIE', 'BTS', 'OTP', 'SOF',
            'ATH', 'MLA', 'FAO', 'LIS', 'OPO', 'AGA', 'RAK', 'FEZ', 'TNG', 'CPH',
            'TRF', 'HEL', 'RIX', 'VNO', 'TLL', 'KUN', 'BJV', 'DLM', 'PFO', 'ZTH',
            'CHQ', 'CFU', 'KGS', 'RHO', 'SPU', 'DBV', 'ZAD', 'PUY', 'TIA', 'TGD',
            'RVN', 'SZG', 'VCE', 'PSR', 'OLB', 'MXP', 'BLQ'],
    'NOC': ['DUB', 'STN', 'LGW', 'MAN', 'BHX', 'BRS', 'EDI', 'GLA', 'LPL', 'EMA',
            'BFS', 'ORK', 'SNN', 'KIR', 'AGP', 'ALC', 'PMI', 'MAH', 'ACE', 'LPA',
            'TFS', 'FUE', 'BCN', 'GRO', 'VLC', 'MAD', 'SVQ', 'BVA', 'NTE', 'TLS',
            'MRS', 'CRL', 'BGY', 'CIA', 'PSA', 'VRN', 'PMO', 'CTA', 'CAG', 'BRI',
            'NAP', 'TRN', 'AMS', 'EIN', 'FMM', 'CGN', 'HHN', 'BER', 'KRK', 'GDN',
            'WRO', 'POZ', 'KTW', 'WMI', 'PRG', 'BUD', 'VIE', 'BTS', 'OTP', 'SOF',
            'ATH', 'MLA', 'FAO', 'LIS', 'OPO', 'AGA', 'RAK', 'FEZ', 'TNG', 'CPH',
            'TRF', 'HEL', 'RIX', 'VNO', 'TLL', 'KUN', 'BJV', 'DLM', 'PFO', 'ZTH',
            'CHQ', 'CFU', 'KGS', 'RHO', 'SPU', 'DBV', 'ZAD', 'PUY', 'TIA', 'TGD',
            'RVN', 'SZG', 'VCE', 'PSR', 'OLB', 'MXP', 'BLQ'],
    # Continental bases (trimmed but real topology)
    'MAD': ['STN', 'LGW', 'MAN', 'BHX', 'BRS', 'EDI', 'GLA', 'LPL', 'EMA', 'BFS',
            'DUB', 'ORK', 'CWL', 'NCL', 'LBA', 'BCN', 'VLC', 'ALC', 'PMI', 'IBZ',
            'MAH', 'AGP', 'SVQ', 'ACE', 'LPA', 'TFS', 'FUE', 'LEI', 'RMU', 'SCQ',
            'SDR', 'ZAZ', 'REU', 'GRO', 'CDT', 'BVA', 'MRS', 'NTE', 'TLS', 'CRL',
            'BGY', 'CIA', 'FCO', 'PSA', 'VRN', 'BLQ', 'PMO', 'CTA', 'CAG', 'BRI',
            'NAP', 'TRN', 'MXP', 'AMS', 'EIN', 'FMM', 'CGN', 'HHN', 'BER', 'HAM',
            'NUE', 'KRK', 'WMI', 'PRG', 'BUD', 'VIE', 'BTS', 'OTP', 'CLJ', 'SOF',
            'ATH', 'SKG', 'MLA', 'FAO', 'LIS', 'OPO', 'AGA', 'RAK', 'FEZ', 'TNG',
            'RBA', 'ESU', 'CPH', 'ARN', 'TRF', 'HEL', 'RIX', 'VNO', 'TLL', 'DUB'],
    'BCN': ['STN', 'LGW', 'MAN', 'BHX', 'BRS', 'EDI', 'GLA', 'LPL', 'EMA', 'BFS',
            'DUB', 'ORK', 'CWL', 'NCL', 'LBA', 'MAD', 'VLC', 'ALC', 'PMI', 'IBZ',
            'MAH', 'AGP', 'SVQ', 'ACE', 'LPA', 'TFS', 'FUE', 'LEI', 'RMU', 'SCQ',
            'SDR', 'ZAZ', 'BVA', 'MRS', 'NTE', 'TLS', 'CRL', 'BGY', 'CIA', 'FCO',
            'PSA', 'VRN', 'BLQ', 'PMO', 'CTA', 'CAG', 'BRI', 'NAP', 'TRN', 'MXP',
            'AMS', 'EIN', 'FMM', 'CGN', 'HHN', 'BER', 'HAM', 'NUE', 'KRK', 'GDN',
            'WRO', 'POZ', 'KTW', 'WMI', 'PRG', 'BUD', 'VIE', 'BTS', 'OTP', 'CLJ',
            'SOF', 'ATH', 'SKG', 'MLA', 'FAO', 'LIS', 'OPO', 'AGA', 'RAK', 'FEZ',
            'TNG', 'RBA', 'CPH', 'ARN', 'TRF', 'HEL', 'RIX', 'VNO', 'TLL', 'KUN'],
    'ALC': ['STN', 'LGW', 'MAN', 'BHX', 'BRS', 'EDI', 'GLA', 'LPL', 'EMA', 'BFS',
            'DUB', 'ORK', 'CWL', 'NCL', 'LBA', 'NQY', 'MAD', 'BCN', 'VLC', 'PMI',
            'IBZ', 'MAH', 'AGP', 'SVQ', 'ACE', 'LPA', 'TFS', 'FUE', 'LEI', 'RMU',
            'BVA', 'MRS', 'NTE', 'TLS', 'CRL', 'BGY', 'CIA', 'PSA', 'VRN', 'BLQ',
            'PMO', 'CTA', 'CAG', 'BRI', 'NAP', 'TRN', 'AMS', 'EIN', 'FMM', 'CGN',
            'HHN', 'BER', 'HAM', 'NUE', 'KRK', 'GDN', 'WRO', 'POZ', 'KTW', 'WMI',
            'PRG', 'BUD', 'VIE', 'BTS', 'OTP', 'SOF', 'ATH', 'MLA', 'FAO', 'LIS',
            'OPO', 'AGA', 'RAK', 'FEZ', 'TNG', 'CPH', 'ARN', 'TRF', 'HEL', 'RIX',
            'VNO', 'TLL', 'KUN', 'DUB', 'BFS'],
    'PMI': ['STN', 'LGW', 'MAN', 'BHX', 'BRS', 'EDI', 'GLA', 'LPL', 'EMA', 'BFS',
            'DUB', 'ORK', 'CWL', 'NCL', 'LBA', 'NQY', 'MAD', 'BCN', 'VLC', 'ALC',
            'IBZ', 'MAH', 'AGP', 'SVQ', 'ACE', 'LPA', 'TFS', 'FUE', 'LEI', 'RMU',
            'BVA', 'MRS', 'NTE', 'TLS', 'CRL', 'BGY', 'CIA', 'PSA', 'VRN', 'BLQ',
            'PMO', 'CTA', 'CAG', 'BRI', 'NAP', 'TRN', 'MXP', 'AMS', 'EIN', 'FMM',
            'CGN', 'HHN', 'BER', 'HAM', 'NUE', 'KRK', 'GDN', 'WRO', 'POZ', 'KTW',
            'WMI', 'PRG', 'BUD', 'VIE', 'BTS', 'OTP', 'SOF', 'ATH', 'MLA', 'FAO',
            'LIS', 'OPO', 'AGA', 'RAK', 'FEZ', 'TNG', 'CPH', 'ARN', 'TRF', 'HEL',
            'RIX', 'VNO', 'TLL', 'KUN', 'DUB'],
    'AGP': ['STN', 'LGW', 'MAN', 'BHX', 'BRS', 'EDI', 'GLA', 'LPL', 'EMA', 'BFS',
            'DUB', 'ORK', 'SNN', 'CWL', 'NCL', 'LBA', 'NQY', 'MAD', 'BCN', 'VLC',
            'ALC', 'PMI', 'IBZ', 'MAH', 'SVQ', 'ACE', 'LPA', 'TFS', 'FUE', 'LEI',
            'RMU', 'BVA', 'MRS', 'NTE', 'TLS', 'CRL', 'BGY', 'CIA', 'FCO', 'PSA',
            'VRN', 'BLQ', 'PMO', 'CTA', 'CAG', 'BRI', 'NAP', 'TRN', 'MXP', 'AMS',
            'EIN', 'FMM', 'CGN', 'HHN', 'BER', 'HAM', 'NUE', 'KRK', 'GDN', 'WRO',
            'POZ', 'KTW', 'WMI', 'PRG', 'BUD', 'VIE', 'BTS', 'OTP', 'CLJ', 'SOF',
            'ATH', 'SKG', 'MLA', 'FAO', 'LIS', 'OPO', 'AGA', 'RAK', 'FEZ', 'TNG',
            'RBA', 'CPH', 'ARN', 'TRF', 'HEL', 'RIX', 'VNO', 'TLL', 'KUN', 'DUB'],
    'CRL': ['STN', 'LGW', 'MAN', 'BHX', 'BRS', 'EDI', 'GLA', 'LPL', 'EMA', 'BFS',
            'DUB', 'ORK', 'CWL', 'NCL', 'LBA', 'NQY', 'MAD', 'BCN', 'VLC', 'ALC',
            'PMI', 'IBZ', 'MAH', 'AGP', 'SVQ', 'ACE', 'LPA', 'TFS', 'FUE', 'LEI',
            'RMU', 'BVA', 'MRS', 'NTE', 'TLS', 'BGY', 'CIA', 'FCO', 'PSA', 'VRN',
            'BLQ', 'PMO', 'CTA', 'CAG', 'BRI', 'NAP', 'TRN', 'MXP', 'AMS', 'EIN',
            'FMM', 'CGN', 'HHN', 'BER', 'HAM', 'NUE', 'KRK', 'GDN', 'WRO', 'POZ',
            'KTW', 'WMI', 'PRG', 'BUD', 'VIE', 'BTS', 'OTP', 'CLJ', 'SOF', 'ATH',
            'SKG', 'MLA', 'FAO', 'LIS', 'OPO', 'AGA', 'RAK', 'FEZ', 'TNG', 'RBA',
            'CPH', 'ARN', 'TRF', 'HEL', 'RIX', 'VNO', 'TLL', 'KUN', 'DUB'],
    'BVA': ['STN', 'LGW', 'MAN', 'BHX', 'BRS', 'EDI', 'GLA', 'LPL', 'EMA', 'BFS',
            'DUB', 'ORK', 'CWL', 'NCL', 'LBA', 'NQY', 'MAD', 'BCN', 'VLC', 'ALC',
            'PMI', 'IBZ', 'MAH', 'AGP', 'SVQ', 'ACE', 'LPA', 'TFS', 'FUE', 'LEI',
            'RMU', 'MRS', 'NTE', 'TLS', 'CRL', 'BGY', 'CIA', 'FCO', 'PSA', 'VRN',
            'BLQ', 'PMO', 'CTA', 'CAG', 'BRI', 'NAP', 'TRN', 'MXP', 'AMS', 'EIN',
            'FMM', 'CGN', 'HHN', 'BER', 'HAM', 'NUE', 'KRK', 'GDN', 'WRO', 'POZ',
            'KTW', 'WMI', 'PRG', 'BUD', 'VIE', 'BTS', 'OTP', 'CLJ', 'SOF', 'ATH',
            'SKG', 'MLA', 'FAO', 'LIS', 'OPO', 'AGA', 'RAK', 'FEZ', 'TNG', 'RBA',
            'CPH', 'ARN', 'TRF', 'HEL', 'RIX', 'VNO', 'TLL', 'KUN', 'DUB'],
    'MRS': ['STN', 'LGW', 'MAN', 'BHX', 'BRS', 'EDI', 'GLA', 'LPL', 'EMA', 'BFS',
            'DUB', 'ORK', 'CWL', 'NCL', 'LBA', 'NQY', 'MAD', 'BCN', 'VLC', 'ALC',
            'PMI', 'IBZ', 'MAH', 'AGP', 'SVQ', 'ACE', 'LPA', 'TFS', 'FUE', 'LEI',
            'RMU', 'BVA', 'NTE', 'TLS', 'CRL', 'BGY', 'CIA', 'FCO', 'PSA', 'VRN',
            'BLQ', 'PMO', 'CTA', 'CAG', 'BRI', 'NAP', 'TRN', 'MXP', 'AMS', 'EIN',
            'FMM', 'CGN', 'HHN', 'BER', 'HAM', 'NUE', 'KRK', 'GDN', 'WRO', 'POZ',
            'KTW', 'WMI', 'PRG', 'BUD', 'VIE', 'BTS', 'OTP', 'CLJ', 'SOF', 'ATH',
            'SKG', 'MLA', 'FAO', 'LIS', 'OPO', 'AGA', 'RAK', 'FEZ', 'TNG', 'RBA',
            'CPH', 'ARN', 'TRF', 'HEL', 'RIX', 'VNO', 'TLL', 'KUN', 'DUB'],
    'BGY': ['STN', 'LGW', 'MAN', 'BHX', 'BRS', 'EDI', 'GLA', 'LPL', 'EMA', 'BFS',
            'DUB', 'ORK', 'CWL', 'NCL', 'LBA', 'NQY', 'MAD', 'BCN', 'VLC', 'ALC',
            'PMI', 'IBZ', 'MAH', 'AGP', 'SVQ', 'ACE', 'LPA', 'TFS', 'FUE', 'LEI',
            'RMU', 'BVA', 'MRS', 'NTE', 'TLS', 'CRL', 'CIA', 'FCO', 'PSA', 'VRN',
            'BLQ', 'PMO', 'CTA', 'CAG', 'BRI', 'NAP', 'TRN', 'MXP', 'AMS', 'EIN',
            'FMM', 'CGN', 'HHN', 'BER', 'HAM', 'NUE', 'KRK', 'GDN', 'WRO', 'POZ',
            'KTW', 'WMI', 'PRG', 'BUD', 'VIE', 'BTS', 'OTP', 'CLJ', 'SOF', 'ATH',
            'SKG', 'MLA', 'FAO', 'LIS', 'OPO', 'AGA', 'RAK', 'FEZ', 'TNG', 'RBA',
            'CPH', 'ARN', 'TRF', 'HEL', 'RIX', 'VNO', 'TLL', 'KUN', 'DUB'],
    'CIA': ['STN', 'LGW', 'MAN', 'BHX', 'BRS', 'EDI', 'GLA', 'LPL', 'EMA', 'BFS',
            'DUB', 'ORK', 'CWL', 'NCL', 'LBA', 'NQY', 'MAD', 'BCN', 'VLC', 'ALC',
            'PMI', 'IBZ', 'MAH', 'AGP', 'SVQ', 'ACE', 'LPA', 'TFS', 'FUE', 'LEI',
            'RMU', 'BVA', 'MRS', 'NTE', 'TLS', 'CRL', 'BGY', 'FCO', 'PSA', 'VRN',
            'BLQ', 'PMO', 'CTA', 'CAG', 'BRI', 'NAP', 'TRN', 'MXP', 'AMS', 'EIN',
            'FMM', 'CGN', 'HHN', 'BER', 'HAM', 'KRK', 'GDN', 'WRO', 'POZ', 'KTW',
            'WMI', 'PRG', 'BUD', 'VIE', 'BTS', 'OTP', 'CLJ', 'SOF', 'ATH', 'SKG',
            'MLA', 'FAO', 'LIS', 'OPO', 'AGA', 'RAK', 'FEZ', 'TNG', 'RBA', 'CPH',
            'ARN', 'TRF', 'HEL', 'RIX', 'VNO', 'TLL', 'KUN', 'DUB'],
    'BUD': ['STN', 'LGW', 'MAN', 'BHX', 'BRS', 'EDI', 'GLA', 'LPL', 'EMA', 'BFS',
            'DUB', 'ORK', 'CWL', 'NCL', 'LBA', 'MAD', 'BCN', 'VLC', 'ALC', 'PMI',
            'IBZ', 'MAH', 'AGP', 'SVQ', 'ACE', 'LPA', 'TFS', 'FUE', 'BVA', 'MRS',
            'NTE', 'TLS', 'CRL', 'BGY', 'CIA', 'FCO', 'PSA', 'VRN', 'BLQ', 'PMO',
            'CTA', 'CAG', 'BRI', 'NAP', 'TRN', 'MXP', 'AMS', 'EIN', 'FMM', 'CGN',
            'HHN', 'BER', 'HAM', 'NUE', 'KRK', 'GDN', 'WRO', 'POZ', 'KTW', 'WMI',
            'PRG', 'VIE', 'BTS', 'OTP', 'CLJ', 'SOF', 'ATH', 'SKG', 'MLA', 'FAO',
            'LIS', 'OPO', 'AGA', 'RAK', 'FEZ', 'TNG', 'RBA', 'CPH', 'ARN', 'TRF',
            'HEL', 'RIX', 'VNO', 'TLL', 'KUN', 'DUB'],
    'WMI': ['STN', 'LGW', 'MAN', 'BHX', 'BRS', 'EDI', 'GLA', 'LPL', 'EMA', 'BFS',
            'DUB', 'ORK', 'CWL', 'NCL', 'LBA', 'MAD', 'BCN', 'VLC', 'ALC', 'PMI',
            'IBZ', 'MAH', 'AGP', 'SVQ', 'ACE', 'LPA', 'TFS', 'FUE', 'BVA', 'MRS',
            'NTE', 'TLS', 'CRL', 'BGY', 'CIA', 'FCO', 'PSA', 'VRN', 'BLQ', 'PMO',
            'CTA', 'CAG', 'BRI', 'NAP', 'TRN', 'MXP', 'AMS', 'EIN', 'FMM', 'CGN',
            'HHN', 'BER', 'HAM', 'NUE', 'KRK', 'GDN', 'WRO', 'POZ', 'KTW', 'PRG',
            'BUD', 'VIE', 'BTS', 'OTP', 'CLJ', 'SOF', 'ATH', 'MLA', 'FAO', 'LIS',
            'OPO', 'AGA', 'RAK', 'CPH', 'ARN', 'TRF', 'HEL', 'RIX', 'VNO', 'TLL',
            'KUN', 'DUB'],
    'KRK': ['STN', 'LGW', 'MAN', 'BHX', 'BRS', 'EDI', 'GLA', 'LPL', 'EMA', 'BFS',
            'DUB', 'ORK', 'CWL', 'NCL', 'LBA', 'MAD', 'BCN', 'VLC', 'ALC', 'PMI',
            'IBZ', 'MAH', 'AGP', 'SVQ', 'ACE', 'LPA', 'TFS', 'FUE', 'BVA', 'MRS',
            'NTE', 'TLS', 'CRL', 'BGY', 'CIA', 'FCO', 'PSA', 'VRN', 'BLQ', 'PMO',
            'CTA', 'CAG', 'BRI', 'NAP', 'TRN', 'MXP', 'AMS', 'EIN', 'FMM', 'CGN',
            'HHN', 'BER', 'HAM', 'NUE', 'GDN', 'WRO', 'POZ', 'KTW', 'WMI', 'PRG',
            'BUD', 'VIE', 'BTS', 'OTP', 'CLJ', 'SOF', 'ATH', 'MLA', 'FAO', 'LIS',
            'OPO', 'AGA', 'RAK', 'CPH', 'ARN', 'TRF', 'HEL', 'RIX', 'VNO', 'TLL',
            'KUN', 'DUB'],
    'ATH': ['STN', 'LGW', 'MAN', 'BHX', 'BRS', 'EDI', 'GLA', 'LPL', 'EMA', 'BFS',
            'DUB', 'ORK', 'CWL', 'NCL', 'LBA', 'MAD', 'BCN', 'VLC', 'ALC', 'PMI',
            'IBZ', 'MAH', 'AGP', 'SVQ', 'ACE', 'LPA', 'TFS', 'FUE', 'BVA', 'MRS',
            'NTE', 'TLS', 'CRL', 'BGY', 'CIA', 'FCO', 'PSA', 'VRN', 'BLQ', 'PMO',
            'CTA', 'CAG', 'BRI', 'NAP', 'TRN', 'MXP', 'AMS', 'EIN', 'FMM', 'CGN',
            'HHN', 'BER', 'HAM', 'KRK', 'GDN', 'WRO', 'POZ', 'KTW', 'WMI', 'PRG',
            'BUD', 'VIE', 'BTS', 'OTP', 'CLJ', 'SOF', 'SKG', 'MLA', 'FAO', 'LIS',
            'OPO', 'AGA', 'RAK', 'CPH', 'ARN', 'TRF', 'HEL', 'RIX', 'VNO', 'TLL',
            'DUB', 'PFO', 'CHQ', 'CFU', 'KGS', 'RHO', 'JTR', 'ZTH', 'EFL'],
    'LIS': ['STN', 'LGW', 'MAN', 'BHX', 'BRS', 'EDI', 'GLA', 'LPL', 'EMA', 'BFS',
            'DUB', 'ORK', 'CWL', 'NCL', 'LBA', 'MAD', 'BCN', 'VLC', 'ALC', 'PMI',
            'IBZ', 'MAH', 'AGP', 'SVQ', 'ACE', 'LPA', 'TFS', 'FUE', 'BVA', 'MRS',
            'NTE', 'TLS', 'CRL', 'BGY', 'CIA', 'FCO', 'PSA', 'VRN', 'BLQ', 'PMO',
            'CTA', 'CAG', 'BRI', 'NAP', 'TRN', 'MXP', 'AMS', 'EIN', 'FMM', 'CGN',
            'HHN', 'BER', 'HAM', 'KRK', 'GDN', 'WRO', 'POZ', 'KTW', 'WMI', 'PRG',
            'BUD', 'VIE', 'BTS', 'OTP', 'CLJ', 'SOF', 'ATH', 'SKG', 'MLA', 'FAO',
            'OPO', 'AGA', 'RAK', 'CPH', 'ARN', 'TRF', 'HEL', 'RIX', 'VNO', 'TLL',
            'DUB'],
    'OTP': ['STN', 'LGW', 'MAN', 'BHX', 'BRS', 'EDI', 'GLA', 'LPL', 'EMA', 'BFS',
            'DUB', 'ORK', 'CWL', 'NCL', 'LBA', 'MAD', 'BCN', 'VLC', 'ALC', 'PMI',
            'IBZ', 'MAH', 'AGP', 'SVQ', 'ACE', 'LPA', 'TFS', 'FUE', 'BVA', 'MRS',
            'NTE', 'TLS', 'CRL', 'BGY', 'CIA', 'FCO', 'PSA', 'VRN', 'BLQ', 'PMO',
            'CTA', 'CAG', 'BRI', 'NAP', 'TRN', 'MXP', 'AMS', 'EIN', 'FMM', 'CGN',
            'HHN', 'BER', 'HAM', 'KRK', 'GDN', 'WRO', 'POZ', 'KTW', 'WMI', 'PRG',
            'BUD', 'VIE', 'BTS', 'CLJ', 'SOF', 'ATH', 'SKG', 'MLA', 'FAO', 'LIS',
            'OPO', 'AGA', 'RAK', 'CPH', 'ARN', 'TRF', 'HEL', 'RIX', 'VNO', 'TLL',
            'DUB'],
    'SOF': ['STN', 'LGW', 'MAN', 'BHX', 'BRS', 'EDI', 'GLA', 'LPL', 'EMA', 'BFS',
            'DUB', 'ORK', 'CWL', 'NCL', 'LBA', 'MAD', 'BCN', 'VLC', 'ALC', 'PMI',
            'IBZ', 'MAH', 'AGP', 'SVQ', 'ACE', 'LPA', 'TFS', 'FUE', 'BVA', 'MRS',
            'NTE', 'TLS', 'CRL', 'BGY', 'CIA', 'FCO', 'PSA', 'VRN', 'BLQ', 'PMO',
            'CTA', 'CAG', 'BRI', 'NAP', 'TRN', 'MXP', 'AMS', 'EIN', 'FMM', 'CGN',
            'HHN', 'BER', 'HAM', 'KRK', 'GDN', 'WRO', 'POZ', 'KTW', 'WMI', 'PRG',
            'BUD', 'VIE', 'BTS', 'OTP', 'CLJ', 'ATH', 'SKG', 'MLA', 'FAO', 'LIS',
            'OPO', 'AGA', 'RAK', 'CPH', 'ARN', 'TRF', 'HEL', 'RIX', 'VNO', 'TLL',
            'DUB'],
    'FAO': ['STN', 'LGW', 'MAN', 'BHX', 'BRS', 'EDI', 'GLA', 'LPL', 'EMA', 'BFS',
            'DUB', 'ORK', 'SNN', 'CWL', 'NCL', 'LBA', 'NQY', 'MAD', 'BCN', 'VLC',
            'ALC', 'PMI', 'IBZ', 'MAH', 'AGP', 'SVQ', 'ACE', 'LPA', 'TFS', 'FUE',
            'BVA', 'MRS', 'NTE', 'TLS', 'CRL', 'BGY', 'CIA', 'PSA', 'VRN', 'BLQ',
            'PMO', 'CTA', 'CAG', 'BRI', 'NAP', 'TRN', 'MXP', 'AMS', 'EIN', 'FMM',
            'CGN', 'HHN', 'BER', 'KRK', 'GDN', 'WRO', 'POZ', 'KTW', 'WMI', 'PRG',
            'BUD', 'VIE', 'BTS', 'OTP', 'CLJ', 'SOF', 'ATH', 'SKG', 'MLA', 'LIS',
            'OPO', 'AGA', 'RAK', 'FEZ', 'TNG', 'CPH', 'ARN', 'TRF', 'HEL', 'RIX',
            'VNO', 'TLL', 'KUN', 'DUB'],
    'MLA': ['STN', 'LGW', 'MAN', 'BHX', 'BRS', 'EDI', 'GLA', 'LPL', 'EMA', 'BFS',
            'DUB', 'ORK', 'CWL', 'NCL', 'LBA', 'MAD', 'BCN', 'VLC', 'ALC', 'PMI',
            'IBZ', 'MAH', 'AGP', 'SVQ', 'ACE', 'LPA', 'TFS', 'FUE', 'BVA', 'MRS',
            'NTE', 'TLS', 'CRL', 'BGY', 'CIA', 'FCO', 'PSA', 'VRN', 'BLQ', 'PMO',
            'CTA', 'CAG', 'BRI', 'NAP', 'TRN', 'MXP', 'AMS', 'EIN', 'FMM', 'CGN',
            'HHN', 'BER', 'HAM', 'KRK', 'GDN', 'WRO', 'POZ', 'KTW', 'WMI', 'PRG',
            'BUD', 'VIE', 'BTS', 'OTP', 'CLJ', 'SOF', 'ATH', 'SKG', 'FAO', 'LIS',
            'OPO', 'AGA', 'RAK', 'TNG', 'CPH', 'ARN', 'TRF', 'HEL', 'RIX', 'VNO',
            'TLL', 'KUN', 'DUB'],
    'EIN': ['STN', 'LGW', 'MAN', 'BHX', 'BRS', 'EDI', 'GLA', 'LPL', 'EMA', 'BFS',
            'DUB', 'ORK', 'CWL', 'NCL', 'LBA', 'MAD', 'BCN', 'VLC', 'ALC', 'PMI',
            'IBZ', 'MAH', 'AGP', 'SVQ', 'ACE', 'LPA', 'TFS', 'FUE', 'BVA', 'MRS',
            'NTE', 'TLS', 'CRL', 'BGY', 'CIA', 'FCO', 'PSA', 'VRN', 'BLQ', 'PMO',
            'CTA', 'CAG', 'BRI', 'NAP', 'TRN', 'MXP', 'CGN', 'HHN', 'BER', 'HAM',
            'NUE', 'KRK', 'GDN', 'WRO', 'POZ', 'KTW', 'WMI', 'PRG', 'BUD', 'VIE',
            'BTS', 'OTP', 'CLJ', 'SOF', 'ATH', 'SKG', 'MLA', 'FAO', 'LIS', 'OPO',
            'AGA', 'RAK', 'TNG', 'CPH', 'ARN', 'TRF', 'HEL', 'RIX', 'VNO', 'TLL',
            'KUN', 'DUB'],
    'BER': ['STN', 'LGW', 'MAN', 'BHX', 'BRS', 'EDI', 'GLA', 'LPL', 'EMA', 'BFS',
            'DUB', 'ORK', 'CWL', 'NCL', 'LBA', 'MAD', 'BCN', 'VLC', 'ALC', 'PMI',
            'IBZ', 'MAH', 'AGP', 'SVQ', 'ACE', 'LPA', 'TFS', 'FUE', 'BVA', 'MRS',
            'NTE', 'TLS', 'CRL', 'BGY', 'CIA', 'FCO', 'PSA', 'VRN', 'BLQ', 'PMO',
            'CTA', 'CAG', 'BRI', 'NAP', 'TRN', 'MXP', 'EIN', 'FMM', 'CGN', 'HHN',
            'HAM', 'NUE', 'KRK', 'GDN', 'WRO', 'POZ', 'KTW', 'WMI', 'PRG', 'BUD',
            'VIE', 'BTS', 'OTP', 'CLJ', 'SOF', 'ATH', 'SKG', 'MLA', 'FAO', 'LIS',
            'OPO', 'AGA', 'RAK', 'CPH', 'ARN', 'TRF', 'HEL', 'RIX', 'VNO', 'TLL',
            'KUN', 'DUB'],
    'CGN': ['STN', 'LGW', 'MAN', 'BHX', 'BRS', 'EDI', 'GLA', 'LPL', 'EMA', 'BFS',
            'DUB', 'ORK', 'CWL', 'NCL', 'LBA', 'MAD', 'BCN', 'VLC', 'ALC', 'PMI',
            'IBZ', 'MAH', 'AGP', 'SVQ', 'ACE', 'LPA', 'TFS', 'FUE', 'BVA', 'MRS',
            'NTE', 'TLS', 'CRL', 'BGY', 'CIA', 'FCO', 'PSA', 'VRN', 'BLQ', 'PMO',
            'CTA', 'CAG', 'BRI', 'NAP', 'TRN', 'MXP', 'EIN', 'FMM', 'HHN', 'BER',
            'HAM', 'NUE', 'KRK', 'GDN', 'WRO', 'POZ', 'KTW', 'WMI', 'PRG', 'BUD',
            'VIE', 'BTS', 'OTP', 'CLJ', 'SOF', 'ATH', 'SKG', 'MLA', 'FAO', 'LIS',
            'OPO', 'AGA', 'RAK', 'CPH', 'ARN', 'TRF', 'HEL', 'RIX', 'VNO', 'TLL',
            'KUN', 'DUB'],
    'PRG': ['STN', 'LGW', 'MAN', 'BHX', 'BRS', 'EDI', 'GLA', 'LPL', 'EMA', 'BFS',
            'DUB', 'ORK', 'CWL', 'NCL', 'LBA', 'MAD', 'BCN', 'VLC', 'ALC', 'PMI',
            'IBZ', 'MAH', 'AGP', 'SVQ', 'ACE', 'LPA', 'TFS', 'FUE', 'BVA', 'MRS',
            'NTE', 'TLS', 'CRL', 'BGY', 'CIA', 'FCO', 'PSA', 'VRN', 'BLQ', 'PMO',
            'CTA', 'CAG', 'BRI', 'NAP', 'TRN', 'MXP', 'EIN', 'FMM', 'CGN', 'HHN',
            'BER', 'HAM', 'NUE', 'KRK', 'GDN', 'WRO', 'POZ', 'KTW', 'WMI', 'BUD',
            'VIE', 'BTS', 'OTP', 'CLJ', 'SOF', 'ATH', 'SKG', 'MLA', 'FAO', 'LIS',
            'OPO', 'AGA', 'RAK', 'CPH', 'ARN', 'TRF', 'HEL', 'RIX', 'VNO', 'TLL',
            'KUN', 'DUB'],
    'VIE': ['STN', 'LGW', 'MAN', 'BHX', 'BRS', 'EDI', 'GLA', 'LPL', 'EMA', 'BFS',
            'DUB', 'ORK', 'CWL', 'NCL', 'LBA', 'MAD', 'BCN', 'VLC', 'ALC', 'PMI',
            'IBZ', 'MAH', 'AGP', 'SVQ', 'ACE', 'LPA', 'TFS', 'FUE', 'BVA', 'MRS',
            'NTE', 'TLS', 'CRL', 'BGY', 'CIA', 'FCO', 'PSA', 'VRN', 'BLQ', 'PMO',
            'CTA', 'CAG', 'BRI', 'NAP', 'TRN', 'MXP', 'EIN', 'FMM', 'CGN', 'HHN',
            'BER', 'HAM', 'NUE', 'KRK', 'GDN', 'WRO', 'POZ', 'KTW', 'WMI', 'PRG',
            'BUD', 'BTS', 'OTP', 'CLJ', 'SOF', 'ATH', 'SKG', 'MLA', 'FAO', 'LIS',
            'OPO', 'AGA', 'RAK', 'CPH', 'ARN', 'TRF', 'HEL', 'RIX', 'VNO', 'TLL',
            'KUN', 'DUB'],
    'RAK': ['STN', 'LGW', 'MAN', 'BHX', 'BRS', 'EDI', 'GLA', 'LPL', 'EMA', 'BFS',
            'DUB', 'ORK', 'CWL', 'NCL', 'LBA', 'MAD', 'BCN', 'VLC', 'ALC', 'PMI',
            'IBZ', 'MAH', 'AGP', 'SVQ', 'ACE', 'LPA', 'TFS', 'FUE', 'BVA', 'MRS',
            'NTE', 'TLS', 'CRL', 'BGY', 'CIA', 'FCO', 'PSA', 'VRN', 'BLQ', 'PMO',
            'CTA', 'CAG', 'BRI', 'NAP', 'TRN', 'MXP', 'EIN', 'FMM', 'CGN', 'HHN',
            'BER', 'HAM', 'KRK', 'GDN', 'WRO', 'POZ', 'KTW', 'WMI', 'PRG', 'BUD',
            'VIE', 'BTS', 'OTP', 'CLJ', 'SOF', 'ATH', 'SKG', 'MLA', 'FAO', 'LIS',
            'OPO', 'AGA', 'CPH', 'ARN', 'TRF', 'HEL', 'RIX', 'VNO', 'TLL', 'DUB'],
    'CPH': ['STN', 'LGW', 'MAN', 'BHX', 'BRS', 'EDI', 'GLA', 'LPL', 'EMA', 'BFS',
            'DUB', 'ORK', 'CWL', 'NCL', 'LBA', 'MAD', 'BCN', 'VLC', 'ALC', 'PMI',
            'IBZ', 'MAH', 'AGP', 'SVQ', 'ACE', 'LPA', 'TFS', 'FUE', 'BVA', 'MRS',
            'NTE', 'TLS', 'CRL', 'BGY', 'CIA', 'FCO', 'PSA', 'VRN', 'BLQ', 'PMO',
            'CTA', 'CAG', 'BRI', 'NAP', 'TRN', 'MXP', 'EIN', 'FMM', 'CGN', 'HHN',
            'BER', 'HAM', 'NUE', 'KRK', 'GDN', 'WRO', 'POZ', 'KTW', 'WMI', 'PRG',
            'BUD', 'VIE', 'BTS', 'OTP', 'CLJ', 'SOF', 'ATH', 'SKG', 'MLA', 'FAO',
            'LIS', 'OPO', 'AGA', 'RAK', 'TNG', 'ARN', 'TRF', 'HEL', 'RIX', 'VNO',
            'TLL', 'KUN', 'DUB'],
    'HEL': ['STN', 'LGW', 'MAN', 'BHX', 'BRS', 'EDI', 'GLA', 'LPL', 'EMA', 'BFS',
            'DUB', 'ORK', 'CWL', 'NCL', 'LBA', 'MAD', 'BCN', 'VLC', 'ALC', 'PMI',
            'IBZ', 'MAH', 'AGP', 'SVQ', 'ACE', 'LPA', 'TFS', 'FUE', 'BVA', 'MRS',
            'NTE', 'TLS', 'CRL', 'BGY', 'CIA', 'FCO', 'PSA', 'VRN', 'BLQ', 'PMO',
            'CTA', 'CAG', 'BRI', 'NAP', 'TRN', 'MXP', 'EIN', 'FMM', 'CGN', 'HHN',
            'BER', 'HAM', 'NUE', 'KRK', 'GDN', 'WRO', 'POZ', 'KTW', 'WMI', 'PRG',
            'BUD', 'VIE', 'BTS', 'OTP', 'CLJ', 'SOF', 'ATH', 'SKG', 'MLA', 'FAO',
            'LIS', 'OPO', 'AGA', 'RAK', 'TNG', 'CPH', 'ARN', 'TRF', 'RIX', 'VNO',
            'TLL', 'KUN', 'DUB', 'RVN'],
    'RIX': ['STN', 'LGW', 'MAN', 'BHX', 'BRS', 'EDI', 'GLA', 'LPL', 'EMA', 'BFS',
            'DUB', 'ORK', 'CWL', 'NCL', 'LBA', 'MAD', 'BCN', 'VLC', 'ALC', 'PMI',
            'IBZ', 'MAH', 'AGP', 'SVQ', 'ACE', 'LPA', 'TFS', 'FUE', 'BVA', 'MRS',
            'NTE', 'TLS', 'CRL', 'BGY', 'CIA', 'FCO', 'PSA', 'VRN', 'BLQ', 'PMO',
            'CTA', 'CAG', 'BRI', 'NAP', 'TRN', 'MXP', 'EIN', 'FMM', 'CGN', 'HHN',
            'BER', 'HAM', 'NUE', 'KRK', 'GDN', 'WRO', 'POZ', 'KTW', 'WMI', 'PRG',
            'BUD', 'VIE', 'BTS', 'OTP', 'CLJ', 'SOF', 'ATH', 'SKG', 'MLA', 'FAO',
            'LIS', 'OPO', 'AGA', 'RAK', 'CPH', 'ARN', 'TRF', 'HEL', 'VNO', 'TLL',
            'KUN', 'DUB'],
    'AGA': ['STN', 'LGW', 'MAN', 'BHX', 'BRS', 'EDI', 'GLA', 'LPL', 'EMA', 'BFS',
            'DUB', 'ORK', 'CWL', 'NCL', 'LBA', 'MAD', 'BCN', 'VLC', 'ALC', 'PMI',
            'IBZ', 'MAH', 'AGP', 'SVQ', 'ACE', 'LPA', 'TFS', 'FUE', 'BVA', 'MRS',
            'NTE', 'TLS', 'CRL', 'BGY', 'CIA', 'FCO', 'PSA', 'VRN', 'BLQ', 'PMO',
            'CTA', 'CAG', 'BRI', 'NAP', 'TRN', 'MXP', 'EIN', 'FMM', 'CGN', 'HHN',
            'BER', 'HAM', 'KRK', 'GDN', 'WRO', 'POZ', 'KTW', 'WMI', 'PRG', 'BUD',
            'VIE', 'BTS', 'OTP', 'CLJ', 'SOF', 'ATH', 'SKG', 'MLA', 'FAO', 'LIS',
            'OPO', 'RAK', 'FEZ', 'TNG', 'RBA', 'CPH', 'ARN', 'TRF', 'HEL', 'DUB'],
    'TFS': ['STN', 'LGW', 'MAN', 'BHX', 'BRS', 'EDI', 'GLA', 'LPL', 'EMA', 'BFS',
            'DUB', 'ORK', 'CWL', 'NCL', 'LBA', 'NQY', 'MAD', 'BCN', 'VLC', 'ALC',
            'PMI', 'IBZ', 'MAH', 'AGP', 'SVQ', 'ACE', 'LPA', 'FUE', 'LEI', 'RMU',
            'BVA', 'MRS', 'NTE', 'TLS', 'CRL', 'BGY', 'CIA', 'FCO', 'PSA', 'VRN',
            'BLQ', 'PMO', 'CTA', 'CAG', 'BRI', 'NAP', 'TRN', 'MXP', 'AMS', 'EIN',
            'FMM', 'CGN', 'HHN', 'BER', 'HAM', 'NUE', 'KRK', 'GDN', 'WRO', 'POZ',
            'KTW', 'WMI', 'PRG', 'BUD', 'VIE', 'BTS', 'OTP', 'CLJ', 'SOF', 'ATH',
            'MLA', 'FAO', 'LIS', 'OPO', 'AGA', 'RAK', 'CPH', 'ARN', 'TRF', 'HEL',
            'RIX', 'VNO', 'TLL', 'KUN', 'DUB'],
    'MXP': ['STN', 'LGW', 'MAN', 'BHX', 'BRS', 'EDI', 'GLA', 'LPL', 'EMA', 'BFS',
            'DUB', 'ORK', 'CWL', 'NCL', 'LBA', 'MAD', 'BCN', 'VLC', 'ALC', 'PMI',
            'IBZ', 'MAH', 'AGP', 'SVQ', 'ACE', 'LPA', 'TFS', 'FUE', 'BVA', 'MRS',
            'NTE', 'TLS', 'CRL', 'BGY', 'CIA', 'FCO', 'PSA', 'VRN', 'BLQ', 'PMO',
            'CTA', 'CAG', 'BRI', 'NAP', 'TRN', 'AMS', 'EIN', 'FMM', 'CGN', 'HHN',
            'BER', 'HAM', 'NUE', 'KRK', 'GDN', 'WRO', 'POZ', 'KTW', 'WMI', 'PRG',
            'BUD', 'VIE', 'BTS', 'OTP', 'CLJ', 'SOF', 'ATH', 'SKG', 'MLA', 'FAO',
            'LIS', 'OPO', 'AGA', 'RAK', 'TNG', 'CPH', 'ARN', 'TRF', 'HEL', 'RIX',
            'VNO', 'TLL', 'KUN', 'DUB'],
    'FCO': ['STN', 'LGW', 'MAN', 'BHX', 'BRS', 'EDI', 'GLA', 'LPL', 'EMA', 'BFS',
            'DUB', 'ORK', 'CWL', 'NCL', 'LBA', 'MAD', 'BCN', 'VLC', 'ALC', 'PMI',
            'IBZ', 'MAH', 'AGP', 'SVQ', 'ACE', 'LPA', 'TFS', 'FUE', 'BVA', 'MRS',
            'NTE', 'TLS', 'CRL', 'BGY', 'CIA', 'PSA', 'VRN', 'BLQ', 'PMO', 'CTA',
            'CAG', 'BRI', 'NAP', 'TRN', 'MXP', 'AMS', 'EIN', 'FMM', 'CGN', 'HHN',
            'BER', 'HAM', 'NUE', 'KRK', 'GDN', 'WRO', 'POZ', 'KTW', 'WMI', 'PRG',
            'BUD', 'VIE', 'BTS', 'OTP', 'CLJ', 'SOF', 'ATH', 'SKG', 'MLA', 'FAO',
            'LIS', 'OPO', 'AGA', 'RAK', 'TNG', 'CPH', 'ARN', 'TRF', 'HEL', 'RIX',
            'VNO', 'TLL', 'KUN', 'DUB'],
}

# Real STN <-> DUB schedules captured from the live results page 2026-09-24.
REAL_STN_DUB = {
    'STN-DUB': [
        ('FR 271', '06:30', '07:50'), ('FR 31', '08:30', '09:50'),
        ('FR 287', '11:35', '12:55'), ('FR 203', '13:15', '14:35'),
        ('FR 289', '16:20', '17:40'), ('FR 205', '17:30', '18:50'),
        ('FR 291', '20:00', '21:20'), ('FR 210', '22:00', '23:20'),
    ],
    'DUB-STN': [
        ('FR 30', '06:30', '07:50'), ('FR 272', '08:30', '09:50'),
        ('FR 202', '11:30', '12:50'), ('FR 288', '13:20', '14:40'),
        ('FR 204', '15:45', '17:05'), ('FR 290', '18:05', '19:25'),
        ('FR 211', '20:00', '21:20'), ('FR 292', '22:00', '23:20'),
    ],
}


def haversine(a, b):
    lat1, lon1 = a
    lat2, lon2 = b
    r = 6371.0
    p1, p2 = math.radians(lat1), math.radians(lat2)
    dp = p2 - p1
    dl = math.radians(lon2 - lon1)
    h = math.sin(dp / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dl / 2) ** 2
    return 2 * r * math.asin(math.sqrt(h))


def block_minutes(distance_km):
    # calibrated against real Ryanair block times (STN-DUB 470km = 80min)
    return max(55, int(round(35 + distance_km / 650 * 60)))


def hhmm_add(t, minutes):
    h, m = map(int, t.split(':'))
    total = h * 60 + m + minutes
    return f'{(total // 60) % 24:02d}:{total % 60:02d}'


def build_airports():
    rows = []
    for code, (name, city, country, lat, lon, is_base) in AIRPORTS.items():
        rows.append({
            'code': code, 'name': name, 'city': city, 'country': country,
            'latitude': lat, 'longitude': lon, 'is_base': is_base,
            'image': f'airports/{code.lower()}_desktop.jpg',
        })
    rows.sort(key=lambda r: r['code'])
    return rows


def build_routes(airports):
    by_code = {a['code']: a for a in airports}
    # Realistic network size: trim each base's destination list to its tier.
    tier1 = {'STN', 'DUB', 'LGW', 'MAN', 'BHX'}
    tier2 = {'BRS', 'EDI', 'GLA', 'LPL', 'EMA', 'BFS', 'ORK', 'MAD', 'BCN',
             'ALC', 'AGP', 'CRL', 'BVA', 'MRS', 'BGY', 'CIA'}
    pairs = set()
    for origin, dests in BASES.items():
        limit = 70 if origin in tier1 else (45 if origin in tier2 else 24)
        kept = 0
        for dest in dests:
            if kept >= limit:
                break
            if dest not in by_code or origin not in by_code:
                continue
            pairs.add((origin, dest))
            pairs.add((dest, origin))  # every route is bidirectional
            kept += 1

    # Connect every remaining airport to its nearest base airports so the
    # whole universe is reachable (small airports feed the nearest hubs).
    base_codes = [c for c in by_code if by_code[c]['is_base']]
    for code, a in by_code.items():
        if any(o == code or d == code for o, d in pairs):
            continue
        near = sorted(base_codes,
                      key=lambda b: haversine((a['latitude'], a['longitude']),
                                              (by_code[b]['latitude'],
                                               by_code[b]['longitude'])))
        for b in near[:3]:
            pairs.add((code, b))
            pairs.add((b, code))

    rng = random.Random(RNG_SEED)
    routes = []
    taken_numbers = {num.strip('FR ') and int(num.split()[1])
                     for legs in REAL_STN_DUB.values()
                     for num, _, _ in legs}

    def next_number(base):
        while True:
            n = rng.randint(1, 9999)
            if n not in taken_numbers:
                taken_numbers.add(n)
                return n
            base += 1
            if base > 9999:
                base = 1
            if base not in taken_numbers:
                taken_numbers.add(base)
                return base
    for origin, dest in sorted(pairs):
        if origin == dest:
            continue
        a, b = by_code[origin], by_code[dest]
        dist = round(haversine((a['latitude'], a['longitude']),
                               (b['latitude'], b['longitude'])))
        minutes = block_minutes(dist)
        key = f'{origin}-{dest}'
        # daily frequency: real pair keeps 8; else 1-6 by route hash
        if key in REAL_STN_DUB:
            freq = len(REAL_STN_DUB[key])
        elif dist < 1500:
            freq = rng.randint(1, 3)
        else:
            freq = rng.randint(1, 2)
        schedules = []
        if key in REAL_STN_DUB:
            for num, dep, arr in REAL_STN_DUB[key]:
                schedules.append({'flight_number': num, 'departure': dep,
                                  'arrival': arr, 'days': list(range(1, 8))})
        else:
            base_num = next_number(rng.randint(100, 9800))
            # dep times spread across the day
            start = rng.choice([6, 7, 8, 9, 10, 11, 13, 14, 15, 16, 17, 18, 19, 20, 21])
            for i in range(freq):
                dep_h = (start + i * 3) % 24
                if dep_h < 6:
                    dep_h += 6
                dep = f'{dep_h:02d}:{rng.choice(["00", "05", "10", "15", "20", "25", "30", "35", "40", "45", "50", "55"])}'
                num = f'FR {next_number(base_num + i)}'
                arr = hhmm_add(dep, minutes)
                days = sorted(rng.sample(range(1, 8), rng.randint(5, 7)))
                schedules.append({'flight_number': num, 'departure': dep,
                                  'arrival': arr, 'days': days})
        # base price by distance band (GBP, one-way Basic)
        if dist < 600:
            base = rng.choice([9.99, 12.99, 14.99, 15.99, 17.99, 19.99, 21.99])
        elif dist < 1200:
            base = rng.choice([19.99, 21.99, 24.99, 26.99, 29.99, 32.99])
        elif dist < 2500:
            base = rng.choice([29.99, 34.99, 39.99, 44.99, 49.99, 59.99])
        else:
            base = rng.choice([39.99, 49.99, 59.99, 69.99, 79.99])
        routes.append({
            'origin': origin, 'destination': dest,
            'distance_km': dist, 'duration_minutes': minutes,
            'base_price': base, 'schedules': schedules,
        })
    return routes


CONTENTS = {
    'mirror_today': '2026-09-24',
    'site_market': 'gb/en',
    'currency': 'GBP',
    'currency_symbol': '£',
    # Fee table (captured from the live bags/seats/extras steps + help pages)
    'fees': [
        {'item': 'Priority & 2 Cabin Bags', 'online': 'from £16.00',
         'airport': '£/€25', 'note': 'per person, per flight'},
        {'item': '10kg Check-in Bag', 'online': '£11.49', 'airport': '£15.99',
         'note': 'per flight, 1 per passenger'},
        {'item': '20kg Check-in Bag', 'online': '£25.49', 'airport': '£50.00',
         'note': 'per flight, up to 3 per passenger'},
        {'item': '23kg Check-in Bag', 'online': '£34.49', 'airport': '£68.00',
         'note': 'per flight, 1 per passenger'},
        {'item': 'Airport check-in', 'online': 'free (online)',
         'airport': '£55', 'note': 'per passenger'},
        {'item': 'Boarding pass re-issue', 'online': 'free (in app)',
         'airport': '£20', 'note': 'per passenger'},
        {'item': 'Name change', 'online': '£/€115', 'airport': '£/€115',
         'note': 'per booking'},
        {'item': 'Date change (online)', 'online': '£/€45 per passenger',
         'airport': 'fare difference applies', 'note': 'per flight'},
        {'item': 'Security Fast Track (STN)', 'online': '£8.49', 'airport': '—',
         'note': 'per person'},
        {'item': 'Security Fast Track (DUB)', 'online': '£12.03', 'airport': '—',
         'note': 'per person'},
    ],
    'fares': [
        {'key': 'basic', 'name': 'Basic', 'tagline': 'Travel light',
         'features': ['1 small bag (must fit under the seat in front)']},
        {'key': 'regular', 'name': 'Regular',
         'tagline': 'Choose your seat and 10kg bag on board',
         'features': ['Reserved seat (specific rows available)',
                      '10kg overhead locker bag', 'Priority boarding']},
        {'key': 'plus', 'name': 'Plus',
         'tagline': 'Choose your seat and a 20kg checked in bag',
         'features': ['Reserved seat (specific rows available)',
                      '20kg check-in bag', 'Priority boarding',
                      'Speed through security (Fast Track)']},
        {'key': 'flexi_plus', 'name': 'Flexi Plus',
         'tagline': 'Our most flexible bundle',
         'features': ['Any seat on the plane', 'Priority boarding',
                      '20kg check-in bag', 'Speed through security (Fast Track)',
                      'Change flights with no fees (pay fare difference only)',
                      'Move to an earlier flight (same day)']},
    ],
    'seat_bands': [
        {'label': 'XL', 'sub': 'Extra legroom up front', 'rows': '1 - 2',
         'price': 21.50},
        {'label': 'GET OFF QUICK', 'sub': 'Get off quick', 'rows': '2 - 6',
         'price': 14.00},
        {'label': 'BEST VALUE UP FRONT', 'sub': 'Best value up front',
         'rows': '7 - 15', 'price': 13.50},
        {'label': 'XL', 'sub': 'Stretch out for less', 'rows': '16 - 17',
         'price': 14.50},
        {'label': 'BEST VALUE AT THE BACK', 'sub': 'Best value at the back',
         'rows': '18 - 33', 'price': 9.50},
    ],
    'bags': {
        'cabin_options': [
            {'key': 'small-bag', 'title': '1 Small Bag only',
             'sub': 'Included with fare', 'price': 0.0,
             'dims': '40 x 30 x 20cm'},
            {'key': 'priority', 'title': 'Priority & 2 Cabin Bags',
             'sub': 'Be the first on board', 'price': 16.0,
             'dims': '40 x 30 x 20cm and 55 x 40 x 20cm'},
        ],
        'checkin_options': [
            {'key': '10kg', 'title': '10kg Check-in Bag',
             'sub': '55 x 40 x 20 cm, 1 per passenger', 'online': 11.49,
             'airport': 15.99},
            {'key': '20kg', 'title': '20kg Check-in Bag',
             'sub': '80 x 120 x 120 cm, up to 3 per passenger', 'online': 25.49,
             'airport': 50.00},
            {'key': '23kg', 'title': '23kg Check-in Bag',
             'sub': '80 x 120 x 120 cm, 1 per passenger', 'online': 34.49,
             'airport': 68.00},
        ],
        'equipment': {'title': 'Sports, music or baby equipment',
                      'from': 15.0},
    },
    'extras': {
        'fast_track': [
            {'airport': 'London Stansted', 'price': 8.49},
            {'airport': 'Dublin', 'price': 12.03},
        ],
        'insurance': [
            {'key': 'standard', 'title': 'STANDARD INSURANCE', 'per_day': 1.46,
             'medical': 'Up to £2,500,000',
             'baggage': 'Up to £1,500', 'cancellation': 'Up to £3,000'},
            {'key': 'plus', 'title': 'INSURANCE PLUS', 'per_day': 1.90,
             'medical': 'Up to £5,000,000 nil excess',
             'baggage': 'Up to £2,000 nil excess',
             'cancellation': 'Up to £5,000 nil excess'},
            {'key': 'annual', 'title': 'ANNUAL STANDARD', 'per_person': 28.18,
             'medical': 'Up to £2,500,000', 'baggage': 'Up to £1,500',
             'cancellation': 'Up to £3,000'},
        ],
        'inflight_credit': {'from': 4.31, 'to': 17.24, 'bonus_pct': 10},
        'sms_updates': 2.99,
    },
    'payment_fee_pct': 2.0,
    'promo_codes': [
        {'code': 'RYANAIR10', 'discount_pct': 10,
         'note': 'Newsletter welcome offer: 10% off the flight fare'},
        {'code': 'FLY20', 'discount_pct': 20,
         'note': 'Flash sale: 20% off the flight fare'},
    ],
    'hero_slides': [
        {'title': 'UK city escapes from £14.99',
         'sub': 'Book by 30 September for travel through December',
         'image': 'home/2026-flights-09-4-sept-uk-tactical-crea-6674-uk-20hero-jpg.jpg',
         'cta': 'Book now', 'href': '/gb/en/cheap-flight-destinations'},
        {'title': 'Winter sun sale',
         'sub': 'Escape the cold: Canaries & Morocco from £19.99',
         'image': 'home/2026-flights-09-25-sept-september-winter-sun-crea-6753-hero-.jpg',
         'cta': 'Book now', 'href': '/gb/en/cheap-flight-destinations'},
        {'title': 'City breaks refreshed',
         'sub': 'Over 240 routes across Europe',
         'image': 'home/2026-flights-09-18-sept-leisure-refresh-crea-6724-hero-gb-cr.jpg',
         'cta': 'Book now', 'href': '/gb/en/cheap-flight-destinations'},
        {'title': 'Gift a great getaway',
         'sub': 'Ryanair gift cards from £25',
         'image': 'home/2026-gift-cards-09-1st-sept-gc-comms-crea6619-gb-gb-crea-661.jpg',
         'cta': 'Buy now', 'href': '/gb/en/lp/gift-cards'},
    ],
    'partner_cards': [
        {'title': 'GIFT CARDS',
         'text': 'Gift a great getaway with a Ryanair Gift Card.',
         'image': 'home/2026-gift-cards-09-1st-sept-gc-comms-crea6619-gb-gb-crea-661.jpg',
         'cta': 'Buy now', 'href': '/gb/en/lp/gift-cards'},
        {'title': 'CHEAP CAR HIRE',
         'text': 'Ryanair connects you to the biggest brands in car hire.',
         'image': 'home/2026-ancillaries-01-25-jan-car-hire-25-off-crea6193-angel-ca.jpg',
         'cta': 'Book now', 'href': '/gb/en/lp/car-hire'},
        {'title': 'HOTELS',
         'text': 'High quality rooms at affordable prices.',
         'image': 'home/2026-ancillaries-09-18-sept-car-hire-up-409-hero-crea-6714-r.jpg',
         'cta': 'Book now', 'href': '/gb/en/lp/hotels'},
        {'title': 'PRIVATE TRANSFERS',
         'text': 'Up to 10% off. Plus, with free cancellation up to 24 hours '
                 'before pick up, you can book with confidence.',
         'image': 'home/2025-ancillaries-04-04-apr-private-transfer-discount-crea548.jpg',
         'cta': 'Book Now', 'href': '/gb/en/lp/private-transfers'},
    ],
    'explore_europe': [
        {'title': 'A city break that just hits different', 'cta': 'Discover Poznan',
         'image': 'home/2026-ja-09-18-sept-poz-mkt-12826-fd-20banner-201600x628-pozn.jpg'},
        {'title': 'Your next trip: Dakhla', 'cta': 'Find out more',
         'image': 'home/2026-ja-07-21-july-morocco-mkt-12756-crea-6540-dahkla-explor.jpg'},
        {'title': 'Toulouse in Southwest France', 'cta': 'Discover',
         'image': 'home/2026-ja-07-24-july-tls-mkt12789-toulouse-1600x628px-jpg.jpg'},
        {'title': 'Meet Wroclaw\u2019s tiny dwarfs', 'cta': 'Fly today',
         'image': 'home/2026-ja-08-05-aug-wro-mkt-12791-wroc-c5-82aw-20-1-png.png'},
        {'title': 'Katowice. So many reasons to fly!', 'cta': 'Plan your trip.',
         'image': 'home/2026-ja-04-20-apr-ktw-mkt-12539-ktw-jpg.jpg'},
        {'title': 'Welcome to the Loire Valley!', 'cta': 'Discover more',
         'image': 'home/2026-ja-01-12-jan-tuf-carousel-mkt-7931-loire-valley-v1-jpg.jpg'},
        {'title': 'Provence, where the sun shines 300 days a year',
         'cta': 'Enjoy Provence',
         'image': 'home/2020-others-mrs-20fd-20updated-jpg.jpg'},
        {'title': 'Unveil the beauty of the Adriatic pearl',
         'cta': 'Explore Dubrovnik Now!',
         'image': 'home/2025-ja-12-22-dec-dbv-mkt-12495-dbv-airport-fd-banner-2-jpg.jpg'},
        {'title': 'Fall in love with Cologne', 'cta': 'VisitK\u00f6ln',
         'image': 'home/2025-ja-04-07-apr-cgn-mkt11920-cgn-20banner-jpg.jpg'},
        {'title': 'Milan and Bergamo', 'cta': 'One step away from BGY',
         'image': 'home/2020-ams-bgy-20fd-202-jpg.jpg'},
        {'title': 'Explore Bergamo\u2019s Citt\u00e0 Alta',
         'cta': 'Plan your visit now',
         'image': 'home/2023-ja-campaigns-04-bgy-carousel-mkt10283-14april-bgy-jpg.jpg'},
        {'title': 'Discover Lake W\u00f6rthersee', 'cta': 'Fly to Klagenfurt',
         'image': 'home/2024-ja-02-klu-carousel-mkt10982-5feb-klu-fdb-jpg.jpg'},
    ],
    'network_stats': [
        {'value': '40', 'label': 'Countries connected'},
        {'value': '82', 'label': 'Bases in Europe and North Africa'},
        {'value': '470', 'label': 'New aircraft', 'new': True},
        {'value': '2,400+', 'label': 'Daily flights'},
        {'value': '19,000', 'label': 'Skilled professionals'},
    ],
    'help_topics': [
        {'slug': 'fees', 'title': 'Fees', 'icon': 'fees',
         'summary': 'The full Ryanair fee table: bags, seats, check-in and '
                    'changes, online vs at the airport.',
         'body': [
             ('h2', 'Online vs airport prices'),
             ('p', 'Ryanair keeps its lowest prices online. Buying at the '
                   'airport or through the call centre always costs more. '
                   'The table below lists the fees that apply to bookings '
                   'made on this website (gb/en market, GBP).'),
             ('table', 'fees'),
             ('h2', 'Card payment processing fee'),
             ('p', 'A card payment processing fee of 2% of the total booking '
                   'value is applied once the card number has been entered. '
                   'The fee is always shown as a separate line in the price '
                   'breakdown before you pay.'),
             ('h2', 'SMS flight updates'),
             ('p', 'Optional SMS flight updates cost £2.99 per booking and '
                   'cover both outbound and return flights.'),
         ]},
        {'slug': 'cabin-bags', 'title': 'Cabin Bag Policy', 'icon': 'bags',
         'summary': 'What you can bring on board: the free small bag, the '
                    '10kg cabin bag and Priority & 2 Cabin Bags.',
         'body': [
             ('h2', '1 small bag - included with every fare'),
             ('p', 'Every passenger can bring one small bag measuring 40 x '
                   '30 x 20cm, which must fit under the seat in front of '
                   'you. No weight limit applies, but it must fit in the '
                   'sizer at the gate.'),
             ('h2', 'Priority & 2 Cabin Bags'),
             ('p', 'Priority Boarding and 2 Cabin Bags (from £16.00 per '
                   'person, per flight) lets you bring a 55 x 40 x 20cm '
                   '10kg bag plus your small bag, board first through the '
                   'priority lane, and guarantee overhead locker space.'),
             ('h2', 'At the gate'),
             ('p', 'Non-priority passengers whose 10kg bag does not fit in '
                   'the sizer must pay the gate bag fee of £/€25 and the '
                   'bag travels in the hold.'),
         ]},
        {'slug': 'checkin-bags', 'title': 'Check-in Bag Options', 'icon': 'bags',
         'summary': '10kg, 20kg and 23kg checked bag prices online versus at '
                    'the airport.',
         'body': [
             ('h2', 'Buy online, save at the airport'),
             ('p', 'A 10kg check-in bag costs £11.49 online or £15.99 at the '
                   'airport. The 20kg check-in bag costs £25.49 online '
                   'versus £50.00 at the airport, and the 23kg bag £34.49 '
                   'online versus £68.00 at the airport. Up to 3 bags of '
                   '20kg may be purchased per passenger per flight.'),
             ('h2', 'Pool your bags'),
             ('p', 'Passengers on the same booking can pool their purchased '
                   'check-in allowance at the bag drop desk.'),
             ('h2', 'Equipment'),
             ('p', 'Sports, music and baby equipment can be added to any '
                   'booking from £15.00 per item per flight.'),
         ]},
        {'slug': 'check-in', 'title': 'Online Check-in & Boarding Passes',
         'icon': 'checkin',
         'summary': 'When check-in opens, how to get your boarding pass, and '
                    'what happens if you have not checked in.',
         'body': [
             ('h2', 'When can I check in?'),
             ('p', 'Customers who have purchased an allocated seat can check '
                   'in online from 60 days before departure until 2 hours '
                   'before the scheduled flight. Customers travelling on a '
                   'randomly allocated seat can check in from 24 hours '
                   'before departure until 2 hours before.'),
             ('h2', 'Boarding passes'),
             ('p', 'Boarding passes are digital: the Ryanair app displays '
                   'the QR code. Paper boarding passes are no longer '
                   'issued at the airport; a re-issued boarding pass costs '
                   '£20 per passenger.'),
             ('h2', 'If you do not check in online'),
             ('p', 'Customers who have not checked in online at least 2 '
                   'hours before departure must pay the airport check-in '
                   'fee of £55 per passenger (€30 for flights departing '
                   'Spain, €40 for Austria).'),
         ]},
        {'slug': 'travel-documents', 'title': 'Travel Documents', 'icon': 'docs',
         'summary': 'Passports, national ID cards and entry requirements '
                    'for Ryanair routes.',
         'body': [
             ('h2', 'Which documents do I need?'),
             ('p', 'All passengers must present a valid travel document: a '
                   'machine-readable passport, or a national ID card on '
                   'routes where it is accepted. Your document must match '
                   'the name on the booking exactly.'),
             ('h2', 'UK passport holders travelling to the EU'),
             ('p', 'Your passport must have been issued less than 10 years '
                   'before the date you enter the country and be valid for '
                   'at least 3 months after the day you plan to leave.'),
             ('h2', 'Non-EEA nationals'),
             ('p', 'Non-EEA nationals must travel with a valid passport and '
                   'any visa required for entry. It is your responsibility '
                   'to confirm the entry requirements of every country on '
                   'your booking.'),
         ]},
        {'slug': 'flight-changes', 'title': 'Flight Changes & Name Changes',
         'icon': 'changes',
         'summary': 'How to change a flight date or a passenger name, and '
                    'the fees that apply.',
         'body': [
             ('h2', 'Date changes'),
             ('p', 'You can change the date of any flight up to 2.5 hours '
                   'before departure. The online change fee is £/€45 per '
                   'passenger per flight, plus any fare difference. Flexi '
                   'Plus customers change flights with no change fee and '
                   'only pay the fare difference.'),
             ('h2', 'Name changes'),
             ('p', 'Passenger names can be corrected online up to 2 hours '
                   'before departure. The name change fee is £/€115 per '
                   'booking.'),
             ('h2', 'Same-day moves'),
             ('p', 'Flexi Plus customers may move to an earlier flight on '
                   'the same day at no charge, subject to seat '
                   'availability.'),
         ]},
        {'slug': 'seats', 'title': 'Allocated Seats', 'icon': 'seats',
         'summary': 'How seat selection works, the seat bands on board, and '
                    'random allocation at check-in.',
         'body': [
             ('h2', 'Choose your seat'),
             ('p', 'Seats can be selected during booking or via My bookings '
                   'up to 2 hours before departure. XL rows 1-2 offer the '
                   'most legroom (from £21.50); Get Off Quick rows 2-6 cost '
                   'from £14.00; Best Value Up Front rows 7-15 from '
                   '£13.50; XL rows 16-17 from £14.50; Best Value At The '
                   'Back rows 18-33 from £9.50.'),
             ('h2', 'Random allocation'),
             ('p', 'Customers who do not select a seat are allocated a '
                   'seat at check-in free of charge. Randomly allocated '
                   'seats open at check-in 24 hours before departure and '
                   'may separate groups travelling together.'),
         ]},
        {'slug': 'payment', 'title': 'Payment & Card Fees', 'icon': 'payment',
         'summary': 'Accepted payment methods and the card processing fee.',
         'body': [
             ('h2', 'Accepted payment methods'),
             ('p', 'Ryanair accepts Visa, MasterCard, American Express, '
                   'Diners Club, Discover, UATP and PayPal. Pay by Bank is '
                   'available for eligible UK bank accounts with no card '
                   'processing fee.'),
             ('h2', 'Card processing fee'),
             ('p', 'A fee of 2% of the booking total applies to credit and '
                   'debit card payments. The fee appears in the price '
                   'breakdown after the card number is entered.'),
             ('h2', 'Request an invoice'),
             ('p', 'Business travellers can request an invoice during '
                   'payment instead of paying immediately.'),
         ]},
        {'slug': 'refunds', 'title': 'Refunds & Compensation', 'icon': 'refunds',
         'summary': 'Refund timelines, EU261 compensation for disruption, '
                    'and the Refund Hub.',
         'body': [
             ('h2', 'Refund timelines'),
             ('p', 'Approved refunds are processed within 7 working days '
                   'back to the original payment method. It can take up to '
                   '10 working days for the amount to appear on your '
                   'statement.'),
             ('h2', 'Disrupted flights (EU261)'),
             ('p', 'If your flight is cancelled you can choose between a '
                   'full refund and a free move to the next available '
                   'flight. Depending on the notice given and the '
                   'rerouting offered, compensation of £/€250-£/€400 per '
                   'passenger may apply for flights under 1,500km.'),
             ('h2', 'Refund application'),
             ('p', 'Refund requests are submitted through the Refund Hub '
                   'with the booking reference and the email address used '
                   'at booking.'),
         ]},
        {'slug': 'special-assistance', 'title': 'Special Assistance',
         'icon': 'assistance',
         'summary': 'Requesting assistance for reduced-mobility passengers '
                    'and medical conditions.',
         'body': [
             ('h2', 'How to request assistance'),
             ('p', 'Assistance can be requested free of charge up to 2 '
                   'hours before departure through the special assistance '
                   'form or at the airport assistance desk. Please arrive '
                   'at the meeting point at least 30 minutes before '
                   'departure.'),
             ('h2', 'Medical conditions and equipment'),
             ('p', 'Passengers with medical conditions should carry a '
                   'medical certificate. Medical equipment up to 2 items '
                   'travels free of charge in addition to your cabin '
                   'allowance.'),
         ]},
        {'slug': 'children', 'title': 'Children & Infants', 'icon': 'children',
         'summary': 'Fares, baggage and seating rules for infants, children '
                    'and teens travelling with adults.',
         'body': [
             ('h2', 'Infants (under 2)'),
             ('p', 'Infants travel on an adult\u2019s lap for a fixed '
                   '£/€25 fee per flight. Infants do not receive a cabin '
                   'bag allowance but a 5kg bag of baby items may be '
                   'checked in free of charge.'),
             ('h2', 'Children (2-11) and teens (12-15)'),
             ('p', 'Children must be accompanied by an adult aged 16 or '
                   'over. Teens may travel alone with a signed parental '
                   'consent form presented at check-in.'),
             ('h2', 'Family seating'),
             ('p', 'Adults travelling with children under 12 are assigned '
                   'seats together with at least one child when they check '
                   'in, even without a paid seat selection.'),
         ]},
        {'slug': 'fast-track', 'title': 'Security Fast Track', 'icon': 'fasttrack',
         'summary': 'Skip the security queue at participating airports.',
         'body': [
             ('h2', 'What is Fast Track?'),
             ('p', 'Security Fast Track gives you access to a dedicated '
                   'security lane with shorter queues. At London Stansted '
                   'it costs £8.49 per person and at Dublin £12.03 per '
                   'person. Fast Track can be added during booking or via '
                   'My bookings up to 2 hours before departure.'),
             ('h2', 'Included with some fares'),
             ('p', 'Fast Track is included with the Plus and Flexi Plus '
                   'fares at airports where the service operates.'),
         ]},
        {'slug': 'priority-boarding', 'title': 'Priority Boarding',
         'icon': 'priority',
         'summary': 'Board first and guarantee overhead locker space.',
         'body': [
             ('h2', 'Priority Boarding'),
             ('p', 'Priority Boarding lets you board the aircraft first '
                   'through the dedicated priority lane. It is sold '
                   'together with the 10kg cabin bag as Priority & 2 Cabin '
                   'Bags from £16.00 per person, per flight, and is '
                   'included with Regular, Plus and Flexi Plus fares.'),
         ]},
        {'slug': 'group-travel', 'title': 'Group Travel', 'icon': 'groups',
         'summary': 'Discounted fares for groups of 15 or more.',
         'body': [
             ('h2', 'Groups of 15+'),
             ('p', 'Groups of 15 or more passengers can request a '
                   'discounted group fare through the group travel form. '
                   'Group bookings include name flexibility up to 2 hours '
                   'before departure and a dedicated support team.'),
         ]},
        {'slug': 'promo-codes', 'title': 'Promo Codes & Newsletter',
         'icon': 'promo',
         'summary': 'How to apply a promo code when searching and what the '
                    'newsletter welcome offer includes.',
         'body': [
             ('h2', 'Applying a promo code'),
             ('p', 'Enter the code in the promo code field of the flight '
                   'search widget before you search. The discount is '
                   'applied to the flight fare for every passenger on the '
                   'booking and is reflected in the price breakdown. Only '
                   'one promo code can be used per booking.'),
             ('h2', 'Newsletter welcome offer'),
             ('p', 'New newsletter subscribers receive the welcome code '
                   'RYANAIR10, which gives 10% off the flight fare. Flash '
                   'sale codes are published on the homepage banner from '
                   'time to time.'),
             ('h2', 'Terms'),
             ('p', 'Promo codes apply to the flight fare only; seats, bags '
                   'and extras are charged at the standard prices. Codes '
                   'cannot be applied to bookings already made.'),
         ]},
        {'slug': 'inflight', 'title': 'On Board', 'icon': 'inflight',
         'summary': 'Inflight menu, pre-paid credit and using the app on '
                    'board.',
         'body': [
             ('h2', 'Inflight menu'),
             ('p', 'A full food and drink menu is available on every '
                   'flight, including hot drinks, snacks and sandwiches. '
                   'Pre-paid inflight credit gives you 10% extra credit '
                   'free: buy £4.31 - £17.24 of credit and use it on any '
                   'inflight purchase.'),
             ('h2', 'Inflight receipts'),
             ('p', 'Receipts for onboard purchases are issued through the '
                   'inflight receipts portal using your seat number and '
                   'flight date.'),
         ]},
        {'slug': 'general-terms-carriage',
         'title': 'General terms & conditions of carriage',
         'icon': 'legal',
         'summary': 'The conditions of carriage that apply to every '
                    'booking: your contract, check-in deadlines, baggage, '
                    'delays and your rights.',
         'body': [
             ('h2', 'Your contract of carriage'),
             ('p', 'Your booking confirmation together with these general '
                   'terms & conditions of carriage (GTCC) forms the '
                   'contract between you and Ryanair for the flights '
                   'shown on it. By completing a booking you accept these '
                   'conditions on behalf of every passenger in the '
                   'booking.'),
             ('h2', 'Check-in and boarding'),
             ('p', 'Online check-in opens 60 days before departure for '
                   'customers who purchased an allocated seat and 24 '
                   'hours before departure for customers travelling on a '
                   'randomly allocated seat, and always closes 2 hours '
                   'before the scheduled departure. Boarding closes 30 '
                   'minutes before departure and the gate is not reopened '
                   'for late passengers.'),
             ('h2', 'Baggage'),
             ('p', 'Every fare includes a free small personal bag that '
                   'must fit under the seat in front of you. Priority & 2 '
                   'Cabin Bags customers may bring a 10kg cabin bag and a '
                   'small bag on board. Checked bags of 10kg, 20kg and '
                   '23kg can be added per passenger per flight; airport '
                   'bag drop opens 2 hours before departure.'),
             ('h2', 'Delays, cancellations and refunds'),
             ('p', 'If a flight is cancelled you can choose between a full '
                   'refund and a free move to the next available flight; '
                   'EU261 compensation may also apply depending on the '
                   'notice given. See the Refunds article for refund '
                   'timelines and the EU261 rules that apply to disrupted '
                   'flights.'),
             ('h2', 'Changes and names'),
             ('p', 'Flight dates can be changed up to 2.5 hours before '
                   'departure and passenger names up to 2 hours before '
                   'departure. The change fees and the fare difference are '
                   'shown before you confirm the change; Flexi Plus '
                   'customers change flights with no change fee.'),
         ]},
    ],
    'guides': [
        {'code': 'DUB', 'city': 'dublin',
         'must_reads': [
             '12 Great Mid-Term Destinations for 12\u2019s and under',
             'Classic Movie Tour of Europe - 17 Places You Can See in Real Life',
             'The Top 13 Scariest Places in Europe',
             'Where to go for a winter hen party'],
         'intro': 'From the Book of Kells to the live music in Temple Bar, '
                  'Dublin packs centuries of history into a walkable city '
                  'centre. The Airlink and Dublin Bus connect the airport '
                  'to the city in about 30 minutes.'},
        {'code': 'ALC', 'city': 'alicante',
         'must_reads': [
             'Castillo de Santa Barbara: Alicante\u2019s hilltop fortress',
             'Girona: the day trip from Barcelona that locals keep quiet',
             'Shutterstock destinations: what the Costa Blanca really looks like',
             'Other country, other coast: the Amalfi side of Italy'],
         'intro': 'Alicante is the Costa Blanca\u2019s capital of sun: '
                  'seven hours of sunshine even in winter, a castle on a '
                  'hill and a postiguet beach ten minutes from the bus '
                  'station.'},
        {'code': 'AGP', 'city': 'malaga',
         'must_reads': [
             'EUR SKI: the Sierra Nevada day trip from Malaga',
             'Visit Malaga: the old town in a weekend',
             'Semana Santa: Malaga\u2019s Holy Week processions',
             'Malaga Club Atletico: matchday guide'],
         'intro': 'Malaga has grown from a beach stopover into Andalusia\u2019s '
                  'culture capital: Picasso\u2019s birthplace, the '
                  'Alcazaba and a tapas scene that runs late into the '
                  'night.'},
        {'code': 'BCN', 'city': 'barcelona',
         'must_reads': [
             'Lanzarote: the Canary Island that isn\u2019t what you think',
             'Barcelona beyond Gaudi: five neighbourhoods to get lost in',
             'Verona: new places, an old romance',
             'City breaks that hit different in autumn'],
         'intro': 'Barcelona needs no introduction: Gaudi\u2019s '
                  'spires, the Gothic Quarter and a beach at the end of '
                  'the metro line. Fly to El Prat or Girona for the Costa '
                  'Brava.'},
        {'code': 'BVA', 'city': 'paris',
         'must_reads': [
             'Paris in the rain: a photographer\u2019s guide',
             '12 places in Europe you have seen in films',
             'Where to eat within 10 minutes of every major station',
             'Christmas markets that open before December'],
         'intro': 'The City of Light rewards every kind of traveller: '
                  'museum queues at opening time, riverside bouquinistes '
                  'and the 15:00 pause-cafe. Beauvais airport connects '
                  'to Paris by a 75-minute shuttle bus.'},
    ],
}


def main():
    airports = build_airports()
    routes = build_routes(airports)
    root = HERE.parent
    (root / 'source_data_airports.json').write_text(
        json.dumps({'snapshot_date': '2026-09-24', 'airports': airports},
                   ensure_ascii=False, indent=1) + '\n', encoding='utf-8')
    (root / 'source_data_routes.json').write_text(
        json.dumps({'snapshot_date': '2026-09-24', 'routes': routes},
                   ensure_ascii=False, indent=1) + '\n', encoding='utf-8')
    (root / 'source_data_content.json').write_text(
        json.dumps(CONTENTS, ensure_ascii=False, indent=1) + '\n',
        encoding='utf-8')
    print(f'airports={len(airports)} routes={len(routes)} '
          f'schedules={sum(len(r["schedules"]) for r in routes)}')


if __name__ == '__main__':
    main()
