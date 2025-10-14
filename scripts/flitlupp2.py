import requests
import time
from collections import defaultdict
from datetime import datetime

def get_user_contributions(username, lang="sv", startdate=None, enddate=None):
    """Hämta alla bidrag för en användare från Wikipedia."""
    base_url = f"https://{lang}.wikipedia.org/w/api.php"
    
    headers = {
        "User-Agent": "WikipediaContribAnalyzer/1.0 (Educational tool for contribution analysis)"
    }
    
    params = {
        "action": "query",
        "list": "usercontribs",
        "ucuser": username,
        "ucprop": "title|sizediff|flags|ids|timestamp",
        "uclimit": "500",
        "format": "json",
        "formatversion": "2"
    }
    
    # Wikipedia API: ucstart = börja här (nyare), ucend = sluta här (äldre)
    # För att få edits mellan startdate och enddate:
    # ucstart = enddate (börja från slutdatum, går bakåt)
    # ucend = startdate (sluta vid startdatum)
    if enddate:
        params["ucstart"] = f"{enddate}T23:59:59Z"
    if startdate:
        params["ucend"] = f"{startdate}T00:00:00Z"
    
    contributions = []
    
    while True:
        try:
            response = requests.get(base_url, params=params, headers=headers, timeout=30)
            response.raise_for_status()
            
            data = response.json()
            
            if "error" in data:
                print(f"Fel från API: {data['error'].get('info', 'Okänt fel')}")
                break
            
            if "query" in data and "usercontribs" in data["query"]:
                contributions.extend(data["query"]["usercontribs"])
            
            if "continue" in data:
                params["uccontinue"] = data["continue"]["uccontinue"]
                time.sleep(0.1)
            else:
                break
                
        except requests.exceptions.RequestException as e:
            print(f"Nätverksfel: {e}")
            break
        except ValueError as e:
            print(f"JSON-parsningsfel: {e}")
            break
    
    print(f"  → API returnerade {len(contributions)} bidrag för perioden")
    return contributions

def analyze_contributions(username, lang="sv", startdate=None, enddate=None):
    """Analysera en användares bidrag."""
    print(f"Hämtar data för {username}...")
    contribs = get_user_contributions(username, lang, startdate, enddate)
    
    print(f"  → Analyserar {len(contribs)} bidrag")
    
    articles = defaultdict(lambda: {"chars": 0, "created": False})
    pages_marked_as_new = set()
    
    for contrib in contribs:
        title = contrib["title"]
        sizediff = contrib.get("sizediff", 0)
        is_new = contrib.get("parentid", 1) == 0
        
        articles[title]["chars"] += sizediff
        
        if is_new and title not in pages_marked_as_new:
            articles[title]["created"] = True
            pages_marked_as_new.add(title)
    
    return articles, contribs

def generate_report(usernames, lang="sv", startdate=None, enddate=None):
    """Generera rapport för flera användare."""
    output = []
    
    # Om enddate är None, använd dagens datum
    display_enddate = enddate if enddate is not None else datetime.now().strftime("%Y-%m-%d")
    
    # Lägg till titel med Wikipedia-URL
    output.append(f"Analys över användarbidrag på https://{lang}.wikipedia.org/")
    
    # Lägg till tidsperiod
    output.append(f"Tidsperiod: {startdate} - {display_enddate}")
    output.append("")
    
    all_user_data = []
    
    for username in usernames:
        try:
            articles, all_contribs = analyze_contributions(username, lang, startdate, enddate)
            
            total_chars = sum(data["chars"] for data in articles.values())
            total_articles = len(articles)
            total_created = sum(1 for data in articles.values() if data["created"])
            
            all_user_data.append({
                "username": username,
                "articles": articles,
                "total_chars": total_chars,
                "total_articles": total_articles,
                "total_created": total_created
            })
            
            output.append(f"{username}, bidrag {total_chars:+,} tecken, redigerat {total_articles} artiklar, skapat {total_created}".replace(",", " "))
        except Exception as e:
            print(f"FEL vid bearbetning av {username}: {e}")
            import traceback
            traceback.print_exc()
    
    output.append("")
    
    for user_data in all_user_data:
        output.append(f"\n{user_data['username']}")
        
        sorted_articles = sorted(user_data['articles'].items(), 
                                key=lambda x: abs(x[1]["chars"]), 
                                reverse=True)
        
        for title, data in sorted_articles:
            chars_display = f"{data['chars']:+,}".replace(",", " ")
            created_mark = " (skapad)" if data["created"] else ""
            output.append(f"{title}, {chars_display}{created_mark}")
    
    return "\n".join(output)


# Kör analysen
print("=== STARTAR ANALYS ===")
usernames = ["Robertsilen", "Cogitato"]
lang = "sv"  # Ändra till "en", "de", "fr", etc. för andra språk
startdate = "2025-01-01"  # Format: "YYYY-MM-DD" eller None för från början
enddate = None  # Format: "YYYY-MM-DD" eller None för till nu (dagens datum)

report = generate_report(usernames, lang, startdate, enddate)

print("\n=== SKRIVER TILL FIL ===")

# Skriv till fil
try:
    with open("wikipedia_bidrag.txt", "w", encoding="utf-8") as f:
        f.write(report)
    print("✓ Filen har skrivits!")
except Exception as e:
    print(f"✗ Kunde inte skriva filen: {e}")
    import traceback
    traceback.print_exc()

print("\n=== RAPPORT ===")
print(report)