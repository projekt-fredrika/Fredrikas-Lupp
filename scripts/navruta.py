import mwclient
import pandas as pd

username = "Cqsi" # sätt användarnament för botten här
password = open("password.txt", "r").read() # Mitt lösenord är i denna fil och därför finns inte filen på Github

lang = "fi" # fi/sv/en etc

site = mwclient.Site(lang + ".wikipedia.org")
site.login(username, password) 

edit_summary = "Added {{Nauvo}} navbox"

def add_nauvo_navbox(excel_file):

    counter = 0
    found = 0
    edited = 0

    try:
        df = pd.read_excel(excel_file, engine='openpyxl')
        print("Excel read.")
    except Exception as e:
        print("Something went wrong. Check the error:")
        print(e)

    for index, row in df.iterrows():
        counter+=1
        cur = row["artikel"]

        # load Wikipedia page
        page = site.pages[cur]

        if page.exists:
            found += 1
            article_text = page.text()

            if "{{Nauvo}}" not in article_text:

                edited += 1

                text = article_text.replace("[[Luokka:", "{{Nauvo}}\n\n[[Luokka:", 1)
                print(text)
                
                # DO NOT RUN THE LINE BELOW IF YOU DON'T WANT TO EDIT THE ARTICLE
                #page.edit(text, edit_summary)
            else:
                print("{{Nauvo}} already in page")

        else:
            print("Wikipedia page doesn't exist")

        # make the output clearer
        print()
        print("************************************************************")
        print()

    print("Found " + str(found) + "/" + str(counter) + " Wikipedia articles.")
    print("Edited " + str(edited) + "/" + str(found) + " Wikipedia articles.")
        

add_nauvo_navbox("excel\\input.xlsx")
