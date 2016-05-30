#!/usr/bin/python

import pickle,os,requests

data_file = "data"



def load_options(data_file):
    return pickle.load(open(data_file, "rb"))

def save_options(data_file, options):
    pickle.dump(options, open(data_file, "wb"))

if os.path.isfile(data_file):
    options = load_options(data_file)

else:
    options = {}

if not "api-user" in options:
    options["api-user"] = input("User ID: ")
    save_options(data_file, options)

if not "api-key" in options:
    options["api-key"] = input("API Token: ")
    save_options(data_file, options)

print(options)

headers = {"Content-Type": "application/json", "x-api-user": options["api-user"], "x-api-key": options["api-key"]}
params = {"type": "completedTodos"}

r = requests.get("https://habitica.com/api/v3/tasks/user", headers=headers, params=params)

j = r.json()

for d in j["data"]:
    print(d["text"])


