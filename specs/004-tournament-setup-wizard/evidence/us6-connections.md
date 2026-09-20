# US6 connection administration evidence

Workspace integration accounts expose safe provider/health metadata and support
credential replacement, enable/disable, and removal. AI connections use the
same encrypted account store, retain immutable assistant controls, and degrade
health when a current key fails. No endpoint returns secret material. The full
backend regression suite passed with these lifecycle changes enabled.
