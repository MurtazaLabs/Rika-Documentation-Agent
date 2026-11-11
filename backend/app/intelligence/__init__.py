"""Project intelligence: facts derived from the index, and the analyses on them.

Every module here reads only what ingestion already stored — documents, chunks,
symbols and import edges — so nothing needs a second pass over the source files
or a model call. The analyses are deterministic, which is what lets the API label
a conclusion as confirmed instead of guessed.
"""
