import logging
import os
from string import Template

import pandas as pd
import streamlit as st

from tools.actuator import execute_command
from tools.generate_files import generate_prediction_config_file

logger = logging.getLogger(__name__)


# class that represents the UI and the variables associated with the ui
class PredictUI:
    def __init__(self):
        self.config_output_fields = None
        self.config_input_fields = None
        self.test = None
        self.title = "ARISE predictions"
        self.output_fields = None
        self.input_fields = None

    def set_input_fields(self, input_fields, input_fields_details):
        self.config_input_fields = input_fields
        self.input_fields = {}
        for input_field in input_fields:
            # handle categorical fields
            field_details = input_fields_details[input_field]
            if field_details["type"] == "categorical":
                self.input_fields[input_field] = {"name": input_field,
                                                  "placeholder": input_field,
                                                  "options": field_details["values"],
                                                  "type": "multiselect"}
            # handle numeric fields
            elif field_details["type"] == "numeric":
                self.input_fields[input_field] = {"name": input_field,
                                                  "placeholder": input_field,
                                                  "min_value": field_details["min"],
                                                  "max_value": field_details["max"],
                                                  "type": "select_slider"}
            # handle any other unknown fields as text
            else:
                self.input_fields[input_field] = {"name": input_field,
                                                  "placeholder": input_field,
                                                  "type": "text_input"}

    def set_output_fields(self, output_fields):
        self.config_output_fields = output_fields
        self.output_fields = {}
        for output_field in output_fields:
            self.output_fields[output_field] = {"name": output_field,
                                                "placeholder": output_field,
                                                "value": True,
                                                "type": "toggle"}

    def show(self):
        self.set_page_layout()
        self.show_page_content()
        self.show_sidebar()

    def set_page_layout(self):
        st.set_page_config(page_icon="⌛️", layout="wide", page_title="ARISE Prediction")

    def show_page_content(self):
        st.markdown("""
                    # ARISE prediction landing page

                    This page is used for predicting required resources and execution time of an AI workload, 
                    based on historical executions or performance benchmarks of similar workloads (a workload dataset)

                    ## How to use this page

                    On the sidebar
                    
                    1. Select the input values for the predictions 
                    2. Select the output values to be shown in the results
                    3. Click on the `Predict` button
                    
                    4. The results will be shown in the main page

                    > Note: Make sure to train the models before performing prediction, more info can be found on the   
                    on the training page.
                    > Note: Be patient. The operations might take some time.    
                    """)

        if 'all-predictions.csv' in st.session_state:
            st.markdown("## Prediction result")
            st.write(st.session_state['all-predictions.csv'])

        if 'predictions-with-ground-truth.csv' in st.session_state:
            st.markdown("## Ground-truth result")
            st.write(st.session_state['predictions-with-ground-truth.csv'])

        if 'prediction_results' in st.session_state:
            st.divider
            st.markdown("## Prediction command output")
            st.divider
            st.markdown(st.session_state.prediction_results)

    def add_form_element(self, element):
        if element["type"] == "text_input":
            st.text_input(element["name"], key=element["name"], placeholder=element["placeholder"])
        elif element["type"] == "multiselect":
            container = st.container(border=True)
            if container.checkbox("Select all", key=f'{element["name"]}_select_all'):
                container.multiselect(element["name"], key=element["name"], options=element["options"],
                                      default=element["options"],
                                      placeholder=element["placeholder"])
            else:
                container.multiselect(element["name"], key=element["name"], options=element["options"],
                                      placeholder=element["placeholder"])

        elif element["type"] == "slider":
            st.slider(element["name"], key=element["name"],
                      min_value=element["min_value"], max_value=element["max_value"])
        elif element["type"] == "select_slider":
            st.select_slider(element["name"], key=element["name"],
                             options=list(range(element["min_value"], element["max_value"] + 1)),
                             value=(element["min_value"], element["max_value"]))
        elif element["type"] == "toggle":
            st.toggle(element["name"], key=element["name"], value=element["value"])
        else:
            st.text(f"Unknown element type {element}")

    def show_sidebar(self):
        with (st.sidebar):
            st.header("Prediction configuration:")
            with st.form("Configuration"):
                st.subheader("Select input configuration:",
                             help="For each of the input features, select a specific value or"
                                  "use-multi selection to predict for all the values")
                for input_field_value in self.input_fields.values():
                    self.add_form_element(input_field_value)

                st.divider()
                st.subheader("Select output configuration:",
                             help="For each of the output features, select which features to present")

                for output_field_value in self.output_fields.values():
                    self.add_form_element(output_field_value)

                st.divider()

                st.form_submit_button("Predict", on_click=self.on_predict)

                st.toggle("compare with ground truth", key="compare_with_ground_truth", value=False,
                          help="Compare the results with the ground truth")

    def get_prediction_configuration(self, config_input_fields, config_output_fields):
        # generate the prediction config file
        fixed_input_values = []
        variable_input_values = []
        output_values = []

        logger.debug(f"generate_prediction_config_file")
        for config_input_field in config_input_fields:
            if (st.session_state[config_input_field] and
                    st.session_state[config_input_field] != "None"):
                # handle categorical
                if isinstance(st.session_state[config_input_field], list):
                    if len(st.session_state[config_input_field]) > 1:
                        variable_input_values.append(
                            {config_input_field : st.session_state[config_input_field]})
                    else:
                        fixed_input_values.append(
                            {config_input_field: st.session_state[config_input_field][0]})
                # handle numerical
                elif isinstance(st.session_state[config_input_field], tuple):
                    if st.session_state[config_input_field][0] is not st.session_state[config_input_field][1]:
                        variable_input_values.append(
                            {config_input_field: [i for i in range(st.session_state[config_input_field][0],
                                                                   st.session_state[config_input_field][1] + 1)]
                             }
                        )
                    else:
                        fixed_input_values.append(
                            {config_input_field: st.session_state[config_input_field][0]})
                # handle all other fields
                else:
                    fixed_input_values.append(
                        {config_input_field: st.session_state[config_input_field]})
            else:
                st.toast("Make sure to fill all input and output fields! Submit again", icon=":material/error:")
                return False, [], [], []

        for config_output_field in config_output_fields:
            if (st.session_state[config_output_field] and
                    st.session_state[config_output_field] is True):
                output_values.append(config_output_field)

        logger.info("prediction config file")

        logger.info(f"fixed_input_values: {fixed_input_values}")
        logger.info(f"variable_input_values: {variable_input_values}")
        logger.info(f"output_values: {output_values}")

        return True, fixed_input_values, variable_input_values, output_values

    def on_predict(self):
        from config import config

        logger.debug(f"on_predict")
        if st.session_state['compare_with_ground_truth']:
            command_template = Template(config["actuation_templates"]["demo-predict"])
        else:
            command_template = Template(config["actuation_templates"]["predict"])
        logger.debug(f"command_template: {command_template}")

        # build the prediction configuration file based on customer inputs and outputs:
        success, fixed_input_values, variable_input_values, output_values = (
            self.get_prediction_configuration(self.config_input_fields, self.config_output_fields))
        if not success:
            logger.debug(f"get_prediction_configuration failed")
            return

        generate_prediction_config_file(fixed_input_values,
                                        variable_input_values,
                                        output_values)

        # Substitute values
        command = command_template.substitute(
            title=self.title,
            job_spec_file=config["job"]["job_spec_file"],
            input_path=config["job"]["input_path"],
            python=config["job"]["python"],
            executable=config["job"]["executable"],
            model_path=config["job"]["model_path"],
            prediction_config_file=config["job"]["prediction"]["config_file"]
        )

        result = execute_command(command)
        logger.debug(f"on_predict result: {result}")

        st.session_state['prediction_results'] = f"""
### Execution of `prediction` is completed!  
The results are:
```{result}
```
"""

        # get the prediction file if exists
        if os.path.exists("../examples/MLCommons/ARISE-predictions/all-predictions.csv"):
            csv = pd.read_csv("../examples/MLCommons/ARISE-predictions/all-predictions.csv")
            st.session_state['all-predictions.csv'] = csv

        # get the ground-truth file if exists
        if os.path.exists("../examples/MLCommons/ARISE-predictions/predictions-with-ground-truth.csv"):
            csv = pd.read_csv("../examples/MLCommons/ARISE-predictions/predictions-with-ground-truth.csv")
            st.session_state['predictions-with-ground-truth.csv'] = csv
