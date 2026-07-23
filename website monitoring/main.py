import argparse
from database import add_new_website, find_website_history
from monitoring import update

parse = argparse.ArgumentParser
parse.add_argument(
    "-a",
)
