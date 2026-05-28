# Security And Data Policy

Do not open issues or pull requests containing private biological, operational, or customer data.

Never include:

- API keys, provider tokens, or registry credentials
- private strain details
- unpublished sequences
- customer batch records
- confidential media formulations
- proprietary process histories
- private supplier quotes

Use synthetic examples or public data with source and transformation notes.

If you discover a security issue in the code or release process, report it privately to the repository owner via GitHub's [private vulnerability reporting](https://docs.github.com/en/code-security/security-advisories/guidance-on-reporting-and-writing-information-about-vulnerabilities/privately-reporting-a-security-vulnerability) rather than posting sensitive details in a public issue.

The repo also ships a required `make secret-scan` target (gitleaks) and CI secret scanning for pull requests and `main` pushes. Local contributors should run `make public-ready` before opening a PR; see [`CONTRIBUTING.md`](CONTRIBUTING.md).
