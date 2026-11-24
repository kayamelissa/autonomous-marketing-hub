# Demo fixtures

Synthetic, recorded-style API responses used by the test suite and by the
offline demo:

```bash
python -m hub.run_all --brand boyer-law-firm --fixtures tests/fixtures/demo --no-send
```

Everything in these files is made up for testing: queries, impressions,
review counts, video accounts and AI answers. Competitor and page names are real
so the matching logic is exercised realistically. Never quote these numbers.
