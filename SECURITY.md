# Security scope

Threadline is a local portfolio prototype. Run it on loopback on a trusted
computer with fictional or public documents. Do not expose port 8765 through a
public tunnel, reverse proxy or internet-facing host. Publishing the source
repository does not publish or deploy the running application.

First startup generates per-account demo passwords in the configured data
directory. Passwords are hashed in SQLite, but the local credentials helper,
documents, reports and backups are plaintext. Keep that directory outside the
repository and cloud sync. Never commit credentials, session cookies, runtime
databases, raw evaluation exports or snapshot payloads. Review any report before
sharing it. The source-controlled private/injection fixtures are explicitly
synthetic tests, not real credentials or confidential data.

The application applies document permissions before retrieval, checks canonical
SQL evidence after inference, limits tools to local operations, and requires an
independent reviewer for sensitive actions. Access approval creates a review
ticket; it does not grant system permissions. These controls do not guarantee
semantic correctness or resistance to every prompt injection. Read the evidence
and use independent human review before relying on policy answers.

Before a real deployment, replace demo identity with enterprise authentication,
define transport and storage protection, test capacity and recovery, and obtain
domain-owner approval. Current verified limitations and test scope are recorded
in the [engineering audit](docs/E2E_AUDIT.md).

Report security findings through
[GitHub private vulnerability reporting](https://github.com/MohamedZakkaria2004/Threadline/security/advisories/new).
Include the affected commit, role/scope, public or synthetic reproduction, and
expected versus actual behavior. Do not put passwords, private source material
or usable exploit credentials into public issues. This portfolio project does
not promise a production support SLA. If private reporting is unavailable,
withhold sensitive details until a private channel is available.
