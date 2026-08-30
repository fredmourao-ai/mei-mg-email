-- Superseded: this migration used an obsolete authorization gate.
-- The current eligibility contract is enforced by the queue/replenisher and
-- by the canonical live envio trigger.
set search_path = mei_email, public;

select 1;
