"""Shared infrastructure for the chess studies of this repository.

Everything here is study-independent: the clients of the two public APIs, the
record types, the JSONL stores and the engine that measures move quality. A study
decides what to collect and how to analyse it; this package only knows how.
"""
