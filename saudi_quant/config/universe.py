from __future__ import annotations

TEST_UNIVERSE = (
    {"ticker": "1120.SR", "name": "Al Rajhi Bank"},
    {"ticker": "2222.SR", "name": "Saudi Aramco"},
    {"ticker": "7010.SR", "name": "STC"},
    {"ticker": "1180.SR", "name": "Saudi National Bank"},
    {"ticker": "2010.SR", "name": "SABIC"},
    {"ticker": "1211.SR", "name": "Maaden"},
    {"ticker": "1150.SR", "name": "Alinma Bank"},
    {"ticker": "2380.SR", "name": "Petro Rabigh"},
    {"ticker": "7203.SR", "name": "Elm"},
    {"ticker": "2082.SR", "name": "ACWA Power"},
)


def test_tickers() -> list[str]:
    return [item["ticker"] for item in TEST_UNIVERSE]
