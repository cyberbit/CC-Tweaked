#!/usr/bin/env python3
"""
Parse reports generated by Gradle and convert them into GitHub annotations.

See https://github.com/actions/toolkit/blob/master/docs/problem-matchers.md and
https://github.com/actions/toolkit/blob/master/docs/commands.md.
"""

import os.path
import pathlib
import re
import xml.etree.ElementTree as ET
from typing import Optional, Tuple

LUA_ERROR_LOCATION = re.compile(r"^\s+(/[\w./-]+):(\d+):", re.MULTILINE)
JAVA_LUA_ERROR_LOCATION = re.compile(r"^java.lang.IllegalStateException: (/[\w./-]+):(\d+):")
JAVA_ERROR_LOCATION = re.compile(r"^\tat ([\w.]+)\.[\w]+\([\w.]+:(\d+)\)$", re.MULTILINE)
ERROR_MESSAGE = re.compile(r"(.*)\nstack traceback:", re.DOTALL)

SPACES = re.compile(r"\s+")

SOURCE_LOCATIONS = [
    "src/main/java",
    "src/main/resources/data/computercraft/lua",
    "src/test/java",
    "src/test/resources",
]

PROJECT_LOCATIONS = [
    "projects/core-api",
    "projects/core",
    "projects/common-api",
    "projects/common",
    "projects/forge-api",
    "projects/forge",
]

TEST_REPORTS = []


def find_file(path: str) -> Optional[str]:
    while len(path) > 0 and path[0] == "/":
        path = path[1:]

    for project in PROJECT_LOCATIONS:
        for source_dir in SOURCE_LOCATIONS:
            child_path = os.path.join(project, source_dir, path)
            if os.path.exists(child_path):
                return child_path

    return None


def find_location(message: str) -> Optional[Tuple[str, str]]:
    location = LUA_ERROR_LOCATION.search(message)
    if location:
        file = find_file(location[1])
        if file:
            return file, location[2]

    location = JAVA_LUA_ERROR_LOCATION.search(message)
    if location:
        file = find_file(location[1])
        if file:
            return file, location[2]

    for location in JAVA_ERROR_LOCATION.findall(message):
        file = find_file(location[0].replace(".", "/") + ".java")
        if file:
            return file, location[1]

    return None


def _parse_junit_file(path: pathlib.Path):
    for testcase in ET.parse(path).getroot():
        if testcase.tag != "testcase":
            continue

        for result in testcase:
            if result.tag != "failure":
                continue

            name = f'{testcase.attrib["classname"]}.{testcase.attrib["name"]}'
            message = result.attrib.get("message")

            location = find_location(result.text)
            error = ERROR_MESSAGE.match(message)
            if error:
                error = error[1]
            else:
                error = message

            if location:
                print(f'## {location[0]}:{location[1]}: {name} failed: {SPACES.sub(" ", error)}')
            else:
                print(f"::error::{name} failed")

            print("::group::Full error message")
            print(result.text)
            print("::endgroup")


def parse_junit() -> None:
    """
    Scrape JUnit test reports for errors. We determine the location from the Lua
    or Java stacktrace.
    """
    print("::add-matcher::.github/matchers/junit.json")

    for project in PROJECT_LOCATIONS:
        for path in pathlib.Path(os.path.join(project, "build/test-results/test")).glob("TEST-*.xml"):
            _parse_junit_file(path)

    print("::remove-matcher owner=junit::")


def _parse_checkstyle(path: pathlib.Path):
    for file in ET.parse(path).getroot():
        for error in file:
            filename = os.path.relpath(file.attrib["name"])

            attrib = error.attrib
            print(
                f'{attrib["severity"]} {filename}:{attrib["line"]}:{attrib.get("column", 1)}: {SPACES.sub(" ", attrib["message"])}'
            )


def parse_checkstyle() -> None:
    """
    Scrape JUnit test reports for errors. We determine the location from the Lua
    or Java stacktrace.
    """
    print("::add-matcher::.github/matchers/checkstyle.json")

    for project in PROJECT_LOCATIONS:
        for path in pathlib.Path(os.path.join(project, "build/reports/checkstyle/")).glob("*.xml"):
            _parse_checkstyle(path)

    print("::remove-matcher owner=checkstyle::")


if __name__ == "__main__":
    parse_junit()
    parse_checkstyle()
