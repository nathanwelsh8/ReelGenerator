import os
from services.logger import get_logger
from use_cases.process_project_flow import process_project

logger = get_logger()


def run_flow():
    process_project()

if __name__ == "__main__":
    run_flow()
