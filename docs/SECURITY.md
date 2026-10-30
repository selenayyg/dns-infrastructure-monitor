# Security and publication guidance

- Do not commit the original `dis_dns.xlsx` inventory or any internal DNS export.
- Never publish internal hostnames, private IP allocations, resolver addresses, LDAP configuration, authentication tokens, or actual scan results.
- Run checks only against systems and resolvers you are authorized to test.
- Keep internal inventory and output files outside the repository; `.gitignore` is a backup safeguard, not a substitute for review.
- TLS verification must remain enabled. Do not bypass certificate failures.
- Review Git changes before every push (`git status`, `git diff --cached`).
