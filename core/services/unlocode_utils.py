import csv
from typing import List, Dict
import requests
AIRPORTS_FILE = 'core/static/csv/airports.dat'
PUERTOS_FILE = "core/static/csv/2024-2 UNLOCODE CodeListPart1.csv"  # Cambia al path correcto

import csv
import os

def fetch_unlocode_csv():
    """
    Lee el archivo de aeropuertos desde core/static/csv/airports.dat
    """
    base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))  # Subir desde core/services
    ruta_archivo = os.path.join(base_dir, "static", "csv", "airports.dat")

    ubicaciones = []

    with open(ruta_archivo, encoding="utf-8") as file:
        reader = csv.reader(file)

        for row in reader:
            if len(row) < 8:
                continue

            country = row[3].strip()
            city = row[2].strip()
            name = row[1].strip()
            iata = row[4].strip()
            icao = row[5].strip()
            latitude = row[6].strip()
            longitude = row[7].strip()

            ubicaciones.append({
                "country": country,
                "city": city,
                "name": name,
                "iata": iata,
                "icao": icao,
                "latitude": latitude,
                "longitude": longitude
            })

    return ubicaciones


def pais_a_codigo(pais_nombre):
    """
    Devuelve el código ISO 2 letras para un país dado.
    """
    response = requests.get("https://restcountries.com/v3.1/name/" + pais_nombre)
    if response.ok:
        data = response.json()
        return data[0]["cca2"].upper()  # Ej: "CL"
    return None
def fetch_airports() -> List[Dict[str, str]]:
    """
    Lee el archivo airports.dat y devuelve una lista de aeropuertos.
    """
    airports: List[Dict[str, str]] = []
    with open(AIRPORTS_FILE, mode='r', encoding='utf-8') as f:
        reader = csv.reader(f)
        for row in reader:
            # Solo incluir aeropuertos con código IATA válido
            if row[4] and row[4] != "\\N":
                airports.append({
                    "airport_id": row[0],
                    "name": row[1],
                    "city": row[2],
                    "country": row[3],
                    "iata": row[4],
                    "icao": row[5],
                    "latitude": row[6],
                    "longitude": row[7]
                })
    return airports

def get_airports_by_country(country_name: str) -> List[Dict[str, str]]:
    """
    Filtra los aeropuertos por país.
    """
    all_airports = fetch_airports()
    filtered = [
        a for a in all_airports if a["country"].strip().lower() == country_name.strip().lower()
    ]
    return filtered

def get_ports_by_country(pais_codigo, funcion="1"):
    ubicaciones = []
    base_dir = os.path.dirname(os.path.abspath(__file__))
    csv_path = os.path.join(base_dir, '..', 'static', 'csv', 'flat-ui__data-Wed May 28 2025.csv')

    with open(csv_path, encoding='utf-8') as archivo:
        reader = csv.DictReader(archivo)
        for fila in reader:
            # Filtro por país y función
            if fila["Country"].upper() == pais_codigo.upper() and funcion in fila["Function"]:
                ubicaciones.append({
                    "name": fila["NameWoDiacritics"],
                    "locode": f"{fila['Country']}{fila['Location']}"
                })
    return ubicaciones