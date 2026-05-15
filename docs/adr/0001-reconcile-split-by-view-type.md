# Reconcile is split by view type, not one parser for all

Marrow lets Lumi hand-edit rendered md and reconciles it back to SQLite. We decided that reconcile is split by view type: structured views (Open Threads, milestone, vocab, pit, alerts) reconcile by a visible per-row id (id present = update, id deleted = delete, no id = insert), while narrative views (diary, goose-bites) reconcile only by date-heading block (edit body = whole-content overwrite by id; delete the whole heading block = delete that day) and do not support splitting narrative into new rows. Re-organising narrative history goes through the `ny` CLI or telling Claude, not md edits.

## Considered Options

- One uniform reconcile parser over all views with a hidden HTML-comment anchor — rejected: free-text diff on narrative (Chinese diary) is structurally fragile, cannot tell an intended row-delete from a render artifact, and silently risks dropping system-only columns. Workable but never product-level.

## Consequences

- "Edit md directly" is the primary correction path for structured views but a secondary one for narrative views; the primary narrative path is the CLI / conversation.
- Anchor character format and per-view render template stay Pending; the reconcile semantics above are fixed.
