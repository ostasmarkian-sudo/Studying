-- Telegram bot: its users and what each of them asked to monitor.
--
-- Kept apart from core/schema.sql on purpose. The bot runs this file on every
-- start, and core/schema.sql carries ALTER TABLE cars, which waits for an
-- ACCESS EXCLUSIVE lock: a bot restart must not queue up behind a scraper.
-- Nothing here touches cars, and nothing has an FK to it, for the same reason
-- car_history has none.


CREATE TABLE IF NOT EXISTS bot_users (
    tg_user_id     bigint PRIMARY KEY,
    username       text,
    first_name     text,
    language       text,

    -- For whoever sends the notifications: set it when Telegram answers 403,
    -- the user blocked the bot. /start clears it again.
    is_blocked     boolean NOT NULL DEFAULT false,

    created_at     timestamptz NOT NULL DEFAULT now(),
    last_active_at timestamptz NOT NULL DEFAULT now()
);


-- A saved set of search parameters: "tell me about new ads like this".
CREATE TABLE IF NOT EXISTS search_subscriptions (
    subscription_id bigserial PRIMARY KEY,
    tg_user_id      bigint NOT NULL REFERENCES bot_users ON DELETE CASCADE,

    -- Keys are the names of the cars columns, so a filter maps onto SQL with
    -- no translation table:
    --   a scalar    -> column = value
    --                  {"brand_id": 84, "gearbox": "Автомат", "is_dealer": false}
    --   [min, max]  -> both ends included, null is an open end
    --                  {"year": [2016, null], "price_usd": [null, 12000]}
    -- Take column names from a fixed list when building the query, not from
    -- these keys: a key must never reach the SQL text.
    filters         jsonb NOT NULL,

    -- What the user saw when saving, ready for a "my monitors" list.
    summary         text NOT NULL,

    is_active       boolean NOT NULL DEFAULT true,
    created_at      timestamptz NOT NULL DEFAULT now(),

    -- Starts at now(): a fresh subscription must not dump every car already
    -- on sale. Compare it with cars.first_seen_at rather than listed_at:
    -- listed_at is the bump time, so a bumped old ad would pass for a new one.
    last_checked_at timestamptz NOT NULL DEFAULT now(),

    -- jsonb compares by value regardless of key order, so saving the same
    -- parameters twice hits this key instead of adding a duplicate.
    UNIQUE (tg_user_id, filters)
);

CREATE INDEX IF NOT EXISTS idx_subs_active ON search_subscriptions (last_checked_at) WHERE is_active;


-- One particular ad the user follows, and which of its changes to report.
CREATE TABLE IF NOT EXISTS car_watches (
    watch_id        bigserial PRIMARY KEY,
    tg_user_id      bigint NOT NULL REFERENCES bot_users ON DELETE CASCADE,
    car_id          bigint NOT NULL,

    -- price, price_down, status and mileage are read from car_history (mileage
    -- inside snapshot). relist is a new car_id with the same fingerprint.
    events          text[] NOT NULL CHECK (
        cardinality(events) > 0
        AND events <@ ARRAY['price', 'price_down', 'status', 'mileage', 'relist']
    ),

    is_active       boolean NOT NULL DEFAULT true,
    created_at      timestamptz NOT NULL DEFAULT now(),
    -- Compare with car_history.recorded_at.
    last_checked_at timestamptz NOT NULL DEFAULT now(),

    UNIQUE (tg_user_id, car_id)
);

CREATE INDEX IF NOT EXISTS idx_watches_car ON car_watches (car_id) WHERE is_active;


-- What has already been sent for a subscription.
--
-- The notifier cannot rely on last_checked_at alone. cars.first_seen_at holds
-- the start time of the scraper transaction, and the row only becomes visible
-- when that transaction commits seconds later, so a check that ran in between
-- would step over it forever. The notifier therefore looks back further than
-- last_checked_at, and this table is what keeps the overlap from resending.
CREATE TABLE IF NOT EXISTS sent_cars (
    subscription_id bigint NOT NULL REFERENCES search_subscriptions ON DELETE CASCADE,
    car_id          bigint NOT NULL,
    sent_at         timestamptz NOT NULL DEFAULT now(),
    PRIMARY KEY (subscription_id, car_id)
);

-- first_seen_at of a car never changes, so once a car falls out of the look-back
-- window it can never come back into it: old rows here are dead weight.
CREATE INDEX IF NOT EXISTS idx_sent_cars_time ON sent_cars (sent_at);
