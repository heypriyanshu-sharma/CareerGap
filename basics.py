import csv
'''def greet(name):
    print("Hello!", name, "Welcome to CareerGap!")


def calculate_age(birth_year):
    current_year = 2026
    age = current_year - birth_year
    return age


name = input("Enter your name: ")
birth_year = int(input("Enter your birth year: "))
fav = input("Enter your favorite programming language: ").lower()

age = calculate_age(birth_year)

print("\n--- Your Information ---")
print("Name:", name)
print("Age:", age)
print("Favorite language:", fav)

if fav == "python":
    print("Great choice! Python will be useful for CareerGap.")
else:
    print("We'll eventually learn Python for this project.")

greet(name)

skills = ["Python","SQL","pandas","numpy","git"]
print(skills)
for skill in skills:
    print("i know ",skill)

req_skills = ["Python","SQL","pandas","DOCKER","AWS"]
resume_skills=["Python","SQL","pandas","git"]
for skill in req_skills:
    if skill in resume_skills:
        print("matched:",skill)
    else:
        print("missing:",skill)

text = "I know Python, SQL and Pandas."

text = text.replace(",", "")
text = text.replace(".", "")

print(text)

skill_aliases = {
    "ml": "Machine Learning",
    "machine learning": "Machine Learning",
    "machine-learning": "Machine Learning"
}

print(skill_aliases["MACHINE LEARNING"])'''

import csv

with open("market_data.csv", "r") as file:
    data = csv.DictReader(file)

    for row in data:
        if row["skill"] == "Python":
            print("Python market demand:", row["market_demand"], "%")