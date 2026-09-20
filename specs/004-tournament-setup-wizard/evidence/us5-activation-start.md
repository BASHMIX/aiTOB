# US5 activation and provider start evidence

Local materialization and activation are implemented as separate workspace
transactions. Activation queues one idempotent initial-sync outbox event after
the local status commit. Provider remote-start adapters intentionally return
`remote_start_contract_unverified` and perform no undocumented mutation; this
is the safe result until each provider documents a supported write capability.
