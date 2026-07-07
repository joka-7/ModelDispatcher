"""Internal helpers for the Vercel gateway wrapper.

Split out of :mod:`api.gateway` so the handler stays a thin adapter: perimeter
verification (:mod:`_lib.appcheck`), gateway assembly (:mod:`_lib.wiring`), and
JSON (de)serialization (:mod:`_lib.http`).
"""
