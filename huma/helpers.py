from logging import error
from os import wait
import json
from typing import List
from huma_sdk.sdk import huma_sdk
from huma_sdk.utils.log_utils import get_logger
from deepdiff import DeepDiff
import re
import sys
from schema import Schema, And, Use, Optional, SchemaError
from huma.tests import Tests
import concurrent.futures
from pathlib import Path, PurePath
from ruamel.yaml import YAML
import requests
import logging
import time
LOG_MSG_DIVIDER = f"-------------------------------------------"
class bcolors:
    HEADER = '\033[95m'
    OKBLUE = '\033[94m'
    OKCYAN = '\033[96m'
    OKGREEN = '\x1b[0;32m'
    WARNING = '\033[93m'
    FAIL = '\033[91m'
    CLEAR = '\033[0m'
    BOLD = '\033[1m'
    UNDERLINE = '\033[4m'

def format_log_msg(msg):
    msg = "\n" + LOG_MSG_DIVIDER + "\n" + msg + "\n" + LOG_MSG_DIVIDER
    return msg


def automated_tests(autostart, config):
    if autostart:
        pass
    print(config)

# decorator to check status of server
def check_server_status(func):
    logger = get_logger(__name__, level=logging.INFO)
    def status(*args, **kwargs):
        is_spinning_system = True
        autostart = True if 'autostart' in kwargs and kwargs['autostart']=='True' else False
        if args:
            customer = args[0]['customer']
            environment = args[0]['environment']
        if kwargs:
            environment = kwargs['environment']
            customer = kwargs['customer']
        log_msg = format_log_msg(f"Checking if system for customer {customer} on environment {environment} is up or not...")
        logger.info(log_msg) 
        try:
            activity = get_system_status(customer=customer, environment=environment)
        except Exception as e:
            sys.exit(f"Could not get system status because {e}.") 

        if activity['are_all_services_available']:
            log_msg = format_log_msg(f"""
            System is up and running. 
            Fetching results for the command...
            """)
            logger.info(log_msg)
            # getting the returned value
            returned_value = func(*args, **kwargs)
            return returned_value
        elif autostart: # start the system    

            # in case server is recently shut down, it takes time to shut down all services.   
            # we will wait for the services to shut down before starting them up again
            is_server_shutting_down = True
            is_server_down_initially = False
            while is_server_shutting_down:
                activity = get_system_status(customer=customer, environment=environment)

                if activity['are_servers_shuting_down'] or activity['are_rds_instances_shutting_down']:
                    logger.info(f"Currently services are being shut down. It can take some time. Please wait before we continue with commands...")
                    time.sleep(20) # wait for servers to shut down and check status every 20 seconds
                    # sys.exit(f"Servers are shutting down. Please wait.") 
                else:
                    is_server_shutting_down = False

            if activity['are_all_services_available'] == False:
                    is_server_down_initially = True
            # start system services if services are not working
            start_system_activity(customer, environment) # spin up system

            log_msg = format_log_msg(f"""
            System is spinning up. 
            It can take some time.
            """)

            while is_spinning_system:
                print("waiting for system to be active to execute commands......")
                activity = get_system_status(customer=customer, environment=environment)
                if activity['are_all_services_available']:
                    is_spinning_system = False

                    returned_value = func(*args, **kwargs)

                    if is_server_down_initially:
                        logger.info(f"System services will shutdown again after execution of commands.")
                        stop_system_activity(customer, environment) # spin down system

                    return returned_value
                else:
                    time.sleep(10) # wait 10 seconds and check for system status again
            
            
        elif activity['are_servers_shuting_down'] or activity['are_rds_instances_shutting_down']: # if system is being shut down, wait for completion and hold further executions
            log_msg = format_log_msg(f"""
            System is spinning down. 
            Please wait for the process to execute completely before taking further actions. 
            You can check system status by using get-system-status command.
            """)
            logger.info(log_msg)
            sys.exit()
        elif activity['are_servers_starting_up'] or activity['are_rds_instances_starting_up']: # if system is being shut down, wait for completion and hold further executions
            log_msg = format_log_msg(f"""
            System is spinning up. 
            Please wait for the process to execute completely before taking further actions. 
            You can check system status by using get-system-status command.
            """)
            logger.info(log_msg)
            sys.exit()        
        else:
            log_msg = format_log_msg(f"""
            System is shut down and some cli commands can not be executed at this time.
            Please start system using command start-system or use autostart parameter with the command to start the system.
            """)
            sys.exit(log_msg) 
    # returning the value to the original frame    
    return status


def whoami():
    return sys._getframe(1).f_code.co_name

def ask_to_proceed_with_overwrite(filepath):
    """Produces a prompt asking about overwriting a file.

    # Arguments
        filepath: the path to the file to be overwritten.

    # Returns
        True if we can proceed with overwrite, False otherwise.
    """
    get_input = input
    overwrite = get_input('[WARNING] %s already exists - overwrite? '
                          '[y/n]' % (filepath))
    while overwrite not in ['y', 'n']:
        overwrite = get_input('Enter "y" (overwrite) or "n" (cancel).')
    if overwrite == 'n':
        return False
    return True

def diff_data(data, new_data) -> dict:
    exclude_paths = ["root['suggested_questions']"]
    exclude_paths += ["root['cache_key']"]
    exclude_paths += ["root['output_hints']['explanation_human']"]
    exclude_paths += ["root['utterances']"]
    exclude_paths += ["root['op_defs']"]
    exclude_paths += ["root['date_column']"]
    exclude_paths += ["root['data']['utterance']"]
    exclude_paths += ["root['utterance']"]
    exclude_paths += ["root['canonical_form']"]
    exclude_paths += ["root['confidence']"]
    diff = DeepDiff(data, new_data, exclude_paths=exclude_paths, ignore_order=True)

    return diff


def adjust_utterance_for_cache(no_cache: bool, no_up_cache: bool, pre_utterance: str) -> str:
    # adjust question to adhere to command line option for no cache
    no_cache_list = re.findall(pre_utterance, "no cache", re.IGNORECASE)
    if len(no_cache_list) == 0 and no_cache:
        pre_utterance += " no cache"
    elif len(no_cache_list) > 0 and not no_cache:
        pre_utterance = re.sub("no cache", "", re.IGNORECASE)
    # adjust question to adhere to command line option for no up cache
    no_up_cache_list = re.findall(pre_utterance, "no up cache", re.IGNORECASE)
    if len(no_up_cache_list) == 0 and no_up_cache:
        pre_utterance += " no up cache"
    elif len(no_up_cache_list) > 0 and not no_up_cache:
        pre_utterance = re.sub("no upcache", "", re.IGNORECASE)
    return pre_utterance

def logout(customer=None, environment=None):
    huma_sdk_instantiated = huma_sdk(customer=customer, environment=environment)
    logged_out = huma_sdk_instantiated.logout()
    return logged_out

# @check_server_status
def login_with_config(config):
    logger = get_logger(__name__)
    try:
        huma_sdk_instantiated = huma_sdk(customer=config["customer"], environment=config["environment"], cli_token=config.get("cli_token", None))
        token, error = huma_sdk_instantiated.token_manager.get_token()
        return True if token else False
    except Exception as e:
        customer = config.get("customer")
        environment = config.get("environment")
        cust_env = customer + "-" + environment
        logger.error(f"{cust_env} Failed to login and get an auth token, because {e}")
        return False

def login(customer=None, environment=None):
    logger = get_logger(__name__)
    try:
        huma_sdk_instantiated = huma_sdk(customer=customer, environment=environment)
        return True if huma_sdk_instantiated.login() else False
    except Exception as e:
        logger.error(f"Failed to login and get an auth token, because {e}")
        return False

def clean_utterance(u):
    # 1. remove phrase 'new'
    # 2. remove phrase 'no cache'
    # 3. remove phrase 'no up cache'
    # 4. strip outer whitespace
    u = u.strip()
    if u.endswith(' new') or u.endswith(' old') :
        clean_u = u[:-4]
    else:
        clean_u = u
    clean_u = clean_u.replace("no cache", "")
    clean_u = clean_u.replace("no up cache", "")
    clean_u = clean_u.strip()
    clean_u = " ".join(clean_u.split())
    return clean_u

def run_test_process_manager(configs: list, recursive: bool, depth: int, no_cache: bool) -> list:
    configs_results = []
    with concurrent.futures.ProcessPoolExecutor(max_workers=len(configs)) as executor:
        for config in configs:
            config['recursive'] = recursive
            config['depth'] = depth
            config['no_cache'] = no_cache
        futures = [executor.submit(run_test_process, config) for config in configs]
        configs_results = [f.result() for f in futures]
    return configs_results

def dump_yaml(object: dict, file):
    yaml = YAML()
    yaml.indent(mapping=2, sequence=4, offset=2)
    yaml.version = (1, 2)
    yaml.dump(object, file)


def run_test_process(config: List[dict]) -> List[dict]:
    current_test_results = []
    name_prefix = config["customer"] + "_" + config["environment"] + "_"
    name_suffix = 1
    for test_class in Tests.__subclasses__():
        class_name = re.sub(r'(?<!^)(?=[A-Z])', '_', test_class.__name__).lower()
        test_case_name = name_prefix + class_name
        # run a test if it is specified in the input config file
        if class_name in config["tests"]:
            # instantiate the class otherwise can't reach the method
            my_class = test_class(config)
            test_result = my_class.run_test()
            current_test_results.append({
                    "class_name": class_name,
                    "test_case_name": test_case_name,
                    "test_description": my_class.test_description,
                    "result": test_result["results"],
                    "error": test_result.get("errors"),
                    "error_data": test_result.get("error_data")
                })
            name_suffix += 1
    test_results =  {
            "cust-env" : config["customer"] + "-" + config["environment"],
            "tests": current_test_results
        }
    return test_results

def get_payload_by_utterance_id(utterance_id, payloads):
    found_payload = {}
    for payload in payloads:
        if payload.get("utteranceId") == utterance_id:
            found_payload.update(payload)
            break
    return found_payload

def divide_chunks(l, n):
    # looping till length l
    for i in range(0, len(l), n):
        yield l[i:i + n]

def complete_async_answers(unanswered_question_payloads, hsdki):
    # TODO: Fix sloppy/difficult code
    # This function is not a proud moment. Leaving it for now.
    new_remaining_questions = []
    newly_answered_questions = []
    new_responses = []
    utterance_ids = [pyld.get("utteranceId") for pyld in unanswered_question_payloads]

    utterance_id_chunks = list(divide_chunks(utterance_ids, 10))
    for utterance_id_chunk in utterance_id_chunks:
        response = hsdki.complete_async_answers(utterance_id_chunk)
        new_responses.extend(response.get("completed", []))
    if isinstance(new_responses, list) and len(new_responses) > 0:
        for new_response in new_responses:
            past_payload = get_payload_by_utterance_id(utterance_id=new_response.get("utteranceId"), payloads=unanswered_question_payloads)
            if new_response.get("status") == "Done":
                mapped_payload = map_submit_payload_to_complete_payload( past_payload, new_response)
                newly_answered_questions.append(mapped_payload)
            else:
                mapped_payload = map_submit_payload_to_complete_payload( past_payload, new_response)
                new_remaining_questions.append(mapped_payload)
            pass
    return newly_answered_questions, new_remaining_questions

def map_submit_payload_to_complete_payload(complete_async_payload, submit_payload ):
   complete_async_payload.update(submit_payload)
   return complete_async_payload

def get_answers( unanswered_question_payloads, hsdki):
    # This function is not a proud moment. Leaving it for now.
    new_remaining_questions = []
    newly_answered_questions = []
    for question_payload in unanswered_question_payloads:
        if question_payload.get("status") == "Calculating":
            payload = hsdki.get_answer(job_id=question_payload["job_id"])
            if payload:
                if payload.get("status") == "Calculating":
                    new_remaining_questions.append(payload)
                else: # status = Done
                    newly_answered_questions.append(payload)
    return newly_answered_questions, new_remaining_questions

def normalize_question_payload(payload, question_payload = {}):
    if payload.get("crash"):
        return( {
                "answer_type": question_payload.get("answer_type"),
                "status": "Done",
                "utterance": payload.get("utterance") or None,
                "visual": {},
                "job_id": None,
                "job_status": None,
                "qa_response": {},
                "error_message": "Question could not be submitted.",
                "error": True
            })
    message = payload.get("message")
    error, error_message = None, None
    # We get a message when there is a splat from a cached answer
    # perhaps other times also?
    if message:
        error, error_message = True, payload.get("utterance")

        return( {
                    "answer_type": payload.get("answer_type"),
                    "status": "Done",
                    "utterance": payload.get("utterance"),
                    "visual": {},
                    "job_id": None,
                    "job_status": None,
                    "qa_response": {},
                    "error_message": error_message or None,
                    "error": error or None
                })
    # we have a cached answer
    elif payload.get("answer_type") == "cached":
        error, error_message = None, None
        if "did not understand" in payload["visual"]:
            error, error_message = True, "Did not undestand"

        # check for splat error and append into payload for summary reporting
        qa_response = payload.get("qa_response")
        if isinstance(qa_response, str):
            qa_response = json.loads(qa_response)
        if qa_response:
            if qa_response.get("splat_code"):
                error = True
                error_message = payload.get("utterance")

        return( {
                    "answer_type": payload.get("answer_type"),
                    "status": payload.get("status"),
                    "utterance": payload.get("utterance"),
                    "visual": payload.get("visual"),
                    "job_id": None,
                    "job_status": "Done",
                    "qa_response": payload.get("qa_response") or None,
                    "error_message": error_message or None,
                    "error": error or None
                })
    elif payload.get("answer_type") == "help":
        error, error_message = False, ""

        return( {
                    "answer_type": payload.get("answer_type"),
                    "status": payload.get("status"),
                    "utterance": payload.get("utterance"),
                    "visual": payload.get("visual"),
                    "job_id": None,
                    "job_status": "Done",
                    "qa_response": payload.get("qa_response") or None,
                    "error_message": error_message or None,
                    "error": error or None
                })
    elif payload.get("answer_type") == "splat":

        return( {
                    "answer_type": payload.get("answer_type"),
                    "status": payload.get("status"),
                    "utterance": payload.get("utterance"),
                    "visual": payload.get("visual"),
                    "job_id": None,
                    "qa_response": payload.get("qa_response") or None,
                    "error_message": error_message or None,
                    "error": error or None
                })
    else:
        # not a splat and not a status code 500 (that has an error message)
        # could be done or still running.
        error, error_message = None, None

        job_id = question_payload.get("job_id") or payload.get("job_id")
        utterance = question_payload.get("utterance") or payload.get("utterance")
        job_status = payload.get("job_status") or None
        status = "Calculating" if job_status not in ["SUCCEEDED", "FAILED"] else "Done"

        # check for splat error and append into payload for summary reporting
        qa_response = {}
        if status == "Done":
            if "did not understand" in payload.get("visual"):
                error, error_message = True, "Did not undestand"
            qa_response = payload.get("qa_response")
            if isinstance(qa_response, str):
                qa_response = json.loads(qa_response)
            if qa_response:
                # check qa_response for a splat condition
                if qa_response.get("splat_code"):
                    error = True
                    error_message = payload.get("utterance")

        # batch job failed
        if job_status == "FAILED":
            error, error_message = True, payload.get("utterance")

        return( {
                    "status": status,
                    "utterance": utterance,
                    "visual": payload.get("visual"),
                    "job_id": job_id,
                    "job_status": job_status,
                    "qa_response": payload.get("qa_response") or None,
                    "error_message": error_message or None,
                    "error": error or None
                })


def get_configs(input_file):
    logger = get_logger(__name__)
    configs = []
    with open(input_file, 'r') as config_file:
        configs = json.load(config_file)
        config_count = len(configs)
        configs = validate_or_delete_configs(configs)
        if len(configs) != config_count:
            logger.error(f"the input-file provided had an invalid config record")
            exit(1)
        return configs

def get_config_schema():
    return Schema([
        {
            "customer": And(Use(str)),
            "environment": And(Use(str)),
            Optional('cli_token') : And(Use(str)),
            "tests": [ And(Use(str))],
            Optional('parameters'): And(Use(dict))
            }
        ],
        ignore_extra_keys=True)

def validate_or_delete_configs(configs):
    try:
        config_schema = get_config_schema()
        return config_schema.validate(configs)
    except SchemaError:
        return None

def get_utterance(utterance: str, customer: str, environment: str):
    # returns the up_response for a single utterance
    huma_sdk_instantiated = huma_sdk(customer=customer, environment=environment)
    output = huma_sdk_instantiated.get_utterance(utterance)
    return output


def compare_utterance(utterance: str, customer: str, environment: str):
    # takes in an utterance, creates a copy with 'new' appended to the end of the string. Then returns the up_response from both.
    huma_sdk_instantiated = huma_sdk(customer=customer, environment=environment)
    utterances = []
    utterances.append(utterance)
    utterances.append(utterance + " new")
    u1_output = huma_sdk_instantiated.get_utterance(utterances[0])
    u2_output = huma_sdk_instantiated.get_utterance(utterances[1])
    return u1_output, u2_output


def ask_question(question: str, customer: str, environment: str):
    logger = get_logger(__name__)
    try:
        huma_sdk_instantiated = huma_sdk(customer=customer, environment=environment)
    except Exception as e:
        logger.error(f"Failed to instantiate huma_sdk: {whoami()}::for {customer}: Error {e}")
    payload = huma_sdk_instantiated.submit_question(question)
    return append_ask_question_payload(payload)

def append_ask_question_payload(payload, question_payload = {}):
    # TODO: this needs updated logic from tests.py near line 130
    logger = get_logger(__name__)
    job_id = question_payload.get("job_id") or payload.get("job_id")
    job_status = payload.get("job_status") or None
    status = "Calculating" if job_status not in ["SUCCEEDED", "FAILED"] else "Done"
    if not payload.get('answer_type') == 'cached':
        logger.info(f"Question was NOT cached for job_id {job_id}.")
    else:
        logger.info("Question WAS cached, for  job_id {job_id}.  Returning answer visual.")
    return( {
                    "status": status, 
                    "utterance": payload.get("utterance"), 
                    "visual": payload.get("visual"), 
                    "job_id": job_id,
                    "job_status": payload.get("job_status") or None,
                    "qa_response": payload.get("qa_response") or None
                })

def get_answer(customer: str, environment: str, job_id: str):
    try:
        huma_sdk_instantiated = huma_sdk(customer=customer, environment=environment)
        payload = huma_sdk_instantiated.get_answer(job_id)
        return payload
    except Exception as e:
        logger = get_logger(__name__)
        logger.error(f"error caught in helpers.py, failed to get answer because error {e}")


def get_audit_trail(customer: str, environment: str):
    try:
        huma_sdk_instantiated = huma_sdk(customer=customer, environment=environment)
        payload = huma_sdk_instantiated.get_audit_trail()
        return payload
    except Exception as e:
        logger = get_logger(__name__)
        logger.error(f"error caught in helpers.py, failed to get audit trail because error {e}")


def get_analyzer_logs(customer: str, environment: str, job_id:str):
    try:
        huma_sdk_instantiated = huma_sdk(customer=customer, environment=environment)
        payload = huma_sdk_instantiated.get_analyzer_logs(job_id=job_id)
        return payload
    except Exception as e:
        logger = get_logger(__name__)
        logger.error(f"error caught in helpers.py, failed to get analyzer logs because error {e}")

def get_user_activity(customer: str, environment: str,duration:int):
    try:
        huma_sdk_instantiated = huma_sdk(customer=customer, environment=environment)
        payload = huma_sdk_instantiated.get_user_activity(duration = duration)
        return payload
    except Exception as e:
        logger = get_logger(__name__)
        logger.error(f"error caught in helpers.py, failed to get activity logs because error {e}")

def get_redis_key(customer: str, environment: str, key: str):
    print(customer,environment,key)
    try:
        huma_sdk_instantiated = huma_sdk(customer=customer, environment=environment)
        payload = huma_sdk_instantiated.get_redis_key(key)
        return payload
    except Exception as e:
        logger = get_logger(__name__)
        logger.error(f"error caught in helpers.py, failed to get redis key because error {e}")

def clear_redis_keys(customer: str, environment: str, namespace: str):
    try:
        huma_sdk_instantiated = huma_sdk(customer=customer, environment=environment)
        payload =  huma_sdk_instantiated.clear_redis_keys(namespace)
        return payload
    except Exception as e:
        logger = get_logger(__name__)
        logger.error(f"error caught in helpers.py, failed to clean redis key because error {e}")

def get_redis_keys(customer: str, environment: str, namespace_filter: str):
    try:
        huma_sdk_instantiated = huma_sdk(customer=customer, environment=environment)
        payload = huma_sdk_instantiated.get_redis_keys(namespace_filter)
        if payload == '':
            payload = []
        return payload.get("redis_keys",[])
    except Exception as e:
        logger = get_logger(__name__)
        logger.error(f"error caught in helpers.py, failed to get redis keys because error {e}")


def put_redis_key(customer: str, environment: str, key: str, value: str):
    try:
        huma_sdk_instantiated = huma_sdk(customer=customer, environment=environment)
        payload = huma_sdk_instantiated.put_redis_key(key, value)
        return payload
    except Exception as e:
        logger = get_logger(__name__)
        logger.error(f"error caught in helpers.py, failed to put redis key value because error {e}")


def get_up_config(customer: str, environment: str, version: int) -> dict:
    try:
        huma_sdk_instantiated = huma_sdk(customer=customer, environment=environment)
        payload = huma_sdk_instantiated.get_up_config(version)
        return payload
    except Exception as e:
        logger = get_logger(__name__)
        logger.error(f"error caught in helpers.py, failed to get activity logs because error {e}")

def _get_up_yml_config_from_local(filepath: str) -> dict:
    """returns a key, value pair like { 'filename' : 'file content'} where 'file content' is a string """
    try:
        p = Path(filepath)
        up_config = {}
        if p.exists() and p.is_file():
            up_config[p.name.replace('.yml', '')] = open(filepath, "r").read()
        return up_config
    except Exception as e:
        logger = get_logger(__name__)
        logger.error(f"faile to get {filepath} from local because error {e}")

def _get_up_configs_from_local(filepath: str):
    try:
        parent_path = Path(filepath).parent
        up_config_all = _get_up_yml_config_from_local(filepath)
        if not up_config_all:
            raise Exception(f"config {filepath} was not found or it was not a valid up_condig.yml file.")
        for v in up_config_all.values():
            yaml = YAML(typ="rt")
            #yaml.indent(mapping=2, sequence=4, offset=2)
            up_config_yml = yaml.load(v)
            break
        list_of_config_filenames = []
        if up_config_yml:
            list_of_config_filenames = up_config_yml.get("new_up_data_files")
        for config_name in list_of_config_filenames:
            fullpath = PurePath.joinpath(parent_path, config_name + ".yml")
            config = _get_up_yml_config_from_local(fullpath)
            if not config:
                raise Exception(f"config {fullpath} in config group {filepath} was not found.")
            up_config_all.update(config)
        return up_config_all
    except Exception as e:
        logger = get_logger(__name__)
        logger.error(f"Fetch of config group {filepath} from local failed because {e}")
        return None

def put_up_config(customer: str, environment: str, filepath: str):
    try:
        up_config_group = _get_up_configs_from_local(filepath)
        huma_sdk_instantiated = huma_sdk(customer=customer, environment=environment)
        payload = huma_sdk_instantiated.put_up_config(up_config_group)

        if payload.status_code == 200:
            reply_test = json.loads(payload.text)
            if not reply_test.get("msg"):
                return True
            return reply_test.get("msg")
        if payload.status_code != 200:
            return False
    except Exception as e:
        logger = get_logger(__name__)
        logger.error(f"error caught in helpers.py, failed to get activity logs because error {e}")


def get_activity_dump(customer: str, environment: str,duration:int):
    try:
        huma_sdk_instantiated = huma_sdk(customer=customer, environment=environment)
        payload = huma_sdk_instantiated.get_activity_dump(duration = duration)
        return payload
    except Exception as e:
        logger = get_logger(__name__)
        logger.error(f"error caught in helpers.py, failed to get activity dump because error {e}")


def get_suggestions(customer: str, environment: str):
    try:
        huma_sdk_instantiated = huma_sdk(customer=customer, environment=environment)
        suggestions_payload = huma_sdk_instantiated.get_suggestions()
        # returns a dict with a suggestions key
        return suggestions_payload
    except Exception as e:
        logger = get_logger(__name__)
        logger.error(f"error caught in helpers.py, failed to get suggestion config because error {e}")


def create_suggestions(suggestions: list, customer: str, environment: str):
    try:
        huma_sdk_instantiated = huma_sdk(customer=customer, environment=environment)
        response = huma_sdk_instantiated.create_suggestions(suggestions)
        return response
    except Exception as e:
        logger = get_logger(__name__)
        logger.error(f"Failed to update suggestion config because {e}")


@check_server_status
def get_minimum_vcpu(customer: str, environment: str, autostart: bool):
    # returns the minimum vcpu and errors if any
    huma_sdk_instantiated = huma_sdk(customer=customer, environment=environment)
    output = huma_sdk_instantiated.get_minimum_vcpu()
    return output
    
@check_server_status
def set_minimum_vcpu(customer: str, environment: str, minvcpu:int, autostart: bool):
    # returns the set minimum vcpu and errors if any
    huma_sdk_instantiated = huma_sdk(customer=customer, environment=environment)
    output = huma_sdk_instantiated.set_minimum_vcpu(minvcpu)
    return output

def get_system_status(customer: str, environment: str):
    # returns the system status and errors if any
    huma_sdk_instantiated = huma_sdk(customer=customer, environment=environment)
    output = huma_sdk_instantiated.get_system_status()
    return output

def get_system_activity(customer: str, environment: str):
    # returns the system status and errors if any
    huma_sdk_instantiated = huma_sdk(customer=customer, environment=environment)
    output = huma_sdk_instantiated.get_system_activity()
    return output

# @check_server_status
def stop_system_activity(customer: str, environment: str):
    # returns the system status and errors if any
    if environment=="prod":
        sys.exit("WARNING! CAN NOT RUN THIS COMMAND FOR PRODUCTION ENVIRONMENT.")
    huma_sdk_instantiated = huma_sdk(customer=customer, environment=environment)
    output = huma_sdk_instantiated.stop_system_activity()
    return output


def start_system_activity(customer: str, environment: str):
    # returns the system status and errors if any
    if environment=="prod":
        sys.exit("WARNING! CAN NOT RUN THIS COMMAND FOR PRODUCTION ENVIRONMENT.")
    huma_sdk_instantiated = huma_sdk(customer=customer, environment=environment)
    output = huma_sdk_instantiated.start_system_activity()
    return output

def spin_systems_for_smoke_tests(configs):
    logger = get_logger(__name__)
    system_info = []
    log_msg = format_log_msg(f"Start environment services for different clients if they are shut and execute smoke tests on them and shut them again.")
    logger.info(log_msg)
    for conf in configs:
        try:
            activity = get_system_status(customer=conf['customer'], environment=conf['environment'])
        except Exception as e:
            sys.exit(f"Could not get system status because {e}.") 
        if  'message' in activity or not activity or activity['results'] is None: # in case there is permission related issues on customer environment
            log_msg = format_log_msg(f"""
            There is problem getting status for customer {conf['customer']} on environemnt {conf['environment']}
            We will continue checking further systems and run smoke tests on active customer environment only.
            """)
            logger.info(log_msg)

        else:
            if activity['are_all_services_available']:
                pass # skip to running tests as all services are working fine
            else:
                if activity['are_servers_shuting_down'] or activity['are_rds_instances_shutting_down']: # wait for system services to stop if they are in stopping state
                    is_shutting_down = True
                    while is_shutting_down:
                        log_msg = format_log_msg(f"Please wait. System services are currently invoked to shut for customer {conf['customer']} on environemnt {conf['environment']}")
                        logger.info(log_msg)
                        stop_activity = get_system_status(customer=conf['customer'], environment=conf['environment'])
                        if not stop_activity['are_servers_shuting_down'] and stop_activity['are_rds_instances_shutting_down']:
                            is_shutting_down = False # system is started now
                        else:
                            time.sleep(10) # wait for every 10 seconds for system to stop
                time.sleep(20)
                is_system_starting = True
                log_msg = format_log_msg(f"System services for customer {conf['customer']} on environemnt {conf['environment']} are down. ")
                logger.info(log_msg)
                system_to_start_now = {'customer': conf['customer'], 'environment': conf['environment']}
                system_info.append(system_to_start_now)
                start_system_activity(conf['customer'], conf['environment']) # spin up system
                while is_system_starting:
                    log_msg = format_log_msg(f"Starting services for customer {conf['customer']} on environemnt {conf['environment']}")
                    logger.info(log_msg)
                    start_activity = get_system_status(customer=conf['customer'], environment=conf['environment'])
                    if start_activity['are_all_services_available']:
                        is_system_starting = False # system is started now
                    else:
                        time.sleep(10) # wait for every 10 seconds for system to start
        time.sleep(20)
    return system_info

def get_latest_user_context_helper(customer: str, environment: str, user_id: str):
    huma_sdk_instantiated = huma_sdk(customer=customer, environment=environment)
    result = huma_sdk_instantiated.get_latest_user_context(user_id)
    return result

def get_all_user_context_helper(customer: str, environment: str, user_id: str):
    huma_sdk_instantiated = huma_sdk(customer=customer, environment=environment)
    result = huma_sdk_instantiated.get_all_user_context(user_id)
    return result

def _get_user_context_json_from_local(filepath: str) -> dict:
    try:
        p = Path(filepath)
        user_context = {}
        if p.exists() and p.is_file():
            file = open(filepath, "r")
            user_context = json.load(file)
        return user_context
    except Exception as e:
        logger = get_logger(__name__)
        logger.error(f"failed to get {filepath} from local because error {e}")

def create_user_context(customer: str, environment: str, user_id: str, filepath: str):
    try:
        user_context = _get_user_context_json_from_local(filepath)
        huma_sdk_instantiated = huma_sdk(customer=customer, environment=environment)
        payload = huma_sdk_instantiated.create_user_context(user_id, user_context)

        if payload.status_code == 200:
            reply_test = json.loads(payload.text)
            return True
        if payload.status_code != 200:
            return False
        
    except Exception as e:
        logger = get_logger(__name__)
        logger.error(f"error caught in helpers.py, failed to create user context because error {e}")

