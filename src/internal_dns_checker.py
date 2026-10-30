#!/usr/bin/env python3
"""Read-only DNS resolution checks for explicitly supplied internal records.

Only run with authorization on the target network. No discovery or subnet scanning.
Input CSV: hostname,record_type,expected_value (expected_value optional).
"""
import argparse
import csv
import ipaddress
import json
import sys
import time
from datetime import datetime, timezone

try:
    import dns.resolver
    import dns.exception
except ImportError:
    sys.exit('Install dependencies: pip install -r requirements.txt')

ALLOWED = {'A', 'AAAA', 'CNAME', 'MX', 'TXT', 'PTR'}

def check_record(resolver, hostname, record_type, expected=''):
    start = time.monotonic()
    try:
        answers = resolver.resolve(hostname, record_type, search=False)
        values = [str(a).rstrip('.') for a in answers]
        ok = not expected or expected.rstrip('.').casefold() in [v.casefold() for v in values]
        return {'status': 'PASS' if ok else 'MISMATCH', 'answers': values,
                'latency_ms': round((time.monotonic()-start)*1000, 1)}
    except dns.exception.Timeout:
        return {'status': 'TIMEOUT', 'answers': [], 'latency_ms': None}
    except dns.resolver.NXDOMAIN:
        return {'status': 'NXDOMAIN', 'answers': [], 'latency_ms': None}
    except dns.resolver.NoAnswer:
        return {'status': 'NO_ANSWER', 'answers': [], 'latency_ms': None}
    except dns.exception.DNSException as exc:
        return {'status': type(exc).__name__, 'answers': [], 'latency_ms': None}

def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--input', required=True, help='Private CSV file of approved DNS records')
    p.add_argument('--resolver', required=True, help='Authorized DNS server IP address')
    p.add_argument('--output', default='internal_dns_results.json')
    p.add_argument('--timeout', type=float, default=2.0)
    args = p.parse_args()
    ipaddress.ip_address(args.resolver)
    if args.timeout <= 0: p.error('--timeout must be positive')
    resolver = dns.resolver.Resolver(configure=False)
    resolver.nameservers = [args.resolver]
    resolver.timeout = args.timeout
    resolver.lifetime = args.timeout
    results = []
    with open(args.input, newline='', encoding='utf-8-sig') as f:
        reader = csv.DictReader(f)
        if not {'hostname','record_type'}.issubset(reader.fieldnames or []):
            p.error('CSV must contain hostname and record_type columns')
        for row in reader:
            hostname = (row.get('hostname') or '').strip()
            kind = (row.get('record_type') or '').strip().upper()
            expected = (row.get('expected_value') or '').strip()
            if not hostname or kind not in ALLOWED:
                p.error(f'Invalid record: {hostname!r}, {kind!r}')
            result = check_record(resolver, hostname, kind, expected)
            results.append({'hostname': hostname, 'record_type': kind,
                            'expected_value': expected, **result})
            print(f'{hostname} {kind}: {result["status"]}')
    report = {'checked_at': datetime.now(timezone.utc).isoformat(),
              'resolver': args.resolver, 'results': results}
    with open(args.output, 'w', encoding='utf-8') as f:
        json.dump(report, f, ensure_ascii=False, indent=2)
    print(f'Report saved: {args.output}')

if __name__ == '__main__': main()
