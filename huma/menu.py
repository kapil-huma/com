import click
from typing import Callable, Dict, List, Union, Optional
from huma_sdk.utils.log_utils import get_logger
import csv
import huma.helpers as h
from huma.cli_init import init_extensions, check_latest_cli_version
import traceback

import json
import os.path
from click.testing import CliRunner
from os import environ, path
import sys
import requests
import logging
from pathlib import Path, PurePath
import huma.__init__ as i
from pygments import highlight
from pygments.lexers import JsonLexer
from pygments.formatters import TerminalFormatter
import time


@init_extensions
@click.group()
def cli():
    """
    \033[95mRecent changes:\n
    \033[94m- smoke test updates to make recursion and autostart a flage.  you will not pass is '-r True', just '--recursion'.\n
    \033[0m
    """
    if not check_latest_cli_version():
        click.echo(click.style("There is s a new version of the CLI.  The CLI is now coupled to version of the environment that is released.", fg='red'))
        click.echo(click.style("Please update with `pip install 'huma@git+ssh://github.com/humahq/huma-cli.git' --upgrade`", fg='green'))
        exit(0)
    pass

@cli.command()
@click.option("--utterance", "-u", is_flag=False, required=True, help="Provide the customer number.", default=None)
@click.option("--customer", "-c", is_flag=False, required=True, help="Provide the customer number.", default=None)
@click.option("--environment", "-e", is_flag=False, required=True, help="Provide the environment.", default=None)
@click.option("--debug/--no-debug", "-d", is_flag=True, required=False, help="On error output debug stack trace.", default=False)
@click.option("--color/--no-color", "-l", is_flag=True, required=False, help="Print the output with color codes", default=True)
def get_utterance(utterance: str, customer: str, environment: str, debug: bool, color: bool):
    """Get an utterance payload from a provided utterance.

    This will submit an utterance to the utterance processor via huma-server.
    It requires username and password for the environment you are attempting to use.
    You can register in the front end of a given environment to get a username and password
    at <env>.<customer_number>.huma.ai.

    Permissions

        This command can be run by huma and customer logins.\n

    Required

        -c CUSTOMER_NUMBER (e.g. 009)\n
        -e ENVIRONMENT (e.g. dev)\n

    Options

        --debug/--no-debug\n

    Example:

        huma get-utterance --customer=009 --environment=dev --utterance="List insights related to drug Dupilumab"
    """
    # call helper func to talk to huma-server
    level = logging.DEBUG if debug else logging.ERROR
    logger = get_logger(__name__, level=level)
    try:
        payload = h.get_utterance(utterance=utterance,
                                  customer=customer,
                                  environment=environment)
        if payload:
            json_str = json.dumps(payload, indent=4, sort_keys=True)
            if color:
                print(highlight(json_str, JsonLexer(), TerminalFormatter()))
            else:
                print("{}".format(json_str))
            return
        else:
            logger.error(f"UNSUCCESSFUL on command get-utterance")
    except Exception:
        if debug:
            exception_info = traceback.format_exc()
            error_msg = 'CRITICAL ERROR on command get-utterance\n{:s}'.format(exception_info)
            logger.critical(error_msg)
        else:
            logger.error(f"UNSUCCESSFUL on command get-utterance.")
            logger.info(f"You can run this command with --debug to get more information")

@cli.command()
@click.option("--output-json-file", "-o", required=True, is_flag=False, help="A json file where the suggestions can be written", default=None)
@click.option("--customer", "-c", is_flag=False, help="Provide the customer number and override env HUMA_CUSTOMER", default=None)
@click.option("--environment", "-e", is_flag=False, help="Provide the environment and override env HUMA_ENVIRONMENT_KEY", default=None)
@click.option("--debug/--no-debug", "-d", is_flag=True, required=False, help="On error output debug stack trace.", default=False)
def get_suggestions(customer: str, environment: str, output_json_file: str, debug: bool):
    """
    Get a list of all (up to 1000) suggestions in the auto suggest module.

    Permissions

        This command can be run by huma logins only.\n

    Required

        -c CUSTOMER_NUMBER (e.g. 009)\n
        -e ENVIRONMENT (e.g. dev)\n
        -o full filepath to a json file.

    Options

        --debug/--no-debug\n

    Example

        huma get-suggestions -c 009 -e dev -o ./my_json_output_file.json\n
    """
    level = logging.DEBUG if debug else logging.ERROR
    logger = get_logger(__name__, level=level)
    try:
        suggestions_payload = h.get_suggestions(customer=customer, environment=environment)
        if len(suggestions_payload.get("suggestions")) != 0:
            with open(output_json_file, mode='w', encoding="utf-8") as current_save_file:
                current_save_file.write(json.dumps(suggestions_payload))
        else:
            logger.error(f"Unsuccessful in retreiving huma-server response on command get-suggestions")
    except Exception:
        if debug:
            exception_info = traceback.format_exc()
            error_msg = 'CRITICAL ERROR on command get-suggestions\n{:s} '.format(exception_info)
            logger.critical(error_msg)
        else:
            logger.error(f"UNSUCCESSFUL on command get-suggestions.")
            logger.info(f"You can run this command with --debug to get more information")


@cli.command()
@click.option("--customer", "-c", is_flag=False, required=True, help="Provide the customer number and override env HUMA_CUSTOMER", default=None)
@click.option("--environment", "-e", is_flag=False, required=True, help="Provide the environment and override env HUMA_ENVIRONMENT_KEY", default=None)
@click.option("--debug/--no-debug", "-d", help="Show debug logging", default=False)
def login(customer: str, environment: str, debug: bool) -> Callable:
    """
    Get and store a token locally.  Token are used to authenticate against the back end of huma platform.

    Permissions

        This command can be run by huma and customers.\n

    Required

        -c CUSTOMER_NUMBER (e.g. 009)\n
        -e ENVIRONMENT (e.g. dev)\n

    Options

        --debug/--no-debug\n

    Example

        huma login -c 009 -e dev\n
    """
    level = logging.DEBUG if debug else logging.ERROR
    logger = get_logger(__name__, level=level)
    try:
        logged_in = h.login(customer=customer, environment=environment)
        if logged_in:
            logger.info(f"You are logged into {customer}-{environment}.")
        else:
            logger.info(f"Failed to login to {customer}-{environment}")
    except Exception:
        if debug:
            exception_info = traceback.format_exc()
            error_msg = 'CRITICAL ERROR on login\n{:s}'.format(exception_info)
            logger.critical(error_msg)
        else:
            logger.error(f"UNSUCCESSFUL on command login.")
            logger.info(f"You can run this command with --debug to get more information")

@cli.command()
@click.option("--customer", "-c", is_flag=False, required=True, help="Provide the customer number and override env HUMA_CUSTOMER", default=None)
@click.option("--environment", "-e", is_flag=False, required=True, help="Provide the environment and override env HUMA_ENVIRONMENT_KEY", default=None)
@click.option("--debug/--no-debug", "-d", help="Show debug logging", default=False)
def logout(customer: str, environment: str, debug: bool) -> Callable:
    """
    Delete a specified locally stored tokens.

    Permissions

        This command can be run by huma and customers.\n

    Required

        -c CUSTOMER_NUMBER (e.g. 009)\n
        -e ENVIRONMENT (e.g. dev)

    Options

        --debug/--no-debug\n

    Example

        huma logout -c 009 -e dev\n
    """
    level = logging.DEBUG if debug else logging.ERROR
    logger = get_logger(__name__, level=level)
    try:
        logged_out = h.logout(customer=customer, environment=environment)
        if logged_out:
            logger.info(f"You have been logged out of {customer}-{environment}.")
        else:
            logger.info(f"Failed logout of to {customer}-{environment}")
    except Exception:
        if debug:
            exception_info = traceback.format_exc()
            error_msg = 'CRITICAL ERROR on logout\n{:s}'.format(exception_info)
            logger.critical(error_msg)
        else:
            logger.error(f"UNSUCCESSFUL on command logout.")
            logger.info(f"You can run this command with --debug to get more information")

@cli.command()
@click.option("--input-json-file", "-i", required=True, is_flag=False, help="A json file with a key of suggestions and list of suggestions", default=None)
@click.option("--customer", "-c", required=True, is_flag=False, help="Provide the customer number and override env HUMA_CUSTOMER", default=None)
@click.option("--environment", "-e", required=True, is_flag=False, help="Provide the environment and override env HUMA_ENVIRONMENT_KEY", default=None)
@click.option("--debug/--no-debug", "-d", help="Show debug logging", default=False)
def put_suggestions(customer: str, environment: str, input_json_file: str, debug: bool):
    """
    Put the specified suggestions list into an enviroment.

    Permissions

        This command can be run by huma logins only.\n

    Required

        -c CUSTOMER_NUMBER (e.g. 009)\n
        -e ENVIRONMENT (e.g. dev)

    Options

        --debug/--no-debug\n

    Example

        huma put_suggestions -c 009 -e dev -i ./suggestions.json\n
    """
    level = logging.DEBUG if debug else logging.ERROR
    logger = get_logger(__name__, level=level)
    suggestions = []
    try:
        with open(input_json_file, newline='', mode='r') as current_load_file:
            suggestions_payload = json.load(current_load_file)
            suggestions = suggestions_payload.get("suggestions")
            if not suggestions:
                logger.error(
                    f"No suggestions found in input_json_file. You must provide a json payload with a key called 'suggestions' with a value of a list of suggestions ")

        response = h.create_suggestions(suggestions,
                             customer=customer,
                             environment=environment)

        if (isinstance(response, requests.Response) and response.status_code == 200):
            logger.info(f"Create suggestions succeeded with input file {input_json_file}.")
        elif isinstance(response, requests.Response) and response.status_code != 200:
            logger.error(f"Create suggestions failed with input file {input_json_file} with status_code of {response.status_code} from {response.request.url}.")
        else:
            logger.error(f"Create suggestions failed with input file {input_json_file}.")

    except Exception:
        logger.error(f"Failed to update autosuggest config because error {e}")
    except Exception:
        if debug:
            exception_info = traceback.format_exc()
            error_msg = 'CRITICAL ERROR on put-suggestions\n{:s}'.format(exception_info)
            logger.critical(error_msg)
        else:
            logger.error(f"UNSUCCESSFUL on command put-suggestions.")
            logger.info(f"You can run this command with --debug to get more information")

    # working


@cli.command()
@click.option("--job-id", "-j", required=True, is_flag=False, help="An analyzer batch job_id", default=None)
@click.option("--output-json-file", "-o", required=False, is_flag=False, help="A json file to write the output into", default=None)
@click.option("--customer", "-c", required=True, is_flag=False, help="Provide the customer number and override env HUMA_CUSTOMER", default=None)
@click.option("--environment", "-e", required=True, is_flag=False, help="Provide the environment and override env HUMA_ENVIRONMENT_KEY", default=None)
@click.option("--debug/--no-debug", "-d", help="Show debug logging", default=False)
def get_analyzer_log(customer: str, environment: str, job_id: str, output_json_file: str, debug: bool):
    """
    Get the logs for a provided job_id.  The job_id must exist in the specified customer environment.\n

    Permissions

        This command can be run by huma logins only.\n

    Required

        -c CUSTOMER_NUMBER (e.g. 009)\n
        -e ENVIRONMENT (e.g. dev)
        -i JOB-ID

    Options

        --debug/--no-debug\n


    Outputs

        The results of the tests are printed to the screen.\n
        If an output-json-file was provided, the detailed results are placed in the output-json-file\n

    Example

        huma get-analyzer-log -c 009 -e dev -j 19823740923839 -o ./mylog.json\n
    """
    level = logging.DEBUG if debug else logging.ERROR
    logger = get_logger(__name__, level=level)
    try:
        analyzer_log_request = h.get_analyzer_logs(customer=customer,
                            environment=environment,
                            job_id=job_id)
        logs = analyzer_log_request.get("logs")
        if isinstance(logs, dict) and len(logs) > 0:
            for events in logs["logs"]["events"]:
                if isinstance(events, list):
                    for event_group in events:
                        for item in event_group:
                            print(item.get("message"))
                if isinstance(events, dict):
                    print(events.get("message"))
        else:
            print(f"No logs were returned from job_id {job_id} which may mean that the job is still processing.")
        if output_json_file and len(logs) > 0:
            with open(output_json_file, mode='w', encoding="utf-8") as current_save_file:
                current_save_file.write(json.dumps(logs))

    except Exception:
        if debug:
            exception_info = traceback.format_exc()
            error_msg = 'CRITICAL ERROR on login\n{:s}'.format(exception_info)
            logger.critical(error_msg)
        else:
            logger.error(f"UNSUCCESSFUL on command login.")
            logger.info(f"You can run this command with --debug to get more information")

@cli.command()
@click.option("--output-json-file", "-j", required=True, is_flag=False, help="A json file to write the output into", default=None)
@click.option("--output-csv-file", "-f", required=True, is_flag=False, help="A csv file to write the output into", default=None)
@click.option("--customer", "-c", is_flag=False, help="Provide the customer number and override env HUMA_CUSTOMER", default=None)
@click.option("--environment", "-e", is_flag=False, help="Provide the environment and override env HUMA_ENVIRONMENT_KEY", default=None)
@click.option("--duration", "-u", is_flag=False, help="Provide the number (integer) of days you would like get user activity from default=90 (ex: 90 for the last 90 days of activity)", default=90)
@click.option("--unique-records-only/--all-records", "-n", help="Provie unique records only", default=False)
@click.option("--debug/--no-debug", "-d", help="Show debug logging", default=False)
def get_user_activity(customer: str, environment: str, output_json_file: str, output_csv_file: str, unique_records_only: bool, duration:int, debug: bool):
    """Get user activity from huma user activity service for all users.\n
    If you provide a filepath to a file that already exists for --output-json-file or --output-csv-file, the CLI will not overwrite the file.\n
    The output_csv_file can be used as an input file to ask-questions and other commands that use a csv with an utterances header.\n

    Known Issue

        If there is dirty data in the output, the command may crash.  If you experience this, lessen the number of days of activity that you request.

    Permissions

        This command can be run by huma logins only.\n

    Required

        -c CUSTOMER_NUMBER (e.g. 009)\n
        -e ENVIRONMENT (e.g. dev)
        -j ./output.json
        -f ./output.csv

    Options

        --duration n (e.g. '90' is 90 days )
        --unique-records-only/--all-records
        --debug/--no-debug\n

    Outputs

        Detailed results are placed in the output-json-file and output-csv-file\n

    Example

        huma get-user-activity --customer=009 --environment=dev --output-json-file=./output.json --output-csv-file=./output.csv
    """
    level = logging.DEBUG if debug else logging.ERROR
    logger = get_logger(__name__, level=level)
    try:
        # call helper function to talk to huma-server
        payload = h.get_activity_dump(customer=customer,
            environment=environment,
            duration = duration)
        if len(payload) == 0:
            logger.info(f"The system returned an empty activity response.")
            exit(0)
    except Exception:
        if debug:
            exception_info = traceback.format_exc()
            error_msg = 'CRITICAL ERROR on getting data for get-user-activity\n{:s}'.format(exception_info)
            logger.critical(error_msg)
        else:
            logger.error(f"UNSUCCESSFUL on command get-user-activity.")
            logger.info(f"You can run this command with --debug to get more information")

    try:
        with open(output_json_file, mode='w', encoding="utf-8") as current_save_file:
            json.dump(payload, current_save_file, ensure_ascii=False, indent=4)
        logger.info(f"Success, activity dump has been written to the output_json_file {output_json_file}")
    except Exception:
        if debug:
            exception_info = traceback.format_exc()
            error_msg = 'CRITICAL ERROR on writing results to json file for get-user-activity\n{:s}'.format(exception_info)
            logger.critical(error_msg)
        else:
            logger.error(f"UNSUCCESSFUL on writing results to json file for command get-user-activity.")
            logger.info(f"You can run this command with --debug to get more information")

    try:
        with open(output_csv_file, 'w', newline='', encoding="utf-8") as csv_f:
            header = ['utterance']
            writer = csv.DictWriter(csv_f, fieldnames=header)
            writer.writeheader()
            utterances_all = []
            # remove any utterances that came back as Splats
            for activity in payload['activity']:
                if activity['splat'] == False:
                    utterances_all.append(activity["utterance"])
            clean_utterances = []
            if unique_records_only:
                # Reduce list to unique and preserve order
                for u in utterances_all:
                    clean_u = h.clean_utterance(u)
                    if clean_u not in clean_utterances:
                        clean_utterances.append(clean_u)
            else:
                for u in utterances_all:
                    clean_u = h.clean_utterance(u)
                    clean_utterances.append(clean_u)
            for u in clean_utterances:
                writer.writerow({'utterance': u})
        logger.info(f"Success, the utterances have been written to the output_csv_file {output_csv_file}")
    except Exception:
        if debug:
            exception_info = traceback.format_exc()
            error_msg = 'CRITICAL ERROR on writing results to csv file for get-user-activity\n{:s}'.format(exception_info)
            logger.critical(error_msg)
        else:
            logger.error(f"UNSUCCESSFUL on writing results to csv file for command get-user-activity.")
            logger.info(f"You can run this command with --debug to get more information")


@cli.command()
@click.option("--customer", "-c", required=True, is_flag=False, help="Provide the customer number and override env HUMA_CUSTOMER", default=None)
@click.option("--environment", "-e", required=True, is_flag=False, help="Provide the environment and override env HUMA_ENVIRONMENT_KEY", default=None)
@click.option("--duration", "-d",  is_flag=False, help="Provide the number (integer) of days you would like get user activity from default=15 (ex: 15 for the last 15 days of activity)", default=15)
@click.option("--no-cache/--cache", "-nc", help="Run with 'no cache' option", default=False)
@click.option("--no-up-cache/--up-cache", "-nu", help="Run with 'no up cache' option", default=False)
@click.option("--debug/--no-debug", "-d", help="Show debug logging", default=False)
def recache_from_activity(customer: str, environment: str, no_cache: bool, no_up_cache: bool, duration:int, debug: bool):
    """Recache all questions asked from a specified duration of time

    This will find all the questions from user activity that were asked in the past N days where N is a duration that can
    be specified by the user. Defaults to 15 days.

    Simple command that will run get-activity-dump, then automatically ask the questions retrieved back to huma server.

    Permissions

        This command can be run by huma logins only.\n

    Required

        -c CUSTOMER_NUMBER (e.g. 009)\n
        -e ENVIRONMENT (e.g. dev)
        -j ./output.json
        -f ./output.csv

    Options

        --duration n or -d n
        --no-cache/--cache
        --no-up-cache/--up-cache
        --debug/--no-debug\n

    Outputs

        The results of the tests are printed to the screen.\n

    Example

        huma recache-from-activity -c 009 -e dev -d 30 -nc -nu\n
    """
    level = logging.DEBUG if debug else logging.ERROR
    logger = get_logger(__name__, level=level)
    logger.info(f"Recaching questions asked in the past {duration} days...")
    results = []
    try:
        # call helper function to talk to huma-server
        logger.info(f"Retrieving activity dump...")
        payload = h.get_activity_dump(customer=customer,
            environment=environment,
            duration = duration
            )
    except Exception:
        if debug:
            exception_info = traceback.format_exc()
            error_msg = 'CRITICAL ERROR on retreiving activity from huma-platform on command recache-from-activity\n{:s}'.format(exception_info)
            logger.critical(error_msg)
        else:
            logger.error(f"UNSUCCESSFUL on retreiving activity from huma-platform on command recache-from-activity")
            logger.info(f"You can run this command with --debug to get more information")

    try:
        utterances_all = []
        # remove any utterances that came back as Splats
        for activity in payload['activity']:
            if activity['splat'] == False:
                utterances_all.append(activity["utterance"])
        clean_utterances = []
        # Reduce list to unique and preserve order
        for u in utterances_all:
            clean_u = h.clean_utterance(u)
            if clean_u not in clean_utterances:
                clean_utterances.append(clean_u)

        count = str(len(clean_utterances))
        logger.info(f"Found {count} unique utterances from the past {duration} days")
    except Exception:
        if debug:
            exception_info = traceback.format_exc()
            error_msg = 'CRITICAL ERROR on cleaning activity on huma-platform on command recache-from-activity.\n{:s}'.format(exception_info)
            logger.critical(error_msg)
        else:
            logger.error(f"UNSUCCESSFUL on cleaning activity on huma-platform on command recache-from-activity.")
            logger.info(f"You can run this command with --debug to get more information")

    logger.info(f"Begin asking questions...")
    for utterance in clean_utterances:
        try:
            question = h.adjust_utterance_for_cache(no_cache=no_cache, no_up_cache=no_up_cache, pre_utterance=utterance)
            logger.info(f"Asking Huma Server... {question}")
            # call helper function to talk to huma-server
            payload = h.ask_question(question=question,
                                        customer=customer,
                                        environment=environment)
            if isinstance(payload, dict):
                results.append(payload)
        except Exception:
            if debug:
                exception_info = traceback.format_exc()
                error_msg = 'CRITICAL ERROR on asking utterance {:s} on huma-platform on command recache-from-activity.\n{:s}'.format(question, exception_info)
                logger.critical(error_msg)
            else:
                logger.error(f"UNSUCCESSFUL on asking utterance {question} on huma-platform on command recache-from-activity..\n")
                logger.info(f"You can run this command with --debug to get more information")
            results.append({"question": question, "error": e})
    logger.info(f"Finished re-asking questions from the past {duration} days of activity")
    try:
        #TODO fails on write of json.  need to fix.
        results_json = {"recache_results":results}
        with open("recache_results.json", 'w', newline='', encoding="utf-8") as f:
            f.write(json.dumps(results_json, ensure_ascii=False, indent=4))
    except Exception:
        if debug:
            exception_info = traceback.format_exc()
            error_msg = 'CRITICAL ERROR on writing results to json file on command recache-from-activity.\n{:s}'.format(exception_info)
            logger.critical(error_msg)
        else:
            logger.error(f"UNSUCCESSFUL on writing results to json file on command recache-from-activity.\n")
            logger.info(f"You can run this command with --debug to get more information")


@cli.command()
@click.option("--output-json-file", "-j", required=True, is_flag=False, help="A json file to write the output into", default=None)
@click.option("--customer", "-c", required=True, is_flag=False, help="Provide the customer number and override env HUMA_CUSTOMER", default=None)
@click.option("--environment", "-e", required=True, is_flag=False, help="Provide the environment and override env HUMA_ENVIRONMENT_KEY", default=None)
@click.option("--target-environment", "-te", required=True, is_flag=False, help="Provide the target environment", default=None)
@click.option("--target-customer", "-tc", required=True, is_flag=False, help="Provide the target customer", default=None)
@click.option("--duration", "-du", is_flag=False, help="Provide the number (integer) of days you would like get user activity from default=15 (ex: 15 for the last 15 days of activity)", default=15)
@click.option("--no-cache/--cache", "-nc", help="Run with 'no cache' option", default=False)
@click.option("--no-up-cache/--up-cache", "-nu", help="Run with 'no up cache' option", default=False)
@click.option("--debug/--no-debug", "-d", help="Show debug logging", default=False)
def transfer_activity(customer: str, environment: str, target_customer: str, target_environment: str, no_cache: bool, no_up_cache: bool, duration:int, output_json_file: str, debug: bool):
    """Recache all questions from source environment to target environment (dev->stage, dev->prod, etc..)

    This will ask all the questions from user activity in the source environment in\n
    the target environment within the past N days where N is a duration that can\n
    be specified by the user. Defaults to 15 days.

    Command that will run get-activity-dump, then automatically ask the questions\n
    retrieved back to huma server for the target environment.

    Permissions

        This command can be run by huma logins only.\n

    Required

        -c CUSTOMER_NUMBER (e.g. 009)\n
        -e ENVIRONMENT (e.g. dev)
        -j ./output.json

    Options

        --duration n or -d n
        --no-cache/--cache or -nc
        --no-up-cache/--up-cache or -nu
        --debug/--no-debug or -d\n

    Outputs

        The results of the command are printed to the provided json file.\n

    Example

        huma transfer-activity -c 009 -e dev -te stage -d 30 -nc -nu\n

    """
    level = logging.DEBUG if debug else logging.ERROR
    logger = get_logger(__name__, level=level)
    logger.info(f"Recaching questions asked in the past {duration} days...")
    results = []
    try:
        # call helper function to talk to huma-server
        logger.info(f"Retrieving activity dump...")
        payload = h.get_activity_dump(customer=customer,
            environment=environment,
            duration = duration
            )
    except Exception:
        if debug:
            exception_info = traceback.format_exc()
            error_msg = 'CRITICAL ERROR on getting activity dump on command transfer-activity.\n{:s}'.format(exception_info)
            logger.critical(error_msg)
        else:
            logger.error(f"UNSUCCESSFUL on getting activity dump on command transfer-activity.\n")
            logger.info(f"You can run this command with --debug to get more information")


    try:
        logger.info(f"Begin cleaning and identifying unique on command transfer-activity...")
        utterances_all = []
        # remove any utterances that came back as Splats
        for activity in payload['activity']:
            if activity['splat'] == False:
                utterances_all.append(activity["utterance"])
        clean_utterances = []
        # Reduce list to unique and preserve order
        for u in utterances_all:
            clean_u = h.clean_utterance(u)
            if clean_u not in clean_utterances:
                clean_utterances.append(clean_u) 

        count = str(len(clean_utterances))
        logger.info(f"Found {count} unique utterances from the past {duration} days")
    except Exception:
        if debug:
            exception_info = traceback.format_exc()
            error_msg = 'CRITICAL ERROR on identifying unique utterances on command transfer-activity.\n{:s}'.format(exception_info)
            logger.critical(error_msg)
        else:
            logger.error(f"UNSUCCESSFUL on identifying unique utterances on command transfer-activity.\n")
            logger.info(f"You can run this command with --debug to get more information")


    logger.info(f"Begin asking questions...")
    for utterance in clean_utterances:
        try:
            question = h.adjust_utterance_for_cache(no_cache=no_cache, no_up_cache=no_up_cache, pre_utterance=utterance)
            logger.info(f"Asking Huma Server... {question}")
            # call helper function to talk to huma-server
            payload = h.ask_question(question=question,
                                        customer=target_customer,
                                        environment=target_environment)
            if isinstance(payload, dict):
                results.append(payload)
        except Exception:
            if debug:
                exception_info = traceback.format_exc()
                error_msg = 'CRITICAL ERROR on cleaning questions and asking them on command transfer-activity.\n{:s}'.format(exception_info)
                logger.critical(error_msg)
            else:
                logger.error(f"UNSUCCESSFUL on identifying unique utterances on command transfer-activity.\n")
                logger.info(f"You can run this command with --debug to get more information")
    logger.info(f"Finished re-asking questions from the past {duration} days of activity.")
    try:
        results_dict = { "transfer_recache_results" : results }
        with open(output_json_file, 'w', newline='', encoding="utf-8") as f:
            f.write(json.dumps(results_dict, ensure_ascii=False, indent=4))
    except Exception:
        logger.error(f"Could not write to output file {output_json_file} because error: {e}")
        if debug:
            exception_info = traceback.format_exc()
            error_msg = f"CRITICAL ERROR on writing summary json file {output_json_file} with error {exception_info}.\n"
            logger.critical(error_msg)
        else:
            logger.error(f"UNSUCCESSFUL on writing summary json file..\n")
            logger.info(f"You can run this command with --debug to get more information")

@cli.command()
@click.option("--customer", "-c", required=True, is_flag=False, help="Provide the customer number and override env HUMA_CUSTOMER", default=None)
@click.option("--environment", "-e", required=True, is_flag=False, help="Provide the environment and override env HUMA_ENVIRONMENT_KEY", default=None)
@click.option("--target-environment", "-te", required=True, is_flag=False, help="Provide the environment and override env HUMA_ENVIRONMENT_KEY", default=None)
@click.option("--namespace", "-ns", required=False, is_flag=False, help="Provide the redis-key name space filter.", default=":analyzer")
@click.option("--debug/--no-debug", "-d", help="Show debug logging", default=False)
def transfer_redis_keys(customer: str, environment: str, target_environment: str, namespace: str, debug: bool):
    """Copy the redis keys from one environment to a target environment (dev->stage, dev->prod, etc..)

    To target the analyzer keys use the default namespace filter of '*:analyzer'

    Permissions

        This command can be run by huma logins only.\n

    Required

        -c CUSTOMER_NUMBER (e.g. 009)\n
        -e ENVIRONMENT (e.g. dev)\n
        -te TARGET_ENVIRONMENT (.e.g. stage)

    Options

        --namespace-filter (e.g. '*:*' or '*:analyzer)\n
        --debug/--no-debug or -d\n

    Outputs

        The results of the command are printed to the screen.\n

    Example

        transfer-redis-keys --customer=001 --environment=dev --target-environment=stage --namespace '*:analyzer'\n
        if you have difficulty and are a mac or linux, first run `set -o noglob` and then when you are done `set +o noglob`

    """
    level = logging.DEBUG if debug else logging.ERROR
    logger = get_logger(__name__, level=level)
    results = {}
    if len(namespace) > 0 and ":" not in namespace:
        namespace = ":" + namespace
    try:
        # call helper function to talk to huma-server
        logger.info(f"Retrieving redis keys...")
        list_of_keys = h.get_redis_keys(customer=customer, environment=environment, namespace_filter=namespace)
        last_key_index = len(list_of_keys) - 1
        for index, key in enumerate(list_of_keys):
            logger.info("\rCopying key {} of {}                           ".format(index, last_key_index))
            value = h.get_redis_key(customer=customer, environment=environment, key=key)
            if value:
                copied_value = h.put_redis_key(customer=customer, environment=target_environment, key=key, value=value)

    except Exception:
        if debug:
            exception_info = traceback.format_exc()
            error_msg = 'CRITICAL ERROR on transfer-redis-keys command\n{:s}'.format(exception_info)
            logger.critical(error_msg)
        else:
            logger.error(f"UNSUCCESSFUL on transfer-redis-keys command.\n")
            logger.info(f"You can run this command with --debug to get more information")


@cli.command()
@click.option("--customer", "-c", required=True, is_flag=False, help="Provide the customer number and override env HUMA_CUSTOMER", default=None)
@click.option("--environment", "-e", required=True, is_flag=False, help="Provide the environment and override env HUMA_ENVIRONMENT_KEY", default=None)
@click.option("--key", "-k", required=True, is_flag=False, help="Provide the redis key you would like to retreive.", default=None)
@click.option("--color/--no-color", "-l", is_flag=True, required=False, help="Print the output with color codes", default=True)
@click.option("--debug/--no-debug", "-d", help="Show debug logging", default=False)
def get_redis_key(customer: str, environment: str, key: str, color: bool, debug: bool):
    """Get a redis entry by key.\n

    Keys stored in redis for analzyer use a namespace of ':analyzer'.  So typically, your key request\n
    would be '{up_cache_key}:analzyer'

    Permissions

        This command can be run by huma logins only.\n

    Required

        -c CUSTOMER_NUMBER (e.g. 009)\n
        -e ENVIRONMENT (e.g. dev)\n
        -k KEY\n

    Options

        --debug/--no-debug or -d\n

    Outputs

        The results of the command are printed to the screen.\n

    Example

        huma get-redis-key -c 009 -e dev -k "928409823928:analyzer"\n

    """
    level = logging.DEBUG if debug else logging.ERROR
    logger = get_logger(__name__, level=level)
    try:
        response = h.get_redis_key(customer=customer, environment=environment, key=key) or {}

        if not response.get("msg"):
            json_str = json.dumps(response.get('redis_key'), indent=4, sort_keys=True)
            if color:
                print(highlight(json_str, JsonLexer(), TerminalFormatter()))
            else:
                print("{}".format(json_str))
        else:
            msg = response.get("msg")
            logger.error(f"Get redis key failed because error {msg}")

    except Exception as e:
        logger.error(f"Get redis key failed because error {e}")



@cli.command()
@click.option("--customer", "-c", required=True, is_flag=False, help="Provide the customer number and override env HUMA_CUSTOMER", default=None)
@click.option("--environment", "-e", required=True, is_flag=False, help="Provide the environment and override env HUMA_ENVIRONMENT_KEY", default=None)
@click.option("--namespace", "-n", required=False, is_flag=False, help="Provide the redis namespace you would like to delete the keys.", default="*:analyzer")
@click.option("--color/--no-color", "-l", is_flag=True, required=False, help="Print the output with color codes", default=True)
@click.option("--debug/--no-debug", "-d", help="Show debug logging", default=False)
def clear_redis_keys(customer: str, environment: str, namespace: str, color: bool, debug: bool):
    """clear a redis keys by namespace or redis key name.\n

    currently this function have hard code namespace name to delete (:analyzer) namespace keys.\n

    Permissions

        This command can be run by huma logins only.\n

    Required

        -c CUSTOMER_NUMBER (e.g. 009)\n
        -e ENVIRONMENT (e.g. dev)\n
        -n NAMESPACE\n

    Options

        --debug/--no-debug or -d\n

    Outputs

        The results of the command are printed to the screen.\n

    Example

        huma clear-redis-keys -c 009 -e dev -namespace "234324d324d3:analyzer"\n

    """
    level = logging.DEBUG if debug else logging.ERROR
    logger = get_logger(__name__, level=level)
    try:
        response = h.clear_redis_keys(customer=customer, environment=environment, namespace=namespace) or {}

        if not response.get("msg"):
            json_str = json.dumps(response.get('keys_deleted'), indent=4, sort_keys=True)
            json_str = json_str + " keys deleted"
            if color:
                print(highlight(json_str, JsonLexer(), TerminalFormatter()))
            else:
                print("{}".format(json_str))
        else:
            msg = response.get("msg")
            logger.error(f"clear redis keys failed because error {msg}")

    except Exception as e:
        logger.error(f"Clear redis keys failed because error {e}")


@cli.command()
@click.option("--customer", "-c", required=True, is_flag=False, help="Provide the customer number and override env HUMA_CUSTOMER", default=None)
@click.option("--environment", "-e", required=True, is_flag=False, help="Provide the environment and override env HUMA_ENVIRONMENT_KEY", default=None)
@click.option("--key", "-k", required=True, is_flag=False, help="Provide the redis key you would like to put.", default=None)
@click.option("--value", "-v", required=True, is_flag=False, help="Provide the redis value you would like to put.", default=None)
@click.option("--color/--no-color", "-l", is_flag=True, required=False, help="Print the output with color codes", default=True)
@click.option("--debug/--no-debug", "-d", help="Show debug logging", default=False)
def put_redis_key(customer: str, environment: str, key: str, value: str, color: bool, debug: bool):
    """Put a redis entry by key.\n

    Keys stored in redis for analzyer use a namespace of ':analyzer'.  So typically, your key request\n
    would be '{up_cache_key}:analzyer'

    Permissions

        This command can be run by huma logins only.\n

    Required

        -c CUSTOMER_NUMBER (e.g. 009)\n
        -e ENVIRONMENT (e.g. dev)\n
        -k KEY\n
        -v VALUE\n

    Options

        --debug/--no-debug or -d\n

    Outputs

        The results of the command are printed to the screen.\n

    Example

        huma put-redis-key -c 009 -e dev -k "928409823928:analyzer" -v "{ \"abc\": \"def\"}"\n

    """
    level = logging.DEBUG if debug else logging.ERROR
    logger = get_logger(__name__, level=level)

    try:
        response = h.put_redis_key(customer=customer, environment=environment, key=key, value=value) or {}
        if not response.get("msg"):
            json_str = json.dumps(response.get('redis_key'), indent=4, sort_keys=True)
            if color:
                print(highlight(json_str, JsonLexer(), TerminalFormatter()))
            else:
                print("{}".format(json_str))
        else:
            msg = response.get("msg")
            logger.error(f"Put redis key failed because error ss {msg}")

    except Exception as e:
        logger.error(f"Put redis key failed because error {e}")

@cli.command()
@click.option("--yml-config-file-path", "-f", required=True, is_flag=False, help="A file path to store the main yml file", default=".")
@click.option("--customer", "-c", required=True, is_flag=False, help="Provide the customer number and override env HUMA_CUSTOMER", default=None)
@click.option("--environment", "-e", required=True, is_flag=False, help="Provide the environment and override env HUMA_ENVIRONMENT_KEY", default=None)
@click.option("--debug/--no-debug", "-d", help="Show debug logging", default=False)
@click.option("--version", "-v", help="Get the specific version, latest version is 0", default=0)
def get_up_config(customer: str, environment: str, yml_config_file_path: str, debug: bool, version: int):
    """Get the latest up_config.yml and it's referenced files and save them locally.\n

    Permissions

        This command can be run by huma logins only.\n

    Required

        -c CUSTOMER_NUMBER (e.g. 009)\n
        -e ENVIRONMENT (e.g. dev)\n
        -f (e.g. ~/mydirectory)

    Options

        --debug/--no-debug or -d\n
        -v version number (e.g 0 or 1, range from 0(latest) to 9(oldest))

    Outputs

        The results of the command are printed to the screen.\n

    Example

        huma get-up-config -c 009 -e dev -f . -v 0\n

    """
    level = logging.DEBUG if debug else logging.ERROR
    logger = get_logger(__name__, level=level)
    try:
        p = Path(yml_config_file_path)
        if not p.exists() or not p.is_dir():
            logger.error(f"get up config failed because error {yml_config_file_path} is not a valid directory.")
            exit(0)
        configs = h.get_up_config(customer=customer, environment=environment, version=version)

        if not configs.get("msg"):
            # confs = json.dumps(configs.get("up_config"))
            confs = configs.get("up_config")
            for conf in confs:
                for k,v in conf["payload"].items():
                    filename = k + ".yml"
                    fullpath = os.path.join(yml_config_file_path, filename)
                    if Path(fullpath).exists():
                        proceed: bool = h.ask_to_proceed_with_overwrite(fullpath)
                        if not proceed:
                            logger.info(f"stopping without write due to file already exists. Please move the conflicting files and try again.")
                            exit(0)
                    with open(fullpath, "w") as f:
                        f.write(v)
                        logger.info(f"Saving {filename} to {yml_config_file_path}.")
        else:
            msg = configs.get("msg")
            logger.error(f"Get up config files failed because error {msg}")

    except Exception as e:
        logger.error(f"Get up config files failed because error {e}")


@cli.command()
@click.option("--up-config-yml", "-f", required=False, is_flag=False, help="A path to a up_config.yml file with referenced module config files.", default="up_config.yml")
@click.option("--customer", "-c", required=True, is_flag=False, help="Provide the customer number and override env HUMA_CUSTOMER", default=None)
@click.option("--environment", "-e", required=True, is_flag=False, help="Provide the environment and override env HUMA_ENVIRONMENT_KEY", default=None)
@click.option("--debug/--no-debug", "-d", help="Show debug logging", default=False)
def put_up_config(customer: str, environment: str, up_config_yml: str, debug: bool):
    """
    Gather up_config.yml and referenced files and send to s3 and redis for the UP to use as its current config.\n

    Permissions

        This command can be run by huma logins only.\n

    Required

        -c CUSTOMER_NUMBER (e.g. 009)\n
        -e ENVIRONMENT (e.g. dev)\n
        -f (e.g. ~/mydirectory/up_config.yml)\n

    Options

        --debug/--no-debug or -d\n

    Outputs

        The results of the command are saved to the directory of the provided yml file.\n

    Example

        huma put-up-config -c 009 -e dev -f ~/mydirectory/up_config.yml\n
    """
    level = logging.DEBUG if debug else logging.ERROR
    logger = get_logger(__name__, level=level)
    try:
        response = h.put_up_config(customer=customer, environment=environment, filepath=up_config_yml)
        if response == True:
            logger.info(f"Put up config files succeeded.")
        else:
            logger.error(f"Put up config files failed because error {response}")
    except Exception as e:
        logger.error(f"Put up config files failed because error {e}")
    pass

def clean_analyzer_logs(logs_object):
    clean_logs = {}
    clean_logs["messages"] = []
    logs = logs_object.get("logs")
    if isinstance(logs, dict) and len(logs) > 0:
        for events in logs["logs"]["events"]:
            if isinstance(events, list):
                for event_group in events:
                    for item in event_group:
                        clean_logs["messages"].append(item.get("message"))
            if isinstance(events, dict):
                clean_logs["messages"].append(events.get("message"))
    clean_logs["exit_code"] = logs_object.get("exitCode")
    clean_logs["status_reason"] = logs_object.get("statusReason")
    return clean_logs


@cli.command()
@click.option("--input-file", "-i", required=True, is_flag=False, help="A yaml input file with test configuration.  See test types and sample input file.", default=None)
@click.option("--output-file", "-o", is_flag=False, help="A yaml output file used to save the results to.", default=None)
@click.option("--hard-exit-on-fail", "-e", is_flag=True, help="Exits with exit code 1 on failed tests.", default=False)
@click.option("--autostart/--no-autostart", "-a", is_flag=True, help="If system is shut, turn on the system resources, execute smoke tests and shut them down", default=False)
@click.option("--recursion/--no-recursion", "-r", is_flag=True, help="Recursively check the answer data to check status of further question links.", default=False)
@click.option("--recursion-depth", "-rd", help="it is a number which represents the limit level upto which recursion to be performed. 0 means no limit, default is 10", default=10)
@click.option("--debug/--no-debug", "-d", help="Show debug logging", default=False)
@click.option("--no-cache", "-nc", help="If True, checks for utterances with no cache option", default=False)
def smoke_tests(input_file: str, output_file: str, hard_exit_on_fail: bool, debug: bool, autostart: bool, recursion: bool, recursion_depth: int, no_cache: bool) -> Callable:
    """
    Perform a set of system tests as provided for in the input-file.\n

    Last updated 10/28/2021 09:58:00 PT

    Sample input-file content:

        [\n
            { "customer":"009", "environment": "dev", "tests":["dashboard-questions"] }\n
        ]\n
        There is a sample config file here: https://github.com/humahq/huma-cli/blob/main/sample_test_config_example.json\n

    Outputs

        The results of the tests are printed to the screen.\n
        If an output-file was provided, the detailed results are placed in the output-file and summary results are placed in output-file.csv\n
        If an output file was provided and there are errors, results of the error questions are place in the out-file_errors.\n

    Tests

        https://humahq.stoplight.io/docs/huma-platform-cli/ZG9jOjI1OTc3Mzc2-smoke-tests

    Example

        huma smoke-tests --input-file ./smoke_tests_config.json  --output-file ./test_results.json

    Returns

        Exit 0 if all tests are successful, otherwise exit 1\n
    """
    level = logging.DEBUG if debug else logging.ERROR
    logger = get_logger(__name__, level=level)
    test_results = {}
    # perform tests
    try:
        configs = h.get_configs(input_file)
        system_info = []
        # this gets executed if we pass autostart parameter as True, otherwise simple smoke tests execution continues.
        if autostart == 'True':
            system_info = h.spin_systems_for_smoke_tests(configs)
            print("system info ", system_info)
        # get the tokens before parallelizing so that the processes can proceed without walking on one another
        # in attempting to get auth tokens.
        for config in configs:
            h.login_with_config(config)
        test_results = h.run_test_process_manager(configs, recursion, recursion_depth, no_cache)

        # if system_info returned is not empty, return them to initial state and turn the system services down 
        if system_info:
            logger.info(f"Stopping system services for all different clients and environments which were started now.")
            for system in system_info:
                try:
                    h.stop_system_activity(customer=system['customer'], environment=system['environment'])
                except Exception as e:
                    logger.error(f"Could not stop the system services because {e}.")
        else:
            logger.info(f"System services for all different clients and environments are up and working. Getting results.")

    except Exception as e:
        logger.error(f"The smoke-tests failed to fully run and exited because {e}.")
        if hard_exit_on_fail:
            exit(1)

    # print to screen
    try:
        if test_results:
            print(h.bcolors.HEADER + "summary results:" + h.bcolors.CLEAR)
            print(h.bcolors.HEADER + "customer-environment       test-name          pass/fail     error_data     " + h.bcolors.CLEAR)
            print(h.bcolors.HEADER + "---------------------------------------------------------------------------" + h.bcolors.CLEAR)
            for env in test_results:
                environment = env.get("cust-env").center(20, " ")
                for test in env.get("tests"):
                    class_name = test.get("class_name").center(20, " ")
                    error = test.get("error")
                    pass_fail = "fail" if error else "pass"
                    pass_fail_c = pass_fail.center(20, " ")
                    error_data = str(test.get("error_data")) or None
                    error_data = error_data.center(20, " ") if error_data else None
                    color = h.bcolors.OKGREEN if pass_fail == "pass" else h.bcolors.FAIL
                    clear = h.bcolors.CLEAR
                    print(f"{color}{environment}{class_name}{pass_fail_c}{error_data}{clear}")
    except Exception:
        logger.error(f"The print of summary to screen file failed because {e}.")
        if hard_exit_on_fail:
            exit(1)

    # write yaml detailed output
    try:
        if output_file and test_results:
            with open(output_file, "w") as o:
                h.dump_yaml(test_results, o)
            print(f"Full results written to: {h.bcolors.OKBLUE}{output_file}{h.bcolors.CLEAR}")

    except Exception as e:
        logger.error(f"The output detail file failed because {e}.")
        if hard_exit_on_fail:
            exit(1)

    # write yaml detailed output for errors only
    try:
        if output_file and test_results:
            p = PurePath(output_file)
            output_file_path = p.parent
            test_errors = []
            if len(test_results) != 0:
                for test_result in test_results:
                    test_result_errors = {}
                    test_result_errors["cust-env"] = test_result["cust-env"]
                    test_result_errors["tests"] = []
                    tests = test_result.get("tests", [])
                    test_errors = []
                    for test in tests:
                        output_file_name = p.stem + test["test_case_name"] + "_errors" + p.suffix
                        errors_output_file = os.path.join(output_file_path, output_file_name)
                        test_stub = { "test_name": test["test_case_name"],
                                    "test_description": test["test_description"],
                                    "error": test["error"],
                                    "error_data":
                                    test["error_data"],
                                    "result": [] }
                        if type(test.get("result")) != bool:
                            for r in test.get("result"):
                                if r["visual"]["type"] == 'error' \
                                    or r.get("answer_type") == "splat":
                                        if r.get("job_id"):
                                            cust = test_result["cust-env"].split("-")[0]
                                            env = test_result["cust-env"].split("-")[1]
                                            logs_object = h.get_analyzer_logs(customer=cust, environment=env, job_id=r.get("job_id"))
                                            if logs_object:
                                                c_logs = clean_analyzer_logs(logs_object)
                                                r["analyzer_logs"] = c_logs
                                        test_errors.append(r)
                        if len(test_errors) > 0 or test_stub.get("error") == True:
                            test_stub["result"].append(test_errors)
                            test_result_errors["tests"].append(test_stub)
                            try:
                                with open(errors_output_file, "w") as o:
                                    h.dump_yaml(test_result_errors, o)
                                print(f"Error summary for errors only: {h.bcolors.OKBLUE}{errors_output_file}{h.bcolors.CLEAR}")
                            except:
                                print(f"Was not able to print to {h.bcolors.OKBLUE}{errors_output_file}{h.bcolors.CLEAR}")

    except Exception as e:
        logger.error(f"The yaml output detail file failed because {e}.")
        if hard_exit_on_fail:
            exit(1)

    # write summary csv
    try:
        if output_file and test_results:
            output_file_csv = output_file.replace(".json", ".csv")
            output_file_csv = output_file_csv.replace(".yaml", ".csv")
            output_file_csv = output_file_csv.replace(".yml", ".csv")

            with open(output_file_csv, 'w', newline='', encoding="utf-8") as csv_f:
                header = ['customer-environment', "test-name", "pass/fail", "error data"]
                writer = csv.DictWriter(csv_f, fieldnames=header)
                writer.writeheader()

                for env in test_results:
                    environment = env.get("cust-env")
                    for test in env.get("tests"):
                        test_name = test.get("test_case_name")
                        error = test.get("error")
                        pass_fail = "fail" if error else "pass"
                        pass_fail_c = pass_fail
                        error_data = "{}".format(test.get("error_data")) or None
                        writer.writerow( {"customer-environment": environment, "test-name": test_name, "pass/fail": pass_fail, "error data": error_data})
            print(f"Summary results: {h.bcolors.OKBLUE}{output_file_csv}{h.bcolors.CLEAR}")

    except Exception as e:
        print(f"The csv export file failed to write because {e}.")
        if hard_exit_on_fail:
            exit(1)

    # hard exit on fail (for github action)
    error = None
    if test_results:
        for env in test_results:
            environment = env.get("cust-env").center(20, " ")
            for test in env.get("tests"):
                error = test.get("error") or error
    if error and hard_exit_on_fail:
        sys.exit(1)


@cli.command()
def run_tests():
    """
    Run huma-cli tests.

    Required
        You must export these environment variables HUMA_CUSTOMER,  HUMA_ENVIRONMENT_KEY, HUMA_USERNAME, HUMA_PASSWORD

    Returns
        An error if any of the tests fail.
    """
    level = logging.DEBUG
    logger = get_logger(__name__, level=level)
    customer = os.environ.get("HUMA_CUSTOMER", '009')
    environment = os.environ.get("HUMA_ENVIRONMENT_KEY", 'dev')
    target_environment = "dev"

    assert customer
    assert environment
    assert target_environment

    runner = CliRunner()

    result = runner.invoke(get_user_activity, args=["--customer",
                                                    f"{customer}",
                                                    "--environment",
                                                    f"{environment}",
                                                    "--unique-records-only",
                                                    "./get-user-activity.json",
                                                    "./get-user-activity.csv"])
    os.remove("./get-user-activity.json")
    os.remove("./get-user-activity.csv")
    assert result.exit_code == 0

    result = runner.invoke(transfer_activity, args=["--customer",
                                                    f"{customer}",
                                                    "--environment",
                                                    f"{environment}",
                                                    "-te",
                                                    f"{target_environment}",
                                                    "./transfer_activity_output.json"])
    os.remove("./transfer_activity_output.json")
    assert result.exit_code == 0

    sample_configs = [
        { "customer":"009", "environment": "dev", "token" : "5yFYB6h09swAk85", "tests":["dashboard_questions"] }
    ]

@cli.command()
@click.option("--customer", "-c", is_flag=False, required=True, help="Provide the customer number and override env HUMA_CUSTOMER", default=None)
@click.option("--environment", "-e", is_flag=False, required=True, help="Provide the environment and override env HUMA_ENVIRONMENT_KEY", default=None)
@click.option("--debug/--no-debug", "-d", help="Show debug logging", default=False)
@click.option("--autostart", "-f", help="If system is shut, turn on the system resources.", default=False)
def get_batch_minimum_vcpu(customer: str, environment: str, debug: bool, autostart: bool):
    """ gets the minimum vcpu for the customer on specified environment and instance type """
    level = logging.DEBUG if debug else logging.ERROR
    logger = get_logger(__name__, level=level)
    try:
        # call helper function to talk to huma-server
        logger.info(f"Retrieving minimum vcpu...")
        payload = h.get_minimum_vcpu(customer=customer,
                                      environment=environment,
                                      autostart=autostart
                                      )
        if 'minimum_vcpus' in payload:
            logger.info(f"successfully retrieved huma-server response")
            logger.info(f"-------------------------------------------\n")
            logger.info(f"Batch min vCPUs for customer {customer} on {environment} environment for intsanceType c5 are {payload['minimum_vcpus']}\n")
        else:
            logger.error(json.dumps(payload['message'], indent=4, sort_keys=True))

    except Exception as e:
        logger.error(f"Could not get the minimum vcpu: {e}")


@cli.command()
@click.option("--customer", "-c", is_flag=False, required=True, help="Provide the customer number and override env HUMA_CUSTOMER", default=None)
@click.option("--environment", "-e", is_flag=False, required=True, help="Provide the environment and override env HUMA_ENVIRONMENT_KEY", default=None)
@click.option("--minvcpu", "-min", is_flag=False, required=True, help="Provide the min vcpu count to be set on g5 instance type on compute environment.", default=None)
@click.option("--debug/--no-debug", "-d", help="Show debug logging", default=False)
def set_batch_minimum_vcpu(customer: str, environment: str, minvcpu: int, debug: bool, autostart: bool):
    """ sets the minimum vcpu for the customer on specified environment and intance type """
    try:
        # call helper function to talk to huma-server
        level = logging.DEBUG if debug else logging.ERROR
        logger = get_logger(__name__, level=level)
        logger.info(f"Setting minimum vcpu...")
        payload = h.set_minimum_vcpu(customer=customer,
                                      environment=environment,
                                      minvcpu=minvcpu,
                                      autostart=autostart
                                      )
        if 'minimum_vcpus' in payload:
            logger.info(f"successfully retrieved huma-server response")
            logger.info(f"-------------------------------------------\n")
            logger.info(f"{payload['minimum_vcpus']} min vCPUs for customer {customer} on {environment} compute environment are set.\n")
        else:
            logger.error(json.dumps(payload['message'], indent=4, sort_keys=True))
    except Exception as e:
        logger.error(f"Could not set the minimum vcpu: {e}")



@cli.command()
@click.option("--customer", "-c", is_flag=False, required=True, help="Provide the customer number and override env HUMA_CUSTOMER", default=None)
@click.option("--environment", "-e", is_flag=False, required=True, help="Provide the environment and override env HUMA_ENVIRONMENT_KEY", default=None)
@click.option("--debug/--no-debug", "-d", help="Show debug logging", default=False)
def get_system_status(customer: str, environment: str, debug: bool):
    """ gets the system status for the customer on specified environment """
    try:
        # call helper function to talk to huma-server
        level = logging.DEBUG if debug else logging.ERROR
        logger = get_logger(__name__, level=level)
        logger.info(f"Getting system status...")
        payload = h.get_system_status(customer=customer, environment=environment)

        if 'results' in payload:
            click.echo(f"""
            \nSystem status for customer {customer} on {environment} environment is \n\n
            All ECS Services and RDS Instances Running - {payload['are_all_services_available']} \n
            Are servers shutting down - {payload['are_servers_shuting_down']}\n
            Are servers starting up - {payload['are_servers_starting_up']}\n
            Are RDS Instances shutting down - {payload['are_rds_instances_shutting_down']}\n
            Are RDS Instances starting up - {payload['are_rds_instances_starting_up']}\n
            """)
        else:
            logger.error(f"Error retrieving system status.")

    except Exception as e:
        logger.error(f"Could not get the system status: {e}")

@cli.command()
@click.option("--customer", "-c", is_flag=False, required=True, help="Provide the customer number and override env HUMA_CUSTOMER", default=None)
@click.option("--environment", "-e", is_flag=False, required=True, help="Provide the environment and override env HUMA_ENVIRONMENT_KEY", default=None)
@click.option("--debug/--no-debug", "-d", help="Show debug logging", default=False)
def stop_system_if_inactive(customer: str, environment: str, debug: bool):
    """ Stops the system services if the inactivity found for last 1 hour for the customer on specified environment """
    try:
        # call helper function to talk to huma-server
        level = logging.DEBUG if debug else logging.ERROR
        logger = get_logger(__name__, level=level)
        logger.info(f"Getting system activity...")
        payload = h.get_system_activity(customer=customer,
                                      environment=environment
                                      )
        if 'status' in payload:
            logger.info(f"successfully retrieved huma-server response")
            logger.info(f"-------------------------------------------\n")
            logger.info(f"Customer {customer} on {environment} environment - {payload['status']}")
        else:
            logger.error(f"{payload['status']}")

    except Exception as e:
        logger.error(f"Could not get the system activity: {e}")


@cli.command()
@click.option("--customer", "-c", is_flag=False, required=True, help="Provide the customer number and override env HUMA_CUSTOMER", default=None)
@click.option("--environment", "-e", is_flag=False, required=True, help="Provide the environment and override env HUMA_ENVIRONMENT_KEY", default=None)
@click.option("--debug/--no-debug", "-d", help="Show debug logging", default=False)
def stop_system(customer: str, environment: str, debug: bool):
    """ Stops the system services (Utterances, suggestions, user-activity, rasa), stops the DB Instances of postgres and docdb for the customer on specified environment """
    try:
        # call helper function to talk to huma-server
        level = logging.DEBUG if debug else logging.ERROR
        logger = get_logger(__name__, level=level)
        logger.info(f"Stopping system...")
        payload = h.stop_system_activity(customer=customer,
                                      environment=environment
                                      )
        
        logger.info(f"successfully retrieved huma-server response")
        logger.info(f"-------------------------------------------\n")
        logger.info(f"Stopped system services for Customer {customer} on {environment} environment - {payload}")
        

    except Exception as e:
        logger.error(f"Could not stop the system services: {e}")

@cli.command()
@click.option("--customer", "-c", is_flag=False, required=True, help="Provide the customer number and override env HUMA_CUSTOMER", default=None)
@click.option("--environment", "-e", is_flag=False, required=True, help="Provide the environment and override env HUMA_ENVIRONMENT_KEY", default=None)
@click.option("--debug/--no-debug", "-d", help="Show debug logging", default=False)
def start_system(customer: str, environment: str, debug: bool):
    """ Starts the system services (Utterances, suggestions, user-activity, rasa), stops the DB Instances of postgres and docdb for the customer on specified environment """
    try:
        # call helper function to talk to huma-server
        level = logging.DEBUG if debug else logging.ERROR
        logger = get_logger(__name__, level=level)
        payload = h.start_system_activity(customer=customer,
                                    environment=environment
                                    )

        logger.info(f"Started system services for Customer {customer} on {environment} environment")
        print(f"{payload}")

    except Exception as e:
        logger.error(f"Could not start the system services: {e}")

@cli.command()
@click.option("--customer", "-c", required=True, is_flag=False, help="Provide the customer number and override env HUMA_CUSTOMER", default=None)
@click.option("--environment", "-e", required=True, is_flag=False, help="Provide the environment and override env HUMA_ENVIRONMENT_KEY", default=None)
@click.option("--user-id", "-u", required=True, is_flag=False, help="Provide a user id", default=None)
@click.option("--output-json-file", "-o", required=True, is_flag=False, help="A json file to write the output into", default=None)
@click.option("--debug/--no-debug", "-d", help="Show debug logging", default=False)
def get_latest_user_context(customer: str, environment: str, user_id: str, output_json_file: str, debug: bool):
    """
    Gets the latest user context for a user (collapsed).

    Required

        -c CUSTOMER_NUMBER (e.g. 009)\n
        -e ENVIRONMENT (e.g. dev)\n
        -u USER_ID (e.g. 31e66159-d76a-4f42-add2-93ac8d2389eb)\n
        -o OUTPUT_JSON_FILE (e.g. output.json)\n

    Options

        --debug/--no-debug\n

    Example

        huma get_latest_user_context -c 009 -e dev -u 31e66159-d76a-4f42-add2-93ac8d2389eb -o ./output.json\n
    """

    try:
        level = logging.DEBUG if debug else logging.ERROR
        logger = get_logger(__name__, level=level)
        payload = h.get_latest_user_context_helper(customer=customer, environment=environment, user_id=user_id)

        with open(output_json_file, 'w', newline='', encoding="utf-8") as f:
            f.write(json.dumps(payload, ensure_ascii=False, indent=4))

    except Exception as e:
        logger.error(f"Could not write to output file {output_json_file} because error: {e}")
        if debug:
            exception_info = traceback.format_exc()
            error_msg = f"CRITICAL ERROR on writing summary json file {output_json_file} with error {exception_info}.\n"
            logger.critical(error_msg)
        else:
            logger.error(f"UNSUCCESSFUL on writing summary json file..\n")
            logger.info(f"You can run this command with --debug to get more information")

@cli.command()
@click.option("--customer", "-c", required=True, is_flag=False, help="Provide the customer number and override env HUMA_CUSTOMER", default=None)
@click.option("--environment", "-e", required=True, is_flag=False, help="Provide the environment and override env HUMA_ENVIRONMENT_KEY", default=None)
@click.option("--user-id", "-u", required=True, is_flag=False, help="Provide a user id", default=None)
@click.option("--output-json-file", "-o", required=True, is_flag=False, help="A json file to write the output into", default=None)
@click.option("--debug/--no-debug", "-d", help="Show debug logging", default=False)
def get_all_user_context(customer: str, environment: str, user_id: str, output_json_file: str, debug: bool):
    """
    Gets the all the user context for a user in a uncollapsed manner.

    Required

        -c CUSTOMER_NUMBER (e.g. 009)\n
        -e ENVIRONMENT (e.g. dev)\n
        -u USER_ID (e.g. 31e66159-d76a-4f42-add2-93ac8d2389eb)\n
        -o OUTPUT_JSON_FILE (e.g. output.json)\n

    Options

        --debug/--no-debug\n

    Example

        huma get_all_user_context -c 009 -e dev -u 31e66159-d76a-4f42-add2-93ac8d2389eb -o ./output.json\n
    """

    try:
        level = logging.DEBUG if debug else logging.ERROR
        logger = get_logger(__name__, level=level)
        payload = h.get_all_user_context_helper(customer=customer, environment=environment, user_id=user_id)

        with open(output_json_file, 'w', newline='', encoding="utf-8") as f:
            f.write(json.dumps(payload, ensure_ascii=False, indent=4))

    except Exception as e:
        logger.error(f"Could not write to output file {output_json_file} because error: {e}")
        if debug:
            exception_info = traceback.format_exc()
            error_msg = f"CRITICAL ERROR on writing summary json file {output_json_file} with error {exception_info}.\n"
            logger.critical(error_msg)
        else:
            logger.error(f"UNSUCCESSFUL on writing summary json file..\n")
            logger.info(f"You can run this command with --debug to get more information")
        
@cli.command()
@click.option("--customer", "-c", required=True, is_flag=False, help="Provide the customer number and override env HUMA_CUSTOMER", default=None)
@click.option("--environment", "-e", required=True, is_flag=False, help="Provide the environment and override env HUMA_ENVIRONMENT_KEY", default=None)
@click.option("--user-id", "-u", required=True, is_flag=False, help="Provide a user id", default=None)
@click.option("--input-json-file", "-i", required=True, is_flag=False, help="A file path to store the user context json file", default=".")
@click.option("--debug/--no-debug", "-d", help="Show debug logging", default=False)
def create_user_context(customer: str, environment: str, user_id: str, input_json_file: str, debug: bool):
    """
    Creates a new user context object for a user.

    Required

        -c CUSTOMER_NUMBER (e.g. 009)\n
        -e ENVIRONMENT (e.g. dev)\n
        -u USER_ID (e.g. 31e66159-d76a-4f42-add2-93ac8d2389eb)\n
        -i INPUT_JSON_FILE (e.g. input.json)\n

    Options

        --debug/--no-debug\n

    Example

        huma create_user_context -c 009 -e dev -u 31e66159-d76a-4f42-add2-93ac8d2389eb -i ./input.json\n
    """

    level = logging.DEBUG if debug else logging.ERROR
    logger = get_logger(__name__, level=level)
    try:
        response = h.create_user_context(customer=customer, environment=environment, user_id=user_id, filepath=input_json_file)

        if response:
            logger.info(f"Create user context succeeded with input file {input_json_file}.")
        else:
            logger.error(f"Create user context failed with input file {input_json_file}.")
    except Exception as e:
        logger.error(f"Could not create user context with {input_json_file} because error: {e}")
        if debug:
            exception_info = traceback.format_exc()
            error_msg = 'CRITICAL ERROR on create-user-context\n{:s}'.format(exception_info)
            logger.critical(error_msg)
        else:
            logger.error(f"UNSUCCESSFUL on command create-user-context.")
            logger.info(f"You can run this command with --debug to get more information")

# """
#     Put the specified suggestions list into an enviroment.

#     Permissions

#         This command can be run by huma logins only.\n

#     Required

#         -c CUSTOMER_NUMBER (e.g. 009)\n
#         -e ENVIRONMENT (e.g. dev)

#     Options

#         --debug/--no-debug\n

#     Example

#         huma put_suggestions -c 009 -e dev -i ./suggestions.json\n
#     """


if __name__ == '__main__':
    cli()
