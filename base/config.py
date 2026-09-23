"""Run configuration for IBMQExperiments.py.

ibmq-processing: "cpu" = local simulator (all paper experiments),
                 "qpu" = real IBM Q backend (needs IBMQ_TOKEN and ibmq-backend),
                 "collected" = skip running.
"""

import os

configuration = {
    "ibmq-processing": "cpu",
    "ibmq-token": os.environ.get("IBMQ_TOKEN", ""),
    "ibmq-hub": "open",
    "ibmq-group": "open",
    "ibmq-project": "main",
    "ibmq-backend": "",
}
