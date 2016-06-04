#!/usr/bin/python

# Copyright 2016 Vegard Knutsen Lillevoll
#
# Follow this project at https://github.com/vegardli/PyBitica.txt
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
# 
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
# 
# You should have received a copy of the GNU General Public License
# along with this program.  If not, see <http://www.gnu.org/licenses/>.
#
# THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
# IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
# FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
# AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
# LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
# OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN
# THE SOFTWARE. 

import pickle,os,requests,re,datetime,argparse

# Parse command-line options
parser = argparse.ArgumentParser(description="Sync todo lists between todo.txt and Habitica")
parser.add_argument("--options_file", help="File to read and write options")
args = parser.parse_args()

# Default data file location
data_file = os.path.join(os.path.expanduser("~"), ".pybitica.txt")
if args.options_file:
    data_file = args.options_file

# Todo superclass, for both local and Habitica todos
class Todo:
    def __str__(self):
        outstr = ""

        if self.done:
            outstr += "x "
            if self.completed:
                outstr += self.completed.isoformat() + " "
            if self.created:
                outstr += self.created.isoformat() + " "

        else:
            if self.priority:
                outstr += self.priority
            if self.created:
                outstr += self.created.isoformat() + " "

        outstr += self.text

        for p in self.projects:
            outstr += " " + p
        for c in self.contexts:
            outstr += " " + c
        for k, v in self.addons.items():
            if type(v) == type(datetime.date.today()):
                outstr += " " + k + ":" + v.isoformat()

            else:
                outstr += " " + k + ":" + v

        return outstr + "\n"

    def get_dict(self):
        d = {}

        d['type'] = 'todo'
        d['completed'] = self.done

        if self.created:
            d['createdAt'] = self.created.isoformat()
        if self.completed:
            d['dateCompleted'] = self.completed.isoformat()
        
        if "habitica_id" in self.addons:
            d['id'] = self.addons['habitica_id']

        d['text'] = self.text

        return d


class LocalTodo(Todo):
    def __init__(self, init_str):
        self.done = False
        self.created = None
        self.completed = None
        self.priority = None
        self.text = ""

        # Search for priority, date and text (incomplete tasks)
        incomplete_result = re.match("(\([A-Z]\) )?\s*([0-9]{4}-[0-9]{2}-[0-9]{2} )?(.+)", init_str)

        # Search for completeness, completion date, creation date and text (complete tasks)
        complete_result = re.match("x \s*([0-9]{4}-[0-9]{2}-[0-9]{2} )?\s*([0-9]{4}-[0-9]{2}-[0-9]{2} )?(.+)", 
                init_str)

        if complete_result:
            # Task is complete
            self.done = True
            
            if complete_result.group(1):
                self.completed = datetime.datetime.strptime(complete_result.group(1).strip(), "%Y-%m-%d").date()

            if complete_result.group(2):
                self.created = datetime.datetime.strptime(complete_result.group(2).strip(), "%Y-%m-%d").date()

            self.text = complete_result.group(3)

        elif incomplete_result:
            # Task is incomplete
            self.priority = incomplete_result.group(1)

            if incomplete_result.group(2):
                self.created = datetime.datetime.strptime(incomplete_result.group(2).strip(), "%Y-%m-%d").date()

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

    if j['success']:
        task.id = j['data']['_id']
        print('Created task "' + task.text + '" on Habitica')

    else:
        print("Warning: Task creation failed with message: " + r.text)

def complete_habitica_task(headers, task):
    r = requests.post("https://habitica.com/api/v3/tasks/" + task.id + "/score/up", headers = headers)
    j = r.json()

    if j['success']:
        print('Completed task "' + task.text + ' on Habitica')

    else:
        print("Warning: Task completion failed with message: " + r.text)

def update_habitica_name(headers, task):
    payload = {"text": str(task)}
    r = requests.put("https://habitica.com/api/v3/task/" + task.id, headers = headers, json=payload)
    j = r.json()

    if j['success']:
        print('Updated name of "' + task.text + ' on Habitica')

    else:
        print("Warning: Task update failed with message: " + r.text)

# Make sure the tasks on Habitica are sorted by the order given in local_tasklist
def sort_habitica_tasks(headers, local_tasklist):
    for i in range(len(local_tasklist)):
        task = local_tasklist[i]
        if task.done:
            continue

        if not "habitica_id" in task.addons:
            print("Warning: couldn't find habitica_id for \"" + task + "\" when sorting.")
            continue

        r = requests.post("https://habitica.com/api/v3/tasks/" + task.addons["habitica_id"] + "/move/to/" + str(i), 
                headers=headers)
        j = r.json()

        if not j['success']:
            print("Warning: sorting failed for \"" + str(task) + "\"")
            print(r.text)

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
    # Make sure the file can be written to
    open(options["todo.txt-location"], "a").close()
    save_options(data_file, options)


# Load todos from todo.txt
local_todos = []

with open(options["todo.txt-location"], "r") as local_todos_file:
    for line in local_todos_file.readlines():
        if line.strip():
            local_todos.append(LocalTodo(line))


# Load todos from habitica
habitica_todos = []

# Headers that will be used for all requests
headers = {"Content-Type": "application/json", "x-api-user": options["api-user"], "x-api-key": options["api-key"]}
# We need to retrieve both completed and uncompleted todos
params = ({"type": "todos"}, {"type": "completedTodos"})

for p in params:
    r = requests.get("https://habitica.com/api/v3/tasks/user", headers=headers, params=p)

    j = r.json()

    for d in j["data"]:
        habitica_todos.append(HabiticaTodo(d))


# Start synchronization loop
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


# Sort tasks locally and on Habitica
local_todos.sort(key = lambda x: str(x))
sort_habitica_tasks(headers, local_todos)

# Save changes
with open(options["todo.txt-location"], "w") as local_todos_file:
    for todo in local_todos:
        local_todos_file.write(str(todo))

