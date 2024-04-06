import time
import json
import re
import requests

from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys
from bs4 import BeautifulSoup
from llmHandler import LlmHandler
from problem import Problem
from user import User
from utils import last_message_is_clarification, get_message_for_clarification, last_message_is_suggestion, get_message_for_suggestion

base_url = "https://betatutorchat.uv.es"
agents_collection = 15
default_sleep = 3
max_consecutive_helps = 10
max_steps = 100
max_resolutions = 10

class FakeUser:
    def __init__(self, problem_in_wrapper):
        self.problem = Problem()
        self.session = requests.Session()
        self.set_problem(problem_in_wrapper)
        self.get_additional_problem_info()
        self.problem_in_wrapper = problem_in_wrapper

    def solve_problem(self):
        self.llm_handler = LlmHandler(self.problem)
        self.finished = False
        self.consecutive_helps = 0
        self.steps = 0
        self.helps = 0

        self.enter_problem(self.problem_in_wrapper)

        #print("SOLVING NOW")
        while not self.finished:
            self.get_problem_state()
            if not self.finished:
                self.send_message(self.get_message())
                time.sleep(default_sleep)
            #print("\n")

        self.save_statistics()

    def get_message(self):
        if self.problem.chat[-1]["message"].startswith("Muy bien"):
            self.problem.last_suggestion = ""

        if last_message_is_clarification(self.problem):
            #self.send_message(get_message_for_clarification(self.problem))
            response = get_message_for_clarification(self.problem)
        elif last_message_is_suggestion(self.problem):
            #self.send_message(get_message_for_suggestion(self.problem))
            self.problem.last_suggestion += "\n".join([l for l in self.problem.chat[-1]["message"].splitlines() if l])+"\n\n"
            response = get_message_for_suggestion(self.problem)
            if response == "<CALL LLM>": response = self.llm_handler.call()
        else:
            response = self.llm_handler.call()

        #response = self.ask_for_human_message(response)

        response = response.strip().lower()

        if not re.search(r"^[0-9]+$|^si$", response): self.steps+=1
        if re.search(r"ayuda", response):
            self.helps+=1
            self.consecutive_helps+=1
        else:
            self.consecutive_helps = 0

        return response
    
    def save_statistics(self):
        self.nb = len(self.problem.notebook)
        self.uq = len(self.problem.unknown_quantities)
        self.eq = len(self.problem.equations)
        self.gs = len(self.problem.graphs[0]["paths"])
        if self.nb>self.uq: self.uq=self.nb
        if self.eq>self.gs: self.gs=self.eq
        if self.consecutive_helps == max_consecutive_helps:
            self.finish_state = "HELP LOOP"
        elif self.steps == max_steps:
            self.finish_state = "MANY STEPS"
        else:
            self.finish_state = "FINISHED"

    def ask_for_human_message(self, response):
        print(f"AGENT RESPONSE: {response}")
        if opt := input("DEFAULT? "):
            response = opt
        return response
            
    def last_message_is_from_tutor(self):
        return self.problem.chat[-1]["sender"] == "system"

    def clean_chat_message(self, message):
        message = message.replace("\r", "")
        message = re.sub(r"</?br/?>", "\n", message)
        message = re.sub(r"&gt;", ">", message)
        return message

    def reset_current_problem(self):
        try: driver.find_element(By.XPATH, "//button[contains(text(), 'Entendido')]").click()
        except: ...
        time.sleep(1)
        try: driver.find_element(By.XPATH, "//button[contains(text(), 'Reiniciar')]").click()
        except: ...
        time.sleep(1)
        try: driver.find_element(By.CSS_SELECTOR, ".accept").click()
        except: ...
        
    def go_to_problem(self):
        while True:
            try: driver.find_element(By.CSS_SELECTOR, ".message_input_collection.message_input.form-control")
            except:
                driver.get(f"https://betatutorchat.uv.es/collections")
                time.sleep(default_sleep)
                while True:
                    try: collection = driver.find_element(By.ID, f"row-{str(agents_collection)}")
                    except:
                        driver.find_element(By.ID, "pagination-next-page").click()
                        time.sleep(1)
                    else: break
                collection.click()
                time.sleep(5)
            else: break
    
    def set_problem(self, problem_index):
        collection_dict = json.loads(open("collection_all_problems.json", "r").read())
        all_problems = collection_dict["problems"]
        number_of_problems = len(all_problems)
        #if problem_index >= number_of_problems: problem_index = number_of_problems
        collection_dict["problems"] = [all_problems[problem_index]]
        self.login_backend()
        while True:
            if (
                self.session.put(
                    f"https://betatutorchat.uv.es/api/wrapper/{str(agents_collection)}",
                    json=json.loads(json.dumps(collection_dict)),
                ).status_code
                == 200
            ):
                break

    def enter_problem(self, problem_index):
        self.go_to_problem()
        time.sleep(default_sleep)
        self.reset_current_problem()
        time.sleep(default_sleep)
        self.go_to_problem()
        #while True:
        #    try: driver.find_element(By.CSS_SELECTOR, ".message_input_collection.message_input.form-control")
        #    except:
        #        driver.get(f"https://betatutorchat.uv.es/collections/{str(agents_collection)}/problem/{problem_id}")
        #        time.sleep(5)
        #    else: break
        
    def send_message(self, message):
        chat_input = driver.find_element(By.CSS_SELECTOR, ".message_input_collection.message_input.form-control")
        time.sleep(0.3)
        chat_input.clear()
        time.sleep(0.3)
        chat_input.send_keys(message)
        time.sleep(0.3)
        chat_input.send_keys(Keys.ENTER)
    
    def check_if_finished(self):
        try:
            driver.find_element(By.XPATH, "//button[contains(text(), '¡Felicidades! Has resuelto el problema (Presiona para continuar)')]")
            self.finished = True
        except:
            if self.consecutive_helps == max_consecutive_helps or self.steps == max_steps:
                self.finished = True

    def get_problem_state(self):
        soup = BeautifulSoup(driver.page_source, "html.parser")
        self.check_if_finished()
        self.problem.text = soup.find("p", class_="card-text").text
        self.problem.notebook = [note.text for note in soup.find_all("div", id="Notebook")[0].find_all("div") if not note.input]
        self.problem.equations = [note.text for note in soup.find_all("div", id="Notebook")[1].find_all("div") if not note.input]
        boxes = soup.find("ul", id="chatMessages").find_all("div", class_="box")
        self.problem.chat = [{"sender": ("system" if "left" in box.li["class"] else "user"), "message": self.clean_chat_message(box.find("div",class_="text").decode_contents())} for box in boxes]

    def login_backend(self):
        while True:
            if (
                self.session.post(
                    f"{base_url}/api/login",
                    json={
                        "username": "agent",
                        "password": "agent",
                        "timeZone": "Europe/Madrid",
                        "lastConnection": 0,
                    },
                ).status_code
                == 200
            ):
                break
        
    def get_additional_problem_info(self):
        self.login_backend()
        
        while True:
            wrapper_response = self.session.get(
                f"{base_url}/api/wrapper/{str(agents_collection)}/problems"
            )
            if wrapper_response.status_code == 200:
                break
            
        problem_id = json.loads(wrapper_response.text)["wrapperProblems"][0]["id"]
        
        while True:
            problem_response = self.session.get(
                f"{base_url}/api/problems/{str(problem_id)}"
            )
            if problem_response.status_code == 200:
                break
            
        problem_dict = json.loads(problem_response.text)
        self.problem.name = problem_dict["name"]
        self.problem.known_quantities = problem_dict["knownQuantities"]
        self.problem.unknown_quantities = problem_dict["unknownQuantities"]
        self.problem.graphs = problem_dict["graphs"]
        self.problem.id = problem_id
        self.uq = len(self.problem.unknown_quantities)
        self.eq = len(self.problem.equations)
        self.gs = len(self.problem.graphs[0]["paths"])
            
def login():
    driver.get("https://betatutorchat.uv.es")

    while True:
        try: username_input = driver.find_element(By.ID, "username")
        except: time.sleep(1)
        else: break
    
    username_input.clear()
    username_input.send_keys("agent")
    
    password_input = driver.find_element(By.ID, "password")
    password_input.clear()
    password_input.send_keys("agent")
    
    password_input.send_keys(Keys.ENTER)

def main():
    global driver
    chrome_options = webdriver.ChromeOptions()
    chrome_options.add_argument("--headless=new")
    driver = webdriver.Chrome(options=chrome_options)
    login()
    results = []
    for p in range(4,20):
        fu = FakeUser(p)
        problem = {
            "name": fu.problem.name,
            "id": fu.problem.id,
            "graph_length": fu.gs,
            "unknown_quantities": fu.uq,
            "resolutions": []
        }
        for r in range(max_resolutions):
            print(f"PROBLEM {p} | RESOLUTION {r}")
            fu.solve_problem()
            resolution = {
                "state": fu.finish_state,
                "steps": fu.steps,
                "helps": fu.helps,
                "variables": fu.nb,
                "equations": fu.eq
            }
            problem["resolutions"].append(resolution)
            time.sleep(5)
        results.append(problem)
        f = open("resolutions", "a")
        f.write(json.dumps(problem))
        f.write(", ")
        f.close()
    #print(results)
    #open("resolutions", "w").write(json.dumps(results))
    driver.quit()
    
if __name__ == "__main__":
    main()
