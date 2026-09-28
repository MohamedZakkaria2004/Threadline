# Roles and permissions

Authorization combines **role, department, ownership, and workflow state**. The model and UI are not permission authorities: the API reloads roles/departments from SQLite, and write paths recheck authority within their transactions.

## Demo accounts

| Username | Role | Department | Purpose |
|---|---|---|---|
| `employee` | Employee | IT | Everyday knowledge, personal requests and reports |
| `hr` | Employee | HR | Same role with different departmental knowledge |
| `manager` | Manager | Operations | Leadership knowledge and departmental oversight |
| `admin` | Admin | All | Document management and platform oversight |

Fresh installs generate passwords locally. Credentials and sessions are excluded from Git. These accounts are not a tenant or identity-provider implementation.

## Capability matrix

| Capability | Employee | Manager | Admin |
|---|---|---|---|
| Company-wide internal documents | Yes | Yes | Yes |
| Own-department internal documents | Yes | Yes | Yes |
| Other-department documents | No | No | Yes |
| Company-wide / own-department leadership sources | No | Yes | Yes |
| Upload / replace documents | No | No | Yes |
| Request supported local actions | Yes | Yes | Yes; eligible reviewer must exist when needed |
| Read conversations / detailed action activity | Own only | Own only | Own only |
| Generate / view / download reports | Own only; sources rechecked | Own only; sources rechecked | Own only; sources rechecked |
| View / update tickets | Own | Own + eligible departmental tickets | All |
| Review sensitive requests | No | Other users in eligible department | Other users across departments |
| Approve own request | No | No | No |
| Personal insights / feedback | Yes | Yes | Yes |
| Platform aggregates / redacted audit view | No | No | Yes |
| Quality lab / human review judgments | No | No | Yes |
| Read-only prompt registry | No | No | Yes |
| Business-case scenarios | Yes | Yes | Yes |

Manager review and ticket visibility require both the request-time department and requester's current department to match the manager's. An access approval after a requester changes department is rejected and must be resubmitted.

## Boundaries to demonstrate

- Operations Manager can retrieve the fictional contingency reserve; IT Employee receives insufficient evidence. The restricted passage must not reach the Employee model context.
- Admin can inspect submitted approval requests and tickets, but cannot read another user's conversation or private report. Inaccessible private conversation IDs return 404.
- Approval of `request_access` creates an `access_review` ticket. It changes no role, department, or external workspace permission.
- The single demo Admin cannot approve their own sensitive request. No eligible independent reviewer means a clear failure rather than indefinite waiting.
- Source access is rechecked before answer publication and report view/export. Downloaded files cannot be revoked.

The standard demo has no Employee in Operations. Use Admin to review the default IT Employee; demonstrate Manager departmental review through a controlled test fixture. Do not imply that the Manager can approve an IT request.

Implementation: [HTTP guards](../app/main.py), [document scope](../app/knowledge.py), [decisions](../app/service.py), [metrics scope](../app/insights.py). Tests: [API](../tests/test_api.py), [operations](../tests/test_operations.py), [audit boundaries](../tests/test_e2e_audit_regressions.py).
