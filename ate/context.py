import copy
import importlib
import os
import re
import sys
import types
from collections import OrderedDict

from ate import testcase, utils


def is_function(tup):
    """ Takes (name, object) tuple, returns True if it is a function.
    """
    name, item = tup
    return isinstance(item, types.FunctionType)

class Context(object):
    """ Manages context functions and variables.
        context has two levels, testset and testcase.
    """
    def __init__(self):
        self.testset_shared_variables_mapping = OrderedDict()
        self.testcase_variables_mapping = OrderedDict()
        self.init_context()

    def init_context(self, level='testset'):
        """
        testset level context initializes when a file is loaded,
        testcase level context initializes when each testcase starts.
        """
        if level == "testset":
            self.testset_functions_config = {}
            self.testset_request_config = {}
            self.testset_shared_variables_mapping = OrderedDict()

        # testcase config shall inherit from testset configs,
        # but can not change testset configs, that's why we use copy.deepcopy here.
        self.testcase_functions_config = copy.deepcopy(self.testset_functions_config)
        self.testcase_request_config = {}
        self.testcase_variables_mapping = copy.deepcopy(self.testset_shared_variables_mapping)

    def import_requires(self, modules):
        """ import required modules dynamicly
        """
        for module_name in modules:
            globals()[module_name] = importlib.import_module(module_name)

    def bind_functions(self, function_binds, level="testcase"):
        """ Bind named functions within the context
            This allows for passing in self-defined functions in testing.
            e.g. function_binds:
            {
                "add_one": lambda x: x + 1,             # lambda function
                "add_two_nums": "lambda x, y: x + y"    # lambda function in string
            }
        """
        eval_function_binds = {}
        for func_name, function in function_binds.items():
            if isinstance(function, str):
                function = eval(function)
            eval_function_binds[func_name] = function

        self.__update_context_functions_config(level, eval_function_binds)

    def import_module_functions(self, modules, level="testcase"):
        """ import modules and bind all functions within the context
        """
        sys.path.insert(0, os.getcwd())
        for module_name in modules:
            imported = importlib.import_module(module_name)
            imported_functions_dict = dict(filter(is_function, vars(imported).items()))
            self.__update_context_functions_config(level, imported_functions_dict)

    def bind_variables(self, variable_binds, level="testcase"):
        """ bind variables to testset context or current testcase context.
            variables in testset context can be used in all testcases of current test suite.

        @param (list) variable_binds, variable can be value or custom function.
            if value is function, it will be called and bind result to variable.
        e.g.
            [
                {"TOKEN": "debugtalk"},
                {"random": "${gen_random_string(5)}"},
                {"json": {'name': 'user', 'password': '123456'}},
                {"md5": "${gen_md5($TOKEN, $json, $random)}"}
            ]
        """
        for variable_bind in variable_binds:
            for variable_name, value in variable_bind.items():
                variable_evale_value = testcase.parse_content_with_bindings(
                    value,
                    self.testcase_variables_mapping,
                    self.testcase_functions_config
                )

                if level == "testset":
                    self.testset_shared_variables_mapping[variable_name] = variable_evale_value

                self.testcase_variables_mapping[variable_name] = variable_evale_value

    def __update_context_functions_config(self, level, config_mapping):
        """
        @param level: testset or testcase
        @param config_type: functions
        @param config_mapping: functions config mapping
        """
        if level == "testset":
            self.testset_functions_config.update(config_mapping)

        self.testcase_functions_config.update(config_mapping)

    def register_request(self, request_dict, level="testcase"):
        self.__update_context_request_config(level, request_dict)

    def __update_context_request_config(self, level, config_mapping):
        """
        @param level: testset or testcase
        @param config_type: request
        @param config_mapping: request config mapping
        """
        if level == "testset":
            self.testset_request_config.update(config_mapping)

        self.testcase_request_config = utils.deep_update_dict(
            copy.deepcopy(self.testset_request_config),
            config_mapping
        )

    def get_parsed_request(self):
        """ get parsed request, with each variable replaced by bind value.
        """
        parsed_request = testcase.parse_content_with_bindings(
            self.testcase_request_config,
            self.testcase_variables_mapping,
            self.testcase_functions_config
        )

        return parsed_request

    def get_testcase_variables_mapping(self):
        return self.testcase_variables_mapping
