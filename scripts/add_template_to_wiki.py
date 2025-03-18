import pandas as pd
import re
from urllib.parse import unquote
from selenium import webdriver
from selenium.webdriver.common.by import By
import time

# Load the Excel file
file_path = "Finlands författare, temp.xlsx"
sheet_name = "master with wiki"
column_with_wiki_urls = "Wiki_SV"
startfrom = None # None means from beginning, for example "Hanna_Rönnberg" means start from Hanna Rönnberg
df = pd.read_excel(file_path, sheet_name=sheet_name, header=1)

# Extract Wikipedia titles
df["Title"] = df[column_with_wiki_urls].astype(str).apply(
    lambda x: unquote(x.replace("https://sv.wikipedia.org/wiki/", "")) if x.startswith("https://sv.wikipedia.org/wiki/") else ""
)

# Setup Selenium
driver = webdriver.Chrome()  # Ensure ChromeDriver is installed

# Open login page and wait for user to log in
print("Opening Wikipedia login page...")
driver.get("https://sv.wikipedia.org/w/index.php?title=Special:Inloggning")
input("Please log in to Wikipedia and press Enter once you're logged in...")

# Template to insert
template_to_add = "* {{Finlands författare 1809-1916}}\n"


startfound = False
# Loop through each article
for _, row in df.iterrows():
    title = row["Title"]
    print(f"Processing {title}")
    if not title:  # Skip if title is empty (e.g., invalid or missing row)
        continue
    if startfrom != None:
        if not startfound:
            if title != startfrom:
                continue
            else:
                startfound = True
    
    url = f"https://sv.wikipedia.org/w/index.php?title={title}&action=edit"
    
    # Open the edit page
    driver.get(url)
    time.sleep(2)  # Wait for page to load

    # Find the edit box
    try:
        textarea = driver.find_element(By.ID, "wpTextbox1")
        text = textarea.get_attribute("value")

        # Check if template is already present
        if template_to_add.strip() in text:
            print(f"Template already present in {title}, skipping.")
            continue

        # Check if "Finlands författare" is present in the text
        if "Finlands författare" in text:
            print(f"Manual edit needed for {title}: {url}")
            input("Press Enter to continue to next article...")
            continue

        # Check if "==Vidare läsning==" or "== Vidare läsning ==" exists in the text
        if "==Vidare läsning==" in text or "== Vidare läsning ==" in text:
            # If "Vidare läsning" exists, add the template directly
            new_text = text.replace("==Vidare läsning==" if "==Vidare läsning==" in text else "== Vidare läsning ==",
                                    "== Vidare läsning ==\n" + template_to_add)
        else:
            # If "Vidare läsning" is not found, insert it before the first relevant section
            split_points = ["== Externa länkar ==", "==Externa länkar==", "{{STANDARDSORTERING", "{{Auktoritetsdata", "{{auktoritetsdata", "[[Kategori:", "==Se även", "== Se även"]
            insert_pos = len(text)
            for point in split_points:
                pos = text.find(point)
                if pos != -1:
                    insert_pos = min(insert_pos, pos)

            new_text = text[:insert_pos] + "== Vidare läsning ==\n" + template_to_add + "\n" + text[insert_pos:]

        # Insert updated text into the Wikipedia editor
        textarea.clear()
        textarea.send_keys(new_text)

        print(f"Edit ready for {title}. Review in browser and submit manually.")

        # Pause for review
        while True:
            user_input = input("Press Enter after submission to continue to next article (or type 'skip' to move on): ").strip().lower()
            if user_input == "" or user_input == "skip":
                break  # Only continue when the user presses Enter or types 'skip'

    except Exception as e:
        print(f"Error processing {title}: {e}")
        continue

driver.quit()
print("Done!")
