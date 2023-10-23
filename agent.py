import json
import requests

from unidecode import unidecode

from llmHandler import LlmHandler
from problem import Problem
from user import User


base_url = "http://localhost:8080"

"""
TODO:
    Maybe Done - Ignore (do not process) message if agent sent the last message.
    - Change frontend other-user icon
    - Fix having to reaload chat page to show message
"""


class Agent:
    session = requests.Session()
    problem = Problem()
    llm_handler = LlmHandler(problem)
    user = User()
    have_processed_first = False

    def __init__(self, frame):
        self.room_id = frame.body.split(":")[1]
        self.create_user()

    def __str__(self):
        return self.room_id

    def process_message(self, frame):
        body = json.loads(frame.body)

        self.get_resolution_info(body)

        new_problem_id = body["problem"]["id"]
        if self.problem.id != new_problem_id:
            self.get_problem_info(body)

        if self.last_message_is_from_agent():
            return

        if self.last_message_is_from_user():
            print("USER MESSAGE")
            print(self.problem.chat)
            self.handle_chat_message()

    def last_message_is_from_agent(self):
        sender = self.problem.chat[-2]["sender"]
        username = self.user.username
        if sender == username:
            return True
        else:
            return False

    def last_message_is_from_user(self):
        sender = self.problem.chat[-2]["sender"]
        username = self.user.username
        if sender != username and sender != "system":
            return True
        else:
            return False

    def login(self, username, password):
        while True:
            if (
                self.session.post(
                    f"{base_url}/api/login",
                    json={
                        "username": username,
                        "password": password,
                        "timeZone": "UTC",
                    },
                ).status_code
                == 200
            ):
                break

    def get_problem_info(self, body):
        problem_id = body["problem"]["id"]

        while True:
            problem_response = self.session.get(
                f"{base_url}/api/problems/{str(problem_id)}"
            )
            if problem_response.status_code == 200:
                break

        self.problem.id = problem_id
        problem_dict = json.loads(problem_response.text)
        # self.problem.text = problem_json["text"]
        self.problem.known_quantities = problem_dict["knownQuantities"]
        self.problem.unknown_quantities = problem_dict["unknownQuantities"]
        self.problem.graphs = problem_dict["graphs"]

    def get_resolution_info(self, body):
        # This should be in get_problem_info but the endpoint returns null
        self.problem.text = body["problem"]["text"]
        self.problem.notebook = body["notebook"]
        self.problem.equations = body["equations"]
        self.problem.chat = body["chat"]

    def handle_chat_message(self):
        response = self.llm_handler.call()
        response = "RESPONSE"
        # response = "2*(x - 4 -6) = x - 6"
        if True:
            while True:
                if (
                    self.session.put(
                        f"{base_url}/api/chat/{self.room_id}",
                        json={"message": response, "variable": "variable"},
                    ).status_code
                    == 200
                ):
                    break
            print("AGENT SENT MESSAGE")

    def create_user(self):
        self.login("admin", "admin")

        # Get new user's random info
        while True:
            user_info_response = self.session.get(
                "https://randomuser.me/api/1.4/?nat=es"
            )
            if user_info_response.status_code == 200:
                break
        user_dict = json.loads(user_info_response.text)["results"][0]

        # Create new user
        self.user.username = unidecode(
            f"{user_dict['name']['first']}_{user_dict['name']['last']}".lower()
        )
        self.user.email = user_dict["email"]
        self.user.password = user_dict["login"]["sha256"]
        self.user.sex = user_dict["gender"].title()

        # Register the new user and login
        while True:
            if (
                self.session.post(
                    f"{base_url}/api/signup", json=self.user.for_backend()
                ).status_code
                == 200
            ):
                break
        self.login(self.user.username, self.user.password)

    def __del__(self):
        while True:
            if (
                self.session.delete(
                    f"{base_url}/api/users/{self.user.username}"
                ).status_code
                == 200
            ):
                break

        print("AGENT DELETED")
