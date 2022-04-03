from abc import ABC
from logging import NullHandler
import re
from huma_sdk.sdk import huma_sdk
import time
import requests
from huma_sdk.utils.log_utils import get_logger
import uuid
import huma.helpers as h
import json
from datetime import datetime
class Tests(ABC):
    def __init__(self, config):
        self.config = config
        self.results = None
        self.description = config['description']
        self.logger = logger = get_logger(__name__ + " " + config.get("customer", None) + "-" + config.get("environment", None))
        self.huma_sdk_instantiated = huma_sdk(customer=self.config["customer"], environment=self.config["environment"], cli_token=self.config.get("cli_token") or None)

    @property
    def test_description(self):
        return self.description

    def _data_frame_empty(self, payload):
        visual = payload.get("visual")
        df = None
        if visual:
            df = visual.get("data")
        if df:
            return False
        return True

    def process_question(self, q, question_payloads, error_utterance_list, errors, no_cache:bool, ask_no_cache_all: bool):
        next_level_questions = []
        """
        In case of quick_links_all_no_cache, ask_no_cache_all parameter is set to True,
        so further level questions should be asked with no cache too

        """

        if self.config['no_cache'] == True and 'no cache' not in q:
            if no_cache: 
                '''
                no cache is set to false when we are processing a recursive question, 
                otherwise we are asking utterance with no cache every time recursively.
                no cache is added only on first iteration of recursive question.
                '''
                q = q + " no cache"

        payload = self.huma_sdk_instantiated.submit_question(question=q)
        print("Processing Question: ", q)
        if payload:
            question_template = ""
            exiting_utterances = [d['utteranceId'] for d in question_payloads if 'utteranceId' in d]
            if 'utteranceId' in payload and payload['utteranceId'] not in exiting_utterances:
                question_payloads.append(payload)

            if self.config['recursive'] == True:
                if 'visual' in payload:
                    if payload['visual']['type'] == 'line_chart':
                        question_template = ''
                        if 'nextQuestionTemplate' in payload['visual']:
                            question_template = payload['visual']['nextQuestionTemplate']
                        if question_template:
                            for qnext in payload['visual']['data']:
                                seriesID = qnext['id']
                                for data in qnext['data']:
                                    label = data['x']
                                    label = datetime.strptime(label, '%Y-%m-%d').strftime('%b %Y')
                                    question = question_template.replace("{{seriesID}}", seriesID).replace("{{label}}", str(label))
                                    next_level_questions.append(question)
                    elif payload['visual']['type'] == 'bar_chart':
                        question_template = ''
                        if 'nextQuestionTemplate' in payload['visual']:
                            question_template = payload['visual']['nextQuestionTemplate']
                        if question_template:
                            if 'groupMode' in payload['visual'] and payload['visual']['groupMode'] == 'stacked':
                                for label in payload['visual']['labels']:
                                    for data in payload['visual']['data']:
                                        question = question_template.replace("{{seriesID}}", label).replace("{{label}}", str(data['index']))
                                        next_level_questions.append(question)
                            else:
                                for data in payload['visual']['data']:
                                    label = data['label']
                                    question = question_template.replace("{{label}}", str(label))
                                    next_level_questions.append(question)
                    elif payload['visual']['type'] == 'dashboard':
                        components = payload['visual'].get("components", [])
                        for data in components:
                            question_template = ''
                            if 'nextQuestionTemplate' in data:
                                question_template = data['nextQuestionTemplate']
                                if question_template:
                                    dt = data.get("data", None)
                                    if dt:
                                        for d in dt:
                                            label = d.get('label', None)
                                            if label:
                                                question = question_template.replace("{{label}}", str(label))
                                                next_level_questions.append(question)
                    elif payload['visual']['type'] == 'calculation':
                        print("This question is being calculated")
                        pass
            else:
                print("skip traversing further questions for this utterance as recursion is set to False")

            if payload.get("message"):
                errors = True
                error_utterance_list.append(q + " -> {}".format(payload.get("message")))
            elif payload.get("answer_type") == "splat":
                errors = True
                error_utterance_list.append(q)
            else:
                pass
        else:
            errors = True
            error_utterance_list.append(q + " -> Empty return payload")

        if ask_no_cache_all:
            next_level_questions_no_cache = []
            for question in next_level_questions:
                if 'no cache' not in question:
                    question = question + " no cache"
                next_level_questions_no_cache.append(question)
            return errors, error_utterance_list, question_payloads, next_level_questions_no_cache

        return errors, error_utterance_list, question_payloads, next_level_questions

    def process_next_level_questions(self, question_list, question_payloads, error_utterance_list, errors, ask_no_cache_all:bool, no_cache:bool, level:int):
        if self.config['depth'] != 0 and level > self.config['depth']:
            return question_payloads, error_utterance_list, errors

        for q in question_list:
            errors, error_utterance_list, question_payloads, next_level_questions = self.process_question(q, question_payloads, error_utterance_list, errors, no_cache, ask_no_cache_all)
            if self.config['recursive'] == True:
                if next_level_questions:
                    print("Processing Internal Questions for: ", q)
                    errors, error_utterance_list, question_payloads = self.process_next_level_questions(next_level_questions, question_payloads, error_utterance_list, errors, ask_no_cache_all, no_cache=True, level= level+1)

        return errors, error_utterance_list, question_payloads

    def loop_to_get_answers(self, list_of_questions, errors, ask_no_cache_all, no_cache=True, max_wait_for_answer_seconds=600):
        list_of_questions_unanswered = []
        answered_question_payloads = []
        unanswered_question_payloads = []
        question_payloads = []
        error_utterance_list = []
        ques = question_payloads
        if isinstance(list_of_questions, list):
            errors, error_utterance_list, question_payloads = self.process_next_level_questions(list_of_questions, question_payloads, error_utterance_list, errors, ask_no_cache_all, no_cache, level=0)
        if len(question_payloads) == 0:
            errors = True
            error_utterance_list.append("len suggestions return payload is 0")
        answered_question_payloads = [question_payload for question_payload in question_payloads if question_payload.get("status") == "Done"]
        unanswered_question_payloads = [question_payload for question_payload in question_payloads if question_payload.get("status") == "Calculating"]
        list_of_questions_unanswered = [question_payload['utterance'].replace('no cache', '') for question_payload in unanswered_question_payloads  if 'no cache' in question_payload['utterance']]
        list_of_questions_unanswered = list(filter(None, list_of_questions_unanswered))
        # list_of_questions_unanswered =[x.replace('no cache', '') for x in list_of_questions_unanswered]
        start_time = time.time()
        try:
            # max_wait_for_answer_seconds = max(max_wait_for_answer_seconds, len(unanswered_question_payloads) * 60)
            while len(unanswered_question_payloads) > 0:
                self.logger.info(f"Pausing for 60 seconds to wait for questions to complete analysis.")
                time.sleep(60)
                answers, still_calculating = h.complete_async_answers(unanswered_question_payloads, self.huma_sdk_instantiated)
                answered_question_payloads.extend(answers)
                unanswered_question_payloads = [question_payload for question_payload in still_calculating if question_payload.get("status") == "Calculating"]
                # break if a questions are taking longer than 10 minutes
                if time.time() - start_time > max_wait_for_answer_seconds and max_wait_for_answer_seconds != 0:
                    errors = True
                    error_utterance_list.append(f"stopped at max duration of '{max_wait_for_answer_seconds}'")
                    self.logger.info(f"Tests did not complete within the allowed time of {max_wait_for_answer_seconds} seconds and we are done waiting.  An error has been indicated.")
                    break

        except Exception as e:
            pass
        if list_of_questions_unanswered:
            print("Processing again list of questions unanswered for recursive utterances: ", list_of_questions_unanswered)
            list_of_questions_unanswered, answered_question_payloads_internal, errors, error_utterance_list, unanswered_question_payloads_internal = self.loop_to_get_answers(list_of_questions_unanswered, errors, ask_no_cache_all, no_cache=False)
            answered_question_payloads = answered_question_payloads_internal #answered_question_payloads.extend(x for x in answered_question_payloads_internal if x not in answered_question_payloads)
            unanswered_question_payloads = unanswered_question_payloads_internal#unanswered_question_payloads.extend(x for x in unanswered_question_payloads_internal if x not in unanswered_question_payloads)

        return list_of_questions_unanswered, answered_question_payloads, errors, error_utterance_list, unanswered_question_payloads

    def _run_questions(self, loq_object):
        # loq = loq_object
        ask_no_cache_all = loq_object.get("ask_no_cache_all", False)
        errors = loq_object["errors"] or None
        list_of_questions = loq_object["questions"]
        max_wait_for_answer_seconds = loq_object.get("max_wait_for_answer_seconds", 600)

        list_of_questions, answered_question_payloads, errors, error_utterance_list, unanswered_question_payloads = self.loop_to_get_answers(list_of_questions, errors, ask_no_cache_all, max_wait_for_answer_seconds=max_wait_for_answer_seconds)

        test_results = answered_question_payloads or []
        test_results.extend(unanswered_question_payloads)
        if len(unanswered_question_payloads) != 0:
            errors = True
            unanswered_question_payloads.extend(unanswered_question_payloads)
        test_result_errors = [test_result.get("utterance") for test_result in test_results if test_result["visual"].get("type")  == "error"]

        # identify empty answer dataframes and report them as errors
        test_result_empty_df = []
        for test_result in test_results:
            # dashboard
            components = test_result["visual"].get("components") or []
            for component in components:
                short_answer_number = None
                try:
                    short_answer_number = float(component.get("shortAnswer"))
                except Exception as e:
                    pass
                if type(short_answer_number) == float and short_answer_number != 0.0:
                    continue
                elif type(short_answer_number) == float and short_answer_number == 0.0:
                    test_result_empty_df.append(test_result.get("utterance") + "-> empty dataframe in dashboard component")
                    continue
                elif type(short_answer_number) == str and "The system cannot find any data" in short_answer_number:
                    test_result_empty_df.append(test_result.get("utterance") + "-> no data found for question")
                    continue
                else:  # type is not int
                    if not component.get("data"):
                        test_result_empty_df.append(test_result.get("utterance") + "-> empty dataframe in dashboard component")
                        break
                    continue
            # non dashboard
            if not components:
                short_answer_number = None
                try:
                    short_answer_number = float(test_result["visual"].get("shortAnswer"))
                except Exception as e:
                    pass
                if type(short_answer_number) == float and short_answer_number != 0.0:
                    continue
                elif type(short_answer_number) == float and short_answer_number == 0.0:
                    test_result_empty_df.append(test_result.get("utterance") + "-> empty dataframe")
                    continue
                elif type(short_answer_number) == str and "The system cannot find any data" in short_answer_number:
                    test_result_empty_df.append(test_result.get("utterance") + "-> no data found for question")
                    continue
                else:  # type is not a number
                    if not test_result["visual"].get("data"):
                        test_result_empty_df.append(test_result.get("utterance") + "-> empty dataframe")
        test_result_errors.extend(test_result_empty_df)

        if len(test_result_errors)>0:
            errors = True
        #test_result_errors = [test_result.get("error_message") for test_result in test_results if test_result.get("error") == True]
        error_utterance_list.extend(test_result_errors)
        return { "results" : test_results, "errors" : errors, "error_data": error_utterance_list }

    # def run_test(self):
    #     pass

    #         for s in new_suggestions:
    #             if "no cache" not in s:
    #                 t = s + " no cache"
    #             else:
    #                 t = s
    #             if "help" not in t:
    #                 suggestions.append(t)
    
class QuicklinksAllNoCache(Tests):
    '''This test runs all questions in the QuickLinks without no cache'''
    def __init__(self, config):
        config['description'] = "This test runs the first question from each quicklink group with 'no cache' and reports if there was an error returned for any of the quetions."
        super().__init__(config)

    @property
    def test_description(self):
        return self.description

    def run_test(self):
        results = self._run_quicklink_questions()
        self._update_quicklinks_data(results)
        return results

    def _update_quicklinks_data(self, results):
        parameters = None
        parameters: dict = self.config.get("parameters")
        test_key = None
        if parameters:
            test_key: dict = parameters.get("quicklinks_all_no_cache")
        data = None
        if test_key:
            data = {
                "update_quicklinks": test_key.get("update_quicklinks"),
                "email_announce": test_key.get("email_announce"),
                "error_utterance_list": results.get('error_data')
            }
        if data:
            self.huma_sdk_instantiated.update_quicklinks_reporting(data)

    def _get_list_of_questions(self):
        errors = None
        error_data = []
        quick_links = []
        parameters: dict = self.config.get("parameters")
        question_parameters = {}
        if parameters:
            question_parameters = parameters.get("quicklinks_all_no_cache")
        max_wait_for_answer_seconds = 600
        if question_parameters:
            max_wait_for_answer_seconds = question_parameters.get("max_wait_for_answer_seconds",600 )
        try:
            new_quick_links = self.huma_sdk_instantiated.get_quick_links()
            for categories in new_quick_links.get("categories"):
                for k,v in categories.items():
                    if k == "suggestions":
                        if type(v) == list:
                            list_category_questions = v
                            for s in list_category_questions:
                                if type(s) == dict:
                                    for a, b in s.items():
                                        if a == "suggestions":
                                            list_sub_category_questions = b
                                            for su in list_sub_category_questions:
                                                if type(su) == str and "help" not in su:
                                                    quick_links.append(su)
                                elif type(s) == str and "help" not in s:
                                    quick_links.append(s)
                        elif type(v) == dict:
                            if type(su) == dict:
                                for j, w in su.items():
                                    if j == "suggestions":
                                        list_sub_sub_category_questions = w
                                        for l in list_sub_sub_category_questions:
                                            if type(s) == str and "help" not in l:
                                                quick_links.append(s)
                            else:
                                if type(s) == str and "help" not in su:
                                    quick_links.append(s)
                        else:
                            pass
            if len(quick_links) == 0:
                errors = True
                error_data.append("len quick links is 0")
        except Exception as e:
            errors = True
            error_data.append("could not invoke huma_sdk")
            self.logger.error(f"could not invoke huma_sdk because {e}")

        # convert all questions to 'no cache'
        quick_links_no_cache = []
        for q in quick_links:
            if "no cache" not in q:
                t = q + " no cache"
            else:
                t = q
            quick_links_no_cache.append(t)
        return {"questions": quick_links_no_cache,
                "max_wait_for_answer_seconds": max_wait_for_answer_seconds,
                "results" : None,
                "errors" : errors,
                "error_data": error_data,
                "ask_no_cache_all": True }

    def _run_quicklink_questions(self):
        parameters: dict = self.config.get("parameters")
        if not parameters:
            return { "results" : "fail", "errors" : True, "error_data": "parameters not found" }
        quicklinks_all_no_cache = parameters.get("quicklinks_all_no_cache")
        if not quicklinks_all_no_cache:
            return { "results" : "fail", "errors" : True, "error_data": "parameters not found" }
        loq_object = self._get_list_of_questions()
        # loq_object['questions'] = ["what the weather now in india"]
        results = super()._run_questions(loq_object)
        return results

    def _flag_errors(answered_question_payload):
        pass

    def _get_random_uuid(self):
        return uuid.uuid4()

    def _get_answers(self, unanswered_question_payloads):
        return h.get_answers(unanswered_question_payloads, self.huma_sdk_instantiated)

    def ask_question(self, question):
        payload = self.huma_sdk_instantiated.submit_question(question)
        return h.normalize_question_payload(payload)


class QuicklinksAll(Tests):
    '''This test runs all questions in the QuickLinks without no cache'''
    def __init__(self, config):
        config['description'] = "This test runs the first question from each quicklink group with 'no cache' and reports if there was an error returned for any of the quetions."
        super().__init__(config)

    @property
    def test_description(self):
        return self.description

    def run_test(self):
        results = self._run_quicklink_questions()
        self._update_quicklinks_data(results)
        return results

    def _update_quicklinks_data(self, results):
        parameters = None
        parameters: dict = self.config.get("parameters")
        test_key = None
        if parameters:
            test_key: dict = parameters.get("quicklinks_all")
        data = None
        if test_key:
            data = {
                "update_quicklinks": test_key.get("update_quicklinks"),
                "email_announce": test_key.get("email_announce"),
                "error_utterance_list": results.get('error_data')
            }
        if data:
            self.huma_sdk_instantiated.update_quicklinks_reporting(data)

    def _get_list_of_questions(self):
        errors = None
        error_data = []
        quick_links = []
        parameters: dict = self.config.get("parameters")
        question_parameters = {}
        if parameters:
            question_parameters = parameters.get("quicklinks_all")
        max_wait_for_answer_seconds = 600
        if question_parameters:
            max_wait_for_answer_seconds = question_parameters.get("max_wait_for_answer_seconds",600 )
        try:
            new_quick_links = self.huma_sdk_instantiated.get_quick_links()
            for categories in new_quick_links.get("categories"):
                for k,v in categories.items():
                    if k == "suggestions":
                        if type(v) == list:
                            list_category_questions = v
                            for s in list_category_questions:
                                if type(s) == dict:
                                    for a, b in s.items():
                                        if a == "suggestions":
                                            list_sub_category_questions = b
                                            for su in list_sub_category_questions:
                                                if type(su) == str and "help" not in su:
                                                    quick_links.append(su)
                                elif type(s) == str and "help" not in s:
                                    quick_links.append(s)
                        elif type(v) == dict:
                            if type(su) == dict:
                                for j, w in su.items():
                                    if j == "suggestions":
                                        list_sub_sub_category_questions = w
                                        for l in list_sub_sub_category_questions:
                                            if type(s) == str and "help" not in l:
                                                quick_links.append(s)
                            else:
                                if type(s) == str and "help" not in su:
                                    quick_links.append(s)
                        else:
                            pass
            if len(quick_links) == 0:
                errors = True
                error_data.append("len quick links is 0")
        except Exception as e:
            errors = True
            error_data.append("could not invoke huma_sdk")
            self.logger.error(f"could not invoke huma_sdk because {e}")
        return {"questions": quick_links,
                "max_wait_for_answer_seconds": max_wait_for_answer_seconds,
                "results" : None,
                "errors" : errors,
                "error_data": error_data }

    def _run_quicklink_questions(self):
        loq_object = self._get_list_of_questions()
        results = super()._run_questions(loq_object)
        return results

    def _flag_errors(answered_question_payload):
        pass

    def _get_random_uuid(self):
        return uuid.uuid4()

    def _get_answers(self, unanswered_question_payloads):
        return h.get_answers(unanswered_question_payloads, self.huma_sdk_instantiated)

    def ask_question(self, question):
        payload = self.huma_sdk_instantiated.submit_question(question)
        return h.normalize_question_payload(payload)
class Quicklinks(Tests):
    '''This test runs the first question of each group in the QuickLinks with no cache'''
    def __init__(self, config):
        config['description'] = "This test runs the first question from each quicklink group with 'no cache' and reports if there was an error returned for any of the quetions."
        super().__init__(config)

    @property
    def test_description(self):
        return self.description

    def run_test(self):
        results = self._run_quicklink_questions()
        return results

    def _get_list_of_questions(self):
        errors = None
        error_data = []
        quick_links = []
        parameters: dict = self.config.get("parameters")
        question_parameters = {}
        if parameters:
            question_parameters = parameters.get("quicklinks")
        max_wait_for_answer_seconds = 600
        if question_parameters:
            max_wait_for_answer_seconds = question_parameters.get("max_wait_for_answer_seconds",600 )
        try:
            new_quick_links = self.huma_sdk_instantiated.get_quick_links()
            for categories in new_quick_links.get("categories"):
                for k,v in categories.items():
                    if k == "suggestions":
                        if type(v) == list:
                            list_category_questions = v
                            for s in list_category_questions:
                                if type(s) == dict:
                                    for a, b in s.items():
                                        if a == "suggestions":
                                            list_sub_category_questions = b
                                            for su in list_sub_category_questions:
                                                if type(su) == str and "help" not in su:
                                                    quick_links.append(su)
                                                    break
                                elif type(s) == str and "help" not in s:
                                    quick_links.append(s)
                                    break
                        elif type(v) == dict:
                            if type(su) == dict:
                                for j, w in su.items():
                                    if j == "suggestions":
                                        list_sub_sub_category_questions = w
                                        for l in list_sub_sub_category_questions:
                                            if type(s) == str and "help" not in l:
                                                quick_links.append(s)
                                                break
                            else:
                                if type(s) == str and "help" not in su:
                                    quick_links.append(s)
                                    break
                        else:
                            pass
            if len(quick_links) == 0:
                errors = True
                error_data.append("len quick links is 0")
        except Exception as e:
            errors = True
            error_data.append("could not invoke huma_sdk")
            self.logger.error(f"could not invoke huma_sdk because {e}")
        quick_links_no_cache = []
        for q in quick_links:
            if "no cache" not in q:
                quick_links_no_cache.append(q + " no cache")
            else:
                quick_links_no_cache.append(q)
        return {"questions": quick_links,
                "max_wait_for_answer_seconds": max_wait_for_answer_seconds,
                "results" : None,
                "errors" : errors,
                "error_data": error_data }

    def _run_quicklink_questions(self):
        loq_object = self._get_list_of_questions()
        results = super()._run_questions(loq_object)
        return results

    def _flag_errors(answered_question_payload):
        pass

    def _get_random_uuid(self):
        return uuid.uuid4()

    def _get_answers(self, unanswered_question_payloads):
        return h.get_answers(unanswered_question_payloads, self.huma_sdk_instantiated)

    def ask_question(self, question):
        payload = self.huma_sdk_instantiated.submit_question(question)
        return h.normalize_question_payload(payload)
class FrontEndExists(Tests):
    def __init__(self, config):
        config['description'] = "This test tests whether or not the front-end returns a status code of 200."
        super().__init__(config)

    @property
    def test_description(self):
        return self.description

    def run_test(self):
        # get 200 from front end
        huma_sdk_instantiated = huma_sdk(self.config["customer"], 
                                         self.config["environment"], 
                                         cli_token=self.config.get("token", None))
        # example
        # url = f"https://huma-server.{environment}.{customer}.huma.ai/"
        backend_url = huma_sdk_instantiated.url
        frontend_url = backend_url.replace("huma-server.", "")
        if "localhost" in frontend_url:
            self.logger.error("Could not test frontend because HUMA_SERVER_URL environment variable is set to localhost")
            # test passed, test failed, test info
            return False, True, frontend_url
        response = requests.get(frontend_url)

        if response.status_code == 200:
            # test_result, error_exists
            return { "results" : True, "errors" : False, "error_data": None }

        # test_result, error_exists
        return { "results" : False, "errors" : True, "error_data": frontend_url }


class CustomAll(Tests):
    def __init__(self, config):
        config['description'] = self.description = self.description = "This test runs all questions from a provided list without 'no cache' and reports if there was an error returned for any of the quetions."
        super().__init__(config)

    @property
    def test_description(self):
        return self.description

    def run_test(self):
        loq_object = self._get_list_of_questions()
        results = super()._run_questions(loq_object)
        self._update_customall_data(results)
        return results

    def _update_customall_data(self, results):
        parameters = None
        parameters: dict = self.config.get("parameters")
        test_key = None
        if parameters:
            test_key: dict = parameters.get("custom_all")
        data = None
        if test_key:
            data = {
                "email_announce": test_key.get("email_announce"),
                "error_utterance_list": results.get('error_data')
            }
        # if data:
        #     self.huma_sdk_instantiated.custom_all_error_reporting(data)

    def _get_list_of_questions(self):
        # get dashboard questions
        errors, list_of_questions, question_parameters, results, error_data = None, [], {}, None, None

        try:
            parameters: dict = self.config.get("parameters")
            if not parameters:
                return { "results" : "fail", "errors" : True, "error_data": "parameters not found" }
            question_parameters = parameters.get("custom_all")
            if not question_parameters:
                return { "results" : "fail", "errors" : True, "error_data": "parameters not found" }
            list_of_questions = question_parameters.get("questions")
            max_wait_for_answer_seconds = question_parameters.get("max_wait_for_answer_seconds")

            if not list_of_questions:
                questions_file_name: str = question_parameters.get("questions_file")
                if questions_file_name:
                        with open(questions_file_name, 'r') as questions_file:
                            file_payload = json.load(questions_file)
                            list_of_questions = file_payload.get("questions")
                else:
                    return { "results" : "fail", "errors" : True, "error_data": "could not load questions from questions file in parameters" }

            errors = True if len(list_of_questions) == 0 else errors
        except Exception as e:
            errors = True
            self.logger.error(f"could not invoke huma_sdk because {e}")

        return {"questions": list_of_questions,
                "max_wait_for_answer_seconds": max_wait_for_answer_seconds,
                "results" : None,
                "errors" : errors,
                "error_data": error_data,
                "ask_no_cache_all": self.config.get("no_cache", False)}

    def _run_list_of_questions(self):
        loq_object = self._get_list_of_questions()
        results = super()._run_questions(loq_object)
        return results

    def _get_answers(self, unanswered_question_payloads):
        return h.get_answers(unanswered_question_payloads, self.huma_sdk_instantiated)

class ValidDomainCheck(Tests):
    def __init__(self, config):
        config['description'] = "This test tests whether or not the production have more than 1 valid domain"
        super().__init__(config)

    @property
    def test_description(self):
        return self.description

    def run_test(self):
        valid_domains = self.huma_sdk_instantiated.get_valid_domains()
        domains = []
        for d in valid_domains:
            domains.append(d['id'])

        env = self.config["environment"]
        if len(domains) == 0:
             return { "results" : False, "errors" : True, "error_data": "No domains available" }
        if env == "dev" or env == 'stage':
            if len(domains) < 1:
                return { "results" : False, "errors" : True, "error_data": "No domains available" }
            else:
                return { "results" : True, "errors" : False, "error_data": None }
        else:
            if len(domains) < 2 and 'huma.ai' in domains:
                return { "results" : False, "errors" : True, "error_data": "Only huma.ai domain available" }
            else:
                return { "results" : True, "errors" : False, "error_data": None }

class AutoSuggestionList(Tests):
    def __init__(self, config):
        config['description'] = "This test tests whether or not the auto suggeste list  have more than 0 guggestions"
        super().__init__(config)

    @property
    def test_description(self):
        return self.description

    def run_test(self):
        suggestions_payload = h.get_suggestions(self.config["customer"], environment=self.config["environment"])
        if suggestions_payload:
            suggestions = suggestions_payload.get('suggestions', [])
            suggestions_count = len(suggestions)

            if(suggestions_count > 0):
                return { "results" : True, "errors" : False, "error_data": None }
        return { "results" : False, "errors" : True, "error_data": "No suggestions available" }

class EcsServicesStatus(Tests):
    def __init__(self, config):
        config['description'] = "This test tests ECS services status (desired count == runnint count)"
        super().__init__(config)

    @property
    def test_description(self):
        return self.description

    def run_test(self):
        results = self.huma_sdk_instantiated.get_ecs_services_status()

        error = ''
        if len(results) > 0:
            for result in results:
                if result['desiredCount'] != result['runningCount']:
                    error += " " + result['serviceName']
            if error:
                return { "results" : False, "errors" : True, "error_data": error + ' Not Running' }
            else:
                return { "results" : True, "errors" : False, "error_data": None}

        return { "results" : False, "errors" : True, "error_data": "No Services Found or huma-server error"}

class BatchCpuStatus(Tests):
    def __init__(self, config):
        config['description'] = "This test tests Batch cpu uses"
        super().__init__(config)

    @property
    def test_description(self):
        return self.description

    def run_test(self):
        results = self.huma_sdk_instantiated.get_batch_cpu_status()
        error = ''
        if len(results) > 0:
            for result in results:
                if result['minvCpus'] >0 or result['maxvCpus'] <64:
                    error += " " + result['computeEnvironmentName']
            if error:
                return { "results" : False, "errors" : True, "error_data": 'Error in ' + error + 'envs'}
            else:
                return { "results" : True, "errors" : False, "error_data": None}

        return { "results" : False, "errors" : True, "error_data": "No data Found or huma-server error"}

class JobAlpineStatus(Tests):
    def __init__(self, config):
        config['description'] = "This test tests whether Batch job definition contain image alpine or not"
        super().__init__(config)

    @property
    def test_description(self):
        return self.description

    def run_test(self):
        # result will empty if no alpine found in recent 5 batch job with job status ACTIVE
        results = self.huma_sdk_instantiated.get_batch_recent_job_definition()

        if len(results) > 0:
            job_def_with_alpine = ""
            for result in results:
                job_def_with_alpine += result['jobDefinitionName'] + " "
            return { "results" : False, "errors" : True, "error_data": 'Alpine in ' + str(len(results)) + ' jobs for '+ job_def_with_alpine}

        return { "results" : True, "errors" : False, "error_data": None}
class DashboardCategory(Tests):
    def __init__(self, config):
        config['description'] = "This test tests dashboard category other than help"
        super().__init__(config)

    @property
    def test_description(self):
        return self.description

    def run_test(self):
        dash_categories = self.huma_sdk_instantiated.get_quick_links()['categories']
        question_count = 0
        help_question_count = 0

        for category in dash_categories:
            if isinstance(category['suggestions'], list):
                if len(category['suggestions']) == 1:
                    if category['suggestions'][0] == 'help':
                        help_question_count = help_question_count + 1
                elif len(category['suggestions']) < 1 and isinstance(category['suggestions'], list):
                    question_count = question_count + 1

            suggestions_count = len(dash_categories)

            if help_question_count == suggestions_count:
                return { "results" : False, "errors" : True, "error_data": "No questions other than help"}
            elif question_count == suggestions_count:
                return { "results" : False, "errors" : True, "error_data": "No questions found"}
            else:
                return { "results" : True, "errors" : False, "error_data": None}

        return { "results" : False, "errors" : True, "error_data": ""}

class MongodbConnection(Tests):
    def __init__(self, config):
        config['description'] = "This test tests mongo db is running or not"
        super().__init__(config)

    @property
    def test_description(self):
        return self.description

    def run_test(self):
        response = self.huma_sdk_instantiated.get_mongodb_connection_status()

        if "status" in response and response['status'] == True:
            return { "results" : True, "errors" : False, "error_data": None}
        return { "results" : False, "errors" : True, "error_data": "connection/api error"}

class RedisConnection(Tests):
    def __init__(self, config):
        config['description'] = "This test tests redis is running or not"
        super().__init__(config)

    @property
    def test_description(self):
        return self.description

    def run_test(self):
        response = self.huma_sdk_instantiated.get_redis_connection_test()
            
        if "status" in response and response['status'] == True:
            return { "results" : True, "errors" : False, "error_data": None}
        return { "results" : False, "errors" : True, "error_data": "connection/api error"}


class CtGovDbCheck(Tests):
    def __init__(self, config):
        config['description'] = "This test tests ct-gov db running or not"
        super().__init__(config)

    @property
    def test_description(self):
        return self.description

    def run_test(self):
        response = self.huma_sdk_instantiated.get_ctgov_db_status()
        if response["status"] == True:
            return { "results" : True, "errors" : False, "error_data": None}
        return { "results" : False, "errors" : True, "error_data": response["error"]}

class ClientDbCheck(Tests):
    def __init__(self, config):
        config['description'] = "This test tests client db running or not (Postgres DB)."
        super().__init__(config)

    @property
    def test_description(self):
        return self.description

    def run_test(self):
        db_name = 'postgres'
        response = self.huma_sdk_instantiated.get_client_db_status(db_name)
        if response.get("status") == True:
            return { "results" : True, "errors" : False, "error_data": None}
        return { "results" : False, "errors" : True, "error_data": response["error"]}

class ClientDbMysqlCheck(Tests):
    def __init__(self, config):
        config['description'] = "This test tests client db running or not (MySQL DB)"
        super().__init__(config)

    @property
    def test_description(self):
        return self.description

    def run_test(self):
        db_name = 'mysql'
        print(db_name)
        response = self.huma_sdk_instantiated.get_client_db_status(db_name)
        if response.get("status") == True:
            return { "results" : True, "errors" : False, "error_data": None}
        return { "results" : False, "errors" : True, "error_data": response["error"]}

class CheckSiteSettingsApi(Tests):
    def __init__(self, config):
        config['description'] = "This test tests whether or not the /get-site-settings api returns a status code of 200."
        super().__init__(config)

    @property
    def test_description(self):
        return self.description

    def run_test(self):
        url = self.huma_sdk_instantiated.url
        response = requests.get(url + 'get-site-settings')

        if response.status_code == 200:
            return { "results" : True, "errors" : False, "error_data": None }

        return { "results" : False, "errors" : True, "error_data":  'failed with http status ' + str(response.status_code)}




def tests():
    test_results = []
    for test_class in Tests.__subclasses__():
        rest_result = test_class.run_test()
        test_case_name = re.sub(r'(?<!^)(?=[A-Z])', '_', test_class.__name__).lower()
        test_results.append({ "test_name": test_case_name, "result": rest_result})
    return test_results

if __name__ == "__main__":
    # execute only if run as a script
    results = tests()
    print("{}".format(results))