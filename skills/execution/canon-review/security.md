# Security angle

Review only when the project or feature is security-related or the user asked. Rate severity by exploitability and impact under the project's real deployment, not a worst case it never faces.

## Trust boundaries

Map where untrusted data enters (requests, files, environment, messages, third-party responses) and follow it inward:

- Validation and normalization at the boundary.
- Authentication and authorization on every entry point, including internal and admin routes.
- Injection: SQL, shell, template, path traversal, deserialization of untrusted data.
- Server-side requests to user-supplied URLs.

## Secrets and data

- Secrets in source, config, logs, error messages or test fixtures.
- Personal or sensitive data in logs and error responses.
- Cryptography: home-made primitives, weak algorithms, missing integrity checks, predictable randomness for tokens.

## Dependencies

Run the ecosystem's audit tool when available (`npm audit`, `pip-audit`, `cargo audit`, `govulncheck`) and report only advisories reachable from the scope.

Quote evidence with secrets replaced by `<REDACTED>`.
