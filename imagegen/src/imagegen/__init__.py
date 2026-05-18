"""imagegen — shared provider-pluggable cloud image-gen core.

The README.md in this package is the CONTRACT. Skill authors and future Claude
sessions should read it before integrating or extending this tool. Code here
deliberately owns only the fragile transport layer (SDK churn, cache, ledger);
prompt construction and provider routing live in the consuming skill.
"""

__version__ = "0.1.0"
