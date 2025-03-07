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
    try:
        # Rensa text och ta bort kodblock-markörer
        text = text.strip().replace('```json', '').replace('```', '').strip()
        
        # Ta bort extra slutande måsvinge
        text = text.replace('}]}', ']}')
        
        print("DEBUG: Rensat text:", text)

        # Försök parsa JSON
        parsed = json.loads(text)
        
        # Validera struktur
        if (isinstance(parsed, dict) and 
            'horses' in parsed and 
            all('name' in h and 'start_number' in h and 'calculated_percentage' in h for h in parsed['horses'])):
            
            # Normalisera procentvärden
            total_percentage = sum(h['calculated_percentage'] for h in parsed['horses'])
            
            if abs(total_percentage - 100) > 0.1:
                for h in parsed['horses']:
                    h['calculated_percentage'] *= 100 / total_percentage
            
            return parsed

    except json.JSONDecodeError as e:
        print(f"JSON-tolkningsfel: {e}")
        
        # Fallback: skapa standardsvar
        return {
            "horses": [
                {
                    "name": horse['name'], 
                    "start_number": horse['start_number'], 
                    "calculated_percentage": 100/len(horses_data)
                } 
                for horse in horses_data
            ],
            "analysis_summary": "Kunde inte genomföra fullständig analys"
        }
    except Exception as e:
        print(f"Oväntat fel vid JSON-extrahering: {e}")
        
        # Sista fallback
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
        prompt = f"""Analysera och fördela EXAKT 100% mellan {len(horses_data)} hästar.

KRITISKA KRAV:
- Fullständig, giltig JSON
- Exakt {len(horses_data)} hästar
- Varje häst MÅSTE ha:
  * Namn
  * Startnummer
  * Procentsats
- Procentsatser MÅSTE summera till 100% exakt
- INGEN ofullständig data
- INGEN extra text utanför JSON

STRIKT FORMAT:
{{
    "horses": [
        {{
            "name": "Hästnamn",
            "start_number": nummer,
            "calculated_percentage": procent (0-100)
        }}
    ],
    "analysis_summary": "Mycket kort analys"
}}

Hästdata:
{json.dumps(horses_data, indent=2)}"""
        
        response = client.chat.completions.create(
            model="gpt-3.5-turbo", 
            messages=[
                {"role": "system", "content": "Du MÅSTE returnera perfekt JSON för travhästanalys"},
                {"role": "user", "content": prompt}
            ],
            temperature=0.7,
            max_tokens=800
        )
        
        # Hämta det fullständiga svaret
        full_response = response.choices[0].message.content.strip()
        
        # Skapa debug-katalog om den inte finns
        debug_dir = os.path.expanduser('~/Desktop/travanalys_debug')
        os.makedirs(debug_dir, exist_ok=True)
        
        # Skapa filnamn med tidsstämpel
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        debug_file = os.path.join(debug_dir, f'ai_debug_{timestamp}.txt')
        
        # Skriv all debug-information till samma fil
        try:
            with open(debug_file, 'w', encoding='utf-8') as f:
                # Skriv hästdata
                f.write("HÄSTDATA:\n")
                f.write(json.dumps(horses_data, indent=2) + "\n\n")
                
                # Skriv prompt
                f.write("PROMPT:\n")
                f.write(prompt + "\n\n")
                
                # Skriv fullständigt AI-svar
                f.write("FULLSTÄNDIGT AI-SVAR:\n")
                f.write(full_response + "\n\n")
            
            print(f"Debug-information sparad i: {debug_file}")
        
        except Exception as e:
            print(f"Kunde inte spara debug-fil: {e}")
        
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