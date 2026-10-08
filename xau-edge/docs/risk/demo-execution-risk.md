# Demo execution: risks and controls

| Risk | Control | Evidence |
|---|---|---|
| An order on a live account | `Settings` rejects the live flag; DEMO check at connect, at every gate, and at the last look before sending; account whitelist required | `tests/unit/brokers/test_executor.py`, `test_connect.py`, `test_config.py` |
| An order nobody approved | the executor sends only intents the bridge recorded as approved for real submission; dry-run approvals do not count | `test_an_intent_the_bridge_never_approved_is_refused` |
| Trading with no edge | evidence gate (ADR-0017) closes every BUY/SELL until a configuration passes all periods | `signals/` tests; every real cycle so far is WAIT |
| Duplicate orders (restart, crash, retry) | submission row written before sending; same intent is never sent twice | `test_the_same_intent_is_never_sent_twice_even_after_its_position_is_closed` |
| Unknown order state | kill switch trips, no retry; ambiguous retcodes resolved by lookup | `test_an_ambiguous_retcode_*`, `test_no_answer_*` |
| Naked position | the intent's stop/target are what is recorded; a mismatch closes the position at once and stops the bot | `test_a_broker_that_strips_the_stop_*` |
| Loss limits reset by a restart | account baseline persisted; daily risk and loss streak derived from state and deal history | `test_state_baseline.py`, `test_reconcile_closed.py` |
| Stale price or intent | tick age, intent age, expiry and the symbol's own point bound the entry | `test_a_stale_tick_is_refused`, `test_stale_and_expired_intents_are_refused` |
| State changes between check and send | last-look recheck after the submission row | `test_the_kill_switch_tripped_after_the_gates_*` |
| Manual interference | a manual position on the symbol stops the bot; the bot closes only its own positions | `test_a_position_with_the_bot_magic_but_unknown_*` |
| Secrets in logs | redaction in logs and journal; trading password in a separate variable, never printed | `test_secret_like_fields_are_redacted`, `test_the_password_is_not_in_the_settings_repr` |

Residual risks: the real `order_send` path is exercised only against a fake terminal until the trading
password is supplied; demo fills differ from live fills; the economic calendar is not supplied (all
signals WAIT); the kill switch does not close positions by design; a second process on another machine
is not prevented by the local lock.
