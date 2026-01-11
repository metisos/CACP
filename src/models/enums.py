from enum import Enum


class ProjectStatus(str, Enum):
    PLANNING = "planning"
    IMPLEMENTING = "implementing"
    INTEGRATING = "integrating"
    COMPLETE = "complete"


class ContractType(str, Enum):
    API_ENDPOINT = "api_endpoint"
    EVENT_SCHEMA = "event_schema"
    DATA_MODEL = "data_model"
    CONFIG_SPEC = "config_spec"
    RPC_INTERFACE = "rpc_interface"
    CUSTOM = "custom"


class ContractStatus(str, Enum):
    PROPOSED = "proposed"
    NEGOTIATING = "negotiating"
    AGREED = "agreed"
    IMPLEMENTED = "implemented"
    VERIFIED = "verified"


class ContextType(str, Enum):
    CODE_SNIPPET = "code_snippet"
    TYPE_DEFINITION = "type_definition"
    API_SPEC = "api_spec"
    ERROR_CATALOG = "error_catalog"
    ENV_CONFIG = "env_config"
    TEST_CASE = "test_case"
    DEPENDENCY_INFO = "dependency_info"
    IMPLEMENTATION_STATUS = "implementation_status"
    QUESTION = "question"
    DECISION = "decision"


class ImplementationStatus(str, Enum):
    PENDING = "pending"
    IN_PROGRESS = "in_progress"
    COMPLETE = "complete"
    NEEDS_REVISION = "needs_revision"
