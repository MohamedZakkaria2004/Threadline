# Local verification output

Generated logs, test reports, evaluation exports and snapshot-path records belong
here and are excluded from Git. They can contain machine paths, account context
or document content. Do not force-add them, credentials, databases or snapshots.

Historical engineering reviews refer to local filenames as provenance; those
files are deliberately absent from a fresh checkout. Selected reviewed,
path-free historical summaries are published in
[docs/evidence](../docs/evidence/README.md). The source corpus, gold questions,
tests and scripts remain available to reproduce validation. Running a suite
creates new results; it does not recreate the exact historical model outputs.

The historical consolidation scripts (`audit_final_status`, `summarize_e2e_audit`,
and `review_audit_initial`) need their referenced local run outputs. Use the
[repository verification commands](../docs/EVALUATION.md) on a fresh checkout.
