import logging
import ruamel.yaml

from config import config

logger = logging.getLogger(__name__)


def generate_prediction_config_file(fixed_input_values, variable_input_values, output_values):
    # generate the prediction configuration file
    prediction_config = {
        "fixed_values": fixed_input_values,
        "variable_values": variable_input_values,
        "estimators": {"target_variable": output_values[0],  # TODO: output_values[0] is only the first --- what about others?
                       "estimator_file": config["job"]["prediction"]["estimator_file"], # TODO: automation?
                       "greater_is_better": config["job"]["prediction"]["greater_is_better"]}  # TODO: automation?

    }

    # Write the prediction configuration file
    try:
        prediction_config_file = config["job"]["prediction"]["config_file"]
        with open(prediction_config_file, "w") as f:
            yaml = ruamel.yaml.YAML()
            yaml.indent(sequence=4, offset=2)
            yaml.default_flow_style = False
            yaml.dump(prediction_config, f)
    except Exception as e:
        logger.error(f"Error writing prediction configuration file: {e}")
    pass
