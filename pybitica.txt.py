#!/usr/bin/python

import pickle,os,requests,re,datetime,argparse

parser = argparse.ArgumentParser(description="Sync todo lists between todo.txt and Habitica")
parser.add_argument("--options_file", help="File to read and write options")
options = parser.parse_args()

data_file = "data"

if options.options_file:
    data_file = options.options_file

class Todo:
    def __str__(self):
        outstr = ""

        if self.done:
            outstr += "x "
            if self.completed:
                outstr += self.completed + " "
            if self.created:
                outstr += self.created + " "

        else:
            if self.priority:
                outstr += self.priority
            if self.created:
                outstr += self.created

        outstr += self.text

        for p in self.projects:
            outstr += " " + p
        for c in self.contexts:
            outstr += " " + c
        for k, v in self.addons.items():
            outstr += " " + k + ":" + v

        return outstr + "\n"

    def get_dict(self):
        d = {}

        d['type'] = 'todo'
        d['completed'] = self.done

        if self.created:
            d['createdAt'] = self.created
        if self.completed:
            d['dateCompleted'] = self.completed
        
        if "habitica_id" in self.addons:
            d['id'] = self.addons['habitica_id']

        d['text'] = str(self)

        return d


class LocalTodo(Todo):
    def __init__(self, init_str):
        self.done = False
        self.created = None
        self.completed = None
        self.priority = None
        self.text = ""

        # Search for priority, date and text (incomplete tasks)
        incomplete_result = re.match("(\([A-Z]\) )?([0-9]{4}-[0-9]{2}-[0-9]{2} )?(.+)", init_str)

        # Search for completeness, completion date, creation date and text (complete tasks)
        complete_result = re.match("x ([0-9]{4}-[0-9]{2}-[0-9]{2} )?([0-9]{4}-[0-9]{2}-[0-9]{2} )?(.+)", init_str)

        if complete_result:
            # Task is complete
            self.done = True
            # TODO: Completed and created dates
            self.text = complete_result.group(3)

        elif incomplete_result:
            # Task is incomplete
            self.priority = incomplete_result.group(1)

            # TODO: Set date
            self.text = incomplete_result.group(3)

        else:
            # TODO: Implement own exception
            raise Exception("Couldn't parse task: " + init_str)

        (self.text, self.projects, self.contexts, self.addons) = parse_todotext(self.text)


class HabiticaTodo(Todo):
    def __init__(self, init_dict):
        self.done = init_dict['completed']
        self.created = None
        self.completed = None
        self.text = re.sub("^(\([A-Z]\) )", "", init_dict['text'])
        self.priority = None

        if "id" in init_dict:
            self.id = init_dict["id"]
        else:
            self.id = None

        (self.text, self.projects, self.contexts, self.addons) = parse_todotext(self.text)

# Returns (text, projects, contexts, addons)
def parse_todotext(text):
    projects = []
    contexts = []
    addons = {}

    project_regex = re.compile(" \+[^ ]+")
    context_regex = re.compile(" \@[^ ]+")
    addon_regex = re.compile("([^ :]+):([^ :]+)")

    for p in project_regex.findall(text):
        projects.append(p.lstrip(" "))

    for c in context_regex.findall(text):
        contexts.append(c.lstrip(" "))

    for a in addon_regex.findall(text):
        addons[a[0]] = a[1]

    # Remove projects, contexts and addons from text
    (text, n) = project_regex.subn("", text)
    (text, n) = context_regex.subn("", text)
    (text, n) = addon_regex.subn("", text)

    text = text.strip()

    return (text, projects, contexts, addons)


def load_options(data_file):
    return pickle.load(open(data_file, "rb"))

def save_options(data_file, options):
    pickle.dump(options, open(data_file, "wb"))

def create_habitica_task(headers, task):
    r = requests.post("https://habitica.com/api/v3/tasks/user", headers=headers, json=task.get_dict())
    j = r.json()

    if j['success'] == True:
        task.id = j['data']['_id']
        print('Created task "' + task.text + '" on Habitica')

    else:
        print("Warning: Task creation failed with message: " + r.text)

def complete_habitica_task(headers, task):
    r = requests.post("https://habitica.com/api/v3/tasks/" + task.id + "/score/up", headers = headers)
    j = r.json()

    if j['success'] == True:
        print('Completed task "' + task.text + ' on Habitica')

    else:
        print("Warning: Task completion failed with message: " + r.text)

def update_habitica_name(headers, task):
    payload = {"text": str(task)}
    r = requests.put("https://habitica.com/api/v3/task/" + task.id, headers = headers, json=payload)
    print(r.url)
    j = r.json()

    if j['success'] == True:
        print('Updated name of "' + task.text + ' on Habitica')

    else:
        print("Warning: Task update failed with message: " + r.text)

# Load options
if os.path.isfile(data_file):
    options = load_options(data_file)

else:
    options = {}

# Take option input from user
if not "api-user" in options:
    options["api-user"] = input("User ID: ")
    save_options(data_file, options)

if not "api-key" in options:
    options["api-key"] = input("API Token: ")
    save_options(data_file, options)

if not "todo.txt-location" in options:
    options["todo.txt-location"] = input("todo.txt location: ")
    open(options["todo.txt-location"], "w").close()
    save_options(data_file, options)


# Load todos from todo.txt
local_todos = []

with open(options["todo.txt-location"], "r") as local_todos_file:
    for line in local_todos_file.readlines():
        if line.strip():
            local_todos.append(LocalTodo(line))


# Load todos from habitica
habitica_todos = []

headers = {"Content-Type": "application/json", "x-api-user": options["api-user"], "x-api-key": options["api-key"]}
params = ({"type": "todos"}, {"type": "completedTodos"})

for p in params:
    r = requests.get("https://habitica.com/api/v3/tasks/user", headers=headers, params=p)

    j = r.json()

    for d in j["data"]:
        habitica_todos.append(HabiticaTodo(d))

# Do sync
actions = 1
while actions != 0:
    actions = 0

    # Look for (uncompleted) tasks on Habitica that don't exist locally
    for habitica_todo in habitica_todos:
        if not habitica_todo.done:
            found = False

            # Search by ID
            for local_todo in local_todos:
                if "habitica_id" in local_todo.addons and local_todo.addons["habitica_id"] == habitica_todo.id:
                    found = True
                    break

            if found:
                continue

            # Search by text
            for local_todo in local_todos:
                if local_todo.text == habitica_todo.text:
                    found = True
                    local_todo.addons["habitica_id"] = habitica_todo.id
                    print('"' + local_todo.text + '" sync established')
                    actions += 1
                    break

            if found:
                continue

            # Not found, create
            local_todos.append(LocalTodo(str(habitica_todo)))
            print('"' + habitica_todo.text + '" created locally')
            actions += 1

    if actions > 0:
        continue

    # Look for (uncompleted) tasks locally that don't exist on Habitica
    for local_todo in local_todos:
        if not local_todo.done and not "habitica_id" in local_todo.addons:
            new_todo = HabiticaTodo(local_todo.get_dict())
            create_habitica_task(headers, new_todo)
            habitica_todos.append(new_todo)
            actions += 1

    if actions > 0:
        continue


    # Check for information discrepancies between habitica and local
    for local_todo in local_todos:
        for habitica_todo in habitica_todos:
            if "habitica_id" in local_todo.addons and local_todo.addons["habitica_id"] == habitica_todo.id:
                # Check if task is done on Habitica but not locally
                if habitica_todo.done and not local_todo.done:
                    print('"' + local_todo.text + '" is completed on Habitica but not locally')
                    local_todo.done = True
                    actions += 1

                # Check if task is done locally but not on habitica
                if local_todo.done and not habitica_todo.done:
                    print('"' + local_todo.text + '" is completed locally but not on Habitica')
                    habitica_todo.done = True
                    complete_habitica_task(headers, habitica_todo)
                    actions += 1

                # Check for projects that exist only locally
                for p_l in local_todo.projects:
                    found = False
                    for p_h in habitica_todo.projects:
                        if p_l == p_h:
                            found = True
                            break

                    if not found:
                        habitica_todo.projects.append(p_l)
                        #update_habitica_name(headers, habitica_todo)


# Save local todos
with open(options["todo.txt-location"], "w") as local_todos_file:
    for todo in local_todos:
        local_todos_file.write(str(todo))

