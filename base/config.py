"""Run configuration for IBMQExperiments.py.

ibmq-processing: "cpu" = local simulator (all paper experiments),
                 "qpu" = real IBM Q backend (needs IBMQ_TOKEN and ibmq-backend),
                 "collected" = skip running.
qubo-formulation: "qaoa" = no predicate qubits, linear cost, derived penalty (default);
                  "q2o"  = original encoding. Old results and SPIQ files were made with "q2o".
                  Used by IBMQExperiments.py, spiq_initialization.py and postprocess_results.py.
"""

import os

configuration = {
    "ibmq-processing": "cpu",
    "ibmq-token": os.environ.get("IBMQ_TOKEN", ""),
    "ibmq-hub": "open",
    "ibmq-group": "open",
    "ibmq-project": "main",
    "ibmq-backend": "",
    "qubo-formulation": "qaoa",
}
