# DNS Infrastructure Monitor

Python-based DNS monitoring utilities adapted from a network engineering internship project. Includes **external DNS / web endpoint checks** and a separate **internal DNS record verification** workflow.

> **Portfolio adaptation:** This repository uses synthetic examples and does not include any real organizational hostnames, internal IP addresses, DNS inventories, credentials, or monitoring results. It is not an official product of the internship organization.

## Features

### External DNS & web checks
- Resolve hostnames and check HTTP(S) availability.
- Measure end-to-end HTTP response time and report status codes.
- Detect likely login forms using HTML heuristics.
- Score observed availability and export a formatted Excel report.
- Run concurrent checks with configurable timeouts and worker counts.

**Interpretation:** The external score is a custom heuristic, **not** a DNS health standard or security rating. Redirects are followed, so the final HTTP response code is evaluated. Login-form detection is heuristic and may yield false positives. TLS certificate validation is enabled; invalid HTTPS certificates are reported without silently disabling verification.

### Internal DNS checks
- Query a **specified, authorized DNS resolver** for records listed in a local CSV file.
- Verify A, AAAA, CNAME, MX, TXT, and PTR records against optional expected values.
- Report resolution results, mismatches, timeouts, and query latency in JSON.
- Does not perform host discovery, subnet scans, or automatic inventory collection.

**Important:** Internal DNS is a separate portfolio module. It is not presented as a recovered original internship implementation. Use only in networks where you have permission. The real internal DNS inventory is deliberately not included.

## Installation

Requires Python 3.10+.

```bash
python -m venv .venv
# Windows PowerShell:
.venv\\Scripts\\Activate.ps1
pip install -r requirements.txt
```

## External checks

The original script reads an `.xlsx` file with a header row and URLs in **column B**. Create your own authorized workbook using that layout, e.g. `ZONE | Dış DNS`.

```bash
python src/external_dns_checker.py --excel my_external_dns.xlsx --output external_dns_results.xlsx --timeout 8 --workers 5
```

The original organizational inventory spreadsheet is excluded from this repository. Only test endpoints you are permitted to monitor.

## Internal DNS checks

```bash
python src/internal_dns_checker.py --input examples/internal_dns_template.csv --resolver 192.0.2.53 --output internal_dns_results.json
```

The resolver and records in this example are **documentation-only TEST-NET addresses**, not a working DNS service. Replace them with a DNS server and hostnames that you are authorized to query. Do not commit the resulting inventory or report.

Input CSV columns: `hostname`, `record_type`, `expected_value` (optional).

## Tests

```bash
python -m unittest discover -s tests -v
python -m compileall -q src
```

## Repository layout

- `src/external_dns_checker.py` — adapted external checker
- `src/internal_dns_checker.py` — independent internal DNS record checks
- `examples/` — synthetic templates only
- `tests/` — offline unit tests
- `docs/SECURITY.md` — publication and authorization guidance

## Limitations

This is a command-line monitoring toolkit, not a web dashboard. It does not implement LDAP authentication, long-term monitoring, alerting, or production-grade observability. Results reflect the time and network vantage point of execution.

## Acknowledgment

Developed as a portfolio presentation of network internship learning, with publication-safe examples. No endorsement by the host organization is implied.
