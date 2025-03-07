import pandas as pd
import numpy as np
import json
import os
import re
from dotenv import load_dotenv
from openai import OpenAI

# Ladda miljövariabler från .env filen
load_dotenv()

# Konfigurera OpenAI API
client = OpenAI(api_key=os.getenv('OPENAI_API_KEY'))

# Funktioner för filhantering
def list_csv_files(directory="csv"):
    """Lista CSV-filer i en katalog"""
    try:
        if not os.path.exists(directory):
            os.makedirs(directory)
        return [f for f in os.listdir(directory) if f.lower().endswith('.csv')]
    except Exception as e:
        print(f"Fel vid listning av filer: {e}")
        return []

def list_json_files(directory="json"):
    """Lista JSON-filer i en katalog"""
    try:
        if not os.path.exists(directory):
            os.makedirs(directory)
        return [f for f in os.listdir(directory) if f.lower().endswith('.json')]
    except Exception as e:
        print(f"Fel vid listning av JSON-filer: {e}")
        return []

def select_csv_file():
    """Låt användaren välja en CSV-fil"""
    csv_files = list_csv_files()
    
    if not csv_files:
        print("Inga CSV-filer hittades. Lägg till filer och försök igen.")
        return None
    
    print("\nTillgängliga CSV-filer:")
    for i, file in enumerate(csv_files, 1):
        print(f"{i}. {file}")
    
    try:
        choice = int(input("\nVälj filnummer: "))
        if 1 <= choice <= len(csv_files):
            return os.path.join("csv", csv_files[choice-1])
        else:
            print("Ogiltigt val!")
            return None
    except ValueError:
        print("Ange ett giltigt nummer!")
        return None

def select_json_files():
    """Låt användaren välja JSON-filer för spelprocent och banstatistik"""
    print("\n===== VÄLJ JSON-FILER =====")
    
    json_files = list_json_files()
    
    if not json_files:
        print("Inga JSON-filer hittades.")
        return None, None
    
    # Separera filer
    spelprocent_files = [f for f in json_files if 'spelprocent' in f.lower()]
    banstatistik_files = [f for f in json_files if 'axevalla' in f.lower()]
    
    # Välj spelprocentfil
    print("\nTillgängliga spelprocentfiler:")
    for i, file in enumerate(spelprocent_files, 1):
        print(f"{i}. {file}")
    
    try:
        spelprocent_choice = int(input("\nVälj spelprocentfil: ")) - 1
        spelprocent_path = os.path.join("json", spelprocent_files[spelprocent_choice])
    except (ValueError, IndexError):
        print("Ogiltigt val!")
        return None, None
    
    # Välj banstatistikfil
    print("\nTillgängliga banstatistikfiler:")
    for i, file in enumerate(banstatistik_files, 1):
        print(f"{i}. {file}")
    
    try:
        banstatistik_choice = int(input("\nVälj banstatistikfil: ")) - 1
        banstatistik_path = os.path.join("json", banstatistik_files[banstatistik_choice])
    except (ValueError, IndexError):
        print("Varning: Ingen banstatistikfil vald.")
        banstatistik_path = None
    
    return spelprocent_path, banstatistik_path

def load_horse_data(race_csv_path, spelprocent_json_path):
    """Läs in hästdata från CSV och JSON"""
    try:
        # Läs CSV-fil
        horses_df = pd.read_csv(race_csv_path)
        
        # Läs spelprocentfil
        with open(spelprocent_json_path, 'r', encoding='utf-8') as f:
            betting_data = json.load(f)
        
        # Bestäm loppnummer
        race_number = determine_race_number(race_csv_path, horses_df)
        
        return horses_df, betting_data, race_number
    
    except Exception as e:
        print(f"Fel vid inläsning av data: {e}")
        return None, None, None

def determine_race_number(race_csv_path, df):
    """Bestäm loppnummer från filnamn eller data"""
    # Försök från filnamn
    filename = os.path.basename(race_csv_path)
    match = re.search(r'Lopp\s*(\d+)', filename, re.IGNORECASE)
    if match:
        return int(match.group(1))
    
    # Fallback
    return 1

def analyze_distance_performance(horse):
    """
    Analysera hästens prestanda på olika distanser
    """
    # Samla distanser från de tre senaste loppen
    distances = [
        horse.get('previous_race_1_distance', 0),
        horse.get('previous_race_2_distance', 0),
        horse.get('previous_race_3_distance', 0)
    ]
    
    # Gruppera resultat per distans
    distance_results = {
        1640: [],  # Korta distansen
        2140: [],  # Mellandistansen
        2640: []   # Långa distansen
    }
    
    # Placeringar för respektive distans
    for i, distance in enumerate(distances, 1):
        # Konvertera till integer och kolla mot närmaste standarddistans
        try:
            distance = int(distance)
            placement = horse.get(f'previous_race_{i}_position', 0)
            
            # Robust hantering av placering
            if pd.isna(placement):
                continue
            
            # Konvertera placering till integer, hantera strängar
            try:
                placement = int(str(placement).replace('d', '10'))
            except (ValueError, TypeError):
                continue
            
            if abs(distance - 1640) <= 100:
                distance_results[1640].append(placement)
            elif abs(distance - 2140) <= 100:
                distance_results[2140].append(placement)
            elif abs(distance - 2640) <= 100:
                distance_results[2640].append(placement)
        except (ValueError, TypeError):
            continue
    
    # Beräkna poäng per distans
    distance_scores = {}
    for dist, placements in distance_results.items():
        if placements:
            # Poängsätt placeringar
            points = []
            for placement in placements:
                if placement == 1:
                    points.append(10)
                elif placement == 2:
                    points.append(8)
                elif placement == 3:
                    points.append(6)
                elif 4 <= placement <= 5:
                    points.append(4)
                else:
                    points.append(1)
            
            # Vägt genomsnitt med senaste loppet viktat tyngre
            if not points:
                distance_scores[dist] = 0
            elif len(points) == 1:
                distance_scores[dist] = points[0]
            elif len(points) == 2:
                distance_scores[dist] = (points[0] * 0.7 + points[1] * 0.3)
            else:
                distance_scores[dist] = (points[0] * 0.5 + points[1] * 0.3 + points[2] * 0.2)
        else:
            distance_scores[dist] = 0
    
    return distance_scores

def calculate_form_score(horse):
    """
    Beräkna formvärde baserat på de tre senaste loppen
    """
    # Samla placeringar
    placements = [
        horse.get('previous_race_1_position', 0),
        horse.get('previous_race_2_position', 0),
        horse.get('previous_race_3_position', 0)
    ]
    
    # Rensa och hantera olika datatyper
    clean_placements = []
    for placement in placements:
        try:
            if pd.isna(placement):
                continue
            placement = int(placement)
            if placement > 0:
                clean_placements.append(placement)
        except (ValueError, TypeError):
            continue
    
    # Om inga placeringar
    if not clean_placements:
        return 5.0  # Neutralt värde
    
    # Poängsätt placeringar med viktning
    points = []
    weights = [0.5, 0.3, 0.2]  # Vikta senaste loppet tyngre
    
    for i, placement in enumerate(clean_placements[:3]):
        weight = weights[i] if i < len(weights) else 0.2
        
        if placement == 1:
            points.append(10 * weight)
        elif placement == 2:
            points.append(8 * weight)
        elif placement == 3:
            points.append(6 * weight)
        elif placement <= 5:
            points.append(4 * weight)
        else:
            points.append(1 * weight)
    
    # Summera poäng
    total_score = sum(points)
    
    # Normalisera till 0-10 skala
    return min(10, max(0, total_score * 2))

def calculate_career_score(horse):
    """
    Beräkna karriärvärde baserat på intjänade pengar och vinstprocent
    """
    # Extrahera vinstprocent
    def extract_win_percentage(career_results):
        if pd.isna(career_results):
            return 0
        
        try:
            # Förväntat format: "X Y-Z" där X är totala starter, Y-Z är vinster-totalresultat
            parts = str(career_results).split()
            if len(parts) >= 2:
                total_starts = int(parts[0])
                wins_part = parts[1].split('-')[0]
                wins = int(wins_part)
                
                if total_starts > 0:
                    return (wins / total_starts) * 100
        except:
            pass
        return 0
    
    # Beräkna vinstprocent
    win_percentage = extract_win_percentage(horse.get('career_results', '0 0-0'))
    
    # Normalisera intjänade pengar
    earnings = horse.get('earnings', 0)
    
    # Viktad poängsättning
    win_score = min(10, win_percentage / 10)  # Normalisera till 0-10
    earnings_score = min(10, (earnings / 1000000) * 10)  # Anta maxvärde 1 miljon
    
    # Kombinera poäng
    return (win_score * 0.7 + earnings_score * 0.3)

def calculate_track_position_score(horse, track_data=None):
    """
    Beräkna poäng baserat på startnummer
    """
    # Standardvärde om ingen banstatistik finns
    if not track_data:
        return 5.0
    
    start_number = horse['start_number']
    
    # Hämta spårstatistik
    try:
        autostart_stats = track_data['spårstatistik']['Axevalla']['autostart']['hög']
        
        # Hitta statistik för detta startnummer
        for stat in autostart_stats:
            if int(stat['spår']) == start_number:
                # Konvertera segerprocent till poäng
                seg_procent = float(stat['segerprocent']['värde'].rstrip('%'))
                return min(10, max(1, seg_procent))
    except:
        pass
    
    # Fallback
    return 5.0

def calculate_betting_percentages(horses_df, betting_data, race_number):
    """
    Beräkna och tilldela spelprocentar från JSON-data
    """
    # Extrahera spelprocent för specifikt lopp
    race_key = f"V75-{race_number}"
    
    # Standardvärde om ingen data finns
    default_percentage = 100 / len(horses_df)
    
    if betting_data and race_key in betting_data:
        betting_percentages = {
            int(horse['number']): horse['percentage'] 
            for horse in betting_data[race_key]['horses']
        }
        
        # Tilldela spelprocent
        horses_df['betting_percentage'] = horses_df['start_number'].map(
            betting_percentages
        ).fillna(default_percentage)
    else:
        # Jämn fördelning om ingen data
        horses_df['betting_percentage'] = default_percentage
    
    return horses_df

def extract_json_safely(text, horses_data):
    """
    Robust JSON-extrahering med flera fallback-metoder
    """
    import re
    import json

    def safe_parse(text):
        """
        Försöker parsa JSON med olika metoder
        """
        # Rensa och förbered text
        text = text.strip()
        
        # Ta bort eventuell text före/efter JSON
        text = re.sub(r'^[^{]*', '', text)
        text = re.sub(r'[^}]*$', '', text)
        
        # Kontrollera och justera JSON
        try:
            # Försök parsa direkt
            parsed = json.loads(text)
            
            # Validera att vi har rätt struktur
            if not isinstance(parsed, dict):
                raise ValueError("Inte ett JSON-objekt")
            
            # Säkerställ att vi har rätt nycklar
            if 'horses' not in parsed or 'analysis_summary' not in parsed:
                raise ValueError("Saknar förväntade nycklar")
            
            return parsed
        except (json.JSONDecodeError, ValueError) as e:
            print(f"JSON-tolkningsfel: {e}")
            
            # Fallback: skapa standardsvar
            return {
                "horses": [
                    {"name": horse['name'], "start_number": horse['start_number'], "calculated_percentage": 100/len(horses_data)} 
                    for horse in horses_data
                ],
                "analysis_summary": "Kunde inte genomföra fullständig analys"
            }

    # Olika metoder att extrahera JSON
    extraction_methods = [
        lambda: safe_parse(text),
        lambda: safe_parse(re.sub(r'```json\n?', '', text).replace('```', '')),
        lambda: safe_parse(re.sub(r'`', '', text))
    ]
    
    # Testa olika extraktionsmetoder
    for method in extraction_methods:
        try:
            result = method()
            if result:
                return result
        except Exception:
            continue
    
    # Sista utvägen - skapa standardsvar
    print("VARNING: Kunde inte extrahera JSON")
    return {
        "horses": [
            {"name": horse['name'], "start_number": horse['start_number'], "calculated_percentage": 100/len(horses_data)} 
            for horse in horses_data
        ],
        "analysis_summary": "Kunde inte genomföra fullständig analys"
    }

def analyze_horse_with_ai(horses_df):
    """
    AI analyserar och rankar hästar baserat på förberedda data
    """
    try:
        # Förbered data för AI
        horses_data = []
        for _, horse in horses_df.iterrows():
            horse_info = {
                "name": horse['name'],
                "start_number": horse['start_number'],
                "form_score": round(horse['form_score'], 2),
                "career_earnings": horse['earnings'],
                "distance_1640_score": round(horse['distance_1640_score'], 2),
                "distance_2140_score": round(horse['distance_2140_score'], 2),
                "distance_2640_score": round(horse['distance_2640_score'], 2),
                "track_position_score": round(horse['track_position_score'], 2),
                "betting_percentage": round(horse['betting_percentage'], 2)
            }
            horses_data.append(horse_info)
        
        # Skapa prompt för AI
        prompt = f"""Analysera följande hästdata och fördela 100% mellan hästarna:

Hästdata:
{json.dumps(horses_data, indent=2)}

INSTRUKTIONER:
1. Returnera EXAKT detta JSON-format:
{{
    "horses": [
        {{
            "name": "Hästnamn",
            "start_number": nummer,
            "calculated_percentage": procent (0-100, summa 100)
        }}
    ],
    "analysis_summary": "Förklaring"
}}

2. Viktning baserad på:
   - Formvärde
   - Karriärresultat
   - Distansprestanda
   - Spårplacering
   - Aktuell spelad procent

3. Summan MÅSTE bli exakt 100
4. Använd decimaler för precision"""
        
        response = client.chat.completions.create(
            model="gpt-3.5-turbo",
            messages=[
                {"role": "system", "content": "Du är en expert på travanalys som gör nyanserade kvantitativa bedömningar."},
                {"role": "user", "content": prompt}
            ],
            temperature=0.7,
            max_tokens=300,
            response_format={"type": "json_object"}
        )
        
        # Hämta och skriv ut det fullständiga svaret
        full_response = response.choices[0].message.content.strip()
        print("\n===== FULLSTÄNDIGT AI-SVAR =====")
        print(full_response)
        print("===== SLUT PÅ AI-SVAR =====\n")
        
        # Använd robust JSON-extrahering
        parsed_response = extract_json_safely(full_response, horses_data)
        
        return parsed_response
    
    except Exception as e:
        print(f"Fel vid AI-analys: {e}")
        
        # Skapa fallback-svar
        return {
            "horses": [
                {
                    "name": horse['name'], 
                    "start_number": horse['start_number'], 
                    "calculated_percentage": 100/len(horses_df)
                } 
                for _, horse in horses_df.iterrows()
            ],
            "analysis_summary": "Kunde inte genomföra fullständig analys"
        }

def extract_json_safely(text, horses_data):
    """
    Robust JSON-extrahering med flera fallback-metoder
    """
    import re
    import json

    def safe_parse(text):
        """
        Försöker parsa JSON med olika metoder
        """
        # Rensa och förbered text
        text = text.strip()
        
        # Ta bort kodblock-markörer
        text = text.replace('```json', '').replace('```', '').strip()
        
        # Mer robust regex för att extrahera hästdata
        horses_match = re.findall(
            r'\{\s*"name":\s*"([^"]+)"\s*,\s*"start_number":\s*(\d+)\s*,\s*"calculated_percentage":\s*(\d+(?:\.\d+)?)\s*\}', 
            text, 
            re.DOTALL
        )
        
        # Om vi hittade data manuellt, skapa JSON
        if horses_match:
            parsed_horses = [
                {
                    "name": horse[0], 
                    "start_number": int(horse[1]), 
                    "calculated_percentage": float(horse[2])
                } 
                for horse in horses_match
            ]
            
            # Normalisera procentvärden
            total_percentage = sum(horse['calculated_percentage'] for horse in parsed_horses)
            
            if abs(total_percentage - 100) > 0.1:
                for horse in parsed_horses:
                    horse['calculated_percentage'] *= 100 / total_percentage
            
            return {
                "horses": parsed_horses,
                "analysis_summary": "AI-analys baserad på hästdata"
            }
        
        # Fallback till standard JSON-parsing
        try:
            # Ta bort ofullständiga rader
            text = re.sub(r'"calculated_percentage":\s*[0-9.]+$', '', text, flags=re.MULTILINE)
            text = re.sub(r'\s*}\s*$', '', text, flags=re.MULTILINE)
            
            # Ta bort eventuell text före/efter JSON
            text = re.sub(r'^[^{]*', '', text)
            text = re.sub(r'[^}]*$', '', text)
            
            # Lägg till stängande hakparentes om den saknas
            if not text.strip().endswith(']}'):
                text = text.rstrip() + ']}}'
            
            print("Rensat text:")
            print(text)
            
            parsed = json.loads(text)
            
            # Validera strukturen
            if not isinstance(parsed, dict):
                raise ValueError("Inte ett JSON-objekt")
            
            # Säkerställ rätt nycklar och normalisera procentvärden
            if 'horses' in parsed:
                # Ta bara med poster som har alla nödvändiga nycklar
                parsed['horses'] = [
                    horse for horse in parsed['horses'] 
                    if all(key in horse for key in ['name', 'start_number', 'calculated_percentage'])
                ]
                
                total_percentage = sum(horse.get('calculated_percentage', 0) for horse in parsed['horses'])
                
                # Justera procentvärden om de inte summerar till 100
                if abs(total_percentage - 100) > 0.1:
                    # Proportionell justering
                    for horse in parsed['horses']:
                        horse['calculated_percentage'] = horse.get('calculated_percentage', 0) * (100 / total_percentage)
                
                return parsed
            
            raise ValueError("Saknar 'horses' nyckel")
        
        except (json.JSONDecodeError, ValueError) as e:
            print(f"JSON-tolkningsfel: {e}")
            
            # Fallback: skapa standardsvar
            return {
                "horses": [
                    {"name": horse['name'], "start_number": horse['start_number'], "calculated_percentage": 100/len(horses_data)} 
                    for horse in horses_data
                ],
                "analysis_summary": "Kunde inte genomföra fullständig analys"
            }

    # Testa extraktionsmetoden
    try:
        result = safe_parse(text)
        if result:
            return result
    except Exception as e:
        print(f"Extraktionsmetod misslyckades: {e}")
    
    # Sista utvägen - skapa standardsvar
    print("VARNING: Kunde inte extrahera JSON")
    return {
        "horses": [
            {"name": horse['name'], "start_number": horse['start_number'], "calculated_percentage": 100/len(horses_data)} 
            for horse in horses_data
        ],
        "analysis_summary": "Kunde inte genomföra fullständig analys"
    }

def compare_ai_ranking_with_betting_percentages(ai_ranking, horses_df):
    """
    Jämför AI:ns ranking med faktiska spelade procenten
    """
    print("\n=== JÄMFÖRELSE: AI-RANKING MOT SPELAD PROCENT ===")
    
    # Skapa dictionary för enkel sökning
    betting_percentages = {
        horse['start_number']: horse['betting_percentage'] 
        for _, horse in horses_df.iterrows()
    }
    
    # Sortera hästar efter AI:ns ranking
    sorted_horses = sorted(
        ai_ranking['horses'], 
        key=lambda x: x.get('calculated_percentage', 0), 
        reverse=True
    )
    
    # Analysera varje häst
    for horse in sorted_horses:
        start_number = horse['start_number']
        ai_percentage = horse.get('calculated_percentage', 0)
        actual_percentage = betting_percentages.get(start_number, 0)
        
        # Beräkna avvikelse
        deviation = ai_percentage - actual_percentage
        
        print(f"\nHäst {start_number}:")
        print(f"  Namn: {horse['name']}")
        print(f"  AI-ranking: {ai_percentage:.1f}%")
        print(f"  Faktisk spelad: {actual_percentage:.1f}%")
        print(f"  Avvikelse: {deviation:.1f}%")
        print(f"  Status: {'Överspelad' if deviation > 1 else 'Underspelad' if deviation < -1 else 'Normal'}")
    
    # Skriv ut AI:ns övergripande analys
    print("\nAI:ns analyssammanfattning:")
    print(ai_ranking.get('analysis_summary', 'Ingen övergripande analys tillgänglig'))

def analyze_horse_with_ai(horses_df):
    """
    AI analyserar och rankar hästar baserat på förberedda data
    """
    try:
        # Förbered data för AI
        horses_data = []
        for _, horse in horses_df.iterrows():
            horse_info = {
                "name": horse['name'],
                "start_number": horse['start_number'],
                "form_score": round(horse['form_score'], 2),
                "career_earnings": horse['earnings'],
                "distance_1640_score": round(horse['distance_1640_score'], 2),
                "distance_2140_score": round(horse['distance_2140_score'], 2),
                "distance_2640_score": round(horse['distance_2640_score'], 2),
                "track_position_score": round(horse['track_position_score'], 2),
                "betting_percentage": round(horse['betting_percentage'], 2)
            }
            horses_data.append(horse_info)
        
        # Skapa prompt för AI
        prompt = f"""Analysera och fördela exakt 100% mellan dessa hästar:

Hästdata:
{json.dumps(horses_data, indent=2)}

VIKTIGT:
- Returnera JSON med "horses" lista
- Varje häst får procentsats
- Summan MÅSTE bli 100%
- Basera på: form, karriär, distans, spårplacering

JSON-FORMAT:
{{
    "horses": [
        {{
            "name": "Hästnamn",
            "start_number": nummer,
            "calculated_percentage": procent (0-100)
        }}
    ],
    "analysis_summary": "Förklaring"
}}"""
        
        response = client.chat.completions.create(
            model="gpt-3.5-turbo",
            messages=[
                {"role": "system", "content": "Du är en expert på travanalys som gör kvantitativa bedömningar."},
                {"role": "user", "content": prompt}
            ],
            temperature=0.7,
            max_tokens=300
        )
        
        # Hämta och skriv ut det fullständiga svaret
        full_response = response.choices[0].message.content.strip()
        print("\n===== FULLSTÄNDIGT AI-SVAR =====")
        print(full_response)
        print("===== SLUT PÅ AI-SVAR =====\n")
        
        # Använd robust JSON-extrahering
        parsed_response = extract_json_safely(full_response, horses_data)
        
        return parsed_response
    
    except Exception as e:
        print(f"Fel vid AI-analys: {e}")
        
        # Skapa fallback-svar
        return {
            "horses": [
                {
                    "name": horse['name'], 
                    "start_number": horse['start_number'], 
                    "calculated_percentage": 100/len(horses_df)
                } 
                for _, horse in horses_df.iterrows()
            ],
            "analysis_summary": "Kunde inte genomföra fullständig analys"
        }

def analyze_race(race_csv_path, spelprocent_json_path, banstatistik_json_path=None):
    """
    Huvudfunktion för att analysera ett lopp
    """
    # Läs in data
    horses_df, betting_data, race_number = load_horse_data(race_csv_path, spelprocent_json_path)
    
    # Läs in banstatistik om tillgänglig
    track_data = None
    if banstatistik_json_path and os.path.exists(banstatistik_json_path):
        with open(banstatistik_json_path, 'r', encoding='utf-8') as f:
            track_data = json.load(f)
    
    if horses_df is None:
        print("Kunde inte läsa in hästdata.")
        return None
    
    # Beräkna och sortera efter spelvärde
    result_df = calculate_betting_value(horses_df, betting_data, race_number, track_data)
    
    # AI-ranking
    ai_ranking = analyze_horse_with_ai(result_df)
    
    # Jämför AI-ranking med spelade procent
    if ai_ranking:
        compare_ai_ranking_with_betting_percentages(ai_ranking, result_df)
    
    return result_df

def calculate_betting_value(horses_df, betting_data, race_number, track_data=None):
    """
    Beräkna spelvärde för hästar
    """
    # Beräkna distanspoäng
    def extract_distance_score(row, target_distance):
        return row['distance_performance'].get(target_distance, 0)
    
    # Lägg till distansanalys
    horses_df['distance_performance'] = horses_df.apply(analyze_distance_performance, axis=1)
    horses_df['distance_1640_score'] = horses_df.apply(lambda row: extract_distance_score(row, 1640), axis=1)
    horses_df['distance_2140_score'] = horses_df.apply(lambda row: extract_distance_score(row, 2140), axis=1)
    horses_df['distance_2640_score'] = horses_df.apply(lambda row: extract_distance_score(row, 2640), axis=1)
    
    # Beräkna formvärde
    horses_df['form_score'] = horses_df.apply(calculate_form_score, axis=1)
    
    # Beräkna karriärvärde
    horses_df['career_score'] = horses_df.apply(calculate_career_score, axis=1)
    
    # Beräkna spårplaceringspoäng
    horses_df['track_position_score'] = horses_df.apply(
        lambda row: calculate_track_position_score(row, track_data), 
        axis=1
    )
    
    # Lägg till spelprocentar
    horses_df = calculate_betting_percentages(horses_df, betting_data, race_number)
    
    # Beräkna totalvärde
    horses_df['total_score'] = (
        horses_df['form_score'] * 0.3 +
        horses_df['career_score'] * 0.2 +
        horses_df['distance_1640_score'] * 0.1 +
        horses_df['distance_2140_score'] * 0.1 +
        horses_df['distance_2640_score'] * 0.1 +
        horses_df['track_position_score'] * 0.2
    )
    
    # Sortera efter totalvärde
    result_df = horses_df.sort_values('total_score', ascending=False)
    
    return result_df

# Huvudprogram
def main():
    """
    Huvudprogram för V75 Spelvärdesanalys
    """
    print("===== V75 SPELVÄRDESANALYS =====")
    print("En app för att hitta bästa värdespel i V75")
    
    while True:
        try:
            # Välj CSV-fil
            csv_path = select_csv_file()
            if not csv_path:
                continue
            
            # Välj JSON-filer
            spelprocent_path, banstatistik_path = select_json_files()
            
            if not spelprocent_path:
                continue
            
            # Analysera loppet
            result = analyze_race(csv_path, spelprocent_path, banstatistik_path)
            
        except Exception as e:
            print(f"Ett oväntat fel inträffade: {e}")
        
        # Fråga om fortsatt analys
        continue_analysis = input("\nVill du analysera ett annat lopp? (j/n): ").lower()
        if continue_analysis != 'j':
            break
    
    print("\nTack för att du använder V75 Spelvärdesanalys!")

# Säkerställ att programmet bara körs när det startas direkt
if __name__ == "__main__":
    main()