"""Data-access layer: network fetches and persistence, cached for the UI.

Views call these functions; they never talk to yfinance, RSS feeds or the
filesystem directly. Pricing maths lives in `models/` and has no I/O.
"""
